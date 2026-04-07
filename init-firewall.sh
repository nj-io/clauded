#!/bin/bash
# Network hardening: restrict outbound traffic to only necessary domains.
# Run with: sudo /usr/local/bin/init-firewall.sh
# This must run as root (the container user is non-root by default).

set -euo pipefail

# Default policy: drop all outbound
iptables -P OUTPUT DROP

# Allow loopback
iptables -A OUTPUT -o lo -j ACCEPT

# Allow established connections
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow DNS
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# Anthropic API
iptables -A OUTPUT -d api.anthropic.com -p tcp --dport 443 -j ACCEPT
iptables -A OUTPUT -d statsig.anthropic.com -p tcp --dport 443 -j ACCEPT
iptables -A OUTPUT -d sentry.io -p tcp --dport 443 -j ACCEPT

# GitHub (for git operations)
iptables -A OUTPUT -d github.com -p tcp --dport 22 -j ACCEPT
iptables -A OUTPUT -d github.com -p tcp --dport 443 -j ACCEPT
iptables -A OUTPUT -d api.github.com -p tcp --dport 443 -j ACCEPT

# npm registry (for package installs)
iptables -A OUTPUT -d registry.npmjs.org -p tcp --dport 443 -j ACCEPT

# PyPI (for pip installs)
iptables -A OUTPUT -d pypi.org -p tcp --dport 443 -j ACCEPT
iptables -A OUTPUT -d files.pythonhosted.org -p tcp --dport 443 -j ACCEPT

# Chrome bridge (for Claude in Chrome integration)
iptables -A OUTPUT -d bridge.claudeusercontent.com -p tcp --dport 443 -j ACCEPT

echo "Firewall rules applied. Only whitelisted domains are accessible."
