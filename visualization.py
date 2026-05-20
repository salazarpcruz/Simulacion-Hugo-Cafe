import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import scipy.stats as stats

# Palette: Primary Blue #003781, Secondary Soft Blue #2563EB, Grey #64748B, light background
PRIMARY_COLOR = "#003781"
SECONDARY_COLOR = "#2563EB"
BG_COLOR = "#ffffff"
CARD_BG_COLOR = "#f8fafc"

def plot_process_times(activity_averages):
    """
    Renders a bar chart showing the average time spent in each process phase.
    """
    labels_mapping = {
        "toma_pedido": "Toma de Pedido",
        "comanda": "Envío de Comanda",
        "preparacion": "Preparación (Cocina)",
        "consumo": "Consumo (Mesa)",
        "pago": "Pago (Caja)",
        "reocupacion": "Reocupación (Limpieza)"
    }
    
    phases = list(activity_averages.keys())
    values = list(activity_averages.values())
    nice_labels = [labels_mapping.get(p, p) for p in phases]
    
    df = pd.DataFrame({
        "Fase del Proceso": nice_labels,
        "Tiempo Promedio (min)": values
    })
    
    # Sort logically by flow sequence
    flow_order = ["Toma de Pedido", "Envío de Comanda", "Preparación (Cocina)", "Consumo (Mesa)", "Pago (Caja)", "Reocupación (Limpieza)"]
    df["Fase del Proceso"] = pd.Categorical(df["Fase del Proceso"], categories=flow_order, ordered=True)
    df = df.sort_values("Fase del Proceso")
    
    fig = px.bar(
        df,
        x="Fase del Proceso",
        y="Tiempo Promedio (min)",
        text="Tiempo Promedio (min)",
        color_discrete_sequence=[PRIMARY_COLOR]
    )
    
    fig.update_traces(
        texttemplate='%{text:.2f} min',
        textposition='outside',
        marker_line_color='rgb(8,48,107)',
        marker_line_width=1.5,
        opacity=0.9
    )
    
    fig.update_layout(
        title={
            'text': "<b>Análisis de Tiempos por Fase del Proceso</b>",
            'y':0.95, 'x':0.5, 'xanchor': 'center', 'yanchor': 'top'
        },
        xaxis_title="Fase del Proceso",
        yaxis_title="Tiempo (minutos)",
        template="plotly_white",
        height=400,
        margin=dict(l=40, r=40, t=60, b=40)
    )
    
    return fig

def plot_resource_utilization(table_utils, kitchen_util, checkout_util):
    """
    Renders a bar chart comparing utilization of tables, kitchen, and checkout.
    """
    resources = []
    utilization = []
    categories = []
    
    # Tables T1-T3 (Terraza, Cap 2)
    for t in ['T1', 'T2', 'T3']:
        resources.append(f"Mesa {t} (Cap: 2)")
        utilization.append(table_utils.get(t, 0.0) * 100)
        categories.append("Terraza (Cap 2)")
        
    # Tables T4-T5 (Interior, Cap 3)
    for t in ['T4', 'T5']:
        resources.append(f"Mesa {t} (Cap: 3)")
        utilization.append(table_utils.get(t, 0.0) * 100)
        categories.append("Interior (Cap 3)")
        
    # Kitchen and Checkout
    resources.append("Cocina (Kitchen)")
    utilization.append(kitchen_util * 100)
    categories.append("Áreas de Servicio")
    
    resources.append("Caja (Checkout)")
    utilization.append(checkout_util * 100)
    categories.append("Áreas de Servicio")
    
    df = pd.DataFrame({
        "Recurso": resources,
        "Utilización (%)": utilization,
        "Categoría": categories
    })
    
    fig = px.bar(
        df,
        y="Recurso",
        x="Utilización (%)",
        color="Categoría",
        text="Utilización (%)",
        orientation="h",
        color_discrete_map={
            "Terraza (Cap 2)": "#3b82f6", # Soft blue
            "Interior (Cap 3)": "#1d4ed8", # Darker blue
            "Áreas de Servicio": PRIMARY_COLOR # Deep Navy #003781
        }
    )
    
    fig.update_traces(
        texttemplate='%{text:.1f}%',
        textposition='outside',
        opacity=0.9
    )
    
    fig.update_layout(
        title={
            'text': "<b>Porcentaje de Utilización de Recursos Operativos</b>",
            'y':0.95, 'x':0.5, 'xanchor': 'center', 'yanchor': 'top'
        },
        xaxis_title="Utilización (%)",
        yaxis_title="Recurso",
        xaxis=dict(range=[0, 115]), # Leave space for labels
        template="plotly_white",
        height=450,
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.2,
            xanchor="center",
            x=0.5
        )
    )
    
    return fig

