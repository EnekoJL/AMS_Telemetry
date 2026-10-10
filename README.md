# AMS Telemetry
> Professional Motorsport Telemetry Studio & Hexagonal Binary Log Parser for AMS STM32 Black-Box.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

---

## ⚡ Overview

**AMS Telemetry** es la suite de análisis de datos y telemetría de competición para el prototipo de moto eléctrica de **Araba Motorsport (AMS)**. Permite ingerir, decodificar y correlacionar registros de alta frecuencia generados por el microcontrolador STM32F469 sobre la tarjeta microSD (caja negra):

1. **CLI Headless Parser (AMS_Parser)**: Motor de streaming de alto rendimiento basado en arquitectura hexagonal que decodifica ficheros binarios heterogéneos (`.bin`) a ficheros CSV limpios sin desbordamiento de memoria ($O(1)$ RAM).
2. **AMS Telemetry Studio (Web Dashboard)**: Aplicación interactiva de telemetría de competición con estética motorsport oscura, trazado satélite vectorial en alta definición y panel vertical de 4 gráficos apilados y sincronizados a 60 FPS (uPlot).

---

## 🏎️ Características Principales

### 1. Panel Unificado ("Unified Cockpit")
- **Mapa y HUD Colapsables**: Barra superior con selector de sesiones, estado de subida y botón de alternancia (`[ 🗺️ Ocultar Mapa ]` / `[ 🗺️ Mostrar Mapa ]`) para maximizar el área de análisis de curvas cuando se desee.
- **Trazado Satélite Vectorial (Leaflet + SVG)**: Renderizado del circuito mediante elementos SVG vectoriales nativos (sin clipping de canvas) sobre cartografía satélite Google HD pre-cacheadora (sin parpadeos ni cuadrículas negras en zooms profundos).
- **Gradiente Dinámico de Velocidad**: Gradiente continuo en la trazada de pista (Verde Racing ➔ Lima ➔ Dorado ➔ Rosa Racing).
- **HUD Digital en Vivo**: Indicadores instantáneos de velocidad, RPM, aceleración longitudinal (G), distancia acumulada, tiempo de sesión y coordenadas UTC.

### 2. Multi-Canal Sincronizado (4 Gráficas Apiladas)
Cuatro series temporales sincronizadas en el mismo eje de tiempo (`rel_time_s` / `timestamp_ms`):
- **Gráfico 1: Motor & Dinámica**: Velocidad GPS (`km/h`, Verde Racing `#00ff88`) y Régimen del Motor (`RPM`, Rosa Racing `#ff007f`) en doble eje Y.
- **Gráfico 2: Suspensiones**: Recorrido de suspensión delantera (horquilla) y trasera (amortiguador) en milivoltios/milímetros.
- **Gráfico 3: Batería & Alta Tensión**: Tensión total del pack (`V`), corriente consumida/regenerada (`A`) y dispersión/delta de celdas (`mV`).
- **Gráfico 4: Térmicas**: Temperaturas en tiempo real de motor, inversor, celdas de batería y microcontrolador STM32 (`°C`).

### 3. Interacción y Zoom Avanzado
- **Drag-to-Zoom Sincronizado**: Haz clic y arrastra horizontalmente en cualquiera de las 4 gráficas para seleccionar un rango temporal. El recuadro de pre-selección verde neón (`.u-select`) resalta el tramo exacto y todas las gráficas amplían la vista al unísono.
- **Doble Clic para Resetear**: Doble clic sobre cualquier gráfica restaura el zoom completo de la sesión instantáneamente en todas las series.
- **Crosshair Bidireccional a 60 FPS**: Mover el cursor sobre cualquier gráfica o sobre la pista actualiza simultáneamente la posición del vehículo (marcador rosa) en el mapa y todos los indicadores del HUD.

### 4. Carga Modular y Desacoplada
- Soporte para ficheros `.bin` crudos de la caja negra STM32.
- Soporte para subida multi-fichero de CSVs independientes (`adc_sensors.csv`, `bms_battery.csv`, `inverter_can.csv`).
- Interpolación y alineación temporal transparente por `timestamp_ms`. Si falta alguna fuente, el panel se adapta dinámicamente mostrando los canales disponibles.

### 5. 100% Autónomo y Offline
- Librerías frontend locales empaquetadas (`Leaflet 1.9.4`, `uPlot 1.6.31`, fuentes e iconos). Operación completa en box o paddock sin conexión a internet.

---

## 🚀 Inicio Rápido

### Instalación

