# intersect
spark.sql("""
SELECT p.*, pl.id_poligonu, pl.nazwa_poligonu
FROM punkty p, poligony pl
WHERE ST_Intersects(p.geometria, pl.geometria)
""").show()

# centroids
val result = spark.sql("""
SELECT ST_Centroid(geometry) AS centroid_geometry
FROM polygons
""")
result.show()

# transform
val transformed = spark.sql("""
SELECT ST_Transform(geometry, 'EPSG:4326', 'EPSG:3035') AS transformed_geometry
FROM spatial_data
""")
transformed.show()


-- Wykorzystaj SQL do stworzenia tabeli z geometrią
spark.sql("""
    CREATE OR REPLACE TEMP VIEW sedona_points_with_geom AS
    SELECT 
        id, 
        latitude, 
        longitude, 
        ST_Point(CAST(longitude AS Decimal(24, 20)), CAST(latitude AS Decimal(24, 20))) AS geom
    FROM sedona_points
""")
