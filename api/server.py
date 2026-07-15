#!/usr/bin/env python3
"""
Cloud Android Runner — Management REST API
Provides HTTP endpoints for device management, screenshot, ADB proxy,
APK install, and health checks.
"""

import json
import os
import subprocess
import tempfile
import time
from datetime import datetime
from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

DEVICE_LOCK = None
LOG_DIR = "/data/logs"
SCREENSHOT_DIR = "/data/screenshots"
DEVICE_STATUS_FILE = "/data/device_status"

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def log(msg):
    """Log to both stdout and file."""
    ts = datetime.utcnow().isoformat()
    msg = f"[{ts}] {msg}"
    print(msg)
    with open(f"{LOG_DIR}/api.log", "a") as f:
        f.write(msg + "\n")


def _adb(args, timeout=30):
    """Run ADB command and return (stdout, stderr, returncode)."""
    cmd = ["adb"] + args
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "ADB timeout after {timeout}s", -1
    except FileNotFoundError:
        return "", "ADB not found", -1


def _check_device():
    """Check if emulator device is online."""
    out, _, rc = _adb(["get-state"])
    if rc != 0 or out.strip() != "device":
        return None
    return True


# ── Health ──────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    """Basic health check."""
    device_online = _check_device() is not None
    status = "ok" if device_online else "degraded"
    if os.path.exists(DEVICE_STATUS_FILE):
        device_status = open(DEVICE_STATUS_FILE).read().strip()
    else:
        device_status = "unknown"
    return jsonify({
        "status": status,
        "device_status": device_status,
        "uptime": open("/proc/uptime").read().split()[0] if os.path.exists("/proc/uptime") else "unknown",
        "timestamp": datetime.utcnow().isoformat()
    })


# ── Device Info ─────────────────────────────────────────────────────────

@app.route("/device", methods=["GET"])
def device_info():
    """Detailed device info."""
    if _check_device() is None:
        return jsonify({"error": "Device not available"}), 503

    props = {
        "ro.product.model": "model",
        "ro.product.manufacturer": "manufacturer",
        "ro.build.version.release": "android_version",
        "ro.build.version.sdk": "api_level",
        "ro.serialno": "serial",
        "persist.sys.timezone": "timezone",
    }
    result = {}
    for prop, key in props.items():
        out, _, _ = _adb(["shell", "getprop", prop])
        result[key] = out.strip() or "unknown"

    result["avd_name"] = os.path.exists("/data/device_name") and open("/data/device_name").read().strip() or "unknown"
    result["vnc_url"] = os.path.exists("/data/vnc_url") and open("/data/vnc_url").read().strip() or "unknown"
    return jsonify(result)


# ── Screenshot ─────────────────────────────────────────────────────────

@app.route("/screenshot", methods=["GET"])
def screenshot():
    """Capture and return device screenshot."""
    if _check_device() is None:
        return jsonify({"error": "Device not available"}), 503

    remote = "/sdcard/screenshot.png"
    local = f"{SCREENSHOT_DIR}/screen_{int(time.time())}.png"
    _adb(["shell", "screencap", "-p", remote])
    _adb(["pull", remote, local])
    _adb(["shell", "rm", remote])

    if os.path.exists(local) and os.path.getsize(local) > 0:
        return send_file(local, mimetype="image/png")

    # Fallback: framebuffer capture
    out, err, _ = _adb(["exec-out", "screencap", "-p"])
    if out:
        fb_path = f"{SCREENSHOT_DIR}/screen_fb_{int(time.time())}.png"
        with open(fb_path, "wb") as f:
            f.write(out.encode() if isinstance(out, str) else out)
        return send_file(fb_path, mimetype="image/png")
    return jsonify({"error": "Screenshot failed", "details": err}), 500


# ── Shell ───────────────────────────────────────────────────────────────

@app.route("/shell", methods=["POST"])
def shell():
    """Execute shell command on device."""
    data = request.get_json(silent=True) or {}
    cmd = data.get("command", "")
    if not cmd:
        return jsonify({"error": "command required"}), 400

    out, err, rc = _adb(["shell", cmd])
    return jsonify({"exit_code": rc, "stdout": out, "stderr": err})


