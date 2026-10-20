import numpy as np
import pandas as pd

from chairforecast.features import build_features, insurance_group, procedure_category
from chairforecast.settings import Settings
from chairforecast.staffing import miss_count_distribution, plan_day


def _frame(rows):
    df = pd.DataFrame(rows, columns=["pid_raw", "dt", "status"])
    df["dt"] = pd.to_datetime(df["dt"])
    for col, val in (("procedure_raw", "Prophy"), ("insurance_raw", "Delta Dental PPO"), ("provider", "HYG1"),
                     ("operatory", "1"), ("fee", np.nan), ("duration_min", np.nan),
                     ("lead_time_days", 10.0), ("age", 40.0)):
        df[col] = val
    return df


def test_history_features_only_look_backwards():
    df = _frame([
        ("A", "2026-01-05 09:00", "no_show"),
        ("A", "2026-02-05 09:00", "kept"),
        ("A", "2026-03-05 09:00", "no_show"),
        ("A", "2026-04-05 09:00", "scheduled"),
        ("B", "2026-01-06 10:00", "kept"),
    ])
    f = build_features(df, Settings())
    a = f[f["pid_raw"] == "A"].sort_values("dt")
    assert a["prior_no_shows"].tolist() == [0, 1, 1, 2]
    assert a["prior_visits"].tolist() == [0, 1, 2, 3]
    assert a["first_visit"].tolist() == [1, 0, 0, 0]


def test_history_cutoff_hides_held_back_outcomes():
    df = _frame([
        ("A", "2026-01-05 09:00", "no_show"),
        ("A", "2026-03-05 09:00", "no_show"),
        ("A", "2026-03-06 09:00", "kept"),
    ])
    f = build_features(df, Settings(), history_cutoff=pd.Timestamp("2026-03-01"))
    assert f.sort_values("dt")["prior_no_shows"].tolist() == [0, 1, 1]


def test_categories():
    assert procedure_category("D1110 Pro, D0120 PerEx") == "Hygiene"
    assert procedure_category("D2740 crown + D2950 buildup") == "Crowns and bridges"
    assert procedure_category("RCT-Molar") == "Root canal"
    assert procedure_category("") == "Other"
    assert insurance_group("Keystone First (Medicaid)") == "Medicaid or CHIP"
    assert insurance_group("") == "Self-pay or none"
    assert insurance_group("Aetna DMO") == "HMO or DHMO"
    assert insurance_group("MetLife PDP") == "PPO or commercial"


def test_miss_distribution_matches_brute_force():
    p = np.array([0.1, 0.3, 0.5, 0.05])
    dist = miss_count_distribution(p)
    brute = np.zeros(5)
    for mask in range(16):
        bits = [(mask >> i) & 1 for i in range(4)]
        prob = np.prod([pi if b else 1 - pi for pi, b in zip(p, bits)])
        brute[sum(bits)] += prob
    assert np.allclose(dist, brute)
    assert abs(dist.sum() - 1) < 1e-12


def test_staffing_never_recommends_more_than_booked_and_flags_empty_hours():
    s = Settings()
    day = pd.DataFrame({
        "dt": pd.to_datetime(["2026-05-04 08:00"] * 4 + ["2026-05-04 10:00"] * 2),
        "p": [0.6, 0.6, 0.6, 0.05, 0.02, 0.02],
        "minutes": [60] * 6,
        "fee_filled": [200.0] * 6,
        "procedure_cat": ["Hygiene"] * 4 + ["Fillings"] * 2,
    })
    plan = plan_day(day, s)
    for role in ("hygienists", "assistants", "front_desk"):
        assert plan[role]["recommended"] <= plan[role]["booked"]
    eight = next(h for h in plan["hours"] if h["hour"] == 8)
    assert eight["flag"]
    assert plan["hygienists"]["booked"] == 4
    assert plan["hygienists"]["recommended"] < 4
    assert abs(plan["expected_misses"] - 1.9) < 0.05
