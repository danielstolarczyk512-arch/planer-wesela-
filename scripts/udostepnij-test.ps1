# Udostępnia środowisko testowe znajomym przez darmowy tunel Cloudflare (bez konta i domeny).
# Instrukcja: docs/test-dla-znajomych.md. Uruchomienie z katalogu repozytorium:
#   powershell -ExecutionPolicy Bypass -File scripts\udostepnij-test.ps1
# Działa, dopóki to okno jest otwarte, a laptop włączony. Ctrl+C zamyka tunel (aplikacja zostaje w Dockerze).

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$deploy = Join-Path $repo "deploy"
$envFile = Join-Path $deploy ".env.test"
$log = Join-Path $env:TEMP "naszdzien-tunel.log"
$compose = @("compose", "-p", "naszdzien-test", "-f", "compose.prod.yaml", "-f", "compose.test.yaml", "--env-file", ".env.test")

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    Write-Host "Brak programu cloudflared. Zainstaluj (raz):  winget install --id Cloudflare.cloudflared -e"
    Write-Host "Potem zamknij i otworz ponownie okno PowerShell i uruchom ten skrypt jeszcze raz."
    exit 1
}
if (-not (Test-Path $envFile)) {
    Write-Host "Brak pliku deploy\.env.test - opis w docs\test-dla-znajomych.md."
    exit 1
}

Push-Location $deploy
try {
    Write-Host "1/3 Uruchamiam aplikacje (Docker)..."
    & docker @compose up -d | Out-Null

    Write-Host "2/3 Otwieram tunel..."
    if (Test-Path $log) { Remove-Item $log }
    $tunnel = Start-Process cloudflared -ArgumentList "tunnel", "--no-autoupdate", "--url", "http://127.0.0.1:8090", "--logfile", $log -PassThru -WindowStyle Hidden
    $url = $null
    for ($i = 0; $i -lt 60 -and -not $url; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Path $log) {
            $hit = Select-String -Path $log -Pattern "https://[a-z0-9-]+[.]trycloudflare[.]com" | Select-Object -First 1
            if ($hit) { $url = $hit.Matches[0].Value }
        }
    }
    if (-not $url) { throw "Tunel nie podal adresu w 60 s - log: $log" }

    Write-Host "3/3 Ustawiam adres w linkach e-maili i kodach QR..."
    $utf8 = New-Object System.Text.UTF8Encoding $false
    $lines = [IO.File]::ReadAllLines($envFile, $utf8) | ForEach-Object {
        if ($_.StartsWith("WP_PUBLIC_APP_URL=")) { "WP_PUBLIC_APP_URL=$url" } else { $_ }
    }
    [IO.File]::WriteAllLines($envFile, [string[]]$lines, $utf8)
    & docker @compose up -d --force-recreate api worker | Out-Null

    Write-Host ""
    Write-Host "Gotowe. Wyslij koledze ten adres:  $url"
    Write-Host "E-maile (potwierdzenie konta, reset hasla) podgladasz na laptopie: http://127.0.0.1:8026"
    Write-Host "Adres zmienia sie przy kazdym uruchomieniu skryptu. Ctrl+C zamyka tunel."
    Wait-Process -Id $tunnel.Id
}
finally {
    if ($tunnel -and -not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id }
    Pop-Location
}
