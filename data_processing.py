import pandas as pd
import numpy as np
import scipy.stats as stats


# ---------------------------------------------------------------------------
# 1. DATA LOADING & VALIDATION
# ---------------------------------------------------------------------------

def load_and_validate_data(file_path):
    """
    Loads operational Excel data from HUGO CAFÉ and validates it.
    Sheet: 'Base_Recoleccion_350', headers at row 4 (header=3).
    """
    validation = {
        "success": True,
        "errors": [],
        "warnings": [],
        "metrics": {}
    }

    try:
        xl = pd.ExcelFile(file_path)
        if 'Base_Recoleccion_350' not in xl.sheet_names:
            validation["success"] = False
            validation["errors"].append(
                "La hoja 'Base_Recoleccion_350' no existe en el archivo."
            )
            return None, validation

        df = pd.read_excel(
            file_path, sheet_name='Base_Recoleccion_350', header=3
        )

        # --- Clean column names ---
        df.columns = [str(c).strip() for c in df.columns]

        # --- Robust rename for encoding / accent issues ---
        rename_map = {}
        for col in df.columns:
            cl = col.lower()

            if ('tipo' in cl
                    and ('dia' in cl or 'da' in cl
                         or ('d' in cl and 'a' in cl and len(cl) <= 10))):
                rename_map[col] = 'Tipo_Dia'
            elif (('dia' in cl or 'da' in cl
                   or ('d' in cl and 'a' in cl)) and len(cl) <= 4):
                rename_map[col] = 'Dia'
            elif 'reocupacion' in cl or 'reocupaci' in cl:
                rename_map[col] = 'Tiempo_Reocupacion_Mesa_min'
            elif 'total_mesa' in cl or ('total' in cl and 'mesa' in cl):
                rename_map[col] = 'Tiempo_Total_Mesa_min'
            elif 'total_sistema' in cl or ('total' in cl and 'sistema' in cl):
                rename_map[col] = 'Tiempo_Total_Sistema_min'
            elif 'preparacion' in cl or 'preparaci' in cl:
                rename_map[col] = 'Preparacion_min'
            elif 'toma_pedido' in cl or ('toma' in cl and 'pedido' in cl):
                rename_map[col] = 'Toma_Pedido_min'

        df.rename(columns=rename_map, inplace=True)

        # --- Required columns ---
        required = [
            'ID', 'Semana', 'Fecha', 'Dia', 'Tipo_Dia', 'Hora_Llegada',
            'Franja_Horaria', 'Interarribo_min', 'Grupo', 'Mesa',
            'Zona_Mesa', 'Capacidad_Mesa', 'Toma_Pedido_min',
            'Comanda_min', 'Preparacion_min', 'Consumo_min', 'Pago_min',
            'Tiempo_Reocupacion_Mesa_min', 'Tiempo_Total_Mesa_min',
            'Ruta_Principal', 'Distancia_Ruta_m'
        ]
        missing = [c for c in required if c not in df.columns]
        if missing:
            validation["success"] = False
            validation["errors"].append(
                f"Faltan columnas requeridas: {', '.join(missing)}"
            )
            return None, validation

        # --- Sort by Fecha + Hora_Llegada ---
        df = df.sort_values(['Fecha', 'Hora_Llegada']).reset_index(drop=True)

        # --- Clean rows ---
        df = df.dropna(subset=['ID', 'Interarribo_min', 'Grupo', 'Mesa'])
        df['ID'] = df['ID'].astype(int)
        df['Grupo'] = df['Grupo'].astype(int)
        df['Capacidad_Mesa'] = df['Capacidad_Mesa'].astype(int)
        df['Comanda_min'] = df['Comanda_min'].astype(int)

        # ============ VALIDATIONS ============

        # V1 — Negative times
        time_cols = [
            'Interarribo_min', 'Toma_Pedido_min', 'Comanda_min',
            'Preparacion_min', 'Consumo_min', 'Pago_min',
            'Tiempo_Reocupacion_Mesa_min'
        ]
        for col in time_cols:
            neg = df[df[col] < 0]
            if not neg.empty:
                validation["warnings"].append(
                    f"'{col}' contiene {len(neg)} valores negativos "
                    f"(reemplazados por 0)."
                )
                df.loc[df[col] < 0, col] = 0.0

        # V2 — Table capacity rules
        cap_rules = {'T1': 2, 'T2': 2, 'T3': 2, 'T4': 3, 'T5': 3}
        for tbl, cap in cap_rules.items():
            rows = df[df['Mesa'] == tbl]
            bad = rows[rows['Capacidad_Mesa'] != cap]
            if not bad.empty:
                validation["warnings"].append(
                    f"Mesa {tbl} debe tener capacidad {cap}, pero "
                    f"{len(bad)} registros difieren."
                )

        # V3 — Group-3 only in T4/T5
        g3 = df[df['Grupo'] == 3]
        g3_bad = g3[~g3['Mesa'].isin(['T4', 'T5'])]
        if not g3_bad.empty:
            validation["warnings"].append(
                f"{len(g3_bad)} grupos de 3 asignados a mesas de "
                f"capacidad 2 (T1, T2 o T3)."
            )

        # V4 — Group-4 exception marking
        g4 = df[df['Grupo'] == 4]
        if 'Observaciones' in df.columns:
            g4_no = g4[~g4['Observaciones'].str.contains(
                'exception|excepci', case=False, na=True)]
        else:
            g4_no = g4
        if len(g4_no) > 0:
            validation["warnings"].append(
                f"{len(g4_no)} grupos de 4 sin nota de excepcion "
                f"en observaciones."
            )

        # V5 — Tiempo_Total_Mesa = sum of phases (tolerance 1 min)
        phase_sum = (
            df['Toma_Pedido_min'] + df['Comanda_min']
            + df['Preparacion_min'] + df['Consumo_min']
            + df['Pago_min'] + df['Tiempo_Reocupacion_Mesa_min']
        )
        diff = (df['Tiempo_Total_Mesa_min'] - phase_sum).abs()
        mismatch = diff[diff > 1.0]
        if not mismatch.empty:
            validation["warnings"].append(
                f"En {len(mismatch)} registros, Tiempo_Total_Mesa_min "
                f"difiere de la suma de fases por mas de 1 minuto."
            )

        # V6 — Interarrival recalculation by day
        try:
            df_tmp = df.copy()
            hora = df_tmp['Hora_Llegada'].astype(str)
            td = pd.to_timedelta(
                hora.apply(lambda x: x if x.count(':') == 2 else x + ':00')
            )
            df_tmp['_td'] = td
            recalc = []
            for _, grp in df_tmp.groupby('Fecha'):
                grp = grp.sort_values('_td')
                diffs = grp['_td'].diff().dt.total_seconds() / 60.0
                recalc.extend(diffs.tolist())
            df_tmp['_rc'] = recalc
            mask = df_tmp['_rc'].notna()
            if mask.sum() > 0:
                delta = (df_tmp.loc[mask, 'Interarribo_min']
                         - df_tmp.loc[mask, '_rc']).abs()
                large = delta[delta > 1.0]
                if not large.empty:
                    validation["warnings"].append(
                        f"En {len(large)} registros, el interarribo del "
                        f"Excel difiere del recalculado (Hora_Llegada) en "
                        f"mas de 1 min. Se usaran los valores originales."
                    )
        except Exception:
            pass

        # ============ METRICS ============
        avg_sys = 0.0
        if 'Tiempo_Total_Sistema_min' in df.columns:
            avg_sys = float(df['Tiempo_Total_Sistema_min'].mean())

        validation["metrics"] = {
            "total_records": len(df),
            "groups_by_size": df['Grupo'].value_counts().to_dict(),
            "tables_count": df['Mesa'].value_counts().to_dict(),
            "average_interarrival": float(df['Interarribo_min'].mean()),
            "average_table_time": float(df['Tiempo_Total_Mesa_min'].mean()),
            "average_system_time": avg_sys,
            "total_exceptions": int((df['Grupo'] == 4).sum())
        }

        return df, validation

    except Exception as e:
        validation["success"] = False
        validation["errors"].append(
            f"Error al leer el archivo Excel: {str(e)}"
        )
        return None, validation


