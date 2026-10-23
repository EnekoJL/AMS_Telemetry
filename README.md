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

Especificación completa (objetivos, formato de entrada, API, UI): [`docs/Specification.md`](docs/Specification.md).

---

## 🏎️ Características Principales

### 1. Panel Unificado ("Unified Cockpit")
- **Mapa y HUD Colapsables**: Barra superior con selector de sesiones, estado de subida y botón de alternancia (`[ 🗺️ Ocultar Mapa ]` / `[ 🗺️ Mostrar Mapa ]`) para maximizar el área de análisis de curvas cuando se desee.
- **Trazado Satélite Vectorial (Leaflet + SVG)**: Renderizado del circuito mediante elementos SVG vectoriales nativos (sin clipping de canvas) sobre cartografía satélite Google HD pre-cacheadora (sin parpadeos ni cuadrículas negras en zooms profundos).
- **Gradiente Dinámico de Velocidad**: Gradiente continuo en la trazada de pista (Verde Racing ➔ Lima ➔ Dorado ➔ Rosa Racing).
- **HUD Digital en Vivo**: Indicadores instantáneos de velocidad, RPM, aceleración longitudinal (G), distancia acumulada, tiempo de sesión y coordenadas UTC.

### 2. Multi-Canal Sincronizado (4 Gráficas Apiladas con Ejes Y Duales)
Cuatro series temporales sincronizadas en el mismo eje de tiempo (`rel_time_s` / `timestamp_ms`):
- **1. Dinámica**:
  - **Eje Y izquierdo (Verde Neón `#00ff88`)**: Velocidad GPS en `km/h`.
  - **Eje Y derecho (Rosa Racing `#ff007f`)**: Régimen del motor en `RPM` (escala desacoplada sin interferencia de cuadrículas).
- **2. Suspensiones**: Recorrido de suspensión delantera (horquilla) y trasera (amortiguador) en milímetros (`mm`).
- **3. Batería**:
  - **Eje Y izquierdo (Verde Neón `#00ff88`)**: Tensión total del pack en `V` (con auto-rango dinámico para alta tensión, sin forzar base cero para maximizar la resolución de caídas de tensión).
  - **Eje Y derecho (Rosa Racing `#ff007f`)**: Corriente del pack en `A` (signo positivo en descarga/tracción, negativo en regeneración/freno).
- **4. Temperaturas**: Temperaturas en tiempo real del motor, inversor, celdas de batería y microcontrolador STM32 (`°C`).

### 3. Escalas Dinámicas y Rango Inteligente (`calcScaleRange`)
- **Ajuste Automático Bounding**: Cálculo de límites mín/máx según los datos de la sesión, aplicando un margen proporcional y pasos de división limpios. Evita que señales con valores altos (como el voltaje de batería de 340 V – 400 V) queden comprimidas en una franja estrecha.
- **Formateo Numérico Riguroso**: Etiquetas de eje con valores enteros y unidades explícitas (`km/h`, `RPM`, `mm`, `V`, `A`, `°C`), garantizando visualización limpia sin artefactos.

### 4. Modo Pantalla Completa / Maximizar Gráfica
- **Botón `[ ⛶ Maximizar ]` / `[ 🗗 Minimizar ]`**: Presente en la cabecera de cada una de las 4 tarjetas de telemetría.
- **Ampliación Instantánea a 100% Pantalla**: Al pulsar maximizar, la gráfica seleccionada se expande a pantalla completa (`100vw × 100vh`), redimensionando automáticamente el canvas del gráfico para inspección milimétrica de curvas.
- **Atajo de Teclado**: Presionar la tecla <kbd>Escape</kbd> restaura inmediatamente la vista stacked original de los 4 canales.
- **Sincronización Total Conservada**: El modo maximizado mantiene intacto el crosshair sincronizado, la actualización del punto en el mapa y el refresco a 60 FPS del HUD digital.

### 5. Interacción y Zoom Avanzado
- **Drag-to-Zoom Sincronizado**: Haz clic y arrastra horizontalmente en cualquiera de las gráficas para seleccionar un rango temporal. El recuadro de pre-selección verde neón (`.u-select`) resalta el tramo exacto y todas las gráficas amplían la vista al unísono.
- **Doble Clic para Resetear**: Doble clic sobre cualquier gráfica restaura el zoom completo de la sesión instantáneamente en todas las series.
- **Crosshair Bidireccional a 60 FPS**: Mover el cursor sobre cualquier gráfica o sobre la pista actualiza simultáneamente la posición del vehículo (marcador rosa) en el mapa y todos los indicadores del HUD.

### 6. Carga Modular y Desacoplada
- Soporte para ficheros `.bin` crudos de la caja negra STM32.
- Soporte para subida multi-fichero de CSVs independientes (`adc_sensors.csv`, `bms_battery.csv`, `inverter_can.csv`).
- Interpolación y alineación temporal transparente por `timestamp_ms`. Si falta alguna fuente, el panel se adapta dinámicamente mostrando los canales disponibles.

### 7. 100% Autónomo, Offline y Control de Caché
- Librerías frontend locales empaquetadas (`Leaflet 1.9.4`, `uPlot 1.6.31`, fuentes e iconos). Operación completa en box o paddock sin conexión a internet.
- Control de versión de assets (`?v=2.1`) en las importaciones para evitar que los navegadores sirvan archivos `.js` o `.css` obsoletos en caché local.

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

Para pruebas sin hardware físico, el script `scripts/generate_mock_telemetry.py` genera ficheros CSV realistas alineados con la ventana temporal del log GPS de referencia:

```bash
# Desde tools/AMS_Telemetry:
python3 scripts/generate_mock_telemetry.py
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
├── scripts/
│   └── generate_mock_telemetry.py     # Generador de datos sintéticos multi-canal
└── tests/                             # Suite de pruebas automatizadas (22 tests unitarios e integración)
```
