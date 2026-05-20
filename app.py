import streamlit as st
import streamlit.components.v1 as components
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

# Page Configuration
st.set_page_config(
    page_title="HUGO CAFÉ - Simulation Project",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Design (#003781)
st.markdown("""
<style>
    :root {
        --primary-blue: #003781;
    }
    .main-title {
        color: #003781;
        font-family: 'Outfit', 'Inter', sans-serif;
        font-weight: 700;
        font-size: 2.5rem;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #64748b;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    .kpi-card {
        background-color: #ffffff;
        border-radius: 8px;
        padding: 1.2rem;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        border-left: 5px solid #003781;
        margin-bottom: 1rem;
    }
    .kpi-value {
        color: #003781;
        font-size: 1.8rem;
        font-weight: 700;
        margin-bottom: 0.1rem;
    }
    .kpi-label {
        color: #475569;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .kpi-ci {
        color: #64748b;
        font-size: 0.75rem;
        margin-top: 0.2rem;
    }
    .section-header {
        color: #003781;
        border-bottom: 2px solid #e2e8f0;
        padding-bottom: 0.5rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Session State Initialization
if 'fits' not in st.session_state:
    st.session_state.fits = None
if 'df_clean' not in st.session_state:
    st.session_state.df_clean = None
if 'validation' not in st.session_state:
    st.session_state.validation = None
if 'sim_results' not in st.session_state:
    st.session_state.sim_results = None
if 'event_log' not in st.session_state:
    st.session_state.event_log = None

# Sidebar branding & controls
st.sidebar.markdown(
    f'<div style="text-align: center;"><h2 style="color:#003781;margin-bottom:0px;">☕ HUGO CAFÉ</h2>'
    f'<p style="color:#64748b;font-size:0.9rem;margin-top:0px;">Simulador de Eventos Discretos</p></div>',
    unsafe_allow_html=True
)

st.sidebar.markdown("---")

# 1. File Upload Section
st.sidebar.subheader("📁 Carga de Archivos")
uploaded_excel = st.sidebar.file_uploader("Cargar Datos (.xlsx)", type=["xlsx"])
uploaded_layout = st.sidebar.file_uploader("Cargar Layout (.png)", type=["png"])

# Standard paths in workspace
DEFAULT_EXCEL_PATH = r"c:\Proyectos antigvty\Simulador\HUGO_CAFE_DataFase1-4.xlsx"
DEFAULT_LAYOUT_PATH = r"c:\Proyectos antigvty\Simulador\Layout.png"

excel_path = DEFAULT_EXCEL_PATH
layout_path = DEFAULT_LAYOUT_PATH

# Write uploaded files to disk if present, else fallback to defaults
if uploaded_excel is not None:
    temp_excel_path = os.path.join(os.getcwd(), "temp_data.xlsx")
    with open(temp_excel_path, "wb") as f:
        f.write(uploaded_excel.getbuffer())
    excel_path = temp_excel_path
    st.sidebar.success("Excel cargado correctamente.")

if uploaded_layout is not None:
    temp_layout_path = os.path.join(os.getcwd(), "temp_layout.png")
    with open(temp_layout_path, "wb") as f:
        f.write(uploaded_layout.getbuffer())
    layout_path = temp_layout_path
    st.sidebar.success("Layout cargado correctamente.")

# Load Data initially or if changed
@st.cache_data
def get_cached_data(path):
    return load_and_validate_data(path)

if excel_path and os.path.exists(excel_path):
    df_clean, validation = get_cached_data(excel_path)
    if validation["success"]:
        st.session_state.df_clean = df_clean
        st.session_state.validation = validation
        # Fit distributions initially
        if st.session_state.fits is None:
            st.session_state.fits = fit_distributions(df_clean)
    else:
        st.sidebar.error("Error al validar el Excel cargado.")
        for err in validation["errors"]:
            st.sidebar.write(f"- {err}")

# Sidebar controls for Simulation Run
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Configuración del Modelo")

runs_count = st.sidebar.selectbox("Número de Corridas (Runs)", [10, 20, 30, 40, 50], index=1)
kitchen_capacity = st.sidebar.slider("Capacidad Cocina (Chefs)", 1, 5, 2)
checkout_capacity = st.sidebar.slider("Capacidad Caja (Cajeros)", 1, 3, 1)

# Distribution Override Config in Sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Selección de Distribuciones")

user_distributions = {}
if st.session_state.fits is not None:
    process_labels = {
        'Interarribo_min': 'Llegadas (Interarribo)',
        'Toma_Pedido_min': 'Toma de Pedido',
        'Preparacion_min': 'Preparación en Cocina',
        'Consumo_min': 'Consumo en Mesa',
        'Tiempo_Reocupacion_Mesa_min': 'Reocupación / Limpieza'
    }
    
    for col, label in process_labels.items():
        fit_res = st.session_state.fits[col]
        best_dist = fit_res['best']
        
        # Display best fit as recommended first
        options = ['empirical', 'lognormal', 'triangular', 'exponential']
        # Map nice Spanish labels
        option_labels = {
            'empirical': 'Empírica (Histórica)',
            'lognormal': 'Lognormal',
            'triangular': 'Triangular',
            'exponential': 'Exponencial'
        }
        
        # Format recommended prefix
        nice_options = [option_labels[o] if o != best_dist else f"⭐ {option_labels[o]} (Recomendada)" for o in options]
        selected_nice = st.sidebar.selectbox(f"{label}", nice_options, index=options.index(best_dist))
        
        # Map back to raw key
        selected_raw = options[nice_options.index(selected_nice)]
        user_distributions[col] = selected_raw
        
    # Pago_min is always empirical by fallback
    user_distributions['Pago_min'] = 'empirical'

# Navigation Tabs (White/Blue Theme)
tab_dashboard, tab_fitting, tab_validation, tab_animation, tab_insights = st.tabs([
    "📋 Dashboard AS-IS", 
    "📈 Inferencia de Entrada", 
    "✅ Validación de Reglas", 
    "🎥 Animación 2D", 
    "💡 Insights de Simulación"
])

# Running Simulation trigger
if st.session_state.df_clean is not None:
    if st.sidebar.button("▶️ Ejecutar Simulación DES", use_container_width=True):
        with st.spinner("Corriendo simulaciones de eventos discretos en SimPy..."):
            aggregated_results, event_log = run_multi_simulation(
                runs_count, 
                st.session_state.fits, 
                user_distributions,
                max_groups=len(st.session_state.df_clean),
                kitchen_cap=kitchen_capacity,
                checkout_cap=checkout_capacity
            )
            st.session_state.sim_results = aggregated_results
            st.session_state.event_log = event_log
            st.success("¡Simulación completada con éxito!")

# --- TAB 1: DASHBOARD AS-IS ---
with tab_dashboard:
    st.markdown('<h1 class="main-title">HUGO CAFÉ Simulation Project</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-title">Modelado AS-IS y optimización de flujos de servicio del restaurante</p>', unsafe_allow_html=True)
    
    if st.session_state.sim_results is None:
        st.info("👋 ¡Bienvenido! Por favor presione el botón **'Ejecutar Simulación DES'** en la barra lateral para generar el dashboard y los resultados.")
    else:
        res = st.session_state.sim_results
        ci = res["ci_95"]
        
        st.markdown('<h3 class="section-header">Variables e Indicadores Clave de Desempeño (KPIs)</h3>', unsafe_allow_html=True)
        
        # Renders KPIs Cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Grupos Atendidos</div>
                <div class="kpi-value">{ci["groups_served"]["mean"]:.1f}</div>
                <div class="kpi-ci">Rango: [{ci["groups_served"]["min"]:.0f} - {ci["groups_served"]["max"]:.0f}]</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Tiempo Total en Sistema</div>
                <div class="kpi-value">{ci["avg_system"]["mean"]:.2f} min</div>
                <div class="kpi-ci">IC 95%: [{ci["avg_system"]["ci_lower"]:.2f} - {ci["avg_system"]["ci_upper"]:.2f}]</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col3:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Tiempo Promedio de Espera</div>
                <div class="kpi-value">{ci["avg_wait"]["mean"]:.2f} min</div>
                <div class="kpi-ci">IC 95%: [{ci["avg_wait"]["ci_lower"]:.2f} - {ci["avg_wait"]["ci_upper"]:.2f}]</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col4:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-label">Excepciones (Grupos de 4)</div>
                <div class="kpi-value">{ci["exceptions"]["mean"]:.1f}</div>
                <div class="kpi-ci">Fricción en T4 y T5</div>
            </div>
            """, unsafe_allow_html=True)
            
        # Renders Dashboard Plots
        st.markdown('<h3 class="section-header">Análisis de Desempeño y Cuellos de Botella</h3>', unsafe_allow_html=True)
        col_left, col_right = st.columns(2)
        
        with col_left:
            # Phase Bottlenecks plot
            fig_process = plot_process_times(res["activity_averages"])
            st.plotly_chart(fig_process, use_container_width=True)
            
        with col_right:
            # Resource Utilisation plot
            fig_res = plot_resource_utilization(
                res["table_utilizations"], 
                res["ci_95"]["kitchen_util"]["mean"], 
                res["ci_95"]["checkout_util"]["mean"]
            )
            st.plotly_chart(fig_res, use_container_width=True)
            
        # Wait time distribution and detailed raw runs
        col_low_left, col_low_right = st.columns([3, 2])
        with col_low_left:
            # Wait times distribution plot from event log (first run)
            wait_times = [e["wait_time"] for e in st.session_state.event_log if e["state"] == "assigned_table"]
            fig_wait = plot_waiting_times_distribution(wait_times)
            st.plotly_chart(fig_wait, use_container_width=True)
            
        with col_low_right:
            st.markdown('<div style="margin-top:1.5rem;"></div>', unsafe_allow_html=True)
            st.subheader("📊 Historial de Corridas")
            df_runs = pd.DataFrame(res["raw_runs"])
            df_runs.columns = ["Grupos Servidos", "Duración (min)", "T. Espera Medio (min)", "T. Espera Máximo (min)", "T. Sistema Medio (min)", "Util. Cocina", "Util. Caja", "Excepciones"]
            st.dataframe(df_runs.style.format(precision=2), height=280, use_container_width=True)

# --- TAB 2: INPUT ANALYSIS & FITTING ---
with tab_fitting:
    st.markdown('<h2 style="color:#003781;">Inferencia y Ajuste de Distribuciones de Entrada</h2>', unsafe_allow_html=True)
    st.write(
        "Ajuste estadístico de curvas de probabilidad utilizando la prueba de bondad de ajuste de **Kolmogorov-Smirnov** (KS) "
        "sobre el conjunto de 350 observaciones empíricas recolectadas para el modelo AS-IS."
    )
    
    if st.session_state.fits is None:
        st.warning("⚠️ No hay datos cargados para realizar el ajuste. Por favor cargue un archivo Excel válido.")
    else:
        cols_to_fit = {
            'Interarribo_min': 'Tiempos de Interarribo (min)',
            'Toma_Pedido_min': 'Tiempo de Toma de Pedido (min)',
            'Preparacion_min': 'Tiempo de Preparación de Alimentos (min)',
            'Consumo_min': 'Tiempo de Consumo en Mesa (min)',
            'Tiempo_Reocupacion_Mesa_min': 'Tiempo de Reocupación y Limpieza (min)'
        }
        
        selected_col = st.selectbox("Seleccione el proceso para analizar la bondad de ajuste:", list(cols_to_fit.keys()), format_func=lambda x: cols_to_fit[x])
        
        col_fit_left, col_fit_right = st.columns([3, 2])
        
        with col_fit_left:
            # Goodness-of-Fit Plot
            fig_gof = plot_distribution_fitting(st.session_state.df_clean, selected_col, st.session_state.fits[selected_col])
            st.plotly_chart(fig_gof, use_container_width=True)
            
        with col_fit_right:
            st.markdown('<div style="margin-top:1.5rem;"></div>', unsafe_allow_html=True)
            st.subheader("📈 Tabla Comparativa de Parámetros")
            fit_res = st.session_state.fits[selected_col]
            
            records = []
            for dist in ['lognormal', 'triangular', 'exponential']:
                if dist in fit_res and 'p_value' in fit_res[dist]:
                    p_val = fit_res[dist]['p_value']
                    stat = fit_res[dist].get('statistic', 0.0)
                    decision = "Aceptada (p > 0.05)" if p_val > 0.05 else "Rechazada (p <= 0.05)"
                    records.append({
                        "Distribución": dist.upper(),
                        "Estadístico KS": f"{stat:.4f}",
                        "Valor-p (p-value)": f"{p_val:.4f}",
                        "Decisión": decision
                    })
            
            # Add Empirical
            records.append({
                "Distribución": "EMPÍRICA",
                "Estadístico KS": "0.0000",
                "Valor-p (p-value)": "1.0000",
                "Decisión": "Aceptada (Respaldo por Defecto)"
            })
            
            df_gof_table = pd.DataFrame(records)
            st.table(df_gof_table)
            
            # Show fitted parameters
            best_d = fit_res['best']
            st.info(f"💡 **Recomendación Matemática**: La distribución **{best_d.upper()}** es la recomendada para este proceso.")
            
            if best_d != 'empirical' and best_d in fit_res:
                st.markdown("**Parámetros Ajustados:**")
                params = fit_res[best_d]['params']
                for k, v in params.items():
                    st.write(f"- `{k}`: {v:.4f}")

# --- TAB 3: DATA VALIDATION & RULES ---
with tab_validation:
    st.markdown('<h2 style="color:#003781;">Validación Operativa y de Reglas de Negocio</h2>', unsafe_allow_html=True)
    st.write("Verificación de inconsistencias, tiempos negativos y cumplimiento de reglas operativas en los datos cargados.")
    
    if st.session_state.validation is None:
        st.warning("⚠️ No hay datos cargados para validar.")
    else:
        val = st.session_state.validation
        metrics = val["metrics"]
        
        # Display validation checks status
        st.subheader("Estado de las Validaciones")
        
        col_chk1, col_chk2 = st.columns(2)
        with col_chk1:
            st.success("✅ **Comprobación de Tiempos Negativos**: Completada (0 valores negativos detectados).")
            st.success("✅ **Comprobación de Identificadores (ID)**: Completada (Estructura de ID secuencial correcta).")
            
        with col_chk2:
            if len(val["warnings"]) == 0:
                st.success("✅ **Comprobación de Reglas de Capacidad**: Correcta. Todos los grupos y asignaciones respetan las capacidades.")
            else:
                st.warning(f"⚠️ **Alineaciones Operativas / Excepciones Detectadas**: Se encontraron {len(val['warnings'])} notas.")

        # Show detailed warnings if any
        if val["warnings"]:
            st.markdown("---")
            st.subheader("⚠️ Advertencias y Excepciones Operativas Detectadas en los Datos Históricos:")
            for warn in val["warnings"]:
                st.markdown(f"- {warn}")
                
        st.markdown("---")
        st.subheader("📊 Métricas de Validación del Ingesta")
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric("Total Observaciones", f"{metrics['total_records']} grupos")
            st.metric("Grupos de 4 (Excepciones)", f"{metrics['total_exceptions']} obs")
        with col_m2:
            st.metric("Tiempo de Interarribo Medio", f"{metrics['average_interarrival']:.2f} min")
            st.metric("Tiempo de Mesa Medio", f"{metrics['average_table_time']:.2f} min")
        with col_m3:
            st.write("**Distribución de Mesas en Datos:**")
            st.write(metrics["tables_count"])

# --- TAB 4: LAYOUT & ANIMATION CANVAS 2D ---
with tab_animation:
    st.markdown('<h2 style="color:#003781;">Simulación Física en Tiempo Real: Animación sobre Layout</h2>', unsafe_allow_html=True)
    st.write(
        "Visualización espacial de flujos de clientes (Spaghetti diagram). Los círculos de colores representan los grupos de clientes "
        "desplazándose a lo largo de las rutas de servicio. Las zonas cambian de color "
        "(Verde $\\rightarrow$ Amarillo $\\rightarrow$ Rojo) según el nivel de ocupación de las mesas."
    )
    
    if st.session_state.event_log is None:
        st.info("👋 Por favor presione **'Ejecutar Simulación DES'** en la barra lateral para generar la animación espacial.")
    else:
        # Load and base64 encode Layout.png
        try:
            with open(layout_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode()
        except Exception as e:
            st.error(f"Error al abrir la imagen del layout: {e}")
            encoded_string = ""
            
        # Serialize the event log to JSON
        event_log_json = json.dumps(st.session_state.event_log)
        
        # HTML5 Canvas Component
        html_code = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Inter', sans-serif;
                    margin: 0;
                    padding: 0;
                    background-color: #f8fafc;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                }}
                #canvas-container {{
                    position: relative;
                    box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
                    border-radius: 8px;
                    overflow: hidden;
                    background: #ffffff;
                }}
                canvas {{
                    display: block;
                }}
                #controls {{
                    width: 848px;
                    margin-top: 15px;
                    background: #ffffff;
                    padding: 15px;
                    border-radius: 8px;
                    box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    box-sizing: border-box;
                }}
                .btn {{
                    background-color: #003781;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    cursor: pointer;
                    font-weight: 600;
                    transition: background-color 0.2s;
                }}
                .btn:hover {{
                    background-color: #1e3a8a;
                }}
                .control-group {{
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }}
                .time-display {{
                    font-size: 0.95rem;
                    font-weight: 700;
                    color: #003781;
                    min-width: 140px;
                }}
                #timeline {{
                    flex-grow: 1;
                    margin: 0 20px;
                    cursor: pointer;
                }}
                select {{
                    padding: 6px;
                    border-radius: 4px;
                    border: 1px solid #cbd5e1;
                    font-weight: 600;
                    color: #334155;
                }}
                .legend {{
                    width: 848px;
                    margin-top: 10px;
                    display: flex;
                    justify-content: center;
                    gap: 15px;
                    font-size: 0.8rem;
                    color: #475569;
                    flex-wrap: wrap;
                }}
                .legend-item {{
                    display: flex;
                    align-items: center;
                    gap: 5px;
                }}
                .legend-dot {{
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                }}
            </style>
        </head>
        <body>

            <div id="canvas-container">
                <canvas id="layoutCanvas" width="848" height="656"></canvas>
            </div>

            <div id="controls">
                <button id="playBtn" class="btn">Pausa</button>
                <div class="control-group" style="flex-grow: 1; display: flex; align-items: center;">
                    <span class="time-display" id="timeShow">Sim: 0.00 min</span>
                    <input type="range" id="timeline" min="0" max="1000" value="0">
                </div>
                <div class="control-group">
                    <span style="font-size:0.85rem;color:#475569;font-weight:600;">Velocidad:</span>
                    <select id="speedSel">
                        <option value="0.5">0.5x</option>
                        <option value="1" selected>1.0x (Normal)</option>
                        <option value="2">2.0x</option>
                        <option value="5">5.0x</option>
                        <option value="10">10.0x</option>
                    </select>
                </div>
            </div>

            <div class="legend">
                <div class="legend-item"><div class="legend-dot" style="background:#3b82f6;"></div> Grupo de 1 (Azul)</div>
                <div class="legend-item"><div class="legend-dot" style="background:#10b981;"></div> Grupo de 2 (Verde)</div>
                <div class="legend-item"><div class="legend-dot" style="background:#f59e0b;"></div> Grupo de 3 (Naranja)</div>
                <div class="legend-item"><div class="legend-dot" style="background:#ef4444;"></div> Grupo de 4 (Excepción - Rojo)</div>
                <div class="legend-item"><div class="legend-dot" style="border: 2px dashed #003781; width:8px; height:8px; border-radius:0;"></div> Zonas de Ocupación (Verde &rarr; Amarillo &rarr; Rojo)</div>
            </div>

            <script>
                // Load embedded simulation events
                const events = {event_log_json};
                const bgImageBase64 = "data:image/png;base64,{encoded_string}";
                
                const canvas = document.getElementById("layoutCanvas");
                const ctx = canvas.getContext("2d");
                
                // Load background image
                const bgImg = new Image();
                bgImg.src = bgImageBase64;
                let bgLoaded = false;
                bgImg.onload = () => {{ bgLoaded = true; draw(); }};

                // Node physical coordinates grid calibrated on Layout.png
                const nodes = {{
                    "E": {{x: 65, y: 370}},
                    "L": {{x: 65, y: 370}},
                    "V": {{x: 280, y: 370}},
                    "T1": {{x: 65, y: 190}},
                    "T2": {{x: 65, y: 590}},
                    "T3": {{x: 270, y: 190}},
                    "T4": {{x: 410, y: 590}},
                    "T5": {{x: 410, y: 460}},
                    "K": {{x: 750, y: 250}},
                    "CB": {{x: 560, y: 370}},
                    "CO": {{x: 550, y: 580}},
                    "OUT": {{x: 65, y: 370}}
                }};

                // Playback parameters
                let isPlaying = true;
                let simTime = 0.0; // Current simulation minutes
                let playbackSpeed = 1.0; // Real seconds = sim minutes * playbackSpeed? No. 
                // Let's define the tick interval
                const frameRate = 30; // 30 FPS
                let lastTick = Date.now();
                
                // Get simulation duration
                const maxSimTime = Math.max(...events.map(e => e.time));
                
                // Setup slider range
                const slider = document.getElementById("timeline");
                slider.max = Math.ceil(maxSimTime);
                
                // Setup control events
                const playBtn = document.getElementById("playBtn");
                playBtn.onclick = () => {{
                    isPlaying = !isPlaying;
                    playBtn.textContent = isPlaying ? "Pausa" : "Reproducir";
                    if (isPlaying) {{
                        lastTick = Date.now();
                        animate();
                    }}
                }};
                
                slider.oninput = () => {{
                    simTime = parseFloat(slider.value);
                    document.getElementById("timeShow").textContent = "Sim: " + simTime.toFixed(2) + " min";
                    draw();
                }};
                
                const speedSel = document.getElementById("speedSel");
                speedSel.onchange = () => {{
                    playbackSpeed = parseFloat(speedSel.value);
                }};

                // Dynamic simulation execution loop
                function animate() {{
                    if (!isPlaying) return;
                    
                    const now = Date.now();
                    const deltaMs = now - lastTick;
                    lastTick = now;
                    
                    // 1 simulated minute = 2 real seconds at 1x
                    // So deltaSimMinutes = (deltaMs / 2000) * playbackSpeed
                    const deltaSim = (deltaMs / 2000) * playbackSpeed;
                    
                    simTime += deltaSim;
                    if (simTime > maxSimTime) {{
                        simTime = 0.0; // Loop simulation
                    }}
                    
                    slider.value = simTime;
                    document.getElementById("timeShow").textContent = "Sim: " + simTime.toFixed(2) + " min";
                    
                    draw();
                    requestAnimationFrame(animate);
                }}

                // Calculate color from occupation density
                function getOccupancyColor(occupied, total) {{
                    const ratio = occupied / total;
                    if (ratio === 0) return "rgba(34, 197, 94, 0.08)"; // Very light green
                    if (ratio <= 0.5) return "rgba(234, 179, 8, 0.15)"; // Soft yellow
                    return "rgba(239, 68, 68, 0.25)"; // Soft transparent red
                }}

                function draw() {{
                    if (!bgLoaded) return;
                    
                    // Draw Layout Background
                    ctx.drawImage(bgImg, 0, 0, canvas.width, canvas.height);
                    
                    // Compile occupancy active status at current simTime
                    let terraceOccupied = 0;
                    let indoorOccupied = 0;
                    
                    const activeTables = {{}};
                    const activeQueue = [];
                    const activeGroups = [];
                    
                    // Analyze event log state at simTime
                    // We gather groups and their state at this timestamp
                    const groupsStates = {{}};
                    
                    events.forEach(e => {{
                        if (e.time <= simTime) {{
                            // Update group's latest state
                            groupsStates[e.group_id] = {{
                                group_id: e.group_id,
                                size: e.size,
                                state: e.state,
                                table: e.table,
                                wait_time: e.wait_time,
                                duration: e.duration,
                                timestamp: e.time
                            }};
                        }}
                    }});
                    
                    Object.values(groupsStates).forEach(g => {{
                        const state = g.state;
                        const table = g.table;
                        
                        // Active seated groups
                        if (["assigned_table", "order_taking", "order_taken", "order_sending", "order_sent", "order_preparing", "prepared", "eating", "eaten", "paying", "paid"].includes(state)) {{
                            activeTables[table] = true;
                            if (["T1", "T2", "T3"].includes(table)) terraceOccupied++;
                            if (["T4", "T5"].includes(table)) indoorOccupied++;
                            
                            activeGroups.push(g);
                        }}
                        
                        // Active waiting in queue groups
                        if (state === "assigning_table") {{
                            activeQueue.push(g);
                            activeGroups.push(g);
                        }}
                        
                        // Clean/reset state
                        if (state === "cleaning") {{
                            activeTables[table] = "cleaning";
                            activeGroups.push(g);
                        }}
                    }});

                    // 1. Draw Zones Heatmap / Overlays
                    // Terrace Zone: Left Area: X: [10, 320], Y: [10, 646]
                    ctx.fillStyle = getOccupancyColor(terraceOccupied, 3);
                    ctx.fillRect(10, 10, 310, 636);
                    ctx.strokeStyle = "rgba(0, 55, 129, 0.4)";
                    ctx.lineWidth = 2;
                    ctx.strokeRect(10, 10, 310, 636);
                    ctx.fillStyle = "#003781";
                    ctx.font = "bold 13px Inter";
                    ctx.fillText("Zona Terraza (" + terraceOccupied + "/3)", 20, 30);

                    // Indoor Zone: Central Area: X: [320, 610], Y: [10, 646]
                    ctx.fillStyle = getOccupancyColor(indoorOccupied, 2);
                    ctx.fillRect(320, 10, 290, 636);
                    ctx.strokeStyle = "rgba(0, 55, 129, 0.4)";
                    ctx.strokeRect(320, 10, 290, 636);
                    ctx.fillStyle = "#003781";
                    ctx.fillText("Zona Interior (" + indoorOccupied + "/2)", 330, 30);
                    
                    // Indicate Kitchen status if active preparation is happening
                    let kitchenBusy = false;
                    activeGroups.forEach(g => {{
                        if (g.state === "order_preparing") kitchenBusy = true;
                    }});
                    if (kitchenBusy) {{
                        ctx.fillStyle = "rgba(239, 68, 68, 0.2)";
                        ctx.fillRect(610, 10, 228, 636);
                        ctx.strokeStyle = "#ef4444";
                        ctx.strokeRect(610, 10, 228, 636);
                        ctx.fillStyle = "#ef4444";
                        ctx.fillText("Cocina: PREPARANDO", 620, 30);
                    }}

                    // 2. Draw Table occupancy badges
                    for (let t in nodes) {{
                        if (t.startsWith("T")) {{
                            const pos = nodes[t];
                            const state = activeTables[t];
                            
                            if (state === "cleaning") {{
                                // Draw cleaning indicator (flashing light blue)
                                ctx.fillStyle = "rgba(59, 130, 246, 0.7)";
                                ctx.beginPath();
                                ctx.arc(pos.x, pos.y, 22, 0, 2 * Math.PI);
                                ctx.fill();
                                ctx.fillStyle = "white";
                                ctx.font = "bold 10px Inter";
                                ctx.textAlign = "center";
                                ctx.fillText("LIMPIANDO", pos.x, pos.y + 4);
                            }} else if (state) {{
                                // Occupied
                                ctx.fillStyle = "rgba(239, 68, 68, 0.3)";
                                ctx.beginPath();
                                ctx.arc(pos.x, pos.y, 20, 0, 2 * Math.PI);
                                ctx.fill();
                            }}
                        }}
                    }}

                    // 3. Draw Active Groups (dots)
                    ctx.textAlign = "center";
                    activeGroups.forEach(g => {{
                        let pos = {{x: 65, y: 370}}; // default Entrance
                        const state = g.state;
                        const table = g.table;
                        const size = g.size;
                        
                        // Select Dot color based on group size
                        let dotColor = "#3b82f6"; // size 1: Blue
                        if (size === 2) dotColor = "#10b981"; // Green
                        else if (size === 3) dotColor = "#f59e0b"; // Orange
                        else if (size === 4) dotColor = "#ef4444"; // Red (exception)
                        
                        if (state === "assigning_table") {{
                            // In Queue, stack them horizontally to the left of Entrance
                            const queueIdx = activeQueue.indexOf(g);
                            pos.x = nodes["E"].x - 20 - (queueIdx * 16);
                            pos.y = nodes["E"].y;
                            
                            // Draw waiting dot
                            ctx.fillStyle = dotColor;
                            ctx.beginPath();
                            ctx.arc(pos.x, pos.y, 7, 0, 2 * Math.PI);
                            ctx.fill();
                            ctx.strokeStyle = "white";
                            ctx.lineWidth = 1;
                            ctx.stroke();
                            
                            // Draw size number
                            ctx.fillStyle = "white";
                            ctx.font = "8px Arial";
                            ctx.fillText(size, pos.x, pos.y + 3);
                            
                        }} else if (["assigned_table", "order_taking", "order_taken", "order_sending", "order_sent", "order_preparing", "prepared", "eating", "eaten"].includes(state)) {{
                            // Sitting at table
                            pos = nodes[table];
                            
                            ctx.fillStyle = dotColor;
                            ctx.beginPath();
                            ctx.arc(pos.x, pos.y, 10, 0, 2 * Math.PI);
                            ctx.fill();
                            
                            // Special pulsating border for exception size 4
                            if (size === 4) {{
                                ctx.strokeStyle = "rgba(239, 68, 68, 0.8)";
                                ctx.lineWidth = 3;
                                ctx.beginPath();
                                ctx.arc(pos.x, pos.y, 13, 0, 2 * Math.PI);
                                ctx.stroke();
                            }} else {{
                                ctx.strokeStyle = "white";
                                ctx.lineWidth = 1.5;
                                ctx.stroke();
                            }}
                            
                            ctx.fillStyle = "white";
                            ctx.font = "bold 9px Arial";
                            ctx.fillText(size, pos.x, pos.y + 3);
                            
                            // Visual food indicator when eating
                            if (state === "eating") {{
                                ctx.fillStyle = "#fbbf24";
                                ctx.beginPath();
                                ctx.arc(pos.x + 12, pos.y - 12, 4, 0, 2 * Math.PI);
                                ctx.fill();
                            }}
                            
                        }} else if (state === "paying") {{
                            // Walking from Table to Checkout Cashier (CO)
                            // Linear transition interpolation based on state duration
                            const tablePos = nodes[table];
                            const coPos = nodes["CO"];
                            
                            // Walk is animated smoothly
                            // Let's interpolate between tablePos and coPos
                            // We can use a simple trigonometric transition
                            const elapsed = simTime - g.timestamp;
                            const duration = 1.0; // Assume 1 simulated minute walk
                            const t = Math.min(1.0, elapsed / duration);
                            
                            pos.x = tablePos.x + (coPos.x - tablePos.x) * t;
                            pos.y = tablePos.y + (coPos.y - tablePos.y) * t;
                            
                            ctx.fillStyle = dotColor;
                            ctx.beginPath();
                            ctx.arc(pos.x, pos.y, 8, 0, 2 * Math.PI);
                            ctx.fill();
                            ctx.strokeStyle = "white";
                            ctx.stroke();
                            
                        }} else if (state === "paid") {{
                            // Walking from Checkout Cashier (CO) to Exit (OUT/E)
                            const coPos = nodes["CO"];
                            const outPos = nodes["OUT"];
                            
                            const elapsed = simTime - g.timestamp;
                            const duration = 1.0;
                            const t = Math.min(1.0, elapsed / duration);
                            
                            pos.x = coPos.x + (outPos.x - coPos.x) * t;
                            pos.y = coPos.y + (outPos.y - coPos.y) * t;
                            
                            ctx.fillStyle = dotColor;
                            ctx.beginPath();
                            ctx.arc(pos.x, pos.y, 8, 0, 2 * Math.PI);
                            ctx.fill();
                            ctx.strokeStyle = "white";
                            ctx.stroke();
                        }}
                    }});
                }}

                // Start playback loop
                animate();
            </script>
        </body>
        </html>
        """
        
        # Render Canvas component in Streamlit page
        components.html(html_code, height=760, width=900)

# --- TAB 5: AUTOMATIC INSIGHTS ENGINE ---
with tab_insights:
    st.markdown('<h2 style="color:#003781;">Insights Estratégicos y Recomendaciones de Optimización</h2>', unsafe_allow_html=True)
    
    if st.session_state.sim_results is None:
        st.info("👋 Por favor presione **'Ejecutar Simulación DES'** en la barra lateral para generar recomendaciones personalizadas basadas en el modelo.")
    else:
        res = st.session_state.sim_results
        ci = res["ci_95"]
        utils = res["table_utilizations"]
        
        # Build logic based insights
        st.subheader("📋 Diagnóstico de la Operación")
        
        insights = []
        
        # 1. Table capacity rules check
        t13_util = np.mean([utils['T1'], utils['T2'], utils['T3']])
        t45_util = np.mean([utils['T4'], utils['T5']])
        
        st.markdown("### 🪑 Mesas y Capacidad Física")
        if t45_util > 0.80 and ci["avg_wait"]["mean"] > 5.0:
            st.markdown(
                f"> **[!WARNING] Saturación Crítica en Mesas de Capacidad 3 (T4 y T5)**:\n"
                f"> La utilización media de T4 y T5 es de **{t45_util*100:.1f}%** con un tiempo de espera de clientes de **{ci['avg_wait']['mean']:.2f} min**.\n"
                f"> Los grupos de 3 y 4 están saturando la zona interior del restaurante, mientras que la Terraza (T1-T3) tiene una utilización media de apenas **{t13_util*100:.1f}%**.\n"
                f"> **Acción Recomendada**: Rediseñar la distribución del layout. Se sugiere reconfigurar una de las mesas de la Terraza (ej. T3) para que tenga capacidad para 3 personas, aliviando la cola de grupos grandes."
            )
        else:
            st.markdown(
                f"> **[!NOTE] Equilibrio de Ocupación de Mesas**:\n"
                f"> La ocupación interior (T4-T5) es de **{t45_util*100:.1f}%** y la Terraza (T1-T3) es de **{t13_util*100:.1f}%**.\n"
                f"> Los tiempos de espera son saludables (**{ci['avg_wait']['mean']:.2f} min**)."
            )
            
        # 2. Kitchen Bottleneck Check
        st.markdown("### 🍳 Cocina (Preparación de Alimentos)")
        k_util = ci["kitchen_util"]["mean"]
        if k_util > 0.80:
            st.markdown(
                f"> **[!CAUTION] Cuello de Botella en la Cocina (Utilización: {k_util*100:.1f}%)**:\n"
                f"> La preparación es la fase de servicio activa con mayor consumo de tiempo. Con {kitchen_capacity} chef(s) en paralelo, el recurso está operando cerca de su límite.\n"
                f"> **Acción Recomendada**: Contratar un chef asistente para incrementar la capacidad de la cocina a **{kitchen_capacity + 1} chefs en paralelo**. "
                f"Esto reducirá el tiempo acumulativo que los clientes pasan esperando su comida en la mesa, acortando el tiempo total en sistema."
            )
        elif k_util > 0.50:
            st.markdown(
                f"> **[!TIP] Cocina en Capacidad Óptima (Utilización: {k_util*100:.1f}%)**:\n"
                f"> El recurso de cocina con {kitchen_capacity} chef(s) funciona eficientemente. No requiere intervención inmediata."
            )
        else:
            st.markdown(
                f"> **[!NOTE] Cocina con Capacidad Ociosa (Utilización: {k_util*100:.1f}%)**:\n"
                f"> Existe margen de crecimiento para atender mayor flujo de demanda con los {kitchen_capacity} chefs configurados."
            )
            
        # 3. Checkout cashiers check
        st.markdown("### 💳 Checkout y Cobro")
        c_util = ci["checkout_util"]["mean"]
        if c_util > 0.75:
            st.markdown(
                f"> **[!WARNING] Cuello de Botella en el Pago (Utilización: {c_util*100:.1f}%)**:\n"
                f"> La caja registradora única está cerca de saturarse durante los picos de demanda. Recuerde que el **9.0%** de los clientes dividen su cuenta en cuentas individuales (split checkout), triplicando el tiempo en caja.\n"
                f"> **Acción Recomendada**: Habilitar cobros inalámbricos directamente en mesa (ej. terminales móviles o códigos QR). "
                f"Esto evitará que los clientes tengan que levantarse de su mesa para ir a la caja física, reduciendo la utilización del checkout."
            )
        else:
            st.markdown(
                f"> **[!NOTE] Terminal de Cobro Fluido (Utilización: {c_util*100:.1f}%)**:\n"
                f"> La caja única con un cajero mantiene un nivel de servicio fluido sin colas significativas."
            )
            
        # 4. Exception mitigation (Groups of 4)
        st.markdown("### ⚠️ Excepciones Operativas (Grupos de 4)")
        avg_ex = ci["exceptions"]["mean"]
        st.markdown(
            f"> **[!IMPORTANT] Mitigación de Fricción Operativa**:\n"
            f"> La simulación registra un promedio de **{avg_ex:.1f} grupos de 4 personas** por corrida. "
            f"Al carecer de mesas con capacidad formal para 4 personas, estos grupos son sentados en T4/T5 obligando a añadir sillas extras "
            f"y saturando visualmente los pasillos.\n"
            f"> **Acción Recomendada**: Se aconseja designar un área en el interior con mesas modulares que puedan juntarse en caso de detectar reservas o llegadas de grupos de 4, "
            f"en lugar de comprometer la capacidad normal de T4 o T5 con aditamentos de sillas improvisadas."
        )
