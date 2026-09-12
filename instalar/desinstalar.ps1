<#
.SYNOPSIS
    Desinstala Control Horario de este equipo.

.DESCRIPTION
    Quita el programa y los accesos directos. Los datos (registros de jornada,
    clave de cifrado y copias de seguridad) se conservan salvo que se pidan
    borrar expresamente: la ley obliga a guardarlos cuatro años.
#>

[CmdletBinding()]
param([switch]$BorrarDatos, [switch]$Silencioso)

$ErrorActionPreference = 'Stop'
$IdApp        = 'ControlHorario'
$NombreApp    = 'Control Horario'
$Destino      = Join-Path $env:LOCALAPPDATA "Programs\$IdApp"
$CarpetaDatos = Join-Path $env:APPDATA $IdApp

Write-Host ""
Write-Host "  Desinstalar $NombreApp" -ForegroundColor Blue
Write-Host ""

foreach ($carpeta in @([Environment]::GetFolderPath('Desktop'),
                       (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'))) {
    $enlace = Join-Path $carpeta "$NombreApp.lnk"
    if (Test-Path $enlace) {
        Remove-Item $enlace -Force
        Write-Host "    Acceso directo eliminado: $enlace" -ForegroundColor Gray
    }
}

$clave = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$IdApp"
if (Test-Path $clave) { Remove-Item $clave -Recurse -Force }

if (Test-Path $Destino) {
    # El propio script vive dentro de la carpeta que hay que borrar, así que se
    # copia a temporal y se relanza desde allí para poder eliminarla entera.
    if ($PSScriptRoot -eq $Destino) {
        $temporal = Join-Path $env:TEMP "desinstalar_$IdApp.ps1"
        Copy-Item $PSCommandPath $temporal -Force
        $argumentos = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $temporal)
        if ($BorrarDatos) { $argumentos += '-BorrarDatos' }
        if ($Silencioso)  { $argumentos += '-Silencioso' }
        Start-Process powershell -ArgumentList $argumentos
        exit 0
    }
    Start-Sleep -Seconds 1
    Remove-Item $Destino -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "    Programa eliminado de $Destino" -ForegroundColor Gray
}

if ($BorrarDatos) {
    $seguro = $Silencioso
    if (-not $Silencioso) {
        Write-Host ""
        Write-Host '    ATENCION: vas a borrar los registros de jornada.' -ForegroundColor Red
        Write-Host '    El art. 34.9 del Estatuto de los Trabajadores obliga a' -ForegroundColor Red
        Write-Host '    conservarlos cuatro años. Exporta antes un informe.' -ForegroundColor Red
        Write-Host ""
        $seguro = (Read-Host '    Escribe BORRAR para confirmar') -ceq 'BORRAR'
    }
    if ($seguro -and (Test-Path $CarpetaDatos)) {
        Remove-Item $CarpetaDatos -Recurse -Force
        Write-Host '    Datos eliminados.' -ForegroundColor Yellow
    } else {
        Write-Host '    Datos conservados.' -ForegroundColor Green
    }
} else {
    Write-Host ""
    Write-Host "    Los datos siguen en: $CarpetaDatos" -ForegroundColor Green
    Write-Host '    (registros de jornada, clave de cifrado y copias)' -ForegroundColor Gray
}

Write-Host ""
Write-Host '  Desinstalación terminada.' -ForegroundColor Green
Write-Host ""
if (-not $Silencioso) { Read-Host 'Pulsa Intro para salir' }
