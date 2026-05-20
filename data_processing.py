import pandas as pd
import numpy as np
import scipy.stats as stats
import openpyxl

def load_and_validate_data(file_path):
    """
    Loads operational Excel data from HUGO CAFÉ simulation project and validates it.
    Expected sheet: 'Base_Recoleccion_350'
    Expected headers: row 3 (0-indexed) or row 4 (1-indexed) in the sheet.
    """
    validation = {
        "success": True,
        "errors": [],
        "warnings": [],
        "metrics": {}
    }
    
    try:
        # Load the Excel file
        xl = pd.ExcelFile(file_path)
        if 'Base_Recoleccion_350' not in xl.sheet_names:
            validation["success"] = False
            validation["errors"].append("La hoja 'Base_Recoleccion_350' no existe en el archivo Excel.")
            return None, validation
            
        df = pd.read_excel(file_path, sheet_name='Base_Recoleccion_350', header=3)
        
        # Clean column names (strip whitespace and standardise characters)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Solve common encoding/spelling differences for Spanish
        rename_dict = {}
        for col in df.columns:
            col_clean = str(col).strip()
            col_lower = col_clean.lower()
            
            # Match "Tipo_Dia" / "Tipo Día" / "Tipo_Da" (e.g. "tipo_da" or "tipo_da")
            if 'tipo' in col_lower and ('dia' in col_lower or 'da' in col_lower or ('d' in col_lower and 'a' in col_lower and len(col_lower) <= 10)):
                rename_dict[col] = 'Tipo_Dia'
            # Match "Dia" / "Día" / "Da" (must be very short, e.g. length <= 4, e.g. "da" or "da")
            elif ('dia' in col_lower or 'da' in col_lower or ('d' in col_lower and 'a' in col_lower)) and len(col_lower) <= 4:
                rename_dict[col] = 'Dia'
            elif 'reocupacion' in col_lower or 'reocupaci' in col_lower:
                rename_dict[col] = 'Tiempo_Reocupacion_Mesa_min'
            elif 'total_mesa' in col_lower or ('total' in col_lower and 'mesa' in col_lower):
                rename_dict[col] = 'Tiempo_Total_Mesa_min'
            elif 'total_sistema' in col_lower or ('total' in col_lower and 'sistema' in col_lower):
                rename_dict[col] = 'Tiempo_Total_Sistema_min'
            elif 'preparacion' in col_lower or 'preparaci' in col_lower:
                rename_dict[col] = 'Preparacion_min'
            elif 'toma_pedido' in col_lower or ('toma' in col_lower and 'pedido' in col_lower):
                rename_dict[col] = 'Toma_Pedido_min'
                
        df.rename(columns=rename_dict, inplace=True)
        
        # Required columns list
        required_cols = [
            'ID', 'Semana', 'Fecha', 'Dia', 'Tipo_Dia', 'Hora_Llegada', 'Franja_Horaria',
            'Interarribo_min', 'Grupo', 'Mesa', 'Zona_Mesa', 'Capacidad_Mesa',
            'Toma_Pedido_min', 'Comanda_min', 'Preparacion_min', 'Consumo_min', 'Pago_min',
            'Tiempo_Reocupacion_Mesa_min', 'Tiempo_Total_Mesa_min', 'Ruta_Principal', 'Distancia_Ruta_m'
        ]
        
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            validation["success"] = False
            validation["errors"].append(f"Faltan columnas requeridas en el archivo: {', '.join(missing_cols)}")
            return None, validation
            
        # Clean data: drop rows where ID or other key fields are null
        df = df.dropna(subset=['ID', 'Interarribo_min', 'Grupo', 'Mesa'])
        df['ID'] = df['ID'].astype(int)
        df['Grupo'] = df['Grupo'].astype(int)
        df['Capacidad_Mesa'] = df['Capacidad_Mesa'].astype(int)
        df['Comanda_min'] = df['Comanda_min'].astype(int)
        
        # 1. Validation: Negative times
        time_cols = [
            'Interarribo_min', 'Toma_Pedido_min', 'Comanda_min', 'Preparacion_min',
            'Consumo_min', 'Pago_min', 'Tiempo_Reocupacion_Mesa_min'
        ]
        
        for col in time_cols:
            negatives = df[df[col] < 0]
            if not negatives.empty:
                validation["warnings"].append(
                    f"La columna '{col}' contiene {len(negatives)} filas con valores negativos (serán reemplazados por 0)."
                )
                df.loc[df[col] < 0, col] = 0.0

        # 2. Validation: Rule checks (T1-T3 capacity 2, T4-T5 capacity 3)
        valid_tables = {'T1': 2, 'T2': 2, 'T3': 2, 'T4': 3, 'T5': 3}
        for table, cap in valid_tables.items():
            table_rows = df[df['Mesa'] == table]
            incorrect_cap = table_rows[table_rows['Capacidad_Mesa'] != cap]
            if not incorrect_cap.empty:
                validation["warnings"].append(
                    f"Mesa {table} debe tener capacidad {cap}, pero se encontraron {len(incorrect_cap)} registros con capacidad incorrecta en los datos."
                )

        # 3. Validation: Group 3 table assignment rule
        g3_rows = df[df['Grupo'] == 3]
        g3_invalid = g3_rows[~g3_rows['Mesa'].isin(['T4', 'T5'])]
        if not g3_invalid.empty:
            validation["warnings"].append(
                f"Se detectaron {len(g3_invalid)} grupos de 3 personas asignados a mesas de capacidad 2 (T1, T2 o T3)."
            )

        # 4. Validation: Group 4 exceptions
        g4_rows = df[df['Grupo'] == 4]
        g4_no_ex = g4_rows[~g4_rows['Observaciones'].str.contains('exception|excepción', case=False, na=True)]
        if len(g4_no_ex) > 0:
            validation["warnings"].append(
                f"Se detectaron {len(g4_no_ex)} grupos de 4 personas que no tienen marcada la nota de excepción en observaciones."
            )
            
        # Summary metrics
        validation["metrics"] = {
            "total_records": len(df),
            "groups_by_size": df['Grupo'].value_counts().to_dict(),
            "tables_count": df['Mesa'].value_counts().to_dict(),
            "average_interarrival": float(df['Interarribo_min'].mean()),
            "average_table_time": float(df['Tiempo_Total_Mesa_min'].mean()),
            "total_exceptions": int((df['Grupo'] == 4).sum())
        }
        
        return df, validation
        
    except Exception as e:
        validation["success"] = False
        validation["errors"].append(f"Error al leer el archivo Excel: {str(e)}")
        return None, validation