# ---------------------------------------------------------------------------
# 2. DISTRIBUTION FITTING
# ---------------------------------------------------------------------------

def fit_single_distribution(data, col_name):
    """Fits Exponential, Lognormal, Triangular; returns KS stats."""
    results = {}
    data = data[data > 0]

    if len(data) < 5:
        return {"best": "empirical",
                "empirical": {"data": data.tolist()}}

    # Exponential
    try:
        loc_e, sc_e = stats.expon.fit(data)
        ks = stats.kstest(data, 'expon', args=(loc_e, sc_e))
        results['exponential'] = {
            "params": {"loc": float(loc_e), "scale": float(sc_e)},
            "p_value": float(ks.pvalue),
            "statistic": float(ks.statistic)
        }
    except Exception:
        results['exponential'] = {"p_value": 0.0, "params": {}}

    # Lognormal
    try:
        s, loc_l, sc_l = stats.lognorm.fit(data, floc=0)
        ks = stats.kstest(data, 'lognorm', args=(s, loc_l, sc_l))
        results['lognormal'] = {
            "params": {"s": float(s), "loc": float(loc_l),
                       "scale": float(sc_l)},
            "p_value": float(ks.pvalue),
            "statistic": float(ks.statistic)
        }
    except Exception:
        results['lognormal'] = {"p_value": 0.0, "params": {}}

    # Triangular
    try:
        c, loc_t, sc_t = stats.triang.fit(data)
        ks = stats.kstest(data, 'triang', args=(c, loc_t, sc_t))
        results['triangular'] = {
            "params": {"c": float(c), "loc": float(loc_t),
                       "scale": float(sc_t)},
            "p_value": float(ks.pvalue),
            "statistic": float(ks.statistic)
        }
    except Exception:
        results['triangular'] = {"p_value": 0.0, "params": {}}

    # Empirical fallback
    results['empirical'] = {
        "params": {"observed_values": data.tolist()},
        "p_value": 1.0,
        "statistic": 0.0
    }

    # Best fit (prefer theoretical with p > 0.05)
    best, best_p = 'empirical', -1.0
    for cand in ['lognormal', 'triangular', 'exponential']:
        if cand in results and results[cand]["p_value"] > 0.05:
            if results[cand]["p_value"] > best_p:
                best_p = results[cand]["p_value"]
                best = cand
    results['best'] = best
    return results


