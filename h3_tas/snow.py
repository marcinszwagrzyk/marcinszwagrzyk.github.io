import pandas as pd

# Załóżmy, że DataFrame (df) ma kolumny:
# "date" (data), "temp" (średnia dobowa temperatura) i "precip" (dobowy opad)
# Przykład wczytania: df = pd.read_csv('dane.csv', parse_dates=['date'])
df = df.set_index('date').sort_index()

snowpack = 0.0
snowpack_list = []

for idx, row in df.iterrows():
    t = row['temp']
    p = row['precip']
    
    if t <= 0:
        # Dodajemy śnieg do pokrywy
        snowpack += p
    else:
        # Odejmuje śnieg - topnienie
        snowpack -= p
        if snowpack < 0:
            snowpack = 0
    
    snowpack_list.append(snowpack)

df['snowpack'] = snowpack_list

print(df[['temp', 'precip', 'snowpack']])
