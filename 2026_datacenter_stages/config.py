# -*- coding: utf-8 -*-
"""Konfiguracja analizatora etapów budowy kampusów data center (USA).

================================ UWAGA O LIŚCIE ================================
To NIE jest autorytatywny ranking „10 największych inwestycji" po nakładach.
Nie mam wiarygodnego, weryfikowalnego źródła takiego rankingu, a wymyślanie
kwot i współrzędnych byłoby zmyślaniem. Poniżej jest **moja selekcja dziesięciu
powszechnie znanych, bardzo dużych kampusów i projektów hiperskalowych w USA**,
z **przybliżonymi** środkami obszaru.

Każdy wpis ma pola `approx` i `source_note`. Przed wyciąganiem wniosków:
  1. sprawdź współrzędne (np. na mapie satelitarnej — kampus musi być w kadrze),
  2. ustaw `radius_m` tak, by objąć całą działkę inwestycji,
  3. podmień wpisy na te, które Cię interesują — plik jest jedynym miejscem,
     które trzeba ruszyć.
Potok liczy to, co mu wskażesz; jakość listy jest oddzielną sprawą od jakości
klasyfikacji.
================================================================================
"""

# --- okno czasowe analizy -----------------------------------------------------
# Sentinel-2 L2A na Planetary Computer sięga 2015/2016; sensowny start dla
# „sprzed budowy" to 2017, bo wtedy są już oba satelity (S2A+S2B) i zdjęcia
# co ~5 dni, czyli jest z czego robić kompozyty bezchmurne.
START_YEAR = 2018
END_YEAR = 2025

# Kompozyty półroczne: wiosna-lato (zieleń w pełni) i jesień-zima.
# Etap budowy zmienia się w miesiącach, nie w dniach — półrocze to właściwa
# rozdzielczość, a przy okazji daje dość scen na medianę bez chmur.
EPOCHS_PER_YEAR = 2

# --- dane źródłowe ------------------------------------------------------------
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
S2_COLLECTION = "sentinel-2-l2a"

# Pasma 10 m i 20 m, których używamy. B11/B12 (SWIR) są kluczowe: to one
# rozdzielają świeży beton i blachę od gołej ziemi, czego samo RGB+NIR nie robi.
S2_BANDS = ["B02", "B03", "B04", "B08", "B11", "B12", "SCL"]
RESOLUTION_M = 10

# Maksymalne zachmurzenie scen wchodzących do kompozytu.
MAX_CLOUD = 35

# Klasy SCL (Scene Classification Layer) do ODRZUCENIA przed medianą.
# 3 = cienie chmur, 8/9 = chmury średnie/wysokie, 10 = cirrus, 11 = śnieg.
# Śnieg odrzucamy, bo zasypany placu budowy nie da się klasyfikować.
SCL_DROP = [0, 1, 3, 8, 9, 10, 11]

# Warstwy publiczne na POLA TRENINGOWE (nie na wykrywanie etapów — patrz labels.py).
WORLDCOVER_COLLECTION = "esa-worldcover"
MSBUILDINGS_COLLECTION = "ms-buildings"

# --- parametry etapow ---------------------------------------------------------
# ROBOTY ZIEMNE rozpoznajemy po PRZYROSCIE golego gruntu wzgledem wlasnego
# poziomu wyjsciowego obszaru, nie po wartosci bezwzglednej. W Mesa (AZ) i
# Abilene (TX) goly grunt to naturalny stan terenu i prog bezwzgledny oglosilby
# tam roboty ziemne juz w pierwszej epoce szeregu.
BASELINE_EPOCHS = 2          # ile pierwszych epok daje poziom wyjsciowy (mediana)
TH_BARE_DELTA = 0.12         # przyrost gruntu wzgledem poziomu wyjsciowego
TH_BARE_MIN = 0.18           # ...i minimalny udzial, zeby odsiac szum
TH_BARE_SETTLED = 0.15       # tyle gruntu = plac budowy juz sprzatniety

