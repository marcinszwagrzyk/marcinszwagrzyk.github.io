# Analizator etapów budowy kampusów data center (USA)

Szereg czasowy Sentinel-2 z Microsoft Planetary Computer → klasyfikacja pokrycia
terenu → **etap budowy** dla dziesięciu największych kampusów.

Pięć etapów, dokładnie w kolejności procesu budowy:

| etap | nazwa | po czym rozpoznany |
|---|---|---|
| 0 | PRZED BUDOWĄ | nie spełnia warunków etapu 1+ |
| 1 | ROBOTY ZIEMNE | przyrost gołego gruntu względem **własnego** poziomu wyjściowego obszaru |
| 2 | ZABUDOWA ROŚNIE | zabudowa potwierdzona ≥ 15% **celu kampusu** |
| 3 | BRYŁA ZAMKNIĘTA | zabudowa potwierdzona ≥ 65% **celu kampusu** |
| 4 | ZIELEŃ URZĄDZONA | bryła zamknięta + **powrót** zieleni w kołnierzu wokół hal + grunt opadł |

## Uruchomienie

```bash
python discover.py        # 1. zbuduj listę obszarów z OSM -> sites.json
python run.py             # 2. policz wszystko -> out/
python build_notebook.py  # 3. złóż i wykonaj analiza.ipynb
```

`python run.py <id> [<id>...]` liczy wybrane obszary, `--no-osm` pomija obrysy.
Interpreter: `C:\Users\marci\anaconda3\python.exe` (base anaconda).
Wymagane: `pystac-client`, `planetary-computer`, `odc-stac`, `xarray`, `rasterio`,
`geopandas`, `scikit-learn`, `scipy`, `matplotlib`, `requests`, `nbformat`, `nbclient`.

## Co gdzie ląduje

| ścieżka | zawartość |
|---|---|
| `analiza.ipynb` | **notatnik z wszystkimi wizualizacjami** — wykonany, otwiera się z obrazkami |
| `out/etapy.csv` | jeden wiersz na obszar: etap, od kiedy, postęp, udziały |
| `out/przebieg.csv` | metryki epoka po epoce — surowe liczby pod każdym wnioskiem |
| `out/etapy.png` | mapa etapów: obszar × epoka × kolor |
| `out/krzywe/<id>.png` | krzywe udziałów klas + schodki etapu |
| `out/maps/<id>.npz` | mapy klas i zabudowy (notatnik tylko je rysuje) |
| `out/model.joblib` | model + jego ocena (ta sama, co w raporcie) |
| `out/cache/*.nc` | kompozyty Sentinel-2 — drugi bieg liczy się w minutach |
| `out/osm/*.gpkg` | obrysy budynków i nawierzchni (otwieralne w QGIS) |

## Pliki

| plik | rola |
|---|---|
| `discover.py` | **lista obszarów z OSM** — ranking po powierzchni hal |
| `config.py` | progi, okno czasu; wczytuje `sites.json` |
| `mpc.py` | STAC + kompozyty medianowe, harmonizacja offsetu BOA |
| `osm.py` | obrysy budynków i nawierzchni z Overpass |
| `labels.py` | pola treningowe z ESA WorldCover + OSM |
| `features.py` | cechy spektralne (odbicia + NDVI/NDBI/BSI/NDWI/jasność) |
| `classify.py` | las losowy + **ostrożne potwierdzanie zabudowy** |
| `stages.py` | maszyna etapów |
| `viz.py`, `plot.py` | mapki i wykresy |
| `run.py`, `build_notebook.py` | przebieg całości i notatnik |

---

# Sześć rzeczy, które w tym zadaniu łatwo zrobić źle

Każda z nich sama z siebie daje wynik, który wygląda sensownie i jest nieprawdziwy.
Trzy pierwsze **popełniłem** i wyszły dopiero przy sprawdzaniu — zostawiam je
opisane, bo to one tłumaczą, dlaczego kod wygląda tak, a nie prościej.

## 1. Zły kadr daje poprawny wynik dla złego miejsca

Pierwsza lista obszarów pochodziła z mojej pamięci. Dla Ashburn miała punkt
`39.0437, -77.4875`. Sprawdzenie obrysami budynków:

```
Ashburn — udział hal (budynki > 10 000 m²) w kwadracie o półboku R
   R [m]   pole [km2]   hale [km2]   udział   wszystkie budynki
     600         1.44        0.000     0.0%          8.3%
    1200         5.76        0.007     0.1%          9.3%
    1500         9.00        0.024     0.3%          9.8%
    3000        36.00        0.347     1.0%         10.4%
```

Zabudowa zajmuje tam 9,8% powierzchni, ale **halami jest 0,0%** — to dzielnica
domów jednorodzinnych, kilka kilometrów od Data Center Alley. Potok policzył
*„PRZED BUDOWĄ, zabudowa 1,6%"* dla najgęstszego skupiska data center na
świecie: wynik poprawny dla złego kadru.

