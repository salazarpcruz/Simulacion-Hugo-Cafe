import pandas as pd

file_path = r"c:\Proyectos antigvty\Simulador\HUGO_CAFE_DataFase1-4.xlsx"

try:
    df_prob = pd.read_excel(file_path, sheet_name='Probabilidades')
    print("--- Sheet 'Probabilidades' ---")
    print(df_prob.head(20).to_string())
except Exception as e:
    print("Error reading Probabilidades:", e)

try:
    df_fit = pd.read_excel(file_path, sheet_name='Bondad_Ajuste')
    print("\n--- Sheet 'Bondad_Ajuste' ---")
    print(df_fit.head(20).to_string())
except Exception as e:
    print("Error reading Bondad_Ajuste:", e)
