from pathlib import Path
import os
import csv
import tempfile
import json

import streamlit as st
from streamlit_file_browser import st_file_browser

from utils.env import load_env
from utils.extract_text import convert_file_to_txt
from utils.analysis import collect_txt_files, analyze_to_csv, analyze_sentencia_juridica, extract_metadata_ia
from utils.classify import classify_tutela, read_txt
from utils.labeling import label_from_text
from utils.zip_extractor import extract_zip_files, scan_zip_directory, clean_extracted_directory, get_supported_files_from_extracted


def ui_mod0():
    st.header("Módulo 0: Descompresión Masiva de ZIP 📦")
    
    # Opción de selección de carpeta
    selection_method = st.radio(
        "Método de selección de carpeta:",
        ["Escribir ruta manualmente", "Explorar carpetas"],
        horizontal=True,
        key="mod0_selection"
    )
    
    source_dir_str = ""
    if selection_method == "Escribir ruta manualmente":
        source_dir_str = st.text_input("Carpeta con archivos ZIP", value="", key="mod0_path")
    else:
        st.write("**Explorar carpetas:**")
        selected_path = st_file_browser(
            path=".",
            key="mod0_browser"
        )
        if selected_path:
            source_dir_str = str(selected_path)
            st.success(f"Carpeta seleccionada: {source_dir_str}")
    
    source_dir = Path(source_dir_str).expanduser() if source_dir_str else None
    
    if source_dir and source_dir.exists():
        # Escanear archivos ZIP
        zip_info = scan_zip_directory(source_dir)
        
        st.subheader("📊 Información de archivos ZIP encontrados")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total ZIPs", zip_info['total_zips'])
        with col2:
            st.metric("Tamaño total", f"{zip_info['total_size_mb']:.1f} MB")
        with col3:
            st.metric("Estado", "✅ Listo" if zip_info['total_zips'] > 0 else "❌ Sin ZIPs")
        
        if zip_info['zip_details']:
            st.subheader("📋 Detalle de archivos ZIP")
            for detail in zip_info['zip_details']:
                status_icon = "✅" if detail['status'] == 'OK' else "❌"
                st.write(f"{status_icon} **{detail['name']}** - {detail['size_mb']} MB - {detail['file_count']} archivos")
        
        col1, col2 = st.columns(2)
        with col1:
            extract_btn = st.button("🔓 Descomprimir todos los ZIPs", type="primary")
        with col2:
            clean_btn = st.button("🗑️ Limpiar archivos extraídos")
        
        # Directorio de extracción
        extract_dir = source_dir / "extracted"
        
        if extract_btn:
            with st.spinner("Descomprimiendo archivos ZIP..."):
                extracted_files, errors = extract_zip_files(source_dir, extract_dir)
                
                if extracted_files:
                    st.success(f"✅ Se extrajeron {len(extracted_files)} archivos en total")
                    
                    # Mostrar resumen por tipo de archivo
                    doc_count = len([f for f in extracted_files if f.suffix.lower() in ['.doc', '.docx']])
                    pdf_count = len([f for f in extracted_files if f.suffix.lower() == '.pdf'])
                    txt_count = len([f for f in extracted_files if f.suffix.lower() == '.txt'])
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Word", doc_count)
                    with col2:
                        st.metric("PDF", pdf_count)
                    with col3:
                        st.metric("TXT", txt_count)
                    
                    st.info(f"📁 Los archivos fueron extraídos en: {extract_dir}")
                    
                    # Botón para continuar al módulo 1 con los archivos extraídos
                    if st.button("🔄 Ir al Módulo 1 con archivos extraídos"):
                        st.session_state.mod1_extracted_dir = str(extract_dir)
                        st.rerun()
                
                if errors:
                    st.error("❌ Errores encontrados:")
                    for error in errors:
                        st.error(error)
        
        if clean_btn:
            with st.spinner("Limpiando archivos extraídos..."):
                if clean_extracted_directory(extract_dir):
                    st.success("✅ Directorio de archivos extraídos limpiado")
                else:
                    st.error("❌ Error al limpiar el directorio")
    
    elif source_dir_str:
        st.error("❌ La carpeta no existe")


