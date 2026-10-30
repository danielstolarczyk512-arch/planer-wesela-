Set-Location $PSScriptRoot
Write-Host "NASZ DZIEN - FILM DIRECTOR STUDIO 4.0"
Write-Host "SOGNI UNLIMITED ONLY: bez Spark, bez platnych modeli premium."
Write-Host "Polaczenie z telefonu wymaga prywatnej sieci Wi-Fi. Nie otwieraj portu w Internecie."
$keySecure = Read-Host "NOWY klucz API Sogni (ukryty)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($keySecure)
try { $env:SOGNI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr); $keySecure.Dispose() }
$tokenSecure = Read-Host "Haslo dostepu z telefonu min. 8 znakow (ukryte)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($tokenSecure)
try { $env:STUDIO_ACCESS_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr); $tokenSecure.Dispose() }
if ($env:STUDIO_ACCESS_TOKEN.Length -lt 8) {
    Write-Error "Haslo musi miec co najmniej 8 znakow."
    Remove-Item Env:SOGNI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:STUDIO_ACCESS_TOKEN -ErrorAction SilentlyContinue
    exit 1
}
try {
    Write-Host "Na PC: http://127.0.0.1:8765"
    Write-Host "Na telefonie w tej samej sieci: http://ADRES_IP_KOMPUTERA:8765"
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 server.py --host 0.0.0.0 }
    else { python server.py --host 0.0.0.0 }
} finally {
    Remove-Item Env:SOGNI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:STUDIO_ACCESS_TOKEN -ErrorAction SilentlyContinue
}
