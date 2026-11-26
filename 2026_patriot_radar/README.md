# Zasięg radaru Patriot (AN/MPQ-65) nad Polską

Aplikacja w przeglądarce: stawiasz baterie Patriot na mapie i od razu widzisz, gdzie radar „widzi” cel lecący np. 100 / 200 / 500 m nad terenem.

**Demo:** https://marcinszwagrzyk.github.io/2026_patriot_radar/

- klik na mapie = nowa bateria (znacznik można przeciągać), wiele baterii = suma pokrycia
- parametry baterii: wysokość anteny, zasięg instrumentalny, sektor i azymut
- progi wysokości celu, rozdzielczość DEM (~100 / ~50 m), współczynnik refrakcji k
- odczyt pod kursorem: najniższa wysokość, od której cel jest widoczny
- powierzchnia pokrycia w legendzie; ustawienia zapisane w adresie URL (link do udostępnienia)

Model: linia wzroku po ~3600 promieniach z krzywizną Ziemi (k = 4/3), DEM Terrarium (AWS Open Data, głównie SRTM) bez lasów i zabudowy. To ograniczenie wynikające z ukształtowania terenu, a nie pełny model radaru (brak wielodrogowości, echa od terenu, zakłóceń, mocy i RCS celu).

Statyczny HTML + Leaflet, obliczenia w Web Workerze, bez backendu.
