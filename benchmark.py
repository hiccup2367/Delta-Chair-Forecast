"""Time the full pipeline on a large made-up export.

    python scripts/benchmark.py            # about 300,000 visits
    python scripts/benchmark.py 1000000    # about a million

The rows are copies of the sample practice with distinct chart numbers, as if
a multi-location group exported every office at once.
"""

from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from chairforecast.pipeline import run  # noqa: E402
from chairforecast.synthetic import generate, to_dentrix_style  # noqa: E402


def main(target_rows: int = 300_000) -> None:
    base = generate(seed=3, upcoming_days=10)
    copies = max(1, target_rows // len(base))
    parts = []
    for i in range(copies):
        part = base.copy()
        part["chart"] = part["chart"] + f"-{i}"
        parts.append(part)
    big = pd.concat(parts, ignore_index=True).sort_values("dt", kind="mergesort")
    data = to_dentrix_style(big).encode()
    print(f"{len(big):,} rows, {len(data) / 1e6:.0f} MB")

    t0 = time.perf_counter()
    last = [t0]

    def progress(stage, text, pct=None):
        now = time.perf_counter()
        print(f"  {now - last[0]:6.2f}s  {text}")
        last[0] = now

    state = run(data, "benchmark.csv", progress=progress)
    print(f"Total {time.perf_counter() - t0:.1f}s for {state.result['meta']['rows_read']:,} rows; "
          f"{len(state.result['days'])} days planned")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 300_000)