def ui_mod1():
    st.header("Módulo 1: Conversión a .txt 🧾")
    
    # Verificar si hay archivos extraídos del Módulo 0
    extracted_dir = None
    if hasattr(st.session_state, 'mod1_extracted_dir'):
        extracted_dir = st.session_state.mod1_extracted_dir
        st.success(f"📁 Usando archivos extraídos de: {extracted_dir}")
    
    # Opción de selección de carpeta
    selection_method = st.radio(
        "Método de selección de carpeta:",
        ["Usar archivos extraídos", "Escribir ruta manualmente", "Explorar carpetas"] if extracted_dir else ["Escribir ruta manualmente", "Explorar carpetas"],
        horizontal=True
    )
    
    source_dir_str = ""
    if selection_method == "Usar archivos extraídos" and extracted_dir:
        source_dir_str = extracted_dir
    elif selection_method == "Escribir ruta manualmente":
        source_dir_str = st.text_input("Carpeta de origen (doc, docx, pdf, txt)", value="")
    else:
        st.write("**Explorar carpetas:**")
        selected_path = st_file_browser(
            path=".",
            key="mod1_browser"
        )
        if selected_path:
            source_dir_str = str(selected_path)
            st.success(f"Carpeta seleccionada: {source_dir_str}")
    
    col1, col2 = st.columns(2)
    with col1:
        scan_btn = st.button("Escanear origen")
    with col2:
        run_btn = st.button("Convertir a .txt")

    source_dir = Path(source_dir_str).expanduser() if source_dir_str else None

    if scan_btn and source_dir and source_dir.exists():
        # Función para recopilar archivos soportados
        def collect_input_files(source_dir: Path) -> list[Path]:
            files: list[Path] = []
            for root, _dirs, filenames in os.walk(source_dir):
                for name in filenames:
                    path = Path(root) / name
                    if path.suffix.lower() in {".txt", ".doc", ".docx", ".pdf"}:
                        files.append(path)
            return files

        files = collect_input_files(source_dir)
        st.session_state["m1_files"] = files
        st.success(f"Encontrados {len(files)} archivo(s) soportados.")
        if files:
            st.dataframe({
                "archivo": [str(p.relative_to(source_dir)) for p in files],
                "formato": [p.suffix.lower() for p in files],
            })
    elif scan_btn:
        st.error("La carpeta de origen no existe o no fue proporcionada.")

    files = st.session_state.get("m1_files", [])

    if run_btn:
        if not source_dir or not source_dir.exists():
            st.error("La carpeta de origen no existe o no fue proporcionada.")
            return
        target_dir = source_dir / "archvos .txt"
        target_dir.mkdir(parents=True, exist_ok=True)
        if not files:
            # Función para recopilar archivos soportados
            def collect_input_files(source_dir: Path) -> list[Path]:
                files: list[Path] = []
                for root, _dirs, filenames in os.walk(source_dir):
                    for name in filenames:
                        path = Path(root) / name
                        if path.suffix.lower() in {".txt", ".doc", ".docx", ".pdf"}:
                            files.append(path)
                return files

            files = collect_input_files(source_dir)
        if not files:
            st.warning("No se encontraron archivos soportados.")
            return
        progress = st.progress(0, text="Iniciando…")
        ok = 0
        rows: list[dict[str, str]] = []
        for idx, path in enumerate(files, start=1):
            try:
                out_txt = convert_file_to_txt(path, target_dir)
                ok += 1
                rows.append({"archivo_origen": str(path), "archivo_txt": str(out_txt), "estado": "OK", "mensaje": ""})
            except Exception as e:  # noqa: BLE001
                rows.append({"archivo_origen": str(path), "archivo_txt": "", "estado": "ERROR", "mensaje": str(e)})
            progress.progress(idx / len(files), text=f"Procesando {idx}/{len(files)}: {path.name}")
        progress.empty()
        log_path = target_dir / "log.csv"
        with log_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["archivo_origen", "archivo_txt", "estado", "mensaje"])
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        st.success(f"Completado: {ok}/{len(files)} convertidos. Log: {log_path}")
        st.dataframe(rows)


