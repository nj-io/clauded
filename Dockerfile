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
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium

# Match host UID/GID so mounted files have correct ownership
ARG USER_ID=501
ARG GROUP_ID=20
ARG HOME_DIR=/home/claude
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
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/play-sound /usr/local/bin/pbcopy /usr/local/bin/pbpaste /usr/local/bin/xclip /usr/local/bin/xsel /usr/local/bin/xdg-open /usr/local/bin/entrypoint.sh

# Optional firewall hardening
COPY init-firewall.sh /usr/local/bin/init-firewall.sh
RUN chmod +x /usr/local/bin/init-firewall.sh

# Prevent OOM on large projects
ENV NODE_OPTIONS="--max-old-space-size=4096"

# GitHub SSH host keys (system-wide, immune to home dir mount overlays)
RUN mkdir -p /etc/ssh && ssh-keyscan github.com >> /etc/ssh/ssh_known_hosts 2>/dev/null

RUN pip3 install pre-commit --break-system-packages

USER claude

# Install Claude Code via direct installer (more up-to-date than npm)
ARG CLAUDE_VERSION=latest
RUN curl -fsSL https://claude.ai/install.sh | bash && \
    sudo cp ~/.local/bin/claude /usr/local/bin/claude


RUN mkdir -p ~/dev ~/.claude && mkdir -m 700 -p ~/.ssh

WORKDIR ${HOME_DIR}/dev

ENTRYPOINT ["entrypoint.sh"]
