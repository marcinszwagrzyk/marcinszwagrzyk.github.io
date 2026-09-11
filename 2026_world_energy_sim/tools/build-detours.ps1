# Regenerate js/data/sea-detours.js by running the sea router in headless Edge.
#
#     powershell -ExecutionPolicy Bypass -File tools/build-detours.ps1

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$page = Join-Path $here 'build-detours.html'
$dest = Join-Path (Split-Path -Parent $here) 'js\data\sea-detours.js'

$edge = @("$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
          "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
          "$env:ProgramFiles\Google\Chrome\Application\chrome.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $edge) { throw 'no Edge/Chrome found' }

$dump = Join-Path $env:TEMP 'wes-detours-dom.txt'
$url = 'file:///' + ($page -replace '\\', '/')

$p = Start-Process -FilePath $edge -NoNewWindow -Wait -PassThru -RedirectStandardOutput $dump `
  -ArgumentList '--headless=new', '--disable-gpu', '--no-sandbox',
                "--user-data-dir=$env:TEMP\wes-edge-profile",
                '--virtual-time-budget=600000', '--dump-dom', $url
if ($p.ExitCode -ne 0) { throw "browser exited $($p.ExitCode)" }

$dom = Get-Content $dump -Raw
$m = [regex]::Match($dom, '(?s)<pre id="out">(.*?)</pre>')
if (-not $m.Success) { throw "no output in DOM (page threw?)`n$dom" }
$text = [Net.WebUtility]::HtmlDecode($m.Groups[1].Value)

$parts = $text -split '===FILE===', 2
$report = ($parts[0] -replace '===REPORT===', '').Trim()
if ($parts.Count -lt 2) { throw "generator produced no file`n$report" }

[IO.File]::WriteAllText($dest, $parts[1].TrimStart("`r", "`n"), (New-Object Text.UTF8Encoding $false))
$report
"{0}  {1:N1} KB" -f $dest, ((Get-Item $dest).Length / 1KB)
