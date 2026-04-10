"""
AnalisIA v2.1 — app_unificado.py
Sin dependencias de archivos iCloud en el startup path.
"""
from pathlib import Path
import os
import csv
import json
import tempfile

import streamlit as st

# ── Único import de utils disponible localmente ───────────────────────────────
from utils.parser import parse_analysis

# ── CSS verde oscuro ──────────────────────────────────────────────────────────
CSS = """
<style>
[data-testid="stAppViewContainer"] { background-color: #0d2818; }
[data-testid="stSidebar"] { background-color: #0a1f12; border-right: 1px solid #2d5a3d; }
[data-testid="stHeader"] { background-color: #0a1f12; border-bottom: 1px solid #2d5a3d; }
html, body, [class*="css"] { color: #e8f5e9; }
[data-testid="metric-container"] {
    background-color: #1a3a2a; border: 1px solid #2d5a3d;
    border-radius: 8px; padding: 12px;
}
[data-testid="stTextInput"] input, textarea {
    background-color: #1a3a2a !important; color: #e8f5e9 !important;
    border: 1px solid #2d5a3d !important;
}
[data-testid="stButton"] button[kind="primary"] { background-color: #2e7d32; color: white; border: none; }
[data-testid="stButton"] button[kind="primary"]:hover { background-color: #388e3c; }
[data-testid="stButton"] button { background-color: #1a3a2a; color: #a5d6a7; border: 1px solid #2d5a3d; }
[data-testid="stTabs"] [data-baseweb="tab"] { background-color: #1a3a2a; color: #a5d6a7; }
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    border-bottom: 2px solid #4CAF50; color: #e8f5e9;
}
[data-testid="stExpander"] { background-color: #1a3a2a; border: 1px solid #2d5a3d; border-radius: 8px; }
hr { border-color: #2d5a3d; }
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0d2818; }
::-webkit-scrollbar-thumb { background: #2d5a3d; border-radius: 3px; }
</style>
"""

# ── Constantes ────────────────────────────────────────────────────────────────
LOCAL_CONFIG = Path.home() / ".analisia" / "config.env"
APP_DIR = Path(__file__).parent

MODELOS = [
    "gpt-4.1-nano",
    "gpt-4o-mini",
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-4o",
]


# ── API key local ─────────────────────────────────────────────────────────────

def _load_local_key() -> str:
    if LOCAL_CONFIG.exists():
        for line in LOCAL_CONFIG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _save_local_key(key: str):
    LOCAL_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_CONFIG.write_text(f"OPENAI_API_KEY={key}\n", encoding="utf-8")
    LOCAL_CONFIG.chmod(0o600)


def _init_key():
    """Carga la key solo desde fuentes locales — nunca toca iCloud."""
    if not os.getenv("OPENAI_API_KEY"):
        key = _load_local_key()
        if key:
            os.environ["OPENAI_API_KEY"] = key
    if not os.getenv("OPENAI_API_KEY"):
        try:
            key = st.secrets.get("OPENAI_API_KEY", "")
            if key:
                os.environ["OPENAI_API_KEY"] = str(key)
        except Exception:
            pass


# ── OpenAI directo (sin pasar por utils/analysis.py) ─────────────────────────

def _load_prompts() -> tuple[str, str]:
    """Lee los prompts desde disco. Solo se llama al analizar, no en startup."""
    pd = APP_DIR / "prompts"
    system = (pd / "analysis_system.txt").read_text(encoding="utf-8")
    user   = (pd / "analysis_user.txt").read_text(encoding="utf-8")
    return system, user


def _analyze(text: str, model: str) -> str:
    """Llama a OpenAI directamente y devuelve el texto crudo de la respuesta."""
    from openai import OpenAI
    system_prompt, user_template = _load_prompts()
    user_prompt = user_template.replace("{{TEXT}}", text[:40000])  # límite seguro

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=4096,
    )
    return resp.choices[0].message.content


def _extract_metadata(text: str, model: str) -> dict:
    """Extrae metadatos básicos con una llamada ligera."""
    from openai import OpenAI
    prompt = """Extrae los siguientes metadatos de la sentencia en JSON estricto:
{
  "radicado": "string",
  "consejero_ponente": "string",
  "sala": "string",
  "seccion": "string",
  "fecha": "YYYY-MM-DD o No consta",
  "ciudad": "string",
  "actor": "string",
  "demandado": "string"
}
Si no encuentras un dato, usa "No consta". Solo devuelve el JSON, sin texto adicional.

SENTENCIA:
""" + text[:8000]

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=400,
    )
    raw = resp.choices[0].message.content
    import re
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}


