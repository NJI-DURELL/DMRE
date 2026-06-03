"""
retrain_reranker.py
====================
Retrains the DMRE XGBoost re-ranker with 6 features and saves the new model.

Run from the backend/ directory with the .venv active:
    .venv/Scripts/python.exe retrain_reranker.py

Key improvements over the original model:
  - Adds title_semantic_similarity (fixes YouTube / video page ranking)
  - All features normalised to [0, 1] so XGBoost can weight them fairly
  - Synthetic data includes video-page scenarios where title > text similarity
  - Better hyperparameters (early stopping, more trees, subsampling)
"""

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, roc_auc_score
import xgboost as xgb
from pathlib import Path

np.random.seed(42)
OUTPUT_PATH = Path(__file__).parent / "app" / "services" / "reranker_model.ubj"

# =============================================================================
# 1. Synthetic dataset generation
# =============================================================================
# We generate 10,000 (query, candidate) pairs across four browsing archetypes
# so the model learns different relevance patterns.

def gen_standard_pages(n: int) -> pd.DataFrame:
    """Regular web articles: text and title are equally informative."""
    base = np.random.beta(2, 2, n) * 0.7 + 0.15          # semantic_sim ~ 0.15-0.85
    title_sim = np.clip(base + np.random.normal(0, 0.10, n), 0, 1)
    sem_sim    = np.clip(base + np.random.normal(0, 0.10, n), 0, 1)
    recency    = np.clip(np.exp(-np.random.exponential(5, n) / 7), 0, 1)
    engagement = np.clip(np.log1p(np.random.gamma(1.5, 8, n)) / np.log1p(62), 0, 1)
    term_ov    = np.clip(np.random.beta(1.5, 5, n), 0, 1)
    time_m     = (np.random.rand(n) < 0.25).astype(float)
    return pd.DataFrame(dict(
        semantic_similarity=sem_sim,
        title_semantic_similarity=title_sim,
        recency_score=recency,
        engagement_norm=engagement,
        term_overlap=term_ov,
        time_of_day_match=time_m,
    ))


def gen_video_pages(n: int) -> pd.DataFrame:
    """
    YouTube / video pages:
      - Body text is noisy (ads, comments, recommended videos) → lower sem_sim
      - Title is clean and descriptive → higher title_sim
      - Users typically have high dwell time when they watched the video
    This is the archetype that the old model got wrong (ranked 5th).
    """
    # Title is strong signal; text is noisy
    title_sim  = np.clip(np.random.beta(3, 2, n) * 0.6 + 0.3, 0, 1)   # 0.30–0.90
    sem_sim    = np.clip(title_sim * 0.45 + np.random.normal(0, 0.12, n), 0, 1)
    # Recently watched videos (users search for them soon after)
    recency    = np.clip(np.exp(-np.random.exponential(2, n) / 7), 0, 1)
    # High engagement: long videos = high dwell
    raw_eng    = np.random.gamma(3, 15, n)   # mean 45 minutes watch time
    engagement = np.clip(np.log1p(raw_eng) / np.log1p(62), 0, 1)
    term_ov    = np.clip(np.random.beta(2, 4, n), 0, 1)
    time_m     = (np.random.rand(n) < 0.30).astype(float)  # slightly more time-correlated
    return pd.DataFrame(dict(
        semantic_similarity=sem_sim,
        title_semantic_similarity=title_sim,
        recency_score=recency,
        engagement_norm=engagement,
        term_overlap=term_ov,
        time_of_day_match=time_m,
    ))


def gen_skimmed_pages(n: int) -> pd.DataFrame:
    """Pages the user opened briefly and closed — low engagement, may still match query."""
    base       = np.random.beta(2, 3, n) * 0.6 + 0.1
    title_sim  = np.clip(base + np.random.normal(0, 0.15, n), 0, 1)
    sem_sim    = np.clip(base + np.random.normal(0, 0.15, n), 0, 1)
    recency    = np.clip(np.exp(-np.random.exponential(8, n) / 7), 0, 1)
    engagement = np.clip(np.log1p(np.random.uniform(0, 5, n)) / np.log1p(62), 0, 1)
    term_ov    = np.clip(np.random.beta(1, 6, n), 0, 1)
    time_m     = (np.random.rand(n) < 0.20).astype(float)
    return pd.DataFrame(dict(
        semantic_similarity=sem_sim,
        title_semantic_similarity=title_sim,
        recency_score=recency,
        engagement_norm=engagement,
        term_overlap=term_ov,
        time_of_day_match=time_m,
    ))


def gen_old_deep_reads(n: int) -> pd.DataFrame:
    """Old but deeply-read pages — high engagement, but visited a while ago."""
    base       = np.random.beta(2.5, 1.5, n) * 0.5 + 0.35
    title_sim  = np.clip(base + np.random.normal(0, 0.10, n), 0, 1)
    sem_sim    = np.clip(base + np.random.normal(0, 0.10, n), 0, 1)
    recency    = np.clip(np.exp(-np.random.uniform(14, 60, n) / 7), 0, 1)   # 2–8 weeks old
    raw_eng    = np.random.gamma(4, 20, n)
    engagement = np.clip(np.log1p(raw_eng) / np.log1p(62), 0, 1)
    term_ov    = np.clip(np.random.beta(2, 4, n), 0, 1)
    time_m     = (np.random.rand(n) < 0.25).astype(float)
    return pd.DataFrame(dict(
        semantic_similarity=sem_sim,
        title_semantic_similarity=title_sim,
        recency_score=recency,
        engagement_norm=engagement,
        term_overlap=term_ov,
        time_of_day_match=time_m,
    ))


