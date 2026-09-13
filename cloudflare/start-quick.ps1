# Expose la webapp locale (127.0.0.1:8080) via Cloudflare Quick Tunnel.
# Prefixe : lancer d'abord  python -m webapp.server

$ErrorActionPreference = "Stop"

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    Write-Host "[-] cloudflared introuvable dans le PATH." -ForegroundColor Red
    Write-Host "    Installer : https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
    exit 1
}

Write-Host "[i] Tunnel Quick -> http://127.0.0.1:8080" -ForegroundColor Cyan
Write-Host "[i] Copiez l'URL https://....trycloudflare.com affichee ci-dessous dans BotFather." -ForegroundColor Cyan
Write-Host ""

& cloudflared tunnel --url http://127.0.0.1:8080
