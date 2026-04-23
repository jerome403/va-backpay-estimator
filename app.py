"""
VA Backpay Estimator - Flask Web Application

Runs locally and serves the backpay/combined-rating/SMC calculator, integrating
with the same `ClientFolders` layout used by va-form-filler so calculations can
be saved directly into a client's folder.
"""

import os
import io
import json
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)

# ─── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Shared client folders root (sibling to this project, same convention as
# va-form-filler). Override with CLIENT_FOLDERS_BASE env var if needed.
CLIENT_FOLDERS_BASE = os.environ.get(
    "CLIENT_FOLDERS_BASE",
    os.path.join(os.path.dirname(BASE_DIR), "ClientFolders"),
)

# Subfolder within each client folder where reports get saved.
CALC_SUBFOLDER = "Calculations"


# ─── Client_Data.txt helpers (compatible with va-form-filler format) ────────
def parse_client_data(filepath):
    """Read Client_Data.txt and return a dict."""
    data = {}
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    key, val = line.split("=", 1)
                    data[key.strip()] = val.strip()
    return data


def client_header_fields(folder_name):
    """Return a minimal set of fields useful for a report header."""
    client_path = os.path.join(CLIENT_FOLDERS_BASE, folder_name)
    data = parse_client_data(os.path.join(client_path, "Client_Data.txt"))

    # Prefer split first/last over legacy single "Name"
    first = data.get("FirstName", "").strip()
    last = data.get("LastName", "").strip()
    full = " ".join(p for p in [first, last] if p) or data.get("Name", "").strip()

    dob_parts = [data.get("DOBMonth", ""), data.get("DOBDay", ""), data.get("DOBYear", "")]
    dob = "/".join(p for p in dob_parts if p)

    return {
        "folder": folder_name,
        "full_name": full or folder_name,
        "first_name": first,
        "last_name": last,
        "file_number": data.get("FileNumber", ""),
        "ssn": data.get("SSN", ""),
        "dob": dob,
        "has_client_data": any(data.values()),
    }


def write_file_with_retry(filepath, data_bytes, attempts=5, initial_delay=0.3):
    """Write bytes to filepath, retrying briefly on PermissionError (OneDrive
    sync / file-open conflicts). Mirrors the pattern used in va-form-filler."""
    delay = initial_delay
    last_err = None
    for _ in range(attempts):
        try:
            with open(filepath, "wb") as f:
                f.write(data_bytes)
            return filepath
        except PermissionError as e:
            last_err = e
            time.sleep(delay)
            delay = min(delay * 2, 3.0)
    # Last resort: temp-write + atomic replace
    tmp_path = filepath + ".tmp"
    try:
        with open(tmp_path, "wb") as f:
            f.write(data_bytes)
        os.replace(tmp_path, filepath)
        return filepath
    except PermissionError:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise last_err


def safe_filename(s):
    """Scrub a string for use in a filename."""
    s = (s or "").strip()
    bad = '<>:"/\\|?*\n\r\t'
    for ch in bad:
        s = s.replace(ch, "_")
    return s[:120] or "report"


# ─── Routes ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/client-folders", methods=["GET"])
def list_client_folders():
    """Return the list of subfolders under CLIENT_FOLDERS_BASE."""
    folders = []
    if os.path.isdir(CLIENT_FOLDERS_BASE):
        folders = sorted(
            d for d in os.listdir(CLIENT_FOLDERS_BASE)
            if os.path.isdir(os.path.join(CLIENT_FOLDERS_BASE, d))
            and not d.startswith(".")
        )
    return jsonify({
        "base": CLIENT_FOLDERS_BASE,
        "exists": os.path.isdir(CLIENT_FOLDERS_BASE),
        "folders": folders,
    })


@app.route("/api/client-data/<path:folder_name>", methods=["GET"])
def get_client_data(folder_name):
    """Return minimal header info for a single client."""
    client_path = os.path.join(CLIENT_FOLDERS_BASE, folder_name)
    if not os.path.isdir(client_path):
        return jsonify({"error": f"Client folder not found: {folder_name}"}), 404
    return jsonify(client_header_fields(folder_name))


@app.route("/api/save-report", methods=["POST"])
def save_report():
    """Accept a rendered HTML report + metadata and write it into the client
    folder's Calculations subfolder. Returns the saved path."""
    payload = request.get_json(force=True, silent=True) or {}
    client_folder = (payload.get("client_folder") or "").strip()
    report_type = (payload.get("report_type") or "Report").strip()
    html = payload.get("html") or ""

    if not client_folder:
        return jsonify({"error": "No client selected."}), 400
    if not html:
        return jsonify({"error": "No report content."}), 400

    client_path = os.path.join(CLIENT_FOLDERS_BASE, client_folder)
    if not os.path.isdir(client_path):
        return jsonify({"error": f"Client folder not found: {client_folder}"}), 404

    save_dir = os.path.join(client_path, CALC_SUBFOLDER)
    os.makedirs(save_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = f"{safe_filename(report_type)}_{timestamp}.html"
    filepath = os.path.join(save_dir, filename)

    try:
        write_file_with_retry(filepath, html.encode("utf-8"))
    except PermissionError as e:
        return jsonify({
            "error": (
                f"Could not save report — file appears locked "
                f"(OneDrive sync or open in a viewer). Try again in a moment. "
                f"({e})"
            )
        }), 423

    return jsonify({
        "message": f"Saved report to {client_folder}/{CALC_SUBFOLDER}/",
        "path": filepath,
        "filename": filename,
    })


@app.route("/api/open-folder", methods=["POST"])
def open_folder():
    """Open a client's Calculations folder in Windows Explorer."""
    payload = request.get_json(force=True, silent=True) or {}
    client_folder = (payload.get("client_folder") or "").strip()
    if not client_folder:
        return jsonify({"error": "No client selected."}), 400
    client_path = os.path.join(CLIENT_FOLDERS_BASE, client_folder)
    target = os.path.join(client_path, CALC_SUBFOLDER)
    if not os.path.isdir(target):
        target = client_path
    if not os.path.isdir(target):
        return jsonify({"error": "Folder not found."}), 404
    try:
        os.startfile(target)  # Windows-only
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"opened": target})


if __name__ == "__main__":
    print("=" * 60)
    print(" VA Backpay Estimator - Spearman Appeals LLC")
    print("=" * 60)
    print(f"  Client folders: {CLIENT_FOLDERS_BASE}")
    print(f"  Exists: {os.path.isdir(CLIENT_FOLDERS_BASE)}")
    print(f"  URL: http://127.0.0.1:5001")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5001, debug=False)
