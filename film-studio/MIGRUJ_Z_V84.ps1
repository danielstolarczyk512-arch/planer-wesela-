param(
  [Parameter(Mandatory=$true)][string]$Source
)
$ErrorActionPreference = 'Stop'
$Target = Split-Path -Parent $MyInvocation.MyCommand.Path
$From = Join-Path $Source 'data'
$To = Join-Path $Target 'data'
if (-not (Test-Path -PathType Container $From)) { throw "Nie znaleziono katalogu data w V8.4: $From" }
if ((Resolve-Path $Source).Path -eq (Resolve-Path $Target).Path) { throw 'Nie kopiuj do siebie samego' }
Write-Host 'Zamknij aplikację V8.4 i V8.5, zanim rozpoczniesz migrację.'
$Answer = Read-Host 'Migracja może zastąpić dane w NOWYM folderze V8.5. Wpisz MIGRUJ'
if ($Answer -ne 'MIGRUJ') { throw 'Migracja anulowana' }
$Stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$Backup = Join-Path $Target ('data_backup_before_migration_' + $Stamp)
if (Test-Path $To) { Copy-Item -LiteralPath $To -Destination $Backup -Recurse -Force }
New-Item -ItemType Directory -Path $To -Force | Out-Null
Copy-Item -Path (Join-Path $From '*') -Destination $To -Recurse -Force
Push-Location $Target
try {
  if (Get-Command py -ErrorAction SilentlyContinue) { py -3 tools/install_master_v85.py }
  else { python tools/install_master_v85.py }
  if ($LASTEXITCODE -ne 0) { throw 'Nie udało się przypisać nowego wzorca. Sprawdź instrukcję.' }
} finally { Pop-Location }
Write-Host "Przeniesiono dane do $To"
Write-Host "Kopia poprzednich danych: $Backup"
Write-Host 'Obrazy i stare renderowania pozostają, ale ponownie przypnij Master Visual Lock oraz oceń klipy.'
