"""
osg-daemon – main entry point.

Starts the asyncio event loop, wires up the tracker → pipeline → outputs
chain, starts the IPC server, and handles SIGTERM / SIGINT cleanly.

Usage:
    osg-daemon [--mock] [--config PATH] [--verbose]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys

log = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="osg-daemon",
                                description="Tobii Eye Tracker 5 Linux daemon")
    p.add_argument("--mock",    action="store_true",
                   help="Use synthetic data instead of real hardware")
    p.add_argument("--config",  metavar="PATH",
                   help="Path to config.toml (default: ~/.config/openstargazer/config.toml)")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        level=level,
    )


async def _async_main(args: argparse.Namespace) -> None:
    from openstargazer.config.settings import Settings
    from openstargazer.daemon.ipc_server import IPCServer
    from openstargazer.daemon.pipeline import DataPipeline

    # ── Load config ───────────────────────────────────────────────────
    settings = Settings.load(args.config)
    log.info("Config loaded from %s", settings.config_path)

    # ── Tracker ───────────────────────────────────────────────────────
    loop = asyncio.get_event_loop()
    if args.mock:
        from openstargazer.daemon.tracker import MockTrackerManager
        tracker = MockTrackerManager(loop)
        log.info("Using MockTrackerManager (--mock)")
    else:
        from openstargazer.daemon.tracker import TrackerManager
        tracker = TrackerManager(loop)

    # ── Pipeline ──────────────────────────────────────────────────────
    pipeline = DataPipeline(settings)

    if settings.output.opentrack_udp.enabled:
        from openstargazer.output.opentrack_udp import OpenTrackUDPOutput
        udp = OpenTrackUDPOutput(
            host=settings.output.opentrack_udp.host,
            port=settings.output.opentrack_udp.port,
        )
        pipeline.add_output(udp)

    if settings.output.freetrack_shm.enabled:
        from openstargazer.output.freetrack_shm import FreeTrackSHMOutput
        pipeline.add_output(FreeTrackSHMOutput())

    tracker.add_consumer(pipeline.process)

    # ── IPC Server ────────────────────────────────────────────────────
    ipc = IPCServer(tracker=tracker, pipeline=pipeline, settings=settings)

    # ── Start everything ──────────────────────────────────────────────
    await pipeline.start()
    await tracker.start()
    await ipc.start()

    log.info("osg-daemon running. Send SIGTERM or SIGINT to stop.")

    stop_event = asyncio.Event()

    def _on_signal(*_):
        stop_event.set()

    loop.add_signal_handler(signal.SIGTERM, _on_signal)
    loop.add_signal_handler(signal.SIGINT,  _on_signal)

    await stop_event.wait()

    log.info("Shutting down…")
    await ipc.stop()
    await tracker.stop()
    await pipeline.stop()
    log.info("osg-daemon stopped")


def main() -> None:
    args = _parse_args()
    _setup_logging(args.verbose)
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
