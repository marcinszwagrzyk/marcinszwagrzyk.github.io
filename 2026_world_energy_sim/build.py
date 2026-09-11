"""
Bundle the multi-file project into one self-contained HTML page.

The repo keeps the app split across css/ and js/ for editing; the published
page has to be a single file with no external requests (no CDN, no tiles),
so this inlines everything in the order index.html loads it.

    python build.py        ->  dist/world-oil-routes.html
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).parent
DIST = ROOT / 'dist'
OUT = DIST / 'world-oil-routes.html'

html = (ROOT / 'index.html').read_text(encoding='utf-8')

# body markup, minus the tags we replace with inlined content
body = html.split('<body>', 1)[1].split('</body>', 1)[0]
body = re.sub(r'\s*<script src="[^"]+"></script>', '', body)

css = (ROOT / 'css' / 'main.css').read_text(encoding='utf-8')

# same order as the <script> tags in index.html - data first, then engine, view, ui, app
scripts = [
    'js/data/world-shapes.js',
    'js/data/world.js',
    'js/data/routes.js',
    'js/data/sea-detours.js',
    'js/data/scenarios.js',
    'js/engine.js',
    'js/mapview.js',
    'js/ui.js',
    'js/app.js',
]
js = '\n\n'.join(
    '/* ===== %s ===== */\n%s' % (s, (ROOT / s).read_text(encoding='utf-8'))
    for s in scripts
)

title = re.search(r'<title>(.*?)</title>', html).group(1)

# No doctype/html/head/body: the artifact host wraps the page itself.
page = (
    '<title>%s</title>\n'
    '<style>\n%s\n</style>\n'
    '%s\n'
    '<script>\n%s\n</script>\n'
) % (title, css, body.strip(), js)

DIST.mkdir(exist_ok=True)
OUT.write_text(page, encoding='utf-8')

print('%s  %.0f KB' % (OUT, OUT.stat().st_size / 1024))
for s in scripts:
    print('   %-28s %6.1f KB' % (s, (ROOT / s).stat().st_size / 1024))
print('   %-28s %6.1f KB' % ('css/main.css', (ROOT / 'css' / 'main.css').stat().st_size / 1024))
assert '<script src=' not in page and 'unpkg' not in page, 'external reference left in bundle'
assert '<!DOCTYPE' not in page and '<body' not in page, 'wrapper tags left in bundle'
print('\nself-contained: no external requests')
