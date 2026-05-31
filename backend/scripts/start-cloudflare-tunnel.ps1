# Túnel alternativo a ngrok (Twilio suele conectar mejor con Cloudflare)
# Uso: .\scripts\start-cloudflare-tunnel.ps1
# Copia la URL https://....trycloudflare.com a PUBLIC_BASE_URL y Twilio webhook

Write-Host "Iniciando Cloudflare Tunnel hacia localhost:8000..." -ForegroundColor Cyan
Write-Host "Asegurate de que uvicorn este corriendo en el puerto 8000." -ForegroundColor Yellow
Write-Host ""

$cfPath = "$env:LOCALAPPDATA\Microsoft\WinGet\Links\cloudflared.exe"
if (-not (Test-Path $cfPath)) {
    $cf = Get-Command cloudflared -ErrorAction SilentlyContinue
    if ($cf) { $cfPath = $cf.Source }
}
if (-not (Test-Path $cfPath)) {
    Write-Host "cloudflared no instalado. Instala con:" -ForegroundColor Red
    Write-Host "  winget install Cloudflare.cloudflared" -ForegroundColor White
    exit 1
}

& $cfPath tunnel --url http://localhost:8000
