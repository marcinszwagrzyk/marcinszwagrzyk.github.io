import pandas as pd

# Załóżmy, że DataFrame (df) jest wczytany z kolumnami "date", "temp", "precip"
# df = pd.read_csv('dane.csv', parse_dates=['date'])
df = df.set_index('date').sort_index()

# Parametry
temp_threshold = 0.0       # Próg temperatury rozróżniający śnieg/deszcz
melt_rate = 3.0            # mm/°C/dzień topnienia
density_new_snow = 100.0   # kg/m³ dla świeżego śniegu
density_snow = 200.0       # początkowa średnia gęstość śniegu
density_max = 300.0        # maks. gęstość śniegu po kompresji
compression_rate = 5.0     # kg/m³/dzień wzrost gęstości przy braku nowego śniegu i temp ≤0°C

# Zmienna przechowująca masę śniegu w kg/m² (równa mm w.e.)
# 1 mm w.e. = 1 kg/m²
snowpack_mass = 0.0

snowpack_cm_list = []
snowpack_in_list = []

for idx, row in df.iterrows():
    t = row['temp']
    p = row['precip']  # mm w.e. opadu
    
    # Dzień zimny
    if t <= temp_threshold:
        if p > 0:
            # Dodaj nowy śnieg
            # Stara warstwa:
            old_mass = snowpack_mass
            old_thickness = old_mass / density_snow  # grubość starego śniegu w m
            
            # Nowy śnieg:
            new_mass = p  # kg/m²
            new_thickness = new_mass / density_new_snow
            
            # Suma:
            total_mass = old_mass + new_mass
            total_thickness = old_thickness + new_thickness
            
            # Nowa gęstość to masowy średni stosunek:
            if total_mass > 0:
                density_snow = total_mass / total_thickness
            
            snowpack_mass = total_mass
        else:
            # Brak nowego śniegu - kompresja
            # Masa ta sama, gęstość rośnie do pewnego limitu
            if snowpack_mass > 0:
                density_snow = min(density_snow + compression_rate, density_max)
            # masa bez zmian
    else:
        # Temp > 0°C: topnienie
        # Nie powstaje nowy śnieg
        melted_amount = melt_rate * t
        snowpack_mass = max(0, snowpack_mass - melted_amount)
        # Gęstości nie zmieniamy - w uproszczeniu

    # Oblicz grubość pokrywy śnieżnej na koniec dnia
    if snowpack_mass > 0 and density_snow > 0:
        thickness_m = snowpack_mass / density_snow
    else:
        thickness_m = 0.0

    thickness_cm = thickness_m * 100.0
    thickness_in = thickness_m * 39.3701

    snowpack_cm_list.append(thickness_cm)
    snowpack_in_list.append(thickness_in)

df['snowpack_cm'] = snowpack_cm_list
df['snowpack_in'] = snowpack_in_list

print(df[['temp', 'precip', 'snowpack_cm', 'snowpack_in']])
