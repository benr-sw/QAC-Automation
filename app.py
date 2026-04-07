import io
import os
import queue
import threading
import uuid

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from src.workflow import run_analyze_again, run_workflow

app = Flask(__name__, static_folder="static")
CORS(app)

# In-memory job store: job_id -> job dict
_jobs: dict = {}
_jobs_lock = threading.Lock()


def _make_job():
    return {
        "log_queue": queue.Queue(),
        "result_queue": queue.Queue(),
        "messages": [],
        "result": None,
        "running": True,
        "run_dir": None,
    }


def _drain_job(job_id: str):
    """Drain log_queue and result_queue into the job dict. Call before reading."""
    job = _jobs.get(job_id)
    if not job:
        return
    while not job["log_queue"].empty():
        try:
            job["messages"].append(job["log_queue"].get_nowait())
        except queue.Empty:
            break
    if job["result"] is None and not job["result_queue"].empty():
        try:
            result = job["result_queue"].get_nowait()
            job["result"] = result
            job["running"] = False
            if result.get("run_dir"):
                job["run_dir"] = result["run_dir"]
        except queue.Empty:
            pass


def _file_to_bytesio(file_storage):
    """Wrap a Flask FileStorage in BytesIO so the engine can seek/read it."""
    if file_storage is None:
        return None
    data = file_storage.read()
    if not data:
        return None
    buf = io.BytesIO(data)
    buf.name = file_storage.filename
    return buf


# ---- Routes ----

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/start", methods=["POST"])
def start():
    sheet_url = request.form.get("sheet_url", "").strip()
    if not sheet_url:
        return jsonify({"error": "sheet_url is required"}), 400

    classroom_override = request.form.get("classroom_override", "").strip() or None
    reviewer_notes = request.form.get("reviewer_notes", "").strip() or None

    pdf_files = {
        doc_type: _file_to_bytesio(request.files.get(doc_type))
        for doc_type in ("SE", "TE", "Printables", "Walkthrough")
    }

    job_id = str(uuid.uuid4())
    job = _make_job()
    with _jobs_lock:
        _jobs[job_id] = job

    thread = threading.Thread(
        target=run_workflow,
        args=(
            sheet_url,
            pdf_files,
            job["log_queue"],
            job["result_queue"],
            classroom_override,
            reviewer_notes,
        ),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404

    _drain_job(job_id)

    return jsonify({
        "running": job["running"],
        "messages": job["messages"],
        "result": job["result"],
        "run_dir": job["run_dir"],
    })


@app.route("/analyze-again", methods=["POST"])
def analyze_again():
    data = request.get_json()
    sheet_url = (data.get("sheet_url") or "").strip()
    run_dir = (data.get("run_dir") or "").strip()
    reviewer_notes = (data.get("reviewer_notes") or "").strip() or None

    if not sheet_url or not run_dir:
        return jsonify({"error": "sheet_url and run_dir are required"}), 400

    job_id = str(uuid.uuid4())
    job = _make_job()
    with _jobs_lock:
        _jobs[job_id] = job

    thread = threading.Thread(
        target=run_analyze_again,
        args=(
            sheet_url,
            run_dir,
            job["log_queue"],
            job["result_queue"],
            reviewer_notes,
        ),
        daemon=True,
    )
    thread.start()

    return jsonify({"job_id": job_id})


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8080)
