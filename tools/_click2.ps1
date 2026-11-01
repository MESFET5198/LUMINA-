param([int]$X, [int]$Y, [string]$Proc = "Lumina Studio")
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class W2 {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll", SetLastError=true)] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint f, int dx, int dy, uint d, IntPtr e);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
$p = Get-Process | Where-Object { $_.MainWindowTitle -and $_.ProcessName -like "*$Proc*" } | Select-Object -First 1
if (-not $p) { Write-Output "no window"; exit 1 }
$h = $p.MainWindowHandle
if ([W2]::IsIconic($h)) { [W2]::ShowWindow($h, 9) | Out-Null; Start-Sleep -Milliseconds 300 }
[W2]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 500
$fg = [W2]::GetForegroundWindow()
$sb = New-Object System.Text.StringBuilder 256
[W2]::GetWindowTextW($fg, $sb, 256) | Out-Null
$r = New-Object W2+RECT
[W2]::GetWindowRect($h, [ref]$r) | Out-Null
Write-Output ("foreground=" + $sb.ToString() + " | targetRect=" + $r.Left + "," + $r.Top + " - " + $r.Right + "," + $r.Bottom)
[W2]::SetCursorPos($X, $Y) | Out-Null
Start-Sleep -Milliseconds 200
[W2]::mouse_event(0x0002, 0, 0, 0, [IntPtr]::Zero)
Start-Sleep -Milliseconds 80
[W2]::mouse_event(0x0004, 0, 0, 0, [IntPtr]::Zero)
Start-Sleep -Milliseconds 200
$fg2 = [W2]::GetForegroundWindow()
$sb2 = New-Object System.Text.StringBuilder 256
[W2]::GetWindowTextW($fg2, $sb2, 256) | Out-Null
Write-Output ("after click foreground=" + $sb2.ToString() + " | clicked " + $X + "," + $Y)
