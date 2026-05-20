import os
import data_processing
import simulation_engine

def run_tests():
    excel_path = r"c:\Proyectos antigvty\Simulador\HUGO_CAFE_DataFase1-4.xlsx"
    print("--- 1. Testing Data Loading and Validation ---")
    if not os.path.exists(excel_path):
        print(f"Excel file not found at {excel_path}")
        return
        
    df, val = data_processing.load_and_validate_data(excel_path)
    print("Ingestion Success:", val["success"])
    print("Validation Errors:")
    for err in val["errors"]:
        print(" ERROR:", err)
    print("Validation Warnings:")
    for warn in val["warnings"]:
        print(" WARNING:", warn)
        
    if not val["success"]:
        # Print actual columns to debug
        import pandas as pd
        df_raw = pd.read_excel(excel_path, sheet_name='Base_Recoleccion_350', header=3)
        print("\nActual Columns loaded from file:")
        print(df_raw.columns.tolist())
        return

    print("\n--- 2. Testing Statistical Distribution Fitting ---")
    try:
        fits = data_processing.fit_distributions(df)
        print("Distribution Fitting: SUCCESS")
        print("Interarrival Best Distribution:", fits["Interarribo_min"]["best"])
        print("Preparación Best Distribution:", fits["Preparacion_min"]["best"])
    except Exception as e:
        print("Distribution Fitting: FAILED with error:", str(e))
        import traceback
        traceback.print_exc()
        return

    print("\n--- 3. Testing SimPy Discrete Event Simulation Run ---")
    try:
        # Construct chosen distributions dict
        selected_dists = {}
        for col, fit_res in fits.items():
            if "best" in fit_res:
                selected_dists[col] = fit_res["best"]
                
        results, log = simulation_engine.run_multi_simulation(
            runs_count=5,
            fits=fits,
            selected_dists=selected_dists,
            max_groups=350,
            kitchen_cap=2,
            checkout_cap=1
        )
        print("Simulation Run: SUCCESS")
        print("Groups Served (Mean):", results["ci_95"]["groups_served"]["mean"])
        print("Average System Time (Mean):", results["ci_95"]["avg_system"]["mean"])
        print("Kitchen Utilization (Mean):", results["ci_95"]["kitchen_util"]["mean"])
        print("Checkout Utilization (Mean):", results["ci_95"]["checkout_util"]["mean"])
        print("Events Logged in First Run:", len(log))
        print("\nINTEGRATION TESTS PASSED SUCCESSFULLY!")
    except Exception as e:
        print("Simulation Run: FAILED with error:", str(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_tests()
