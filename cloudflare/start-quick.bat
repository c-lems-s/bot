@echo off
REM Expose la webapp locale (127.0.0.1:8080) via Cloudflare Quick Tunnel.
REM Prefixe : lancer d'abord  python -m webapp.server

where cloudflared >nul 2>&1
if errorlevel 1 (
    echo [-] cloudflared introuvable dans le PATH.
    echo     Installer : https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
    pause
    exit /b 1
)

echo [i] Tunnel Quick -^> http://127.0.0.1:8080
echo [i] Copiez l'URL https://....trycloudflare.com affichee ci-dessous dans BotFather.
echo [!] Si QUIC/7844 echoue : couper Mullvad/VPN puis relancer.
echo.

cloudflared tunnel --url http://127.0.0.1:8080
pause
