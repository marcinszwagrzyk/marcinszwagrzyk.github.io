# Runs tools/check-routes.html in headless Edge and prints the report.
#
#     powershell -ExecutionPolicy Bypass -File tools/check-routes.ps1

$ErrorActionPreference = 'Stop'
$page = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'check-routes.html'

$edge = @("$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
          "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
          "$env:ProgramFiles\Google\Chrome\Application\chrome.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $edge) { throw 'no Edge/Chrome found' }

$url = 'file:///' + ($page -replace '\\', '/')
$dom = & $edge --headless=new --disable-gpu --no-sandbox --virtual-time-budget=30000 --dump-dom $url 2>$null

$m = [regex]::Match(($dom -join "`n"), '(?s)<pre id="out">(.*?)</pre>')
if (-not $m.Success) { throw "no report in DOM`n$dom" }
[Net.WebUtility]::HtmlDecode($m.Groups[1].Value)
