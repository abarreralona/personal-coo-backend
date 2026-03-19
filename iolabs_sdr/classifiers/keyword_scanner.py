"""
IOlabs AI SDR Platform — Keyword Scanner (Step 7)

Deterministic, case-insensitive keyword matching against scraped page text.
No LLM involvement. Fast and auditable.

Returns:
  matched_keywords: List[str]
  count: int
  detected: bool  (count > 0)
"""

from __future__ import annotations

from pydantic import BaseModel


class KeywordResult(BaseModel):
    """Result of a keyword scan against page text."""

    matched_keywords: list[str]
    count: int
    detected: bool


class KeywordScanner:
    """
    Deterministic keyword scanner for the classification pipeline.

    Usage:
        result = KeywordScanner.scan(page_text, rule.keywords)
        # result.detected → True if any keyword found
        # result.matched_keywords → list of matched keywords (in order found)
    """

    @staticmethod
    def scan(text: str, keywords: list[str]) -> KeywordResult:
        """
        Case-insensitive scan of `text` for each keyword in `keywords`.

        A keyword matches if it appears anywhere in the text as a substring
        (not necessarily a whole word — consistent with the spirit of "signals
        on page text"). Matching is case-insensitive.

        Args:
            text:     Scraped page text to search in.
            keywords: List of keyword strings to look for.

        Returns:
            KeywordResult with matched_keywords, count, and detected flag.
        """
        if not text or not keywords:
            return KeywordResult(matched_keywords=[], count=0, detected=False)

        lowered = text.lower()
        matched: list[str] = []
        seen: set[str] = set()

        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower in lowered and kw_lower not in seen:
                matched.append(kw)
                seen.add(kw_lower)

        return KeywordResult(
            matched_keywords=matched,
            count=len(matched),
            detected=len(matched) > 0,
        )
