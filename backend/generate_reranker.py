# =============================================================================
# backend/generate_reranker.py
# Reproduces the training from DMRE_Reranker_Training.ipynb and saves the
# model directly to backend/app/services/reranker_model.pkl for the FastAPI
# backend to load.  Run once; do not re-run unless you intend to retrain.
# =============================================================================

import numpy as np
import pandas as pd
import joblib
from pathlib import Path
from sklearn.model_selection import GroupShuffleSplit
import xgboost as xgb

np.random.seed(42)

# ---------------------------------------------------------------------------
# 1. Generate synthetic dataset (identical to notebook)
# ---------------------------------------------------------------------------
NUM_QUERIES = 200
CANDIDATES_PER_QUERY = 20

def generate_row(query_id, rank_in_query):
    base = max(0.3, 0.95 - (rank_in_query * 0.03))
    semantic_similarity = np.clip(base + np.random.normal(0, 0.08), 0.0, 1.0)
    recency_days = min(np.random.exponential(scale=30), 365)
    engagement_score = np.random.beta(1.5, 5) * 100
    term_overlap = np.random.beta(2, 5)
    time_of_day_match = np.random.beta(2, 2)
    relevance = (
        0.45 * semantic_similarity
        + 0.20 * (1 - min(recency_days / 180, 1.0))
        + 0.15 * (engagement_score / 100)
        + 0.15 * term_overlap
        + 0.05 * time_of_day_match
    )
    relevance = np.clip(relevance + np.random.normal(0, 0.05), 0.0, 1.0)
    return {
        "query_id": query_id,
        "semantic_similarity": round(semantic_similarity, 4),
        "recency_days": round(recency_days, 2),
        "engagement_score": round(engagement_score, 2),
        "term_overlap": round(term_overlap, 4),
        "time_of_day_match": round(time_of_day_match, 4),
        "relevance": round(relevance, 4),
    }

rows = [
    generate_row(qid, rank)
    for qid in range(NUM_QUERIES)
    for rank in range(CANDIDATES_PER_QUERY)
]
df = pd.DataFrame(rows).sample(frac=1, random_state=42).reset_index(drop=True)
print(f"Generated {len(df)} rows across {df.query_id.nunique()} queries.")

# ---------------------------------------------------------------------------
# 2. Train/test split grouped by query (no data leakage)
# ---------------------------------------------------------------------------
FEATURES = [
    "semantic_similarity",
    "recency_days",
    "engagement_score",
    "term_overlap",
    "time_of_day_match",
]
TARGET = "relevance"

splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_idx, test_idx = next(splitter.split(df, groups=df["query_id"]))
df_train, df_test = df.iloc[train_idx], df.iloc[test_idx]
X_train, y_train = df_train[FEATURES], df_train[TARGET]
X_test, y_test = df_test[FEATURES], df_test[TARGET]

print(f"Train: {len(X_train)} rows | Test: {len(X_test)} rows")

# ---------------------------------------------------------------------------
# 3. Train XGBoost (identical hyperparameters to notebook)
# ---------------------------------------------------------------------------
model = xgb.XGBRegressor(
    n_estimators=200,
    max_depth=5,
    learning_rate=0.1,
    objective="reg:squarederror",
    random_state=42,
)
model.fit(X_train, y_train)
print("Training complete.")

# ---------------------------------------------------------------------------
# 4. Quick evaluation (should reproduce notebook results)
# ---------------------------------------------------------------------------
from sklearn.metrics import mean_absolute_error, mean_squared_error  # noqa: E402

y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

def ndcg_at_k(y_true, y_pred_scores, k=5):
    order = np.argsort(y_pred_scores)[::-1][:k]
    gains = np.asarray(y_true)[order]
    discounts = 1.0 / np.log2(np.arange(2, len(gains) + 2))
    dcg = np.sum(gains * discounts)
    ideal = np.sort(y_true)[::-1][:k]
    idcg = np.sum(ideal * discounts[: len(ideal)])
    return dcg / idcg if idcg > 0 else 0.0

df_eval = df_test.copy()
df_eval["predicted"] = y_pred
ndcgs = [
    ndcg_at_k(g[TARGET].values, g["predicted"].values, k=5)
    for _, g in df_eval.groupby("query_id")
]

print(f"MAE:    {mae:.4f}  (expected ~0.0424)")
print(f"RMSE:   {rmse:.4f}  (expected ~0.0538)")
print(f"NDCG@5: {np.mean(ndcgs):.4f}  (expected 0.9749)")

# ---------------------------------------------------------------------------
# 5. Save to the location the FastAPI service expects
# ---------------------------------------------------------------------------
out_path = Path(__file__).parent / "app" / "services" / "reranker_model.pkl"
joblib.dump(model, out_path)
print(f"\nModel saved to {out_path}")
print("Phase 2 re-ranker is ready.")
