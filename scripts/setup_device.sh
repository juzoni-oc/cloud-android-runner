#!/bin/bash
# Cloud Android Runner — Device Runtime Setup
# Configures an already-running emulator for cloud phone workloads.
# Run inside the container or via: docker exec <container> bash /app/scripts/setup_device.sh

set -e

echo "═══ Cloud Android Device Setup ═══"
echo ""

# 1. Wait for device
echo "[1/6] Waiting for ADB device..."
adb wait-for-device 2>/dev/null
sleep 5

# 2. Disable animations (speed)
echo "[2/6] Disabling animations..."
adb shell settings put global window_animation_scale 0.0
adb shell settings put global transition_animation_scale 0.0
adb shell settings put global animator_duration_scale 0.0

# 3. Keep screen on
echo "[3/6] Configuring display..."
adb shell settings put system screen_off_timeout 1800000
adb shell settings put global stay_on_while_plugged_in 3
adb shell svc power stayon true

# 4. Disable lock screen
echo "[4/6] Disabling lock screen..."
adb shell locksettings clear --old "" 2>/dev/null || true
adb shell settings put secure lock_screen_lockout 0
adb shell settings put secure lockscreen.disabled 1

# 5. Set timezone and locale
echo "[5/6] Setting timezone and locale..."
adb shell settings put global time_auto 0
adb shell setprop persist.sys.timezone "UTC"
adb shell setprop persist.sys.locale "en-US"

# 6. Network optimization
echo "[6/6] Network configuration..."
adb shell settings put global wifi_on 1
adb shell settings put global airplane_mode_on 0
adb shell content insert --uri content://settings/global --bind name:s:wifi_scan_always_enabled --bind value:i:1

echo ""
echo "═══ Device setup complete ═══"
echo "Model:     $(adb shell getprop ro.product.model)"
echo "Android:   $(adb shell getprop ro.build.version.release)"
echo "API:       $(adb shell getprop ro.build.version.sdk)"
echo "Serial:    $(adb shell getprop ro.serialno)"
echo "ADB:       $(adb devices)"
echo ""
