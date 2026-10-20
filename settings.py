"""Practice settings. Every number here can be changed from the Settings panel.

Fees and lengths are only used when the export does not include them. They are
rough national averages meant as a starting point; a practice should replace
them with its own fee schedule.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

CATEGORIES = [
    "Hygiene", "Exam and x-rays", "Fillings", "Crowns and bridges", "Root canal",
    "Periodontal", "Extraction and surgery", "Dentures and implants", "Orthodontics",
    "Emergency", "Other",
]

# Which team member a visit type mostly occupies.
HYGIENE_CATEGORIES = {"Hygiene", "Periodontal"}


@dataclass
class Settings:
    medium_risk: float = 0.12        # chance of missing at or above this is "Medium"
    high_risk: float = 0.25          # at or above this is "High"
    shift_hours: float = 8.0
    target_busy_share: float = 0.85  # share of a shift a clinician can realistically spend chairside
    assistants_per_doctor: float = 1.0
    patients_per_front_desk: int = 30
    planning_confidence: float = 0.80  # plan for a day this busy or busier 80% of the time
    empty_minutes_to_flag: int = 30    # flag an hour for double booking once this many chair minutes are likely empty
    practice_name: str = "our office"
    default_fee: dict = field(default_factory=lambda: {
        "Hygiene": 160, "Exam and x-rays": 110, "Fillings": 230, "Crowns and bridges": 1150,
        "Root canal": 1000, "Periodontal": 280, "Extraction and surgery": 320,
        "Dentures and implants": 1400, "Orthodontics": 220, "Emergency": 180, "Other": 150,
    })
    default_minutes: dict = field(default_factory=lambda: {
        "Hygiene": 60, "Exam and x-rays": 30, "Fillings": 60, "Crowns and bridges": 90,
        "Root canal": 90, "Periodontal": 60, "Extraction and surgery": 60,
        "Dentures and implants": 60, "Orthodontics": 30, "Emergency": 30, "Other": 45,
    })

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Settings":
        s = cls()
        if not data:
            return s
        for key, val in data.items():
            if not hasattr(s, key):
                continue
            current = getattr(s, key)
            try:
                if isinstance(current, dict) and isinstance(val, dict):
                    merged = dict(current)
                    merged.update({k: float(v) for k, v in val.items() if k in current})
                    setattr(s, key, merged)
                elif isinstance(current, bool):
                    setattr(s, key, bool(val))
                elif isinstance(current, int):
                    setattr(s, key, int(float(val)))
                elif isinstance(current, float):
                    setattr(s, key, float(val))
                elif isinstance(current, str):
                    setattr(s, key, str(val)[:80])
            except (TypeError, ValueError):
                continue
        s.medium_risk = min(max(s.medium_risk, 0.01), 0.95)
        s.high_risk = min(max(s.high_risk, s.medium_risk + 0.01), 0.99)
        s.shift_hours = min(max(s.shift_hours, 1), 16)
        s.target_busy_share = min(max(s.target_busy_share, 0.3), 1.0)
        s.planning_confidence = min(max(s.planning_confidence, 0.5), 0.99)
        s.patients_per_front_desk = max(s.patients_per_front_desk, 5)
        return s