def plot_waiting_times_distribution(wait_times):
    """
    Renders a histogram showing the distribution of queue waiting times.
    """
    if not wait_times:
        wait_times = [0.0]
        
    df = pd.DataFrame({"Tiempo de Espera (min)": wait_times})
    
    fig = px.histogram(
        df,
        x="Tiempo de Espera (min)",
        color_discrete_sequence=[SECONDARY_COLOR],
        nbins=20,
        opacity=0.85
    )
    
    fig.update_layout(
        title={
            'text': "<b>Distribución de los Tiempos de Espera de Clientes</b>",
            'y':0.95, 'x':0.5, 'xanchor': 'center', 'yanchor': 'top'
        },
        xaxis_title="Tiempo de Espera (minutos)",
        yaxis_title="Frecuencia (Grupos)",
        template="plotly_white",
        height=380,
        margin=dict(l=40, r=40, t=60, b=40),
        bargap=0.05
    )
    
    return fig

def plot_distribution_fitting(df, col_name, fit_results):
    """
    Renders actual data distribution histogram and overlays mathematical curves
    (Lognormal, Triangular, Exponential) to show goodness-of-fit.
    """
    data = df[col_name].dropna().values
    data = data[data > 0] # strictly positive for fits
    
    # Sort data for smooth theoretical lines
    x_sorted = np.linspace(max(0.001, float(np.min(data))), float(np.max(data)), 200)
    
    # 1. Base Histogram
    fig = go.Figure()
    
    fig.add_trace(go.Histogram(
        x=data,
        histnorm='probability density',
        name='Datos Históricos (Observed)',
        marker_color='#cbd5e1',
        opacity=0.7,
        nbinsx=25
    ))
    
    # 2. Overlay Lognormal Curve
    if 'lognormal' in fit_results and 'params' in fit_results['lognormal']:
        params = fit_results['lognormal']['params']
        if params:
            s = params['s']
            loc = params['loc']
            scale = params['scale']
            pdf_log = stats.lognorm.pdf(x_sorted, s, loc=loc, scale=scale)
            fig.add_trace(go.Scatter(
                x=x_sorted, y=pdf_log,
                mode='lines',
                name=f"Lognormal (p={fit_results['lognormal']['p_value']:.4f})",
                line=dict(color='#2563eb', width=2.5) # Soft Blue
            ))
            
    # 3. Overlay Triangular Curve
    if 'triangular' in fit_results and 'params' in fit_results['triangular']:
        params = fit_results['triangular']['params']
        if params:
            c = params['c']
            loc = params['loc']
            scale = params['scale']
            pdf_tri = stats.triang.pdf(x_sorted, c, loc=loc, scale=scale)
            fig.add_trace(go.Scatter(
                x=x_sorted, y=pdf_tri,
                mode='lines',
                name=f"Triangular (p={fit_results['triangular']['p_value']:.4f})",
                line=dict(color='#059669', width=2.5) # Emerald Green
            ))
            
    # 4. Overlay Exponential Curve
    if 'exponential' in fit_results and 'params' in fit_results['exponential']:
        params = fit_results['exponential']['params']
        if params:
            loc = params['loc']
            scale = params['scale']
            pdf_exp = stats.expon.pdf(x_sorted, loc=loc, scale=scale)
            fig.add_trace(go.Scatter(
                x=x_sorted, y=pdf_exp,
                mode='lines',
                name=f"Exponencial (p={fit_results['exponential']['p_value']:.4f})",
                line=dict(color='#dc2626', width=2.5) # Crimson Red
            ))
            
    # Clean process label in titles
    clean_label = col_name.replace("_min", "").replace("_", " ").title()
    
    # Recommendation text based on best fit
    best_dist = fit_results.get('best', 'empirical')
    best_label_map = {
        "lognormal": "Lognormal (Distribución Teórica Seleccionada)",
        "triangular": "Triangular (Distribución Teórica Seleccionada)",
        "exponential": "Exponencial (Distribución Teórica Seleccionada)",
        "empirical": "Empírica (Sin distribución teórica válida, p > 0.05)"
    }
    rec_text = best_label_map.get(best_dist, f"Ajuste {best_dist.title()}")
    
    fig.update_layout(
        title={
            'text': f"<b>Bondad de Ajuste: {clean_label}</b><br><span style='font-size:12px;color:#475569'>Recomendación: {rec_text}</span>",
            'y':0.95, 'x':0.5, 'xanchor': 'center', 'yanchor': 'top'
        },
        xaxis_title="Duración (minutos)",
        yaxis_title="Densidad de Probabilidad",
        template="plotly_white",
        height=400,
        margin=dict(l=40, r=40, t=80, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5
        )
    )
    
    return fig
