# Run Northline on Windows with HTTPS (mic requires secure context).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Cert = Join-Path $Root "certs\cert.pem"
$Key = Join-Path $Root "certs\key.pem"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$Uvicorn = Join-Path $Root ".venv\Scripts\uvicorn.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Missing .venv — run .\scripts\install_offline.ps1 first"
}

if (-not (Test-Path $Cert) -or -not (Test-Path $Key)) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root "certs") | Out-Null
    $hostName = $env:COMPUTERNAME
    openssl req -x509 -newkey rsa:2048 -nodes `
      -keyout $Key -out $Cert -days 825 `
      -subj "/CN=$hostName" `
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
}

$env:HF_HUB_OFFLINE = "1"
$env:HF_HOME = Join-Path $Root "models\hf"
$env:LTP_PATH = Join-Path $Root "models\languagetool"
if (-not $env:NORTHLINE_DEVICE) { $env:NORTHLINE_DEVICE = "auto" }

# Prefer HTTPS app on 8443; optional HTTP redirect on 8000
$Redirect = Start-Process -PassThru -WindowStyle Hidden -FilePath $VenvPython -ArgumentList `
  "`"$Root\scripts\http_redirect.py`""
$App = Start-Process -PassThru -WindowStyle Hidden -FilePath $Uvicorn -ArgumentList `
  "app.main:app --host 0.0.0.0 --port 8443 --workers 1 --ssl-certfile `"$Cert`" --ssl-keyfile `"$Key`""

Write-Host "Northline HTTPS: https://127.0.0.1:8443"
Write-Host "HTTP redirect:  http://127.0.0.1:8000"
Write-Host "PIDs: app=$($App.Id) redirect=$($Redirect.Id)"
Write-Host "Stop with: Stop-Process -Id $($App.Id),$($Redirect.Id)"
