"""Made-up practice data for demos, tests and benchmarks.

Every name, chart number, phone number and appointment in here is invented.
Phone numbers use the 555-01xx block, which is reserved for fiction.

The generator simulates a small practice (two dentists, three hygienists,
six operatories) with patients whose chance of missing depends on things that
really do matter in dental scheduling: how far ahead they booked, their own
history, the visit type, the day and time, and the payer.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FIRST = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Avery", "Quinn", "Parker",
         "Drew", "Reese", "Rowan", "Sage", "Emerson", "Hayden", "Kendall", "Logan", "Peyton", "Skyler"]
LAST = ["Sample", "Example", "Testcase", "Demo", "Placeholder", "Fakename", "Mockley", "Dummyson",
        "Notreal", "Pretend", "Fictional", "Madeup", "Imaginary", "Stand-in", "Proxy", "Synth"]

INSURANCE = [  # (carrier as exported, group effect, share)
    ("Delta Dental PPO", 0.0, 0.26), ("MetLife PDP", 0.0, 0.12), ("Cigna DPPO", 0.0, 0.10),
    ("Guardian", 0.0, 0.07), ("United Concordia", 0.0, 0.05), ("Aetna DMO", 0.15, 0.07),
    ("Keystone First (Medicaid)", 0.5, 0.10), ("Health Partners CHIP", 0.45, 0.07),
    ("Self Pay", 0.35, 0.16),
]

VISITS = {  # category: (codes text, open-dental short text, minutes, fee, logit effect, who)
    "recall": ("D1110 Pro, D0120 PerEx, D0274 4BW", "PerEx, Pro, 4BW", 60, 210, 0.20, "hyg"),
    "child": ("D1120 ChildPro, D1206 Fl, D0120 PerEx", "PerEx, ChildPro, Fl", 45, 150, 0.10, "hyg"),
    "perio": ("D4910 PerioMaint", "PerioMaint", 60, 175, 0.05, "hyg"),
    "srp": ("D4341 SRP 4+ teeth", "SRP 4+", 60, 290, 0.0, "hyg"),
    "newpt": ("D0150 CompEx, D0210 FMX, D1110 Pro", "CompEx, FMX, Pro", 90, 330, 0.30, "hyg"),
    "filling": ("D2392 Comp 2s post", "Comp-2S", 60, 240, 0.0, "doc"),
    "crown_prep": ("D2740 Crown porc/cer", "Crn-Prep", 90, 1250, -0.45, "doc"),
    "crown_seat": ("D2740 Seat Crown", "Crn-Seat", 30, 0, -0.55, "doc"),
    "rct": ("D3330 RCT molar", "RCT-Molar", 90, 1150, -0.65, "doc"),
    "ext": ("D7140 Ext erupted", "Ext", 45, 260, -0.2, "doc"),
    "emerg": ("D0140 LimEx, D9110 Palliative", "LimEx, Palliative", 30, 180, -0.9, "doc"),
    "consult": ("D9310 Consult", "Consult", 30, 120, 0.25, "doc"),
    "implant": ("D6010 Implant body", "Implant", 90, 2100, -0.5, "doc"),
}
HYG_MIX = (["recall"] * 60 + ["child"] * 14 + ["perio"] * 14 + ["srp"] * 6 + ["newpt"] * 6)
DOC_MIX = (["filling"] * 38 + ["crown_prep"] * 12 + ["crown_seat"] * 10 + ["rct"] * 6 + ["ext"] * 8
           + ["emerg"] * 12 + ["consult"] * 8 + ["implant"] * 3)


def _patients(rng: np.random.Generator, n: int, anchor: pd.Timestamp) -> pd.DataFrame:
    ins_names = [i[0] for i in INSURANCE]
    ins_p = np.array([i[2] for i in INSURANCE]); ins_p /= ins_p.sum()
    age = np.clip(rng.gamma(4.0, 10.0, n), 3, 92)
    first = rng.choice(FIRST, n); last = rng.choice(LAST, n)
    return pd.DataFrame({
        "pid": np.arange(1, n + 1),
        "chart": [f"{l[:2].upper()}{1000 + i}" for i, l in enumerate(last)],
        "first": first, "last": last,
        "age": age,
        "birth": anchor - pd.to_timedelta((age * 365.25).astype(int), unit="D"),
        "insurance": rng.choice(ins_names, n, p=ins_p),
        "u": rng.normal(0, 1, n),
        "phone": [f"(610) 555-01{rng.integers(0, 100):02d}" for _ in range(n)],
    })


def generate(n_patients: int = 2600, months: int = 18, upcoming_days: int = 10, seed: int = 11,
             anchor: str = "2026-10-16", per_day_scale: float = 1.0) -> pd.DataFrame:
    """Return a tidy frame of visits. anchor = last day with known outcomes."""
    rng = np.random.default_rng(seed)
    anchor_ts = pd.Timestamp(anchor)
    start = anchor_ts - pd.DateOffset(months=months)
    pts = _patients(rng, n_patients, anchor_ts)
    ins_effect = {i[0]: i[1] for i in INSURANCE}

    future_days = pd.bdate_range(anchor_ts + pd.Timedelta(days=1), periods=upcoming_days)
    all_days = pd.bdate_range(start, anchor_ts).append(future_days)

    rows = []
    seen_before = np.zeros(n_patients + 1, dtype=bool)
    for day in all_days:
        last_hour = 13 if day.weekday() == 4 else 17
        # Hygiene: three hygienists, hourly, lunch at noon.
        for hyg in range(3):
            for hour in range(7, last_hour):
                if hour == 12 or rng.random() > 0.93 * per_day_scale:
                    continue
                rows.append((day, hour, 0, f"HYG{hyg + 1}", f"OP{hyg + 4}", rng.choice(HYG_MIX)))
        # Doctors: two dentists, mixed lengths.
        for doc in range(2):
            t = 8 * 60
            end = (last_hour) * 60
            while t < end:
                kind = rng.choice(DOC_MIX)
                mins = VISITS[kind][2]
                if 12 * 60 <= t < 13 * 60:
                    t = 13 * 60
                    continue
                if rng.random() < 0.9 * per_day_scale:
                    rows.append((day, t // 60, t % 60, f"DDS{doc + 1}", f"OP{doc * 1 + 1 + (t // 60) % 2}", kind))
                t += mins

    n = len(rows)
    vis = pd.DataFrame(rows, columns=["day", "hour", "minute", "provider", "op", "kind"])
    vis["dt"] = vis["day"] + pd.to_timedelta(vis["hour"] * 60 + vis["minute"], unit="m")

    # Patients: new-patient and child visits pick matching people; others are random.
    pid = rng.integers(1, n_patients + 1, n)
    young = pts.index[pts["age"] < 14].to_numpy() + 1
    child = vis["kind"].eq("child").to_numpy()
    if len(young):
        pid[child] = rng.choice(young, child.sum())
    vis["pid"] = pid
    vis = vis.sort_values("dt", kind="mergesort").reset_index(drop=True)

    first_seen = ~vis.duplicated("pid")
    vis["new_patient"] = first_seen.to_numpy()

    kinds = vis["kind"].to_numpy()
    recall = np.isin(kinds, ["recall", "child", "perio"])
    lead = np.where(recall & (rng.random(n) < 0.55), rng.integers(150, 190, n), rng.integers(2, 40, n))
    lead = np.where(kinds == "emerg", rng.integers(0, 2, n), lead)
    lead = np.where(kinds == "crown_seat", rng.integers(14, 28, n), lead)
    vis["lead"] = lead

    p = pts.set_index("pid").loc[vis["pid"]].reset_index()
    eff = np.array([VISITS[k][4] for k in kinds])
    age = p["age"].to_numpy()
    hour = vis["hour"].to_numpy()
    wd = vis["dt"].dt.weekday.to_numpy()
    logit = (-3.5 + 0.95 * p["u"].to_numpy() + p["insurance"].map(ins_effect).to_numpy()
             + 0.011 * np.minimum(lead, 120) - 0.5 * (lead <= 2) + eff
             + 0.25 * (wd == 0) + 0.30 * (wd == 4) + 0.35 * (hour <= 7) + 0.25 * (hour >= 16)
             + 0.40 * ((age >= 18) & (age < 30)) - 0.30 * (age >= 65)
             + 0.30 * vis["new_patient"].to_numpy())
    miss = rng.random(n) < 1 / (1 + np.exp(-logit))
    cancel = rng.random(n) < 0.05

    future = vis["dt"].to_numpy() > (anchor_ts + pd.Timedelta(days=1)).to_datetime64()
    status = np.where(future, "scheduled", np.where(miss, "no_show", np.where(cancel, "cancelled", "kept")))

    out = pd.DataFrame({
        "dt": vis["dt"], "pid": vis["pid"], "chart": p["chart"], "first": p["first"], "last": p["last"],
        "birth": p["birth"], "insurance": p["insurance"], "phone": p["phone"], "provider": vis["provider"],
        "op": vis["op"], "kind": kinds, "minutes": [VISITS[k][2] for k in kinds],
        "fee": [VISITS[k][3] for k in kinds], "booked_on": vis["dt"].dt.normalize() - pd.to_timedelta(lead, unit="D"),
        "status": status,
    })
    return out


def to_dentrix_style(v: pd.DataFrame) -> str:
    """CSV laid out like a typical Dentrix appointment list, with report title lines on top."""
    status = v["status"].map({"kept": "Complete", "no_show": "Broken", "cancelled": "Cancelled", "scheduled": "Scheduled"})
    df = pd.DataFrame({
        "Appt Date": v["dt"].dt.strftime("%m/%d/%Y"),
        "Appt Time": v["dt"].dt.strftime("%I:%M %p").str.lstrip("0"),
        "Length": v["minutes"],
        "Patient Name": v["last"] + ", " + v["first"],
        "Chart #": v["chart"],
        "Provider": v["provider"],
        "Op": v["op"],
        "Procedures": v["kind"].map(lambda k: VISITS[k][0]),
        "Status": status,
        "Primary Ins Carrier": v["insurance"].replace({"Self Pay": ""}),
        "Birthdate": v["birth"].dt.strftime("%m/%d/%Y"),
        "Date Scheduled": v["booked_on"].dt.strftime("%m/%d/%Y"),
        "Sched Production": v["fee"].map(lambda f: f"${f:,.2f}"),
        "Home Phone": v["phone"],
    })
    title = ("Appointment List,SAMPLE DATA - every patient and visit here is fabricated\n"
             f"Date range,{df['Appt Date'].iloc[0]} to {df['Appt Date'].iloc[-1]}\n\n")
    return title + df.to_csv(index=False)


def to_open_dental_style(v: pd.DataFrame) -> str:
    """CSV with Open Dental query-style column names and numeric AptStatus codes."""
    code = v["status"].map({"kept": 2, "no_show": 5, "cancelled": 3, "scheduled": 1})
    df = pd.DataFrame({
        "PatNum": v["pid"], "LName": v["last"], "FName": v["first"],
        "AptDateTime": v["dt"].dt.strftime("%Y-%m-%d %H:%M:%S"),
        "AptStatus": code,
        "ProcDescript": v["kind"].map(lambda k: VISITS[k][1]),
        "ProvAbbr": v["provider"], "Op": v["op"], "CarrierName": v["insurance"],
        "Birthdate": v["birth"].dt.strftime("%Y-%m-%d"),
        "SecDateTEntry": v["booked_on"].dt.strftime("%Y-%m-%d"),
        "ProcFee": v["fee"], "WirelessPhone": v["phone"],
    })
    return df.to_csv(index=False)
