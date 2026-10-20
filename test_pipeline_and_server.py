import json
import time

import pytest

from chairforecast.pipeline import NeedsMapping, replan, run
from chairforecast.server import create_app
from chairforecast.settings import Settings


def test_forecast_run(dentrix_bytes):
    state = run(dentrix_bytes, "export.csv")
    r = state.result
    assert r["meta"]["mode"] == "forecast"
    assert len(r["days"]) == 5
    assert r["quality"]["method"] == "model"
    assert 0.55 < r["quality"]["auc"] < 0.95
    assert all(0 < p["chance"] < 1 for p in r["patients"])
    # Patients are numbered 1..n in appointment order, with no chart numbers in the output.
    assert r["patients"][0]["patient"] == 1
    text = json.dumps(r)
    sample_chart = state.key["Chart number in your system"].iloc[0]
    assert sample_chart not in text
    assert "Sample," not in text and "555-01" not in text


def test_backtest_run_includes_outcomes(open_dental_bytes):
    r = run(open_dental_bytes, "query.csv").result
    assert r["meta"]["mode"] == "backtest"
    assert {p["outcome"] for p in r["patients"]} <= {"Came", "Missed"}


def test_replan_is_fast_and_changes_tiers(dentrix_bytes):
    state = run(dentrix_bytes, "export.csv")
    before = state.result["totals"]["high"]
    t = time.perf_counter()
    after = replan(state, Settings.from_dict({"high_risk": 0.15, "medium_risk": 0.08}))
    assert time.perf_counter() - t < 2
    assert after["totals"]["high"] >= before


def test_missing_columns_ask_for_mapping():
    data = b"Visit,Who,Outcome\n2026-01-01,1,Kept\n"
    with pytest.raises(NeedsMapping) as err:
        run(data, "odd.csv")
    payload = err.value.payload
    assert "Visit" in payload["headers"]
    assert "patient_id" in payload["required"]


@pytest.fixture()
def client():
    app = create_app(8765)
    app.testing = True
    return app.test_client()


def _wait(client, job):
    for _ in range(300):
        body = client.get(f"/api/jobs/{job}").get_json()
        if body["stage"] in ("done", "error", "mapping"):
            return body
        time.sleep(0.1)
    raise AssertionError("job never finished")


def test_server_upload_flow(client, dentrix_bytes):
    resp = client.post("/api/analyze", data={"file": (__import__("io").BytesIO(dentrix_bytes), "x.csv")},
                       content_type="multipart/form-data")
    job = resp.get_json()["job"]
    body = _wait(client, job)
    assert body["stage"] == "done"
    assert "Content-Security-Policy" in resp.headers
    csv = client.get(f"/api/jobs/{job}/call-list.csv?tier=High").data.decode()
    assert csv.startswith("Patient,Date,Time")
    upd = client.post(f"/api/jobs/{job}/settings", json={"shift_hours": 10}).get_json()
    assert upd["result"]["settings"]["shift_hours"] == 10
    assert client.delete(f"/api/jobs/{job}").get_json()["ok"]
    assert client.get(f"/api/jobs/{job}").status_code == 404


def test_server_rejects_other_hosts():
    app = create_app(8765)
    c = app.test_client()
    assert c.get("/api/health", headers={"Host": "evil.example:8765"}).status_code == 403
    assert c.get("/api/health", headers={"Host": "127.0.0.1:8765"}).status_code == 200