def ui_mod2():
    st.header("Módulo 2: Filtro de Tutela 🔎")
    
    # Opción de selección de carpeta
    selection_method = st.radio(
        "Método de selección de carpeta:",
        ["Escribir ruta manualmente", "Explorar carpetas"],
        horizontal=True,
        key="m2_selection"
    )
    
    source_dir_str = ""
    if selection_method == "Escribir ruta manualmente":
        source_dir_str = st.text_input("Carpeta con .txt", key="m2_src", value="")
    else:
        st.write("**Explorar carpetas:**")
        selected_path = st_file_browser(
            path=".",
            key="mod2_browser"
        )
        if selected_path:
            source_dir_str = str(selected_path)
            st.success(f"Carpeta seleccionada: {source_dir_str}")
    
    out_csv_str = st.text_input("CSV de salida", key="m2_csv", value="")
    col1, col2 = st.columns(2)
    with col1:
        scan_btn = st.button("Escanear .txt", key="m2_scan")
    with col2:
        run_btn = st.button("Clasificar con OpenAI", key="m2_run")

    source_dir = Path(source_dir_str).expanduser() if source_dir_str else None
    out_csv = Path(out_csv_str).expanduser() if out_csv_str else None

    if scan_btn and source_dir and source_dir.exists():
        files = collect_txt_files(source_dir)
        st.session_state["m2_files"] = files
        st.success(f"Encontrados {len(files)} archivo(s) .txt.")
        if files:
            st.dataframe({
                "archivo": [str(p.relative_to(source_dir)) for p in files],
                "tamano_bytes": [p.stat().st_size for p in files],
            })
    elif scan_btn:
        st.error("La carpeta de origen no existe o no fue proporcionada.")

    files = st.session_state.get("m2_files", [])

    if run_btn:
        if not source_dir or not source_dir.exists():
            st.error("La carpeta de origen no existe o no fue proporcionada.")
            return
        # Guardar carpeta de origen para uso en Módulo 3
        st.session_state["m2_source_dir"] = str(source_dir)
        # Si no se indicó CSV de salida, crear uno por defecto dentro de la carpeta de origen
        if not out_csv:
            default_dir = source_dir / "resultados"
            default_dir.mkdir(parents=True, exist_ok=True)
            out_csv = default_dir / "clasificacion.csv"
            st.info(f"No se indicó CSV. Se usará: {out_csv}")
        if not files:
            files = collect_txt_files(source_dir)
        if not files:
            st.warning("No hay archivos .txt para clasificar.")
            return
        # Crear contenedores para la barra de progreso y estadísticas
        progress_container = st.container()
        stats_container = st.container()
        
        with progress_container:
            progress_bar = st.progress(0, text="Iniciando clasificación...")
            status_text = st.empty()
        
        with stats_container:
            col1, col2, col3 = st.columns(3)
            with col1:
                processed_counter = st.metric("Procesados", "0")
            with col2:
                success_counter = st.metric("Exitosos", "0")
            with col3:
                error_counter = st.metric("Errores", "0")
        
        rows: list[dict[str, str]] = []
        success_count = 0
        error_count = 0
        
        for idx, path in enumerate(files, start=1):
            try:
                # Actualizar estado
                status_text.text(f"Leyendo archivo: {path.name}")
                text = read_txt(path)
                
                status_text.text(f"Clasificando con OpenAI: {path.name}")
                result = classify_tutela(text)
                
                if result.get("error"):
                    error_count += 1
                    rows.append({
                        "archivo": str(path),
                        "is_tutela_contra_providencia": "",
                        "confidence": "",
                        "reason": "",
                        "error": result.get("error", ""),
                    })
                else:
                    success_count += 1
                    rows.append({
                        "archivo": str(path),
                        "is_tutela_contra_providencia": str(result.get("is_tutela_contra_providencia")),
                        "confidence": str(result.get("confidence")),
                        "reason": result.get("reason", ""),
                        "error": "",
                    })
            except Exception as e:  # noqa: BLE001
                error_count += 1
                rows.append({
                    "archivo": str(path),
                    "is_tutela_contra_providencia": "",
                    "confidence": "",
                    "reason": "",
                    "error": str(e),
                })
            
            # Actualizar progreso y métricas
            progress = idx / len(files)
            progress_bar.progress(progress, text=f"Procesando {idx}/{len(files)}: {path.name}")
            processed_counter.metric("Procesados", str(idx))
            success_counter.metric("Exitosos", str(success_count))
            error_counter.metric("Errores", str(error_count))
        
        # Limpiar elementos de progreso
        progress_bar.empty()
        status_text.empty()
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["archivo", "is_tutela_contra_providencia", "confidence", "reason", "error"])
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        st.success(f"Clasificación completa. CSV: {out_csv}")
        st.dataframe(rows)


