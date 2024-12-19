import pandas as pd

# Załóżmy, że DataFrame ma kolumny:
# "date", "temp", "precip"
# i jest już wczytany np. z CSV:
# df = pd.read_csv('dane.csv', parse_dates=['date'])

# Ustaw datę jako indeks (o ile nie jest już ustawiona)
df = df.set_index('date').sort_index()

temp_threshold = 0.0  # próg temperatury
melt_rate = 0.5       # współczynnik topnienia

# Inicjalizacja kolumny na pokrywę śnieżną
snowpack_list = []

previous_snowpack = 0.0
for idx, row in df.iterrows():
    t = row['temp']
    p = row['precip']
    
    if t <= temp_threshold:
        # Dodajemy śnieg do pokrywy
        current_snowpack = previous_snowpack + p
    else:
        # Topnienie śniegu
        melted_amount = melt_rate * t
        current_snowpack = previous_snowpack - melted_amount
        if current_snowpack < 0:
            current_snowpack = 0

    snowpack_list.append(current_snowpack)
    previous_snowpack = current_snowpack

df['snowpack'] = snowpack_list

print(df)
