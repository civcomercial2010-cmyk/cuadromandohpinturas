# Copia la V2 del repo a C:\Hipopotamo (instalacion local que abre ejecutar.bat / tarea programada)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = "C:\Hipopotamo"
if (-not (Test-Path $dest)) {
    Write-Error "No existe $dest"
}
Copy-Item "$repo\cuadro_mando_base.html" "$dest\cuadro_mando_base.html" -Force
Copy-Item "$repo\cuadro_mando.html" "$dest\cuadro_mando.html" -Force
Write-Host "OK V2 copiada a $dest"
Write-Host "Abre: file:///C:/Hipopotamo/cuadro_mando.html o https://civcomercial2010-cmyk.github.io/cuadromandohpinturas/cuadro_mando.html"
