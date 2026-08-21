# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (c) 2026 1psconstructor
from __future__ import annotations

import argparse
import sys

from openstargazer.i18n import t
from openstargazer.ipc.client import IPCClient, IPCError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="osg-recenter",
        description="Set the current head pose as the origin for the outputs.",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="drop the origin instead of setting it",
    )
    args = parser.parse_args(argv)

    from openstargazer.i18n import apply_saved_language
    apply_saved_language()

    client = IPCClient()
    try:
        if args.clear:
            client.clear_recenter()
            print(t("cli.recenter.cleared"))
            return 0

        result = client.recenter()
        pose = result.get("neutral_pose", {})
        print(
            t(
                "cli.recenter.done",
                yaw=f"{pose.get('yaw', 0.0):.1f}",
                x=f"{pose.get('x', 0.0):.0f}",
                z=f"{pose.get('z', 0.0):.0f}",
            )
        )
        return 0
    except IPCError as exc:
        print(t("cli.recenter.failed", reason=str(exc)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
