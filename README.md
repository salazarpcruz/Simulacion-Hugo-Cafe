# HUGO CAFÉ Simulation Project

Este proyecto consiste en un **Simulador de Eventos Discretos (DES)** desarrollado en Python para **HUGO CAFÉ**. El objetivo principal es analizar el flujo operativo AS-IS del restaurante, identificar cuellos de botella mediante simulaciones estadísticas, evaluar la utilización de los recursos físicos (mesas, cocina y caja) y visualizar dinámicamente el comportamiento de los clientes sobre el layout físico.

---

## 📋 Flujo del Proceso Operativo

El simulador recrea de manera secuencial y cronológica el trayecto completo de los grupos de clientes:

1. **Llegada**: Los clientes ingresan al sistema bajo una tasa de interarribos aleatoria.
2. **Asignación de Mesa**: Se asigna una mesa compatible libre. Si no hay mesas libres, los clientes se forman en una cola de espera.
3. **Toma de Pedido**: Se toma la orden del grupo directamente en la mesa asignada.
4. **Comanda**: Se transmite el pedido de la orden al sistema y a la cocina.
5. **Preparación**: Los cocineros preparan los alimentos. Durante esta fase, el grupo ocupa la mesa *y* un espacio en la cocina en paralelo.
6. **Consumo**: Los clientes reciben su comida y la consumen en la mesa.
7. **Pago (Checkout)**: Los clientes realizan el pago. El cajero y la mesa están ocupados simultáneamente durante esta fase.
8. **Reocupación de Mesa**: Tras la salida del grupo, el personal limpia, sanitiza y acomoda la mesa para que quede disponible para el siguiente grupo.
9. **Salida**: El grupo se retira y es descartado del sistema.

---

## ⚙️ Reglas Operativas y del Negocio

El simulador aplica rigurosamente las siguientes restricciones del negocio físico:
- **Capacidades de Mesa**:
  - Mesas **T1, T2 y T3** (Zona Terraza) tienen una capacidad máxima formal de **2 personas**.
  - Mesas **T4 y T5** (Zona Interior) tienen una capacidad máxima formal de **3 personas**.
- **Asignación de Grupos**:
  - Los grupos de **1 o 2 personas** pueden sentarse en cualquier mesa disponible, pero el algoritmo prioriza siempre las mesas de la Terraza (`T1`, `T2`, `T3`) para reservar las mesas interiores más grandes.
  - Los grupos de **3 personas** son incompatibles con la Terraza y solo se les permite sentarse en `T4` o `T5`.
  - Los grupos de **4 personas** representan una **excepción operativa**. Son ubicados en `T4` o `T5` y requieren que el personal les provea una silla adicional, generando notas y advertencias en el sistema.
- **Tiempos del Sistema**:
  - El **tiempo total de mesa** incluye la suma acumulativa de: `Toma de Pedido` + `Comanda` + `Preparación` + `Consumo` + `Pago` + `Reocupación`. No incluye el tiempo de interarribo.

---

## 📊 Inferencia Estadística y Distribuciones

De acuerdo con el análisis de bondad de ajuste realizado sobre la base de datos de 350 observaciones reales, se determinaron los siguientes comportamientos matemáticos para el modelo AS-IS:

| Proceso Operativo | Distribución Seleccionada | Parámetros Ajustados (p-value) | Nota de Modelado |
| :--- | :--- | :--- | :--- |
| **Interarribo** | Empírica (Observed CDF) | KS Fallback (p < 0.05) | Muestreo bootstrap directo por variabilidad de demanda |
| **Toma de Pedido** | Empírica (Observed CDF) | KS Fallback (p < 0.05) | Muestreo bootstrap directo |
| **Transmisión Comanda** | Discreta Empírica | 1 min: 12.9%, 2 min: 48.9%, 3 min: 24.3%, 4 min: 14% | Probabilidades empíricas discretas |
| **Preparación Cocina** | Lognormal | $\sigma = 0.219$, $\mu = 0.00$, $scale = 12.67$ ($p = 0.8127$) | Ajuste teórico de alta fidelidad |
| **Consumo en Mesa** | Lognormal | $\sigma = 0.215$, $\mu = 0.00$, $scale = 50.31$ ($p = 0.8737$) | Ajuste teórico de alta fidelidad |
| **Pago en Caja** | Empírica (Observed CDF) | KS Fallback (p < 0.05) | Muestreo bootstrap directo |
| **Tiempo Reocupación** | Triangular | $min = 4.70$, $moda = 7.72$, $max = 15.90$ ($p = 0.3927$) | Ajuste teórico de alta fidelidad |

---

## 🛠️ Estructura del Código Modular

La aplicación está diseñada de manera estructurada y limpia:
- `app.py`: Control principal del flujo Streamlit, renderizado de menús, pestañas, visualización espacial y generador lógico de insights automáticos.
- `simulation_engine.py`: Motor SimPy que orquesta las corridas, gestiona los hilos de simulación, la cola customizada de asignación de mesas y guarda las bitácoras cronológicas de eventos.
- `data_processing.py`: Ingesta segura de Excel, validación de inconsistencias o números negativos, y ajuste matemático estadístico (`scipy.stats`) de las curvas.
- `visualization.py`: Componentes de visualización Plotly (tiempos promedios por fase, gráficos de calor de recursos y curvas GoF de ajuste).
- `requirements.txt`: Dependencias requeridas por el proyecto.

---

## 🚀 Instrucciones de Instalación y Ejecución

Para iniciar la aplicación en su entorno de desarrollo local, siga estos pasos:

### 1. Clonar o descargar el proyecto
Asegúrese de guardar todos los archivos modularizados en el directorio del proyecto: `c:\Proyectos antigvty\Simulador`.

### 2. Crear y activar el entorno virtual (si no está activo)
En su terminal de Windows (PowerShell):
```powershell
# Crear el entorno virtual
python -m venv venv

# Activar el entorno virtual
.\venv\Scripts\Activate.ps1
```

### 3. Instalar las dependencias requeridas
```powershell
pip install -r requirements.txt
```

### 4. Lanzar la aplicación Streamlit
```powershell
streamlit run app.py
```

La aplicación se abrirá automáticamente en su navegador web predeterminado (usualmente en la dirección `http://localhost:8501`).
