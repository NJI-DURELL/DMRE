# =============================================================================
# backend/app/services/reranker_service.py
# XGBoost re-ranker service.
# Loads reranker_model.pkl and scores each candidate with 6 features:
#   [semantic_similarity, title_semantic_similarity, recency_score,
#    engagement_norm, term_overlap, time_of_day_match]
# ALL features are normalised to [0, 1] so XGBoost can weight them fairly.
# =============================================================================

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

MODEL_PATH = Path(__file__).parent / "reranker_model.ubj"

# Feature order — must match retrain_reranker.py exactly.
FEATURES = [
    "semantic_similarity",
    "title_semantic_similarity",
    "recency_score",
    "engagement_norm",
    "term_overlap",
    "time_of_day_match",
]

_model = None


def _get_model():
    global _model
    if _model is not None:
        return _model
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Re-ranker model not found at {MODEL_PATH}.\n"
            "Run: python backend/retrain_reranker.py"
        )
    try:
        import xgboost as xgb  # noqa: PLC0415
    except ImportError as exc:
        raise ImportError("xgboost is not installed. Run: pip install xgboost") from exc
    bst = xgb.Booster()
    bst.load_model(str(MODEL_PATH))
    _model = bst
    return _model


# ---------------------------------------------------------------------------
# Feature helpers — all return values in [0, 1], higher = more relevant
# ---------------------------------------------------------------------------

def _recency_score(visited_at: datetime) -> float:
    """Exponential decay: 1.0 = visited today, ~0.37 = 7 days ago, ~0 = old."""
    now = datetime.now(timezone.utc)
    if visited_at.tzinfo is None:
        visited_at = visited_at.replace(tzinfo=timezone.utc)
    days = max(0.0, (now - visited_at).total_seconds() / 86_400.0)
    return float(np.exp(-days / 7.0))


def _engagement_norm(
    visit_count: int,
    dwell_time: float,
    click_count: int = 0,
    scroll_depth: float = 0.0,
) -> float:
    """
    Log-normalised engagement in [0, 1] combining dwell, visits, clicks, scroll.
    Cap raw at 72 (≈ 1 visit + 1 hr + heavy interaction).
    """
    raw = (
        float(visit_count) * 2.0
        + (dwell_time / 60.0)
        + float(click_count) * 0.5
        + scroll_depth * 5.0      # full scroll = +5 equivalent minutes
    )
    return float(min(1.0, np.log1p(raw) / np.log1p(72.0)))


def _term_overlap(query: str, title: str) -> float:
    """Jaccard similarity between lower-cased query tokens and title tokens."""
    q_tok = set(query.lower().split())
    t_tok = set(title.lower().split())
    if not q_tok or not t_tok:
        return 0.0
    return len(q_tok & t_tok) / len(q_tok | t_tok)


def _exact_phrase_boost(query: str, text: str) -> float:
    """
    Post-processing multiplier for XGBoost scores.
    Returns a value to add to 1.0:
      +0.50 if a trigram from the query appears verbatim in text
      +0.30 if a bigram appears verbatim
      +0.20 based on fraction of meaningful tokens present (keyword density)
    Total possible boost: up to 0.70 on top of the XGBoost score.
    """
    words = re.findall(r"\w+", query.lower())
    haystack = text.lower()

    phrase_bonus = 0.0
    for n, bonus in ((3, 0.50), (2, 0.30)):
        if len(words) >= n:
            for i in range(len(words) - n + 1):
                if " ".join(words[i : i + n]) in haystack:
                    phrase_bonus = max(phrase_bonus, bonus)
                    break

    meaningful = [w for w in words if len(w) > 2]
    density = (
        sum(1 for w in meaningful if w in haystack) / len(meaningful)
        if meaningful else 0.0
    )
    return phrase_bonus + density * 0.20


