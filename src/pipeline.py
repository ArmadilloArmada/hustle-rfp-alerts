"""End-to-end: poll → filter → summarize → write out/alerts-YYYY-MM-DD.md."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from .feeds import dedupe, fetch_all
from .filter import filter_items
from .report import render_report, write_report

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Config must be a mapping: {path}")
    return data


def run(config_path: Path, out_dir: Path) -> Path:
    cfg = load_config(config_path)
    niche = cfg.get("niche") or "freelancer alerts"
    keywords = list(cfg.get("keywords") or [])
    if not keywords:
        raise SystemExit("config.keywords is required")
    feeds = list(cfg.get("feeds") or [])
    if not feeds:
        raise SystemExit("config.feeds is required")
    location_hints = list(cfg.get("location_hints") or [])
    max_items = int(cfg.get("max_items") or 40)
    openai_cfg = cfg.get("openai") or {}

    raw = fetch_all(feeds)
    items = dedupe(raw)
    logger.info("Fetched %d items (%d after dedupe)", len(raw), len(items))
    matches = filter_items(items, keywords=keywords, location_hints=location_hints, max_items=max_items)
    logger.info("Matched %d items", len(matches))
    md = render_report(niche=niche, matches=matches, openai_cfg=openai_cfg)
    path = write_report(out_dir, md)
    logger.info("Wrote %s", path)
    return path