def _read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _collect_txt(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.txt"))


# ── Pipeline status ───────────────────────────────────────────────────────────

def _pipeline_status(base: Path):
    """Solo glob — nunca lee contenido."""
    dirs = {
        "TXT":        (base / "archivos_txt",         "*.txt"),
        "Caché":      (base / "cache_analisis",        "*_analisis.json"),
        "Exportados": (base / "analisis_individuales", "*_analisis.txt"),
    }
    cols = st.columns(len(dirs))
    for (label, (d, pat)), col in zip(dirs.items(), cols):
        try:
            count = len(list(d.glob(pat))) if d.exists() else 0
        except Exception:
            count = 0
        with col:
            st.metric(label, count)


def get_base_dir() -> Path | None:
    raw = st.session_state.get("base_dir", "")
    if not raw:
        return None
    p = Path(raw).expanduser()
    return p if p.exists() else None


# ── Consolidar CSV desde caché ────────────────────────────────────────────────

def _consolidar_csv(cache_dir: Path, res_dir: Path):
    rows, all_keys = [], []
    for jf in sorted(cache_dir.glob("*_analisis.json")):
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            parsed = data.get("parsed", {})
            if not parsed:
                continue
            rows.append(parsed)
            for k in parsed:
                if k not in all_keys:
                    all_keys.append(k)
        except Exception:
            continue
    if not rows:
        return 0
    res_dir.mkdir(parents=True, exist_ok=True)
    # Guardar en res_dir (puede ser base o resultados/)
    csv_path = res_dir / "analisis_consolidado.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    return len(rows)


# ══ MÓDULOS ═══════════════════════════════════════════════════════════════════

def ui_mod0():
    """Descompresión ZIP."""
    st.subheader("Descompresión masiva de ZIP")
    base = get_base_dir()
    if not base:
        st.info("Configura el directorio del proyecto en el panel izquierdo.")
        return

    try:
        from utils.zip_extractor import extract_zip_files, scan_zip_directory, clean_extracted_directory
    except Exception:
        st.error("No se pudo cargar el módulo de ZIP.")
        return

    zip_info = scan_zip_directory(base)
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("ZIPs", zip_info["total_zips"])
    with c2: st.metric("Tamaño", f"{zip_info['total_size_mb']:.1f} MB")
    with c3: st.metric("Estado", "Listo" if zip_info["total_zips"] > 0 else "Sin ZIPs")

    if zip_info.get("zip_details"):
        with st.expander("Detalle"):
            for d in zip_info["zip_details"]:
                st.write(f"{'✅' if d['status']=='OK' else '❌'} **{d['name']}** — {d['size_mb']} MB")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Descomprimir todos", type="primary", disabled=zip_info["total_zips"] == 0):
            with st.spinner("Descomprimiendo..."):
                extracted, errors = extract_zip_files(base, base / "extracted")
            st.success(f"✅ {len(extracted)} archivos extraídos")
            if errors:
                st.error(f"{len(errors)} errores")
    with c2:
        if st.button("Limpiar extraídos"):
            clean_extracted_directory(base / "extracted")
            st.success("Limpiado")


def ui_mod1():
    """Conversión a TXT."""
    st.subheader("Conversión a .txt")
    base = get_base_dir()
    if not base:
        st.info("Configura el directorio del proyecto en el panel izquierdo.")
        return

    src = st.text_input("Carpeta fuente", value=str(base / "extracted") if (base / "extracted").exists() else str(base))
    src_path = Path(src) if src else None
    target = base / "archivos_txt"

    if st.button("Escanear"):
        if src_path and src_path.exists():
            files = [p for p in src_path.rglob("*") if p.suffix.lower() in {".txt",".doc",".docx",".pdf"}]
            st.session_state["m1_files"] = [str(f) for f in files]
            st.success(f"{len(files)} archivos encontrados")
        else:
            st.error("Carpeta no existe")

    files = [Path(f) for f in st.session_state.get("m1_files", [])]
    if files:
        by_ext = {}
        for f in files:
            by_ext[f.suffix.lower()] = by_ext.get(f.suffix.lower(), 0) + 1
        cols = st.columns(len(by_ext))
        for i, (ext, cnt) in enumerate(by_ext.items()):
            with cols[i]: st.metric(ext, cnt)

    if st.button("Convertir a TXT", type="primary", disabled=not files):
        try:
            from utils.extract_text import convert_file_to_txt
        except Exception:
            st.error("Módulo de conversión no disponible (iCloud). Copia utils/ a una carpeta local.")
            return
        target.mkdir(parents=True, exist_ok=True)
        progress = st.progress(0)
        ok = err = 0
        for idx, path in enumerate(files, 1):
            try:
                convert_file_to_txt(path, target)
                ok += 1
            except Exception:
                err += 1
            progress.progress(idx / len(files), text=f"{idx}/{len(files)} — {path.name}")
        progress.empty()
        st.success(f"✅ {ok} convertidos — {err} errores — `{target}`")


def ui_mod2():
    """Análisis jurídico completo."""
    st.subheader("Análisis jurídico completo con IA")
    base = get_base_dir()
    if not base:
        st.info("Configura el directorio del proyecto en el panel izquierdo.")
        return

    if not os.getenv("OPENAI_API_KEY"):
        st.error("Sin API key. Ingresa tu key en el panel izquierdo.")
        return

    txt_dir   = base / "archivos_txt"
    cache_dir = base / "cache_analisis"
    ana_dir   = base / "analisis_individuales"
    res_dir   = base / "resultados"

    if not txt_dir.exists():
        alt = st.text_input("Carpeta con archivos .txt", value=str(base))
        txt_dir = Path(alt).expanduser() if alt else txt_dir

    c1, c2 = st.columns([2, 1])
    with c1:
        idx_modelo = MODELOS.index(st.session_state.get("modelo_global", MODELOS[0])) \
                     if st.session_state.get("modelo_global") in MODELOS else 0
        model_name = st.selectbox("Modelo", MODELOS, index=idx_modelo, key="m2_model")
    with c2:
        solo_nuevos = st.checkbox("Solo nuevos", value=True, help="Salta archivos ya en caché")

    if st.button("Escanear TXT"):
        if txt_dir.exists():
            files = _collect_txt(txt_dir)
            st.session_state["m2_files"] = [str(f) for f in files]
            st.success(f"{len(files)} archivos encontrados")
        else:
            st.error("La carpeta no existe")

    files = [Path(f) for f in st.session_state.get("m2_files", [])]
    if not files:
        return

    cache_dir.mkdir(exist_ok=True)
    cached = len(list(cache_dir.glob("*_analisis.json")))
    pendientes = [f for f in files if not (cache_dir / f"{f.stem}_analisis.json").exists()] \
                 if solo_nuevos else files

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Total TXT", len(files))
    with c2: st.metric("En caché", cached)
    with c3: st.metric("Por procesar", len(pendientes))

    if not pendientes:
        st.success("Todo procesado. Ve al Dashboard.")
        if st.button("Actualizar CSV"):
            n = _consolidar_csv(cache_dir, res_dir)
            st.success(f"CSV actualizado — {n} filas")
        return

    if st.button(f"▶ Analizar {len(pendientes)} sentencias", type="primary"):
        _run_analysis(pendientes, cache_dir, ana_dir, res_dir, model_name)


def _run_analysis(files: list[Path], cache_dir: Path, ana_dir: Path, res_dir: Path, model: str):
    ana_dir.mkdir(exist_ok=True)
    res_dir.mkdir(exist_ok=True)

    total = len(files)
    progress = st.progress(0)
    status   = st.empty()
    errores  = []
    concede = niega = otro = 0

    for idx, path in enumerate(files, 1):
        status.markdown(f"**{idx}/{total}** — `{path.name}`")
        cache_file = cache_dir / f"{path.stem}_analisis.json"

        try:
            text = _read_txt(path)

            # 1 call: metadatos (barato)
            metadata = _extract_metadata(text, model)
            radicado = metadata.get("radicado") or path.stem

            # 1 call: análisis completo
            analisis_raw = _analyze(text, model)

            # Parsear JSON
            parsed = parse_analysis(analisis_raw, radicado=radicado)

            # Enriquecer con metadatos
            for campo in ["seccion", "sala", "consejero_ponente", "actor", "demandado", "fecha", "ciudad"]:
                if parsed.get(campo, "No consta") in ("No consta", "", None):
                    parsed[campo] = metadata.get(campo, "No consta")

            parsed["archivo"] = str(path)

            # Guardar caché
            with cache_file.open("w", encoding="utf-8") as f:
                json.dump({"radicado": radicado, "metadata": metadata,
                           "analisis_raw": analisis_raw, "parsed": parsed},
                          f, ensure_ascii=False, indent=2)

            # TXT individual
            txt_file = ana_dir / f"{radicado}_analisis.txt"
            txt_file.write_text(
                f"ANÁLISIS JURÍDICO COMPLETO\n{'='*60}\n\n"
                f"RADICADO: {radicado}\n"
                f"PONENTE: {parsed.get('consejero_ponente','No consta')}\n"
                f"SECCIÓN: {parsed.get('seccion','No consta')}\n"
                f"FECHA: {parsed.get('fecha','No consta')}\n"
                f"MATERIA: {parsed.get('materia_principal','No consta')} — {parsed.get('submateria','')}\n\n"
                f"{'='*60}\n\n{analisis_raw}\n\n"
                f"{'='*60}\nGenerado por AnalisIA v2.1\n",
                encoding="utf-8"
            )

            dm = parsed.get("decision_macro", "Otro")
            if dm == "Concede": concede += 1
            elif dm in ("Niega", "Confirma"): niega += 1
            else: otro += 1

        except Exception as e:
            errores.append(f"{path.name}: {e}")

        progress.progress(idx / total)

    progress.empty()
    status.empty()

    n = _consolidar_csv(cache_dir, res_dir)
    st.success(f"✅ {total - len(errores)}/{total} analizadas — CSV con {n} filas")
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Concede", concede)
    with c2: st.metric("Niega/Confirma", niega)
    with c3: st.metric("Otro", otro)
    if errores:
        with st.expander(f"⚠ {len(errores)} errores"):
            for e in errores: st.caption(e)


def ui_mod3():
    """Dashboard de tendencias."""
    st.subheader("Dashboard de tendencias")
    base = get_base_dir()
    if not base:
        st.info("Configura el directorio del proyecto en el panel izquierdo.")
        return

    try:
        import pandas as pd
        import plotly.express as px
    except ImportError:
        st.error("Instala plotly: `pip install plotly`")
        return

    cache_dir = base / "cache_analisis"
    # Buscar CSV en base o en resultados/
    csv_path = base / "analisis_consolidado.csv"
    if not csv_path.exists():
        csv_path = base / "resultados" / "analisis_consolidado.csv"

    if st.button("Actualizar CSV desde caché"):
        n = _consolidar_csv(cache_dir, base)
        st.success(f"CSV actualizado — {n} filas")
        csv_path = base / "analisis_consolidado.csv"

    if not csv_path.exists():
        st.warning("Sin CSV aún. Ejecuta el análisis o actualiza desde caché.")
        return

    try:
        df = pd.read_csv(csv_path)
    except TimeoutError:
        st.error(f"Timeout leyendo `{csv_path}`. Archivo no descargado localmente.")
        return
    except Exception as e:
        st.error(f"Error: {e}")
        return

    total = len(df)
    if total == 0:
        st.warning("CSV vacío.")
        return

    # KPIs
    st.markdown("### Resumen general")
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Total sentencias", total)
    with c2:
        if "decision_macro" in df.columns:
            n = (df["decision_macro"] == "Concede").sum()
            st.metric("Conceden", n, f"{100*n//total}%")
    with c3:
        if "materia_principal" in df.columns:
            top = df["materia_principal"].value_counts().index[0]
            st.metric("Materia top", top)
    with c4:
        col = "c590e_desconocimiento_precedente_si"
        if col in df.columns:
            st.metric("Descon. precedente", int(df[col].sum()))

    st.markdown("---")
    col1, col2 = st.columns(2)

    BG, FONT = "#1a3a2a", "#e8f5e9"

    def _layout(fig):
        fig.update_layout(paper_bgcolor=BG, plot_bgcolor=BG,
                          font_color=FONT, title_font_color=FONT)
        return fig

    with col1:
        if "decision_macro" in df.columns:
            fig = px.pie(df, names="decision_macro", title="Decisiones",
                         color_discrete_sequence=["#4CAF50","#ef5350","#FFA726","#42A5F5"], hole=0.4)
            st.plotly_chart(_layout(fig), use_container_width=True)

    with col2:
        if "materia_principal" in df.columns:
            mc = df["materia_principal"].value_counts().reset_index()
            mc.columns = ["Materia", "n"]
            fig = px.bar(mc, x="n", y="Materia", orientation="h", title="Materias",
                         color="n", color_continuous_scale=["#1a3a2a","#4CAF50"])
            fig.update_layout(yaxis={"categoryorder":"total ascending"})
            st.plotly_chart(_layout(fig), use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        if "submateria" in df.columns:
            sc = df["submateria"].value_counts().head(15).reset_index()
            sc.columns = ["Submateria","n"]
            fig = px.bar(sc, x="n", y="Submateria", orientation="h", title="Top submaterias",
                         color="n", color_continuous_scale=["#1a3a2a","#81C784"])
            fig.update_layout(yaxis={"categoryorder":"total ascending"})
            st.plotly_chart(_layout(fig), use_container_width=True)

    with col4:
        c590_cols = [c for c in df.columns if c.startswith("c590e_") and c.endswith("_si")]
        if c590_cols:
            defectos = {c.replace("c590e_","").replace("_si","").replace("_"," ").title(): int(df[c].sum())
                        for c in c590_cols if df[c].sum() > 0}
            if defectos:
                df_d = pd.DataFrame(list(defectos.items()), columns=["Defecto","n"])
                fig = px.bar(df_d.sort_values("n"), x="n", y="Defecto", orientation="h",
                             title="Defectos C590",
                             color="n", color_continuous_scale=["#1a3a2a","#EF9A9A"])
                st.plotly_chart(_layout(fig), use_container_width=True)

    if "derechos_invocados" in df.columns:
        st.markdown("### Derechos fundamentales invocados")
        from collections import Counter
        cnt = Counter()
        for v in df["derechos_invocados"].dropna():
            for d in str(v).split(" | "):
                d = d.strip()
                if d and d != "No consta": cnt[d] += 1
        if cnt:
            df_der = pd.DataFrame(cnt.most_common(12), columns=["Derecho","n"])
            fig = px.bar(df_der, x="n", y="Derecho", orientation="h",
                         color="n", color_continuous_scale=["#1a3a2a","#4CAF50"])
            fig.update_layout(yaxis={"categoryorder":"total ascending"})
            st.plotly_chart(_layout(fig), use_container_width=True)

    st.markdown("### Explorar sentencias")
    cols_show = [c for c in ["radicado","fecha","seccion","materia_principal","submateria",
                              "decision_macro","resumen_ejecutivo"] if c in df.columns]

    fc1, fc2, fc3 = st.columns(3)
    df_f = df.copy()
    with fc1:
        if "materia_principal" in df.columns:
            opts = ["Todas"] + sorted(df["materia_principal"].dropna().unique().tolist())
            sel = st.selectbox("Materia", opts)
            if sel != "Todas": df_f = df_f[df_f["materia_principal"] == sel]
    with fc2:
        if "decision_macro" in df.columns:
            opts = ["Todas"] + sorted(df["decision_macro"].dropna().unique().tolist())
            sel = st.selectbox("Decisión", opts)
            if sel != "Todas": df_f = df_f[df_f["decision_macro"] == sel]
    with fc3:
        q = st.text_input("Buscar")
        if q:
            df_f = df_f[df_f.apply(lambda r: q.lower() in str(r).lower(), axis=1)]

    st.caption(f"{len(df_f)} sentencias")
    st.dataframe(df_f[cols_show], use_container_width=True, height=400)

    csv_bytes = df_f.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    c1, c2 = st.columns(2)
    with c1:
        st.download_button("Descargar CSV", data=csv_bytes,
                           file_name="analisis_filtrado.csv", mime="text/csv")
    with c2:
        try:
            import io
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine="openpyxl") as w:
                df_f.to_excel(w, index=False, sheet_name="Sentencias")
            st.download_button("Descargar Excel", data=buf.getvalue(),
                               file_name="analisis_filtrado.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        except Exception:
            pass


def ui_mod4():
    """Análisis individual."""
    st.subheader("Análisis individual")
    if not os.getenv("OPENAI_API_KEY"):
        st.error("Sin API key.")
        return

    idx_modelo = MODELOS.index(st.session_state.get("modelo_global", MODELOS[0])) \
                 if st.session_state.get("modelo_global") in MODELOS else 0
    model_name = st.selectbox("Modelo", MODELOS, index=idx_modelo, key="m4_model")

    uploaded = st.file_uploader("Subir sentencia (.txt, .pdf, .doc, .docx)",
                                type=["txt","pdf","doc","docx"])
    texto = st.text_area("O pegar texto aquí", height=180,
                         placeholder="Pega el texto completo de la sentencia...")

    if st.button("Analizar", type="primary"):
        text_to_analyze = ""
        if uploaded:
            if uploaded.name.endswith(".txt"):
                text_to_analyze = uploaded.read().decode("utf-8", errors="replace")
            else:
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded.name).suffix) as tmp:
                    tmp.write(uploaded.getbuffer())
                    tmp_path = Path(tmp.name)
                try:
                    from utils.extract_text import extract_text_from_path
                    text_to_analyze = extract_text_from_path(tmp_path)
                except Exception:
                    st.error("Módulo de extracción no disponible. Sube el archivo en .txt.")
                    return
                finally:
                    tmp_path.unlink(missing_ok=True)
        elif texto.strip():
            text_to_analyze = texto.strip()

        if not text_to_analyze:
            st.warning("Sube un archivo o pega texto.")
            return

        with st.spinner("Analizando..."):
            meta   = _extract_metadata(text_to_analyze, model_name)
            raw    = _analyze(text_to_analyze, model_name)
            parsed = parse_analysis(raw, radicado=meta.get("radicado", ""))

        c1, c2 = st.columns(2)
        with c1:
            for k in ["consejero_ponente","radicado","fecha","ciudad"]:
                st.write(f"**{k.replace('_',' ').title()}:** {meta.get(k,'—')}")
        with c2:
            for k in ["sala","seccion","actor","demandado"]:
                st.write(f"**{k.replace('_',' ').title()}:** {meta.get(k,'—')}")

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.info(f"**Materia:** {parsed.get('materia_principal','—')}  \n"
                    f"**Submateria:** {parsed.get('submateria','—')}")
        with c2:
            st.info(f"**Decisión:** {parsed.get('decision_macro','—')}  \n"
                    f"**Derechos:** {parsed.get('derechos_invocados','—')}")

        with st.expander("Análisis completo"):
            st.markdown(raw)

        st.download_button("Descargar TXT", data=raw,
                           file_name=f"{meta.get('radicado','analisis')}.txt",
                           mime="text/plain")


