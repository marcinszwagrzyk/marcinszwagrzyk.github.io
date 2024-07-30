import pandas as pd

# Przykładowy DataFrame
data = {
    'data': ['2023-01-01', '2023-02-01', '2023-03-01', '2023-04-01', '2023-05-01',
             '2023-06-01', '2023-07-01', '2023-08-01', '2023-09-01', '2023-10-01',
             '2023-11-01', '2023-12-01', '2024-01-01', '2024-02-01', '2024-03-01'],
    'firma': ['A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A'],
    'stan': ['X', 'X', 'X', 'X', 'X', 'X', 'X', 'X', 'X', 'X', 'X', 'X', 'X', 'X', 'X'],
    'kategoria': ['K1', 'K1', 'K1', 'K1', 'K1', 'K1', 'K1', 'K1', 'K1', 'K1', 'K1', 'K1', 'K1', 'K1', 'K1'],
    'rodzaj': ['R1', 'R1', 'R1', 'R1', 'R1', 'R1', 'R1', 'R1', 'R1', 'R1', 'R1', 'R1', 'R1', 'R1', 'R1'],
    'value': [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150]
}

df = pd.DataFrame(data)

# Upewniamy się, że kolumna data jest typu datetime
df['data'] = pd.to_datetime(df['data'])

# Sortujemy DataFrame według kolumny data
df = df.sort_values('data')

# Grupujemy według firma, stan, kategoria, rodzaj
grouped = df.groupby(['firma', 'stan', 'kategoria', 'rodzaj'])

# Obliczamy kroczącą sumę 12-miesięczną dla każdej grupy
df['rolling_sum_12m'] = grouped['value'].rolling(window=12, min_periods=1).sum().reset_index(level=[0,1,2,3], drop=True)

print(df)
