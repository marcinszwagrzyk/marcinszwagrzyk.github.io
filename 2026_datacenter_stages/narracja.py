# -*- coding: utf-8 -*-
"""Obszary odniesienia: udokumentowana oś czasu vs to, co wykrył potok.

    python narracja.py

================================ PO CO TO JEST ================================
Potok sam o sobie mówi, na jakim etapie jest inwestycja. Żeby to sprawdzić,
potrzebny jest obszar, o którym wiadomo z zewnątrz, kiedy co się na nim działo.
Dwa takie obszary są w `sites.json` oznaczone `control=True`.

UCZCIWIE O DOBORZE: wybierałem je kryterium „OSM nie zna tu ani jednej hali
otagowanej `building=construction`", zakładając, że to wskaże kampusy ukończone.
Research pokazał, że założenie było błędne — oba są placami budowy w latach
2024–2026. Tag `building=construction` jest w OSM rzadki i nie świadczy o stanie
inwestycji. Nie są to więc „kampusy ukończone przed szeregiem", tylko obiekty
o UDOKUMENTOWANEJ OSI CZASU — co do sprawdzenia potoku nadaje się nawet lepiej,
bo zamiast pytać „czy wykres jest płaski", można porównać WYKRYTE DATY
z OGŁOSZONYMI.

CZYM TE DATY SĄ, A CZYM NIE SĄ: pochodzą z doniesień branżowych i prasowych,
nie z dokumentacji budowy. Mówią, kiedy coś ogłoszono i kiedy planowano, co nie
zawsze pokrywa się z tym, kiedy wjechały koparki. Traktujemy je jako punkt
odniesienia rzędu kwartału, nie jako prawdę co do dnia — i dlatego zgodność
oceniamy w epokach półrocznych, a nie w datach dziennych.
================================================================================
"""
from __future__ import annotations

import json
import os
import sys

import config as C
import stages as S

# Fakty zebrane z sieci. Każdy ma źródło — bez źródła nie ma wpisu.
FAKTY = {
    "google_3254": {
        "nazwa": "Google Red Oak, Ellis County, Teksas",
        "kamienie": [
            ("2023-08-31", "ogłoszenie inwestycji: kampus za ~600 mln USD "
                           "na działce ~375 akrów przy Ovilla Road", "DCD / KERA"),
            ("2024-04", "planowany początek budowy", "cleanview.co"),
            ("2025-12", "planowane zakończenie budowy", "cleanview.co"),
            ("2025-09", "potwierdzenie, że obiekt jest operacyjny", "WFAA"),
        ],
        "skala": "Building 1: ok. 287 500 sq ft, 107 MW, 165 akrów",
        "oczekiwanie": {
            S.PRZED: "do 2023H2",
            S.ZIEMNE: "2024H1 (budowa od kwietnia 2024)",
            S.ROSNIE: "2024H2 - 2025H1",
            S.ZAMKNIETA: "2025H2 (operacyjny od 2025)",
        },
        "zrodla": [
            "https://www.datacenterdynamics.com/en/news/google-announces-plans-for-red-oak-data-center-campus-in-texas/",
            "https://www.keranews.org/science-technology/2023-09-01/google-is-growing-in-north-texas-with-new-data-center",
            "https://cleanview.co/data-centers/texas/1602/red-oak---building-1",
            "https://www.wfaa.com/article/money/business/google-40-billion-investment-in-texas-ellis-county/287-0bf6e355-b350-4c46-b706-6745e7cb7358",
        ],
    },
    "t5_data_centers_3375": {
        "nazwa": "T5@Atlanta, Lithia Springs, Douglas County, Georgia",
        "kamienie": [
            ("2018", "początek zagospodarowania terenu przy 1456 Trae Lane",
             "DCD"),
            ("2021", "zatwierdzenie wniosku dla obiektu 10-25 MW",
             "interconnection.fyi"),
            ("2024-08", "początek budowy T5@Atlanta III (budynki 3-5, "
                        "ok. 1,2 mln sq ft)", "datacenterhawk"),
            ("2025-06", "zadaszenie (topping out) T5@ATL III", "DCD"),
            ("2026-08", "planowane zakończenie T5@Atlanta III", "datacenterhawk"),
        ],
        "skala": "docelowo ok. 220 MW na ok. 80 akrach; T5@ATL III do 300 MW",
        "oczekiwanie": {
            S.ZIEMNE: "przed 2018 lub na początku szeregu - teren "
                      "zagospodarowywany od 2018",
            S.ROSNIE: "w szeregu widoczna kolejna faza od 2024H2",
            S.ZAMKNIETA: "część kampusu zamknięta wcześniej; III dopiero "
                         "w budowie do 2026",
        },
        "zrodla": [
            "https://www.datacenterdynamics.com/en/news/t5-and-corscale-top-out-data-centers-in-georgia-and-virginia/",
            "https://datacenterhawk.com/marketplace/providers/t5-data-centers/trae-lane/t5-atlanta-bldg-2",
            "https://baxtel.com/data-center/t5-atlanta-iii-campus",
            "https://www.interconnection.fyi/data-center/project/t5-data-centers-bb0cf2bf",
        ],
    },
}


