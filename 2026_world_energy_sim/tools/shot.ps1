# Screenshot the app in headless Edge, for eyeballing the map without a browser.
#
#     powershell -ExecutionPolicy Bypass -File tools/shot.ps1 [-Out shot.png] [-Wait 4000]
#
# -Setup is JS evaluated once the app exists, e.g. to park the view somewhere:
#     -Setup "app.view.cx=wxOf(100); app.view.cy=wyOf(10); app.view.zoom=3.5"

param(
  [string]$Out = "$env:TEMP\wes-shot.png",
  [int]$Width = 1680,
  [int]$Height = 1000,
  [int]$Wait = 4000,
  [string]$Setup = ''
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here

$edge = @("$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
          "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
          "$env:ProgramFiles\Google\Chrome\Application\chrome.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $edge) { throw 'no Edge/Chrome found' }

# a wrapper page so the shot can steer the view before the capture
$page = Join-Path $env:TEMP 'wes-shot.html'
$body = @"
<!DOCTYPE html><meta charset="utf-8"><title>shot</title>
<style>html,body{margin:0;height:100%}iframe{border:0;width:100vw;height:100vh}</style>
<iframe id="f" src="$(($root -replace '\\','/'))/index.html"></iframe>
<script>
document.getElementById('f').addEventListener('load', () => {
  const w = document.getElementById('f').contentWindow;
  const tick = () => {
    if (!w.app) return setTimeout(tick, 50);
    $Setup
    w.app.view.baseDirty = true;
  };
  tick();
});
</script>
"@
[IO.File]::WriteAllText($page, $body, (New-Object Text.UTF8Encoding $false))

if (Test-Path $Out) { Remove-Item $Out -Force }
$p = Start-Process -FilePath $edge -NoNewWindow -Wait -PassThru `
  -ArgumentList '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
                '--allow-file-access-from-files',
                "--user-data-dir=$env:TEMP\wes-edge-profile",
                "--window-size=$Width,$Height",
                "--virtual-time-budget=$Wait",
                "--screenshot=$Out",
                ('file:///' + ($page -replace '\\', '/'))
if (-not (Test-Path $Out)) { throw "no screenshot (exit $($p.ExitCode))" }
"{0}  {1:N0} KB" -f $Out, ((Get-Item $Out).Length / 1KB)
