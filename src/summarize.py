"""Summarize matches with OpenAI when available; else templates."""

from __future__ import annotations

import logging
import os
from typing import Any

from .filter import Match

logger = logging.getLogger(__name__)


def template_summary(match: Match) -> str:
    item = match.item
    bits = [
        f"**Fit score:** {match.fit_score}/100",
        f"**Keywords:** {', '.join(match.matched_keywords)}",
    ]
    if match.deadline_hint:
        bits.append(f"**Deadline signal:** {match.deadline_hint}")
    else:
        bits.append("**Deadline signal:** not detected — verify on source page")
    if match.budget_hint:
        bits.append(f"**Budget signal:** {match.budget_hint}")
    else:
        bits.append("**Budget signal:** not detected")
    snippet = (item.summary or "").strip()
    if len(snippet) > 280:
        snippet = snippet[:277].rstrip() + "…"
    if snippet:
        bits.append(f"**Snippet:** {snippet}")
    bits.append(
        f"**Why it might fit a WP freelancer:** mentions "
        f"{', '.join(match.matched_keywords[:4])}; review scope, contract type, and timeline before bidding."
    )
    return "\n".join(bits)


def llm_summary(match: Match, model: str, max_tokens: int) -> str | None:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package missing; falling back to template")
        return None

    item = match.item
    prompt = (
        "You write concise RFP/job alert blurb for WordPress / small-business web freelancers.\n"
        "Return 4-6 short markdown bullet lines covering: fit, deadline/budget signals if any, "
        "and what to verify before bidding. Do not invent facts not in the text.\n\n"
        f"Title: {item.title}\n"
        f"Source: {item.source}\n"
        f"URL: {item.url}\n"
        f"Matched keywords: {', '.join(match.matched_keywords)}\n"
        f"Fit score (heuristic): {match.fit_score}\n"
        f"Text:\n{(item.summary or item.raw_text)[:3500]}\n"
    )
    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": "You are a careful freelancer opportunity screener."},
                {"role": "user", "content": prompt},
            ],
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or None
    except Exception as exc:  # noqa: BLE001
        logger.error("OpenAI summarize failed: %s", exc)
        return None


def summarize_match(match: Match, openai_cfg: dict[str, Any] | None = None) -> str:
    openai_cfg = openai_cfg or {}
    model = openai_cfg.get("model") or "gpt-4o-mini"
    max_tokens = int(openai_cfg.get("max_tokens") or 220)
    llm = llm_summary(match, model=model, max_tokens=max_tokens)
    if llm:
        header = f"**Fit score:** {match.fit_score}/100 · **Keywords:** {', '.join(match.matched_keywords)}\n"
        return header + llm
    return template_summary(match)
