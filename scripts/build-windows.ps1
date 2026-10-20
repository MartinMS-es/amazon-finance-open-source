param([string]$InnoCompiler='ISCC.exe')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
function CheckExit { if($LASTEXITCODE -ne 0){throw "Build failed ($LASTEXITCODE)"} }
npm ci
CheckExit
npm run typecheck
CheckExit
npm run build
CheckExit
python -m pip install -r requirements-build.txt
CheckExit
python scripts/audit-release.py
CheckExit
python -m PyInstaller --noconfirm --clean --windowed --name AmazonFinanceOpenSource --add-data 'local-web;local-web' --add-data 'public;public' --hidden-import qrcode.image.svg --exclude-module PIL --exclude-module lxml --collect-all cryptography desktop_app.py
CheckExit
& $InnoCompiler packaging/windows.iss
CheckExit