def ui_mod3():
    st.header("Módulo 3: Análisis Completo con IA 🧠")
    st.caption("Análisis jurídico completo + extracción de metadatos estructurados")
    
    # Usar la misma carpeta del Módulo 2 si está disponible
    m2_source = st.session_state.get("m2_source_dir", "")
    
    # Opción de selección de carpeta fuente
    st.subheader("Carpeta con archivos .txt")
    source_selection_method = st.radio(
        "Método de selección:",
        ["Escribir ruta manualmente", "Explorar carpetas"],
        horizontal=True,
        key="m3_source_selection"
    )
    
    source_dir_str = ""
    if source_selection_method == "Escribir ruta manualmente":
        source_dir_str = st.text_input("Carpeta con .txt", key="m3_src", value=m2_source)
    else:
        st.write("**Explorar carpetas:**")
        selected_path = st_file_browser(
            path=".",
            key="mod3_source_browser"
        )
        if selected_path:
            source_dir_str = str(selected_path)
            st.success(f"Carpeta seleccionada: {source_dir_str}")
    
    # CSV de clasificación del Módulo 2
    classification_csv_str = st.text_input("CSV de clasificación (Módulo 2)", key="m3_classification", value="")
    
    out_csv_str = st.text_input("CSV de salida análisis", key="m3_csv", value="")
    
    # Opción de selección de carpeta de prompts
    st.subheader("Carpeta de prompts")
    prompts_selection_method = st.radio(
        "Método de selección de prompts:",
        ["Escribir ruta manualmente", "Explorar carpetas"],
        horizontal=True,
        key="m3_prompts_selection"
    )
    
    prompts_dir_str = ""
    if prompts_selection_method == "Escribir ruta manualmente":
        prompts_dir_str = st.text_input("Carpeta de prompts", key="m3_prompts", value="prompts")
    else:
        st.write("**Explorar carpetas de prompts:**")
        selected_prompts_path = st_file_browser(
            path=".",
            key="mod3_prompts_browser"
        )
        if selected_prompts_path:
            prompts_dir_str = str(selected_prompts_path)
            st.success(f"Carpeta de prompts seleccionada: {prompts_dir_str}")
    
    model_name = st.selectbox("Modelo OpenAI", ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"], key="m3_model")
    
    # Opciones de análisis
    st.subheader("Opciones de Análisis")
    col1, col2 = st.columns(2)
    with col1:
        include_metadata = st.checkbox("Incluir extracción de metadatos con IA", value=True, key="m3_metadata")
    with col2:
        include_juridical = st.checkbox("Incluir análisis jurídico completo", value=True, key="m3_juridical")
    
    # Análisis individual
    st.subheader("Análisis Individual")
    individual_btn = st.button("Análisis individual", key="m3_individual")
    
    if individual_btn:
        st.subheader("Análisis Individual de Sentencia")
        
        # Opción 1: Subir archivo
        uploaded_file = st.file_uploader(
            "Subir archivo de sentencia (.txt, .doc, .docx, .pdf)",
            type=["txt", "doc", "docx", "pdf"],
            help="Selecciona un archivo para analizar individualmente",
            key="m3_upload"
        )
        
        # Opción 2: Pegar texto
        st.subheader("O pegar texto directamente:")
        sentencia_text = st.text_area(
            "Texto de la sentencia",
            height=200,
            placeholder="Pega aquí el texto completo de la sentencia a analizar...",
            help="Puedes copiar y pegar el texto de cualquier sentencia del Consejo de Estado",
            key="m3_text"
        )
        
        if st.button("Analizar sentencia", key="m3_analyze"):
            text_to_analyze = ""
            
            if uploaded_file:
                # Procesar archivo subido
                try:
                    if uploaded_file.name.endswith('.txt'):
                        text_to_analyze = str(uploaded_file.read(), "utf-8")
                    else:
                        # Convertir otros formatos
                        import tempfile
                        with tempfile.NamedTemporaryFile(delete=False, suffix=uploaded_file.name) as tmp_file:
                            tmp_file.write(uploaded_file.getbuffer())
                            tmp_path = Path(tmp_file.name)
                        
                        from utils.extract_text import extract_text_from_path
                        text_to_analyze = extract_text_from_path(tmp_path)
                        tmp_path.unlink()  # Limpiar archivo temporal
                except Exception as e:
                    st.error(f"Error procesando archivo: {e}")
                    return
            elif sentencia_text.strip():
                text_to_analyze = sentencia_text.strip()
            else:
                st.warning("Debes subir un archivo o pegar texto para analizar")
                return
            
            if not text_to_analyze:
                st.warning("No se pudo extraer texto para analizar")
                return
            
            # Mostrar progreso
            with st.spinner("Analizando sentencia con IA..."):
                # Extraer metadatos si está habilitado
                if include_metadata:
                    metadata = extract_metadata_ia(text_to_analyze, model=model_name)
                    if "error" not in metadata:
                        st.success("Metadatos extraídos exitosamente")
                        
                        # Mostrar metadatos en columnas
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("📋 Información General")
                            st.write(f"**Consejero Ponente:** {metadata.get('consejero_ponente', 'No consta')}")
                            st.write(f"**Radicación:** {metadata.get('radicacion', 'No consta')}")
                            st.write(f"**Fecha:** {metadata.get('fecha', 'No consta')}")
                            st.write(f"**Ciudad:** {metadata.get('ciudad', 'No consta')}")
                        
                        with col2:
                            st.subheader("🏛️ Información Judicial")
                            st.write(f"**Sala:** {metadata.get('sala', 'No consta')}")
                            st.write(f"**Sección:** {metadata.get('seccion', 'No consta')}")
                            st.write(f"**Tipo de Proceso:** {metadata.get('tipo_proceso', 'No consta')}")
                        
                        st.subheader("👥 Partes del Proceso")
                        st.write(f"**Actor:** {metadata.get('actor', 'No consta')}")
                        st.write(f"**Demandado:** {metadata.get('demandado', 'No consta')}")
                        
                        st.markdown("---")
                    else:
                        st.warning(f"Error extrayendo metadatos: {metadata['error']}")
                
                # Análisis jurídico si está habilitado
                if include_juridical:
                    resultado = analyze_sentencia_juridica(text_to_analyze, model=model_name)
                    
                    if resultado.startswith("Error:"):
                        st.error(resultado)
                    else:
                        st.success("Análisis jurídico completado")
                        st.markdown("---")
                        st.markdown("## 📖 Análisis Jurídico Completo")
                        st.markdown(resultado)
                        
                        # Opción para descargar análisis jurídico
                        st.download_button(
                            label="Descargar análisis jurídico en TXT",
                            data=resultado,
                            file_name=f"analisis_juridico_{st.session_state.get('analysis_counter', 1)}.txt",
                            mime="text/plain"
                        )
                        st.session_state["analysis_counter"] = st.session_state.get("analysis_counter", 1) + 1
    
    col1, col2 = st.columns(2)
    with col1:
        run_btn = st.button("Ejecutar análisis", key="m3_run")
    with col2:
        cache_btn = st.button("Limpiar cache", key="m3_cache")

    if cache_btn:
        cache_dir = Path(source_dir_str).expanduser() / "cache_analisis" if source_dir_str else None
        if cache_dir and cache_dir.exists():
            import shutil
            shutil.rmtree(cache_dir)
            st.success("Cache eliminado")
        else:
            st.info("No hay cache para limpiar")

    if run_btn:
        source_dir = Path(source_dir_str).expanduser() if source_dir_str else None
        classification_csv = Path(classification_csv_str).expanduser() if classification_csv_str else None
        out_csv = Path(out_csv_str).expanduser() if out_csv_str else None
        prompts_dir = Path(prompts_dir_str).expanduser() if prompts_dir_str else None
        
        if not source_dir or not source_dir.exists():
            st.error("La carpeta de origen no existe o no fue proporcionada.")
            return
        if not classification_csv or not classification_csv.exists():
            st.error("Debe indicar el CSV de clasificación del Módulo 2.")
            return
        # Si no se indicó CSV de salida, crear uno por defecto
        if not out_csv:
            default_dir = source_dir / "resultados"
            default_dir.mkdir(parents=True, exist_ok=True)
            out_csv = default_dir / "analisis_tutelas.csv"
            st.info(f"No se indicó CSV. Se usará: {out_csv}")
        if not prompts_dir or not prompts_dir.exists():
            st.error("La carpeta de prompts no existe.")
            return
        
        try:
            # Leer CSV de clasificación y filtrar solo tutelas contra providencia
            import pandas as pd
            df_classification = pd.read_csv(classification_csv)
            tutela_files = df_classification[
                df_classification['is_tutela_contra_providencia'].astype(str).str.lower().isin(['true', '1', 'sí', 'si', 'yes'])
            ]['archivo'].tolist()
            
            if not tutela_files:
                st.warning("No se encontraron sentencias clasificadas como 'Tutela contra providencia judicial'")
                return
            
            st.info(f"Se analizarán {len(tutela_files)} sentencias de tutela contra providencia")
            
            # Crear directorio de cache
            cache_dir = source_dir / "cache_analisis"
            cache_dir.mkdir(exist_ok=True)
            
            # Procesar solo los archivos filtrados
            progress = st.progress(0, text="Iniciando análisis...")
            results = []
            
            for idx, archivo_path in enumerate(tutela_files, 1):
                archivo_path = Path(archivo_path)
                if not archivo_path.exists():
                    continue
                    
                # Verificar cache
                cache_file = cache_dir / f"{archivo_path.stem}_analisis.json"
                if cache_file.exists():
                    try:
                        with cache_file.open('r', encoding='utf-8') as f:
                            content = f.read().strip()
                            if content:  # Verificar que no esté vacío
                                cached_result = json.loads(content)
                                results.append(cached_result)
                                progress.progress(idx / len(tutela_files), text=f"Usando cache: {archivo_path.name}")
                                continue
                            else:
                                # Archivo vacío, eliminarlo y procesar
                                cache_file.unlink()
                    except (json.JSONDecodeError, Exception):
                        # JSON corrupto, eliminarlo y procesar
                        cache_file.unlink()
                
                # Leer archivo
                text = read_txt(archivo_path)
                
                # Inicializar fila base
                row = {
                    "archivo": str(archivo_path),
                    "clasificacion_organo": "Consejo de Estado",
                    "tipo_tutela": "Tutela contra providencia judicial",  # Ya filtrado
                }
                
                # Extraer metadatos con IA si está habilitado
                if include_metadata:
                    metadata = extract_metadata_ia(text, model=model_name)
                    if "error" not in metadata:
                        # Asegurar que el radicado siempre esté presente (nombre del archivo)
                        metadata["radicado"] = archivo_path.stem.strip()
                        row.update({
                            "radicado": metadata["radicado"],
                            "consejero_ponente": metadata.get("consejero_ponente", "No consta"),
                            "radicacion": metadata.get("radicacion", "No consta"),
                            "actor": metadata.get("actor", "No consta"),
                            "demandado": metadata.get("demandado", "No consta"),
                            "fecha": metadata.get("fecha", "No consta"),
                            "sala": metadata.get("sala", "No consta"),
                            "seccion": metadata.get("seccion", "No consta"),
                            "ciudad": metadata.get("ciudad", "No consta"),
                            "tipo_proceso": metadata.get("tipo_proceso", "No consta"),
                        })
                    else:
                        st.warning(f"Error extrayendo metadatos para {archivo_path.name}: {metadata['error']}")
                        # Asegurar que el radicado siempre esté presente (nombre del archivo)
                        row.update({
                            "radicado": archivo_path.stem.strip(),
                            "consejero_ponente": "Error",
                            "radicacion": "Error",
                            "actor": "Error",
                            "demandado": "Error",
                            "fecha": "Error",
                            "sala": "Error",
                            "seccion": "Error",
                            "ciudad": "Error",
                            "tipo_proceso": "Error",
                        })
                else:
                    # Usar metadatos básicos si no se usa IA
                    from utils.analysis import extract_prelim_metadata
                    prelim = extract_prelim_metadata(archivo_path, text)
                    print(f"RADICADO EN APP: {prelim.get('radicado', 'NO ENCONTRADO')}")  # Debug
                    row.update(prelim)
                
                # Análisis jurídico completo si está habilitado
                if include_juridical:
                    analysis_result = analyze_sentencia_juridica(text, model=model_name)
                    row.update({
                        "analisis_completo": analysis_result,
                    "actos_cuestionados": "Ver análisis completo",
                    "hechos": "Ver análisis completo", 
                    "problemas_juridicos": "Ver análisis completo",
                    "ratio_regla": "Ver análisis completo",
                    "ratio_premisas": "Ver análisis completo",
                    "obiter": "Ver análisis completo",
                    "c590_generales": "Ver análisis completo",
                    "c590_especificos": "Ver análisis completo",
                    "decision_resuelve": "Ver análisis completo",
                    "precedente_normas": "Ver análisis completo",
                    "ordenes": "Ver análisis completo",
                    "observaciones": "Ver análisis completo",
                    "sintesis": "Ver análisis completo",
                    })
                else:
                    row.update({
                        "analisis_completo": "Análisis jurídico deshabilitado",
                        "actos_cuestionados": "No procesado",
                        "hechos": "No procesado", 
                        "problemas_juridicos": "No procesado",
                        "ratio_regla": "No procesado",
                        "ratio_premisas": "No procesado",
                        "obiter": "No procesado",
                        "c590_generales": "No procesado",
                        "c590_especificos": "No procesado",
                        "decision_resuelve": "No procesado",
                        "precedente_normas": "No procesado",
                        "ordenes": "No procesado",
                        "observaciones": "No procesado",
                        "sintesis": "No procesado",
                    })
                
                row["llm_error"] = ""
                
                # Guardar en cache
                try:
                    with cache_file.open('w', encoding='utf-8') as f:
                        json.dump(row, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    st.warning(f"Error guardando cache para {archivo_path.name}: {e}")
                
                results.append(row)
                progress.progress(idx / len(tutela_files), text=f"Analizando {idx}/{len(tutela_files)}: {archivo_path.name}")
            
            progress.empty()
            
            # Escribir CSV final
            out_csv.parent.mkdir(parents=True, exist_ok=True)
            with out_csv.open("w", newline="", encoding="utf-8") as f:
                if results:
                    # Asegurar que todas las filas tengan las mismas columnas
                    all_columns = set()
                    for row in results:
                        all_columns.update(row.keys())
                    
                    writer = csv.DictWriter(f, fieldnames=sorted(all_columns))
                    writer.writeheader()
                    for row in results:
                        writer.writerow(row)
            
            # Exportar análisis individuales en TXT
            txt_export_dir = source_dir / "analisis_individuales"
            txt_export_dir.mkdir(exist_ok=True)
            
            txt_count = 0
            for row in results:
                try:
                    # Crear nombre de archivo basado en radicado
                    radicado = row.get('radicado', 'sin_radicado')
                    txt_file = txt_export_dir / f"{radicado}_analisis.txt"
                    
                    # Usar el análisis completo en lugar de campos individuales
                    analisis_completo = row.get('analisis_completo', 'No se pudo generar análisis')
                    
                    # Crear contenido del análisis
                    content = f"""ANÁLISIS JURÍDICO COMPLETO - SENTENCIA
{'='*60}

RADICADO: {row.get('radicado', 'No consta')}
CONSEJERO PONENTE: {row.get('consejero_ponente', 'No consta')}
SALA: {row.get('sala', 'No consta')}
SECCIÓN: {row.get('seccion', 'No consta')}
FECHA: {row.get('fecha', 'No consta')}

{'='*60}

{analisis_completo}

{'='*60}
Generado automáticamente por AnalisIA
Análisis jurídico completo con prompt especializado
"""
                    
                    with txt_file.open('w', encoding='utf-8') as f:
                        f.write(content)
                    txt_count += 1
                    
                except Exception as e:
                    st.warning(f"Error exportando TXT para {row.get('radicado', 'desconocido')}: {e}")
            
            st.success(f"Análisis completo. {len(results)} sentencias procesadas.")
            st.info(f"📊 CSV: {out_csv}")
            st.info(f"📄 TXT individuales: {txt_count} archivos en {txt_export_dir}")
            st.info(f"💾 Cache: {cache_dir}")
            
        except Exception as e:  # noqa: BLE001
            st.error(f"Error: {str(e)}")
            import traceback
            st.code(traceback.format_exc())


def ui_mod4():
    st.header("Módulo 4: Etiquetado 🏷️")
    
    # Opción de selección de carpeta
    selection_method = st.radio(
        "Método de selección de carpeta:",
        ["Escribir ruta manualmente", "Explorar carpetas"],
        horizontal=True,
        key="m4_selection"
    )
    
    source_dir_str = ""
    if selection_method == "Escribir ruta manualmente":
        source_dir_str = st.text_input("Carpeta con .txt", key="m4_src", value="")
    else:
        st.write("**Explorar carpetas:**")
        selected_path = st_file_browser(
            path=".",
            key="mod4_browser"
        )
        if selected_path:
            source_dir_str = str(selected_path)
            st.success(f"Carpeta seleccionada: {source_dir_str}")
    
    out_csv_str = st.text_input("CSV de etiquetas", key="m4_csv", value="")
    run_btn = st.button("Etiquetar con OpenAI", key="m4_run")

    if run_btn:
        source_dir = Path(source_dir_str).expanduser() if source_dir_str else None
        out_csv = Path(out_csv_str).expanduser() if out_csv_str else None
        if not source_dir or not source_dir.exists():
            st.error("La carpeta de origen no existe o no fue proporcionada.")
            return
        if not out_csv:
            st.error("Debe indicar CSV de salida.")
            return
        files = collect_txt_files(source_dir)
        if not files:
            st.warning("No hay archivos .txt para etiquetar.")
            return
        progress = st.progress(0, text="Iniciando…")
        rows: list[dict[str, str]] = []
        for idx, p in enumerate(files, start=1):
            try:
                text = read_txt(p)
                res = label_from_text(text)
                rows.append({
                    "archivo": str(p),
                    "categorias": ", ".join(res.get("categorias", [])),
                    "temas": ", ".join(res.get("temas", [])),
                    "decisiones": ", ".join(res.get("decisiones", [])),
                    "partes": ", ".join(res.get("partes", [])),
                    "error": res.get("error", ""),
                })
            except Exception as e:  # noqa: BLE001
                rows.append({"archivo": str(p), "categorias": "", "temas": "", "decisiones": "", "partes": "", "error": str(e)})
            progress.progress(idx / len(files), text=f"Procesando {idx}/{len(files)}: {p.name}")
        progress.empty()
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["archivo", "categorias", "temas", "decisiones", "partes", "error"])
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        st.success(f"Etiquetado completo. CSV: {out_csv}")
        st.dataframe(rows)


def ui_mod5():
    st.header("Módulo 5: Visualización 📊")
    
    # Opción de selección de archivo CSV
    selection_method = st.radio(
        "Método de selección de archivo CSV:",
        ["Escribir ruta manualmente", "Explorar archivos"],
        horizontal=True,
        key="m6_selection"
    )
    
    csv_path_str = ""
    if selection_method == "Escribir ruta manualmente":
        csv_path_str = st.text_input("CSV para dashboard", key="m6_csv", value="")
    else:
        st.write("**Explorar archivos CSV:**")
        selected_file = st_file_browser(
            path=".",
            key="mod6_browser",
            file_extensions=[".csv"]
        )
        if selected_file:
            csv_path_str = str(selected_file)
            st.success(f"Archivo seleccionado: {csv_path_str}")
    
    if st.button("Cargar dashboard", key="m6_run"):
        csv_path = Path(csv_path_str).expanduser() if csv_path_str else None
        if not csv_path or not csv_path.exists():
            st.error("CSV no existe.")
            return
        import pandas as pd  # type: ignore

        df = pd.read_csv(csv_path)
        st.dataframe(df.head(50))
        # Gráficos básicos si columnas presentes
        if "is_tutela_contra_providencia" in df.columns:
            st.bar_chart(df["is_tutela_contra_providencia"].value_counts())
        if "categorias" in df.columns:
            # Conteo simple de top categorías
            exploded = df.assign(categorias=df["categorias"].fillna("").astype(str).str.split(", ")).explode("categorias")
            top = exploded["categorias"].value_counts().head(10)
            st.bar_chart(top)


def main():
    load_env()
    st.set_page_config(page_title="AnalisIA - App Unificada", page_icon="🧠", layout="wide")
    st.title("AnalisIA - Aplicación Unificada 🧠")
    # Cargar OPENAI_API_KEY desde backend: .env (utils/env) y/o .streamlit/secrets.toml
    if not os.getenv("OPENAI_API_KEY"):
        try:
            # st.secrets requiere que exista .streamlit/secrets.toml
            secret_key = st.secrets.get("OPENAI_API_KEY")  # type: ignore[attr-defined]
            if secret_key:
                os.environ["OPENAI_API_KEY"] = str(secret_key)
        except Exception:
            pass

    with st.sidebar:
        st.subheader("Configuración")
        if os.getenv("OPENAI_API_KEY"):
            st.caption("OPENAI_API_KEY cargada desde backend (.env o secrets).")
        else:
            st.warning("No se encontró OPENAI_API_KEY. Configure .env o .streamlit/secrets.toml")
    tabs = st.tabs(["0) Descompresión ZIP", "1) Conversión", "2) Filtro", "3) Análisis Completo", "4) Etiquetado", "5) Dashboard"])
    with tabs[0]:
        ui_mod0()
    with tabs[1]:
        ui_mod1()
    with tabs[2]:
        ui_mod2()
    with tabs[3]:
        ui_mod3()
    with tabs[4]:
        ui_mod4()
    with tabs[5]:
        ui_mod5()


if __name__ == "__main__":
    main()


