"""End-to-end integration test for HUGO CAFE simulation modules."""
import os
import sys
import numpy as np

import data_processing
import simulation_engine


def run_tests():
    excel = r"c:\Proyectos antigvty\Simulador\HUGO_CAFE_DataFase1-4.xlsx"

    print("--- 1. Data Loading & Validation ---")
    if not os.path.exists(excel):
        print(f"  FAIL: file not found: {excel}")
        return
    df, val = data_processing.load_and_validate_data(excel)
    assert val["success"], f"Validation failed: {val['errors']}"
    print(f"  OK: {val['metrics']['total_records']} records loaded.")
    if val["warnings"]:
        for w in val["warnings"]:
            print(f"  WARN: {w}")
    print(f"  Avg Interarrival: {val['metrics']['average_interarrival']:.2f} min")
    print(f"  Avg Table Time:   {val['metrics']['average_table_time']:.2f} min")
    print(f"  Avg System Time:  {val['metrics']['average_system_time']:.2f} min")

    print("\n--- 2. Distribution Fitting ---")
    fits = data_processing.fit_distributions(df)
    for col, res in fits.items():
        best = res.get("best", "?")
        print(f"  {col}: best = {best}")

    print("\n--- 3. Multi-Run Simulation (waiter_cap=2) ---")
    user_dists = {}
    for col in ['Interarribo_min', 'Toma_Pedido_min', 'Preparacion_min',
                 'Consumo_min', 'Pago_min', 'Tiempo_Reocupacion_Mesa_min']:
        user_dists[col] = fits[col]['best']
    user_dists['Comanda_min'] = 'empirical_discrete'

    results, event_log = simulation_engine.run_multi_simulation(
        runs_count=5,
        fits=fits,
        selected_dists=user_dists,
        max_groups=len(df),
        kitchen_cap=2,
        checkout_cap=1,
        waiter_cap=2)

    ci = results["ci_95"]
    print(f"  Runs:           {results['runs_count']}")
    print(f"  Groups served:  {ci['groups_served']['mean']:.0f}")
    print(f"  Avg wait:       {ci['avg_wait']['mean']:.2f} min")
    print(f"  Avg system:     {ci['avg_system']['mean']:.1f} min")
    print(f"  Kitchen util:   {ci['kitchen_util']['mean']*100:.1f}%")
    print(f"  Checkout util:  {ci['checkout_util']['mean']*100:.1f}%")
    print(f"  Waiter util:    {ci['waiter_util']['mean']*100:.1f}%")
    print(f"  Avg table time: {ci['avg_table_time']['mean']:.1f} min")
    print(f"  Avg waiter wt:  {ci['avg_waiter_wait']['mean']:.2f} min")
    print(f"  Avg kitchen wt: {ci['avg_kitchen_wait']['mean']:.2f} min")
    print(f"  Avg checkout wt:{ci['avg_checkout_wait']['mean']:.2f} min")
    print(f"  Exceptions:     {ci['exceptions']['mean']:.0f}")

    assert ci['groups_served']['mean'] > 0, "No groups served!"
    assert len(event_log) > 0, "Event log is empty!"
    print(f"  Event log entries: {len(event_log)}")

    print("\n=== ALL TESTS PASSED ===")


if __name__ == "__main__":
    run_tests()
