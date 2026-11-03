<#
 91 TV - build script (Windows 11 x64, PowerShell 5.1+ or 7).
   .\build.ps1                 # build EXE, run self-test, make portable ZIP (+ installer if Inno Setup is installed)
   .\build.ps1 -SkipInstaller  # skip Inno Setup step
 Needs: Python 3.12-3.14 (python.org, 64-bit) and internet access (PyPI + GitHub for the mpv video engine).
#>
param([switch]$SkipInstaller, [switch]$CI)
# Native tools (pip, PyInstaller) write progress to stderr; do not treat that as failure. Exit codes are checked explicitly.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$Version = ([regex]::Match((Get-Content aurora\__init__.py -Raw), '__version__\s*=\s*"([^"]+)"')).Groups[1].Value

function Step($m) { Write-Host "`n=== $m ===" -ForegroundColor Red }

Step "Locating Python"
$py = $null
foreach ($v in "3.12", "3.13", "3.14") {
    try { & py "-$v" -c "import sys" 2>$null; if ($LASTEXITCODE -eq 0) { $py = @("py", "-$v"); break } } catch {}
}
if (-not $py) { $py = @("python") }
& $py[0] $py[1..($py.Length)] --version
if ($LASTEXITCODE -ne 0) { throw "Python not found. Install 64-bit Python 3.12+ from python.org and re-run." }

Step "Creating virtual environment and installing dependencies"
if (-not (Test-Path ".venv")) { & $py[0] $py[1..($py.Length)] -m venv .venv; if ($LASTEXITCODE) { throw "venv failed" } }
$vpy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $vpy -m pip install --upgrade pip
& $vpy -m pip install -r requirements-build.txt
if ($LASTEXITCODE) { throw "pip install failed" }

Step "Downloading the mpv video engine (libmpv)"
New-Item -ItemType Directory -Force build\mpv | Out-Null
if (-not (Test-Path "build\mpv\libmpv-2.dll")) {
    $atom = (Invoke-WebRequest "https://github.com/shinchiro/mpv-winbuild-cmake/releases.atom" -UseBasicParsing -ErrorAction Stop).Content
    $tag = [regex]::Match($atom, 'releases/tag/([^"<]+)').Groups[1].Value
    if (-not $tag) { throw "Could not determine latest mpv build tag" }
    $page = (Invoke-WebRequest "https://github.com/shinchiro/mpv-winbuild-cmake/releases/expanded_assets/$tag" -UseBasicParsing -ErrorAction Stop).Content
    $asset = [regex]::Match($page, 'href="([^"]*mpv-dev-x86_64-\d{8}-git-[0-9a-f]+\.7z)"').Groups[1].Value
    if (-not $asset) { throw "Could not find mpv-dev-x86_64 asset in release $tag" }
    Write-Host "Downloading $asset"
    Invoke-WebRequest "https://github.com$asset" -OutFile build\mpv-dev.7z -UseBasicParsing -ErrorAction Stop
    # The archive uses the BCJ2 filter: Windows' built-in tar.exe (libarchive) can unpack it; 7zr.exe is the fallback.
    & tar.exe -xf build\mpv-dev.7z -C build\mpv libmpv-2.dll 2>&1 | Out-Host
    if (-not (Test-Path "build\mpv\libmpv-2.dll")) {
        Write-Host "tar could not extract it - trying 7zr.exe" -ForegroundColor Yellow
        Invoke-WebRequest "https://www.7-zip.org/a/7zr.exe" -OutFile build\7zr.exe -UseBasicParsing -ErrorAction Stop
        & build\7zr.exe e build\mpv-dev.7z -obuild\mpv libmpv-2.dll -y 2>&1 | Out-Host
    }
    if (-not (Test-Path "build\mpv\libmpv-2.dll")) { throw "libmpv-2.dll extraction failed" }
}

Step "Generating icons (if missing)"
if (-not (Test-Path "assets\aurora.ico")) { & $vpy tools\make_icon.py }

Step "Running unit tests"
& $vpy tests\test_core.py
if ($LASTEXITCODE) { throw "Unit tests failed" }

Step "Building 91TV.exe with PyInstaller"
& $vpy -m PyInstaller aurora.spec --noconfirm --clean
if ($LASTEXITCODE) { throw "PyInstaller failed" }
$exe = "dist\91TV\91TV.exe"
if (-not (Test-Path $exe)) { throw "EXE was not produced" }

Step "Self-test of the built EXE"
$env:AURORA_DATA_DIR = Join-Path $env:TEMP "aurora-selftest"
Remove-Item -Recurse -Force $env:AURORA_DATA_DIR -ErrorAction SilentlyContinue
if ($CI) { $env:QT_QPA_PLATFORM = "offscreen" }
$p = Start-Process -FilePath $exe -ArgumentList "--selftest" -Wait -PassThru
$report = Join-Path $env:AURORA_DATA_DIR "logs\selftest.txt"
if (Test-Path $report) { Get-Content $report }
Remove-Item Env:AURORA_DATA_DIR, Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
if ($p.ExitCode -ne 0) { throw "Self-test of the built EXE FAILED (exit code $($p.ExitCode))" }

Step "Packaging"
New-Item -ItemType Directory -Force release | Out-Null
Copy-Item RUN_DEBUG.bat, README.md, TROUBLESHOOTING.md, FEATURES.md, THIRD_PARTY_NOTICES.md dist\91TV\ -ErrorAction SilentlyContinue
$zip = "release\91TV-$Version-win64-portable.zip"
Remove-Item $zip -ErrorAction SilentlyContinue
Compress-Archive -Path dist\91TV -DestinationPath $zip -ErrorAction Stop
Write-Host "Portable ZIP: $zip" -ForegroundColor Green

if (-not $SkipInstaller) {
    $iscc = @("$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe", "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($iscc) { Step "Building installer"; & $iscc "/DAppVersion=$Version" installer.iss; if ($LASTEXITCODE) { throw "Inno Setup failed" } }
    else { Write-Host "Inno Setup not found - installer skipped (portable ZIP is ready). Install from https://jrsoftware.org/isinfo.php to also build a Setup.exe." -ForegroundColor Yellow }
}
Step "DONE"
