"""End-to-end run: file in, anonymized risk list and staffing plan out.

The pipeline decides what to forecast on its own:

* If the export has upcoming visits (status scheduled, booked, confirmed or
  blank), those are scored and planned. Past visits with known outcomes teach
  the model.
* If every visit already has an outcome, the last five working days are held
  back and scored as if they were upcoming. The results then show what actually
  happened next to each prediction, which is a good way to see whether the tool
  works for this practice before relying on it.

Patients are shown only as "Patient 1", "Patient 2" and so on, numbered in
appointment order. The link back to chart numbers lives in memory and is only
written out if someone asks for the lookup file.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .columns import FIELD_LABELS, REQUIRED_FIELDS, is_identifying, missing_required
from .features import build_features
from .ingest import KEPT, NO_SHOW, SCHEDULED, IngestError, inspect_file, load_columns, standardize
from .model import fit_and_score
from .settings import Settings
from .staffing import plan_all

BACKTEST_DAYS = 5
MAX_FORECAST_DAYS = 60


class NeedsMapping(Exception):
    """Raised when we can't find required columns. Carries what the mapping screen needs."""

    def __init__(self, message: str, headers: list[str], detected: dict[str, str]):
        super().__init__(message)
        self.payload = {
            "message": message,
            "headers": [h for h in headers if h and not is_identifying(h)],
            "hidden_headers": [h for h in headers if h and is_identifying(h)],
            "detected": detected,
            "fields": FIELD_LABELS,
            "required": ["patient_id", "status"],
        }


@dataclass
class RunState:
    scored: pd.DataFrame
    settings: Settings
    key: pd.DataFrame
    result: dict = field(default_factory=dict)


def _time_label(ts: pd.Series) -> pd.Series:
    h = ts.dt.hour
    m = ts.dt.minute
    suffix = np.where(h < 12, "AM", "PM")
    hh = (h % 12).replace(0, 12)
    return hh.astype(str) + ":" + m.astype(str).str.zfill(2) + " " + pd.Series(suffix, index=ts.index)


def _group_rates(hist: pd.DataFrame, key: pd.Series, min_visits: int = 30) -> pd.DataFrame:
    y = (hist["status"] == NO_SHOW).astype(float)
    g = y.groupby(key, observed=True).agg(["mean", "count"])
    return g[g["count"] >= min_visits]


def _patterns(hist: pd.DataFrame) -> list[dict]:
    """Plain group averages from the practice's own history, for the 'What drives misses' panel."""
    if hist.empty:
        return []
    out = []
    lead = pd.cut(hist["lead_time_days"], [-1, 2, 7, 30, 90, 10_000],
                  labels=["0 to 2 days", "3 to 7 days", "8 to 30 days", "31 to 90 days", "Over 90 days"])
    prior = pd.cut(hist["prior_no_shows"], [-1, 0, 1, 2, 10_000],
                   labels=["None", "One", "Two", "Three or more"])
    days = hist["dt"].dt.day_name()
    for title, key, order in (
        ("How far ahead the visit was booked", lead, None),
        ("Past missed visits", prior, None),
        ("Day of the week", days, ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]),
        ("Visit type", hist["procedure_cat"].astype(str), None),
        ("Insurance group", hist["insurance_grp"].astype(str), None),
    ):
        if key.isna().all():
            continue
        g = _group_rates(hist, key)
        if len(g) < 2:
            continue
        if order:
            g = g.reindex([o for o in order if o in g.index])
        elif title in ("Visit type", "Insurance group"):
            g = g.sort_values("mean", ascending=False)
        out.append({"title": title, "rows": [
            {"label": str(idx), "visits": int(r["count"]), "rate": round(float(r["mean"]), 4)}
            for idx, r in g.iterrows()
        ]})
    return out


