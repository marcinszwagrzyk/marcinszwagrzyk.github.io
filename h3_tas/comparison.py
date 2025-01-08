import pandas as pd
import numpy as np

# Przykładowe dane
data = {
    'station_id': ['A', 'A', 'A', 'B', 'B', 'C', 'C', 'C', 'C'],
    'timestamp': [
        '2025-01-01', '2025-01-02', '2025-01-03',  # Stacja A
        '2025-01-01', '2025-01-03',                # Stacja B (brak 2025-01-02)
        '2025-01-01', '2025-01-02', '2025-01-03', '2025-01-04'  # Stacja C
    ],
    'value': [1, 2, 3, 4, 5, 6, 7, 8, 9]
}

# Konwersja danych na DataFrame
df = pd.DataFrame(data)
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Definiujemy pełny zakres czasu
start_date = df['timestamp'].min()
end_date = df['timestamp'].max()
full_time_range = pd.date_range(start=start_date, end=end_date, freq='D')

# Obliczamy pokrycie czasowe dla każdej stacji
results = []
for station_id, group in df.groupby('station_id'):
    station_time_range = group['timestamp']
    coverage = len(np.intersect1d(station_time_range, full_time_range)) / len(full_time_range)
    results.append({'station_id': station_id, 'coverage': coverage})

# Tworzymy DataFrame wynikowy
coverage_df = pd.DataFrame(results)

# Filtrujemy stacje z pokryciem >= 90%
stations_with_high_coverage = coverage_df[coverage_df['coverage'] >= 0.9]

print("Stacje z pełnym pokryciem czasowym (>90%):")
print(stations_with_high_coverage)








df["zgodnosc"] = (
    ((df["kolumna1"] > 0) & (df["kolumna2"] > 0)) |  # Obie dodatnie
    ((df["kolumna1"] < 0) & (df["kolumna2"] < 0))   # Obie ujemne
).astype(int)


# Upewnij się, że indeks to tygodniowy DateTimeIndex
df = df.asfreq('W')  # Ustaw częstotliwość indeksu na tygodniową, jeśli nie jest

# Wybrane kolumny do obliczenia YoY
columns_to_calculate = ["kolumna1", "kolumna2"]

# Oblicz dokładny YoY dla każdej kolumny
for col in columns_to_calculate:
    df[f"{col}_YoY"] = ((df[col] - df[col].shift(52)) / df[col].shift(52)) * 100

# Wyświetl dane
print(df)


import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score

# Przykładowe dane
np.random.seed(42)
data = {
    'Populacja X': np.random.normal(100, 15, 100),
    'Populacja Y': np.random.normal(110, 20, 100),
    'Prog': np.random.choice(['A', 'B', 'C'], 100)
}
df = pd.DataFrame(data)

# Grupowanie po kategorii 'Prog'
results = []
for prog, group in df.groupby('Prog'):
    mae = mean_absolute_error(group['Populacja X'], group['Populacja Y'])
    mape = mean_absolute_percentage_error(group['Populacja X'], group['Populacja Y'])
    r2 = r2_score(group['Populacja X'], group['Populacja Y'])

    results.append({
        'Prog': prog,
        'MAE': mae,
        'MAPE': mape,
        'R²': r2,
        'Średnia X': group['Populacja X'].mean(),
        'Średnia Y': group['Populacja Y'].mean()
    })

results_df = pd.DataFrame(results)

# Wykresy dla każdego progu
plt.figure(figsize=(15, 10))

for i, (prog, group) in enumerate(df.groupby('Prog')):
    plt.subplot(2, 2, i + 1)
    sns.scatterplot(x=group['Populacja X'], y=group['Populacja Y'], label=f'Prog {prog}')
    plt.plot([group['Populacja X'].min(), group['Populacja X'].max()],
             [group['Populacja X'].min(), group['Populacja X'].max()], 'r--', label='Idealna linia')
    plt.xlabel('Populacja X')
    plt.ylabel('Populacja Y')
    plt.title(f'Wykres punktowy dla progu {prog}')
    plt.legend()

# Boxplots
for i, (prog, group) in enumerate(df.groupby('Prog')):
    plt.subplot(3, 3, i + 4)
    sns.boxplot(data=group[['Populacja X', 'Populacja Y']], orient='h', palette='pastel')
    plt.title(f'Boxplot dla progu {prog}')
    plt.yticks([0, 1], ['Populacja X', 'Populacja Y'])

# Histograms
for i, (prog, group) in enumerate(df.groupby('Prog')):
    plt.subplot(3, 3, i + 7)
    sns.histplot(group['Populacja X'], kde=True, color='blue', label='Populacja X', alpha=0.6, bins=15)
    sns.histplot(group['Populacja Y'], kde=True, color='orange', label='Populacja Y', alpha=0.6, bins=15)
    plt.title(f'Histogram dla progu {prog}')
    plt.legend()

plt.tight_layout()
plt.show()

# Wyświetlenie tabeli wyników
print(results_df)
