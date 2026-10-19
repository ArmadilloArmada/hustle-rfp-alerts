"""CLI: run alert pipeline, approve packs, export email drafts (never auto-send)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import approve as approve_mod
from . import export as export_mod
from .pipeline import ROOT, run

logger = logging.getLogger(__name__)


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("-v", "--verbose", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src",
        description=(
            "RFP / job alert packs: fetch → filter → write out/alerts-*.md, "
            "then human-approve and export email drafts (never auto-send)."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    # Default / run
    run_p = sub.add_parser("run", help="Fetch feeds, filter, write out/alerts-YYYY-MM-DD.md")
    run_p.add_argument(
        "-c",
        "--config",
        type=Path,
        default=ROOT / "config.yaml",
        help="Path to config.yaml (default: ./config.yaml)",
    )
    run_p.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=ROOT / "out",
        help="Output directory (default: ./out)",
    )
    _add_common(run_p)

    ap = sub.add_parser("approve", help="Mark out/alerts-*.md as human-reviewed")
    ap.add_argument("path", type=Path, help="Path to out/alerts-YYYY-MM-DD.md")
    _add_common(ap)

    ex = sub.add_parser(
        "export",
        help="Export email-draft HTML + mailto (+ optional Buttondown draft). Requires --approve.",
    )
    ex.add_argument("path", type=Path, help="Path to out/alerts-YYYY-MM-DD.md")
    ex.add_argument(
        "--approve",
        action="store_true",
        help="Required. Confirms you reviewed the pack. Refuses to export without this flag.",
    )
    ex.add_argument(
        "--mailto-to",
        default="",
        help="Optional recipient for the mailto: link (default: empty To:)",
    )
    ex.add_argument(
        "--no-buttondown",
        action="store_true",
        help="Skip Buttondown even if BUTTONDOWN_API_KEY is set",
    )
    ex.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=None,
        help="Directory for email-draft-* files (default: same dir as the alert pack)",
    )
    _add_common(ex)

    # Top-level flags for backward-compatible `python -m src` (implies run)
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=ROOT / "config.yaml",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "-o",
        "--out-dir",
        type=Path,
        default=ROOT / "out",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("-v", "--verbose", action="store_true", help=argparse.SUPPRESS)

    return parser


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )


def _ensure_config(config_path: Path) -> Path | None:
    if config_path.exists():
        return config_path
    example = ROOT / "config.example.yaml"
    if example.exists() and config_path == ROOT / "config.yaml":
        logger.info("No config.yaml; copying from config.example.yaml")
        config_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        return config_path
    logger.error("Config not found: %s", config_path)
    return None


def cmd_run(args: argparse.Namespace) -> int:
    config_path = _ensure_config(args.config)
    if config_path is None:
        return 1
    path = run(config_path, args.out_dir)
    print(path)
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    try:
        marker = approve_mod.approve(args.path)
    except (FileNotFoundError, ValueError) as e:
        logger.error("%s", e)
        return 1
    print(marker)
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    try:
        result = export_mod.export_alert_pack(
            args.path,
            approve_flag=bool(args.approve),
            out_dir=args.out_dir,
            mailto_to=args.mailto_to or "",
            use_buttondown=not args.no_buttondown,
        )
    except PermissionError as e:
        logger.error("%s", e)
        return 2
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        logger.error("%s", e)
        return 1
    print(result.html_path)
    print(result.mailto_path)
    if result.buttondown_id:
        print(f"buttondown_draft_id={result.buttondown_id}")
        if result.buttondown_url:
            print(result.buttondown_url)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()

    # Backward compatible: `python -m src` / `python -m src -v` → run
    # Keep bare -h/--help on the top-level parser.
    if not argv:
        args = parser.parse_args(["run"])
    elif argv[0] in ("-h", "--help"):
        args = parser.parse_args(argv)
        # parse_args handles help and exits; if we get here, fall through
    elif argv[0].startswith("-"):
        args = parser.parse_args(["run", *argv])
    else:
        args = parser.parse_args(argv)
        if args.command is None:
            args = parser.parse_args(["run", *argv])

    _setup_logging(bool(getattr(args, "verbose", False)))

    command = getattr(args, "command", None) or "run"
    if command == "run":
        return cmd_run(args)
    if command == "approve":
        return cmd_approve(args)
    if command == "export":
        return cmd_export(args)
    parser.error(f"Unknown command: {command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
