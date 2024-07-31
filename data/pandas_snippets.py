# Połącz na podstawie daty poprzedniego roku, stanu i firmy
df_merged = df.merge(df, left_on=['prev_year_date', 'state', 'company'], right_on=['date', 'state', 'company'], suffixes=('', '_prev'))

# Oblicz metrykę YoY
df_merged['YoY'] = (df_merged['value'] / df_merged['value_prev']) - 1

# Wyświetl wyniki
print(df_merged[['date_x', 'state', 'company', 'value', 'value_prev', 'YoY']])