Takiego błędu nie widać w liczbach — widać go dopiero, gdy się zapyta, **skąd
wzięły się współrzędne**. Dlatego lista nie jest już wpisywana z ręki:
`discover.py` pobiera z OSM wszystkie obiekty `telecom=data_center` /
`building=data_center` (w CONUS **1730 hal**), skupia je w kampusy promieniem
900 m i wybiera dziesięć największych po powierzchni hal, z odstępem 15 km, żeby
dziesiątka nie była dziesięcioma wycinkami tego samego skupiska w Wirginii.

**Co znaczy „największe": powierzchnia hal zmapowanych w OSM — nie nakłady.**
Rankingu po nakładach nie mam skąd wziąć w sposób weryfikowalny, a wymyślanie
kwot byłoby zmyślaniem. Powierzchnia hal jest mierzalna i sprawdzalna.
Ograniczenia: kompletność OSM jest nierówna, a kampus ≠ działka ewidencyjna.

## 2. Jeden próg zabudowy nie pasuje do dwóch kampusów

Druga wersja miała „zabudowa ≥ 18% obszaru = bryła zamknięta". To była wartość
wzięta z powietrza — i zawyżona o rząd wielkości: prawda z OSM dla tamtego kadru
to 1,6%. Model miał rację, próg był bzdurą.

Teraz progi są **ułamkiem celu danego kampusu**, gdzie cel = powierzchnia hal
z OSM ÷ powierzchnia kadru (`target_built_frac`, liczone w `discover.py`).
Raport pokazuje **postęp** = zabudowa potwierdzona ÷ cel.

Podłoga bezwzględna progu musi być **niższa niż najmniejszy cel** w `sites.json`
(dziś 1,86%). Przy poprzedniej wartości 0,012 próg „bryła zamknięta" (2× podłoga
= 2,4%) był dla najmniejszych kampusów nieosiągalny.

## 3. Obrys działki to nie obrys dachu

Najgroźniejszy z tych błędów, bo wyglądał jak poprawnie zmierzony cel.
`telecom=data_center` bywa w OSM przypięty do **granicy terenu**, nie do hali.
Zmierzone na kampusie Google w Berkeley County — 10 obiektów:

```
  77.2 ha   landuse=industrial, BEZ tagu building, "Google ... Data Center"
   6.5 ha   building=industrial
   2.3 ha   building=industrial
   ...      (jeszcze 7 hal)
  SUMA 96.9 ha   —   ale z tagiem `building` tylko 19.7 ha
```

Ta jedna 77-hektarowa działka zawyżała cel pięciokrotnie (27% zamiast 5,5%
kadru). Skutek: próg „bryła zamknięta" był **nieosiągalny** i w całym biegu
żaden z dziesięciu kampusów nie doszedł dalej niż „zabudowa rośnie" — wynik,
który wyglądał jak ostrożność potoku, a był arytmetyką z zawyżonego mianownika.

Poprawka: wszystkie obiekty służą do **zlokalizowania** kampusu, ale
**powierzchnię hal liczymy wyłącznie z obiektów mających tag `building`**.
Kampusy bez ani jednej zmapowanej hali (sama granica terenu — 37 sztuk)
wypadają z rankingu, bo nie wiadomo, ile zabudowy ma na nich być.
Po poprawce cele spadły z 10–27% do 1,9–9,5% kadru, a ranking zmienił się
na dziewięciu z dziesięciu pozycji.

## 4. Offset BOA — sztuczny uskok w 2022

Sentinel-2 od „processing baseline" 04.00 (styczeń 2022) ma `BOA_ADD_OFFSET = -1000`.
Sprawdzone nad Ashburn:

```
2018 -> 02.12   2020 -> 02.12   2021 -> 03.00   2022 -> 04.00   2024 -> 05.11
```

Bez poprawki **wszystkie** wskaźniki dostają skok na przełomie 2021/2022, a potok
ogłasza „początek budowy" na dziesięciu obszarach w tym samym kwartale. `mpc.py`
ładuje sceny w dwóch grupach według baseline. Kontrola po poprawce — mediana NDVI:

```
2019H1 0.560 | 2020H1 0.599 | 2021H1 0.529 | 2022H1 0.577 | 2023H1 0.521
największy skok rok do roku: 0.070   (przez granicę baseline: 0.048)
```

Skok przez granicę nie jest większy niż zwykła zmienność międzyroczna, a NDVI
p90 ≈ 0,81 to fizycznie poprawna wartość dla lasu w Wirginii latem.

## 5. Próg gołej ziemi nie może być bezwzględny

W Arizonie i Teksasie goła ziemia to **naturalny** stan terenu. Próg „25% gruntu
= ruszyły roboty" ogłosiłby roboty ziemne na pustyni w pierwszej epoce szeregu.
Dlatego roboty ziemne rozpoznajemy po **przyroście** względem mediany pierwszych
dwóch epok danego obszaru, a etap 0 jest zdefiniowany negatywnie — nie przez próg
zieleni, bo w Arizonie nigdy nie będzie 55% zieleni, a obszar i tak jest przed budową.

## 6. Zieleń wokół hal to nie to samo co powrót zieleni

