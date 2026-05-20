import pandas as pd

file_path = r"c:\Proyectos antigvty\Simulador\HUGO_CAFE_DataFase1-4.xlsx"
df = pd.read_excel(file_path, sheet_name='Base_Recoleccion_350', header=3)

print("Columns:")
print(df.columns.tolist())
print("\nShape:", df.shape)
print("\nFirst 3 rows:")
print(df.head(3).to_string())
print("\nData Types:")
print(df.dtypes)
print("\nSummary stats:")
print(df.describe().to_string())
