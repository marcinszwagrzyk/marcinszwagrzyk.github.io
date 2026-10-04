#!/bin/bash
# Bieg odporny na padniecia: model raz, potem obszar po obszarze w osobnych
# procesach (stala pamiec), na koncu zlozenie + mozaiki + notatnik.
# Mozna puscic ponownie - obszary juz policzone (out/rows/*.json) sa pomijane.
set -u
PY=/c/Users/marci/anaconda3/python.exe
export PYTHONIOENCODING=utf-8
cd /c/git/geo-toolbox/GeoProjects/2026_datacenter_stages

# Model: trenujemy, gdy go nie ma ALBO gdy zapisany jest podejrzanie ubogi.
# Powod: po biegu, ktory padl w trakcie, na dysku zostal model nauczony na
# JEDNYM obszarze (8429 probek, klasa WODA: 8 sztuk) - a warunek "plik jest,
# wiec nie trenuje" kazal go uzyc do wszystkich dwunastu obszarow. Sam fakt
# istnienia pliku nic nie mowi o tym, czy model jest uzyteczny.
NEED=1
if [ -f out/model.joblib ] && [ "${1:-}" != "--retrain" ]; then
  NEED=$($PY -c "
import joblib
try:
    r = joblib.load('out/model.joblib')['report']
    print(0 if r['n_train'] + r['n_test'] >= 40000 else 1)
except Exception:
    print(1)
")
fi
if [ "$NEED" != "0" ]; then
  echo "=== TRENING $(date +%H:%M)"
  $PY -u run.py --train-only || exit 1
  $PY -c "
import joblib
r = joblib.load('out/model.joblib')['report']
print(f\"    model: {r['n_train']+r['n_test']} probek, dokladnosc {r['accuracy']*100:.1f}%\")
print('    klasy:', r['counts'])
"
else
  echo "=== model z dysku wystarczajacy, pomijam trening"
fi

IDS=$($PY -c "import json;print(' '.join(s['id'] for s in json.load(open('sites.json',encoding='utf-8'))['sites']))")
for id in $IDS; do
  if [ -f "out/rows/$id.json" ]; then echo "--- $id: juz policzony, pomijam"; continue; fi
  echo "=== $id  $(date +%H:%M)"
  $PY -u run.py --use-model "$id" 2>&1 | grep -E "rdzen|stan na|BLAD|BŁĄD|brak|pomijam" || true
done

echo "=== SKLADANIE $(date +%H:%M)"
$PY -u run.py --assemble
echo "=== MOZAIKI $(date +%H:%M)"
$PY -u mozaiki.py > /dev/null 2>&1 && echo "mozaiki: $(ls out/mozaiki/*.png | wc -l) plikow"
echo "=== NOTATNIK $(date +%H:%M)"
$PY -u build_notebook.py 2>&1 | tail -2
echo "=== KONIEC $(date +%H:%M)"