def fit_distributions(df):
    """Fits distributions for all process time columns."""
    fit_cols = [
        'Interarribo_min', 'Toma_Pedido_min', 'Preparacion_min',
        'Consumo_min', 'Pago_min', 'Tiempo_Reocupacion_Mesa_min'
    ]
    fits = {}
    for col in fit_cols:
        fits[col] = fit_single_distribution(df[col], col)

    # Comanda — discrete PMF
    cc = df['Comanda_min'].value_counts(normalize=True).to_dict()
    fits['Comanda_min'] = {
        "best": "empirical_discrete",
        "empirical_discrete": {
            "pmf": {int(k): float(v) for k, v in sorted(cc.items())}
        }
    }

    # Group size — discrete PMF
    gc = df['Grupo'].value_counts(normalize=True).to_dict()
    fits['Grupo'] = {
        "best": "empirical_discrete",
        "empirical_discrete": {
            "pmf": {int(k): float(v) for k, v in sorted(gc.items())}
        }
    }

    # Checkout mode
    if 'Checkout_Mode' in df.columns:
        cm = df['Checkout_Mode'].value_counts(normalize=True).to_dict()
        fits['Checkout_Mode'] = {
            "best": "bernoulli",
            "bernoulli": {
                "pmf": {str(k): float(v) for k, v in cm.items()}
            }
        }

    return fits


# ---------------------------------------------------------------------------
# 3. SAMPLING HELPERS
# ---------------------------------------------------------------------------

def sample_value(dist_name, params, fallback_data=None):
    """Generates a random sample from the given distribution."""
    if dist_name == 'empirical' or not params:
        if fallback_data is not None and len(fallback_data) > 0:
            return float(np.random.choice(fallback_data))
        if isinstance(params, dict) and 'observed_values' in params:
            return float(np.random.choice(params['observed_values']))
        return 1.0

    if dist_name == 'exponential':
        return float(stats.expon.rvs(
            loc=params.get('loc', 0), scale=params.get('scale', 1)))

    if dist_name == 'lognormal':
        return float(stats.lognorm.rvs(
            s=params.get('s', 0.5), loc=params.get('loc', 0),
            scale=params.get('scale', 1)))

    if dist_name == 'triangular':
        c = params.get('c', 0.5)
        loc = params.get('loc', 0)
        sc = params.get('scale', 1)
        return float(loc) if sc <= 0 else float(
            stats.triang.rvs(c, loc=loc, scale=sc))

    if dist_name == 'empirical_discrete':
        pmf = params.get('pmf', {})
        choices = list(pmf.keys())
        probs = list(pmf.values())
        return int(np.random.choice(choices, p=probs))

    if dist_name == 'bernoulli':
        pmf = params.get('pmf', {})
        choices = list(pmf.keys())
        probs = list(pmf.values())
        return str(np.random.choice(choices, p=probs))

    return 1.0
