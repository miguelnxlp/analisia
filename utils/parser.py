"""
parser.py — Normaliza el JSON devuelto por el LLM en un dict plano listo para CSV.
Maneja todas las variantes de estructura que produce el modelo.
"""

import re
import json


# ── Catálogos válidos ────────────────────────────────────────────────────────
MATERIAS_PRINCIPALES = {
    "Pensional", "Empleo Público", "Salud", "Responsabilidad del Estado",
    "Proceso Judicial", "Desacato / Cumplimiento", "Disciplinario",
    "Político / Electoral", "Contratación Pública", "Otro",
}

DERECHOS_VALIDOS = {
    "Debido proceso", "Igualdad", "Acceso a la administración de justicia",
    "Seguridad social", "Salud", "Trabajo", "Mínimo vital", "Dignidad humana",
    "Petición", "Participación política", "Defensa", "Propiedad privada",
    "Otro derecho fundamental",
}

# ── Alias de claves inconsistentes del modelo ────────────────────────────────
C590_ESP_ALIAS = {
    "1": "defecto_organico", "2": "defecto_procedimental",
    "3": "defecto_factico",  "4": "defecto_material",
    "5": "error_inducido",   "6": "decision_sin_motivacion",
    "7": "desconocimiento_precedente", "8": "violacion_constitucion",
    "defecto_orgánico": "defecto_organico",
    "defecto_procedimental_absoluto": "defecto_procedimental",
    "defecto_fáctico": "defecto_factico",
    "defecto_material_o_sustantivo": "defecto_material",
    "decisión_sin_motivación": "decision_sin_motivacion",
    "desconocimiento_del_precedente": "desconocimiento_precedente",
    "violación_directa_de_la_constitución": "violacion_constitucion",
    "violacion_directa_de_la_constitucion": "violacion_constitucion",
}

