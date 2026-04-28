$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $scriptRoot "scripts\\install_windows.ps1"

if (-not (Test-Path $target)) {
  throw "Installer not found: $target"
}

& $target @args