def _time_of_day_match(visited_at: datetime) -> float:
    """1.0 if visited within ±3 hours of the current hour, else 0.0."""
    now_hour = datetime.now(timezone.utc).hour
    if visited_at.tzinfo is None:
        visited_at = visited_at.replace(tzinfo=timezone.utc)
    diff = abs(now_hour - visited_at.hour)
    diff = min(diff, 24 - diff)
    return 1.0 if diff <= 3 else 0.0


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom < 1e-8:
        return 0.0
    return float(np.clip(np.dot(a, b) / denom, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def rerank(
    query: str,
    candidates: list[dict],
    top_k: int = 5,
    query_embedding: list[float] | None = None,
    time_window: "tuple[datetime, datetime] | None" = None,
) -> list[dict]:
    """
    Re-rank candidates with a 6-feature XGBoost model.

    Feature order (must match training):
        [semantic_similarity, title_semantic_similarity, recency_score,
         engagement_norm, term_overlap, time_of_day_match]

    Args:
        query:           Raw query string.
        candidates:      List of dicts from the vector-store stage.
        top_k:           How many results to return.
        query_embedding: Pre-computed 384-dim query vector (avoids recompute).

    Returns:
        Up to top_k candidates sorted by predicted relevance (descending).
    """
    if not candidates:
        return []

    model = _get_model()

    # Lazy import to avoid circular dependency at module load time.
    from app.services import embedding_service  # noqa: PLC0415

    # Query vector — reuse from Stage 1 to avoid recomputing.
    qvec = np.array(
        query_embedding if query_embedding is not None
        else embedding_service.embed_query(query),
        dtype=np.float32,
    )

    # Batch-embed all candidate titles in one call.
    titles = [c.get("title") or "" for c in candidates]
    title_vecs = np.array(embedding_service.embed(titles), dtype=np.float32)

    rows: list[list[float]] = []
    for i, c in enumerate(candidates):
        visited_at: datetime = c.get("visited_at") or datetime.now(timezone.utc)
        row = [
            float(np.clip(c.get("semantic_similarity", 0.0), 0.0, 1.0)),
            _cosine(qvec, title_vecs[i]),
            _recency_score(visited_at),
            _engagement_norm(
                int(c.get("visit_count", 1)),
                float(c.get("dwell_time", 0.0)),
                int(c.get("click_count", 0)),
                float(c.get("scroll_depth", 0.0)),
            ),
            _term_overlap(query, c.get("title", "")),
            _time_of_day_match(visited_at),
        ]
        rows.append(row)

    import xgboost as xgb  # noqa: PLC0415

    X = np.array(rows, dtype=np.float32)
    dm = xgb.DMatrix(X, feature_names=FEATURES)
    scores: np.ndarray = model.predict(dm)

    # Apply exact-phrase and keyword-density boost on top of XGBoost score.
    # This makes precise keyword queries dominate without retraining the model.
    boosted = []
    for c, base_score in zip(candidates, scores.tolist()):
        text = (c.get("snippet") or "") + " " + (c.get("title") or "")
        boost = _exact_phrase_boost(query, text)
        phrase_score = base_score * (1.0 + boost)

        # Semantic gate: multiply by semantic_similarity so a high-recency but
        # off-topic page (e.g. claude.ai at 0.13) can never outrank a genuinely
        # relevant page (e.g. scholarship article at 0.45).
        sem = float(c.get("semantic_similarity", 0.0))
        boosted.append((c, phrase_score * max(sem, 0.01)))

    # Temporal window boost: when the user specifies a time ("in the morning",
    # "yesterday", etc.) strongly prefer candidates visited in that window and
    # penalise everything outside it so they don't crowd out the right result.
    if time_window is not None:
        tw_start, tw_end = time_window
        adjusted = []
        for c, score in boosted:
            vat: datetime = c.get("visited_at") or datetime.now(timezone.utc)
            if vat.tzinfo is None:
                vat = vat.replace(tzinfo=timezone.utc)
            in_window = tw_start <= vat <= tw_end
            multiplier = 2.0 if in_window else 0.4
            adjusted.append((c, score * multiplier))
        boosted = adjusted

    paired = sorted(boosted, key=lambda x: x[1], reverse=True)
    return [c for c, _ in paired[:top_k]]
