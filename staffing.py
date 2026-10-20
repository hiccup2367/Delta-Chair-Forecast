"""Turning no-show chances into a staffing plan.

For each day we work out how much chair time will probably be used once likely
no-shows are taken out, then plan for a day a bit busier than average (80th
percentile by default) so the office is not caught short. Two numbers come out
for each role: how many people the schedule needs if everyone shows up, and how
many it probably needs.

Cost: one pass over the visits for the daily totals, an n x hours overlap grid
for the hour-by-hour view (hours is about 10, so effectively O(n)), and an exact
distribution of the number of no-shows per day, which is O(n^2) per day. A busy
multi-doctor practice books maybe 150 visits a day, so that is about 20,000
operations: nothing.
"""

from __future__ import annotations

import math
from statistics import NormalDist

import numpy as np
import pandas as pd

from .settings import HYGIENE_CATEGORIES, Settings


def miss_count_distribution(p: np.ndarray) -> np.ndarray:
    """Exact distribution of how many of these visits are missed (Poisson binomial)."""
    dist = np.zeros(len(p) + 1)
    dist[0] = 1.0
    for i, pi in enumerate(p):
        dist[1:i + 2] = dist[1:i + 2] * (1 - pi) + dist[0:i + 1] * pi
        dist[0] *= (1 - pi)
    return dist


def _quantile(dist: np.ndarray, q: float) -> int:
    return int(np.searchsorted(np.cumsum(dist), q - 1e-12))


def _fmt_hour(h: int) -> str:
    suffix = "AM" if h < 12 else "PM"
    hh = h % 12 or 12
    return f"{hh} {suffix}"


def _staff_for_role(rows: pd.DataFrame, overlap: np.ndarray, z: float, cap_hours: float, ratio: float = 1.0) -> dict:
    if len(rows) == 0:
        return {"booked": 0, "recommended": 0, "booked_hours": 0.0, "expected_hours": 0.0}
    p = rows["p"].to_numpy()
    hrs = rows["minutes"].to_numpy() / 60.0
    booked_hours = float(hrs.sum())
    exp_hours = float(((1 - p) * hrs).sum())
    sd = math.sqrt(float((p * (1 - p) * hrs ** 2).sum()))
    plan_hours = min(booked_hours, exp_hours + z * sd)

    conc_booked = overlap.sum(axis=0)
    conc_exp = ((1 - p)[:, None] * overlap).sum(axis=0)
    conc_sd = np.sqrt(((p * (1 - p))[:, None] * overlap ** 2).sum(axis=0)) if overlap.size else np.zeros(0)
    conc_plan = np.minimum(conc_booked, conc_exp + z * conc_sd) if overlap.size else np.zeros(0)

    peak_booked = float(conc_booked.max()) if conc_booked.size else 0.0
    peak_plan = float(conc_plan.max()) if conc_plan.size else 0.0
    booked = max(math.ceil(ratio * booked_hours / cap_hours - 1e-9), math.ceil(ratio * peak_booked - 1e-9))
    rec = max(math.ceil(ratio * plan_hours / cap_hours - 1e-9), math.ceil(ratio * peak_plan - 0.15))
    return {
        "booked": int(booked), "recommended": int(min(rec, booked)),
        "booked_hours": round(booked_hours, 1), "expected_hours": round(exp_hours, 1),
        "by_hour_booked": conc_booked, "by_hour_plan": conc_plan,
    }


