# Offline install on Windows (Python 3.10 + CUDA 11.8 recommended).
param(
    [ValidateSet("gpu", "cpu313")]
    [string]$Mode = "gpu"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if ($Mode -eq "cpu313") {
    $Py = if ($env:PYTHON) { $env:PYTHON } else { "py -3.13" }
    $Wheel = Join-Path $Root "wheelhouse\windows-cp313-cpu"
    $Req = Join-Path $Root "requirements\cpu-py313.txt"
} else {
    $Py = if ($env:PYTHON) { $env:PYTHON } else { "py -3.10" }
    $Wheel = Join-Path $Root "wheelhouse\windows-cp310-cu118"
    $Req = Join-Path $Root "requirements\gpu-cu118.txt"
}

if (-not (Test-Path $Wheel) -or -not (Get-ChildItem "$Wheel\*.whl" -ErrorAction SilentlyContinue)) {
    Write-Error "Missing wheels in $Wheel. On an online PC run: python scripts/download_wheelhouse.py"
}

$java = Get-Command java -ErrorAction SilentlyContinue
if (-not $java) {
    Write-Error "Java 17+ is required for LanguageTool. Install a JRE and re-run."
}

# Flatten -r requirements
$Flat = Join-Path $env:TEMP "northline-reqs-flat.txt"
$lines = @()
Get-Content $Req | ForEach-Object {
    $s = ($_ -replace '#.*', '').Trim()
    if (-not $s) { return }
    if ($s.StartsWith("-r ")) {
        $nested = Join-Path $Root ("requirements\" + $s.Substring(3).Trim())
        Get-Content $nested | ForEach-Object {
            $n = ($_ -replace '#.*', '').Trim()
            if ($n -and -not $n.StartsWith("-r ")) { $lines += $n }
        }
    } else {
        $lines += $s
    }
}
$lines | Set-Content -Encoding utf8 $Flat

& $Py -m venv .venv
$Pip = Join-Path $Root ".venv\Scripts\python.exe"
& $Pip -m pip install --upgrade pip setuptools wheel
& $Pip -m pip install --no-index --find-links="$Wheel" -r "$Flat"

& $Pip -c "import ctranslate2; print('ctranslate2', ctranslate2.__version__, 'cuda', ctranslate2.get_cuda_device_count()); import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())"

Write-Host ""
Write-Host "Installed from $Wheel"
Write-Host "Run: .\scripts\run.ps1"
Write-Host "Copy models\ from an online download_assets.py run if missing."
