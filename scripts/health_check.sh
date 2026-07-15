#!/bin/bash
# Cloud Android Runner — Health Check
# Returns JSON status of the device.

DEVICE_STATUS="/data/device_status"
if [ -f "$DEVICE_STATUS" ]; then
    DS=$(cat "$DEVICE_STATUS")
else
    DS="unknown"
fi

# Check ADB
ADB_STATUS="offline"
if adb get-state 2>/dev/null | grep -q "device"; then
    ADB_STATUS="online"
fi

# Check emulator process
EMULATOR_RUNNING="false"
if pgrep -f "qemu-system" > /dev/null 2>&1; then
    EMULATOR_RUNNING="true"
fi

DISK_USAGE=$(df -h /data 2>/dev/null | tail -1 | awk '{print $5}' || echo "unknown")
UPTIME=$(cat /proc/uptime 2>/dev/null | awk '{print $1}' || echo "unknown")

cat <<EOF
{
  "device_status": "$DS",
  "adb": "$ADB_STATUS",
  "emulator_running": $EMULATOR_RUNNING,
  "disk_usage_pct": "$DISK_USAGE",
  "uptime_sec": $UPTIME,
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
