# PowerShell port of build.py - this machine has no Python installed.
# Bundles the multi-file project into one self-contained HTML page:
#
#     powershell -ExecutionPolicy Bypass -File build.ps1   ->  dist/world-oil-routes.html

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$dist = Join-Path $root 'dist'
$out  = Join-Path $dist 'world-oil-routes.html'

$html = Get-Content (Join-Path $root 'index.html') -Raw -Encoding UTF8

# body markup, minus the tags we replace with inlined content
$body = $html.Split([string[]]@('<body>'), 2, 'None')[1]
$body = $body.Split([string[]]@('</body>'), 2, 'None')[0]
$body = [regex]::Replace($body, '\s*<script src="[^"]+"></script>', '')

$css = Get-Content (Join-Path $root 'css\main.css') -Raw -Encoding UTF8

# same order as the <script> tags in index.html - data first, then engine, view, ui, app
$scripts = @(
  'js/data/world-shapes.js',
  'js/data/world.js',
  'js/data/routes.js',
  'js/data/sea-detours.js',
  'js/data/scenarios.js',
  'js/engine.js',
  'js/mapview.js',
  'js/ui.js',
  'js/app.js'
)

$parts = foreach ($s in $scripts) {
  $src = Get-Content (Join-Path $root ($s -replace '/', '\')) -Raw -Encoding UTF8
  "/* ===== $s ===== */`n$src"
}
$js = $parts -join "`n`n"

$title = [regex]::Match($html, '<title>(.*?)</title>').Groups[1].Value

# No doctype/html/head/body: the artifact host wraps the page itself.
$page = "<title>$title</title>`n<style>`n$css`n</style>`n" + $body.Trim() + "`n<script>`n$js`n</script>`n"

if (-not (Test-Path $dist)) { New-Item -ItemType Directory $dist | Out-Null }
[IO.File]::WriteAllText($out, $page, (New-Object Text.UTF8Encoding $false))

"{0}  {1:N0} KB" -f $out, ((Get-Item $out).Length / 1KB)
foreach ($s in $scripts) {
  "   {0,-28} {1,6:N1} KB" -f $s, ((Get-Item (Join-Path $root ($s -replace '/', '\'))).Length / 1KB)
}
"   {0,-28} {1,6:N1} KB" -f 'css/main.css', ((Get-Item (Join-Path $root 'css\main.css')).Length / 1KB)

if ($page -match '<script src=' -or $page -match 'unpkg') { throw 'external reference left in bundle' }
if ($page -match '<!DOCTYPE' -or $page -match '<body')     { throw 'wrapper tags left in bundle' }
"`nself-contained: no external requests"