C590_GEN_ALIAS = {
    "1": "relevancia_constitucional", "2": "subsidiariedad",
    "3": "inmediatez", "4": "identificacion_hechos_derechos",
    "5": "no_sentencia_tutela",
    "identificacion_y_alegacion_previa": "identificacion_hechos_derechos",
    "no_es_sentencia_de_tutela": "no_sentencia_tutela",
    "legitimacion_activa": "legitimacion_activa",
    "legitimacion_pasiva": "legitimacion_pasiva",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _to_str(v) -> str:
    if v is None:
        return "No consta"
    if isinstance(v, str):
        return v.strip() or "No consta"
    if isinstance(v, list):
        parts = []
        for x in v:
            if isinstance(x, dict):
                parts.append(" | ".join(str(vv) for vv in x.values() if vv))
            else:
                parts.append(str(x))
        return " | ".join(p for p in parts if p)
    if isinstance(v, dict):
        return " | ".join(str(vv) for vv in v.values() if vv)
    return str(v)


def _to_list(v) -> list:
    if isinstance(v, list):
        return [str(x).strip() for x in v if x]
    if isinstance(v, str) and v.strip():
        return [v.strip()]
    return []


def _extract_json(raw_text: str) -> dict | None:
    """Extrae el primer objeto JSON válido del texto, con varios fallbacks."""
    # 1. Bloque ```json ... ```
    m = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 2. Primer { ... } completo
    m = re.search(r"(\{.*\})", raw_text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            # 3. Intentar reparar JSON truncado
            raw = m.group(1)
            for suffix in ["}", "}}", "}}}"]:
                try:
                    return json.loads(raw + suffix)
                except json.JSONDecodeError:
                    continue
    return None


def _normalize_c590_generales(raw: dict) -> dict:
    result = {}
    for k, v in raw.items():
        nombre = C590_GEN_ALIAS.get(str(k).strip(), str(k).strip())
        if isinstance(v, dict):
            val = next((str(vv) for vv in v.values() if vv), "")
        else:
            val = str(v)
        result[nombre] = val.strip()
    return result


def _normalize_c590_especificos(raw: dict) -> dict:
    result = {}
    for k, v in raw.items():
        if k.lower() == "soporte":
            continue
        nombre = C590_ESP_ALIAS.get(str(k).strip(), C590_ESP_ALIAS.get(str(k).strip().lower(), str(k).strip()))
        if isinstance(v, dict):
            val = next((str(vv) for vv in v.values() if vv), "No")
        else:
            val = str(v)
        result[nombre] = val.strip()
    return result


def _decision_macro(texto: str) -> str:
    t = texto.lower()
    if any(w in t for w in ["concede", "conceder", "ampara", "amparar", "tutela"]):
        return "Concede"
    if any(w in t for w in ["niega", "negar", "improcedente", "deniega"]):
        return "Niega"
    if any(w in t for w in ["confirma", "confirmar"]):
        return "Confirma"
    if any(w in t for w in ["revoca", "revocar"]):
        return "Revoca"
    if any(w in t for w in ["carencia", "hecho superado"]):
        return "Carencia de objeto"
    return "Otro"


# ── API pública ───────────────────────────────────────────────────────────────

def parse_analysis(raw_text: str, radicado: str = "") -> dict:
    """
    Toma el texto crudo devuelto por el LLM y devuelve un dict plano
    con todas las columnas normalizadas listas para el CSV.
    """
    row: dict = {"radicado": radicado, "json_ok": False}
    data = _extract_json(raw_text)

    if not data or not isinstance(data, dict):
        row["parse_error"] = "JSON no encontrado o inválido"
        return row

    row["json_ok"] = True

    # ── Clasificación del órgano ────────────────────────────────────────────
    cl = data.get("clasificacion_organo", {})
    if isinstance(cl, dict):
        row["organo"]          = cl.get("organismo") or cl.get("organo") or "Consejo de Estado"
        row["seccion"]         = cl.get("seccion", "No consta")
        row["sala"]            = cl.get("sala", "No consta")
        row["tipo_providencia"]= cl.get("tipo_providencia", "No consta")
    else:
        row["organo"]          = str(cl) or "Consejo de Estado"
        row["seccion"]         = data.get("seccion", "No consta")
        row["sala"]            = data.get("sala", "No consta")
        row["tipo_providencia"]= "No consta"

    # ── Tipo de tutela ──────────────────────────────────────────────────────
    tt = data.get("tipo_tutela", {})
    if isinstance(tt, dict):
        row["tipo_tutela_categoria"]  = tt.get("categoria", "No consta")
        row["tipo_tutela_subcategoria"]= tt.get("subcategoria", "No consta")
        row["regimen_procedencia"]    = tt.get("regimen_procedencia", "No consta")
    else:
        row["tipo_tutela_categoria"]  = str(tt) or "No consta"
        row["tipo_tutela_subcategoria"]= "No consta"
        row["regimen_procedencia"]    = "No consta"

    # ── Actos cuestionados ──────────────────────────────────────────────────
    aq = data.get("actos_cuestionados", {})
    if isinstance(aq, dict):
        row["actos_cuestionados"]  = aq.get("descripcion", "No consta")
        row["naturaleza_acto"]     = aq.get("naturaleza", "No consta")
        row["fecha_acto"]          = aq.get("fecha_acto", "No consta")
        row["autor_acto"]          = aq.get("autor_acto", "No consta")
    else:
        row["actos_cuestionados"]  = _to_str(aq)
        row["naturaleza_acto"]     = "No consta"
        row["fecha_acto"]          = "No consta"
        row["autor_acto"]          = "No consta"

    # ── Hechos ──────────────────────────────────────────────────────────────
    hechos = data.get("hechos", [])
    if isinstance(hechos, list):
        partes = []
        for h in hechos:
            if isinstance(h, dict):
                partes.append(h.get("descripcion") or _to_str(h))
            else:
                partes.append(str(h))
        row["hechos"] = " | ".join(partes)
    else:
        row["hechos"] = _to_str(hechos)

    # ── Problemas jurídicos ─────────────────────────────────────────────────
    pj = data.get("problemas_juridicos", [])
    if isinstance(pj, list):
        partes = []
        for p in pj:
            if isinstance(p, dict):
                partes.append(p.get("problema") or p.get("cuestion_juridica") or _to_str(p))
            else:
                partes.append(str(p))
        row["problemas_juridicos"] = " | ".join(partes)
        row["derechos_en_pj"] = " | ".join(
            str(d) for p in pj if isinstance(p, dict)
            for d in _to_list(p.get("derechos_involucrados", []))
        )
    else:
        row["problemas_juridicos"] = _to_str(pj)
        row["derechos_en_pj"]      = ""

    # ── Ratio ───────────────────────────────────────────────────────────────
    rr = data.get("ratio_regla", {})
    if isinstance(rr, dict):
        row["ratio_regla"]        = rr.get("regla_general", "No consta")
        row["ratio_alcance"]      = rr.get("alcance", "No consta")
        row["ratio_limitaciones"] = rr.get("limitaciones", "No consta")
    else:
        row["ratio_regla"]        = _to_str(rr)
        row["ratio_alcance"]      = "No consta"
        row["ratio_limitaciones"] = "No consta"

    rp = data.get("ratio_premisas", [])
    if isinstance(rp, list):
        row["ratio_premisas"] = " | ".join(
            p.get("premisa", _to_str(p)) if isinstance(p, dict) else str(p)
            for p in rp
        )
    else:
        row["ratio_premisas"] = _to_str(rp)

    # ── Obiter ──────────────────────────────────────────────────────────────
    ob = data.get("obiter", {})
    if isinstance(ob, dict):
        row["obiter"]            = ob.get("descripcion", "No consta")
        row["obiter_relevancia"] = ob.get("relevancia", "No consta")
    else:
        row["obiter"]            = _to_str(ob)
        row["obiter_relevancia"] = "No consta"

    # ── C590 generales ──────────────────────────────────────────────────────
    c590g_raw = data.get("c590_generales", {})
    c590g = _normalize_c590_generales(c590g_raw) if isinstance(c590g_raw, dict) else {}
    for nombre in ["relevancia_constitucional", "subsidiariedad", "inmediatez",
                   "identificacion_hechos_derechos", "no_sentencia_tutela",
                   "legitimacion_activa", "legitimacion_pasiva"]:
        row[f"c590g_{nombre}"] = c590g.get(nombre, "No consta")

    # ── C590 específicos ────────────────────────────────────────────────────
    c590e_raw = data.get("c590_especificos", {})
    c590e = _normalize_c590_especificos(c590e_raw) if isinstance(c590e_raw, dict) else {}
    for nombre in ["defecto_organico", "defecto_procedimental", "defecto_factico",
                   "defecto_material", "error_inducido", "decision_sin_motivacion",
                   "desconocimiento_precedente", "violacion_constitucion"]:
        val = c590e.get(nombre, "No")
        row[f"c590e_{nombre}"] = val
        row[f"c590e_{nombre}_si"] = 1 if val.lower() in ("sí", "si", "yes", "true", "1") else 0

    # ── Decisión ────────────────────────────────────────────────────────────
    dr = data.get("decision_resuelve", {})
    if isinstance(dr, dict):
        row["decision_texto"]     = dr.get("texto_completo", "No consta")
        row["decision_puntos"]    = str(dr.get("numero_puntos", ""))
        row["decision_naturaleza"]= dr.get("naturaleza_decision", "No consta")
    elif isinstance(dr, list):
        row["decision_texto"]     = " | ".join(str(x) for x in dr)
        row["decision_puntos"]    = str(len(dr))
        row["decision_naturaleza"]= "No consta"
    else:
        row["decision_texto"]     = _to_str(dr)
        row["decision_puntos"]    = ""
        row["decision_naturaleza"]= "No consta"

    row["decision_macro"] = _decision_macro(row["decision_texto"])
    if row["decision_macro"] == "Otro" and row.get("decision_naturaleza"):
        row["decision_macro"] = _decision_macro(row["decision_naturaleza"])

    # ── Precedentes y normas ────────────────────────────────────────────────
    pn = data.get("precedente_normas", {})
    if isinstance(pn, dict):
        prec = pn.get("precedentes") or pn.get("precedentes_citados") or pn.get("precedente_citado") or []
        norm = pn.get("normas_interpretadas") or pn.get("normas") or []
        doct = pn.get("doctrina_relevante") or []
        row["precedentes"] = " | ".join(
            (p.get("numero") or p.get("tipo") or _to_str(p)) if isinstance(p, dict) else str(p)
            for p in prec if p
        )
        row["normas"] = " | ".join(
            (n.get("numero") or n.get("tipo") or _to_str(n)) if isinstance(n, dict) else str(n)
            for n in norm if n
        )
        row["doctrina"] = " | ".join(
            (d.get("obra") or _to_str(d)) if isinstance(d, dict) else str(d)
            for d in doct if d
        )
    elif isinstance(pn, list):
        row["precedentes"] = ""
        row["normas"]      = " | ".join(str(x) for x in pn)
        row["doctrina"]    = ""
    else:
        row["precedentes"] = ""
        row["normas"]      = _to_str(pn)
        row["doctrina"]    = ""

    # ── Órdenes ─────────────────────────────────────────────────────────────
    ord_ = data.get("ordenes", {})
    if isinstance(ord_, dict):
        row["sujetos_obligados"]      = _to_str(ord_.get("sujetos_obligados", ""))
        row["actuaciones_ordenadas"]  = _to_str(ord_.get("actuaciones_ordenadas", ""))
        row["plazos"]                 = _to_str(ord_.get("plazos", ""))
        row["consecuencias_incump"]   = _to_str(ord_.get("consecuencias_incumplimiento", ""))
    else:
        row["sujetos_obligados"]     = ""
        row["actuaciones_ordenadas"] = _to_str(ord_)
        row["plazos"]                = ""
        row["consecuencias_incump"]  = ""

    # ── Observaciones ───────────────────────────────────────────────────────
    obs = data.get("observaciones", {})
    if isinstance(obs, dict):
        row["criticas_constitucionales"] = obs.get("criticas_constitucionales", "No consta")
        row["tensiones_normativas"]      = obs.get("tensiones_normativas", "No consta")
        row["vacios_juridicos"]          = obs.get("vacios_juridicos", "No consta")
        row["implicaciones_practicas"]   = obs.get("implicaciones_practicas", "No consta")
    else:
        row["criticas_constitucionales"] = _to_str(obs)
        row["tensiones_normativas"]      = "No consta"
        row["vacios_juridicos"]          = "No consta"
        row["implicaciones_practicas"]   = "No consta"

    # ── Síntesis ────────────────────────────────────────────────────────────
    sint = data.get("sintesis", {})
    if isinstance(sint, dict):
        row["resumen_ejecutivo"]      = sint.get("resumen_ejecutivo", "No consta")
        row["impacto_jurisprudencial"]= sint.get("impacto_jurisprudencial", "No consta")
        row["recomendaciones"]        = sint.get("recomendaciones", "No consta")
    else:
        row["resumen_ejecutivo"]      = _to_str(sint)
        row["impacto_jurisprudencial"]= "No consta"
        row["recomendaciones"]        = "No consta"

    # ── Materia ─────────────────────────────────────────────────────────────
    mat = data.get("materia", {})
    if isinstance(mat, dict):
        mp = mat.get("materia_principal", "")
        row["materia_principal"] = mp if mp in MATERIAS_PRINCIPALES else (mp or "No consta")
        row["submateria"]        = mat.get("submateria", "No consta")
        derechos = _to_list(mat.get("derechos_invocados", []))
        row["derechos_invocados"]= " | ".join(derechos) if derechos else "No consta"
    else:
        row["materia_principal"] = "No consta"
        row["submateria"]        = "No consta"
        row["derechos_invocados"]= "No consta"

    return row


def parse_from_txt_file(path, radicado: str = "") -> dict:
    """Wrapper: lee un archivo .txt de análisis y lo parsea."""
    from pathlib import Path
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    if not radicado:
        # Intentar extraer radicado del encabezado
        m = re.search(r"RADICADO:\s*(.+)", text)
        radicado = m.group(1).strip() if m else Path(path).stem.replace("_analisis", "")
    return parse_analysis(text, radicado=radicado)
