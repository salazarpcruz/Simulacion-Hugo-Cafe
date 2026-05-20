import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import scipy.stats as stats

PRIMARY = "#003781"
SECONDARY = "#2563EB"


def plot_process_times(activity_averages):
    """Bar chart: average time per process phase."""
    label_map = {
        "toma_pedido": "Toma de Pedido",
        "comanda": "Comanda",
        "preparacion": "Preparacion",
        "consumo": "Consumo",
        "pago": "Pago",
        "reocupacion": "Reocupacion"
    }
    flow_order = list(label_map.values())

    phases = list(activity_averages.keys())
    vals = list(activity_averages.values())
    nice = [label_map.get(p, p) for p in phases]

    df = pd.DataFrame({"Fase": nice, "Tiempo (min)": vals})
    df["Fase"] = pd.Categorical(df["Fase"], categories=flow_order,
                                ordered=True)
    df = df.sort_values("Fase")

    fig = px.bar(df, x="Fase", y="Tiempo (min)", text="Tiempo (min)",
                 color_discrete_sequence=[PRIMARY])
    fig.update_traces(texttemplate='%{text:.2f}', textposition='outside',
                      marker_line_color='rgb(8,48,107)',
                      marker_line_width=1, opacity=0.9)
    fig.update_layout(
        title={'text': '<b>Tiempos Promedio por Fase</b>',
               'y': 0.95, 'x': 0.5, 'xanchor': 'center'},
        xaxis_title="", yaxis_title="Tiempo (min)",
        template="plotly_white", height=380,
        margin=dict(l=40, r=40, t=60, b=40))
    return fig


def plot_resource_utilization(table_utils, kitchen_util, checkout_util,
                              waiter_util=0.0):
    """Horizontal bar chart: resource utilisation percentages."""
    resources, utilisation, cats = [], [], []

    for t in ['T1', 'T2', 'T3']:
        resources.append(f"Mesa {t} (Cap 2)")
        utilisation.append(table_utils.get(t, 0.0) * 100)
        cats.append("Terraza")

    for t in ['T4', 'T5']:
        resources.append(f"Mesa {t} (Cap 3)")
        utilisation.append(table_utils.get(t, 0.0) * 100)
        cats.append("Interior")

    resources.append("Meseros")
    utilisation.append(waiter_util * 100)
    cats.append("Recursos")

    resources.append("Cocina")
    utilisation.append(kitchen_util * 100)
    cats.append("Recursos")

    resources.append("Caja")
    utilisation.append(checkout_util * 100)
    cats.append("Recursos")

    df = pd.DataFrame({"Recurso": resources,
                        "Utilizacion (%)": utilisation,
                        "Categoria": cats})

    fig = px.bar(df, y="Recurso", x="Utilizacion (%)",
                 color="Categoria", text="Utilizacion (%)",
                 orientation="h",
                 color_discrete_map={
                     "Terraza": "#93c5fd",
                     "Interior": "#3b82f6",
                     "Recursos": PRIMARY})
    fig.update_traces(texttemplate='%{text:.1f}%',
                      textposition='outside', opacity=0.9)
    fig.update_layout(
        title={'text': '<b>Utilizacion de Recursos</b>',
               'y': 0.95, 'x': 0.5, 'xanchor': 'center'},
        xaxis_title="Utilizacion (%)", yaxis_title="",
        xaxis=dict(range=[0, 115]),
        template="plotly_white", height=480,
        margin=dict(l=40, r=40, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=-0.18,
                    xanchor="center", x=0.5))
    return fig


def plot_waiting_times_distribution(wait_times):
    """Histogram of queue waiting times."""
    if not wait_times:
        wait_times = [0.0]
    df = pd.DataFrame({"Tiempo de Espera (min)": wait_times})

    fig = px.histogram(df, x="Tiempo de Espera (min)",
                       color_discrete_sequence=[SECONDARY],
                       nbins=20, opacity=0.85)
    fig.update_layout(
        title={'text': '<b>Distribucion de Tiempos de Espera</b>',
               'y': 0.95, 'x': 0.5, 'xanchor': 'center'},
        xaxis_title="Tiempo de Espera (min)",
        yaxis_title="Frecuencia",
        template="plotly_white", height=360,
        margin=dict(l=40, r=40, t=60, b=40),
        bargap=0.05)
    return fig


def plot_distribution_fitting(df, col_name, fit_results):
    """Histogram + overlay of theoretical PDF curves."""
    data = df[col_name].dropna().values
    data = data[data > 0]

    x = np.linspace(max(0.001, float(np.min(data))),
                    float(np.max(data)), 200)

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=data, histnorm='probability density',
        name='Datos observados',
        marker_color='#cbd5e1', opacity=0.7, nbinsx=25))

    # Lognormal
    if 'lognormal' in fit_results and fit_results['lognormal'].get('params'):
        p = fit_results['lognormal']['params']
        pdf = stats.lognorm.pdf(x, p['s'], loc=p['loc'], scale=p['scale'])
        fig.add_trace(go.Scatter(
            x=x, y=pdf, mode='lines',
            name=f"Lognormal (p={fit_results['lognormal']['p_value']:.4f})",
            line=dict(color='#2563eb', width=2.5)))

    # Triangular
    if 'triangular' in fit_results and fit_results['triangular'].get('params'):
        p = fit_results['triangular']['params']
        pdf = stats.triang.pdf(x, p['c'], loc=p['loc'], scale=p['scale'])
        fig.add_trace(go.Scatter(
            x=x, y=pdf, mode='lines',
            name=f"Triangular (p={fit_results['triangular']['p_value']:.4f})",
            line=dict(color='#059669', width=2.5)))

    # Exponential
    if 'exponential' in fit_results and fit_results['exponential'].get('params'):
        p = fit_results['exponential']['params']
        pdf = stats.expon.pdf(x, loc=p['loc'], scale=p['scale'])
        fig.add_trace(go.Scatter(
            x=x, y=pdf, mode='lines',
            name=f"Exponencial (p={fit_results['exponential']['p_value']:.4f})",
            line=dict(color='#dc2626', width=2.5)))

    clean = col_name.replace("_min", "").replace("_", " ").title()
    best = fit_results.get('best', 'empirical')
    best_map = {"lognormal": "Lognormal", "triangular": "Triangular",
                "exponential": "Exponencial", "empirical": "Empirica"}
    rec = best_map.get(best, best.title())

    fig.update_layout(
        title={'text': f'<b>Bondad de Ajuste: {clean}</b><br>'
                       f'<span style="font-size:12px;color:#6B7280">'
                       f'Recomendada: {rec}</span>',
               'y': 0.95, 'x': 0.5, 'xanchor': 'center'},
        xaxis_title="Duracion (min)",
        yaxis_title="Densidad de Probabilidad",
        template="plotly_white", height=400,
        margin=dict(l=40, r=40, t=80, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25,
                    xanchor="center", x=0.5))
    return fig