def _reasons(scored: pd.DataFrame, hist: pd.DataFrame, base: float) -> list[list[str]]:
    n = len(scored)
    cols: list[np.ndarray] = []

    def add(mask, text):
        arr = np.full(n, "", dtype=object)
        mask = np.asarray(mask, dtype=bool)
        if mask.any():
            arr[mask] = np.asarray(text, dtype=object)[mask] if not isinstance(text, str) else text
        cols.append(arr)

    pns = scored["prior_no_shows"].to_numpy()
    add(pns == 1, "Missed 1 earlier visit")
    add(pns > 1, pd.Series(pns).map(lambda k: f"Missed {k} earlier visits").to_numpy())
    pcx = scored["prior_cancels"].to_numpy()
    add(pcx >= 2, pd.Series(pcx).map(lambda k: f"Cancelled {k} times before").to_numpy())
    lead = scored["lead_time_days"].to_numpy()
    add(np.nan_to_num(lead) >= 45, pd.Series(lead).map(lambda d: f"Booked {int(d)} days ahead" if d == d else "").to_numpy())
    add(scored["first_visit"].to_numpy() == 1, "First visit with the practice")
    gap = scored["days_since_last"].to_numpy()
    add((np.nan_to_num(gap) > 540) & (scored["first_visit"].to_numpy() == 0), "Over 18 months since the last visit")

    if not hist.empty and base > 0:
        for scored_key, hist_key in (
            (scored["dt"].dt.day_name(), hist["dt"].dt.day_name()),
            (scored["procedure_cat"].astype(str), hist["procedure_cat"].astype(str)),
        ):
            rates = _group_rates(hist, hist_key)
            risky = set(rates.index[rates["mean"] >= 1.3 * base])
            add(scored_key.isin(risky).to_numpy(),
                scored_key.map(lambda v: f"{v} visits are missed more often here").to_numpy())

    # Only say this when it explains a low estimate, never next to a Medium or High one.
    clean = (scored["prior_visits"].to_numpy() >= 3) & (pns == 0) & (scored["p"].to_numpy() < base)
    add(clean, "Has kept every recorded visit")

    stacked = np.stack(cols, axis=1) if cols else np.empty((n, 0), dtype=object)
    return [[s for s in row if s][:3] for row in stacked]


def _tier(p: np.ndarray, s: Settings) -> np.ndarray:
    return np.where(p >= s.high_risk, "High", np.where(p >= s.medium_risk, "Medium", "Low"))


def _patients_payload(scored: pd.DataFrame, s: Settings, backtest: bool) -> list[dict]:
    tiers = _tier(scored["p"].to_numpy(), s)
    rows = []
    for i, r in enumerate(scored.itertuples(index=False)):
        item = {
            "patient": int(r.patient_no), "date": r.date, "time": r.time_label,
            "minutes": int(r.minutes), "visit": r.procedure_cat, "provider": r.provider,
            "chance": round(float(r.p), 4), "tier": str(tiers[i]), "why": list(r.why),
            "fee": round(float(r.fee_filled), 0),
        }
        if backtest:
            item["outcome"] = "Missed" if r.status == NO_SHOW else "Came"
        rows.append(item)
    return rows


def build_result(state: RunState) -> dict:
    s = state.settings
    scored = state.scored
    result = dict(state.result)
    result["settings"] = s.to_dict()
    result["days"] = plan_all(scored, s)
    result["patients"] = _patients_payload(scored, s, result["meta"]["mode"] == "backtest")
    tiers = _tier(scored["p"].to_numpy(), s)
    result["totals"] = {
        "visits": int(len(scored)),
        "expected_misses": round(float(scored["p"].sum()), 1),
        "production_at_risk": round(float((scored["p"] * scored["fee_filled"]).sum()), 0),
        "high": int((tiers == "High").sum()), "medium": int((tiers == "Medium").sum()),
        "low": int((tiers == "Low").sum()),
    }
    return result


