# Lance un tunnel Cloudflare nommé (URL stable).
# Prefixe : copier config.example.yml -> config.yml, puis python -m webapp.server

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$config = Join-Path $PSScriptRoot "config.yml"

if (-not (Test-Path $config)) {
    Write-Host "[-] Fichier manquant : cloudflare\config.yml" -ForegroundColor Red
    Write-Host "    Copiez config.example.yml vers config.yml et renseignez tunnel + hostname."
    exit 1
}

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cloudflared) {
    Write-Host "[-] cloudflared introuvable dans le PATH." -ForegroundColor Red
    exit 1
}

Write-Host "[i] Tunnel nommé avec $config" -ForegroundColor Cyan
& cloudflared tunnel --config $config run