# ZABUDOWA: progi NIE sa tu bezwzgledne - patrz blok "progi zabudowy" na koncu
# pliku (TH_BUILT_REL_*). Prog bezwzgledny bylby zly dla kampusu gestego ALBO
# dla rozrzuconego; nie ma jednej wartosci dobrej dla obu.

# ZIELEN URZADZONA - mierzona w KOLNIERZU wokol potwierdzonej zabudowy, a nie
# w pierscieniu o stalym promieniu. Przed budowa caly obszar jest zielony, wiec
# liczy sie POWROT zieleni, nie jej obecnosc.
LANDSCAPE_COLLAR_M = 120     # szerokosc kolnierza wokol hal
MIN_COLLAR_PIXELS = 200      # mniejszy kolnierz = za maly, zeby cos orzekac
TH_COLLAR_GREEN = 0.35       # tyle zieleni w kolnierzu
TH_COLLAR_RECOVERY = 0.10    # ...i taki przyrost wzgledem minimum z budowy

# OSTROZNOSC PRZY ZABUDOWIE: piksel uznajemy za zabudowe tylko wtedy, gdy
# utrzyma te klase w co najmniej tylu KOLEJNYCH epokach. Swiezy beton i jasna,
# przesuszona ziemia maja podobny podpis; rozni je to, ze budynek NIE ZNIKA.
BUILT_PERSISTENCE_EPOCHS = 3

# --- obszary zainteresowania --------------------------------------------------
# Lista NIE jest wpisywana z ręki. Generuje ją `discover.py` z OpenStreetMap
# (telecom=data_center / building=data_center), skupia hale w kampusy i wybiera
# N największych po POWIERZCHNI HAL, z zachowaniem odstępu, żeby dziesiątka nie
# była dziesięcioma wycinkami tego samego skupiska w Wirginii.
#
# DLACZEGO NIE Z RĘKI: pierwsza wersja pochodziła z mojej pamięci i miała dla
# Ashburn punkt 39.0437,-77.4875. W kwadracie o półboku 1,5 km wokół niego jest
# 0,0% hal (zabudowa 9,8%, ale to domy jednorodzinne) — punkt leżał w dzielnicy
# mieszkaniowej, kilka kilometrów od Data Center Alley. Potok policzył wtedy
# „PRZED BUDOWĄ, zabudowa 1,6%" dla najgęstszego skupiska data center na
# świecie: wynik poprawny dla złego kadru. Takiego błędu nie da się wyłapać
# patrząc na liczby, tylko patrząc na to, skąd wzięły się współrzędne.
#
#     python discover.py          # zbuduj / odśwież sites.json
#     python discover.py --show   # pokaż, co jest w sites.json
N_SITES = 10

import json as _json
import os as _os

_SITES_JSON = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                            "sites.json")

# Zapas na wypadek braku sites.json: kilka znanych rejonów z PRZYBLIŻONYMI
# współrzędnymi, wyłącznie po to, żeby dało się uruchomić potok bez sieci.
# Oznaczone approx=True — i jak widać wyżej, approx=True potrafi znaczyć
# „zupełnie nie ten kadr".
SITES_FALLBACK = [
    dict(id="ashburn_va", name="Data Center Alley, Loudoun County, VA",
         lat=39.0081, lon=-77.4516, radius_m=2500, approx=True,
         target_built_frac=0.12,
         source_note="środek z klastra OSM #1 (AWS, 173 hale) — zapas"),
    dict(id="new_albany_oh", name="New Albany / Johnstown, OH",
         lat=40.0600, lon=-82.7584, radius_m=1800, approx=True,
         target_built_frac=0.10,
         source_note="środek z klastra OSM (Google) — zapas"),
]


def _load_sites():
    if _os.path.exists(_SITES_JSON):
        with open(_SITES_JSON, encoding="utf-8") as f:
            return _json.load(f)["sites"]
    return SITES_FALLBACK


SITES = _load_sites()

