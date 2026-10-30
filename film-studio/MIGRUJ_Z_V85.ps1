param([Parameter(Mandatory=$true)][string]$Source)
$ErrorActionPreference='Stop'
$Target=Split-Path -Parent $MyInvocation.MyCommand.Path
$From=Join-Path $Source 'data'; $To=Join-Path $Target 'data'
if (-not (Test-Path -LiteralPath $From -PathType Container)) { throw "Brak danych V8.5: $From" }
if ((Resolve-Path -LiteralPath $Source).Path -eq (Resolve-Path -LiteralPath $Target).Path) { throw 'Nie kopiuj danych do tego samego folderu' }
Write-Host 'Zamknij V8.5 i V8.6 przed migracją.'
$Answer=Read-Host 'Migracja wykona kopię bezpieczeństwa danych V8.6 i przeniesie dane V8.5. Wpisz MIGRUJ'
if ($Answer -ne 'MIGRUJ') { throw 'Anulowano migrację' }
$Stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$Backup=Join-Path $Target ("data_backup_before_v86_$Stamp")
if (Test-Path -LiteralPath $To) { Copy-Item -LiteralPath $To -Destination $Backup -Recurse -Force }
New-Item -ItemType Directory -Path $To -Force | Out-Null
Copy-Item -Path (Join-Path $From '*') -Destination $To -Recurse -Force
Write-Host "Przeniesiono dane: $To"
Write-Host "Poprzednie dane docelowe: $Backup"
Write-Host 'Nowy Boguś zostanie dołączony przy uruchomieniu serwera. Weryfikuj ręcznie jego zdjęcia przed generacją.'
Write-Host 'Nie kopiuj starych plików web, assets ani studio — wtedy utracisz ulepszenia V8.6.'
