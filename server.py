"""The local web server behind the app.

It listens on 127.0.0.1 only, so other computers on the office network cannot
reach it, and it refuses requests whose Host header is not this computer (which
blocks DNS-rebinding tricks from web pages open in other tabs). Uploaded files
are held in memory, never written to disk, and are forgotten when the person
clicks "Start over", closes the app, or after two idle hours.

Every page response carries a Content Security Policy that only allows loading
files from this server, so the page itself cannot send data anywhere else.
"""

from __future__ import annotations

import io
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, Response, abort, jsonify, request, send_from_directory

from .ingest import IngestError, inspect_file
from .pipeline import NeedsMapping, RunState, replan, run
from .settings import Settings

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DATA = ROOT / "data"
SAMPLES = {
    "forecast": "sample_dentrix_style.csv",
    "check": "sample_open_dental_style.csv",
}
JOB_TTL_SECONDS = 2 * 60 * 60
MAX_UPLOAD_MB = 750


class Job:
    def __init__(self, data: bytes, filename: str, mapping: dict | None, settings: Settings):
        self.id = uuid.uuid4().hex
        self.data = data
        self.filename = filename
        self.mapping = mapping
        self.settings = settings
        self.stage = "queued"
        self.text = "Getting started"
        self.pct = 0
        self.state: RunState | None = None
        self.error: str | None = None
        self.needs_mapping: dict | None = None
        self.touched = time.time()
        self.lock = threading.Lock()

    def progress(self, stage: str, text: str, pct=None) -> None:
        self.stage, self.text = stage, text
        if pct is not None:
            self.pct = pct

    def work(self) -> None:
        try:
            self.state = run(self.data, self.filename, self.mapping, self.settings, self.progress)
            self.stage = "done"
        except NeedsMapping as nm:
            self.needs_mapping = nm.payload
            self.stage = "mapping"
        except IngestError as exc:
            self.error = str(exc)
            self.stage = "error"
        except Exception as exc:  # noqa: BLE001  shown to the person, so keep it plain
            self.error = ("Something in this file stopped the analysis "
                          f"({exc.__class__.__name__}). Try exporting it again as CSV, or check the "
                          "troubleshooting section of the user guide.")
            self.stage = "error"
            import traceback
            traceback.print_exc()


def create_app(port: int = 8765) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    jobs: dict[str, Job] = {}
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}", "127.0.0.1", "localhost"}

    def sweep() -> None:
        now = time.time()
        for jid in [j for j, job in jobs.items() if now - job.touched > JOB_TTL_SECONDS]:
            jobs.pop(jid, None)

    def get_job(jid: str) -> Job:
        job = jobs.get(jid)
        if not job:
            abort(404, "This session has ended. Drop the file in again to start over.")
        job.touched = time.time()
        return job

    def start(job: Job) -> Response:
        sweep()
        jobs[job.id] = job
        threading.Thread(target=job.work, daemon=True).start()
        return jsonify({"job": job.id})

    @app.before_request
    def only_this_computer():
        if request.host not in allowed_hosts:
            abort(403)

    @app.after_request
    def lock_down(resp: Response) -> Response:
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "connect-src 'self'; font-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(413)
    def too_big(_):
        return jsonify({"error": f"That file is over {MAX_UPLOAD_MB} MB. Export a shorter date range, such as the last 18 months."}), 413

    @app.errorhandler(404)
    def missing(err):
        if request.path.startswith("/api/"):
            return jsonify({"error": getattr(err, "description", "Not found")}), 404
        return err

    # ---- pages ---------------------------------------------------------- #
    @app.get("/")
    def index():
        return send_from_directory(WEB, "index.html")

    @app.get("/docs/<path:name>")
    def docs(name: str):
        resp = send_from_directory(ROOT / "docs", name)
        if name.endswith(".md"):
            resp.headers["Content-Type"] = "text/plain; charset=utf-8"
        return resp

    @app.get("/<path:name>")
    def static_files(name: str):
        return send_from_directory(WEB, name)

    # ---- api ------------------------------------------------------------ #
    @app.post("/api/analyze")
    def analyze():
        settings = Settings.from_dict(request.get_json(silent=True) or {}) if request.is_json else Settings()
        sample = request.args.get("sample")
        if sample:
            name = SAMPLES.get(sample)
            if not name or not (DATA / name).exists():
                return jsonify({"error": "That sample file is missing from the data folder."}), 404
            return start(Job((DATA / name).read_bytes(), name, None, settings))
        upload = request.files.get("file")
        if not upload or not upload.filename:
            return jsonify({"error": "No file arrived. Try dropping it in again."}), 400
        data = upload.read()
        return start(Job(data, upload.filename, None, settings))

    @app.get("/api/jobs/<jid>")
    def status(jid: str):
        job = get_job(jid)
        body = {"stage": job.stage, "text": job.text, "pct": job.pct}
        if job.stage == "done":
            body["result"] = job.state.result
        elif job.stage == "error":
            body["error"] = job.error
        elif job.stage == "mapping":
            body["mapping"] = job.needs_mapping
        return jsonify(body)

    @app.post("/api/jobs/<jid>/mapping")
    def remap(jid: str):
        old = get_job(jid)
        mapping = (request.get_json(silent=True) or {}).get("mapping") or {}
        job = Job(old.data, old.filename, mapping, old.settings)
        jobs.pop(jid, None)
        return start(job)

    @app.post("/api/jobs/<jid>/settings")
    def update_settings(jid: str):
        job = get_job(jid)
        if not job.state:
            return jsonify({"error": "The analysis hasn't finished yet."}), 409
        with job.lock:
            settings = Settings.from_dict({**job.state.settings.to_dict(), **(request.get_json(silent=True) or {})})
            return jsonify({"result": replan(job.state, settings)})

    @app.get("/api/jobs/<jid>/call-list.csv")
    def call_list(jid: str):
        job = get_job(jid)
        if not job.state:
            abort(409)
        tier = request.args.get("tier")
        rows = job.state.result["patients"]
        if tier in ("High", "Medium", "Low"):
            rows = [r for r in rows if r["tier"] == tier]
        out = io.StringIO()
        out.write("Patient,Date,Time,Visit,Provider,Chance of missing,Risk,Why\n")
        for r in rows:
            why = "; ".join(r["why"]).replace('"', "'")
            out.write(f'Patient {r["patient"]},{r["date"]},{r["time"]},{r["visit"]},{r["provider"]},'
                      f'{r["chance"] * 100:.0f}%,{r["tier"]},"{why}"\n')
        return Response(out.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=call-list.csv"})

    @app.get("/api/jobs/<jid>/patient-key.csv")
    def patient_key(jid: str):
        job = get_job(jid)
        if not job.state:
            abort(409)
        return Response(job.state.key.to_csv(index=False), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=patient-key-KEEP-PRIVATE.csv"})

    @app.get("/api/jobs/<jid>/mapping")
    def mapping_options(jid: str):
        job = get_job(jid)
        shape = inspect_file(job.data, job.filename)
        current = job.state.result.get("mapping", shape.mapping) if job.state else shape.mapping
        payload = NeedsMapping("Change any column that was matched wrong, then run it again.",
                               shape.headers, current).payload
        return jsonify({"mapping": payload})

    @app.delete("/api/jobs/<jid>")
    @app.post("/api/jobs/<jid>/forget")
    def forget(jid: str):
        jobs.pop(jid, None)
        return jsonify({"ok": True})

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    return app
