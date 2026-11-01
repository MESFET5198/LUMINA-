param([int]$X, [int]$Y, [string]$Proc = "Lumina Studio")
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
}
"@
$p = Get-Process | Where-Object { $_.MainWindowTitle -and $_.ProcessName -like "*$Proc*" } | Select-Object -First 1
if ($p) { [Win]::SetForegroundWindow($p.MainWindowHandle) | Out-Null; Start-Sleep -Milliseconds 400 }
[Win]::SetCursorPos($X, $Y) | Out-Null
Start-Sleep -Milliseconds 150
[Win]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero)   # left down
Start-Sleep -Milliseconds 60
[Win]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero)   # left up
Write-Output ("clicked " + $X + "," + $Y + " on " + ($(if ($p) { $p.MainWindowTitle } else { "<no window>" })))