def fit_single_distribution(data, col_name):
    """
    Fits Exponential, Lognormal, and Triangular distributions to the data.
    Performs KS test and returns parameters and p-values.
    """
    results = {}
    data = data[data > 0] # Filter positive values for statistical fitting
    
    if len(data) < 5:
        return {
            "best": "empirical",
            "empirical": {"data": data.tolist()}
        }
        
    # --- 1. Exponential Fit ---
    try:
        loc_exp, scale_exp = stats.expon.fit(data)
        ks_exp = stats.kstest(data, 'expon', args=(loc_exp, scale_exp))
        results['exponential'] = {
            "params": {"loc": float(loc_exp), "scale": float(scale_exp)},
            "p_value": float(ks_exp.pvalue),
            "statistic": float(ks_exp.statistic)
        }
    except Exception:
        results['exponential'] = {"p_value": 0.0, "params": {}}
        
    # --- 2. Lognormal Fit (floc=0 for strictly positive time durations) ---
    try:
        shape_log, loc_log, scale_log = stats.lognorm.fit(data, floc=0)
        ks_log = stats.kstest(data, 'lognorm', args=(shape_log, loc_log, scale_log))
        results['lognormal'] = {
            "params": {"s": float(shape_log), "loc": float(loc_log), "scale": float(scale_log)},
            "p_value": float(ks_log.pvalue),
            "statistic": float(ks_log.statistic)
        }
    except Exception:
        results['lognormal'] = {"p_value": 0.0, "params": {}}

    # --- 3. Triangular Fit ---
    try:
        c_tri, loc_tri, scale_tri = stats.triang.fit(data)
        ks_tri = stats.kstest(data, 'triang', args=(c_tri, loc_tri, scale_tri))
        results['triangular'] = {
            "params": {"c": float(c_tri), "loc": float(loc_tri), "scale": float(scale_tri)},
            "p_value": float(ks_tri.pvalue),
            "statistic": float(ks_tri.statistic)
        }
    except Exception:
        results['triangular'] = {"p_value": 0.0, "params": {}}

    # --- 4. Empirical Fallback ---
    results['empirical'] = {
        "params": {"observed_values": data.tolist()},
        "p_value": 1.0,
        "statistic": 0.0
    }
    
    # Determine the best-fit theoretical distribution
    best_dist = 'empirical'
    best_p = -1.0
    
    # Check if a theoretical candidate is valid (we prefer theoretical if p > 0.05)
    candidates = ['lognormal', 'triangular', 'exponential']
    for cand in candidates:
        if cand in results and results[cand]["p_value"] > 0.05:
            if results[cand]["p_value"] > best_p:
                best_p = results[cand]["p_value"]
                best_dist = cand
                
    # If no theoretical distribution has p > 0.05, select empirical
    results['best'] = best_dist
    
    return results

