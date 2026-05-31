param(
    [Parameter(Mandatory = $true)]
    [string]$PublicUrl
)

$PublicUrl = $PublicUrl.TrimEnd("/")
$envFile = Join-Path $PSScriptRoot ".." ".env"

if (-not (Test-Path $envFile)) {
    Write-Host "No se encontro $envFile" -ForegroundColor Red
    exit 1
}

$content = Get-Content $envFile -Raw
if ($content -match "PUBLIC_BASE_URL=.*") {
    $content = $content -replace "PUBLIC_BASE_URL=.*", "PUBLIC_BASE_URL=$PublicUrl"
} else {
    $content += "`nPUBLIC_BASE_URL=$PublicUrl`n"
}
Set-Content -Path $envFile -Value $content -NoNewline
Write-Host "OK .env -> PUBLIC_BASE_URL=$PublicUrl" -ForegroundColor Green

$backend = Join-Path $PSScriptRoot ".."
Push-Location $backend
$env:PYTHONPATH = "."
& ".\venv\Scripts\python.exe" ".\scripts\fix_twilio_webhook.py"
Pop-Location

Write-Host ""
Write-Host "Webhook Twilio:" -ForegroundColor Cyan
Write-Host "  $PublicUrl/twilio/voice/incoming"
Write-Host "Reinicia uvicorn (Ctrl+C y vuelve a ejecutar)." -ForegroundColor Yellow
