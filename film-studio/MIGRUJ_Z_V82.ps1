param(
  [Parameter(Mandatory=$true)][string]$Source
)
$ErrorActionPreference='Stop'
$target=Join-Path $PSScriptRoot 'data'
$old=Join-Path $Source 'data'
if(-not (Test-Path $old -PathType Container)) { throw "Nie znaleziono folderu z danymi V8.2: $old" }
New-Item -ItemType Directory -Force -Path $target | Out-Null
$stamp=Get-Date -Format 'yyyyMMdd_HHmmss'
$backup=Join-Path $PSScriptRoot "backup_before_migration_$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null
$folders=@('keyframes','clips','exports','master_assets_v82','v7_audio','v8_voice','v7_render','references_v6','personas')
$files=@('studio.sqlite3','master_visual_v82.json')
foreach($name in $files) {
  $src=Join-Path $old $name
  $dest=Join-Path $target $name
  if(Test-Path $src) {
    if(Test-Path $dest) { Copy-Item $dest (Join-Path $backup $name) -Force; Write-Host "Pominięto istniejący: $dest" }
    else { Copy-Item $src $dest; Write-Host "Skopiowano: $name" }
  }
}
foreach($name in $folders) {
  $src=Join-Path $old $name
  $dest=Join-Path $target $name
  if(Test-Path $src -PathType Container) {
    if(Test-Path $dest) { Write-Host "Istniejący folder pozostawiony bez nadpisania: $name" }
    else { Copy-Item $src $dest -Recurse; Write-Host "Skopiowano folder: $name" }
  }
}
Write-Host 'Migracja zakończona. Istniejące pliki nie zostały nadpisane.'
Write-Host 'Jeśli niektóre katalogi już istniały, porównaj je ręcznie ze starszą wersją.'
