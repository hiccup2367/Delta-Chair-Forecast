from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from chairforecast.synthetic import generate, to_dentrix_style, to_open_dental_style  # noqa: E402


@pytest.fixture(scope="session")
def visits():
    return generate(n_patients=900, months=10, upcoming_days=5, seed=5)


@pytest.fixture(scope="session")
def dentrix_bytes(visits):
    return to_dentrix_style(visits).encode()


@pytest.fixture(scope="session")
def open_dental_bytes():
    v = generate(n_patients=800, months=9, upcoming_days=0, seed=8)
    return to_open_dental_style(v).encode()
