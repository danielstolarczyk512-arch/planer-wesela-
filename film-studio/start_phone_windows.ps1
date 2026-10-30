Set-Location $PSScriptRoot
Write-Host "NASZ DZIEN - DOSTEP Z TELEFONU (SIEC PRYWATNA)"
Write-Host "Wpisz haslo >= 8 znakow. Nie wystawiaj tego serwera do internetu bez HTTPS."
$secure = Read-Host "Haslo dostepu (ukryte)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $env:STUDIO_ACCESS_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr); $secure.Dispose() }
try {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 server.py --host 0.0.0.0 }
    else { python server.py --host 0.0.0.0 }
} finally { Remove-Item Env:STUDIO_ACCESS_TOKEN -ErrorAction SilentlyContinue }
