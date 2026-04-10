#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consolida los 110 archivos _analisis.txt en un CSV completo + estadísticas.
"""

import re
import json
import csv
import sys
from pathlib import Path
from collections import Counter, defaultdict

# ── Mapeo de claves c590_especificos numéricas → nombre ──────────────────────
C590_ESP_NOMBRES = {
    "1": "defecto_orgánico",
    "2": "defecto_procedimental",
    "3": "defecto_fáctico",
    "4": "defecto_material_o_sustantivo",
    "5": "error_inducido",
    "6": "decisión_sin_motivación",
    "7": "desconocimiento_del_precedente",
    "8": "violación_directa_de_la_constitución",
}

C590_GEN_NOMBRES = {
    "1": "relevancia_constitucional",
    "2": "subsidiariedad",
    "3": "inmediatez",
    "4": "identificacion_hechos_derechos",
    "5": "no_sentencia_tutela",
}


def extract_header(text):
    """Extrae metadatos del encabezado del .txt"""
    meta = {}
    for campo, patron in [
        ("radicado",  r"RADICADO:\s*(.+)"),
        ("ponente",   r"(?:CONSEJERO|MAGISTRADO) PONENTE:\s*(.+)"),
        ("sala",      r"SALA:\s*(.+)"),
        ("seccion",   r"SECCIÓN:\s*(.+)"),
        ("fecha",     r"FECHA:\s*(.+)"),
    ]:
        m = re.search(patron, text)
        meta[campo] = m.group(1).strip() if m else "No consta"
    return meta


def extract_json(text):
    """Extrae y parsea el bloque JSON del archivo."""
    # Intenta bloque ```json ... ```
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not m:
        # Fallback: primer { ... } grande
        m = re.search(r"(\{.*\})", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        # Intenta reparar JSON truncado
        raw = m.group(1)
        try:
            return json.loads(raw + "}")
        except Exception:
            return None


def normalize_c590_esp(raw):
    """Normaliza c590_especificos a dict con nombres estandarizados."""
    if not isinstance(raw, dict):
        return {}
    result = {}
    for k, v in raw.items():
        nombre = C590_ESP_NOMBRES.get(str(k), k)
        result[nombre] = str(v).strip()
    return result


def normalize_c590_gen(raw):
    """Extrae si cada criterio general 'Cumple' o no."""
    if not isinstance(raw, dict):
        return {}
    result = {}
    for k, v in raw.items():
        nombre = C590_GEN_NOMBRES.get(str(k), k)
        if isinstance(v, dict):
            # busca el primer valor de texto
            val = next(iter(v.values()), "")
        else:
            val = str(v)
        result[nombre] = val.strip()
    return result


def get_list_as_text(obj, key):
    val = obj.get(key, [])
    if isinstance(val, list):
        return " | ".join(str(x) for x in val)
    return str(val)


def get_precedentes(obj):
    pn = obj.get("precedente_normas", {})
    if not isinstance(pn, dict):
        return "", ""
    prec = pn.get("precedentes") or pn.get("precedentes_citados") or []
    normas = pn.get("normas") or pn.get("normas_interpretadas") or []
    return (
        " | ".join(str(x) for x in prec),
        " | ".join(str(x) for x in normas),
    )


def parse_file(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    meta = extract_header(text)
    data = extract_json(text)

    row = {
        "archivo": path.name,
        "radicado": meta["radicado"],
        "ponente": meta["ponente"],
        "sala": meta["sala"],
        "seccion": meta["seccion"],
        "fecha": meta["fecha"],
        "json_ok": data is not None,
    }

    if data:
        # Clasificacion — acepta dict anidado o campos planos
        cl = data.get("clasificacion_organo", {})
        if isinstance(cl, dict):
            row["organo"] = cl.get("organo", "Consejo de Estado")
            row["tipo_tutela"] = cl.get("tipo_tutela", data.get("tipo_tutela", ""))
            row["actos_cuestionados"] = cl.get("actos_cuestionados", data.get("actos_cuestionados", ""))
        else:
            # clasificacion_organo es string
            row["organo"] = str(cl)
            row["tipo_tutela"] = data.get("tipo_tutela", "")
            row["actos_cuestionados"] = data.get("actos_cuestionados", "")

        # Ponente/sección desde JSON si el header decía "No consta"
        if row["ponente"] == "No consta":
            row["ponente"] = data.get("consejero_ponente", data.get("magistrado_ponente", "No consta"))
        if row["seccion"] == "No consta":
            row["seccion"] = data.get("seccion", "No consta")

        # Narrativa
        row["hechos"] = get_list_as_text(data, "hechos")
        row["problemas_juridicos"] = get_list_as_text(data, "problemas_juridicos")
        row["ratio_regla"] = data.get("ratio_regla", "")
        row["ratio_premisas"] = get_list_as_text(data, "ratio_premisas")
        row["obiter"] = data.get("obiter", "")
        row["decision_resuelve"] = data.get("decision_resuelve", "")
        row["observaciones"] = data.get("observaciones", "")
        row["sintesis"] = data.get("sintesis", "")

        # Ordenes — acepta dict o string
        ord_ = data.get("ordenes", {})
        if isinstance(ord_, dict):
            row["sujetos_obligados"] = ord_.get("sujetos_obligados", "")
            row["actuaciones_ordenadas"] = ord_.get("actuaciones_ordenadas", "")
            row["plazos"] = ord_.get("plazos", "")
        elif isinstance(ord_, str):
            row["sujetos_obligados"] = ""
            row["actuaciones_ordenadas"] = ord_
            row["plazos"] = ""
        else:
            row["sujetos_obligados"] = row["actuaciones_ordenadas"] = row["plazos"] = ""

        # Precedentes y normas — acepta list o dict
        pn = data.get("precedente_normas", {})
        if isinstance(pn, list):
            row["precedentes_citados"] = ""
            row["normas_interpretadas"] = " | ".join(str(x) for x in pn)
        else:
            row["precedentes_citados"], row["normas_interpretadas"] = get_precedentes(data)

        # C590 generales — normaliza claves numéricas o por nombre
        raw_g = data.get("c590_generales", {})
        c590g = {}
        if isinstance(raw_g, dict):
            # Primero normalizamos claves numéricas
            normalized = normalize_c590_gen(raw_g)
            c590g.update(normalized)
            # También buscamos claves por nombre directamente
            for k, v in raw_g.items():
                if k.lower() in ("relevancia_constitucional", "subsidiariedad", "inmediatez",
                                  "identificacion_hechos_derechos", "identificacion_y_alegacion_previa",
                                  "no_sentencia_tutela", "no_es_sentencia_de_tutela"):
                    nombre_std = {
                        "identificacion_y_alegacion_previa": "identificacion_hechos_derechos",
                        "no_es_sentencia_de_tutela": "no_sentencia_tutela",
                    }.get(k.lower(), k.lower())
                    c590g[nombre_std] = str(v).strip()
        for nombre in C590_GEN_NOMBRES.values():
            row[f"c590g_{nombre}"] = c590g.get(nombre, "")

        # C590 específicos — normaliza claves numéricas o por nombre
        raw_e = data.get("c590_especificos", {})
        c590e = {}
        if isinstance(raw_e, dict):
            c590e.update(normalize_c590_esp(raw_e))
            # También busca claves por nombre con variantes
            alias = {
                "defecto_organico": "defecto_orgánico",
                "defecto_procedimental_absoluto": "defecto_procedimental",
                "defecto_factico": "defecto_fáctico",
                "decision_sin_motivacion": "decisión_sin_motivación",
                "violacion_directa_de_la_constitucion": "violación_directa_de_la_constitución",
            }
            for k, v in raw_e.items():
                nombre_std = alias.get(k.lower(), k.lower())
                if nombre_std in C590_ESP_NOMBRES.values():
                    c590e[nombre_std] = str(v).strip()
        for nombre in C590_ESP_NOMBRES.values():
            row[f"c590e_{nombre}"] = c590e.get(nombre, "")

        # Decisión macro: ¿concedió o negó?
        dec = str(row["decision_resuelve"]).lower()
        if any(w in dec for w in ["concede", "conceder", "ampar", "tutela"]):
            row["decision_macro"] = "Concede"
        elif any(w in dec for w in ["niega", "negar", "improcedente", "confirmar"]):
            row["decision_macro"] = "Niega/Confirma"
        elif any(w in dec for w in ["revocar", "revoca"]):
            row["decision_macro"] = "Revoca"
        else:
            row["decision_macro"] = "Otro"

    return row


def print_stats(rows):
    total = len(rows)
    ok = sum(1 for r in rows if r["json_ok"])
    print(f"\n{'='*60}")
    print(f"ESTADÍSTICAS GENERALES — {total} sentencias procesadas")
    print(f"{'='*60}")
    print(f"  JSON parseado correctamente: {ok}/{total}")

    valid = [r for r in rows if r["json_ok"]]

    # Secciones
    print(f"\n--- Secciones ---")
    for sec, cnt in Counter(r["seccion"] for r in valid).most_common():
        print(f"  {sec}: {cnt}")

    # Tipos de tutela
    print(f"\n--- Tipo de tutela ---")
    for t, cnt in Counter(r["tipo_tutela"] for r in valid).most_common():
        print(f"  {t}: {cnt}")

    # Decisiones
    print(f"\n--- Decisión macro ---")
    for d, cnt in Counter(r["decision_macro"] for r in valid).most_common():
        print(f"  {d}: {cnt}")

    # C590 generales — tasa de cumplimiento
    print(f"\n--- C590 Criterios Generales (% que Cumple) ---")
    for nombre in C590_GEN_NOMBRES.values():
        col = f"c590g_{nombre}"
        vals = [r[col] for r in valid if r.get(col)]
        if vals:
            cumple = sum(1 for v in vals if "cumple" in v.lower())
            print(f"  {nombre}: {cumple}/{len(vals)} ({100*cumple//len(vals)}%)")

    # C590 específicos — cuántas sentencias activaron cada defecto
    print(f"\n--- C590 Defectos Específicos (veces identificado como Sí) ---")
    for nombre in C590_ESP_NOMBRES.values():
        col = f"c590e_{nombre}"
        vals = [r[col] for r in valid if r.get(col)]
        si = sum(1 for v in vals if v.lower() in ("sí", "si", "yes", "true", "1"))
        if si > 0:
            print(f"  {nombre}: {si}")

    # Ponentes más activos
    print(f"\n--- Top 10 Ponentes ---")
    for p, cnt in Counter(r["ponente"] for r in valid if r["ponente"] not in ("No consta", "")).most_common(10):
        print(f"  {p}: {cnt}")

    # Normas más citadas
    print(f"\n--- Top 15 Normas más citadas ---")
    normas_counter = Counter()
    for r in valid:
        for n in r.get("normas_interpretadas", "").split(" | "):
            n = n.strip()
            if n:
                normas_counter[n] += 1
    for n, cnt in normas_counter.most_common(15):
        print(f"  {n}: {cnt}")

    print(f"\n{'='*60}\n")


def main(input_dir, output_csv):
    input_path = Path(input_dir)
    files = sorted(input_path.glob("*_analisis.txt"))
    print(f"Encontrados {len(files)} archivos *_analisis.txt en {input_path}")

    rows = []
    errors = []
    for f in files:
        try:
            rows.append(parse_file(f))
        except Exception as e:
            errors.append((f.name, str(e)))
            print(f"  ERROR en {f.name}: {e}")

    if not rows:
        print("No se pudo procesar ningún archivo.")
        return

    # Determinar columnas (unión de todas las keys)
    all_keys = list(rows[0].keys())
    for r in rows[1:]:
        for k in r:
            if k not in all_keys:
                all_keys.append(k)

    # Escribir CSV
    out = Path(output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"\n✅ CSV guardado en: {out}  ({len(rows)} filas, {len(all_keys)} columnas)")

    if errors:
        print(f"⚠️  {len(errors)} archivos con error:")
        for name, err in errors:
            print(f"   {name}: {err}")

    print_stats(rows)


if __name__ == "__main__":
    BASE = "/Users/pro2020/Library/CloudStorage/OneDrive-UniversidadExternadodeColombia/Consejo de Estado IA/Repositorio/ANALES 2019/ACCION DE TUTELA/G1/archvos .txt"
    INPUT_DIR = BASE + "/analisis_individuales"
    OUTPUT_CSV = BASE + "/resultados/analisis_consolidado.csv"

    if len(sys.argv) == 3:
        INPUT_DIR, OUTPUT_CSV = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 2:
        INPUT_DIR = sys.argv[1]

    main(INPUT_DIR, OUTPUT_CSV)
