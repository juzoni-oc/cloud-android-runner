FROM ubuntu:22.04

LABEL maintainer="juzoni-oc" \
      description="Cloud Android Runner — Android emulator cloud platform with remote access"

ENV DEBIAN_FRONTEND=noninteractive \
    ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    DISPLAY=:99 \
    USER=android

# Install system dependencies
RUN apt-get update -qq && \
    apt-get install -y -qq \
        openjdk-17-jdk-headless \
        wget curl unzip git \
        xvfb x11vnc fluxbox \
        python3 python3-pip python3-venv \
        supervisor \
        libpulse0 libnss3 libnspr4 \
        libxcomposite1 libxcursor1 libxi6 \
        libxrandr1 libxss1 libxtst6 \
        libatk-bridge2.0-0 libgtk-3-0 \
        libgbm1 libdrm2 \
        qemu-kvm libvirt-daemon-system \
        net-tools procps \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Android SDK
RUN mkdir -p ${ANDROID_HOME} && \
    wget -q https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip -O /tmp/cmdline-tools.zip && \
    unzip -q /tmp/cmdline-tools.zip -d ${ANDROID_HOME}/cmdline-tools && \
    mv ${ANDROID_HOME}/cmdline-tools/cmdline-tools ${ANDROID_HOME}/cmdline-tools/latest && \
    rm /tmp/cmdline-tools.zip && \
    yes | ${ANDROID_HOME}/cmdline-tools/latest/bin/sdkmanager --licenses > /dev/null 2>&1

# Install SDK components
RUN ${ANDROID_HOME}/cmdline-tools/latest/bin/sdkmanager \
    "platform-tools" \
    "emulator" \
    "platforms;android-34" \
    "system-images;android-34;google_apis;x86_64" \
    "build-tools;34.0.0" \
    --sdk_root=${ANDROID_HOME} && \
    rm -rf ${ANDROID_HOME}/.temp/* && \
    echo "sdk.dir=${ANDROID_HOME}" > /opt/android-sdk/local.properties

ENV PATH=${PATH}:${ANDROID_HOME}/emulator:${ANDROID_HOME}/platform-tools:${ANDROID_HOME}/cmdline-tools/latest/bin

# Install noVNC
RUN git clone --depth 1 https://github.com/novnc/noVNC /opt/novnc && \
    git clone --depth 1 https://github.com/novnc/websockify /opt/novnc/utils/websockify && \
    rm -rf /opt/novnc/.git /opt/novnc/utils/websockify/.git

# Install Python dependencies
RUN pip3 install flask pyyaml requests psutil

# Setup app
COPY scripts/ /app/scripts/
COPY api/ /app/api/
COPY config/ /app/config/
COPY supervisor.conf /etc/supervisor/conf.d/android.conf
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /app/scripts/*.sh /entrypoint.sh && \
    mkdir -p /data/avatars /data/logs /data/screenshots

EXPOSE 5554 5555 5900 6080 8080

VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD adb devices -l 2>/dev/null | grep -q "emulator" || exit 1

ENTRYPOINT ["/entrypoint.sh"]
