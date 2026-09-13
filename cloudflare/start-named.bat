@echo off
REM Lance un tunnel Cloudflare nomme (URL stable).
REM Prefixe : config.example.yml -> config.yml, puis python -m webapp.server

set "CONFIG=%~dp0config.yml"

if not exist "%CONFIG%" (
    echo [-] Fichier manquant : cloudflare\config.yml
    echo     Copiez config.example.yml vers config.yml et renseignez tunnel + hostname.
    pause
    exit /b 1
)

where cloudflared >nul 2>&1
if errorlevel 1 (
    echo [-] cloudflared introuvable dans le PATH.
    pause
    exit /b 1
)

echo [i] Tunnel nomme avec %CONFIG%
cloudflared tunnel --config "%CONFIG%" run
pause
