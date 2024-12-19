import pandas as pd

# Załóżmy, że DataFrame (df) ma kolumny:
# "date", "temp", "precip"
# Odczyt z pliku i parsowanie dat:
# df = pd.read_csv('dane.csv', parse_dates=['date'])
df = df.set_index('date').sort_index()

# Parametry modelu
temp_threshold = 0.0   # Próg temperatury, poniżej którego opad to śnieg
                       # Przyjmijmy np. 0°C, choć w literaturze stosuje się i inne wartości

# Wybór współczynnika topnienia (DDF - Degree-Day Factor)
# Literaturowo wartości wahają się np. 2-6 mm/°C/dzień dla śniegu
# Przyjmijmy wartość początkową 3 mm/°C/dzień i będziemy ją kalibrować
melt_rate = 3.0  # mm/d/°C - wartość przykładowa z literatury

# Opcjonalnie: skalibruj melt_rate na podstawie lokalnych danych obserwacyjnych.
# Proces kalibracji:
# 1. Mamy serię obserwowaną pokrywy śnieżnej (snow_obs), np. z pomiarów.
# 2. Dla różnych wartości melt_rate dokonujemy symulacji i sprawdzamy błąd (np. RMSE).
# 3. Wybieramy tę wartość melt_rate, która minimalizuje błąd.
# To wykracza poza prosty przykład, ale w praktyce wykorzystywane są metody optymalizacji (np. scipy.optimize).

# Tutaj jednak prezentujemy tylko samą symulację z założonym melt_rate.

snowpack_list = []
previous_snowpack = 0.0

for idx, row in df.iterrows():
    t = row['temp']
    p = row['precip']
    
    if t <= temp_threshold:
        # Opad uznawany za śnieg – dodaj do pokrywy
        current_snowpack = previous_snowpack + p
    else:
        # Dodatnia temperatura – topnienie wg metody degree-day
        melted_amount = melt_rate * t
        current_snowpack = previous_snowpack - melted_amount
        if current_snowpack < 0:
            current_snowpack = 0

    snowpack_list.append(current_snowpack)
    previous_snowpack = current_snowpack

df['snowpack'] = snowpack_list

print(df[['temp', 'precip', 'snowpack']])