def run(data: bytes, filename: str, mapping: dict | None = None, settings: Settings | None = None,
        progress=lambda stage, text, pct=None: None) -> RunState:
    t0 = time.perf_counter()
    settings = settings or Settings()

    progress("read", "Reading your file", 5)
    shape = inspect_file(data, filename)
    if mapping:
        mapping = {k: v for k, v in mapping.items() if v and v in shape.headers}
        if mapping.get("appt_datetime") and not mapping.get("appt_date"):
            mapping["appt_date"] = mapping["appt_datetime"]
    else:
        mapping = shape.mapping
    missing = missing_required(mapping)
    if missing or "status" not in mapping:
        what = [FIELD_LABELS[m] for m in missing] + ([] if "status" in mapping else [FIELD_LABELS["status"]])
        raise NeedsMapping("We couldn't find: " + "; ".join(what).lower() + ". Pick the matching columns below.",
                           shape.headers, mapping)

    raw = load_columns(data, shape, mapping)
    rows_read = len(raw)
    progress("clean", f"Cleaning {rows_read:,} rows", 15)
    df, notes = standardize(raw, mapping)
    del raw
    if df.empty:
        raise IngestError("No usable rows were found. Check that the date and patient columns are filled in.")

    status = df["status"].to_numpy()
    known = np.isin(status, [KEPT, NO_SHOW])
    if not known.any():
        raise IngestError(
            "Every visit in this file is still marked as scheduled, so there is no history to learn from. "
            "Export a date range that includes at least six months of past visits along with the upcoming schedule.")
    last_known = df.loc[known, "dt"].max().normalize()

    upcoming = (status == SCHEDULED) & (df["dt"].dt.normalize() >= last_known - pd.Timedelta(days=3)).to_numpy()
    stale = int(((status == SCHEDULED) & ~upcoming).sum())
    if stale:
        notes["warnings"].append(f"{stale:,} older visits were still marked scheduled with no outcome, so they were left out.")

    if upcoming.any():
        mode = "forecast"
        first_day = df.loc[upcoming, "dt"].min().normalize()
        horizon = first_day + pd.Timedelta(days=MAX_FORECAST_DAYS)
        too_far = upcoming & (df["dt"] >= horizon).to_numpy()
        if too_far.any():
            notes["warnings"].append(f"Only the first {MAX_FORECAST_DAYS} days of upcoming visits are planned; "
                                     f"{int(too_far.sum()):,} later visits were left out.")
        upcoming &= ~too_far
        cutoff = None
    else:
        mode = "backtest"
        days = np.sort(df.loc[known, "dt"].dt.normalize().unique())
        cutoff = pd.Timestamp(days[-BACKTEST_DAYS]) if len(days) > BACKTEST_DAYS else pd.Timestamp(days[-1])

    progress("features", "Looking at each patient's history", 30)
    feats = build_features(df, settings, history_cutoff=cutoff)
    st = feats["status"].to_numpy()
    if mode == "forecast":
        train_mask = np.isin(st, [KEPT, NO_SHOW])
        day = feats["dt"].dt.normalize()
        horizon_ok = day < (first_day + pd.Timedelta(days=MAX_FORECAST_DAYS))
        score_mask = (st == SCHEDULED) & (day >= last_known - pd.Timedelta(days=3)).to_numpy() & horizon_ok.to_numpy()
    else:
        is_known = np.isin(st, [KEPT, NO_SHOW])
        train_mask = is_known & (feats["dt"] < cutoff).to_numpy()
        score_mask = is_known & (feats["dt"] >= cutoff).to_numpy()

    pct = {"check": 45, "train": 65, "score": 82}
    p, quality = fit_and_score(feats, train_mask, score_mask, settings.medium_risk, settings.high_risk,
                               progress=lambda stage, text: progress(stage, text, pct.get(stage)))

    progress("plan", "Building the staffing plan", 90)
    scored = feats[score_mask].copy()
    scored["p"] = p
    scored = scored.sort_values(["dt", "provider", "pid_raw"], kind="mergesort").reset_index(drop=True)

    # Anonymize: Patient 1, 2, 3 ... in order of first appointment in the plan.
    codes, uniques = pd.factorize(scored["pid_raw"], sort=False)
    scored["patient_no"] = codes + 1
    key = pd.DataFrame({"Patient": [f"Patient {i + 1}" for i in range(len(uniques))],
                        "Chart number in your system": uniques})
    hist = feats[train_mask]
    base = quality.get("base_rate") or 0.0
    scored["why"] = pd.Series(_reasons(scored, hist, base), index=scored.index, dtype=object)
    scored["date"] = scored["dt"].dt.strftime("%Y-%m-%d")
    scored["time_label"] = _time_label(scored["dt"])
    scored = scored.drop(columns=["pid_raw", "procedure_raw", "insurance_raw"])

    meta = {
        "file_name": filename, "mode": mode,
        "rows_read": int(rows_read),
        "history_visits": int(train_mask.sum()), "upcoming_visits": int(score_mask.sum()),
        "patients_in_plan": int(len(uniques)),
        "history_from": str(df.loc[known, "dt"].min().date()), "history_to": str(last_known.date()),
        "columns_used": {FIELD_LABELS.get(k, k): v for k, v in mapping.items()
                         if not (k == "appt_date" and v == mapping.get("appt_datetime"))},
        "columns_not_read": shape.skipped_identifying,
        "status_values": notes.get("status_values", {}),
        "warnings": notes["warnings"],
        "fees_from_file": bool(feats["fee_known"].mean() > 0.5),
        "lengths_from_file": bool(feats["duration_min"].notna().mean() > 0.5),
        "seconds": None,
    }
    state = RunState(scored=scored, settings=settings, key=key,
                     result={"meta": meta, "quality": quality, "patterns": _patterns(hist), "mapping": mapping})
    state.result = build_result(state)
    state.result["meta"]["seconds"] = round(time.perf_counter() - t0, 2)
    progress("done", "Done", 100)
    return state


def replan(state: RunState, settings: Settings) -> dict:
    """Re-run only the staffing step with new settings. Takes milliseconds; the model is not retrained."""
    state.settings = settings
    fee_known = state.scored["fee_known"].to_numpy()
    default_fee = state.scored["procedure_cat"].astype(str).map(settings.default_fee).astype(float)
    state.scored["fee_filled"] = np.where(fee_known, state.scored["fee"], default_fee)
    if not state.result["meta"]["lengths_from_file"]:
        state.scored["minutes"] = state.scored["procedure_cat"].astype(str).map(settings.default_minutes).astype(float)
    seconds = state.result["meta"].get("seconds")
    state.result = build_result(state)
    state.result["meta"]["seconds"] = seconds
    return state.result
