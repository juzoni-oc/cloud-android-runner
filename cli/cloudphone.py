#!/usr/bin/env python3
"""
Cloud Android Runner CLI — Manage Android emulators via REST API.

Usage:
    python3 cli/cloudphone.py devices [--host http://localhost:8080]
    python3 cli/cloudphone.py screenshot [--host http://localhost:8080] [-o screen.png]
    python3 cli/cloudphone.py install --path app.apk [--host http://localhost:8080]
    python3 cli/cloudphone.py install --url https://example.com/app.apk [--host http://localhost:8080]
    python3 cli/cloudphone.py shell --cmd "dumpsys battery" [--host http://localhost:8080]
    python3 cli/cloudphone.py tap --x 500 --y 1000 [--host http://localhost:8080]
    python3 cli/cloudphone.py exec-command --command "..." [--host http://localhost:8080]
"""

import argparse
import json
import os
import subprocess
import sys
import requests


API_HOST = os.environ.get("CLOUD_ANDROID_HOST", "http://localhost:8080")


def api(method, path, data=None, raw=False):
    """Call the device management API."""
    url = f"{API_HOST.rstrip('/')}/{path.lstrip('/')}"
    try:
        if method == "GET":
            r = requests.get(url, timeout=30)
        elif method == "POST":
            headers = {"Content-Type": "application/json"} if data else {}
            r = requests.post(url, json=data, headers=headers if data else None, timeout=60)
        else:
            print(f"Unsupported method: {method}")
            sys.exit(1)

        if raw:
            return r

        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to API at {url}")
        print(f"Ensure the device container is running and API port is exposed.")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("Error: API request timed out")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"Error: API returned {e.response.status_code}")
        sys.exit(1)


def cmd_devices(args):
    """List devices and their status."""
    try:
        health = api("GET", "health")
        info = api("GET", "device")

        print(f"Device:   {info.get('model', 'unknown')}")
        print(f"Android:  {info.get('android_version', 'unknown')} (API {info.get('api_level', '?')})")
        print(f"Status:   {health.get('status', 'unknown')}")
        print(f"ADB:      {info.get('serial', 'unknown')}")
        print(f"VNC:      {info.get('vnc_url', 'unknown')}")
        print(f"Uptime:   {health.get('uptime', 'unknown')}s")
        print(f"DevInfo:  {json.dumps(info, indent=2)}")
    except SystemExit:
        print("No devices available.")


def cmd_screenshot(args):
    """Capture a device screenshot."""
    r = api("GET", "screenshot", raw=True)
    output = args.output or f"cloud_android_screen_{os.urandom(4).hex()}.png"

    content_type = r.headers.get("content-type", "")
    if "json" in content_type:
        data = r.json()
        print(f"Error: {data.get('error', 'Screenshot failed')}")
        sys.exit(1)

    with open(output, "wb") as f:
        f.write(r.content)
    print(f"Screenshot saved to: {output} ({len(r.content)} bytes)")


def cmd_install(args):
    """Install an APK."""
    data = {}
    if args.path:
        data["apk_path"] = args.path
    if args.url:
        data["apk_url"] = args.url

    if not data:
        print("Error: Specify --path or --url for APK installation")
        sys.exit(1)

    result = api("POST", "install", data)
    if result.get("success"):
        print("APK installed successfully!")
    else:
        print(f"Installation failed: {result.get('stderr', 'unknown error')}")
        sys.exit(1)


def cmd_shell(args):
    """Execute a shell command on the device."""
    result = api("POST", "shell", {"command": args.command})
    if result.get("stdout"):
        print(result["stdout"])
    if result.get("stderr"):
        print(result["stderr"], file=sys.stderr)
    sys.exit(result.get("exit_code", 0))


def cmd_tap(args):
    """Send a tap event."""
    result = api("POST", "input", {"action": "tap", "x": args.x, "y": args.y})
    if result.get("success"):
        print(f"Tap at ({args.x}, {args.y}) sent successfully")
    else:
        print("Tap failed", file=sys.stderr)
        sys.exit(1)


def cmd_packages(args):
    """List installed packages."""
    result = api("GET", "packages")
    print(f"Packages ({result.get('count', 0)}):")
    for pkg in result.get("packages", []):
        print(f"  {pkg}")


def cmd_input_text(args):
    """Send text input."""
    result = api("POST", "input", {"action": "text", "text": args.text})
    print("Text sent" if result.get("success") else "Text failed")


def cmd_keyevent(args):
    """Send key event."""
    key_map = {"home": 3, "back": 4, "menu": 82, "power": 26, "enter": 66}
    key = key_map.get(args.key.lower(), args.key)
    result = api("POST", "input", {"action": "keyevent", "key": int(key)})
    print(f"Key {args.key} sent" if result.get("success") else "Key failed")


def cmd_exec_command(args):
    """Execute command and return result."""
    print(json.dumps(api("POST", "shell", {"command": args.command}), indent=2))


def main():
    parser = argparse.ArgumentParser(
        description="Cloud Android Runner CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument("--host", default=API_HOST, help="API base URL (default: {})".format(API_HOST))
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # devices
    p_devices = sub.add_parser("devices", help="List devices and status")
    p_devices.set_defaults(func=cmd_devices)

    # screenshot
    p_ss = sub.add_parser("screenshot", help="Capture screenshot")
    p_ss.add_argument("-o", "--output", help="Output file path")
    p_ss.set_defaults(func=cmd_screenshot)

    # install
    p_inst = sub.add_parser("install", help="Install APK")
    p_inst_group = p_inst.add_mutually_exclusive_group(required=True)
    p_inst_group.add_argument("--path", help="Local APK file path")
    p_inst_group.add_argument("--url", help="APK download URL")
    p_inst.set_defaults(func=cmd_install)

    # shell
    p_shell = sub.add_parser("shell", help="Execute shell command")
    p_shell.add_argument("command", nargs="?", default=None, help="Command to execute")
    p_shell.add_argument("--cmd", dest="command_opt", help="Alternative: command to execute")
    p_shell.set_defaults(func=lambda a: cmd_shell(a))

    # tap
    p_tap = sub.add_parser("tap", help="Touch screen at coordinates")
    p_tap.add_argument("--x", type=int, required=True, help="X coordinate")
    p_tap.add_argument("--y", type=int, required=True, help="Y coordinate")
    p_tap.set_defaults(func=cmd_tap)

    # packages
    p_pkg = sub.add_parser("packages", help="List installed packages")
    p_pkg.set_defaults(func=cmd_packages)

    # text
    p_text = sub.add_parser("text", help="Input text")
    p_text.add_argument("text", help="Text to input")
    p_text.set_defaults(func=cmd_input_text)

    # key
    p_key = sub.add_parser("key", help="Send key event (home/back/power/enter)")
    p_key.add_argument("key", help="Key name or code")
    p_key.set_defaults(func=cmd_keyevent)

    # exec
    p_exec = sub.add_parser("exec-command", help="Execute command and return JSON")
    p_exec.add_argument("command", help="Command to execute")
    p_exec.set_defaults(func=cmd_exec_command)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    global API_HOST
    API_HOST = args.host

    # Handle shell command positionally
    if args.command == "shell" and args.command_opt:
        args.command = args.command_opt

    args.func(args)


if __name__ == "__main__":
    main()
