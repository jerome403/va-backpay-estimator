"""
VA Backpay Estimator - Flask Web Application

Runs locally and serves the backpay/combined-rating/SMC calculator, integrating
with the same `ClientFolders` layout used by va-form-filler so calculations can
be saved directly into a client's folder.

Security posture (see README "Security Checklist"):
  - Bound to 127.0.0.1 only (never 0.0.0.0)
  - Host header enforced  -> blocks DNS rebinding
  - Origin header enforced on POSTs -> blocks cross-site POST/CSRF
  - Client folder names are path-traversal-sanitized and realpath-verified
  - /api/open-folder only opens the verified Calculations subfolder
  - Waitress WSGI server when available (stricter HTTP parsing than the dev server)
"""

import os
import sys
import time
import subprocess
from datetime import datetime
from flask import Flask, render_template, request, jsonify, abort

app = Flask(__name__)

# ─── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Shared client folders root (sibling to this project, same convention as
# va-form-filler). Override with CLIENT_FOLDERS_BASE env var.
CLIENT_FOLDERS_BASE = os.environ.get(
    "CLIENT_FOLDERS_BASE",
    os.path.join(os.path.dirname(BASE_DIR), "ClientFolders"),
)

# Resolved once at startup for path-containment checks.
CLIENT_FOLDERS_BASE_REAL = os.path.realpath(CLIENT_FOLDERS_BASE)

# Subfolder within each client folder where reports get saved.
CALC_SUBFOLDER = "Calculations"

# ─── Network allow-list (both refer to the same local socket) ───────────────
HOST_PORT = "127.0.0.1:5001"
ALT_HOST_PORT = "localhost:5001"
ALLOWED_HOSTS = {HOST_PORT, ALT_HOST_PORT}
ALLOWED_ORIGINS = {"http://" + HOST_PORT, "http://" + ALT_HOST_PORT}


# ─── Security guards (before_request) ───────────────────────────────────────
@app.before_request
def enforce_host_and_origin():
    """Reject DNS-rebinding and cross-site POSTs before any handler runs.

    - Host header MUST be one of our allowed loopback names. A rebinding
      attack makes `evil.com` resolve to 127.0.0.1 mid-session; the
      browser then sends `Host: evil.com`, which we refuse.
    - On state-changing methods (POST/PUT/DELETE/PATCH), the Origin header
      MUST match our own origin. Cross-site forms and malicious pages
      would have a different Origin and get a 403.
    """
    host = (request.host or "").lower()
    if host not in ALLOWED_HOSTS:
        abort(403, description="Invalid Host header.")

    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("Origin", "")
        if origin and origin not in ALLOWED_ORIGINS:
            abort(403, description="Invalid Origin header.")
        # If no Origin, require a same-site Referer as a fallback. Modern
        # browsers always send Origin on cross-origin POSTs; absence means
        # either a same-origin fetch (fine, check Referer) or a tool like
        # curl (which you control yourself).
        if not origin:
            referer = request.headers.get("Referer", "")
            if referer and not any(referer.startswith(o + "/") or referer == o
                                   for o in ALLOWED_ORIGINS):
                abort(403, description="Invalid Referer header.")


@app.after_request
def tight_cors_and_security_headers(resp):
    """Add conservative security headers on every response."""
    origin = request.headers.get("Origin", "")
    if origin in ALLOWED_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Vary"] = "Origin"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "same-origin"
    resp.headers["X-Frame-Options"] = "DENY"
    return resp


# ─── Path-traversal-safe client folder resolver ─────────────────────────────
# Characters / sequences never allowed in a client folder name from an API.
_BAD_NAME_CHARS = ("/", "\\", "\x00", "\r", "\n", "\t")


def resolve_client_path(name):
    """Return the absolute realpath of a client folder, or None if invalid.

    Rejects names with path separators, null bytes, or `..` components, then
    verifies that the resolved path is a *direct child* of CLIENT_FOLDERS_BASE
    (so even symlink traversal is blocked).
    """
    if not name or not isinstance(name, str):
        return None
    if any(c in name for c in _BAD_NAME_CHARS):
        return None
    if name.strip() in ("", ".", ".."):
        return None
    # Resolve with realpath so we follow symlinks before the containment check.
    candidate = os.path.realpath(os.path.join(CLIENT_FOLDERS_BASE_REAL, name))
    # Must be a direct child of the base (no nested path below).
    if os.path.dirname(candidate) != CLIENT_FOLDERS_BASE_REAL:
        return None
    if not os.path.isdir(candidate):
        return None
    return candidate


# ─── Client_Data.txt helpers (compatible with va-form-filler format) ────────
def parse_client_data(filepath):
    """Read Client_Data.txt and return a dict."""
    data = {}
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    key, val = line.split("=", 1)
                    data[key.strip()] = val.strip()
    return data


