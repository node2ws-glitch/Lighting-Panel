#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this script as root (sudo)." >&2
  exit 1
fi

command -v iptables >/dev/null || { echo "iptables is required." >&2; exit 1; }
iptables -nL DOCKER-USER >/dev/null 2>&1 || {
  echo "Docker DOCKER-USER chain is missing. Enable Docker iptables integration before applying this policy." >&2
  exit 1
}

apply_family() {
  local binary="$1"
  local chain="$2"
  local family="$3"
  shift 3
  local cidr
  "$binary" -nL DOCKER-USER >/dev/null 2>&1 || return 1
  "$binary" -N "$chain" 2>/dev/null || true
  "$binary" -F "$chain"
  for cidr in "$@"; do
    if [[ "$family" == "ipv4" && "$cidr" != *:* ]] || [[ "$family" == "ipv6" && "$cidr" == *:* ]]; then
      "$binary" -A "$chain" -p tcp -m conntrack --ctorigdstport 32000:32999 -s "$cidr" -j RETURN
    fi
  done
  "$binary" -A "$chain" -p tcp -m conntrack --ctorigdstport 32000:32999 -j DROP
  "$binary" -A "$chain" -j RETURN
  "$binary" -C DOCKER-USER -j "$chain" 2>/dev/null || "$binary" -I DOCKER-USER 1 -j "$chain"
}

apply_family iptables LPGP-DB-ALLOW ipv4 "$@"
if command -v ip6tables >/dev/null && ip6tables -nL DOCKER-USER >/dev/null 2>&1; then
  apply_family ip6tables LPGP6-DB-ALLOW ipv6 "$@"
else
  echo "WARNING: IPv6 DOCKER-USER chain is unavailable. Disable Docker IPv6 publishing or configure an equivalent IPv6 firewall policy." >&2
fi

echo "Applied database port allowlist for Docker-published database ports 32000–32999."
echo "Persist the rules across reboot with your distribution's netfilter-persistent/firewall service."
