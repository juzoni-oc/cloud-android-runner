# Cloud Android Runner

> Production-grade Android emulator management platform for cloud device infrastructure. Run Android devices in Docker containers with VNC remote access, REST API control, and multi-device orchestration.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![Android API 34](https://img.shields.io/badge/Android-34-green?logo=android)](https://developer.android.com/)
[![Python 3](https://img.shields.io/badge/Python-3-3776AB?logo=python)](https://python.org)

---

## Features

- **Docker-Packaged Emulator** — Full Android emulator (AOSP/Google APIs) running inside a container, KVM-accelerated
- **Remote Desktop** — Built-in noVNC web client (HTML5), also supports native VNC clients
- **REST Management API** — Full HTTP API for device control: screenshot, input, install APK, shell, file transfer
- **Multi-Device Orchestration** — Compose files for running multiple device nodes with NGINX load balancing
- **Device Profiles** — Pre-configured device skins and specs (Pixel 6 Pro, Samsung S23, OnePlus 11, Pixel 7)
- **Health Monitoring** — Built-in health check endpoints, ADB watchdog, disk usage alerts
- **CI/CD Ready** — Start a device, run tests, tear down — all within a single Docker pipeline

## Quick Start

### Prerequisites

- Linux host with KVM support (`kvm-ok` should return "KVM acceleration can be used")
- Docker Engine 24+ and Docker Compose V2
- 4 GB+ RAM per device, 4 GB+ disk per device

### Single Device

```bash
# Clone and launch
git clone https://github.com/juzoni-oc/cloud-android-runner.git
cd cloud-android-runner
docker compose up device-01 -d

# Check status
docker compose ps
curl http://localhost:8081/health

# Open web VNC
# → http://localhost:6080/vnc.html
```

First boot takes 2-3 minutes (AVD creation + system boot). Subsequent starts are faster.

### Multi-Device Cluster

```bash
# Start two device nodes + proxy
docker compose up -d

# Access via proxy
# API:  http://localhost/api/
# VNC:  http://localhost/vnc/
```

### Custom Device Profile

```bash
docker compose run -e DEVICE_PROFILE=samsung_s23 device-01
```

## REST API Reference

The management API runs on port 8080 per device. With the proxy, routes are available under `/api/`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Device health and status |
| `GET` | `/device` | Device properties (model, Android version, API level) |
| `GET` | `/screenshot` | Capture device screenshot (returns PNG) |
| `POST` | `/shell` | Execute shell command on device |
| `POST` | `/install` | Install APK from URL or local path |
| `GET` | `/packages` | List installed third-party packages |
| `POST` | `/input` | Send touch/keyboard/gesture input |
| `POST` | `/file/push` | Push file to device |
| `POST` | `/file/pull` | Pull file from device |

### Usage Examples

```bash
# Health check
curl http://localhost:8081/health

# Screenshot
curl http://localhost:8081/screenshot -o screen.png

# Install APK from URL
curl -X POST http://localhost:8081/install \
  -H "Content-Type: application/json" \
  -d '{"apk_url": "https://example.com/app.apk"}'

# Execute shell command
curl -X POST http://localhost:8081/shell \
  -H "Content-Type: application/json" \
  -d '{"command": "dumpsys battery"}'

# Tap on screen (x=500, y=1000)
curl -X POST http://localhost:8081/input \
  -H "Content-Type: application/json" \
  -d '{"action": "tap", "x": 500, "y": 1000}'
```

## CLI Tool

```bash
# Install
pip install -r requirements.txt

# List devices
python3 cli/cloudphone.py devices

# Take screenshot
python3 cli/cloudphone.py screenshot --device http://localhost:8081

# Install APK
python3 cli/cloudphone.py install --path app.apk --device http://localhost:8081
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Cloud Proxy                      │
│             nginx (port 80)                       │
│  /api/ → device API  /vnc/ → device VNC          │
├─────────────────────────────────────────────────┤
│                                                   │
│  ┌────────────────┐  ┌────────────────┐          │
│  │  Device 01     │  │  Device 02     │  ...     │
│  │  - AVD Pixel 6 │  │  - AVD Pixel 7 │          │
│  │  - noVNC:6080  │  │  - noVNC:6080  │          │
│  │  - API:8080    │  │  - API:8080    │          │
│  │  - ADB:5555    │  │  - ADB:5555    │          │
│  └────────────────┘  └────────────────┘          │
│  ┌─────────────────────────────────────────┐     │
│  │  Shared → /dev/kvm (hardware acceleration)│    │
│  └─────────────────────────────────────────┘     │
└─────────────────────────────────────────────────┘
```

## Device Profile Specs

| Profile | Model | Android | RAM | Screen |
|---------|-------|---------|-----|--------|
| pixel_6_pro | Google Pixel 6 Pro | 14 (API 34) | 4 GB | 1440x3120 |
| pixel_7 | Google Pixel 7 | 13 (API 33) | 3 GB | 1080x2400 |
| samsung_s23 | Samsung Galaxy S23 | 13 (API 33) | 4 GB | 1080x2340 |
| oneplus_11 | OnePlus 11 | 13 (API 33) | 4 GB | 1440x3216 |
| generic_tablet | Pixel C | 14 (API 34) | 4 GB | 2560x1800 |

## Persisting Data

Mount a volume at `/data` to preserve AVD state, installed apps, and screenshots:

```bash
docker run -v cloud-data:/data cloud-android-runner:latest
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AVD_NAME` | `CloudAndroid` | AVD instance name |
| `ANDROID_API` | `34` | Android API level |
| `DEVICE_PROFILE` | `pixel_6_pro` | Device skin/profile |
| `EMULATOR_RAM` | `4096` | RAM allocation (MB) |
| `EMULATOR_STORAGE` | `2048` | Storage size (MB) |

## Use Cases

- **Mobile CI/CD** — Spin up Android emulators in Docker for automated test pipelines
- **Cloud Phone Infrastructure** — Deploy fleet of Android devices accessible via API
- **App Testing** — Test across multiple device profiles without physical hardware
- **Mobile Automation** — Script APK install, interaction, and screenshot capture
- **Web3 / DeFi** — Run dApp testing on emulated mobile environments

## License

MIT License — see [LICENSE](LICENSE).

## Contact

- Website: https://www.qtphone.com/
- WhatsApp: @along915
- Telegram: @Alongyun
- Email: ailong9281@gmail.com
