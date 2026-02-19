# -*- coding: utf-8 -*-
import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# -----------------------------
# Utilidades y constantes
# -----------------------------

SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}

CSV_COLUMNS = [
    "radicado",
    "consejero_ponente",
    "sala",
    "seccion",
    "fecha",
    "clasificacion_organo",
    "tipo_tutela",
    "actos_cuestionados",
    "hechos",
    "problemas_juridicos",
    "ratio_regla",
    "ratio_premisas",
    "obiter",
    "c590_generales",
    "c590_especificos",
    "decision_resuelve",
    "precedente_normas",
    "ordenes",
    "observaciones",
    "sintesis",
    "llm_error",
]

# -----------------------------
# Lectura de archivos
# -----------------------------

def collect_txt_files(source_dir: Path) -> List[Path]:
    files: List[Path] = []
    for root, _dirs, filenames in os.walk(source_dir):
        for name in filenames:
            path = Path(root) / name
            if path.suffix.lower() == ".txt":
                files.append(path)
    return files

def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

# -----------------------------
# Extractores deterministas (según tu formato)
# -----------------------------

# Ej.: "Consejero ponente: JULIO ROBERTO PIZA RODRÍGUEZ"
_RE_CONSEJERO = re.compile(
    r'(?:Consejero\s+ponente|Magistrado\s+ponente|Ponente)\s*:\s*([A-ZÁÉÍÓÚÑ\s\.\-]+)',
    re.IGNORECASE
)

# Ej.: "Bogotá, D.C., dos (2) de mayo de dos mil diecinueve (2019)"
_RE_FECHA_PARENTESIS_ANIO = re.compile(
    r'\b(\d{1,2})\s*\(\s*\d{1,2}\s*\)\s*de\s*'
    r'(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)'
    r'\s*de\s*[^()\n]*\(\s*(\d{4})\s*\)',
    re.IGNORECASE
)

# Alternativa simple: "12 de marzo de 2024"
_RE_FECHA_SIMPLE = re.compile(
    r'\b(\d{1,2})\s*de\s*'
    r'(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)'
    r'\s*de\s*(\d{4})',
    re.IGNORECASE
)

def _iso(y: int, m: int, d: int) -> str:
    try:
        datetime(y, m, d)  # valida
        return f"{y:04d}-{m:02d}-{d:02d}"
    except Exception:
        return "No consta"

def extract_consejero(text: str) -> str:
    m = _RE_CONSEJERO.search(text)
    return m.group(1).strip() if m else "No consta"

def extract_fecha(text: str) -> str:
    m = _RE_FECHA_PARENTESIS_ANIO.search(text)
    if m:
        d = int(m.group(1))
        mes = SPANISH_MONTHS.get(m.group(2).lower(), 0)
        y = int(m.group(3))
        if 1 <= d <= 31 and 1 <= mes <= 12 and 1500 <= y <= 2100:
            return _iso(y, mes, d)
    m = _RE_FECHA_SIMPLE.search(text)
    if m:
        d = int(m.group(1))
        mes = SPANISH_MONTHS.get(m.group(2).lower(), 0)
        y = int(m.group(3))
        if 1 <= d <= 31 and 1 <= mes <= 12 and 1500 <= y <= 2100:
            return _iso(y, mes, d)
    return "No consta"

# -----------------------------
# IA: extracción de metadatos y análisis
# -----------------------------

def load_prompts(prompts_dir: Path) -> Dict[str, str]:
    prompts: Dict[str, str] = {}
    if not prompts_dir.exists():
        return prompts
    for p in prompts_dir.glob("*.txt"):
        try:
            prompts[p.stem] = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
    return prompts

def _call_openai_analisis(text: str, prompts: Dict[str, str], model: str = "gpt-4o-mini") -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        try:
            import streamlit as st  # type: ignore
            if hasattr(st, 'secrets'):
                secret_key = st.secrets.get("OPENAI_API_KEY")  # type: ignore[attr-defined]
                if secret_key:
                    api_key = str(secret_key)
                    os.environ["OPENAI_API_KEY"] = api_key
        except Exception:
            pass
    if not api_key:
        return {"error": "OPENAI_API_KEY no configurada"}
    try:
        from openai import OpenAI
    except Exception:
        return {"error": "Libreria openai no instalada"}

    client = OpenAI(api_key=api_key)

    system_prompt = prompts.get("analysis_system", "")
    user_prompt_template = prompts.get("analysis_user", "")
    user_prompt = user_prompt_template.replace("{{TEXT}}", text[:200000])  # limitar tamaño

    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = resp.choices[0].message.content or "{}"
        print(f"Respuesta de IA para metadatos: {content}")  # Debug
        result = json.loads(content)
        print(f"JSON parseado para metadatos: {result}")  # Debug
        return result
    except Exception as e:
        return {"error": str(e)}

