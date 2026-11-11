<#
Keep the laptop awake while it is PLUGGED IN, so HoloDesk stays reachable.
Battery behaviour is left alone. Run from an Administrator PowerShell:

    powershell -ExecutionPolicy Bypass -File scripts\power_always_on.ps1

Undo:  powershell -ExecutionPolicy Bypass -File scripts\power_always_on.ps1 -Undo
#>
param([switch]$Undo)

if ($Undo) {
    powercfg /change standby-timeout-ac 30
    powercfg /change hibernate-timeout-ac 180
    powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 1   # lid close = sleep
    powercfg /setactive SCHEME_CURRENT
    Write-Host "Restored: sleeps after 30 min on AC, lid close sleeps."
    exit
}

powercfg /change standby-timeout-ac 0        # never sleep on AC
powercfg /change hibernate-timeout-ac 0      # never hibernate on AC
powercfg /change monitor-timeout-ac 10       # screen may still turn off
powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0       # lid close = do nothing
powercfg /setactive SCHEME_CURRENT

Write-Host "Done. On AC power the laptop no longer sleeps, even with the lid closed."
Write-Host "Tips: cap battery charge at ~80% in your laptop vendor's app, and don't"
Write-Host "run it lid-closed inside a bag or on a bed: it needs airflow."