def client_header_fields(client_path, folder_name):
    """Return a minimal set of fields useful for a report header."""
    data = parse_client_data(os.path.join(client_path, "Client_Data.txt"))
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
    """Write bytes to filepath, retrying briefly on PermissionError
    (OneDrive sync / file-open conflicts)."""
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


def _open_in_file_manager(path):
    """Cross-platform: open a *directory* in the OS file manager.

    The caller MUST pre-validate `path` with resolve_client_path + containment
    check. This function assumes the argument is already a trusted directory
    path and does not take user input directly.
    """
    if not os.path.isdir(path):
        raise FileNotFoundError(path)
    if sys.platform == "win32":
        os.startfile(path)  # noqa: opened by the OS on a verified dir
    elif sys.platform == "darwin":
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)


# ─── Routes ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/client-folders", methods=["GET"])
def list_client_folders():
    """Return the list of subfolders under CLIENT_FOLDERS_BASE."""
    folders = []
    if os.path.isdir(CLIENT_FOLDERS_BASE_REAL):
        folders = sorted(
            d for d in os.listdir(CLIENT_FOLDERS_BASE_REAL)
            if os.path.isdir(os.path.join(CLIENT_FOLDERS_BASE_REAL, d))
            and not d.startswith(".")
        )
    return jsonify({
        "base": CLIENT_FOLDERS_BASE_REAL,
        "exists": os.path.isdir(CLIENT_FOLDERS_BASE_REAL),
        "folders": folders,
    })


# Use the default `string` converter (no slashes allowed) rather than
# `<path:...>` which permits traversal patterns like "..%2f..".
@app.route("/api/client-data/<folder_name>", methods=["GET"])
def get_client_data(folder_name):
    """Return minimal header info for a single client."""
    client_path = resolve_client_path(folder_name)
    if not client_path:
        return jsonify({"error": "Invalid or unknown client."}), 404
    return jsonify(client_header_fields(client_path, folder_name))


@app.route("/api/save-report", methods=["POST"])
def save_report():
    """Accept a rendered HTML report + metadata and write it into the client
    folder's Calculations subfolder."""
    payload = request.get_json(force=True, silent=True) or {}
    client_folder = (payload.get("client_folder") or "").strip()
    report_type = (payload.get("report_type") or "Report").strip()
    html = payload.get("html") or ""

    if not client_folder:
        return jsonify({"error": "No client selected."}), 400
    if not html:
        return jsonify({"error": "No report content."}), 400
    # Sanity cap to prevent an absurdly large paste from filling the disk.
    if len(html) > 10 * 1024 * 1024:  # 10 MB
        return jsonify({"error": "Report too large."}), 413

    client_path = resolve_client_path(client_folder)
    if not client_path:
        return jsonify({"error": "Invalid or unknown client."}), 404

    save_dir = os.path.join(client_path, CALC_SUBFOLDER)
    os.makedirs(save_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = f"{safe_filename(report_type)}_{timestamp}.html"
    filepath = os.path.join(save_dir, filename)

    # Final containment check: make sure filepath is still inside client_path.
    if not os.path.realpath(filepath).startswith(client_path + os.sep):
        return jsonify({"error": "Path validation failed."}), 400

    try:
        write_file_with_retry(filepath, html.encode("utf-8"))
    except PermissionError as e:
        return jsonify({
            "error": (
                f"Could not save report - file appears locked "
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
    """Open a client's Calculations folder in the OS file manager.

    The target is forced to {validated_client_path}/Calculations (or the
    client path itself if the subfolder doesn't exist yet). User input only
    picks which client; the actual path that gets opened is computed from
    CLIENT_FOLDERS_BASE + the resolved folder name.
    """
    payload = request.get_json(force=True, silent=True) or {}
    client_folder = (payload.get("client_folder") or "").strip()

    client_path = resolve_client_path(client_folder)
    if not client_path:
        return jsonify({"error": "Invalid or unknown client."}), 404

    target = os.path.join(client_path, CALC_SUBFOLDER)
    if not os.path.isdir(target):
        target = client_path

    try:
        _open_in_file_manager(target)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"opened": target})


# ─── Main entrypoint ────────────────────────────────────────────────────────
def _print_banner():
    print("=" * 60)
    print(" VA Backpay Estimator - Spearman Appeals LLC")
    print("=" * 60)
    print(f"  Client folders: {CLIENT_FOLDERS_BASE_REAL}")
    print(f"  Exists: {os.path.isdir(CLIENT_FOLDERS_BASE_REAL)}")
    print(f"  URL: http://{HOST_PORT}")
    print("=" * 60)


if __name__ == "__main__":
    _print_banner()
    host, port = HOST_PORT.split(":")
    try:
        from waitress import serve
        print(" Server: waitress (production WSGI, local-only bind)")
        print("=" * 60)
        serve(app, host=host, port=int(port), threads=4, ident="VA-Backpay")
    except ImportError:
        print(" Server: Flask dev server (install waitress for hardened mode)")
        print("=" * 60)
        app.run(host=host, port=int(port), debug=False)