# Ocena zgodnosci - wynik porownania, spisany po tym, jak policzylem oba
# obszary. Nie jest generowana automatycznie, bo wymaga zestawienia z trescia
# zrodel, ale kazde zdanie da sie sprawdzic w tabelach wyzej.
OCENA = {
    "google_3254": """
**Jak wypadlo porownanie.** Koniec budowy potok trafia: BRYLA ZAMKNIETA od
2025H1 wobec obiektu operacyjnego od 2025 r. Poczatek wykrywa na 2023H2, czyli
POL ROKU PRZED oficjalnym startem budowy (kwiecien 2024) i tuz PO ogloszeniu
inwestycji (sierpien 2023) - co jest zgodne z przygotowaniem terenu, ale nalezy
to czytac jako "okolice przelomu 2023/2024", nie jako date dzienna.

**To ten obszar pokazal powazny blad.** W pierwszej wersji roboty ziemne
wychodzily na 2021H2 - dwa i pol roku za wczesnie. Przyczyna: AOI bylo polem
uprawnym, a udzial golej ziemi skakal sezonowo (2019H1 16,5% -> 2019H2 49,7%
-> 2021H1 19,3% -> 2021H2 54,9% -> 2022H1 61,2% -> 2022H2 27,1%). Zaorka daje
55-61% golej ziemi i WRACA do zieleni, czego warunek "przyrost ponad poziom
wyjsciowy" nie odrozniał od wykopu. Stad wymog utrzymania sie podwyzszonego
gruntu przez trzy epoki (`BARE_PERSISTENCE_EPOCHS`).
""",
    "t5_data_centers_3375": """
**Jak wypadlo porownanie.** Potok widzi wczesna faze kampusu: roboty ziemne
i poczatek zabudowy w 2019H1, bryla zamknieta od 2020H2 - co odpowiada
budynkom oddanym na wczesnym etapie zagospodarowania terenu (od 2018).

**Czego NIE widzi: fazy z lat 2024-2026.** T5@Atlanta III ruszylo w sierpniu
2024 i ma sie skonczyc w sierpniu 2026, ale etap na wykresie stoi od 2020H2.
Powod jest wbudowany w konstrukcje: etapy sa NIEMALEJACE (zapadka), wiec raz
osiagnieta "bryla zamknieta" nie cofa sie i kolejna faza rozbudowy nie ma jak
sie pokazac jako zmiana etapu. Zapadka chroni przed migotaniem wyniku na
chmurach, ale kosztuje wlasnie to: ROZBUDOWA DOJRZALEGO KAMPUSU JEST NIEWIDOCZNA
w kolumnie etapu. Widac ja za to w krzywej udzialu zabudowy i na mapie
"kiedy pojawila sie zabudowa" - i tam nalezy jej szukac.
""",
}


def _wynik(sid: str):
    """Wczytaj wynik potoku dla obszaru (out/rows/<id>.json)."""
    p = os.path.join(C.OUT_DIR, "rows", f"{sid}.json")
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))


def porownanie(sid: str) -> dict:
    """Zestaw udokumentowane kamienie milowe z wykrytymi epokami."""
    f = FAKTY.get(sid)
    w = _wynik(sid)
    if not f or not w:
        return {}
    s = w["summary"]
    return {
        "id": sid,
        "nazwa": f["nazwa"],
        "kamienie": f["kamienie"],
        "skala": f["skala"],
        "oczekiwanie": f["oczekiwanie"],
        "zrodla": f["zrodla"],
        "wykryte": {
            S.ZIEMNE: s.get("t_earthworks"),
            S.ROSNIE: s.get("t_structures"),
            S.ZAMKNIETA: s.get("t_mature"),
            S.ZIELEN_U: s.get("t_green"),
        },
        "etap_koncowy": s.get("stage_name"),
        "postep": s.get("progress"),
        "cel": s.get("target_built_frac"),
        "zabudowa": s.get("built_frac"),
    }


def markdown(sid: str) -> str:
    """Narracja w markdownie — do notatnika i do README."""
    d = porownanie(sid)
    if not d:
        return f"**{sid}** — brak wyniku potoku (uruchom `run.py {sid}`)."

    L = [f"### {d['nazwa']}", "", f"*{d['skala']}*", "",
         "**Co mówią źródła:**", "",
         "| data | zdarzenie | źródło |", "|---|---|---|"]
    for data, opis, zr in d["kamienie"]:
        L.append(f"| {data} | {opis} | {zr} |")

    L += ["", "**Co wykrył potok:**", "",
          "| etap | oczekiwane ze źródeł | wykryte z Sentinela |",
          "|---|---|---|"]
    for st in (S.ZIEMNE, S.ROSNIE, S.ZAMKNIETA, S.ZIELEN_U):
        ocz = d["oczekiwanie"].get(st, "—")
        wyk = d["wykryte"].get(st) or "nie wykryto"
        L.append(f"| {S.STAGE_NAMES[st]} | {ocz} | **{wyk}** |")

    p = d["postep"]
    L += ["", f"Stan na koniec szeregu: **{d['etap_koncowy']}**, "
              f"zabudowa potwierdzona {d['zabudowa']*100:.1f}% rdzenia "
              f"przy celu {d['cel']*100:.1f}% "
              f"(postęp {p*100:.0f}%)." if p == p else ""]
    oc = OCENA.get(sid)
    if oc:
        L += ["", oc.strip()]
    L += ["", "Źródła: " + " · ".join(f"[{i+1}]({u})"
                                      for i, u in enumerate(d["zrodla"]))]
    return "\n".join(L)


def main(argv: list) -> int:
    ids = [s["id"] for s in C.SITES if s.get("control")] or list(FAKTY)
    brak = [i for i in ids if not _wynik(i)]
    if brak:
        print(f"brak wyników dla: {', '.join(brak)} — uruchom najpierw bieg\n")
    for sid in ids:
        print(markdown(sid))
        print("\n" + "-" * 70 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
