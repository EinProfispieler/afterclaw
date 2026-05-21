param(
  [switch]$Uninstall,
  [switch]$Update,
  [switch]$Doctor
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $scriptRoot "scripts\\install_windows.ps1"

if (-not (Test-Path $target)) {
  throw "Installer not found: $target"
}

if ($Uninstall) {
  & $target -Uninstall @args
} elseif ($Update) {
  & $target -Update @args
} elseif ($Doctor) {
  & $target -Doctor @args
} else {
  & $target @args
}