def extract_metadata_ia(sentencia: str, model: str = "gpt-4o-mini") -> Dict[str, str]:
    """
    Extrae: consejero_ponente, actor, demandado, fecha, sala, seccion, ciudad, tipo_proceso.
    NO extrae radicado - se obtiene del nombre del archivo.
    """
    if not isinstance(sentencia, str) or not sentencia.strip():
        return {"error": "No se encontró texto para analizar"}

    system_prompt = """Eres un experto en análisis de sentencias del Consejo de Estado de Colombia.
Tu tarea es extraer información específica de las sentencias.

INSTRUCCIONES ESPECÍFICAS:
1. consejero_ponente: Busca "Consejero ponente:", "Consejero:", "CONSEJERO PONENTE:", "CONSEJERO:" y extrae el nombre completo
2. sala: Busca "SALA DE LO CONTENCIOSO ADMINISTRATIVO" y extrae la descripción completa
3. seccion: Busca "SECCIÓN CUARTA", "SECCIÓN PRIMERA", "SECCIÓN SEGUNDA", etc. y extrae la descripción completa
4. fecha: Busca fechas como "Bogotá, D.C., dos (2) de mayo de dos mil diecinueve (2019)" y convierte a YYYY-MM-DD
5. actor: Busca "Actor:", "Demandante:", "Peticionario:" y extrae el nombre
6. demandado: Busca "Demandado:", "Entidad demandada:", "Autoridad:" y extrae el nombre
7. ciudad: Busca "Bogotá, D.C.", "Medellín", "Cali", etc.
8. tipo_proceso: Busca "Tutela contra providencia judicial", "Acción de tutela", etc.

Responde SOLO en JSON con:
{
  "consejero_ponente": "... o No consta",
  "actor": "... o No consta",
  "demandado": "... o No consta",
  "fecha": "YYYY-MM-DD o No consta",
  "sala": "... o No consta",
  "seccion": "... o No consta",
  "ciudad": "... o No consta",
  "tipo_proceso": "... o No consta"
}
No inventes. Si no hay dato, usa "No consta". Convierte fechas a YYYY-MM-DD.
"""

    user_prompt = f"""Analiza esta sentencia del Consejo de Estado y extrae la información:

TEXTO DE LA SENTENCIA:
{sentencia[:15000]}

INSTRUCCIONES:
1. Busca "Consejero ponente:" o "Consejero:" y extrae el nombre completo
2. Busca "SALA DE LO CONTENCIOSO ADMINISTRATIVO" y extrae la descripción
3. Busca "SECCIÓN CUARTA" o similar y extrae la descripción
4. Busca fechas como "Bogotá, D.C., dos (2) de mayo de dos mil diecinueve (2019)" y convierte a YYYY-MM-DD
5. Busca "Actor:" o "Demandante:" y extrae el nombre
6. Busca "Demandado:" o "Entidad demandada:" y extrae el nombre
7. Busca "Bogotá, D.C." o similar para la ciudad
8. Busca "Tutela contra providencia judicial" o similar para el tipo de proceso

Responde SOLO en JSON con las claves: consejero_ponente, actor, demandado, fecha, sala, seccion, ciudad, tipo_proceso"""

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        try:
            import streamlit as st  # type: ignore
            if hasattr(st, 'secrets'):
                secret_key = st.secrets.get("OPENAI_API_KEY")  # type: ignore[attr-defined]
                if secret_key:
                    api_key = str(secret_key)
                    os.environ["OPENAI_API_KEY"] = api_key
        except Exception:
            pass
    if not api_key:
        return {"error": "OPENAI_API_KEY no configurada"}

    try:
        from openai import OpenAI
    except Exception:
        return {"error": "Librería openai no instalada"}

    client = OpenAI(api_key=api_key)
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = resp.choices[0].message.content or "{}"
        result = json.loads(content)
        for key in ["consejero_ponente","actor","demandado","fecha","sala","seccion","ciudad","tipo_proceso"]:
            if key not in result:
                result[key] = "No consta"
        return result
    except Exception as e:
        return {"error": f"Error en extracción: {str(e)}"}