def fit_distributions(df):
    """
    Fits statistical distributions for all process times in HUGO CAFÉ dataset.
    """
    fit_cols = [
        'Interarribo_min', 'Toma_Pedido_min', 'Preparacion_min', 
        'Consumo_min', 'Pago_min', 'Tiempo_Reocupacion_Mesa_min'
    ]
    
    fits = {}
    for col in fit_cols:
        fits[col] = fit_single_distribution(df[col], col)
        
    # --- Fit discrete distributions for Comanda_min ---
    # Comanda_min is discrete (1, 2, 3, 4 min). Let's calculate its PMF.
    comanda_counts = df['Comanda_min'].value_counts(normalize=True).to_dict()
    # Ensure keys are integers and sort
    comanda_pmf = {int(k): float(v) for k, v in sorted(comanda_counts.items())}
    fits['Comanda_min'] = {
        "best": "empirical_discrete",
        "empirical_discrete": {
            "pmf": comanda_pmf
        }
    }
    
    # --- Fit empirical discrete probabilities for Group Sizes ---
    group_counts = df['Grupo'].value_counts(normalize=True).to_dict()
    group_pmf = {int(k): float(v) for k, v in sorted(group_counts.items())}
    fits['Grupo'] = {
        "best": "empirical_discrete",
        "empirical_discrete": {
            "pmf": group_pmf
        }
    }
    
    # --- Checkout Mode ---
    # Single bill vs split checkout
    checkout_counts = df['Checkout_Mode'].value_counts(normalize=True).to_dict()
    checkout_pmf = {str(k): float(v) for k, v in checkout_counts.items()}
    fits['Checkout_Mode'] = {
        "best": "bernoulli",
        "bernoulli": {
            "pmf": checkout_pmf
        }
    }
    
    return fits

# --- Sampling Helpers ---

def sample_value(dist_name, params, fallback_data=None):
    """
    Generates a random sample from a given distribution name and parameters.
    """
    if dist_name == 'empirical' or not params:
        if fallback_data is not None and len(fallback_data) > 0:
            return float(np.random.choice(fallback_data))
        elif 'observed_values' in params:
            return float(np.random.choice(params['observed_values']))
        return 1.0 # fallback

    elif dist_name == 'exponential':
        return float(stats.expon.rvs(loc=params.get('loc', 0), scale=params.get('scale', 1)))

    elif dist_name == 'lognormal':
        return float(stats.lognorm.rvs(s=params.get('s', 0.5), loc=params.get('loc', 0), scale=params.get('scale', 1)))

    elif dist_name == 'triangular':
        c = params.get('c', 0.5)
        loc = params.get('loc', 0)
        scale = params.get('scale', 1)
        # Avoid stats.triang.rvs errors if scale <= 0
        if scale <= 0:
            return float(loc)
        return float(stats.triang.rvs(c, loc=loc, scale=scale))

    elif dist_name == 'empirical_discrete':
        pmf = params.get('pmf', {})
        choices = list(pmf.keys())
        probs = list(pmf.values())
        return int(np.random.choice(choices, p=probs))

    elif dist_name == 'bernoulli':
        pmf = params.get('pmf', {})
        choices = list(pmf.keys())
        probs = list(pmf.values())
        return str(np.random.choice(choices, p=probs))

    return 1.0