# ── APK Install ─────────────────────────────────────────────────────────

@app.route("/install", methods=["POST"])
def install_apk():
    """Install APK from provided URL or path."""
    data = request.get_json(silent=True) or {}
    apk_path = data.get("apk_path", "")
    apk_url = data.get("apk_url", "")

    if not apk_path and not apk_url:
        return jsonify({"error": "apk_path or apk_url required"}), 400

    if apk_url:
        # Download APK
        tmp = tempfile.mktemp(suffix=".apk")
        dl = subprocess.run(["wget", "-q", "-O", tmp, apk_url], capture_output=True, text=True, timeout=60)
        if dl.returncode != 0:
            os.unlink(tmp)
            return jsonify({"error": f"Download failed: {dl.stderr[:200]}"}), 500
        apk_path = tmp

    if not os.path.exists(apk_path):
        return jsonify({"error": "APK file not found"}), 404

    out, err, rc = _adb(["install", "-r", apk_path], timeout=120)
    if apk_url and os.path.exists(apk_path):
        os.unlink(apk_path)

    success = rc == 0 and ("Success" in out or "success" in out)
    return jsonify({
        "success": success,
        "stdout": out,
        "stderr": err,
        "exit_code": rc
    })


# ── Installed Packages ──────────────────────────────────────────────────

@app.route("/packages", methods=["GET"])
def list_packages():
    """List installed third-party packages."""
    out, err, rc = _adb(["shell", "pm", "list", "packages", "-3"])
    if rc != 0:
        return jsonify({"error": err}), 500

    packages = [p.replace("package:", "") for p in out.split("\n") if p.startswith("package:")]
    return jsonify({"count": len(packages), "packages": packages})


# ── Input ───────────────────────────────────────────────────────────────

@app.route("/input", methods=["POST"])
def input_action():
    """Send input events (tap, swipe, text, keyevent)."""
    data = request.get_json(silent=True) or {}
    action = data.get("action", "")

    if action == "tap":
        x, y = data.get("x", 0), data.get("y", 0)
        _, _, rc = _adb(["shell", "input", "tap", str(x), str(y)])
    elif action == "swipe":
        x1, y1 = data.get("x1", 0), data.get("y1", 0)
        x2, y2 = data.get("x2", 0), data.get("y2", 0)
        d = data.get("duration", 300)
        _, _, rc = _adb(["shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(d)])
    elif action == "text":
        text = data.get("text", "")
        _, _, rc = _adb(["shell", "input", "text", text])
    elif action == "keyevent":
        key = data.get("key", 66)
        _, _, rc = _adb(["shell", "input", "keyevent", str(key)])
    else:
        return jsonify({"error": f"Unknown action: {action}"}), 400

    return jsonify({"action": action, "success": rc == 0})


# ── File Push/Pull ─────────────────────────────────────────────────────

@app.route("/file/push", methods=["POST"])
def file_push():
    """Push file to device."""
    data = request.get_json(silent=True) or {}
    local = data.get("local_path", "")
    remote = data.get("remote_path", "/sdcard/")
    if not local or not os.path.exists(local):
        return jsonify({"error": "local_path required and must exist"}), 400
    out, err, rc = _adb(["push", local, remote])
    return jsonify({"success": rc == 0, "stdout": out, "stderr": err})


@app.route("/file/pull", methods=["POST"])
def file_pull():
    """Pull file from device."""
    data = request.get_json(silent=True) or {}
    remote = data.get("remote_path", "")
    local = data.get("local_path", "/data/screenshots/pulled")
    if not remote:
        return jsonify({"error": "remote_path required"}), 400
    out, err, rc = _adb(["pull", remote, local])
    return jsonify({"success": rc == 0, "stdout": out, "stderr": err})


# ── Start ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log("Starting Cloud Android Runner API server...")
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)
