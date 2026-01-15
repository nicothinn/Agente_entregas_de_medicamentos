# 💊 PharmaSchedule AI

> Asistente inteligente de IA para gestión de servicios farmacéuticos en Audifarma

Sistema de agendamiento y gestión de entregas de medicamentos y citas farmacéuticas mediante conversación natural, desarrollado con LangChain y Streamlit.

## 🚀 Inicio Rápido

### Con Docker (Recomendado)

```bash
# 1. Configurar variables de entorno
cp .env.example .env
# Editar .env y agregar tu OPENAI_API_KEY

# 2. Ejecutar con Docker Compose
docker compose up --build

# 3. Acceder a la aplicación
# http://localhost:8501
```

### Instalación Local

```bash
# 1. Clonar repositorio
git clone <repository-url>
cd agente_de_excel

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tu OPENAI_API_KEY

# 5. Ejecutar aplicación
streamlit run app.py
```

## 📋 Características

- **Agendamiento Inteligente**: Programación de entregas y citas mediante lenguaje natural
- **Validación de Horarios**: Restricciones de horario de atención (L-V: 8AM-5PM, S: 8AM-12PM)
- **Consultas Flexibles**: Búsqueda por fecha, rango, paciente o ID
- **Gestión de Estados**: Control de servicios (Pendiente, Entregado, Cancelado)
- **Dashboard Analytics**: KPIs operativos y visualizaciones en tiempo real
- **Búsqueda Insensible a Acentos**: Encuentra pacientes independientemente de acentuación

## 🏗 Arquitectura

```
┌─────────────┐
│ Streamlit UI│
└──────┬──────┘
       │
┌──────▼──────────┐
│ LangChain Agent │
└──────┬──────────┘
       │
┌──────▼──────────┐
│  Excel Service  │
└──────┬──────────┘
       │
┌──────▼──────┐
│ Excel File  │
└─────────────┘
```

### Componentes Principales

- **`src/agents/`**: Agente LangChain con prompts contextualizados
- **`src/tools/`**: Herramientas del agente (Excel, tiempo)
- **`src/services/`**: Lógica de negocio (Excel, tiempo, cancelación)
- **`src/models/`**: Esquemas Pydantic y excepciones
- **`src/config/`**: Configuración centralizada

## 📁 Estructura del Proyecto

```
agente_de_excel/
├── src/
│   ├── agents/          # Agente LangChain
│   ├── tools/           # Herramientas del agente
│   ├── services/        # Lógica de negocio
│   ├── models/          # Esquemas Pydantic
│   ├── config/          # Configuración
│   └── utils/           # Utilidades
├── tests/               # Pruebas unitarias
├── app.py               # Aplicación Streamlit
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 🛠 Stack Tecnológico

- **LangChain**: Orquestación del agente con OpenAI Functions
- **OpenAI GPT-4o-mini**: Modelo de lenguaje
- **Pydantic v2**: Validación de datos
- **Streamlit**: Interfaz web
- **Pandas + OpenPyXL**: Gestión de Excel
- **Loguru**: Logging profesional
- **Docker**: Containerización

## 📖 Uso

### Ejemplos de Comandos

**Agendar entrega:**
```
Agenda una entrega de Insulina para Juan Pérez, cédula 1234567890, 
mañana a las 15:00 en Sede Norte
```

**Consultar servicios:**
```
Consulta los servicios programados para mañana
Muestra todos los servicios de Juan Pérez
```

**Eliminar servicios:**
```
Eliminar entregas de Juan Pérez
```

### Restricciones de Negocio

- **Horarios**: L-V 8AM-5PM (almuerzo 12PM-1PM), S 8AM-12PM, D cerrado
- **Anticipación mínima**: 2 horas antes de la cita
- **Fechas pasadas**: No se pueden agendar
- **Nombre obligatorio**: Requerido para nuevos registros

## ⚙️ Configuración

### Variables de Entorno

```env
OPENAI_API_KEY=your_openai_api_key_here
```

### Gestión de Volúmenes Docker

```bash
# Ver datos del volumen
./docker-helper.sh inspect-data

# Copiar datos del volumen al host
./docker-helper.sh copy-data-out

# Crear backup
./docker-helper.sh backup
```

## 🧪 Testing

```bash
# Ejecutar tests
pytest

# Con cobertura
pytest --cov=src --cov-report=html
```

## 🎨 Calidad de Código

```bash
# Formatear código
black src/ app.py tests/

# Ordenar imports
isort src/ app.py tests/

# Verificar tipos
mypy src/
```

## 📊 Estructura de Datos

El archivo Excel (`data/agenda.xlsx`) contiene:

| Columna | Descripción |
|---------|-------------|
| `ID_Servicio` | UUID único del servicio |
| `Paciente_ID` | Cédula del paciente |
| `Nombre_Paciente` | Nombre completo |
| `Medicamento` | Nombre del medicamento |
| `Tipo_Servicio` | "Entrega Domicilio" o "Cita Presencial" |
| `Sede` | Sede de Audifarma |
| `Fecha` | YYYY-MM-DD |
| `Hora` | HH:MM (24h) |
| `Estado` | Pendiente, Entregado, Cancelado |

## 🔒 Seguridad

- Validación estricta de datos con Pydantic
- Escritura atómica en Excel (previene corrupción)
- Manejo robusto de errores
- Logs estructurados con Loguru

**Nota**: Para producción, implementar autenticación, encriptación y cumplir normativas de protección de datos de salud.

## 📝 Logging

Los logs se almacenan en `logs/pharma_ai_YYYY-MM-DD.log` con:
- Rotación diaria
- Retención de 30 días
- Nivel DEBUG en archivo, INFO en consola

## 🤝 Contribución

1. Crear rama: `git checkout -b feature/nueva-funcionalidad`
2. Seguir convenciones: Black, isort, type hints
3. Agregar tests para nuevas funcionalidades
4. Ejecutar linting: `black . && isort . && mypy src/`
5. Commit con mensajes descriptivos