```bash
# Clonar o acceder al directorio del proyecto
cd tools/AMS_Telemetry

# Crear entorno virtual e instalar dependencias
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 1. Lanzar el Servidor Web (Telemetry Studio)

```bash
# Ejecución directa (puerto 8000 por defecto)
python3 run.py

# O especificar puerto alternativo:
python3 run.py --port 8080
```
Abre tu navegador en **[http://localhost:8000](http://localhost:8000)**. Puedes pulsar *"Cargar Muestra"* para abrir la sesión de referencia de Motorland Aragón, o arrastrar tus propios archivos `.bin` o `.csv`.

### 2. Generador de Datos Sintéticos

Para pruebas sin hardware físico, el script `tools/generate_mock_telemetry.py` genera ficheros CSV realistas alineados con la ventana temporal del log GPS de referencia:

```bash
# Desde la raíz del repositorio AMS_GitHub:
python3 tools/generate_mock_telemetry.py
```
Genera:
- `telemetry/adc_sensors.csv` (25 Hz / 40 ms - Suspensiones, 12V aux, temp STM32).
- `telemetry/bms_battery.csv` (10 Hz / 100 ms - Pack V, I, SoC, celdas min/max/temp).
- `telemetry/inverter_can.csv` (50 Hz / 20 ms - Motor RPM, temperaturas, par Nm).

### 3. Parser CLI Headless — AMS_Parser (Conversión a CSV)

```bash
# Decodificar log binario con AMS_Parser y exportar a CSV
python3 main.py -i data/sample/20261010_144951.bin -o ./output
```

---

## 🧪 Tests y Validación

La suite de pruebas unitarias y de integración cubre decodificadores binarios, lógica de sincronización, modelos y endpoints de la API:

```bash
python3 -m pytest tests -v
```

---

## 📡 API REST

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/sessions/current` | Devuelve la sesión actual (GPS, cinemática y canales cargados). |
| `POST` | `/api/sessions/upload` | Sube y parsea un archivo binario `.bin`. |
| `POST` | `/api/sessions/load-sample` | Recarga la sesión de prueba de Motorland Aragón. |
| `POST` | `/api/telemetry/upload` | Sube uno o varios archivos CSV (`adc_sensors`, `bms_battery`, `inverter_can`). |
| `GET` | `/api/telemetry/current` | Devuelve los puntos multi-canal alineados de la sesión activa. |

---

## 📁 Estructura del Repositorio

```text
tools/AMS_Telemetry/
├── run.py                             # Lanzador del servidor web Uvicorn
├── main.py                            # CLI de parseo binario headless
├── pyproject.toml                     # Configuración del paquete y pytest
├── requirements.txt                   # Dependencias de producción y testing
├── src/
│   ├── AMS_Parser/                # Motor de parseo binario (Arquitectura Hexagonal)
│   │   ├── domain/                    # Modelos de dominio puros (GpsRecord, LogRecordHeader)
│   │   ├── ports/                     # Interfaces abstractas (Reader, Decoder, Exporter)
│   │   ├── application/               # Casos de uso (ParseBinaryLogUseCase, Registry)
│   │   └── adapters/                  # Adaptadores I/O (ChunkedBinaryReader, CsvGpsExporter)
│   └── ams_telemetry_studio/          # Backend FastAPI
│       ├── app.py                     # Definición de rutas y endpoints REST
│       ├── models.py                  # Modelos Pydantic y DTOs multi-canal
│       └── services/                  # Cálculo de distancias (Haversine), aceleraciones G y multi-stream
├── frontend/                          # Interfaz de usuario SPA (Vanilla HTML5/CSS3/ES6)
│   ├── index.html                     # Cockpit unificado con controles y gráficos apilados
│   ├── css/studio.css                 # Estilos Motorsport (Verde Racing, Rosa, uPlot dark)
│   ├── js/
│   │   ├── app.js                     # Orquestación de eventos y carga de datos
│   │   ├── api.js                     # Cliente HTTP REST
│   │   ├── map.js                     # Controlador Leaflet (SVG vectorial, Google Satellite HD)
│   │   ├── chart.js                   # Motor gráfico GPS uPlot (zoom sincronizado)
│   │   ├── multi_chart.js             # Panel vertical de 4 gráficos apilados sincronizados
│   │   ├── hud.js                     # Actualización de telemetría e indicadores en tiempo real
│   │   └── colormap.js                # Cálculo de gradientes de color continuos
│   └── vendor/                        # Dependencias locales offline (Leaflet, uPlot, imágenes)
├── data/
│   └── sample/
│       └── 20261010_144951.bin        # Log binario de referencia (Motorland Aragón)
└── tests/                             # Suite de pruebas automatizadas (22 tests unitarios e integración)
```
