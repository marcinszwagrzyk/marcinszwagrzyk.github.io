# -*- coding: utf-8 -*-
"""Składa synteza.ipynb — wersja do czytania: metoda, case studies, wnioski.

    python build_synteza.py

Różnica wobec analiza.ipynb: tamten jest techniczny i pokazuje WSZYSTKO
(16 epok × 12 obszarów, każda mapa, każda krzywa). Ten jest narracyjny —
jedna sekcja to jedna myśl, z jednym obrazem, który tę myśl niesie.
"""
from __future__ import annotations

import os
import sys

import nbformat as nbf
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

NB = "synteza.ipynb"


def md(t):
    return new_markdown_cell(t.strip("\n"))


def code(t):
    return new_code_cell(t.strip("\n"))


def cells():
    c = []

    # ---------------------------------------------------------------- tytuł
    c.append(md("""
# Etapy budowy kampusów data center w USA
### Szereg czasowy Sentinel-2, 2018–2025, dwanaście obszarów

**Pytanie:** na jakim etapie budowy jest która inwestycja — i czy da się to
orzec z samych zdjęć satelitarnych, bez dostępu do dokumentacji budowy.

**Odpowiedź w jednym zdaniu:** da się rozpoznać *koniec* budowy (bryła
zamknięta) z dokładnością do pół roku, *początek* jest trudniejszy i zależy od
tego, czy teren był wcześniej polem uprawnym, a *rozbudowa dojrzałego kampusu*
jest w tym ujęciu niewidoczna.
"""))

    c.append(code("""
%matplotlib inline
import json, os, warnings
warnings.filterwarnings("ignore")
import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Image, Markdown, display

import config as C, stages as S, viz, plot, narracja

plt.rcParams.update({"figure.dpi": 110, "savefig.bbox": "tight", "font.size": 9})
df  = pd.read_csv(os.path.join(C.OUT_DIR, "etapy.csv"))
dfl = pd.read_csv(os.path.join(C.OUT_DIR, "przebieg.csv"))
EPOCHS = sorted(dfl.epoch.unique())
GDZIE = {x["id"]: x.get("place", "?") for x in C.SITES}
KTORE = {x["id"]: x.get("control", False) for x in C.SITES}
print(f"{len(df)} obszarów · {len(EPOCHS)} epok półrocznych · {EPOCHS[0]}–{EPOCHS[-1]}")
"""))

    # ---------------------------------------------------------------- 1 metoda
    c.append(md("""
---
# 1 · Metoda

**Dane.** Sentinel-2 L2A z Microsoft Planetary Computer, kompozyty medianowe
półroczne (H1 = III–VIII, H2 = IX–II), 10 m, maskowanie chmur przez SCL.
Mediana z półrocza zamiast pojedynczej sceny, bo etap budowy zmienia się
w miesiącach, a chmury w dniach.

**Klasyfikacja.** Las losowy, pięć klas: ZIELEŃ / GRUNT / DACH / ASFALT / WODA.
Pola treningowe z danych publicznych — ESA WorldCover 10 m i obrysy z OSM —
pobierane z otoczenia kampusu **z wyłączeniem samego kampusu**.

**Dach i asfalt są osobno** i to jest sedno ostrożności: droga dojazdowa i plac
manewrowy powstają razem z wykopem, hala rok lub dwa później. Model, który ich
nie rozdziela, ogłasza „stoją budynki" na widok asfaltowego placu budowy.

**Zabudowa potwierdzona** — nie z jednej klasyfikacji, tylko po trzech filtrach,
z których żaden nie jest spektralny:
1. **pewność** `p(DACH) ≥ 0.60`
2. **spójność** skupisko ≥ 50 pikseli (0,5 ha)
3. **trwałość** klasa DACH w 3 kolejnych epokach, potem zapadka

Trzeci jest rozstrzygający: **jasna glina wysycha i moknie, budynek nie znika.**

**Pięć etapów:**

| etap | rozpoznany po |
|---|---|
| 0 PRZED BUDOWĄ | nie spełnia warunków etapu 1+ |
| 1 ROBOTY ZIEMNE | goły grunt podwyższony ponad **własny** poziom obszaru, utrzymany 3 epoki |
| 2 ZABUDOWA ROŚNIE | zabudowa potwierdzona ≥ 15% celu kampusu |
| 3 BRYŁA ZAMKNIĘTA | zabudowa potwierdzona ≥ 65% celu kampusu |
| 4 ZIELEŃ URZĄDZONA | bryła zamknięta + **powrót** zieleni w kołnierzu wokół hal |
"""))

    # ---------------------------------------------------------------- 2 lista
    c.append(md("""
---
# 2 · Skąd lista obszarów — z pomiaru, nie z pamięci

`discover.py` pobiera z OSM wszystkie obiekty `telecom=data_center` /
`building=data_center` w CONUS (**1730 hal**), skupia je w kampusy i wybiera
największe po powierzchni hal.

To jest ranking **mierzalny**, a nie ranking po nakładach — takiego nie da się
tu zweryfikować, więc go nie udaję.

Dwa obszary są **odniesieniem**: mają udokumentowaną oś czasu z doniesień
branżowych, więc można sprawdzić, czy wykryte daty zgadzają się z ogłoszonymi.
"""))
    c.append(code("""
s = pd.DataFrame(json.load(open("sites.json", encoding="utf-8"))["sites"])
s["rola"] = s.get("control", False).fillna(False).map({True: "ODNIESIENIE", False: ""}) \\
    if "control" in s.columns else ""
s["pow. hal [ha]"] = (s.hall_area_m2 / 1e4).round(0)
s["cel [%AOI]"] = (s.target_built_frac * 100).round(1)
display(s[["id", "place", "rola", "halls", "pow. hal [ha]", "cel [%AOI]"]]
        .rename(columns={"id": "obszar", "place": "gdzie", "halls": "hal"}))
"""))

    # ---------------------------------------------------------------- 3 wyniki
    c.append(md("""
---
# 3 · Wyniki — kto na jakim etapie

Wiersz = obszar, kolumna = epoka półroczna, kolor = etap. Przebieg jest
**niemalejący**: budowa się nie cofa, a bez tej zapadki jedna epoka z chmurami
wyrzucałaby obszar z etapu 3 na 1.
"""))
    c.append(code("""
display(Image(os.path.join(C.OUT_DIR, "etapy.png")))
"""))
    c.append(code("""
t = df.copy()
t["gdzie"] = t.id.map(GDZIE)
t["rola"] = t.id.map(lambda i: "ODNIESIENIE" if KTORE.get(i) else "")
t["etap"] = t.stage.map(S.STAGE_SHORT)
t["zabudowa [%]"] = (t.built_frac * 100).round(1)
t["cel_ef [%]"] = (t.target_built_frac * 100).round(1)
t["postęp [%]"] = (t.progress * 100).round(0)
display(t[["gdzie", "rola", "etap", "since", "zabudowa [%]", "cel_ef [%]",
           "postęp [%]"]].rename(columns={"since": "od"})
        .sort_values(["etap", "postęp [%]"], ascending=False))
"""))
    c.append(md("""
**Jak to czytać — i czego tu nie ma.** Werdykt etapu jest wiarygodniejszy niż
liczba postępu. Mianownikiem postępu jest powierzchnia hal zmapowanych w OSM,
a kompletność OSM jest bardzo nierówna: postęp 570% znaczy „OSM zna ułamek
tego, co stoi", a nie „potok widzi pięć razy za dużo". Rozstrzyga to sekcja 7.
"""))

    # ---------------------------------------------------------------- 4 case 1
    c.append(md("""
---
# 4 · Case study: Google Red Oak, Teksas

Najostrzejszy sprawdzian w całym zestawie, bo **cała budowa mieści się wewnątrz
szeregu** i ma publicznie znane daty.
"""))
    c.append(code("""
display(Markdown(narracja.markdown("google_3254")))
"""))
    c.append(code("""
display(Image(os.path.join(C.OUT_DIR, "mozaiki",
                           "KONTROLNY_google_3254_1_barwy_naturalne.png")))
display(Image(os.path.join(C.OUT_DIR, "mozaiki",
                           "KONTROLNY_google_3254_3_klasyfikacja.png")))
display(Image(os.path.join(C.OUT_DIR, "krzywe", "google_3254.png")))
"""))
    c.append(md("""
**To ten obszar wykrył poważny błąd.** W pierwszej wersji roboty ziemne
wychodziły na 2021H2 — dwa i pół roku przed faktycznym startem budowy.
Przyczyna widoczna w krzywej: AOI było **polem uprawnym**, a udział gołej ziemi
skakał sezonowo —

```
2019H1 16,5%  →  2019H2 49,7%  →  2021H1 19,3%  →  2021H2 54,9%  →  2022H1 61,2%  →  2022H2 27,1%
```

Zaorka daje 55–61% gołej ziemi i **wraca do zieleni**, czego warunek „przyrost
ponad poziom wyjściowy" nie odróżniał od wykopu. Stąd wymóg, by podwyższony
grunt utrzymał się przez trzy epoki.
"""))

    # ---------------------------------------------------------------- 5 case 2
    c.append(md("""
---
# 5 · Case study: T5@Atlanta, Lithia Springs, Georgia
"""))
    c.append(code("""
display(Markdown(narracja.markdown("t5_data_centers_3375")))
"""))
    c.append(code("""
display(Image(os.path.join(C.OUT_DIR, "mozaiki",
                           "KONTROLNY_t5_data_centers_3375_4_wzrost_zabudowy.png")))
display(Image(os.path.join(C.OUT_DIR, "krzywe", "t5_data_centers_3375.png")))
"""))
    c.append(md("""
**Ograniczenie konstrukcyjne, nie usterka.** Faza T5@ATL III (start VIII 2024,
zadaszenie VI 2025) nie pokazuje się w kolumnie etapu, bo etapy są niemalejące
i „bryła zamknięta" z 2020H2 już się nie cofnie. Rozbudowy dojrzałego kampusu
trzeba szukać w **krzywej udziału zabudowy** i na **mapie „kiedy pojawiła się
zabudowa"** — obie powyżej.
"""))

    # ---------------------------------------------------------------- 6 case 3
    c.append(md("""
---
# 6 · Case study: Taylor County, Teksas — cena poprawki

Półpustynia: poziom wyjściowy to **58% gołej ziemi**. Sygnał budowy jest tu
czysty i monotoniczny (73,5% → 84,1% → 87,1%), więc wymóg trzech epok
**opóźnił wykrycie z 2024H2 na 2025H2 — o rok**.

To jest świadomy wybór: wariant, który nie wymyśla budowy tam, gdzie jej nie ma,
kosztem spóźnienia tam, gdzie sygnał jest czysty. W tym zadaniu fałszywe
ogłoszenie etapu jest gorsze niż spóźnienie.
"""))
    c.append(code("""
display(Image(os.path.join(C.OUT_DIR, "krzywe", "bez_nazwy_3250.png")))
display(Image(os.path.join(C.OUT_DIR, "mozaiki",
                           "bez_nazwy_3250_1_barwy_naturalne.png")))
"""))

    # ---------------------------------------------------------------- 7 jakość
    c.append(md("""
---
# 7 · Ile to jest warte

Dwie niezależne miary: jakość klasyfikatora na danych sprawdzających
i zgodność „zabudowy potwierdzonej" z obrysami budynków OSM, których model
dla tych obszarów nie widział.
"""))
    c.append(code("""
import joblib
rep = joblib.load(os.path.join(C.OUT_DIR, "model.joblib"))["report"]
viz.confusion(rep); plt.show()
print(f"GRUNT wzięty za DACH: {rep.get('bare_as_roof', float('nan'))*100:.1f}%"
      "  — i to jest błąd, który filtry czasowe mają dociąć")
"""))
    c.append(md("""
Zieleń i woda rozdzielają się bezbłędnie; **cała pomyłka siedzi między gruntem,
dachem i asfaltem** i jest nieusuwalna spektralnie — świeży beton, blacha
i przesuszona jasna glina mają w sześciu pasmach Sentinela podpisy, które na
siebie zachodzą.

Kalibracja progów (`calibrate.py`, 30 kombinacji na zapisanych mapach
prawdopodobieństwa) — średnia po obszarach:

| progi | celność | pokrycie |
|---|---|---|
| 0.60 / 25 px / trwałość 2 | 65% | 74% |
| **0.60 / 50 px / trwałość 3** ← wybrane | **74%** | 67% |
| 0.90 / 50 px / trwałość 3 | 78% | 35% |

Podniesienie progu do 0,90 kupuje jeszcze 4 punkty celności, a kosztuje połowę
pokrycia — dlatego nie.
"""))

    # ---------------------------------------------------------------- 8 wnioski
    c.append(md("""
---
# 8 · Wnioski

**Co działa.**
* **Koniec budowy** — „bryła zamknięta" wypada z dokładnością do pół roku
  (Red Oak: wykryte 2025H1 wobec obiektu operacyjnego od 2025).
* **Rozdzielenie dachu od asfaltu** — bez niego plac manewrowy ogłaszałby halę
  rok za wcześnie.
* **Trwałość zamiast spektrum** — najważniejsze rozstrzygnięcia nie są
  spektralne, tylko czasowe. Jasna glina wysycha i moknie, budynek nie znika.

**Co nie działa albo działa gorzej.**
* **Początek budowy na gruntach rolnych** — zaorka wygląda jak wykop. Wymóg
  trzech epok to łata, nie rozwiązanie; właściwe byłoby porównanie do poziomu
  z tego samego sezonu.
* **Rozbudowa dojrzałego kampusu** — zapadka etapów ją ukrywa. Widać ją tylko
  w krzywych i na mapie wzrostu zabudowy.
* **Postęp jako liczba** — mianownik (powierzchnia hal w OSM) ma nierówną
  kompletność, więc rozrzut 0–570% mówi więcej o OSM niż o budowach.

**Czego ta analiza nie mówi.**
* To **nie jest ranking po nakładach**, tylko po powierzchni hal zmapowanych
  w OSM. Kampus niezmapowany nie istnieje w tym zestawieniu.
* Daty z doniesień branżowych mówią, kiedy coś **ogłoszono i planowano** — nie
  kiedy wjechały koparki. Dlatego zgodność oceniam w epokach półrocznych.
* Zapadka zakłada, że hal się nie rozbiera.

**Gdyby to ciągnąć dalej**, w tej kolejności: poziom wyjściowy gruntu liczony
osobno dla H1 i H2 (usuwa sezonowość rolną u źródła), etap „rozbudowa" obok
niemalejącej skali, i cel zabudowy z obrysów innych niż OSM, żeby postęp
przestał zależeć od kompletności jednego źródła.
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
    from nbclient import NotebookClient
    nb = nbf.read(NB, as_version=4)
    NotebookClient(nb, timeout=1800, kernel_name="python3",
                   resources={"metadata": {"path": here}}).execute()
    nbf.write(nb, NB)
    nerr = sum(1 for cl in nb.cells for o in cl.get("outputs", [])
               if o.get("output_type") == "error")
    nimg = sum(1 for cl in nb.cells for o in cl.get("outputs", [])
               if "image/png" in (o.get("data") or {}))
    print(f"gotowe: {nimg} obrazkow, {nerr} bledow -> {NB}")
    return 1 if nerr else 0


if __name__ == "__main__":
    sys.exit(main())
