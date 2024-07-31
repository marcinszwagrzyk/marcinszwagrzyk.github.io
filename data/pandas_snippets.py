# Ustaw indeks na date, state i company, aby ułatwić join
df.set_index(['date', 'state', 'company'], inplace=True)

# Kopiuj DataFrame i przesuń daty o rok do przodu
df_prev_year = df.copy()
df_prev_year.index = df_prev_year.index.set_levels(df_prev_year.index.get_level_values('date') + pd.DateOffset(years=1), level='date')

# Połącz oryginalny DataFrame z przesuniętym o rok
df_yoy = df.join(df_prev_year, rsuffix='_prev')

# Oblicz YoY
df_yoy['YoY'] = (df_yoy['value'] / df_yoy['value_prev']) - 1
df_yoy.reset_index(inplace=True)

# Opcjonalnie, odfiltruj tylko potrzebne kolumny
df_yoy = df_yoy[['date', 'state', 'company', 'YoY']]
