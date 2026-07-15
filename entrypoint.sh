#!/bin/bash
set -e

# Cloud Android Runner — Entrypoint
# Boot sequence: Xvfb → VNC → noVNC → Emulator → Health API

echo "[cloud-android] Starting boot sequence..."

# Start X Virtual Framebuffer
Xvfb ${DISPLAY} -screen 0 1440x900x24 +extension GLX +render &
sleep 1

# Start window manager
fluxbox &
sleep 1

# Start VNC server
x11vnc -display ${DISPLAY} -forever -shared -rfbport 5900 -nopw -quiet &
sleep 1

# Start noVNC web proxy
/opt/novnc/utils/novnc_proxy --vnc localhost:5900 --listen 6080 &
sleep 1

# Create Android virtual device if not exists
AVD_NAME="${AVD_NAME:-CloudAndroid}"
ANDROID_API="${ANDROID_API:-34}"
DEVICE_PROFILE="${DEVICE_PROFILE:-pixel_6_pro}"
EMULATOR_RAM="${EMULATOR_RAM:-4096}"
EMULATOR_STORAGE="${EMULATOR_STORAGE:-2048}"

if ! ${ANDROID_HOME}/emulator/emulator -list-avds 2>/dev/null | grep -q "${AVD_NAME}"; then
    echo "[cloud-android] Creating AVD: ${AVD_NAME} (API ${ANDROID_API}, ${DEVICE_PROFILE})"
    echo no | ${ANDROID_HOME}/cmdline-tools/latest/bin/avdmanager create avd \
        --name "${AVD_NAME}" \
        --package "system-images;android-${ANDROID_API};google_apis;x86_64" \
        --device "${DEVICE_PROFILE}" \
        --force
fi

# Configure AVD hardware properties
AVD_CONFIG="${HOME}/.android/avd/${AVD_NAME}.avd/config.ini"
if [ -f "${AVD_CONFIG}" ]; then
    echo "[cloud-android] Tuning AVD config..."
    # Improve performance
    echo "hw.ramSize=${EMULATOR_RAM}" >> "${AVD_CONFIG}"
    echo "disk.dataPartition.size=${EMULATOR_STORAGE}M" >> "${AVD_CONFIG}"
    echo "hw.gpu.enabled=yes" >> "${AVD_CONFIG}"
    echo "hw.gpu.mode=host" >> "${AVD_CONFIG}"
    echo "hw.gps=yes" >> "${AVD_CONFIG}"
    echo "hw.sensors.proximity=yes" >> "${AVD_CONFIG}"
    echo "hw.camera.back=virtualscene" >> "${AVD_CONFIG}"
    echo "hw.camera.front=emulated" >> "${AVD_CONFIG}"
    echo "fastboot.forceColdBoot=no" >> "${AVD_CONFIG}"
fi

# Start emulator
echo "[cloud-android] Launching emulator..."
${ANDROID_HOME}/emulator/emulator \
    -avd "${AVD_NAME}" \
    -no-boot-anim \
    -gpu host \
    -no-snapshot \
    -wipe-data \
    -port 5554 \
    -memory ${EMULATOR_RAM} \
    -cores $(nproc --all 2>/dev/null || echo 2) &
sleep 5

# Wait for boot completion
echo "[cloud-android] Waiting for device boot..."
${ANDROID_HOME}/platform-tools/adb wait-for-device 2>/dev/null
BOOT_TIMEOUT=120
ELAPSED=0
while [ ${ELAPSED} -lt ${BOOT_TIMEOUT} ]; do
    BOOT_COMPLETE=$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')
    if [ "${BOOT_COMPLETE}" = "1" ]; then
        echo "[cloud-android] Device boot completed in ${ELAPSED}s"
        break
    fi
    sleep 3
    ELAPSED=$((ELAPSED + 3))
done

if [ "${BOOT_COMPLETE}" != "1" ]; then
    echo "[cloud-android] WARNING: Device did not fully boot within ${BOOT_TIMEOUT}s"
fi

# Setup device — disable lock screen, animations
adb shell settings put global window_animation_scale 0.0
adb shell settings put global transition_animation_scale 0.0
adb shell settings put global animator_duration_scale 0.0
adb shell settings put system screen_off_timeout 1800000
adb shell settings put global stay_on_while_plugged_in 3

# Record device status
echo "booted" > /data/device_status
echo "${AVD_NAME}" > /data/device_name
echo "API ${ANDROID_API}" > /data/android_version
adb shell getprop ro.product.model > /data/device_model
echo "http://localhost:6080" > /data/vnc_url

# Start API server
echo "[cloud-android] Starting management API..."
cd /app/api
python3 server.py &
echo "[cloud-android] API server started on port 8080"

echo "[cloud-android] Boot sequence complete."
echo "  VNC:    http://localhost:5900"
echo "  Web:    http://localhost:6080/vnc.html"
echo "  API:    http://localhost:8080"
echo "  ADB:    localhost:5555"

# Keep running
wait -n
