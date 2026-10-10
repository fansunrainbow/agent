from __future__ import annotations

from difflib import SequenceMatcher
import re
import unicodedata


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower().strip()
    return re.sub(r"[\s，。；、：:！？?（）()\[\]{}]+", "", text)


def partial_ratio(needle: str, haystack: str) -> float:
    needle = normalize_text(needle)
    haystack = normalize_text(haystack)
    if not needle or not haystack:
        return 0.0
    if needle in haystack:
        return 1.0
    if len(needle) > len(haystack):
        needle, haystack = haystack, needle
    width = len(needle)
    scores = [
        SequenceMatcher(None, needle, haystack[index:index + width]).ratio()
        for index in range(max(1, len(haystack) - width + 1))
    ]
    return max(scores, default=0.0)


def best_label_match(query: str, labels: list[str]) -> tuple[float, str | None, str]:
    normalized_query = normalize_text(query)
    best = (0.0, None, "not_found")
    for label in labels:
        normalized_label = normalize_text(label)
        if not normalized_label:
            continue
        if normalized_label == normalized_query or normalized_label in normalized_query:
            score = 1.0
            match_type = "exact" if normalized_label == normalized_query else "substring"
        else:
            score = partial_ratio(normalized_label, normalized_query)
            match_type = "fuzzy"
        if score > best[0] or (score == best[0] and len(normalized_label) > len(normalize_text(best[1]))):
            best = (score, label, match_type)
    return best

