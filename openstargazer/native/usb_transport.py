# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import logging

import usb.core
import usb.util

from openstargazer.native import ttp

log = logging.getLogger(__name__)

VENDOR_ID = 0x2104
PRODUCT_ID_RUNTIME = 0x0313
PRODUCT_ID_BOOTLOADER = 0x0102

INTERFACE_NUM = 0
EXPECTED_EP_IN = 0x83
EXPECTED_EP_OUT = 0x05
READ_SIZE = 64 * 1024

MAX_FRAME_LEN = 256 * 1024
READ_TIMEOUT_MS = 100
WRITE_TIMEOUT_MS = 1000
CONTROL_TIMEOUT_MS = 1000

CTRL_BM_REQUEST_TYPE = 0x41
CTRL_REQ_SESSION_OPEN = 0x41
CTRL_REQ_SESSION_CLOSE = 0x42


class Et5NotFoundError(RuntimeError):
    ...


class Et5BootloaderModeError(RuntimeError):
    ...


class Et5PermissionError(RuntimeError):
    ...


def _is_timeout(exc: usb.core.USBError) -> bool:
    return exc.errno == 110 or "timeout" in str(exc).lower()


class Et5UsbTransport:
    def __init__(self) -> None:
        self._dev: usb.core.Device | None = None
        self._ep_in = None
        self._ep_out = None
        self._detached_kernel_driver = False
        self._recv_buffer = bytearray()

    def open(self) -> None:
        dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID_RUNTIME)
        if dev is None:
            bootloader = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID_BOOTLOADER)
            if bootloader is not None:
                raise Et5BootloaderModeError(
                    "ET5 is stuck in bootloader mode (PID 0x0102) — unplug and replug the device"
                )
            raise Et5NotFoundError(
                f"No ET5 found (VID={VENDOR_ID:#06x} PID={PRODUCT_ID_RUNTIME:#06x})"
            )

        try:
            if dev.is_kernel_driver_active(INTERFACE_NUM):
                dev.detach_kernel_driver(INTERFACE_NUM)
                self._detached_kernel_driver = True
        except NotImplementedError:
            pass
        except usb.core.USBError as exc:
            if exc.errno == 13:
                raise Et5PermissionError(
                    "Access to ET5 denied — check the udev rule (udev/70-openstargazer.rules)"
                ) from exc
            raise

        try:
            if dev.get_active_configuration() is None:
                dev.set_configuration()
        except usb.core.USBError as exc:
            if exc.errno == 13:
                raise Et5PermissionError(
                    "Access to ET5 denied — check the udev rule (udev/70-openstargazer.rules)"
                ) from exc
            if exc.errno == 2:
                dev.set_configuration()
            else:
                raise

        cfg = dev.get_active_configuration()
        intf = cfg[(INTERFACE_NUM, 0)]
        usb.util.claim_interface(dev, INTERFACE_NUM)

        ep_in = usb.util.find_descriptor(
            intf, custom_match=lambda e: e.bEndpointAddress == EXPECTED_EP_IN
        )
        ep_out = usb.util.find_descriptor(
            intf, custom_match=lambda e: e.bEndpointAddress == EXPECTED_EP_OUT
        )
        if ep_in is None or ep_out is None:
            log.warning(
                "Expected endpoints 0x%02x/0x%02x not found — falling back to "
                "direction matching (firmware variant?)",
                EXPECTED_EP_IN, EXPECTED_EP_OUT,
            )
            ep_in = ep_in or usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN,
            )
            ep_out = ep_out or usb.util.find_descriptor(
                intf,
                custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT,
            )
        if ep_in is None or ep_out is None:
            raise RuntimeError("ET5 endpoints not found in descriptor")

        log.info(
            "ET5 endpoints: IN=0x%02x (bmAttributes=0x%02x) OUT=0x%02x (bmAttributes=0x%02x)",
            ep_in.bEndpointAddress, ep_in.bmAttributes,
            ep_out.bEndpointAddress, ep_out.bmAttributes,
        )

        self._dev = dev
        self._ep_in = ep_in
        self._ep_out = ep_out
        self._recv_buffer.clear()

        self._dev.ctrl_transfer(
            CTRL_BM_REQUEST_TYPE, CTRL_REQ_SESSION_OPEN, 0, 0, None, timeout=CONTROL_TIMEOUT_MS
        )

    def close(self) -> None:
        if self._dev is not None:
            try:
                self._dev.ctrl_transfer(
                    CTRL_BM_REQUEST_TYPE, CTRL_REQ_SESSION_CLOSE, 0, 0, None, timeout=CONTROL_TIMEOUT_MS
                )
            except usb.core.USBError:
                log.warning("Session-close control transfer failed (best effort)")
            try:
                usb.util.release_interface(self._dev, INTERFACE_NUM)
            except usb.core.USBError:
                pass
            if self._detached_kernel_driver:
                try:
                    self._dev.attach_kernel_driver(INTERFACE_NUM)
                except (usb.core.USBError, NotImplementedError):
                    pass
            usb.util.dispose_resources(self._dev)
        self._dev = None
        self._ep_in = None
        self._ep_out = None
        self._detached_kernel_driver = False
        self._recv_buffer.clear()

    def send(self, ttp_frame: bytes) -> None:
        assert self._ep_out is not None, "send() called before open()"
        wrapped = ttp.wrap_out(ttp_frame)
        self._ep_out.write(wrapped, timeout=WRITE_TIMEOUT_MS)

    def recv(self, timeout_ms: int = READ_TIMEOUT_MS) -> bytes | None:
        assert self._ep_in is not None, "recv() called before open()"
        frame = self._pop_buffered_frame()
        if frame is not None:
            return frame
        try:
            chunk = self._ep_in.read(READ_SIZE, timeout=timeout_ms)
        except usb.core.USBError as exc:
            if _is_timeout(exc):
                return None
            raise
        self._recv_buffer.extend(bytes(chunk))
        return self._pop_buffered_frame()

    def _pop_buffered_frame(self) -> bytes | None:
        if len(self._recv_buffer) < ttp.ENVELOPE_LEN:
            return None
        declared_len = int.from_bytes(self._recv_buffer[4:8], "little")
        if (
            self._recv_buffer[0] != ttp.DIR_IN
            or declared_len < ttp.ENVELOPE_LEN + ttp.TTP_HEADER_LEN
            or declared_len > MAX_FRAME_LEN
        ):
            log.warning(
                "Implausible IN envelope (dir=0x%02x, len=%d) — dropping %d buffered bytes",
                self._recv_buffer[0], declared_len, len(self._recv_buffer),
            )
            self._recv_buffer.clear()
            return None
        if len(self._recv_buffer) < declared_len:
            return None

        frame = bytes(self._recv_buffer[:declared_len])
        del self._recv_buffer[:declared_len]
        return frame
