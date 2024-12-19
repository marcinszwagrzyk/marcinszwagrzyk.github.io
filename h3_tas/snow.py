import pandas as pd

# Załóżmy, że df ma kolumny: "date", "temp", "precip"
# Odczyt z pliku i parsowanie dat:
# df = pd.read_csv('dane.csv', parse_dates=['date'])
df = df.set_index('date').sort_index()

temp_threshold = 0.0   # Próg temperatury
melt_rate = 3.0        # mm/d/°C - przykladowa wartość z literatury

snowpack_list = []
previous_snowpack = 0.0

for idx, row in df.iterrows():
    t = row['temp']
    p = row['precip']
    
    if t <= temp_threshold:
        # Dodajemy śnieg tylko gdy temperatura ≤ 0°C
        # Topnienie przy temperaturach ujemnych zaniedbujemy (0 mm)
        current_snowpack = previous_snowpack + p
    else:
        # Gdy t > 0°C nie ma przyrostu śniegu
        # Następuje topnienie: melt_rate * t
        melted_amount = melt_rate * t
        current_snowpack = previous_snowpack - melted_amount
        if current_snowpack < 0:
            current_snowpack = 0

    snowpack_list.append(current_snowpack)
    previous_snowpack = current_snowpack

df['snowpack'] = snowpack_list

print(df[['temp', 'precip', 'snowpack']])
