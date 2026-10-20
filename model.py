"""The no-show model.

We use scikit-learn's HistGradientBoostingClassifier. It bins every feature into
at most 255 buckets once, then builds trees from histograms, so each boosting
round costs O(rows x features) instead of the O(rows log rows) sort per split a
classic random forest pays. It also handles missing values and categories
natively, which matters because every practice exports a different subset of
columns.

Before trusting the model, we test it the honest way: train on the older 80% of
the practice's own history and check it against the most recent 20%, which it
has never seen. Those numbers are what the "How reliable is this" panel shows.

If a practice has too little history for that (a few hundred past visits or
fewer than 25 recorded no-shows), we fall back to a transparent estimate built
from each patient's own record and the practice's averages.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss, roc_auc_score

from .features import CATEGORICAL_FEATURES, FEATURES

MAX_TRAIN_ROWS = 400_000   # most recent rows kept for training; bounds run time on huge files
MIN_ROWS_FOR_MODEL = 300
MIN_MISSES_FOR_MODEL = 25


def _new_model(n_rows: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        learning_rate=0.06,
        max_iter=350,
        max_leaf_nodes=31,
        min_samples_leaf=max(20, n_rows // 2000),
        l2_regularization=1.0,
        categorical_features="from_dtype",
        early_stopping=n_rows > 5000,
        validation_fraction=0.12,
        n_iter_no_change=20,
        random_state=7,
    )


def _simple_estimate(df: pd.DataFrame, labeled: pd.DataFrame) -> np.ndarray:
    """Patient's own smoothed miss rate, nudged by how the visit type and lead time compare to average."""
    y = (labeled["status"] == "no_show").astype(float)
    base = max(float(y.mean()), 1e-3) if len(y) else 0.1
    cat_rate = y.groupby(labeled["procedure_cat"], observed=True).agg(["sum", "count"])
    cat_mult = ((cat_rate["sum"] + 5 * base) / (cat_rate["count"] + 5)) / base
    lead_bucket = lambda s: pd.cut(s.fillna(-1), [-2, -0.5, 7, 30, 90, 1e9], labels=False)
    lead_rate = y.groupby(lead_bucket(labeled["lead_time_days"])).agg(["sum", "count"])
    lead_mult = ((lead_rate["sum"] + 5 * base) / (lead_rate["count"] + 5)) / base
    p = (df["prior_miss_rate"].to_numpy()
         * df["procedure_cat"].astype(str).map(cat_mult.rename(index=str)).fillna(1.0).to_numpy()
         * lead_bucket(df["lead_time_days"]).map(lead_mult).fillna(1.0).to_numpy())
    return np.clip(p, 0.005, 0.95)


def _tier_table(y: np.ndarray, p: np.ndarray, medium: float, high: float) -> list[dict]:
    rows = []
    for name, lo, hi in (("Low", 0, medium), ("Medium", medium, high), ("High", high, 1.01)):
        m = (p >= lo) & (p < hi)
        rows.append({
            "tier": name, "visits": int(m.sum()),
            "predicted": float(p[m].mean()) if m.any() else None,
            "actual": float(y[m].mean()) if m.any() else None,
        })
    return rows


def fit_and_score(df: pd.DataFrame, train_mask: np.ndarray, score_mask: np.ndarray,
                  medium: float, high: float, progress=lambda *a: None) -> tuple[np.ndarray, dict]:
    labeled = df[train_mask]
    if len(labeled) > MAX_TRAIN_ROWS:
        labeled = labeled.nlargest(MAX_TRAIN_ROWS, "dt")
    y_all = (labeled["status"] == "no_show").to_numpy().astype(int)
    misses = int(y_all.sum())
    quality: dict = {
        "history_visits": int(len(labeled)), "history_misses": misses,
        "base_rate": float(y_all.mean()) if len(y_all) else None,
    }
    to_score = df[score_mask]

    if len(labeled) < MIN_ROWS_FOR_MODEL or misses < MIN_MISSES_FOR_MODEL:
        quality["method"] = "simple"
        quality["method_note"] = (
            f"Only {len(labeled):,} past visits with {misses:,} misses were found, which is not enough "
            "to train the full model. Estimates use each patient's own record and your practice averages."
        )
        return _simple_estimate(to_score, labeled), quality

    quality["method"] = "model"
    # Drop columns this export doesn't have (all blank) or that never vary.
    usable = [c for c in FEATURES if c in CATEGORICAL_FEATURES
              or (labeled[c].notna().any() and labeled[c].nunique(dropna=True) > 1)]
    quality["features_used"] = usable
    X_all = labeled[usable]

    # Honest check: older 80% trains, newest 20% tests.
    progress("check", "Testing the model on your most recent visits")
    cut = labeled["dt"].quantile(0.8)
    early, late = (labeled["dt"] < cut).to_numpy(), (labeled["dt"] >= cut).to_numpy()
    if early.sum() >= MIN_ROWS_FOR_MODEL and y_all[late].sum() >= 10 and y_all[early].sum() >= 10:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            check = _new_model(int(early.sum())).fit(X_all[early], y_all[early])
            p_late = check.predict_proba(X_all[late])[:, 1]
        y_late = y_all[late]
        base = y_all[early].mean()
        quality.update({
            "test_from": str(pd.Timestamp(cut).date()),
            "test_visits": int(late.sum()),
            "auc": float(roc_auc_score(y_late, p_late)),
            "brier": float(brier_score_loss(y_late, p_late)),
            "brier_guess": float(brier_score_loss(y_late, np.full_like(p_late, base))),
            "tiers": _tier_table(y_late, p_late, medium, high),
        })
        top = np.argsort(-p_late)[: max(1, len(p_late) // 10)]
        quality["top_tenth_miss_rate"] = float(y_late[top].mean())
        quality["test_miss_rate"] = float(y_late.mean())

    progress("train", f"Learning from {len(labeled):,} past visits")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        final = _new_model(len(labeled)).fit(X_all, y_all)
        progress("score", f"Scoring {len(to_score):,} upcoming visits")
        p = final.predict_proba(to_score[usable])[:, 1] if len(to_score) else np.array([])
    return np.clip(p, 0.001, 0.999), quality


__all__ = ["fit_and_score", "CATEGORICAL_FEATURES"]
