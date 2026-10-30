Set-Location $PSScriptRoot
Write-Host "NASZ DZIEN - FILM DIRECTOR STUDIO v4.0"
Write-Host "Uzyj NOWEGO, obroconego klucza Sogni (stary byl juz w rozmowie)."
$secure = Read-Host "Klucz Sogni (ukryty)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $env:SOGNI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    $secure.Dispose()
}
try {
    if (Get-Command py -ErrorAction SilentlyContinue) { py -3 server.py }
    else { python server.py }
} finally {
    Remove-Item Env:SOGNI_API_KEY -ErrorAction SilentlyContinue
}
