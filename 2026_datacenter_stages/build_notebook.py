# -*- coding: utf-8 -*-
"""Składa analiza.ipynb i wykonuje go, żeby otwierał się już z obrazkami.

    python build_notebook.py

Notatnik jest generowany, a nie pisany ręcznie, z jednego powodu: komórki
muszą zgadzać się z tym, co naprawdę zapisał run.py. Jak zmieni się lista
obszarów albo nazwy pól, notatnik odbuduje się zgodnie z nimi.
"""
from __future__ import annotations

import os
import sys

import nbformat as nbf
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

NB = "analiza.ipynb"


def md(t):
    return new_markdown_cell(t.strip("\n"))


def code(t):
    return new_code_cell(t.strip("\n"))


def cells():
    c = []

    c.append(md("""
# Etapy budowy kampusów data center w USA

Szereg czasowy **Sentinel-2 L2A** z Microsoft Planetary Computer, kompozyty
półroczne 2018–2025, klasyfikacja pokrycia terenu i maszyna etapów.

Pięć etapów, w kolejności procesu budowy:

| etap | nazwa | po czym rozpoznany |
|---|---|---|
| 0 | PRZED BUDOWĄ | nie spełnia warunków etapu 1+ |
| 1 | ROBOTY ZIEMNE | przyrost gołego gruntu względem **własnego** poziomu wyjściowego obszaru |
| 2 | ZABUDOWA ROŚNIE | zabudowa potwierdzona ≥ 15% celu kampusu |
| 3 | BRYŁA ZAMKNIĘTA | zabudowa potwierdzona ≥ 65% celu kampusu |
| 4 | ZIELEŃ URZĄDZONA | bryła zamknięta + **powrót** zieleni w kołnierzu wokół hal |

Notatnik tylko **rysuje** to, co policzył `run.py` (`out/maps/*.npz`,
`out/*.csv`, `out/model.joblib`). Nie trenuje modelu od nowa, więc pokazuje
dokładnie te liczby, które poszły do raportu.
"""))

    c.append(code("""
%matplotlib inline
import json, os, warnings
warnings.filterwarnings("ignore")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import config as C, labels as L, stages as S, viz, plot

plt.rcParams.update({"figure.dpi": 110, "savefig.bbox": "tight",
                     "axes.titlesize": 10, "font.size": 9})

df  = pd.read_csv(os.path.join(C.OUT_DIR, "etapy.csv"))
dfl = pd.read_csv(os.path.join(C.OUT_DIR, "przebieg.csv"))
EPOCHS = sorted(dfl.epoch.unique())
print(f"obszarów: {len(df)}   epok: {len(EPOCHS)}   ({EPOCHS[0]} .. {EPOCHS[-1]})")
"""))

    # ---------------------------------------------------------------- 1. lista
    c.append(md("""
---
## 1. Skąd się wzięła lista dziesięciu obszarów

Nie z pamięci — z pomiaru. `discover.py` pobiera z OpenStreetMap wszystkie
obiekty otagowane `telecom=data_center` / `building=data_center` (w CONUS:
**1730 hal**), skupia je w kampusy i wybiera dziesięć największych
po **powierzchni hal**.

To jest ranking **mierzalny**, a nie ranking po nakładach — tego drugiego nie
mam skąd wziąć w sposób weryfikowalny.

Dlaczego to ma znaczenie: pierwsza wersja listy miała dla Ashburn punkt
`39.0437, -77.4875`. W kwadracie o półboku 1,5 km wokół niego jest **0,0% hal**
(zabudowa zajmuje 9,8%, ale to domy jednorodzinne). Punkt leżał w dzielnicy
mieszkaniowej, kilka kilometrów od Data Center Alley — a potok policzył wtedy
*„PRZED BUDOWĄ, zabudowa 1,6%"* dla najgęstszego skupiska data center na
świecie. Wynik był poprawny dla złego kadru.
"""))

    c.append(code("""
meta = json.load(open("sites.json", encoding="utf-8"))
print(f"sites.json wygenerowany {meta['generated']}  ·  {meta['ranking']}")

s = pd.DataFrame(meta["sites"])
s["pow_ha"] = s.hall_area_m2 / 1e4
s["cel_%"]  = s.target_built_frac * 100
if "place" not in s.columns:
    s["place"] = "?"
show = s[["id", "place", "halls", "pow_ha", "cel_%", "radius_m",
          "under_constr", "lat", "lon"]]
show.columns = ["obszar", "gdzie", "hal", "pow. hal [ha]", "cel [%AOI]",
                "R [m]", "w budowie", "lat", "lon"]
show.round(2)
"""))

    c.append(md("""
`cel [%AOI]` to powierzchnia hal z OSM podzielona przez powierzchnię kadru.
Potok porównuje do niej udział zabudowy potwierdzonej z Sentinela — dzięki temu
nie trzeba jednego progu dla kampusu gęstego i rozrzuconego.

**Cel liczymy wyłącznie z obiektów mających tag `building`.** `telecom=data_center`
bywa w OSM przypięty do granicy terenu, nie do hali: na kampusie Google w Berkeley
County jeden taki obiekt ma 77,2 ha (`landuse=industrial`, bez tagu `building`),
podczas gdy wszystkie rzeczywiste hale razem — 19,7 ha. Liczenie działki jako hali
zawyżało cel pięciokrotnie i czyniło próg „bryła zamknięta" nieosiągalnym.

Kolumna `gdzie` pochodzi z geokodowania wstecznego współrzędnych (Nominatim).
Część kampusów nie ma w OSM ani `name`, ani `operator` — skupisko 40 hal
w Taylor County w Teksasie nie ma ich w żadnym z 40 obiektów. Operatora
musiałbym w takim wypadku zmyślić, więc go tam nie ma; położenie natomiast
wynika ze współrzędnych i jest sprawdzalne.
"""))

    # ---------------------------------------------------------------- 2. mapa poglądowa
    c.append(md("""
---
## 2. Wszystkie obszary: „przed" i „teraz"

Barwy naturalne Sentinela. To mapa poglądowa całego zadania — jednym spojrzeniem
widać, które obszary się zmieniły, **niezależnie od tego, co orzekł model**.
Jeśli górny i dolny obrazek są identyczne, a potok mówi „BRYŁA ZAMKNIĘTA", to
znaczy, że kampus stał już w 2018.
"""))
    c.append(code("""
sites = [sd for sd in C.SITES if sd["id"] in set(df.id)]
fig = viz.overview(sites, EPOCHS[0], EPOCHS[-1], ncols=5)
plt.show()
"""))

    # ---------------------------------------------------------------- 3. mapa etapów
    c.append(md("""
---
## 3. Mapa etapów: kto kiedy w który etap wszedł

Wiersz = obszar, kolumna = epoka, kolor = etap. Przebieg jest **niemalejący** —
budowa się nie cofa, a jedna epoka z chmurami bez tej zapadki wyrzucałaby obszar
z etapu 3 na 1.
"""))
    c.append(code("""
plot.timeline(dfl, os.path.join(C.OUT_DIR, "etapy.png"))
from IPython.display import Image, display
display(Image(os.path.join(C.OUT_DIR, "etapy.png")))
"""))

    # ---------------------------------------------------------------- 4. tabela
    c.append(md("""
---
## 4. Na jakim etapie jest która inwestycja

`postęp` = zabudowa potwierdzona / cel z OSM. Mówi więcej niż sam udział
zabudowy, bo uwzględnia, jak gęsty jest dany kampus.

**Jak czytać postęp znacznie powyżej 100%.** Mianownikiem jest powierzchnia hal
zmapowanych w OSM, a nie rzeczywista powierzchnia kampusu. Postęp rzędu 150–200%
znaczy więc jedno z dwóch i trzeba to rozstrzygnąć, a nie zgadywać:

* **OSM jest niekompletny** — stoją hale, których nikt nie zmapował. Wtedy etap
  jest poprawny, a zaniżony jest cel.
* **Potok przesadza** — bierze jasny grunt za dach. Dotyczy zwłaszcza obszarów
  suchych, gdzie goła ziemia jest jasna, a pomyłka GRUNT → DACH wynosi 10,5%.

Rozstrzyga to **sekcja 7b**: jeśli celność (udział potwierdzonej zabudowy
leżącej pod obrysem budynku) jest wysoka, to po prostu brakuje obrysów w OSM;
jeśli niska — potok dolicza grunt. Z tego samego powodu kolumna `cel` jest
w tabeli obok `postępu`: bez niej postęp jest liczbą bez mianownika.
"""))
    c.append(code("""
t = df.copy()
t["etap"] = t.stage.map(S.STAGE_SHORT)
t["postęp [%]"] = (t.progress * 100).round(0)
t["zabudowa [%]"] = (t.built_frac * 100).round(1)
t["cel [%]"] = (t.target_built_frac * 100).round(1)
t["grunt [%]"] = (t.bare_frac * 100).round(1)
t["zieleń [%]"] = (t.veg_frac * 100).round(1)
t["kołnierz [%]"] = (t.collar_green * 100).round(0)
gdzie = {x["id"]: x.get("place", "?") for x in C.SITES}
t["gdzie"] = t.id.map(gdzie)
cols = ["id", "gdzie", "etap", "since", "postęp [%]", "zabudowa [%]", "cel [%]",
        "grunt [%]", "zieleń [%]", "kołnierz [%]"]
t[cols].rename(columns={"id": "obszar", "since": "od"}) \\
    .sort_values("etap", ascending=False)
"""))

    c.append(md("""
### Daty wejścia w kolejne etapy
"""))
    c.append(code("""
d = df[["id", "t_earthworks", "t_structures", "t_mature", "t_green"]].copy()
d.columns = ["obszar", "roboty ziemne", "zabudowa rośnie",
             "bryła zamknięta", "zieleń urządzona"]
d.fillna("—")
"""))

    # --------------------------------------------- 4b. obszary odniesienia
    c.append(md("""
---
## 4b. Obszary odniesienia: udokumentowana oś czasu vs wynik potoku

Potok sam o sobie mówi, na jakim etapie jest inwestycja. Żeby to sprawdzić,
potrzebny jest obszar, o którym wiadomo **z zewnątrz**, kiedy co się na nim
działo. Dwa takie obszary są w `sites.json` oznaczone `control=True`.

**Uczciwie o doborze:** wybierałem je kryterium „OSM nie zna tu ani jednej hali
otagowanej `building=construction`", zakładając, że to wskaże kampusy ukończone.
Research pokazał, że założenie było błędne — oba są placami budowy w latach
2024–2026. Tag `building=construction` jest w OSM rzadki i nie świadczy o stanie
inwestycji. Nie są to więc kampusy ukończone przed szeregiem, tylko obiekty
o **udokumentowanej osi czasu** — co do sprawdzenia potoku nadaje się nawet
lepiej, bo zamiast pytać „czy wykres jest płaski", można porównać **wykryte daty
z ogłoszonymi**.

**Czym te daty są, a czym nie:** pochodzą z doniesień branżowych i prasowych,
nie z dokumentacji budowy. Mówią, kiedy coś ogłoszono i kiedy planowano, co nie
musi się pokrywać z tym, kiedy wjechały koparki. To punkt odniesienia rzędu
kwartału — dlatego zgodność oceniamy w epokach półrocznych, nie w datach
dziennych.
"""))
    c.append(code("""
import narracja
from IPython.display import Markdown, display
for sid in [s["id"] for s in C.SITES if s.get("control")]:
    display(Markdown(narracja.markdown(sid)))
"""))

    # ---------------------------------------------------------------- 5. per site
    c.append(md("""
---
## 5. Każdy obszar osobno

Dla każdego obszaru cztery rzeczy:

1. **barwy naturalne** przez wszystkie epoki — co widać gołym okiem,
2. **klasyfikacja** przez wszystkie epoki — co z tego zrobił model,
3. **mapa „kiedy pojawiła się zabudowa"** — kolor mówi, w której epoce
   dana hala została potwierdzona,
4. **krzywe** udziałów klas + schodki etapu.

Punkt 4 jest najważniejszy do oceny wiarygodności: widać po nim, czy etap
wynika z wyraźnej zmiany w danych, czy z ledwie przekroczonego progu.
"""))
    c.append(code("""
from IPython.display import Markdown, display

def pokaz(site_id):
    sd = next(x for x in C.SITES if x["id"] == site_id)
    r = df[df.id == site_id].iloc[0]
    display(Markdown(
        f"### {site_id} — {sd.get('place', '?')}\\n"
        f"**{sd['name']}**  ·  `{sd['lat']:.4f}, {sd['lon']:.4f}`  ·  "
        f"R = {sd['radius_m']} m  ·  cel {sd.get('target_built_frac', 0)*100:.1f}% AOI\\n\\n"
        f"Stan na {r.epoch_last}: **{r.stage_name}** (od {r.since})  ·  "
        f"zabudowa {r.built_frac*100:.1f}% = {r.progress*100:.0f}% celu  ·  "
        f"grunt {r.bare_frac*100:.1f}%"))

    viz.strip(sd, EPOCHS, kind="rgb", title="barwy naturalne")
    plt.show()
    viz.strip(sd, EPOCHS, kind="cls", title="klasyfikacja i etap")
    plt.show()
    viz.built_growth(sd)
    plt.show()
    plot.site_curves(dfl, site_id, os.path.join(C.OUT_DIR, "krzywe", f"{site_id}.png"))
    display(Image(os.path.join(C.OUT_DIR, "krzywe", f"{site_id}.png")))
"""))

    c.append(code("""
IDS = list(df.sort_values("stage", ascending=False).id)
pokaz(IDS[0])
"""))
    c.append(code("""
for sid in IDS[1:]:
    pokaz(sid)
"""))

    # ---------------------------------------------------------------- 6. kołnierz
    c.append(md("""
---
## 6. Zieleń urządzona — dowód, nie założenie

Ostatni etap budowy to zieleń wokół hal. Ale **przed** budową cały obszar też
jest zielony — pole albo las. Sama obecność zieleni nie odróżnia trawnika od
nietkniętej łąki; odróżnia je **powrót**: zieleń musi najpierw zniknąć (plac
budowy, składowisko, droga technologiczna), a potem wrócić.

Dlatego mierzymy ją w **kołnierzu wokół potwierdzonej zabudowy** (dylatacja
maski hal o 120 m), a nie w pierścieniu o stałym promieniu — i wymagamy
przyrostu względem minimum, jakie ten kołnierz osiągnął w czasie budowy.
"""))
    c.append(code("""
for sid in IDS[:3]:
    sd = next(x for x in C.SITES if x["id"] == sid)
    try:
        viz.collar_view(sd)
        plt.show()
    except Exception as e:
        print(f"{sid}: {type(e).__name__}: {e}")
"""))

    # ---------------------------------------------------------------- 7. model
    c.append(md("""
---
## 7. Ile wart jest klasyfikator

Model: las losowy na cechach spektralnych, uczony **raz** na próbkach ze
wszystkich obszarów — jeden model dla wszystkich, żeby „udział zabudowy 25%"
znaczył to samo na każdym kampusie.

Pola treningowe pochodzą z danych publicznych: **ESA WorldCover 10 m** (klasy
pokrycia) i **OSM** (obrysy budynków i nawierzchni), pobierane z kadru 2×
szerszego **z wyłączeniem samego obszaru inwestycji** — inaczej model uczyłby
się stanu kampusu z 2021 i potem „rozpoznawał" to, co już widział.
"""))
    c.append(code("""
import joblib
m = joblib.load(os.path.join(C.OUT_DIR, "model.joblib"))
rep = m["report"]
print(f"próbek treningowych: {rep['n_train']}   sprawdzających: {rep['n_test']}")
print("liczebność klas:", rep["counts"])
viz.confusion(rep)
plt.show()
viz.importances(rep)
plt.show()
print(f"\\nGRUNT wzięty za DACH: {rep.get('bare_as_roof', float('nan'))*100:.1f}%")
"""))

    c.append(md("""
Cała pomyłka siedzi między **GRUNT / DACH / ASFALT** — zieleń i woda są
rozdzielane bezbłędnie. To jest oczekiwane i nieusuwalne spektralnie: świeży
jasny beton, blacha i przesuszona jasna glina mają w sześciu pasmach Sentinela
podpisy, które na siebie zachodzą.

Dlatego **zabudowa nie jest brana z jednej klasyfikacji**. Piksel wchodzi do
zabudowy po trzech filtrach, z których żaden nie jest spektralny:

1. **pewność** — `p(DACH) ≥ 0.60`; fałszywy alarm jest tu gorszy niż spóźnienie
   o jedną epokę,
2. **spójność przestrzenna** — skupisko ≥ 25 pikseli (0,25 ha); hala ma
   100–500 pikseli, pojedynczy jasny piksel to szum,
3. **trwałość w czasie** — i to jest filtr rozstrzygający:
   **jasna glina wysycha i moknie, budynek nie znika.** Klasa DACH musi się
   utrzymać w dwóch kolejnych epokach, i od tego momentu piksel pozostaje
   zabudową.

Poniżej widać, ile ten filtr zdejmuje: `roof_raw` to surowa klasa DACH z jednej
epoki, `built` to zabudowa potwierdzona.
"""))
    c.append(code("""
fig, ax = plt.subplots(figsize=(9, 4))
for sid in IDS:
    d = dfl[dfl.id == sid].sort_values("epoch")
    ax.plot(d.epoch, (d.roof_raw - d.built) * 100, marker="o", ms=2.5,
            lw=1, alpha=0.75, label=sid[:22])
ax.set_ylabel("roof_raw − built  [punkty proc. AOI]")
ax.set_title("Ile zdejmują filtry ostrożności (surowa klasa DACH minus zabudowa potwierdzona)")
ax.tick_params(axis="x", rotation=90, labelsize=7)
ax.grid(alpha=0.3)
ax.axhline(0, color="k", lw=0.6)
ax.legend(fontsize=6.5, ncol=2, frameon=False)
plt.show()
"""))

    # ------------------------------------------------- 7b. kontrola niezależna
    c.append(md("""
---
## 7b. Kontrola niezależna: czy „zabudowa potwierdzona" to naprawdę budynki

Potok sam o sobie mówi, że zabudowa jest „potwierdzona". To twierdzenie trzeba
sprawdzić czymś **spoza potoku** — a mamy czym: obrysami budynków z OSM, których
klasyfikator dla tego obszaru nie widział (pola treningowe pochodzą z otoczenia,
z wyłączeniem samego kampusu).

Jest to potrzebne właśnie tutaj, bo pomyłka **GRUNT → DACH wynosi 10,5%** w
pojedynczej klasyfikacji, a **zapadka** sprawia, że raz potwierdzona zabudowa już
nie znika. Fałszywie potwierdzony płat suchej, jasnej gliny zostałby w wyniku na
zawsze.

* **celność** — ile z potwierdzonej zabudowy leży pod obrysem budynku.
  Niska celność = potok bierze grunt za dach.
* **pokrycie** — ile z obrysów hal potok zdążył potwierdzić. Niskie pokrycie
  bywa **poprawne**: OSM zna hale, których jeszcze nie ma, bo są otagowane jako
  w budowie albo dopiero powstają. Dlatego pokrycie czytamy razem z etapem.
"""))
    c.append(code("""
rows = []
for sid in IDS:
    sd = next(x for x in C.SITES if x["id"] == sid)
    r = viz.osm_check(sd)
    if r:
        r["obszar"] = sid
        r["etap"] = S.STAGE_SHORT[int(df[df.id == sid].iloc[0].stage)]
        rows.append(r)
chk = pd.DataFrame(rows)
if len(chk):
    chk["celność [%]"] = (chk.celnosc * 100).round(0)
    chk["pokrycie [%]"] = (chk.pokrycie * 100).round(0)
    display(chk[["obszar", "etap", "epoch", "ref_px", "built_px",
                 "celność [%]", "pokrycie [%]"]])
    print("mediana celnosci: {:.0f}%".format(chk.celnosc.median()*100))
else:
    print("brak obrysów OSM do porównania")
"""))

    # ---------------------------------------------------------------- 8. offset
    c.append(md("""
---
## 8. Kontrola: offset BOA, czyli uskok, którego nie ma

Sentinel-2 od *processing baseline* 04.00 (styczeń 2022) ma w metadanych
`BOA_ADD_OFFSET = -1000`. Zmierzone nad Ashburn:

```
2018 → 02.12    2020 → 02.12    2021 → 03.00    2022 → 04.00    2024 → 05.11
```

Bez poprawki **wszystkie** wskaźniki dostają skok dokładnie na przełomie
2021/2022, a potok ogłasza „początek budowy" na dziesięciu obszarach w tym
samym kwartale. `mpc.py` ładuje sceny w dwóch grupach według baseline i odejmuje
offset tylko tam, gdzie należy.

Sprawdzenie: mediana NDVI w obszarach przed budową powinna przechodzić granicę
2021/2022 **bez skoku** większego niż zwykła zmienność międzyroczna.
"""))
    c.append(code("""
fig, ax = plt.subplots(figsize=(9, 3.8))
h1 = [e for e in EPOCHS if e.endswith("H1")]
for sid in IDS:
    d = dfl[(dfl.id == sid) & (dfl.epoch.isin(h1))].sort_values("epoch")
    ax.plot(d.epoch, d.veg * 100, marker="o", ms=3, lw=1, alpha=0.8,
            label=sid[:22])
ax.axvline(h1.index("2022H1") if "2022H1" in h1 else 0, color="#b03030",
           ls="--", lw=1.2)
ax.text(h1.index("2022H1") if "2022H1" in h1 else 0, ax.get_ylim()[1] * 0.96,
        "  granica baseline 04.00", color="#b03030", fontsize=8, va="top")
ax.set_ylabel("udział klasy ZIELEŃ [%]")
ax.set_title("Udział zieleni, epoki H1 — brak uskoku na granicy 2021/2022")
ax.tick_params(axis="x", rotation=90, labelsize=8)
ax.grid(alpha=0.3)
ax.legend(fontsize=6.5, ncol=2, frameon=False)
plt.show()
"""))

    # ---------------------------------------------------------------- 9. zastrzeżenia
    c.append(md("""
---
## 9. Czego ta analiza nie mówi

* **Lista nie jest rankingiem po nakładach.** Jest rankingiem po powierzchni hal
  zmapowanych w OSM. Kompletność OSM jest nierówna — kampus niezmapowany nie
  istnieje w tym rankingu.
* **Cel z OSM to stan dzisiejszy**, w tym hale otagowane
  `building=construction`. Dla kampusu w budowie jest to zaleta (cel ≈ stan
  docelowy), ale jeśli OSM jest niekompletny, cel jest zaniżony i „bryła
  zamknięta" przychodzi za wcześnie.
* **Zapadka etapów** zakłada, że hal się nie rozbiera.
* **Etykiety WorldCover są z 2021**, a model stosujemy do epok 2018–2025.
  Założenie: podpis spektralny materiału nie zmienia się w czasie. Dla odbicia
  znormalizowanego i kompozytów z tej samej pory roku jest rozsądne.
* **Kampus ≠ działka ewidencyjna.** Skupienie hal w promieniu 900 m to
  przybliżenie; kampus bardzo rozciągnięty może zostać rozcięty na dwa, a dwa
  sąsiadujące — zlane w jeden.
* **Jeśli kadr nie obejmuje właściwej działki, etap nie znaczy nic.** Dlatego
  sekcja 2 jest w tym notatniku pierwsza: obrazki „przed/teraz" są jedyną
  kontrolą, która wyłapuje ten błąd.
"""))
    return c


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    os.chdir(here)

    nb = new_notebook(cells=cells())
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python",
                                 "name": "python3"}
    nbf.write(nb, NB)
    print(f"zapisano {NB} ({len(nb.cells)} komórek)")

    if "--no-exec" in sys.argv:
        return 0

    need = [os.path.join("out", "etapy.csv"), os.path.join("out", "model.joblib")]
    miss = [p for p in need if not os.path.exists(p)]
    if miss:
        print(f"\nnie wykonuję — brak {miss}. Najpierw: python run.py")
        return 1

    print("wykonuję notatnik (to potrwa — rysuje kilkaset obrazków)...")
    from nbclient import NotebookClient
    nb = nbf.read(NB, as_version=4)
    NotebookClient(nb, timeout=2400, kernel_name="python3",
                   resources={"metadata": {"path": here}}).execute()
    nbf.write(nb, NB)

    nerr = sum(1 for cl in nb.cells for o in cl.get("outputs", [])
               if o.get("output_type") == "error")
    nimg = sum(1 for cl in nb.cells for o in cl.get("outputs", [])
               if "image/png" in (o.get("data") or {}))
    print(f"gotowe: {nimg} obrazków, {nerr} błędów -> {NB}")
    return 1 if nerr else 0


if __name__ == "__main__":
    sys.exit(main())
