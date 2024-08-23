
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


from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC

# Generowanie danych
X, y = make_classification(n_samples=1000, n_features=20, n_informative=2, n_redundant=10, random_state=42)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Lista modeli do przetestowania
models = [
    ('LogisticRegression', LogisticRegression()),
    ('RandomForest', RandomForestClassifier()),
    ('GradientBoosting', GradientBoostingClassifier()),
    ('SVC', SVC())
]

# Pętla do oceny każdego modelu
results = []
model_names = []
for name, model in models:
    pipeline = Pipeline([
        ('scaler', StandardScaler()),  # Wszystkie dane będą normalizowane
        ('classifier', model)
    ])
    cv_scores = cross_val_score(pipeline, X_train, y_train, cv=5, scoring='accuracy')  # Można zmienić 'accuracy' na inną metrykę
    results.append(cv_scores)
    model_names.append(name)
    print(f"{name}: {cv_scores.mean()} +/- {cv_scores.std()}")

# Opcjonalnie, można użyć biblioteki matplotlib do wizualizacji wyników
import matplotlib.pyplot as plt

fig = plt.figure()
fig.suptitle('Porównanie modeli')
ax = fig.add_subplot(111)
plt.boxplot(results)
ax.set_xticklabels(model_names)
plt.show()



# regresja
from sklearn.datasets import make_regression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.svm import SVR

# Generowanie danych
X, y = make_regression(n_samples=1000, n_features=20, n_informative=10, noise=0.2, random_state=42)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Lista modeli do przetestowania
models = [
    ('LinearRegression', LinearRegression()),
    ('RandomForestRegressor', RandomForestRegressor()),
    ('GradientBoostingRegressor', GradientBoostingRegressor()),
    ('SVR', SVR())
]

# Pętla do oceny każdego modelu
results = []
model_names = []
for name, model in models:
    pipeline = Pipeline([
        ('scaler', StandardScaler()),  # Normalizacja danych
        ('regressor', model)
    ])
    cv_scores = cross_val_score(pipeline, X_train, y_train, cv=5, scoring='neg_mean_squared_error')  # Użyj MSE jako metryki
    results.append(cv_scores)
    model_names.append(name)
    print(f"{name}: {cv_scores.mean()} +/- {cv_scores.std()}")

# Opcjonalnie, wizualizacja wyników
import matplotlib.pyplot as plt

fig = plt.figure()
fig.suptitle('Porównanie modeli regresji')
ax = fig.add_subplot(111)
plt.boxplot(results)
ax.set_xticklabels(model_names)
plt.show()



from sklearn.model_selection import GridSearchCV

grid={"C":np.logspace(-3,3,7), "penalty":["l2"]} # l2 ridge
logreg=LogisticRegression()
logreg_cv=GridSearchCV(logreg, grid, scoring='roc_auc',cv=10)

import pickle

# Zapisz model do pliku
with open('model_pipeline.pkl', 'wb') as file:
    pickle.dump(model, file)

# Wczytaj model z pliku
with open('model_pipeline.pkl', 'rb') as file:
    model = pickle.load(file)


# Discretize the 'Age' variable into bins
bins = [0, 20, 30, 40, 50, 60, 70]
labels = ['0-20', '21-30', '31-40', '41-50', '51-60', '61-70']
df['Age Group'] = pd.cut(df['Age'], bins=bins, labels=labels, right=False)

# Create the boxplot
plt.figure(figsize=(10, 6))
sns.boxplot(x='Age Group', y='Salary', data=df)
plt.title('Salary Distribution by Age Group')
plt.xlabel('Age Group')
plt.ylabel('Salary')
plt.show()


for index, row in df.iterrows():
			sensor_id = row.sensor_id
      df.loc[index, 'kolumna'] = wartosc