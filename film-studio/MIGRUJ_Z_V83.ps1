param([Parameter(Mandatory=$true)][string]$Source)
$ErrorActionPreference = 'Stop'
$Target = Split-Path -Parent $MyInvocation.MyCommand.Path
$FromData = Join-Path $Source 'data'
$ToData = Join-Path $Target 'data'
if (-not (Test-Path $FromData -PathType Container)) { throw "Nie znaleziono katalogu danych: $FromData" }
if ((Resolve-Path $FromData).Path -eq (Resolve-Path $ToData).Path) { throw 'Nie można migrować do tego samego katalogu' }
Write-Host 'NASZ DZIEŃ V8.4 — bezpieczne kopiowanie danych z V8.3'
Write-Host "Źródło: $FromData"
Write-Host "Cel:    $ToData"
Write-Warning 'Najpierw ZAMKNIJ oba uruchomione programy. Nie kopiuj aktywnej bazy SQLite!'
$answer = Read-Host 'Wpisz TAK, aby utworzyć kopię i rozpocząć'
if ($answer -cne 'TAK') { Write-Host 'Anulowano'; exit 1 }
$Backup = Join-Path $Target ('backup_data_przed_migracja_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
New-Item -ItemType Directory -Force -Path $Backup | Out-Null
if (Test-Path $ToData) {
    Copy-Item -LiteralPath $ToData -Destination (Join-Path $Backup 'data') -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $ToData | Out-Null
Get-ChildItem -LiteralPath $FromData -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $ToData -Recurse -Force
}
Write-Host "Zakończono. Kopia poprzednich danych V8.4: $Backup"
Write-Host 'Uruchom start_windows.bat i zweryfikuj projekty.'
Write-Host 'Nie uruchomiono Sogni ani żadnej generacji.'
