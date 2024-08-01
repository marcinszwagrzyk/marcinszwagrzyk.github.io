
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
