"""Keyword filter and simple fit scoring."""

from __future__ import annotations

from dataclasses import dataclass

from .feeds import FeedItem


@dataclass
class Match:
    item: FeedItem
    matched_keywords: list[str]
    fit_score: int
    deadline_hint: str | None
    budget_hint: str | None


def _find_keywords(text: str, keywords: list[str]) -> list[str]:
    found: list[str] = []
    for kw in keywords:
        k = kw.lower().strip()
        if k and k in text:
            found.append(kw)
    return found


def _fit_score(matched: list[str], text: str, location_hints: list[str]) -> int:
    score = min(70, 15 * len(matched))
    # Strong niche signals (WordPress / SMB web freelancers)
    for strong in (
        "wordpress",
        "woocommerce",
        "elementor",
        "shopify",
        "webflow",
        "squarespace",
    ):
        if strong in text:
            score += 15
    for hint in location_hints:
        if hint.lower() in text:
            score += 5
            break
    return max(0, min(100, score))


def _hint(patterns: list[str], text: str) -> str | None:
    import re

    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(0).strip()
    return None


DEADLINE_PATTERNS = [
    r"deadline[:\s]+[^\n.]{3,60}",
    r"due[:\s]+[^\n.]{3,40}",
    r"closes?\s+on[:\s]+[^\n.]{3,40}",
    r"propos(?:al|e)\s+due[^\n.]{0,40}",
]

BUDGET_PATTERNS = [
    r"\$\s?\d[\d,]*(?:\.\d+)?(?:\s*[-–]\s*\$?\d[\d,]*)?(?:\s*(?:k|K|USD))?",
    r"budget[:\s]+[^\n.]{3,40}",
    r"compensation[:\s]+[^\n.]{3,40}",
]


def filter_items(
    items: list[FeedItem],
    keywords: list[str],
    location_hints: list[str] | None = None,
    max_items: int = 40,
) -> list[Match]:
    location_hints = location_hints or []
    matches: list[Match] = []
    for item in items:
        text = item.haystack()
        matched = _find_keywords(text, keywords)
        if not matched:
            continue
        matches.append(
            Match(
                item=item,
                matched_keywords=matched,
                fit_score=_fit_score(matched, text, location_hints),
                deadline_hint=_hint(DEADLINE_PATTERNS, text),
                budget_hint=_hint(BUDGET_PATTERNS, text),
            )
        )
    matches.sort(key=lambda m: (-m.fit_score, m.item.title.lower()))
    return matches[:max_items]
