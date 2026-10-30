# Safe one-time data migration from previous local V8 installation.
param([string]$OldFolder = 'D:\film-studio\V8\Nasz_Dzien_Film_Studio_V8')
$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$OldData = Join-Path $OldFolder 'data'
$NewData = Join-Path $Here 'data'
if (-not (Test-Path -LiteralPath $OldData -PathType Container)) {
  Write-Error "Nie znaleziono starego folderu: $OldData"; exit 1
}
if ([System.IO.Path]::GetFullPath($OldData) -eq [System.IO.Path]::GetFullPath($NewData)) {
  Write-Error 'Folder źródłowy i docelowy są takie same.'; exit 1
}
Write-Host "Źródło: $OldData"
Write-Host "Cel:    $NewData"
Write-Host 'Zamknij obie instancje programu przed przeniesieniem.'
$Decision = Read-Host 'Wpisz PRZENIES, aby zrobić kopię zapasową i skopiować dane z V8 do V8.2'
if ($Decision -ne 'PRZENIES') { Write-Host 'Anulowano. Niczego nie zmieniono.'; exit 0 }
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Backup = Join-Path $Here ("backup_data_przed_migracja_" + $Stamp)
if (Test-Path -LiteralPath $NewData) {
  Copy-Item -LiteralPath $NewData -Destination $Backup -Recurse -Force
  Write-Host "Kopia bieżących danych: $Backup"
}
if (-not (Test-Path -LiteralPath $NewData)) { New-Item -ItemType Directory -Path $NewData | Out-Null }
Copy-Item -Path (Join-Path $OldData '*') -Destination $NewData -Recurse -Force
Write-Host 'Skopiowano dane. Stary folder NIE został zmieniony. Uruchom start_windows.bat w V8.2.'
