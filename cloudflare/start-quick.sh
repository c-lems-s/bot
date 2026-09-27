#!/usr/bin/env bash
# Expose la webapp locale (127.0.0.1:8080) via Cloudflare Quick Tunnel.
# Prefixe : lancer d'abord  python -m webapp.server

set -euo pipefail

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "[-] cloudflared introuvable dans le PATH."
  echo "    Installer : https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
  exit 1
fi

echo "[i] Tunnel Quick -> http://127.0.0.1:8080"
echo "[i] Copiez l'URL https://....trycloudflare.com affichee ci-dessous dans BotFather."
echo "[!] Si QUIC/7844 echoue : couper Mullvad/VPN puis relancer."
echo ""

exec cloudflared tunnel --url http://127.0.0.1:8080
