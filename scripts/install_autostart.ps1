<#
Start the HoloDesk daemon automatically when you log in, and restart it if it
crashes. Run once from the repo folder:

    powershell -ExecutionPolicy Bypass -File scripts\install_autostart.ps1

It registers a Scheduled Task that runs in YOUR desktop session (needed to see
and click windows). Remove it with scripts\uninstall_autostart.ps1.
#>
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

# Prefer the project's virtualenv; pythonw.exe runs without a console window.
$candidates = @(
    (Join-Path $repo ".venv\Scripts\pythonw.exe"),
    (Join-Path $repo "venv\Scripts\pythonw.exe")
)
$python = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $python) {
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if (-not $cmd) { throw "pythonw.exe not found. Activate your virtualenv or install Python first." }
    $python = $cmd.Source
}

$action = New-ScheduledTaskAction -Execute $python -Argument "`"$repo\run_daemon.py`"" -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName "HoloDesk Daemon" -Action $action -Trigger $trigger `
    -Settings $settings -Description "HoloDesk always-on brain and phone bridge" -Force | Out-Null

Start-ScheduledTask -TaskName "HoloDesk Daemon"
Write-Host "Installed. HoloDesk now starts at login using $python"
Write-Host "Log file: $repo\data\holodesk_daemon.log"
