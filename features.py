"""Features the model learns from.

All patient history features use only appointments that happened strictly
before the one being scored, so the model never sees the answer. The whole
build is one sort (O(n log n)) followed by grouped running sums (O(n)); there
are no per-row Python loops.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .ingest import CANCELLED, KEPT, NO_SHOW
from .settings import Settings

NUMERIC_FEATURES = [
    "lead_time_days", "hour", "weekday", "month", "age", "fee", "duration_min",
    "prior_visits", "prior_no_shows", "prior_cancels", "prior_miss_rate",
    "days_since_last", "first_visit",
]
CATEGORICAL_FEATURES = ["procedure_cat", "insurance_grp", "provider_grp"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

_CDT_PATTERN = re.compile(r"\bD?(\d{4})\b")

# Ordered most to least specific. The first keyword hit wins.
_KEYWORDS = [
    ("Root canal", ("root canal", "rct", "endo", "pulp")),
    ("Crowns and bridges", ("crown", " crn ", "bridge", "onlay", "inlay", "veneer", "buildup", "build up", " pfm ", "zirc", "emax", " seat ")),
    ("Dentures and implants", ("denture", "partial", "implant", "abutment", "reline")),
    ("Extraction and surgery", ("extract", "ext ", "surg", "wisdom", "third molar", "bone graft", "biopsy")),
    ("Periodontal", ("srp", "scaling", "root planing", "perio", "gingival", "debride")),
    ("Orthodontics", ("ortho", "braces", "invisalign", "aligner", "retainer", "adjust")),
    ("Emergency", ("emerg", "palliative", "toothache", " pain", "limited", "limex", "broken tooth")),
    ("Fillings", ("fill", "composite", "amalgam", "resto", " comp 1", " comp 2", " comp 3", " comp 4", " mod ", " do ", " mo ")),
    ("Hygiene", ("prophy", "clean", "recall", "hygiene", " hyg", "fluoride", " fl ", "sealant", " pro ", "childpro", "adultpro", "maint")),
    ("Exam and x-rays", ("exam", "perex", "compex", "eval", "x ray", "xray", "bwx", " 4bw", " 2bw", "fmx", "pano", "consult", " np ", "new patient", " poe ", " coe ")),
]

_CDT_RANGES = [  # (low, high, category), checked against the 4 digits after "D"
    (100, 999, "Exam and x-rays"), (1000, 1999, "Hygiene"), (2000, 2499, "Fillings"),
    (2500, 2999, "Crowns and bridges"), (3000, 3999, "Root canal"), (4000, 4999, "Periodontal"),
    (5000, 5899, "Dentures and implants"), (5900, 5999, "Other"), (6000, 6999, "Dentures and implants"),
    (7000, 7999, "Extraction and surgery"), (8000, 8999, "Orthodontics"), (9110, 9110, "Emergency"),
    (9310, 9311, "Exam and x-rays"),
    (9000, 9999, "Other"),
]
# When one visit lists several codes, the most involved procedure decides the category.
_CATEGORY_RANK = ["Root canal", "Dentures and implants", "Crowns and bridges", "Extraction and surgery",
                  "Periodontal", "Orthodontics", "Fillings", "Emergency", "Hygiene", "Exam and x-rays", "Other"]


def procedure_category(text: object) -> str:
    raw = str(text)
    if raw.strip().lower() in ("", "nan", "none"):
        return "Other"
    t = " " + re.sub(r"[^a-z0-9]+", " ", raw.lower()) + " "
    found = []
    for code in _CDT_PATTERN.findall(raw.upper()):
        n = int(code)
        for lo, hi, cat in _CDT_RANGES:
            if lo <= n <= hi:
                found.append(cat)
                break
    if found:
        return min(found, key=_CATEGORY_RANK.index)
    for cat, words in _KEYWORDS:
        if any(w in t for w in words):
            return cat
    return "Other"


def insurance_group(text: object) -> str:
    t = str(text).lower().strip()
    if t in ("", "nan", "none", "n/a", "na", "-", "no insurance", "uninsured"):
        return "Self-pay or none"
    if any(w in t for w in ("medicaid", "chip", "medical assistance", "keystone first", "gateway",
                             "dentaquest", "mcna", "state plan", "health partners", "upmc for you", "ma plan")):
        return "Medicaid or CHIP"
    if any(w in t for w in ("self", "cash", "private pay", "fee for service", "ffs", "uninsured",
                             "membership", "in-house", "in house", "discount")):
        return "Self-pay or none"
    if any(w in t for w in ("hmo", "dhmo", "capitation", "dmo")):
        return "HMO or DHMO"
    return "PPO or commercial"


def _map_unique(series: pd.Series, fn) -> pd.Series:
    uniques = series.astype(str).unique()
    table = {u: fn(u) for u in uniques}
    return series.astype(str).map(table)


def add_categories(df: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    df["procedure_cat"] = _map_unique(df["procedure_raw"], procedure_category)
    df["insurance_grp"] = _map_unique(df["insurance_raw"], insurance_group)

    top = df["provider"].value_counts().index[:30]
    df["provider_grp"] = df["provider"].where(df["provider"].isin(top), "Other")

    df["fee_known"] = df["fee"].notna() & (df["fee"] > 0)
    default_fee = df["procedure_cat"].map(settings.default_fee).astype(float)
    df["fee_filled"] = df["fee"].where(df["fee_known"], default_fee)
    default_len = df["procedure_cat"].map(settings.default_minutes).astype(float)
    df["minutes"] = df["duration_min"].fillna(default_len)
    return df


def build_features(df: pd.DataFrame, settings: Settings, history_cutoff: pd.Timestamp | None = None) -> pd.DataFrame:
    """Add model features. Outcomes on or after history_cutoff are hidden from history counts."""
    df = add_categories(df, settings)
    df = df.sort_values(["pid_raw", "dt"], kind="mergesort").reset_index(drop=True)

    visible = np.ones(len(df), dtype=bool) if history_cutoff is None else (df["dt"] < history_cutoff).to_numpy()
    st = df["status"].to_numpy()
    df["_ns"] = ((st == NO_SHOW) & visible).astype(np.int32)
    df["_kp"] = ((st == KEPT) & visible).astype(np.int32)
    df["_cx"] = ((st == CANCELLED) & visible).astype(np.int32)

    g = df.groupby("pid_raw", sort=False)
    df["prior_no_shows"] = g["_ns"].cumsum() - df["_ns"]
    df["prior_kept"] = g["_kp"].cumsum() - df["_kp"]
    df["prior_cancels"] = g["_cx"].cumsum() - df["_cx"]
    df["prior_visits"] = df["prior_no_shows"] + df["prior_kept"]

    known = (st == NO_SHOW) | (st == KEPT)
    base = float((st[known] == NO_SHOW).mean()) if known.any() else 0.1
    strength = 3.0  # how many visits of evidence the practice average is worth
    df["prior_miss_rate"] = (df["prior_no_shows"] + strength * base) / (df["prior_visits"] + strength)

    df["days_since_last"] = g["dt"].diff().dt.days
    df["first_visit"] = (df["prior_visits"] == 0).astype(np.int8)

    df["hour"] = df["dt"].dt.hour + df["dt"].dt.minute / 60.0
    df["weekday"] = df["dt"].dt.weekday
    df["month"] = df["dt"].dt.month

    for col in CATEGORICAL_FEATURES:
        df[col] = df[col].astype("category")
    df.attrs["base_rate"] = base
    return df.drop(columns=["_ns", "_kp", "_cx"])
