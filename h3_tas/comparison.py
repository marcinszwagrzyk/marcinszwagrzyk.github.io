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