# ══ MAIN ══════════════════════════════════════════════════════════════════════

def main():
    _init_key()

    st.set_page_config(page_title="AnalisIA", page_icon="⚖️", layout="wide",
                       initial_sidebar_state="expanded")
    st.markdown(CSS, unsafe_allow_html=True)

    # ── Sidebar ──────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("## ⚖️ AnalisIA")
        st.markdown("---")

        # Directorio del proyecto
        st.markdown("### Proyecto")
        base_input = st.text_input(
            "Directorio",
            value=st.session_state.get("base_dir", ""),
            placeholder="/ruta/a/tu/carpeta",
            key="base_dir_input",
        )
        if base_input != st.session_state.get("base_dir", ""):
            st.session_state["base_dir"] = base_input

        base = get_base_dir()
        if base:
            st.success(f"✅ `{base.name}`")
            _pipeline_status(base)
        else:
            st.warning("Directorio no configurado")

        st.markdown("---")

        # API Key
        st.markdown("### API Key")
        key_actual = os.getenv("OPENAI_API_KEY", "")
        if key_actual:
            st.success(f"🔑 `...{key_actual[-6:]}`")
            if st.button("Cambiar key", key="btn_cambiar"):
                st.session_state["show_key"] = True
        else:
            st.session_state["show_key"] = True

        if st.session_state.get("show_key"):
            nueva = st.text_input("OpenAI API key", type="password",
                                  placeholder="sk-...", key="key_input")
            if st.button("Guardar", type="primary", key="btn_save_key"):
                if nueva.startswith("sk-"):
                    _save_local_key(nueva)
                    os.environ["OPENAI_API_KEY"] = nueva
                    st.session_state["show_key"] = False
                    st.rerun()
                else:
                    st.error("Debe empezar con sk-")

        st.markdown("---")

        # Modelo global
        st.markdown("### Modelo")
        st.selectbox("Modelo OpenAI", MODELOS, index=0, key="modelo_global",
                     label_visibility="collapsed")

        st.markdown("---")
        st.caption("AnalisIA v2.1 · Consejo de Estado")

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tabs = st.tabs(["📦 ZIP", "📄 Conversión", "🧠 Análisis", "📊 Dashboard", "🔍 Individual"])

    def _safe(fn):
        try:
            fn()
        except TimeoutError:
            st.error("Timeout de iCloud/OneDrive. Espera a que el archivo se descargue.")
        except Exception as e:
            st.error(f"Error: {e}")

    with tabs[0]: _safe(ui_mod0)
    with tabs[1]: _safe(ui_mod1)
    with tabs[2]: _safe(ui_mod2)
    with tabs[3]: _safe(ui_mod3)
    with tabs[4]: _safe(ui_mod4)


if __name__ == "__main__":
    main()
