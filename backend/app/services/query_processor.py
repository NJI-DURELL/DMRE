# =============================================================================
# backend/app/services/query_processor.py
# Strips conversational filler from search queries and extracts temporal hints.
#
# "an article on scholarships I read in the morning"
#   → clean_query  = "scholarships"
#   → temporal_hint = "morning"
#
# The clean query is used for embedding so the vector represents the actual
# topic rather than noise words ("read", "article", "morning").
# The temporal hint is used to boost / penalise candidates by visited_at time.
# =============================================================================

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Temporal patterns — ordered most-specific first so the first match wins
# ---------------------------------------------------------------------------
_TEMPORAL_MAP: list[tuple[str, str]] = [
    (r"\b(this\s+morning|in\s+the\s+morning|early\s+this\s+morning|earlier\s+this\s+morning)\b", "morning"),
    (r"\b(this\s+afternoon|in\s+the\s+afternoon|this\s+pm)\b", "afternoon"),
    (r"\b(this\s+evening|tonight|in\s+the\s+evening)\b", "evening"),
    (r"\b(last\s+night)\b", "last_night"),
    (r"\byesterday\b", "yesterday"),
    (r"\blast\s+week\b", "last_week"),
    (r"\blast\s+month\b", "last_month"),
    (r"\b(just\s+now|a\s+few\s+minutes?\s+ago|minutes?\s+ago|a\s+moment\s+ago)\b", "recent"),
    (r"\b(an?\s+hour\s+ago|hours?\s+ago)\b", "recent"),
    (r"\b(recently|earlier\s+today|earlier)\b", "recent"),
    (r"\btoday\b", "today"),
]

# ---------------------------------------------------------------------------
# Filler phrases — describe the act of finding/visiting, not the content
# ---------------------------------------------------------------------------
_FILLER_PATTERNS: list[str] = [
    # "I read / visited / saw / found ..."
    r"\bi\s+(read|visited|saw|found|came\s+across|looked\s+at|checked\s+out?|browsed|opened|viewed|was\s+reading|was\s+looking\s+at|was\s+watching|watched|heard\s+about|learned\s+about)\b",
    # "an/a/the article/page/post about/on ..."
    r"\b(an?|the)\s+(article|page|post|website|blog\s+post|blog|site|piece|story|write[-\s]?up|news\s+story|report|guide|tutorial|video|clip)\s+(about|on|regarding|covering|discussing|related\s+to|concerning)\b",
    # "an/a/the article/page/..." without trailing preposition
    r"\b(an?|the)\s+(article|page|post|website|blog\s+post|blog|site|piece|story|guide|tutorial)\b",
    # relative pronouns pointing back to the act
    r"\bthat\s+(i\b|was\b|is\b)",
    r"\bwhich\s+i\b",
    r"\bwhere\s+i\b",
    # imperative starters
    r"\b(find\s+me|show\s+me|look\s+for|search\s+for|get\s+me)\b",
    # leading "about"
    r"^about\s+",
]


def preprocess(query: str) -> tuple[str, str | None]:
    """
    Extract the content intent and any temporal hint from a conversational query.

    Returns:
        (clean_query, temporal_hint)
        temporal_hint: 'morning' | 'afternoon' | 'evening' | 'last_night' |
                       'yesterday' | 'last_week' | 'last_month' | 'recent' |
                       'today' | None
    """
    lower = query.lower().strip()

    # 1. Detect temporal hint before stripping anything
    temporal_hint: str | None = None
    for pattern, hint in _TEMPORAL_MAP:
        if re.search(pattern, lower, re.IGNORECASE):
            temporal_hint = hint
            break

    # 2. Strip temporal phrases from content
    cleaned = lower
    for pattern, _ in _TEMPORAL_MAP:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    # 3. Strip navigation / filler phrases
    for pattern in _FILLER_PATTERNS:
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)

    # 4. Remove stray punctuation and collapse whitespace
    cleaned = re.sub(r"[,;:.!?]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # 5. Safety fallback: if too much was stripped, use the original
    if len(cleaned) < 3:
        cleaned = query.strip()

    return cleaned, temporal_hint


def get_time_window(hint: str) -> tuple[datetime, datetime] | None:
    """Convert a temporal hint into a (start, end) UTC datetime window."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if hint == "morning":
        # 05:00 – 12:00; if currently before noon extend back to yesterday morning
        start = today_start.replace(hour=5)
        end   = today_start.replace(hour=12)
        if now.hour < 12:
            start = start - timedelta(days=1)
    elif hint == "afternoon":
        start = today_start.replace(hour=12)
        end   = today_start.replace(hour=18)
    elif hint == "evening":
        start = today_start.replace(hour=17)
        end   = today_start.replace(hour=23, minute=59, second=59)
    elif hint == "last_night":
        yesterday = today_start - timedelta(days=1)
        start = yesterday.replace(hour=20)
        end   = today_start.replace(hour=6)
    elif hint == "yesterday":
        start = today_start - timedelta(days=1)
        end   = today_start
    elif hint == "last_week":
        start = today_start - timedelta(days=7)
        end   = now
    elif hint == "last_month":
        start = today_start - timedelta(days=30)
        end   = now
    elif hint == "recent":
        start = now - timedelta(hours=3)
        end   = now
    elif hint == "today":
        start = today_start
        end   = now
    else:
        return None

    return start, end
