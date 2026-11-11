# Stop and remove the HoloDesk autostart task.
Stop-ScheduledTask -TaskName "HoloDesk Daemon" -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName "HoloDesk Daemon" -Confirm:$false -ErrorAction SilentlyContinue
Write-Host "Removed the HoloDesk Daemon task."
