import pandas as pd

file_path = r"c:\Proyectos antigvty\Simulador\HUGO_CAFE_DataFase1-4.xlsx"
df_dict = pd.read_excel(file_path, sheet_name='Diccionario_Datos')

print("Diccionario de Datos:")
print(df_dict.to_string())