# --- wyjście ------------------------------------------------------------------
OUT_DIR = "out"
CACHE_DIR = "out/cache"       # kompozyty per site/epoka (NetCDF)

# Ile scen maksymalnie wchodzi do jednej mediany. Nad obszarem 6x6 km jest ich
# w poltoczu nawet 57; mediana z 12 rozlozonych po oknie jest praktycznie tak
# samo odporna, a pobranie jest kilka razy krotsze (16 epok x 10 obszarow).
MAX_SCENES_PER_EPOCH = 12

OSM_DIR = "out/osm"          # obrysy z Overpass (GPKG)

# --- pola treningowe ----------------------------------------------------------
# Epoka, z ktorej bierzemy pola treningowe. Musi odpowiadac rocznikowi etykiet
# WorldCover, bo inaczej uczymy model na niezgodnej parze obraz-etykieta.
TRAIN_EPOCH = "2021H1"
WORLDCOVER_YEAR = 2021
TRAIN_SCALE = 2.0            # probki z kadru 2x szerszego, bez samego obszaru
SAMPLES_PER_CLASS = 2500     # na obszar; przy 10 obszarach do 25 tys. na klase
SEED = 20261002

# Warunki, ktore etykieta musi spelnic OPROCZ zgody warstwy publicznej.
# WorldCover ma kilka procent bledu, a zle pole treningowe psuje model bardziej
# niz mniejsza liczba probek.
LBL_VEG_NDVI = 0.45         # zielen: musi byc naprawde zielona w H1
LBL_WATER_NDWI = 0.20       # woda: musi miec dodatni NDWI
LBL_BARE_NDVI = 0.20        # goly grunt / zorana rola: niskie NDVI
LBL_BARE_BSI = 0.05         # i dodatni indeks golej gleby
LBL_IMPERV_NDVI = 0.30      # dach/asfalt: pod obrysem nie moze rosnac trawa

# Obrysy dachow: zwezamy o 10 m (jeden piksel S2) i bierzemy tylko duze
# budynki - maly dom to 1-2 piksele, w wiekszosci mieszane z ogrodem.
ROOF_SHRINK_M = 10.0
ROOF_MIN_AREA = 2000.0

# --- klasyfikator -------------------------------------------------------------
RF_TREES = 300
RF_MIN_LEAF = 4             # lisc nie mniejszy niz 4 piksele - mniej przeuczenia

# ===================== PROGI DOBRANE POMIAREM, NIE NA OKO =====================
# Pierwotnie wpisalem 0,60 / 25 px / trwalosc 2 "na oko". Kontrola wzgledem
# obrysow OSM pokazala, ze na czesci obszarow polowa "zabudowy potwierdzonej"
# nie lezy na zadnym budynku (Los Lunas 96%, Taylor 57%, Loudoun 45%,
# Papillion 40% celnosci) - i nie jest to artefakt odniesienia, bo trzy rozne
# jego definicje daja ten sam wynik co do punktu procentowego.
#
# `calibrate.py` przeszedl 30 kombinacji progow na zapisanych mapach p(DACH)
# (srednia po 9 obszarach):
#     0.60 /  25 / 2   celnosc 65%   pokrycie 74%    <- bylo
#     0.60 /  50 / 3   celnosc 74%   pokrycie 67%    <- jest
#     0.90 /  50 / 3   celnosc 78%   pokrycie 35%
# Trwalosc 3 bije trwalosc 2 na kazdym poziomie prawdopodobienstwa. Wybieramy
# 0.60/50/3: +9 pkt proc. celnosci za -7 pkt proc. pokrycia. W tym zadaniu to
# dobry kurs wymiany, bo falszywe ogloszenie etapu jest gorsze niz spoznienie
# o jedna epoke. Podnoszenie progu do 0,90 kupuje juz tylko 4 pkt celnosci,
# a kosztuje polowe pokrycia.
# Po kazdej zmianie modelu warto puscic `python calibrate.py` ponownie.
MIN_P_ROOF = 0.60
# Hala data center ma 10-50 tys. m2 = 100-500 pikseli po 10 m. Skupisko mniejsze
# niz 50 pikseli (0,5 ha) to szum, nie budynek.
MIN_ROOF_PIXELS = 50

