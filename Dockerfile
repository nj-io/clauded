FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    openssh-client \
    jq \
    ripgrep \
    fd-find \
    build-essential \
    python3 \
    python3-pip \
    python3-venv \
    iptables \
    sudo \
    gh \
    procps \
    net-tools \
    less \
    unzip \
    tree \
    ca-certificates \
    lsof \
    # Voice mode: SoX records through a container-local PulseAudio whose mic
    # is bridged from the Mac (see mic-server.py / entrypoint.sh).
    sox \
    libsox-fmt-pulse \
    pulseaudio-utils \
    pulseaudio \
    # Chromium and dependencies for Puppeteer/Playwright MCP servers
    chromium \
    fonts-liberation \
    fonts-noto-color-emoji \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Tell Puppeteer and Playwright to use system Chromium instead of downloading
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
# @playwright/mcp defaults to the Chrome channel (looked up at /opt/google/chrome/chrome).
# Point that path at the bundled Chromium so the MCP works with no config changes.
RUN mkdir -p /opt/google/chrome && ln -sf /usr/bin/chromium /opt/google/chrome/chrome

# Match host UID/GID so mounted files have correct ownership
ARG USER_ID=501
ARG GROUP_ID=20
ARG HOME_DIR=/home/claude
# USER_ID 0 means the build ran under sudo; the container user must not be root.
RUN if [ "${USER_ID}" = "0" ]; then \
        echo "clauded: USER_ID is 0 because the build ran as root. Run clauded without sudo." >&2; \
        exit 1; \
    fi
RUN groupadd -g ${GROUP_ID} claude 2>/dev/null || true && \
    useradd -m -u ${USER_ID} -g ${GROUP_ID} -d ${HOME_DIR} -s /bin/bash claude && \
    mkdir -p ${HOME_DIR} && chown ${USER_ID}:${GROUP_ID} ${HOME_DIR} && \
    echo "claude ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Cross-platform sound script (calls host sound server via HTTP)
COPY play-sound /usr/local/bin/play-sound
# Clipboard shims (forward to host clipboard server via HTTP)
COPY pbcopy /usr/local/bin/pbcopy
COPY pbpaste /usr/local/bin/pbpaste
COPY xclip /usr/local/bin/xclip
COPY xsel /usr/local/bin/xsel
COPY xdg-open /usr/local/bin/xdg-open
# Voice: on-demand mic bridge client (feeds the container-local PulseAudio)
COPY mic-bridge-client.py /usr/local/bin/mic-bridge-client.py
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/play-sound /usr/local/bin/pbcopy /usr/local/bin/pbpaste /usr/local/bin/xclip /usr/local/bin/xsel /usr/local/bin/xdg-open /usr/local/bin/mic-bridge-client.py /usr/local/bin/entrypoint.sh

# Optional firewall hardening
COPY init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod +x /usr/local/bin/init-firewall.sh

# Prevent OOM on large projects
ENV NODE_OPTIONS="--max-old-space-size=4096"

# GitHub SSH host keys (system-wide, immune to home dir mount overlays)
RUN mkdir -p /etc/ssh && ssh-keyscan github.com >> /etc/ssh/ssh_known_hosts 2>/dev/null

RUN pip3 install pre-commit --break-system-packages

# Python 3.12 alongside the system 3.11.
# node:22-slim is Debian 12 (Bookworm), whose system python3 is 3.11 — kept as
# the default so apt/pip tooling (e.g. pre-commit above) stays undisturbed.
# Debian ships no clean 3.12 (Bookworm=3.11, Trixie=3.13), so uv fetches a
# standalone build into /opt, which is outside the $HOME bind-mount and so
# stays baked in the image. Sessions get python3.12 on PATH, plus `uv` to pull
# any other version on demand (uv python install 3.13, uv venv --python 3.12).
ENV UV_INSTALL_DIR=/usr/local/bin
ENV UV_PYTHON_INSTALL_DIR=/opt/uv/python
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    uv python install 3.12 && \
    ln -sf "$(uv python find 3.12)" /usr/local/bin/python3.12 && \
    chmod -R a+rX /opt/uv

USER claude

# Install Claude Code — pinned version via npm, latest via installer
ARG CLAUDE_VERSION=latest
RUN if [ "$CLAUDE_VERSION" = "latest" ]; then \
        curl -fsSL https://claude.ai/install.sh | bash && \
        sudo cp ~/.local/bin/claude /usr/local/bin/claude; \
    else \
        sudo npm install -g @anthropic-ai/claude-code@${CLAUDE_VERSION}; \
    fi


RUN mkdir -p ~/dev ~/.claude && mkdir -m 700 -p ~/.ssh

WORKDIR ${HOME_DIR}/dev

# The clauded commit this image was built from. clauded compares it with its
# checkout and rebuilds when the checkout has moved on.
ARG CLAUDED_REVISION=unknown
LABEL clauded.revision=${CLAUDED_REVISION}

ENTRYPOINT ["entrypoint.sh"]
