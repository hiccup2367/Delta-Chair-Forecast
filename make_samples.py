"""Rebuild the two sample exports in data/.

    python scripts/make_samples.py

sample_dentrix_style.csv     18 months of history plus two weeks of upcoming visits.
                             Opens in forecast mode.
sample_open_dental_style.csv History only. Opens in check mode, where the last week
                             is predicted and compared with what really happened.
"""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chairforecast.synthetic import generate, to_dentrix_style, to_open_dental_style  # noqa: E402

DATA = Path(__file__).resolve().parents[1] / "data"


def main() -> None:
    DATA.mkdir(exist_ok=True)
    dentrix = generate(seed=11, upcoming_days=10)
    (DATA / "sample_dentrix_style.csv").write_text(to_dentrix_style(dentrix), encoding="utf-8")
    od = generate(seed=29, n_patients=2200, months=14, upcoming_days=0, anchor="2026-10-16")
    (DATA / "sample_open_dental_style.csv").write_text(to_open_dental_style(od), encoding="utf-8")
    print(f"Wrote {len(dentrix):,} and {len(od):,} rows to {DATA}")


if __name__ == "__main__":
    main()