def plan_day(day: pd.DataFrame, settings: Settings) -> dict:
    z = NormalDist().inv_cdf(settings.planning_confidence)
    cap = settings.shift_hours * settings.target_busy_share
    p = day["p"].to_numpy()
    fee = day["fee_filled"].to_numpy()

    dist = miss_count_distribution(p)
    start_min = (day["dt"].dt.hour * 60 + day["dt"].dt.minute).to_numpy()
    end_min = start_min + day["minutes"].to_numpy()
    h0 = int(start_min.min() // 60)
    h1 = int(math.ceil(end_min.max() / 60))
    hours = np.arange(h0, max(h1, h0 + 1))
    lo = hours * 60
    overlap = np.clip(np.minimum(end_min[:, None], lo[None, :] + 60) - np.maximum(start_min[:, None], lo[None, :]), 0, 60) / 60.0

    is_hyg = day["procedure_cat"].astype(str).isin(HYGIENE_CATEGORIES).to_numpy()
    hyg = _staff_for_role(day[is_hyg], overlap[is_hyg], z, cap)
    doc = _staff_for_role(day[~is_hyg], overlap[~is_hyg], z, cap, ratio=settings.assistants_per_doctor)

    expected_patients = float((1 - p).sum())
    plan_patients = expected_patients + z * math.sqrt(float((p * (1 - p)).sum()))
    desk_booked = max(1, math.ceil(len(day) / settings.patients_per_front_desk))
    desk_rec = max(1, math.ceil(plan_patients / settings.patients_per_front_desk))

    start_hour = start_min // 60
    empty = (p[:, None] * overlap * 60).sum(axis=0)
    by_hour = []
    for j, h in enumerate(hours):
        starting = start_hour == h
        by_hour.append({
            "hour": int(h), "label": _fmt_hour(int(h)),
            "starting": int(starting.sum()),
            "chairs_booked": round(float(overlap[:, j].sum()), 2),
            "chairs_expected": round(float(((1 - p) * overlap[:, j]).sum()), 2),
            "empty_minutes": round(float(empty[j]), 0),
            "chance_any_miss": round(float(1 - np.prod(1 - p[starting])) if starting.any() else 0.0, 3),
            "hygienists": int(math.ceil(hyg["by_hour_plan"][j] - 0.15)) if len(hyg.get("by_hour_plan", [])) else 0,
            "hygienists_booked": int(math.ceil(hyg["by_hour_booked"][j] - 1e-9)) if len(hyg.get("by_hour_booked", [])) else 0,
            "assistants": int(math.ceil(settings.assistants_per_doctor * doc["by_hour_plan"][j] - 0.15)) if len(doc.get("by_hour_plan", [])) else 0,
            "assistants_booked": int(math.ceil(settings.assistants_per_doctor * doc["by_hour_booked"][j] - 1e-9)) if len(doc.get("by_hour_booked", [])) else 0,
            "flag": bool(empty[j] >= settings.empty_minutes_to_flag),
        })
    for role in (hyg, doc):
        role.pop("by_hour_booked", None)
        role.pop("by_hour_plan", None)

    high = int((p >= settings.high_risk).sum())
    medium = int(((p >= settings.medium_risk) & (p < settings.high_risk)).sum())
    date = pd.Timestamp(day["dt"].iloc[0]).normalize()
    result = {
        "date": str(date.date()),
        "label": f"{date.strftime('%a %b')} {date.day}",
        "visits": int(len(day)),
        "expected_misses": round(float(p.sum()), 1),
        "misses_low": _quantile(dist, 0.10),
        "misses_high": _quantile(dist, 0.90),
        "chance_three_plus": round(float(dist[3:].sum()), 3),
        "booked_production": round(float(fee.sum()), 0),
        "production_at_risk": round(float((p * fee).sum()), 0),
        "high_risk": high, "medium_risk": medium,
        "hygienists": hyg, "assistants": doc,
        "front_desk": {"booked": desk_booked, "recommended": min(desk_rec, desk_booked)},
        "hours": by_hour,
    }
    result["suggestions"] = suggestions(result)
    return result


def suggestions(day: dict) -> list[str]:
    out = []
    flagged = [h for h in day["hours"] if h["flag"]]
    if day["high_risk"]:
        n = day["high_risk"]
        out.append(f"Call the {n} high-risk patient{'s' if n != 1 else ''} two business days ahead. "
                   "A real phone call does more for these visits than a text reminder.")
    if flagged:
        worst = sorted(flagged, key=lambda h: -h["empty_minutes"])[:3]
        names = ", ".join(f"{h['label']} (about {int(h['empty_minutes'])} min)" for h in worst)
        out.append(f"Most likely empty chair time: {names}. Double-book a short visit there or work the ASAP list first.")
    for role, title in (("hygienists", "hygienist"), ("assistants", "assistant")):
        r = day[role]
        if r["recommended"] < r["booked"]:
            diff = r["booked"] - r["recommended"]
            out.append(f"The schedule asks for {r['booked']} {title}{'s' if r['booked'] != 1 else ''}, but expected "
                       f"turnout needs {r['recommended']}. If you can't fill the gap, {diff} {title} could take a "
                       "shorter shift.")
    if day["chance_three_plus"] >= 0.5:
        out.append(f"There is a {round(day['chance_three_plus'] * 100)}% chance of three or more no-shows. "
                   "Keep the ASAP list handy.")
    if not out:
        out.append("This day looks steady. Normal reminders should be enough.")
    return out


def plan_all(scored: pd.DataFrame, settings: Settings) -> list[dict]:
    if scored.empty:
        return []
    days = scored["dt"].dt.normalize()
    return [plan_day(group, settings) for _, group in scored.groupby(days, sort=True)]
