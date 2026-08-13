$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path ".venv")) {
    py -3.14 -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\python.exe selftest.py

.\.venv\Scripts\python.exe convert_icon.py

.\.venv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --windowed `
    --name "RZ Service" --icon icon.ico --add-data "icon.png;." --add-data "icon.ico;." app_service.py

.\.venv\Scripts\pyinstaller.exe --noconfirm --clean --onefile --windowed `
    --name "RZ unzip" --icon icon.ico --add-data "icon.png;." --add-data "icon.ico;." app_unzip.py

Write-Host ""
Write-Host "Готово! Исполняемые файлы:"
Get-ChildItem -LiteralPath "dist" | ForEach-Object { Write-Host "  $($_.FullName)" }
