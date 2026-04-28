param(
  [string]$WebPort = $(if ($env:WEB_PORT) { $env:WEB_PORT } else { "1288" }),
  [string]$AppRoot = $(if ($env:APP_ROOT) { $env:APP_ROOT } else { Join-Path $env:ProgramData "AfterClaw" }),
  [string]$StorageRoot = $(if ($env:STORAGE_ROOT) { $env:STORAGE_ROOT } else { Join-Path $env:USERPROFILE "AfterClawData\\Storage" }),
  [string]$PublicScheme = $(if ($env:PUBLIC_SCHEME) { $env:PUBLIC_SCHEME } else { "http" }),
  [string]$PublicHost = $(if ($env:PUBLIC_HOST) { $env:PUBLIC_HOST } else { "127.0.0.1:1288" }),
  [string]$DownloadsEnabled = $(if ($env:DOWNLOADS_ENABLED) { $env:DOWNLOADS_ENABLED } else { "1" }),
  [string]$QbtService = $(if ($env:QBT_SERVICE) { $env:QBT_SERVICE } else { "qbittorrent-nox" }),
  [string]$QbtApiUrl = $(if ($env:QBT_API_URL) { $env:QBT_API_URL } else { "http://127.0.0.1:8080" }),
  [string]$QbtApiUsername = $(if ($env:QBT_API_USERNAME) { $env:QBT_API_USERNAME } else { "" }),
  [string]$QbtApiPassword = $(if ($env:QBT_API_PASSWORD) { $env:QBT_API_PASSWORD } else { "" }),
  [string]$DdnsService = $(if ($env:DDNS_SERVICE) { $env:DDNS_SERVICE } else { "ddns-go.service" }),
  [string]$ShareclipStorageRoot = $(if ($env:SHARECLIP_STORAGE_ROOT) { $env:SHARECLIP_STORAGE_ROOT } else { Join-Path (Join-Path $env:ProgramData "AfterClaw") "shareclip\\storage" }),
  [string]$TaskName = "AfterClaw"
)

$ErrorActionPreference = "Stop"

function Write-Step {
  param([string]$Message)
  Write-Host "[AfterClaw] $Message"
}

function Test-IsAdmin {
  $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = New-Object Security.Principal.WindowsPrincipal($identity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Escape-PSString {
  param([string]$Value)
  if ($null -eq $Value) { return "" }
  return $Value.Replace("`", "``").Replace('"', '`"')
}

function Get-HostPythonCommand {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    return @("py", "-3")
  }
  if (Get-Command python -ErrorAction SilentlyContinue) {
    return @("python")
  }
  return $null
}

function Invoke-HostPython {
  param([string[]]$Args)
  $cmd = Get-HostPythonCommand
  if (-not $cmd) {
    throw "Python 3 not found."
  }
  $exe = $cmd[0]
  $prefix = @()
  if ($cmd.Count -gt 1) {
    $prefix = $cmd[1..($cmd.Count - 1)]
  }
  & $exe @prefix @Args
  if ($LASTEXITCODE -ne 0) {
    throw "Python command failed with exit code $LASTEXITCODE: $exe $($Args -join ' ')"
  }
}

if (-not (Test-IsAdmin)) {
  throw "Please run this installer in an elevated PowerShell session (Run as Administrator)."
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$venvDir = Join-Path $AppRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\\python.exe"
$runnerScript = Join-Path $AppRoot "run_afterclaw.ps1"
$mainScript = Join-Path $AppRoot "app.py"

Write-Step "Preparing Python 3..."
if (-not (Get-HostPythonCommand)) {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Step "Python 3 not found, installing via winget..."
    winget install --id Python.Python.3.12 --source winget --silent --accept-package-agreements --accept-source-agreements
  } else {
    throw "Python 3 not found, and winget is unavailable. Please install Python 3.9+ first."
  }
}

if (-not (Get-HostPythonCommand)) {
  throw "Python 3 installation failed or not yet in PATH. Please reopen PowerShell and run again."
}

Write-Step "Preparing directories..."
New-Item -ItemType Directory -Path $AppRoot -Force | Out-Null
New-Item -ItemType Directory -Path $StorageRoot -Force | Out-Null
New-Item -ItemType Directory -Path $ShareclipStorageRoot -Force | Out-Null

Write-Step "Copying application files..."
$copyItems = @(
  "app.py",
  "fcc",
  "ddns",
  "web",
  "naming",
  "shareclip",
  "data",
  "requirements.txt",
  "pyproject.toml"
)

foreach ($name in $copyItems) {
  $src = Join-Path $repoRoot $name
  if (-not (Test-Path $src)) {
    continue
  }
  $dst = Join-Path $AppRoot $name
  if (Test-Path $dst) {
    Remove-Item -Recurse -Force $dst
  }
  Copy-Item -Recurse -Force $src $dst
}

if (-not (Test-Path $mainScript)) {
  throw "app.py was not copied successfully to $AppRoot"
}

Write-Step "Creating virtual environment..."
if (-not (Test-Path $venvPython)) {
  Invoke-HostPython -Args @("-m", "venv", $venvDir)
}

Write-Step "Installing dependencies..."
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
  throw "pip upgrade failed with exit code $LASTEXITCODE"
}

$requirementsFile = Join-Path $AppRoot "requirements.txt"
if (Test-Path $requirementsFile) {
  & $venvPython -m pip install -r $requirementsFile
  if ($LASTEXITCODE -ne 0) {
    throw "pip install -r requirements.txt failed with exit code $LASTEXITCODE"
  }
}

Write-Step "Creating runtime script..."
$runnerLines = @(
  '$ErrorActionPreference = "Stop"',
  '$env:WEB_PORT = "' + (Escape-PSString $WebPort) + '"',
  '$env:STORAGE_ROOT = "' + (Escape-PSString $StorageRoot) + '"',
  '$env:PUBLIC_SCHEME = "' + (Escape-PSString $PublicScheme) + '"',
  '$env:PUBLIC_HOST = "' + (Escape-PSString $PublicHost) + '"',
  '$env:DOWNLOADS_ENABLED = "' + (Escape-PSString $DownloadsEnabled) + '"',
  '$env:QBT_SERVICE = "' + (Escape-PSString $QbtService) + '"',
  '$env:QBT_API_URL = "' + (Escape-PSString $QbtApiUrl) + '"',
  '$env:QBT_API_USERNAME = "' + (Escape-PSString $QbtApiUsername) + '"',
  '$env:QBT_API_PASSWORD = "' + (Escape-PSString $QbtApiPassword) + '"',
  '$env:DDNS_SERVICE = "' + (Escape-PSString $DdnsService) + '"',
  '$env:SHARECLIP_STORAGE_ROOT = "' + (Escape-PSString $ShareclipStorageRoot) + '"',
  'Set-Location "' + (Escape-PSString $AppRoot) + '"',
  '& "' + (Escape-PSString $venvPython) + '" "' + (Escape-PSString $mainScript) + '"'
)
Set-Content -Path $runnerScript -Value ($runnerLines -join "`r`n") -Encoding UTF8

Write-Step "Registering startup task..."
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runnerScript`""
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "NT AUTHORITY\\SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Step "Install completed."
Write-Host "Dashboard URL: http://127.0.0.1:$WebPort"
Write-Host "Task name   : $TaskName"
Write-Host "Task status :"
Get-ScheduledTask -TaskName $TaskName | Format-Table -AutoSize TaskName, State, TaskPath