# --- progi zabudowy: UŁAMEK CELU, nie wartosc bezwzgledna ---------------------
# Cel = powierzchnia hal z OSM / powierzchnia AOI (`target_built_frac` z
# discover.py). Jeden prog bezwzgledny nie moze pasowac do kampusu o celu 27%
# i do kampusu o celu 11%; poprzednia wersja miala 18% "na sztywno" i orzekla
# PRZED BUDOWA dla Data Center Alley, gdzie prawda z OSM to 1,6% kadru.
TH_BUILT_REL_STRUCTURES = 0.15   # 15% celu = stoja pierwsze hale
TH_BUILT_REL_MATURE = 0.65       # 65% celu = bryla zamknieta
# Podloga bezwzgledna, zeby kampus o malym celu nie przechodzil etapow na samym
# szumie. Zmierzony poziom szumu: obszary BEZ realnych hal w kadrze daly
# 0,1-0,6% zabudowy potwierdzonej, wiec 0,5% jest tuz nad szumem.
# UWAGA: ta liczba musi byc NIZSZA niz najmniejszy cel w sites.json (dzis 1,9%),
# inaczej prog "bryla zamknieta" (2x podloga) bylby nieosiagalny - tak bylo przy
# poprzedniej wartosci 0,012, dobranej gdy cele byly zawyzone piciokrotnie.
TH_BUILT_FLOOR = 0.005

# --- rdzen kampusu ------------------------------------------------------------
# Udzialy klas liczymy w obrysie samej inwestycji, nie w calym kwadracie AOI.
# Kwadrat obejmuje magazyny, osiedla i inne zakladu, przez co "zabudowa
# potwierdzona" rosla bez zwiazku z kampusem, a postep wychodzil 120-672%.
CAMPUS_BUFFER_M = 350        # bufor na drogi, parkingi, podstacje, zielen
MIN_CAMPUS_PIXELS = 400      # mniejszy rdzen = za malo, zeby cos orzekac

# --- poprawka na pokrycie detektora ------------------------------------------
# Zmierzone przez calibrate.py: przy obecnych progach detektor trafia w 67%
# powierzchni budynkow znanych z OSM (celnosc 74%). Innymi slowy KOMPLETNY
# kampus da zabudowe potwierdzona rowna okolo 0,67 celu, a nie 1,0 celu.
# Porownywanie go z pelnym celem i stawianie poprzeczki "65% celu" liczyloby
# ten sam niedobor dwa razy - i tak wlasnie Data Center Alley, kampus w pelni
# zabudowany, wychodzil jako "zabudowa rosnie" przy postepie 64%.
# Dlatego mianownikiem postepu i progow jest POKRYCIE x CEL.
# Ta liczba ma byc odswiezana razem z progami: `python calibrate.py`.
DETECTOR_RECALL = 0.67

# --- trwalosc robot ziemnych --------------------------------------------------
# Udzial golej ziemi na polu uprawnym skacze sezonowo. Zmierzone na Red Oak
# (przed budowa, grunty rolne): 2019H1 16,5% -> 2019H2 49,7% -> 2021H1 19,3%
# -> 2021H2 54,9% -> 2022H1 61,2% -> 2022H2 27,1%. Zaorka daje 55-61% golej
# ziemi i WRACA do zieleni w nastepnym sezonie.
# Sam przyrost ponad poziom wyjsciowy brał wiec zaorke za wykop i oglaszal
# roboty ziemne w 2021H2 - dwa i pol roku przed faktycznym poczatkiem budowy
# (kwiecien 2024 wg zrodel). Pole wraca do zieleni, plac budowy nie, wiec
# warunkiem jest UTRZYMANIE sie podwyzszonego gruntu przez tyle epok.
BARE_PERSISTENCE_EPOCHS = 3
