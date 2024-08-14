
df['prev_year_date'] = df['date'] - pd.DateOffset(years=1)

# Połącz na podstawie daty poprzedniego roku, stanu i firmy
df_merged = df.merge(df, left_on=['prev_year_date', 'state', 'company'], right_on=['date', 'state', 'company'], suffixes=('', '_prev'))

# Oblicz metrykę YoY
df_merged['YoY'] = (df_merged['value'] / df_merged['value_prev']) - 1

# Wyświetl wyniki
print(df_merged[['date_x', 'state', 'company', 'value', 'value_prev', 'YoY']])



# Zachowujemy kolumny 'a', 'b', 'c' i "topimy" kolumny 'x', 'y', 'z'
df_melted = df.melt(id_vars=['a', 'b', 'c'], value_vars=['x', 'y', 'z'], var_name='column_name', value_name='value')

print(df_melted)


# renaming
df['kolumna1'] = df['kolumna1'].str.replace('strin1', 'strin2', regex=False)

# renaming
zamiany = {'strin1': 'strin2', 'jest': 'był'}
df['kolumna1'] = df['kolumna1'].replace(zamiany, regex=False)

scaler = StandardScaler()
scaler.fit(df_data_winter_joined[features])
X_scaled = scaler.transform(df_data_winter_joined[features])


from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score
from imblearn.over_sampling import SMOTE
from imblearn.pipeline import make_pipeline as make_pipeline_imblearn

# Przykład danych (załóżmy że już są podzielone)
# X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Tworzenie pipeline z użyciem SMOTE
pipeline = make_pipeline_imblearn(
    StandardScaler(),
    SMOTE(random_state=42),  # Możesz dostosować parametry SMOTE według potrzeb
    LogisticRegression()
)

# Trenowanie modelu
pipeline.fit(X_train, y_train)

# Przewidywanie na danych testowych
y_pred = pipeline.predict(X_test)

# Ocena modelu
print("Accuracy:", accuracy_score(y_test, y_pred))
print(classification_report(y_test, y_pred))