# Build full dataset: 40% standard, 30% video, 20% skimmed, 10% old deep-reads
N = 10_000
df = pd.concat([
    gen_standard_pages(int(N * 0.40)),
    gen_video_pages(int(N * 0.30)),
    gen_skimmed_pages(int(N * 0.20)),
    gen_old_deep_reads(int(N * 0.10)),
], ignore_index=True)

# =============================================================================
# 2. Relevance labels
# Ground truth formula gives each signal an explicit weight.
# title_semantic_similarity is the top signal (fixes the YouTube problem).
# =============================================================================
noise = np.random.normal(0, 0.03, len(df))

# Semantic-first weights: topic relevance must dominate recency and engagement.
# Previous weights (sem=0.25, recency=0.20) allowed a very recent but off-topic
# page (e.g. claude.ai at sim=0.13) to outscore a relevant page visited yesterday.
relevance_score = (
    0.45 * df["semantic_similarity"] +          # topic match is the primary signal
    0.30 * df["title_semantic_similarity"] +    # title match supports topic signal
    0.12 * df["recency_score"] +                # recency helps but cannot dominate
    0.08 * df["engagement_norm"] +              # engagement is a tiebreaker only
    0.04 * df["term_overlap"] +
    0.02 * df["time_of_day_match"] +
    noise
)

# Hard gate: a page with very low semantic similarity is never relevant
# regardless of how recent or engaging it is.
relevance_score = relevance_score * (df["semantic_similarity"] >= 0.20).astype(float)

# Label top-30% as relevant — mirrors the real re-ranking scenario (20 candidates, ~6 good ones)
threshold = np.percentile(relevance_score, 70)
df["relevance"] = (relevance_score > threshold).astype(int)

print(f"Dataset size : {len(df)}")
print(f"Relevant (1) : {df['relevance'].sum()} ({df['relevance'].mean():.1%})")
print(f"Irrelevant(0): {(df['relevance'] == 0).sum()}")

# =============================================================================
# 3. Train / test split
# =============================================================================
FEATURES = [
    "semantic_similarity",
    "title_semantic_similarity",
    "recency_score",
    "engagement_norm",
    "term_overlap",
    "time_of_day_match",
]

X = df[FEATURES].values.astype(np.float32)
y = df["relevance"].values.astype(np.float32)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y
)

# =============================================================================
# 4. XGBoost training with early stopping
# =============================================================================
dtrain = xgb.DMatrix(X_train, label=y_train, feature_names=FEATURES)
dtest  = xgb.DMatrix(X_test,  label=y_test,  feature_names=FEATURES)

params = {
    "objective":        "binary:logistic",
    "eval_metric":      ["logloss", "auc"],
    "max_depth":        5,
    "learning_rate":    0.05,
    "n_estimators":     500,
    "subsample":        0.80,
    "colsample_bytree": 0.80,
    "min_child_weight": 5,
    "gamma":            0.1,
    "scale_pos_weight": (y_train == 0).sum() / (y_train == 1).sum(),  # handle class imbalance
    "seed":             42,
    "verbosity":        0,
}

print("\nTraining XGBoost with early stopping (patience=30)…")
bst = xgb.train(
    params,
    dtrain,
    num_boost_round=500,
    evals=[(dtrain, "train"), (dtest, "test")],
    early_stopping_rounds=30,
    verbose_eval=50,
)

# =============================================================================
# 5. Evaluation
# =============================================================================
y_train_pred = (bst.predict(dtrain) > 0.5).astype(int)
y_test_pred  = (bst.predict(dtest)  > 0.5).astype(int)
y_test_proba = bst.predict(dtest)

train_acc = accuracy_score(y_train, y_train_pred)
test_acc  = accuracy_score(y_test,  y_test_pred)
test_auc  = roc_auc_score(y_test, y_test_proba)

print(f"\nTraining accuracy : {train_acc:.3f}")
print(f"Test accuracy     : {test_acc:.3f}")
print(f"Test AUC-ROC      : {test_auc:.3f}")

# Feature importances
print("\nFeature importances (gain):")
scores = bst.get_score(importance_type="gain")
for feat in FEATURES:
    print(f"  {feat:35s}: {scores.get(feat, 0):.2f}")

# =============================================================================
# 6. Wrap in sklearn-compatible interface and save
#    We wrap the Booster so the inference code can call model.predict(X_numpy).
# =============================================================================
bst.save_model(str(OUTPUT_PATH))
print(f"\nModel saved to: {OUTPUT_PATH}")
print("Restart the backend to load the new model.")
