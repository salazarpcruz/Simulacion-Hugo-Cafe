import pandas as pd

file_path = r"c:\Proyectos antigvty\Simulador\HUGO_CAFE_DataFase1-4.xlsx"
df = pd.read_excel(file_path, sheet_name='Base_Recoleccion_350', header=3)

# 1. Clean column names (strip spaces, resolve encoding if any)
df.columns = [c.strip() for c in df.columns]

# 2. Check for negative times
time_cols = ['Interarribo_min', 'Toma_Pedido_min', 'Comanda_min', 'Preparacion_min', 
             'Consumo_min', 'Pago_min', 'Tiempo_Reocupacion_Mesa_min', 
             'Tiempo_Total_Mesa_min', 'Tiempo_Total_Sistema_min']

print("Negative values check:")
for col in time_cols:
    negatives = df[df[col] < 0]
    print(f" - {col}: {len(negatives)} negative rows")

# 3. Check tables and capacity in data
print("\nUnique tables and their capacities in dataset:")
table_caps = df.groupby(['Mesa', 'Capacidad_Mesa', 'Zona_Mesa']).size().reset_index(name='Count')
print(table_caps)

# 4. Check model rules violations in data:
# Rules: T1, T2, T3 have capacity 2. T4, T5 have capacity 3.
# Groups of 3 can only go to T4 or T5. Groups of 4 are operational exceptions.
print("\nChecking groups of 3 and where they sit:")
g3 = df[df['Grupo'] == 3]
print(g3.groupby('Mesa').size().reset_index(name='Count'))

print("\nChecking groups of 4 and where they sit:")
g4 = df[df['Grupo'] == 4]
print(g4.groupby(['Mesa', 'Observaciones']).size().reset_index(name='Count'))

# 5. Check if there are groups of size > 4
print("\nGroup size distribution:")
print(df['Grupo'].value_counts())

# 6. Check main process paths (Ruta_Principal)
print("\nProcess paths:")
print(df['Ruta_Principal'].value_counts())
