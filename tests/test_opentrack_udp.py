"""Unit tests for OpenTrack UDP packet encoding."""
import struct
import pytest

from openstargazer.engine.api import TrackingFrame
from openstargazer.output.opentrack_udp import OpenTrackUDPOutput, _STRUCT


def _make_frame(**kwargs) -> TrackingFrame:
    defaults = dict(
        gaze_x=0.5, gaze_y=0.5, gaze_valid=True,
        head_x=10.0, head_y=-5.0, head_z=600.0, head_pos_valid=True,
        yaw=15.0, pitch=-8.0, roll=2.0, head_rot_valid=True,
        timestamp_us=1_000_000,
    )
    defaults.update(kwargs)
    return TrackingFrame(**defaults)


def test_packet_size():
    """UDP packet must be exactly 48 bytes."""
    frame = _make_frame()
    packet = _STRUCT.pack(frame.head_x, frame.head_y, frame.head_z,
                          frame.yaw, frame.pitch, frame.roll)
    assert len(packet) == 48


def test_packet_encoding():
    """Values round-trip through pack/unpack correctly."""
    frame = _make_frame(head_x=12.5, head_y=-3.25, head_z=550.0,
                        yaw=22.0, pitch=-5.0, roll=1.5)
    packet = _STRUCT.pack(frame.head_x, frame.head_y, frame.head_z,
                          frame.yaw, frame.pitch, frame.roll)
    x, y, z, yaw, pitch, roll = OpenTrackUDPOutput.decode_packet(packet)

    assert abs(x   - frame.head_x) < 1e-9
    assert abs(y   - frame.head_y) < 1e-9
    assert abs(z   - frame.head_z) < 1e-9
    assert abs(yaw - frame.yaw)    < 1e-9
    assert abs(pitch - frame.pitch) < 1e-9
    assert abs(roll  - frame.roll)  < 1e-9


def test_decode_wrong_size():
    """decode_packet should raise for wrong-size buffers."""
    with pytest.raises(ValueError):
        OpenTrackUDPOutput.decode_packet(b"\x00" * 47)
    with pytest.raises(ValueError):
        OpenTrackUDPOutput.decode_packet(b"\x00" * 49)


def test_little_endian():
    """Verify packet uses little-endian byte order."""
    # Pack value 1.0 as float64 little-endian
    packet = _STRUCT.pack(1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    # Little-endian 1.0 double: 3F F0 00 00 00 00 00 00 → LE: 00 00 00 00 00 00 F0 3F
    expected_first_double = struct.pack("<d", 1.0)
    assert packet[:8] == expected_first_double
