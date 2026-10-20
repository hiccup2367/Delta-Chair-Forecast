import io

import pandas as pd

from chairforecast.columns import detect_columns, is_identifying
from chairforecast.ingest import classify_status_value, inspect_file, load_columns, standardize


def test_detects_dentrix_headers_and_skips_title_lines(dentrix_bytes):
    shape = inspect_file(dentrix_bytes, "export.csv")
    assert shape.header_row == 3
    m = shape.mapping
    assert m["patient_id"] == "Chart #"
    assert m["appt_date"] == "Appt Date"
    assert m["status"] == "Status"
    assert "Patient Name" in shape.skipped_identifying
    assert "Home Phone" in shape.skipped_identifying


def test_detects_open_dental_headers(open_dental_bytes):
    m = inspect_file(open_dental_bytes, "query.csv").mapping
    assert m["patient_id"] == "PatNum"
    assert m["appt_datetime"] == m["appt_date"] == "AptDateTime"
    assert m["insurance"] == "CarrierName"


def test_name_and_contact_columns_are_never_matched():
    headers = ["Patient Name", "LName", "FName", "Email", "Cell Phone", "Address 1", "Chart", "Date", "Status"]
    m = detect_columns(headers)
    assert set(m.values()) <= {"Chart", "Date", "Status"}
    for h in headers[:6]:
        assert is_identifying(h)
    assert not is_identifying("CarrierName")


def test_names_never_reach_memory(dentrix_bytes):
    shape = inspect_file(dentrix_bytes, "export.csv")
    raw = load_columns(dentrix_bytes, shape, shape.mapping)
    joined = " ".join(map(str, raw.head(500).to_numpy().ravel()))
    assert "Sample," not in joined and "555-01" not in joined
    assert not any(is_identifying(c) for c in raw.columns)


def test_status_vocabulary():
    assert classify_status_value("Broken") == "no_show"
    assert classify_status_value("Late Cancel") == "no_show"
    assert classify_status_value("Complete") == "kept"
    assert classify_status_value("Cancelled") == "cancelled"
    assert classify_status_value("Confirmed") == "scheduled"
    assert classify_status_value("") == "scheduled"
    assert classify_status_value("5", "aptstatus") == "no_show"
    assert classify_status_value("2.0", "aptstatus") == "kept"
    assert classify_status_value("Y", "noshow") == "no_show"


def test_excel_and_semicolon_files(visits):
    small = visits.head(400)
    df = pd.DataFrame({
        "Patient": small["chart"], "Date": small["dt"].dt.strftime("%d.%m.%Y %H:%M"),
        "Status": small["status"].map({"kept": "Kept", "no_show": "No show", "cancelled": "Cancelled", "scheduled": "Booked"}),
    })
    # semicolon separated
    data = df.to_csv(sep=";", index=False).encode()
    shape = inspect_file(data, "x.txt")
    assert shape.sep == ";"
    # excel
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    shape = inspect_file(buf.getvalue(), "x.xlsx")
    assert shape.kind == "excel"
    raw = load_columns(buf.getvalue(), shape, {"patient_id": "Patient", "appt_date": "Date", "status": "Status"})
    out, notes = standardize(raw, {"patient_id": "Patient", "appt_date": "Date", "status": "Status"})
    assert len(out) == 400
    assert out["dt"].notna().all()


def test_age_replaces_birthdate(dentrix_bytes):
    shape = inspect_file(dentrix_bytes, "export.csv")
    raw = load_columns(dentrix_bytes, shape, shape.mapping)
    out, _ = standardize(raw, shape.mapping)
    assert "birthdate" not in out.columns
    assert out["age"].between(0, 110).mean() > 0.95
