# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import argparse
import asyncio
import faulthandler
import logging
import os
import signal
import sys

log = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="osg-daemon",
                                description="Tobii Eye Tracker 5 Linux daemon")
    p.add_argument("--mock",    action="store_true",
                   help="Use synthetic data instead of real hardware "
                        "(short for --source mock)")
    p.add_argument("--source",  metavar="NAME", default=None,
                   help="Override the configured input source. "
                        "--list-sources prints the names.")
    p.add_argument("--backend", choices=["native", "stream-engine"], default=None,
                   help="Deprecated spelling of --source, kept for existing "
                        "scripts and service units")
    p.add_argument("--list-sources", action="store_true",
                   help="List the available input sources and exit")
    p.add_argument("--dry-run", action="store_true",
                   help="Build source, pipeline and outputs, report what was "
                        "wired up, then exit without opening a device")
    p.add_argument("--config",  metavar="PATH",
                   help="Path to config.toml (default: ~/.config/openstargazer/config.toml)")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def _chosen_source(args: argparse.Namespace, settings) -> str:
    from openstargazer.config.settings import BACKEND_TO_SOURCE

    if args.mock:
        return "mock"
    if args.source:
        return args.source
    if args.backend:
        return BACKEND_TO_SOURCE[args.backend]
    return settings.input.source


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

    settings = Settings.load(args.config)
    log.info("Config loaded from %s", settings.config_path)

    from openstargazer.input.registry import create_source

    loop = asyncio.get_event_loop()
    source_name = _chosen_source(args, settings)
    tracker = create_source(source_name, settings=settings, loop=loop)
    log.info("Input source: %s", source_name)

    pipeline = DataPipeline(settings)

    from openstargazer.output.registry import create_outputs

    outputs = create_outputs(settings.output.targets)
    for out in outputs:
        pipeline.add_output(out)
    log.info("Outputs: %s", ", ".join(o.name for o in outputs) or "none")

    tracker.add_consumer(pipeline.process)

    if args.dry_run:
        print(f"source:  {source_name}")
        print(f"outputs: {', '.join(o.name for o in outputs) or 'none'}")
        print(f"config:  {settings.config_path}")
        print("dry run: nothing was started")
        return

    from openstargazer.daemon.calibration import CalibrationController
    calibration = CalibrationController(tracker, settings)

    ipc = IPCServer(
        tracker=tracker,
        pipeline=pipeline,
        settings=settings,
        calibration=calibration,
    )

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


def _print_sources() -> None:
    from openstargazer.input.registry import available_sources

    for name, cls in sorted(available_sources().items()):
        print(f"  {name:<20} {cls.description}")


def main() -> None:
    args = _parse_args()
    _setup_logging(args.verbose)
    faulthandler.enable()
    if args.list_sources:
        _print_sources()
        return
    try:
        asyncio.run(_async_main(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