def analyze_sentencia_juridica(sentencia: str, model: str = "gpt-4o-mini") -> str:
    """
    Devuelve análisis en Markdown (si usas esta función por separado).
    """
    if not isinstance(sentencia, str) or not sentencia.strip():
        return "No se encontró texto para analizar."

    prompts_dir = Path(__file__).parent.parent / "prompts"
    system_prompt = ""
    user_prompt = ""
    try:
        system_file = prompts_dir / "analysis_system.txt"
        user_file = prompts_dir / "analysis_user.txt"
        if system_file.exists():
            system_prompt = system_file.read_text(encoding="utf-8", errors="ignore")
        if user_file.exists():
            user_prompt = user_file.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        pass

    if not system_prompt:
        system_prompt = ("Eres un abogado experto en derecho constitucional colombiano, "
                         "especializado en tutela contra providencias judiciales. "
                         "Analiza la sentencia del Consejo de Estado siguiendo el formato estructurado.")
    if not user_prompt:
        user_prompt = "Analiza la siguiente sentencia:\n\n{{TEXT}}\n\nDevuelve el resultado en Markdown."

    user_prompt = user_prompt.replace("{{TEXT}}", sentencia[:200000])

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        try:
            import streamlit as st  # type: ignore
            if hasattr(st, 'secrets'):
                secret_key = st.secrets.get("OPENAI_API_KEY")  # type: ignore[attr-defined]
                if secret_key:
                    api_key = str(secret_key)
                    os.environ["OPENAI_API_KEY"] = api_key
        except Exception:
            pass
    if not api_key:
        return "Error: OPENAI_API_KEY no configurada"

    try:
        from openai import OpenAI
    except Exception:
        return "Error: Librería openai no instalada"

    client = OpenAI(api_key=api_key)
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content or "No se pudo generar análisis"
    except Exception as e:
        return f"Error en análisis: {str(e)}"

# -----------------------------
# Empaquetado de metadatos preliminares
# -----------------------------

def extract_prelim_metadata(file_path: Path, text: str) -> Dict[str, str]:
    """
    SIMPLE: Radicado = nombre del archivo. Otros metadatos con IA.
    """
    # Radicado SIEMPRE del nombre del archivo (sin extensión)
    radicado_archivo = file_path.stem.strip()
    print(f"RADICADO = NOMBRE ARCHIVO: {radicado_archivo}")  # Debug

    # Extraer otros metadatos con IA
    metadata = extract_metadata_ia(text, model="gpt-4o-mini")
    print(f"Metadata de IA: {metadata}")  # Debug

    if "error" in metadata:
        print(f"Error en IA: {metadata['error']}")  # Debug
        return {
            "radicado": radicado_archivo,  # ← SIEMPRE del archivo
            "consejero_ponente": "Error IA",
            "sala": "Error IA",
            "seccion": "Error IA",
            "fecha": "Error IA",
        }

    # Resultado: radicado del archivo + metadatos de IA
    result = {
        "radicado": radicado_archivo,  # ← SIEMPRE del archivo
        "consejero_ponente": metadata.get("consejero_ponente", "No consta"),
        "sala": metadata.get("sala", "No consta"),
        "seccion": metadata.get("seccion", "No consta"),
        "fecha": metadata.get("fecha", "No consta"),
    }
    print(f"RESULTADO FINAL: {result}")  # Debug
    return result

# -----------------------------
# Unión de preliminares + LLM análisis a CSV
# -----------------------------

def _row_from_prelim_and_llm(prelim: Dict[str, str], llm: Dict[str, Any]) -> Dict[str, str]:
    def get_s(key: str, default: str = "No consta") -> str:
        val = llm.get(key)
        if val is None:
            return default
        if isinstance(val, (dict, list)):
            try:
                return json.dumps(val, ensure_ascii=False)
            except Exception:
                return default
        return str(val)

    row: Dict[str, str] = {
        **prelim,
        "clasificacion_organo": get_s("clasificacion_organo", "Consejo de Estado"),
        "tipo_tutela": get_s("tipo_tutela"),
        "actos_cuestionados": get_s("actos_cuestionados"),
        "hechos": get_s("hechos"),
        "problemas_juridicos": get_s("problemas_juridicos"),
        "ratio_regla": get_s("ratio_regla"),
        "ratio_premisas": get_s("ratio_premisas"),
        "obiter": get_s("obiter"),
        "c590_generales": get_s("c590_generales"),
        "c590_especificos": get_s("c590_especificos"),
        "decision_resuelve": get_s("decision_resuelve"),
        "precedente_normas": get_s("precedente_normas"),
        "ordenes": get_s("ordenes"),
        "observaciones": get_s("observaciones"),
        "sintesis": get_s("sintesis"),
        "llm_error": str(llm.get("error", "")),
    }
    return row

def analyze_to_csv(source_dir: Path, out_csv: Path, prompts_dir: Path, model: str = "gpt-4o-mini") -> Path:
    files = collect_txt_files(source_dir)
    prompts = load_prompts(prompts_dir)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for path in files:
            text = _read_text(path)
            prelim = extract_prelim_metadata(path, text)  # radicado desde filename
            llm = _call_openai_analisis(text, prompts, model=model)
            row = _row_from_prelim_and_llm(prelim, llm)
            writer.writerow(row)

    return out_csv

# -----------------------------
# Ejemplo de uso (opcional)
# -----------------------------
# if __name__ == "__main__":
#     src = Path("ruta/a/tu/carpeta_txt")
#     out = Path("salidas/sentencias.csv")
#     prompts_dir = Path("prompts")
#     analyze_to_csv(src, out, prompts_dir)
