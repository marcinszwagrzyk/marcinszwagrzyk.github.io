spark.sql("""
SELECT p.*, pl.id_poligonu, pl.nazwa_poligonu
FROM punkty p, poligony pl
WHERE ST_Intersects(p.geometria, pl.geometria)
""").show()