Przed budową cały obszar jest zielony — pole albo las. Obecność zieleni wokół hal
nie odróżnia trawnika od nietkniętej łąki. Odróżnia je **powrót**: zieleń musi
najpierw zniknąć (plac budowy, składowisko, droga technologiczna), a potem wrócić.

Dlatego nie mierzymy jej w pierścieniu o stałym promieniu, ale w **kołnierzu wokół
potwierdzonej zabudowy** (dylatacja maski hal o 120 m) i wymagamy przyrostu
względem minimum, jakie ten kołnierz osiągnął w czasie budowy. To dosłowne
odwzorowanie „wzrostu zieleni urządzonej dookoła zabudowy".

---

# Ostrożne klasyfikowanie zabudowy — trzy filtry, żaden spektralny

Zmierzona jakość klasyfikatora (las losowy, 5 klas, dane sprawdzające):

```
dokładność 88.1%
             ZIELEŃ    GRUNT     DACH   ASFALT     WODA
  ZIELEŃ     100.0%     0.0%     0.0%     0.0%     0.0%
   GRUNT       0.0%    77.6%     6.6%    15.8%     0.0%
    DACH       0.0%     9.1%    84.0%     6.8%     0.0%
  ASFALT       0.0%    11.9%     4.5%    83.6%     0.0%
    WODA       0.0%     0.0%     0.0%     0.0%   100.0%
```

Zieleń i woda rozdzielają się bezbłędnie; **cała pomyłka siedzi między gruntem,
dachem i asfaltem** i jest nieusuwalna spektralnie — świeży jasny beton, blacha
i przesuszona jasna glina mają w sześciu pasmach Sentinela podpisy, które na
siebie zachodzą. Krytyczna liczba to **GRUNT wzięty za DACH: 6,6%**.

Dlatego zabudowa nie pochodzi z jednej klasyfikacji. Piksel wchodzi do zabudowy
po trzech filtrach, z których żaden nie jest spektralny:

1. **Pewność** — `p(DACH) ≥ 0.60`. Fałszywy alarm (ogłoszenie etapu, który nie
   nastąpił) jest tu gorszy niż spóźnienie o jedną epokę.
2. **Spójność przestrzenna** — skupisko ≥ 25 pikseli (0,25 ha). Hala ma
   10–50 tys. m², czyli 100–500 pikseli; pojedynczy jasny piksel to szum.
3. **Trwałość w czasie** — filtr rozstrzygający: **jasna glina wysycha i moknie,
   budynek nie znika.** Klasa DACH musi się utrzymać w dwóch kolejnych epokach,
   i od tego momentu piksel pozostaje zabudową (zapadka).

Do tego klasyfikator uczy się **osobno DACHU i osobno ASFALTU**, choć oba są
nieprzepuszczalne i oba siedzą w klasie 50 WorldCover. Powód: droga dojazdowa
i plac manewrowy powstają razem z wykopem, hala rok lub dwa później. Model, który
ich nie rozdziela, ogłasza „stoją budynki" na widok asfaltowego placu budowy.
Rozdziela je jasność — dlatego wśród cech jest `BRIGHT`, i dlatego potrzebne są
obrysy z OSM jako prawdziwe przykłady jednej i drugiej klasy.

---

# Założenia i ograniczenia

* **Zapadka etapów** zakłada, że hal się nie rozbiera.
* **Cel z OSM to stan dzisiejszy**, w tym hale `building=construction`. Dla
  kampusu w budowie to zaleta (cel ≈ stan docelowy), ale przy niekompletnym OSM
  cel jest zaniżony i „bryła zamknięta" przychodzi za wcześnie.
* **Pola treningowe pochodzą z otoczenia obszaru, nie z samego obszaru** —
  inaczej model uczyłby się stanu inwestycji z 2021 i „rozpoznawał" to, co już
  widział.
* **Etykiety WorldCover są z 2021**, a model stosujemy do epok 2018–2025.
  Założenie: podpis spektralny materiału nie zmienia się w czasie. Dla odbicia
  znormalizowanego i kompozytów z tej samej pory roku jest rozsądne.
* **ms-buildings z Planetary Computer jest nieużywalne** i nie jest to
  przeoczenie: zasób to jeden GeoParquet na cały kraj — 129 554 779 wierszy, jedna
  kolumna `geometry`, partycja `RegionName=United States`, `msft:partition_info = None`.
  Bez kolumny quadkey ani bbox nie da się przeczytać samego obszaru 6×6 km.
* **Overpass odpowiada nierówno.** Zmierzone: okno 1×1 km → 200 w 1,5 s;
  kafel 3×3 km → 504 po 8 s; kafel 6×6 km → 200 w 2,6 s (13,4 MB, 11 424 budynki).
  Czyli 504 nie bierze się z rozmiaru zapytania, tylko z chwilowego obciążenia —
  kod ponawia u hosta, który odpowiada, zamiast drobić zapytania.
* **Odczyt z blobów Azure bywa przerywany** („Could not resolve host",
  „Chunk and warp failed"). Przy ~170 kompozytach na bieg jest to pewne, więc
  odczyt ma ponowienia, a awaria jednej epoki kosztuje jedną epokę, nie cały bieg.
