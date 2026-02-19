# AnalisIA 🧠

Sistema integral de análisis jurídico con inteligencia artificial para procesamiento masivo de sentencias del Consejo de Estado de Colombia.

## 🚀 Características Principales

### 📦 Módulo 0: Descompresión Masiva ZIP
- Extracción automática de múltiples archivos ZIP
- Organización por carpetas
- Soporte para .doc, .docx, .pdf, .txt
- Estadísticas en tiempo real

### 📄 Módulo 1: Conversión a .txt
- Conversión de documentos a texto plano
- Procesamiento por lotes
- Preservación de metadatos

### 🔍 Módulo 2: Filtrado Inteligente
- Clasificación automática de tutelas
- Filtros por tipo y contenido
- Identificación de providencias judiciales

### ⚖️ Módulo 3: Análisis Jurídico Completo
- Análisis profundo con IA (OpenAI)
- Extracción de ratio decidendi
- Test C-590 automatizado
- Identificación de precedentes

### 🏷️ Módulo 4: Etiquetado Automático
- Clasificación por categorías
- Detección de derechos fundamentales
- Etiquetas contextuales

### 📊 Módulo 5: Dashboard Visual
- Visualización de datos
- Estadísticas interactivas
- Exportación de resultados

## 🛠️ Instalación

### Prerrequisitos
- Python 3.10+
- pip
- Cuenta de OpenAI con API key

### Pasos
```bash
# Clonar el repositorio
git clone https://github.com/miguelnxlp/analisia.git
cd analisia

# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tu OPENAI_API_KEY
```

### Variables de Entorno
```bash
OPENAI_API_KEY=tu_api_key_aqui
```

## 🚀 Ejecución

```bash
streamlit run app_unificado.py
```

La aplicación estará disponible en http://localhost:8501

## 📋 Flujo de Trabajo

1. **Módulo 0**: Seleccionar carpeta con ZIPs → Descomprimir
2. **Módulo 1**: Usar archivos extraídos → Convertir a .txt
3. **Módulo 2**: Filtrar documentos relevantes
4. **Módulo 3**: Análisis jurídico completo con IA
5. **Módulo 4**: Etiquetado automático
6. **Módulo 5**: Visualización y exportación

## 🧠 Prompts Expandidos

El sistema utiliza prompts especializados para análisis jurídico profundo:

### analysis_system.txt
- Definiciones operativas clave
- Metodología de análisis estructurada
- Criterios de trabajo obligatorios
- 15 entregables estandarizados

### analysis_user.txt
- Instrucciones estrictas de formato
- Estructura JSON robusta
- Validación completa de datos
- Análisis crítico y profundo

## 📁 Estructura del Proyecto

```
analisia/
├── app_unificado.py          # Aplicación principal Streamlit
├── utils/                   # Módulos de utilidad
│   ├── analysis.py          # Análisis jurídico con IA
│   ├── classify.py         # Clasificación de documentos
│   ├── extract_text.py     # Extracción de texto
│   ├── labeling.py         # Etiquetado automático
│   ├── env.py             # Manejo de variables de entorno
│   └── zip_extractor.py   # Descompresión masiva
├── prompts/                # Prompts para IA
│   ├── analysis_system.txt  # Prompt de sistema
│   └── analysis_user.txt   # Prompt de usuario
├── .streamlit/            # Configuración de Streamlit
└── README.md             # Este archivo
```

## 🔧 Configuración

### OpenAI API
1. Crear cuenta en https://platform.openai.com
2. Generar API key
3. Configurar en `.env` o `.streamlit/secrets.toml`

### Formatos Soportados
- **Entrada**: .doc, .docx, .pdf, .txt
- **Procesamiento**: .txt
- **Salida**: .csv, .txt, JSON

## 📊 Salidas del Sistema

### Análisis Jurídico Completo
```json
{
  "clasificacion_organo": {...},
  "tipo_tutela": {...},
  "actos_cuestionados": {...},
  "hechos": [...],
  "problemas_juridicos": [...],
  "ratio_regla": {...},
  "c590_generales": {...},
  "c590_especificos": {...},
  "decision_resuelve": {...},
  "precedente_normas": {...},
  "ordenes": {...},
  "observaciones": {...},
  "sintesis": {...}
}
```

## 🎯 Casos de Uso

### Para Abogados
- Análisis masivo de jurisprudencia
- Identificación de precedentes
- Preparación de casos

### Para Investigadores
- Estudios de tendencias jurisprudenciales
- Análisis de decisiones judiciales
- Extracción de datos estructurados

### Para Estudiantes
- Aprendizaje de análisis jurídico
- Estudio de sentencias
- Investigación académica

## 🔍 Características Técnicas

### Optimización
- Sistema de cache inteligente
- Procesamiento por lotes
- Manejo robusto de errores

### Seguridad
- Manejo seguro de API keys
- Exclusión de datos sensibles
- Validación de entradas

### Escalabilidad
- Procesamiento masivo
- Arquitectura modular
- Fácil extensión

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto
2. Crear rama (`git checkout -b feature/AmazingFeature`)
3. Commit cambios (`git commit -m 'Add AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abrir Pull Request

## 📝 Licencia

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles.

## 📞 Contacto

- **Autor**: Miguel López
- **GitHub**: [@miguelnxlp](https://github.com/miguelnxlp)
- **Proyecto**: https://github.com/miguelnxlp/analisia

## 🙏 Agradecimientos

- OpenAI por la API de análisis
- Streamlit por el framework web
- Consejo de Estado de Colombia por la jurisprudencia

---

**AnalisIA** - Transformando el análisis jurídico con inteligencia artificial ⚖️🤖
