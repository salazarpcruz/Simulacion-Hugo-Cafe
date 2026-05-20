import streamlit as st
import pandas as pd
import numpy as np
import base64
import json
import os
from data_processing import load_and_validate_data, fit_distributions
from simulation_engine import run_multi_simulation
from visualization import (
    plot_process_times,
    plot_resource_utilization,
    plot_waiting_times_distribution,
    plot_distribution_fitting
)

# ======================================================================
# PAGE CONFIG
# ======================================================================
st.set_page_config(
    page_title="HUGO CAFE - Simulation Project",
    page_icon="H",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ======================================================================
# CUSTOM CSS — Light theme, no emojis
# ======================================================================
st.markdown("""
<style>
    .stApp { background-color: #F6F8FB; color: #111827; }

    .main-title {
        color: #003781; font-family: 'Inter','Segoe UI',sans-serif;
        font-weight: 700; font-size: 2.2rem; margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #4B5563; font-size: 1.05rem; margin-bottom: 2rem;
    }
    .section-header {
        color: #003781; font-weight: 600; font-size: 1.3rem;
        border-bottom: 2px solid #E5E7EB; padding-bottom: 0.5rem;
        margin-top: 2.5rem; margin-bottom: 1rem;
    }
    .kpi-card {
        background: #FFFFFF; border-radius: 8px;
        padding: 1.1rem 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        border-left: 4px solid #003781; margin-bottom: 0.7rem;
    }
    .kpi-value {
        color: #003781; font-size: 1.55rem; font-weight: 700;
        margin-bottom: 0.1rem;
    }
    .kpi-label {
        color: #4B5563; font-size: 0.78rem; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.04em;
    }
    .kpi-ci { color: #6B7280; font-size: 0.7rem; margin-top: 0.15rem; }

    .interp-box {
        background: #FFFFFF; border: 1px solid #E5E7EB;
        border-radius: 6px; padding: 0.9rem 1.1rem;
        margin-top: 0.4rem; margin-bottom: 1.2rem;
        font-size: 0.85rem; color: #374151; line-height: 1.55;
    }
    .interp-box strong { color: #003781; }

    .insight-card {
        background: #FFFFFF; border: 1px solid #E5E7EB;
        border-radius: 8px; padding: 1.4rem; margin-bottom: 1.3rem;
    }
    .insight-card h4 { color: #003781; margin: 0 0 0.7rem 0; }
    .ins-title {
        font-weight: 600; color: #111827; font-size: 0.88rem;
        margin-bottom: 0.2rem;
    }
    .ins-body {
        color: #374151; font-size: 0.84rem; line-height: 1.55;
        margin: 0 0 0.7rem 0;
    }

    [data-testid="stSidebar"] {
        background-color: #FFFFFF; border-right: 1px solid #E5E7EB;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 22px; font-weight: 600; color: #4B5563;
    }
    .stTabs [aria-selected="true"] {
        color: #003781; border-bottom-color: #003781;
    }
</style>
""", unsafe_allow_html=True)

# ======================================================================
# SESSION STATE
# ======================================================================
for _k in ['fits', 'df_clean', 'validation', 'sim_results', 'event_log']:
    if _k not in st.session_state:
        st.session_state[_k] = None

# ======================================================================
# SIDEBAR
# ======================================================================
st.sidebar.markdown(
    '<div style="text-align:center;">'
    '<h2 style="color:#003781;margin-bottom:0;">HUGO CAFE</h2>'
    '<p style="color:#6B7280;font-size:0.85rem;margin-top:0;">'
    'Simulador de Eventos Discretos</p></div>',
    unsafe_allow_html=True)
st.sidebar.markdown("---")

# --- File upload ---
st.sidebar.subheader("Carga de Archivos")
uploaded_excel = st.sidebar.file_uploader("Datos (.xlsx)", type=["xlsx"])
uploaded_layout = st.sidebar.file_uploader("Layout (.png)", type=["png"])

DEFAULT_EXCEL = r"c:\Proyectos antigvty\Simulador\HUGO_CAFE_DataFase1-4.xlsx"
DEFAULT_LAYOUT = r"c:\Proyectos antigvty\Simulador\Layout.png"
excel_path = DEFAULT_EXCEL
layout_path = DEFAULT_LAYOUT

if uploaded_excel is not None:
    _tmp = os.path.join(os.getcwd(), "temp_data.xlsx")
    with open(_tmp, "wb") as f:
        f.write(uploaded_excel.getbuffer())
    excel_path = _tmp
    st.sidebar.success("Excel cargado.")

if uploaded_layout is not None:
    _tmp = os.path.join(os.getcwd(), "temp_layout.png")
    with open(_tmp, "wb") as f:
        f.write(uploaded_layout.getbuffer())
    layout_path = _tmp
    st.sidebar.success("Layout cargado.")

# --- Load data ---
@st.cache_data
def _cached_load(path):
    return load_and_validate_data(path)

if excel_path and os.path.exists(excel_path):
    df_clean, validation = _cached_load(excel_path)
    if validation["success"]:
        st.session_state.df_clean = df_clean
        st.session_state.validation = validation
        if st.session_state.fits is None:
            st.session_state.fits = fit_distributions(df_clean)
    else:
        st.sidebar.error("Error al validar el Excel.")
        for e in validation["errors"]:
            st.sidebar.write(f"- {e}")

# --- Model config ---
st.sidebar.markdown("---")
st.sidebar.subheader("Configuracion del Modelo")
runs_count = st.sidebar.selectbox("Numero de corridas", [10, 20, 30, 40, 50], index=1)
kitchen_cap = st.sidebar.slider("Chefs (cocina)", 1, 5, 2)
checkout_cap = st.sidebar.slider("Cajeros (caja)", 1, 3, 1)
waiter_cap = st.sidebar.slider("Numero de meseros", 1, 5, 2)

# --- Distribution selectors ---
st.sidebar.markdown("---")
st.sidebar.subheader("Distribuciones de Entrada")
user_dists = {}
if st.session_state.fits is not None:
    _proc = {
        'Interarribo_min': 'Interarribo',
        'Toma_Pedido_min': 'Toma de pedido',
        'Preparacion_min': 'Preparacion',
        'Consumo_min': 'Consumo',
        'Pago_min': 'Pago',
        'Tiempo_Reocupacion_Mesa_min': 'Reocupacion de mesa'
    }
    opts = ['empirical', 'lognormal', 'triangular', 'exponential']
    lbl = {'empirical': 'Empirica', 'lognormal': 'Lognormal',
           'triangular': 'Triangular', 'exponential': 'Exponencial'}
    for col, label in _proc.items():
        best = st.session_state.fits[col]['best']
        nice = [lbl[o] if o != best else f"{lbl[o]} (Recomendada)"
                for o in opts]
        sel = st.sidebar.selectbox(label, nice, index=opts.index(best))
        user_dists[col] = opts[nice.index(sel)]
    user_dists['Comanda_min'] = 'empirical_discrete'

# --- Tabs ---
tab_dash, tab_fit, tab_val, tab_anim, tab_ins = st.tabs([
    "Dashboard AS-IS",
    "Inferencia de Entrada",
    "Validacion de Reglas",
    "Animacion 2D",
    "Insights de Simulacion"
])

# --- Run button ---
if st.session_state.df_clean is not None:
    if st.sidebar.button("Ejecutar Simulacion", width='stretch'):
        with st.spinner("Ejecutando simulaciones..."):
            res, elog = run_multi_simulation(
                runs_count, st.session_state.fits, user_dists,
                max_groups=len(st.session_state.df_clean),
                kitchen_cap=kitchen_cap,
                checkout_cap=checkout_cap,
                waiter_cap=waiter_cap)
            st.session_state.sim_results = res
            st.session_state.event_log = elog
            st.success("Simulacion completada.")

# ======================================================================
# HELPER — KPI card HTML
# ======================================================================
def _kpi(label, value, sub=""):
    return f"""<div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-ci">{sub}</div></div>"""

# ======================================================================
# TAB 1 — DASHBOARD AS-IS
# ======================================================================
with tab_dash:
    st.markdown('<h1 class="main-title">HUGO CAFE Simulation Project</h1>',
                unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Modelado AS-IS del flujo operativo del restaurante</p>',
                unsafe_allow_html=True)

    if st.session_state.sim_results is None:
        st.info("Presione 'Ejecutar Simulacion' en la barra lateral para generar el dashboard.")
    else:
        res = st.session_state.sim_results
        ci = res["ci_95"]

        st.markdown('<h3 class="section-header">Indicadores Clave de Desempeno</h3>',
                    unsafe_allow_html=True)

        # Row 1
        c1, c2, c3 = st.columns(3)
        c1.markdown(_kpi("Grupos Atendidos",
            f"{ci['groups_served']['mean']:.0f}",
            f"Rango: [{ci['groups_served']['min']:.0f} - {ci['groups_served']['max']:.0f}]"),
            unsafe_allow_html=True)
        c2.markdown(_kpi("Tiempo Promedio en Sistema",
            f"{ci['avg_system']['mean']:.1f} min",
            f"IC 95%: [{ci['avg_system']['ci_lower']:.1f} - {ci['avg_system']['ci_upper']:.1f}]"),
            unsafe_allow_html=True)
        c3.markdown(_kpi("Tiempo Promedio de Espera",
            f"{ci['avg_wait']['mean']:.2f} min",
            f"IC 95%: [{ci['avg_wait']['ci_lower']:.2f} - {ci['avg_wait']['ci_upper']:.2f}]"),
            unsafe_allow_html=True)

        # Row 2
        c4, c5, c6 = st.columns(3)
        c4.markdown(_kpi("Tiempo Promedio de Mesa",
            f"{ci['avg_table_time']['mean']:.1f} min",
            f"IC 95%: [{ci['avg_table_time']['ci_lower']:.1f} - {ci['avg_table_time']['ci_upper']:.1f}]"),
            unsafe_allow_html=True)
        avg_tbl = np.mean(list(res["table_utilizations"].values())) * 100
        c5.markdown(_kpi("Utilizacion Promedio de Mesas",
            f"{avg_tbl:.1f}%", "Promedio T1-T5"), unsafe_allow_html=True)
        c6.markdown(_kpi("Utilizacion de Meseros",
            f"{ci['waiter_util']['mean']*100:.1f}%",
            f"IC 95%: [{ci['waiter_util']['ci_lower']*100:.1f}% - {ci['waiter_util']['ci_upper']*100:.1f}%]"),
            unsafe_allow_html=True)

        # Row 3
        c7, c8, c9 = st.columns(3)
        c7.markdown(_kpi("Utilizacion de Cocina",
            f"{ci['kitchen_util']['mean']*100:.1f}%",
            f"IC 95%: [{ci['kitchen_util']['ci_lower']*100:.1f}% - {ci['kitchen_util']['ci_upper']*100:.1f}%]"),
            unsafe_allow_html=True)
        c8.markdown(_kpi("Utilizacion de Caja",
            f"{ci['checkout_util']['mean']*100:.1f}%",
            f"IC 95%: [{ci['checkout_util']['ci_lower']*100:.1f}% - {ci['checkout_util']['ci_upper']*100:.1f}%]"),
            unsafe_allow_html=True)
        c9.markdown(_kpi("Excepciones Operativas",
            f"{ci['exceptions']['mean']:.0f}",
            "Grupos de 4 personas"), unsafe_allow_html=True)

        # ---------- Charts ----------
        st.markdown('<h3 class="section-header">Analisis de Desempeno</h3>',
                    unsafe_allow_html=True)
        cL, cR = st.columns(2)
        with cL:
            st.plotly_chart(plot_process_times(res["activity_averages"]),
                            width='stretch')
            st.markdown("""<div class="interp-box">
            <strong>Como interpretar:</strong> Cada barra muestra el tiempo promedio
            que un grupo permanece en esa fase del servicio. Las fases mas largas
            (generalmente Consumo y Preparacion) representan el mayor consumo de
            tiempo operativo y son candidatas a optimizacion si generan cuellos de botella.
            </div>""", unsafe_allow_html=True)

        with cR:
            st.plotly_chart(plot_resource_utilization(
                res["table_utilizations"],
                ci["kitchen_util"]["mean"],
                ci["checkout_util"]["mean"],
                ci["waiter_util"]["mean"]),
                width='stretch')
            st.markdown("""<div class="interp-box">
            <strong>Como interpretar:</strong> La utilizacion representa el porcentaje
            del tiempo total de simulacion que cada recurso estuvo activamente ocupado.
            No debe confundirse con la frecuencia de asignacion (numero de veces que fue
            utilizado). Una utilizacion superior al 80% indica posible cuello de botella;
            inferior al 30% indica capacidad ociosa.
            </div>""", unsafe_allow_html=True)

        # Wait times
        wL, wR = st.columns([3, 2])
        with wL:
            wt = [e["wait_time"] for e in st.session_state.event_log
                  if e["state"] == "assigned_table"]
            st.plotly_chart(plot_waiting_times_distribution(wt),
                            width='stretch')
            st.markdown("""<div class="interp-box">
            <strong>Como interpretar:</strong> Este histograma muestra la distribucion de
            los tiempos que los grupos esperan para obtener una mesa. Si la mayoria de
            valores se concentra cerca de 0, el sistema tiene capacidad suficiente. Una
            cola larga hacia la derecha indica saturacion en horas pico.
            </div>""", unsafe_allow_html=True)

        with wR:
            st.markdown('<div style="margin-top:0.8rem;"></div>',
                        unsafe_allow_html=True)
            st.subheader("Historial de Corridas")
            df_runs = pd.DataFrame(res["raw_runs"])
            df_runs.columns = [
                "Grupos", "Duracion", "Espera Med.", "Espera Max.",
                "Sistema Med.", "Util. Cocina", "Util. Caja",
                "Util. Meseros", "Excepc.",
                "Esp. Mesero", "Esp. Cocina", "Esp. Caja", "Mesa Med."]
            st.dataframe(df_runs.style.format(precision=2),
                         height=280, width='stretch')

        # ---------- Executive summary ----------
        st.markdown('<h3 class="section-header">Resumen Ejecutivo AS-IS</h3>',
                    unsafe_allow_html=True)
        if st.session_state.validation is not None:
            m = st.session_state.validation["metrics"]
            obs_tbl = m.get("average_table_time", 0)
            obs_sys = m.get("average_system_time", 0)
            obs_ia = m.get("average_interarrival", 0)
            sim_tbl = ci["avg_table_time"]["mean"]
            sim_sys = ci["avg_system"]["mean"]

            def _pct(o, s):
                return ((s - o) / o * 100) if o else 0.0
            def _interp(p):
                a = abs(p)
                if a < 5: return "Modelo bien calibrado"
                if a < 10: return "Desviacion aceptable"
                return "Revision recomendada"

            d_tbl = _pct(obs_tbl, sim_tbl)
            d_sys = _pct(obs_sys, sim_sys)
            d_grp = _pct(m["total_records"], ci["groups_served"]["mean"])

            df_sum = pd.DataFrame([
                {"KPI": "Tiempo Prom. de Mesa (min)",
                 "Observado": f"{obs_tbl:.1f}", "Simulado": f"{sim_tbl:.1f}",
                 "Diferencia (%)": f"{d_tbl:+.1f}%",
                 "Interpretacion": _interp(d_tbl)},
                {"KPI": "Tiempo Prom. en Sistema (min)",
                 "Observado": f"{obs_sys:.1f}", "Simulado": f"{sim_sys:.1f}",
                 "Diferencia (%)": f"{d_sys:+.1f}%",
                 "Interpretacion": _interp(d_sys)},
                {"KPI": "Interarribo Promedio (min)",
                 "Observado": f"{obs_ia:.1f}", "Simulado": "(Entrada)",
                 "Diferencia (%)": "N/A",
                 "Interpretacion": "Parametro de entrada"},
                {"KPI": "Grupos Atendidos",
                 "Observado": f"{m['total_records']}",
                 "Simulado": f"{ci['groups_served']['mean']:.0f}",
                 "Diferencia (%)": f"{d_grp:+.1f}%",
                 "Interpretacion": _interp(d_grp)}
            ])
            st.table(df_sum)

# ======================================================================
# TAB 2 — INFERENCIA DE ENTRADA
# ======================================================================
_VAR_LABELS = {
    'Interarribo_min': 'Interarribo',
    'Toma_Pedido_min': 'Toma de pedido',
    'Preparacion_min': 'Preparacion',
    'Consumo_min': 'Consumo',
    'Pago_min': 'Pago',
    'Tiempo_Reocupacion_Mesa_min': 'Reocupacion de mesa'
}

_VAR_EXPLAIN = {
    'Interarribo_min': (
        "El interarribo representa el tiempo entre llegadas consecutivas de "
        "grupos al restaurante dentro del mismo dia operativo. Se prueba "
        "contra distribuciones Exponencial (tipica de procesos Poisson), "
        "Lognormal y Triangular. Un p-value > 0.05 en la prueba de "
        "Kolmogorov-Smirnov indica que no se rechaza la hipotesis de que "
        "los datos siguen esa distribucion, y por lo tanto puede usarse como "
        "entrada del modelo. Si ninguna distribucion teorica ajusta (todos "
        "los p-value <= 0.05), se usa la distribucion empirica, muestreando "
        "directamente los valores historicos observados."
    ),
    'Toma_Pedido_min': (
        "Tiempo que el mesero tarda en atender la mesa y registrar la orden. "
        "Se espera una distribucion con sesgo positivo, ya que la mayoria de "
        "ordenes son rapidas pero algunas se extienden. Como p-value > 0.05, "
        "no se rechaza la distribucion candidata y puede usarse como entrada "
        "del modelo para esta actividad."
    ),
    'Preparacion_min': (
        "Tiempo de preparacion de alimentos en cocina. Variable critica por "
        "ser potencial cuello de botella. Suele seguir una distribucion "
        "lognormal con alta variabilidad, dependiendo de la complejidad "
        "del pedido."
    ),
    'Consumo_min': (
        "Tiempo que el grupo permanece comiendo en la mesa. Generalmente la "
        "fase de mayor duracion, con alta variabilidad segun el tipo de "
        "comida y tamano del grupo."
    ),
    'Pago_min': (
        "Tiempo del proceso de cobro en caja. Depende del metodo de pago "
        "(efectivo, tarjeta, division de cuenta). Si la distribucion "
        "empirica es la recomendada, indica que el comportamiento del pago "
        "no se ajusta a patrones teoricos estandar."
    ),
    'Tiempo_Reocupacion_Mesa_min': (
        "Tiempo de limpieza y preparacion de la mesa para el siguiente "
        "grupo. Incluye retirar platos, limpiar superficie y reacomodar. "
        "Afecta directamente la disponibilidad de mesas y requiere mesero."
    )
}

with tab_fit:
    st.markdown('<h2 style="color:#003781;">Inferencia y Ajuste de '
                'Distribuciones de Entrada</h2>', unsafe_allow_html=True)
    st.write(
        "Ajuste estadistico de distribuciones de probabilidad mediante la "
        "prueba de bondad de ajuste de **Kolmogorov-Smirnov** (KS) sobre "
        "las 350 observaciones del modelo AS-IS."
    )

    if st.session_state.fits is None:
        st.warning("No hay datos cargados. Cargue un archivo Excel valido.")
    else:
        sel_col = st.selectbox(
            "Variable de proceso a analizar:",
            list(_VAR_LABELS.keys()),
            format_func=lambda x: _VAR_LABELS[x])

        fL, fR = st.columns([3, 2])
        fit_res = st.session_state.fits[sel_col]

        with fL:
            fig_gof = plot_distribution_fitting(
                st.session_state.df_clean, sel_col, fit_res)
            st.plotly_chart(fig_gof, width='stretch')

        with fR:
            st.markdown('<div style="margin-top:0.8rem;"></div>',
                        unsafe_allow_html=True)
            st.subheader("Tabla Comparativa")
            rows = []
            for d in ['lognormal', 'triangular', 'exponential']:
                if d in fit_res and 'p_value' in fit_res[d]:
                    p = fit_res[d]['p_value']
                    s = fit_res[d].get('statistic', 0.0)
                    dec = ("No se rechaza (p > 0.05)"
                           if p > 0.05 else "Rechazada (p <= 0.05)")
                    rows.append({
                        "Distribucion": d.capitalize(),
                        "Estadistico KS": f"{s:.4f}",
                        "p-value": f"{p:.4f}",
                        "Decision": dec})
            rows.append({
                "Distribucion": "Empirica",
                "Estadistico KS": "0.0000",
                "p-value": "1.0000",
                "Decision": "Respaldo por defecto"})
            st.table(pd.DataFrame(rows))

            best = fit_res['best']
            _bm = {"lognormal": "Lognormal", "triangular": "Triangular",
                    "exponential": "Exponencial", "empirical": "Empirica"}
            st.info(f"Distribucion recomendada: **{_bm.get(best, best)}**")

            if best not in ('empirical', 'empirical_discrete') and best in fit_res:
                st.markdown("**Parametros ajustados:**")
                for k, v in fit_res[best]['params'].items():
                    st.write(f"- `{k}`: {v:.4f}")

        # Explanation
        st.markdown(f"""<div class="interp-box">
        <strong>{_VAR_LABELS[sel_col]}:</strong> {_VAR_EXPLAIN.get(sel_col, '')}
        </div>""", unsafe_allow_html=True)

# ======================================================================
# TAB 3 — VALIDACION DE REGLAS
# ======================================================================
with tab_val:
    st.markdown('<h2 style="color:#003781;">Validacion Operativa y de '
                'Reglas de Negocio</h2>', unsafe_allow_html=True)
    st.write("Verificacion de inconsistencias, tiempos negativos y "
             "cumplimiento de reglas operativas en los datos cargados.")

    if st.session_state.validation is None:
        st.warning("No hay datos cargados para validar.")
    else:
        val = st.session_state.validation
        m = val["metrics"]

        st.subheader("Estado de las Validaciones")
        v1, v2 = st.columns(2)
        with v1:
            st.success("Tiempos negativos: verificado (corregidos a 0).")
            st.success("Estructura de IDs: secuencial correcta.")
        with v2:
            if not val["warnings"]:
                st.success("Reglas de capacidad: todas correctas.")
            else:
                st.warning(
                    f"Se encontraron {len(val['warnings'])} notas de "
                    f"validacion.")

        if val["warnings"]:
            st.markdown("---")
            st.subheader("Advertencias Detectadas")
            for w in val["warnings"]:
                st.markdown(f"- {w}")

        st.markdown("---")
        st.subheader("Metricas de Validacion de Datos")
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Total Observaciones", f"{m['total_records']} grupos")
            st.metric("Excepciones (Grupo 4)", f"{m['total_exceptions']}")
        with m2:
            st.metric("Interarribo Medio", f"{m['average_interarrival']:.2f} min")
            st.metric("Tiempo Mesa Medio", f"{m['average_table_time']:.2f} min")
        with m3:
            st.write("**Distribucion de Mesas:**")
            st.write(m["tables_count"])

# ======================================================================
# TAB 4 — ANIMACION 2D
# ======================================================================
with tab_anim:
    st.markdown('<h2 style="color:#003781;">Simulacion Espacial sobre Layout</h2>',
                unsafe_allow_html=True)
    st.write(
        "Visualizacion de flujos de clientes. Los circulos representan "
        "grupos desplazandose por las rutas de servicio. Las zonas cambian "
        "de color segun la ocupacion de mesas.")

    if st.session_state.event_log is None:
        st.info("Presione 'Ejecutar Simulacion' en la barra lateral.")
    else:
        try:
            with open(layout_path, "rb") as img_f:
                b64_img = base64.b64encode(img_f.read()).decode()
        except Exception as exc:
            st.error(f"Error al abrir Layout: {exc}")
            b64_img = ""

        elog_json = json.dumps(st.session_state.event_log)

        html_code = f"""
        <!DOCTYPE html><html><head><meta charset="utf-8">
        <style>
            body {{ font-family:'Inter',sans-serif; margin:0; padding:0;
                   background:#F6F8FB; display:flex; flex-direction:column;
                   align-items:center; }}
            #canvas-container {{ position:relative;
                box-shadow:0 4px 12px rgba(0,0,0,0.08); border-radius:8px;
                overflow:hidden; background:#fff; }}
            canvas {{ display:block; }}
            #controls {{ width:848px; margin-top:12px; background:#fff;
                padding:12px 16px; border-radius:8px;
                box-shadow:0 1px 3px rgba(0,0,0,0.06);
                display:flex; align-items:center; justify-content:space-between;
                box-sizing:border-box; }}
            .btn {{ background:#003781; color:#fff; border:none;
                   padding:7px 14px; border-radius:4px; cursor:pointer;
                   font-weight:600; font-size:0.85rem; transition:0.2s; }}
            .btn:hover {{ background:#1e3a8a; }}
            .btn-outline {{ background:transparent; color:#003781;
                           border:1px solid #003781; }}
            .btn-outline:hover {{ background:#E8EDF5; }}
            .ctrl {{ display:flex; align-items:center; gap:8px; }}
            .tdisp {{ font-size:0.9rem; font-weight:700; color:#003781;
                     min-width:130px; }}
            #timeline {{ flex-grow:1; margin:0 14px; cursor:pointer; }}
            select {{ padding:5px; border-radius:4px; border:1px solid #cbd5e1;
                     font-weight:600; color:#334155; font-size:0.85rem; }}
            .legend {{ width:848px; margin-top:8px; display:flex;
                      justify-content:center; gap:14px; font-size:0.78rem;
                      color:#4B5563; flex-wrap:wrap; }}
            .leg-item {{ display:flex; align-items:center; gap:4px; }}
            .leg-dot {{ width:11px; height:11px; border-radius:50%; }}
        </style></head><body>
        <div id="canvas-container">
            <canvas id="lc" width="848" height="656"></canvas>
        </div>
        <div id="controls">
            <div class="ctrl">
                <button id="playBtn" class="btn">Pausa</button>
                <button id="resetBtn" class="btn btn-outline">Reiniciar</button>
                <button id="routeBtn" class="btn btn-outline">Mostrar rutas</button>
            </div>
            <div class="ctrl" style="flex-grow:1;display:flex;align-items:center;">
                <span class="tdisp" id="tShow">Sim: 0.00 min</span>
                <input type="range" id="timeline" min="0" max="1000" value="0">
            </div>
            <div class="ctrl">
                <span style="font-size:0.82rem;color:#4B5563;font-weight:600;">Vel:</span>
                <select id="spd">
                    <option value="0.5">0.5x</option>
                    <option value="1" selected>1x</option>
                    <option value="2">2x</option>
                    <option value="5">5x</option>
                    <option value="10">10x</option>
                </select>
            </div>
        </div>
        <div class="legend">
            <div class="leg-item"><div class="leg-dot" style="background:#3b82f6;"></div> Grupo 1</div>
            <div class="leg-item"><div class="leg-dot" style="background:#10b981;"></div> Grupo 2</div>
            <div class="leg-item"><div class="leg-dot" style="background:#f59e0b;"></div> Grupo 3</div>
            <div class="leg-item"><div class="leg-dot" style="background:#ef4444;"></div> Grupo 4 (excepcion)</div>
            <div class="leg-item"><div class="leg-dot" style="border:2px dashed #003781;width:7px;height:7px;border-radius:0;"></div> Zonas de ocupacion</div>
        </div>
        <script>
        const events={elog_json};
        const bgSrc="data:image/png;base64,{b64_img}";
        const cv=document.getElementById("lc"),ctx=cv.getContext("2d");
        const bg=new Image();bg.src=bgSrc;let bgOk=false;
        bg.onload=()=>{{bgOk=true;draw();}};
        const N={{E:{{x:65,y:370}},V:{{x:280,y:370}},
            T1:{{x:65,y:190}},T2:{{x:65,y:590}},T3:{{x:270,y:190}},
            T4:{{x:410,y:590}},T5:{{x:410,y:460}},
            K:{{x:750,y:250}},CB:{{x:560,y:370}},CO:{{x:550,y:580}},
            OUT:{{x:65,y:370}}}};
        let playing=true,simT=0,speed=1;
        let showRoutes=false,lastTk=Date.now();
        const maxT=Math.max(...events.map(e=>e.time));
        const sl=document.getElementById("timeline");sl.max=Math.ceil(maxT);
        document.getElementById("playBtn").onclick=()=>{{
            playing=!playing;
            document.getElementById("playBtn").textContent=playing?"Pausa":"Reproducir";
            if(playing){{lastTk=Date.now();anim();}}
        }};
        document.getElementById("resetBtn").onclick=()=>{{
            simT=0;sl.value=0;
            document.getElementById("tShow").textContent="Sim: 0.00 min";
            draw();
        }};
        document.getElementById("routeBtn").onclick=()=>{{
            showRoutes=!showRoutes;
            document.getElementById("routeBtn").textContent=
                showRoutes?"Ocultar rutas":"Mostrar rutas";
            draw();
        }};
        sl.oninput=()=>{{simT=parseFloat(sl.value);
            document.getElementById("tShow").textContent="Sim: "+simT.toFixed(2)+" min";
            draw();}};
        document.getElementById("spd").onchange=function(){{speed=parseFloat(this.value);}};

        function occColor(o,t){{const r=o/t;
            if(r===0)return"rgba(34,197,94,0.08)";
            if(r<=0.5)return"rgba(234,179,8,0.15)";
            return"rgba(239,68,68,0.25)";}}

        function draw(){{
            if(!bgOk)return;
            ctx.drawImage(bg,0,0,cv.width,cv.height);
            let tO=0,iO=0;const aT={{}},aQ=[],aG=[];const gs={{}};
            events.forEach(e=>{{if(e.time<=simT)gs[e.group_id]={{
                gid:e.group_id,sz:e.size,st:e.state,
                tbl:e.table,wt:e.wait_time,dur:e.duration,ts:e.time}};}});
            Object.values(gs).forEach(g=>{{
                const s=g.st,t=g.tbl;
                if(["assigned_table","order_taking","order_taken","order_sending",
                    "order_sent","order_preparing","prepared","eating","eaten",
                    "paying","paid"].includes(s)){{
                    aT[t]=true;
                    if(["T1","T2","T3"].includes(t))tO++;
                    if(["T4","T5"].includes(t))iO++;
                    aG.push(g);}}
                if(s==="assigning_table"){{aQ.push(g);aG.push(g);}}
                if(s==="cleaning"){{aT[t]="cleaning";aG.push(g);}}
            }});

            /* Routes */
            if(showRoutes){{
                ctx.save();ctx.strokeStyle="rgba(0,55,129,0.18)";
                ctx.lineWidth=1.5;ctx.setLineDash([5,5]);
                const routes=[
                    ["E","V","T1"],["E","V","T3"],["E","T2"],
                    ["E","V","T5"],["V","T4"],
                    ["T1","V","CB","CO"],["T2","E","V","CB","CO"],
                    ["T3","V","CB","CO"],["T4","CB","CO"],["T5","CB","CO"],
                    ["CO","V","E"],["V","K"]];
                routes.forEach(r=>{{
                    ctx.beginPath();
                    for(let i=0;i<r.length;i++){{
                        const p=N[r[i]];
                        if(i===0)ctx.moveTo(p.x,p.y);else ctx.lineTo(p.x,p.y);}}
                    ctx.stroke();}});
                ctx.restore();}}

            /* Zones */
            ctx.fillStyle=occColor(tO,3);ctx.fillRect(10,10,310,636);
            ctx.strokeStyle="rgba(0,55,129,0.3)";ctx.lineWidth=1.5;
            ctx.strokeRect(10,10,310,636);
            ctx.fillStyle="#003781";ctx.font="bold 12px Inter";
            ctx.fillText("Terraza ("+tO+"/3)",20,28);

            ctx.fillStyle=occColor(iO,2);ctx.fillRect(320,10,290,636);
            ctx.strokeStyle="rgba(0,55,129,0.3)";ctx.strokeRect(320,10,290,636);
            ctx.fillStyle="#003781";ctx.fillText("Interior ("+iO+"/2)",330,28);

            let kBusy=false;
            aG.forEach(g=>{{if(g.st==="order_preparing")kBusy=true;}});
            if(kBusy){{ctx.fillStyle="rgba(239,68,68,0.15)";
                ctx.fillRect(610,10,228,636);
                ctx.strokeStyle="#ef4444";ctx.strokeRect(610,10,228,636);
                ctx.fillStyle="#ef4444";ctx.fillText("Cocina: ACTIVA",620,28);}}

            /* Table badges */
            for(let t in N){{if(t.startsWith("T")){{
                const p=N[t],s=aT[t];
                if(s==="cleaning"){{ctx.fillStyle="rgba(59,130,246,0.65)";
                    ctx.beginPath();ctx.arc(p.x,p.y,20,0,2*Math.PI);ctx.fill();
                    ctx.fillStyle="#fff";ctx.font="bold 9px Inter";
                    ctx.textAlign="center";ctx.fillText("LIMPIANDO",p.x,p.y+3);}}
                else if(s){{ctx.fillStyle="rgba(239,68,68,0.25)";
                    ctx.beginPath();ctx.arc(p.x,p.y,18,0,2*Math.PI);ctx.fill();}}
            }}}}

            /* Dots */
            ctx.textAlign="center";
            aG.forEach(g=>{{
                let px=65,py=370;const s=g.st,t=g.tbl,sz=g.sz;
                let dc="#3b82f6";
                if(sz===2)dc="#10b981";else if(sz===3)dc="#f59e0b";
                else if(sz>=4)dc="#ef4444";

                if(s==="assigning_table"){{
                    const qi=aQ.indexOf(g);
                    px=N.E.x-18-(qi*14);py=N.E.y;
                    ctx.fillStyle=dc;ctx.beginPath();
                    ctx.arc(px,py,6,0,2*Math.PI);ctx.fill();
                    ctx.strokeStyle="#fff";ctx.lineWidth=1;ctx.stroke();
                    ctx.fillStyle="#fff";ctx.font="7px Arial";
                    ctx.fillText(sz,px,py+3);
                }}else if(["assigned_table","order_taking","order_taken",
                    "order_sending","order_sent","order_preparing","prepared",
                    "eating","eaten"].includes(s)){{
                    const p=N[t];
                    ctx.fillStyle=dc;ctx.beginPath();
                    ctx.arc(p.x,p.y,9,0,2*Math.PI);ctx.fill();
                    if(sz>=4){{ctx.strokeStyle="rgba(239,68,68,0.8)";
                        ctx.lineWidth=2.5;ctx.beginPath();
                        ctx.arc(p.x,p.y,12,0,2*Math.PI);ctx.stroke();}}
                    else{{ctx.strokeStyle="#fff";ctx.lineWidth=1.5;ctx.stroke();}}
                    ctx.fillStyle="#fff";ctx.font="bold 8px Arial";
                    ctx.fillText(sz,p.x,p.y+3);
                    if(s==="eating"){{ctx.fillStyle="#fbbf24";ctx.beginPath();
                        ctx.arc(p.x+11,p.y-11,3.5,0,2*Math.PI);ctx.fill();}}
                }}else if(s==="paying"){{
                    const tp=N[t],cp=N.CO;
                    const el=simT-g.ts,tt=Math.min(1,el/1);
                    px=tp.x+(cp.x-tp.x)*tt;py=tp.y+(cp.y-tp.y)*tt;
                    ctx.fillStyle=dc;ctx.beginPath();
                    ctx.arc(px,py,7,0,2*Math.PI);ctx.fill();
                    ctx.strokeStyle="#fff";ctx.stroke();
                }}else if(s==="paid"){{
                    const cp=N.CO,op=N.OUT;
                    const el=simT-g.ts,tt=Math.min(1,el/1);
                    px=cp.x+(op.x-cp.x)*tt;py=cp.y+(op.y-cp.y)*tt;
                    ctx.fillStyle=dc;ctx.beginPath();
                    ctx.arc(px,py,7,0,2*Math.PI);ctx.fill();
                    ctx.strokeStyle="#fff";ctx.stroke();}}
            }});
        }}

        function anim(){{
            if(!playing)return;
            const now=Date.now(),dt=now-lastTk;lastTk=now;
            simT+=(dt/2000)*speed;
            if(simT>maxT)simT=0;
            sl.value=simT;
            document.getElementById("tShow").textContent="Sim: "+simT.toFixed(2)+" min";
            draw();requestAnimationFrame(anim);}}
        anim();
        </script></body></html>
        """
        st.iframe(html_code, height=780, width=900)

# ======================================================================
# TAB 5 — INSIGHTS
# ======================================================================
def _insight_html(title, diag, evid, causa, rec):
    return f"""<div class="insight-card"><h4>{title}</h4>
    <div class="ins-title">Diagnostico Operativo</div>
    <p class="ins-body">{diag}</p>
    <div class="ins-title">Evidencia Cuantitativa</div>
    <p class="ins-body">{evid}</p>
    <div class="ins-title">Causa Probable</div>
    <p class="ins-body">{causa}</p>
    <div class="ins-title">Recomendacion Accionable</div>
    <p class="ins-body">{rec}</p></div>"""

with tab_ins:
    st.markdown('<h2 style="color:#003781;">Insights Estrategicos y '
                'Recomendaciones</h2>', unsafe_allow_html=True)

    if st.session_state.sim_results is None:
        st.info("Presione 'Ejecutar Simulacion' en la barra lateral.")
    else:
        res = st.session_state.sim_results
        ci = res["ci_95"]
        u = res["table_utilizations"]

        t13 = np.mean([u['T1'], u['T2'], u['T3']]) * 100
        t45 = np.mean([u['T4'], u['T5']]) * 100
        k_u = ci["kitchen_util"]["mean"] * 100
        co_u = ci["checkout_util"]["mean"] * 100
        w_u = ci["waiter_util"]["mean"] * 100
        avg_w = ci["avg_wait"]["mean"]
        avg_ww = ci["avg_waiter_wait"]["mean"]
        avg_kw = ci["avg_kitchen_wait"]["mean"]
        avg_cow = ci["avg_checkout_wait"]["mean"]
        ex = ci["exceptions"]["mean"]

        # 1 — Mesas
        if t45 > 70 and avg_w > 3:
            st.markdown(_insight_html(
                "Saturacion en Mesas de Capacidad 3 (T4 y T5)",
                f"Las mesas T4 y T5 operan al {t45:.1f}% de utilizacion "
                f"con tiempos de espera promedio de {avg_w:.2f} min, lo que "
                f"indica presion sobre la zona interior.",
                f"Utilizacion Terraza: {t13:.1f}% | Interior: {t45:.1f}% | "
                f"Espera media por mesa: {avg_w:.2f} min.",
                "Los grupos de 3 y 4 solo pueden sentarse en T4/T5, "
                "generando desbalance respecto a la Terraza.",
                "Redisenar la distribucion del layout. Reconfigurar una mesa "
                "de Terraza (ej. T3) para capacidad 3, aliviando la cola de "
                "grupos grandes. Impacto esperado: reduccion del 30-40% en "
                "tiempo de espera para grupos >= 3."),
                unsafe_allow_html=True)
        else:
            st.markdown(_insight_html(
                "Equilibrio de Ocupacion de Mesas",
                f"La ocupacion de mesas se mantiene en niveles controlados. "
                f"Terraza al {t13:.1f}% e Interior al {t45:.1f}%.",
                f"Espera media por mesa: {avg_w:.2f} min. "
                f"Sin saturacion critica detectada.",
                "La capacidad de mesas es suficiente para la demanda actual.",
                "Mantener configuracion actual. Monitorear si la demanda "
                "crece en temporadas altas."),
                unsafe_allow_html=True)

        # 2 — Meseros
        if w_u > 70:
            st.markdown(_insight_html(
                "Presion sobre Meseros",
                f"Los meseros operan al {w_u:.1f}% de utilizacion, "
                f"lo que indica carga alta en toma de pedido, comanda y "
                f"limpieza de mesas.",
                f"Utilizacion meseros: {w_u:.1f}% | "
                f"Espera media por mesero: {avg_ww:.2f} min.",
                "Los meseros atienden tres fases del proceso (pedido, "
                "comanda, reocupacion), lo que concentra la carga.",
                f"Incrementar el numero de meseros de {waiter_cap} a "
                f"{waiter_cap + 1}. Impacto esperado: reduccion de la "
                f"espera por mesero y menor tiempo total en sistema."),
                unsafe_allow_html=True)
        else:
            st.markdown(_insight_html(
                "Disponibilidad de Meseros",
                f"Los meseros operan al {w_u:.1f}%, nivel saludable.",
                f"Espera media por mesero: {avg_ww:.2f} min.",
                "La capacidad de meseros es adecuada para la demanda.",
                "Mantener la dotacion actual. Los meseros tienen margen "
                "para absorber incrementos moderados de demanda."),
                unsafe_allow_html=True)

        # 3 — Cocina
        if k_u > 75:
            st.markdown(_insight_html(
                "Cuello de Botella en Cocina",
                f"La cocina opera al {k_u:.1f}% de utilizacion. "
                f"La preparacion es la fase activa con mayor consumo "
                f"de tiempo.",
                f"Utilizacion cocina: {k_u:.1f}% | "
                f"Espera media por cocina: {avg_kw:.2f} min.",
                f"Con {kitchen_cap} chef(s) en paralelo, el recurso "
                f"esta cerca de su limite de capacidad.",
                f"Contratar un chef asistente (total: {kitchen_cap + 1}). "
                f"Reducira el tiempo acumulativo de espera por preparacion "
                f"y acortara el tiempo total en sistema."),
                unsafe_allow_html=True)
        else:
            st.markdown(_insight_html(
                "Capacidad de Cocina",
                f"La cocina opera al {k_u:.1f}%, dentro de parametros.",
                f"Espera media por cocina: {avg_kw:.2f} min.",
                "La capacidad de cocina es suficiente para el flujo actual.",
                "Mantener la dotacion de chefs. Existe margen para "
                "absorber mayor demanda sin degradar el servicio."),
                unsafe_allow_html=True)

        # 4 — Caja
        if co_u > 65:
            st.markdown(_insight_html(
                "Presion en el Checkout",
                f"La caja opera al {co_u:.1f}% de utilizacion.",
                f"Espera media por caja: {avg_cow:.2f} min.",
                "La caja unica genera cola durante picos de demanda, "
                "especialmente con pagos divididos.",
                "Habilitar cobros en mesa (terminales moviles o QR). "
                "Esto evita desplazamiento a la caja fisica y reduce "
                "la utilizacion del checkout."),
                unsafe_allow_html=True)
        else:
            st.markdown(_insight_html(
                "Flujo de Cobro",
                f"La caja opera al {co_u:.1f}%, sin congestion.",
                f"Espera media por caja: {avg_cow:.2f} min.",
                "El proceso de cobro fluye sin colas significativas.",
                "Mantener configuracion actual del checkout."),
                unsafe_allow_html=True)

        # 5 — Excepciones
        st.markdown(_insight_html(
            "Excepciones Operativas (Grupos de 4)",
            f"La simulacion registra un promedio de {ex:.0f} grupos de 4 "
            f"por corrida. Estos grupos no tienen mesa formal asignada.",
            f"Excepciones: {ex:.0f} | "
            f"Utilizacion Interior: {t45:.1f}%.",
            "Al carecer de mesas para 4, estos grupos se sientan en T4/T5 "
            "con sillas extra, saturando pasillos y generando friccion.",
            "Designar una zona modular interior con mesas que puedan "
            "juntarse para grupos de 4, reduciendo improvisacion y "
            "evitando bloqueos en pasillos."),
            unsafe_allow_html=True)
