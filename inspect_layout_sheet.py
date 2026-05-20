import pandas as pd

file_path = r"c:\Proyectos antigvty\Simulador\HUGO_CAFE_DataFase1-4.xlsx"
df_layout = pd.read_excel(file_path, sheet_name='Layout_Rutas')

print("Remaining rows of Layout_Rutas sheet:")
print(df_layout.iloc[14:].to_string())
