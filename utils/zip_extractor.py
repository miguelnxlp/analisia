# -*- coding: utf-8 -*-
import zipfile
import os
from pathlib import Path
from typing import List, Tuple
import streamlit as st


def extract_zip_files(source_dir: Path, extract_to: Path = None) -> Tuple[List[Path], List[str]]:
    """
    Extrae masivamente archivos ZIP de un directorio.
    
    Args:
        source_dir: Directorio que contiene los archivos ZIP
        extract_to: Directorio donde extraer (por defecto: source_dir/extracted)
    
    Returns:
        Tuple[List[Path], List[str]]: (archivos_extraidos, errores)
    """
    if extract_to is None:
        extract_to = source_dir / "extracted"
    
    extract_to.mkdir(exist_ok=True)
    
    extracted_files = []
    errors = []
    
    # Encontrar todos los archivos ZIP
    zip_files = list(source_dir.glob("*.zip"))
    
    if not zip_files:
        errors.append("No se encontraron archivos ZIP en el directorio")
        return extracted_files, errors
    
    st.info(f"Se encontraron {len(zip_files)} archivos ZIP para procesar")
    
    for zip_file in zip_files:
        try:
            # Crear subdirectorio para este ZIP
            zip_extract_dir = extract_to / zip_file.stem
            zip_extract_dir.mkdir(exist_ok=True)
            
            # Extraer el ZIP
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(zip_extract_dir)
            
            # Encontrar archivos extraídos (doc, docx, pdf, txt)
            extracted = []
            for ext in ['*.doc', '*.docx', '*.pdf', '*.txt']:
                extracted.extend(zip_extract_dir.rglob(ext))
            
            extracted_files.extend(extracted)
            st.success(f"✅ {zip_file.name}: {len(extracted)} archivos extraídos")
            
        except zipfile.BadZipFile:
            errors.append(f"❌ {zip_file.name}: Archivo ZIP corrupto o inválido")
        except Exception as e:
            errors.append(f"❌ {zip_file.name}: Error al extraer - {str(e)}")
    
    return extracted_files, errors


def scan_zip_directory(source_dir: Path) -> dict:
    """
    Escanea un directorio y muestra información sobre los ZIP encontrados.
    
    Args:
        source_dir: Directorio a escanear
    
    Returns:
        dict: Información sobre los ZIP encontrados
    """
    zip_files = list(source_dir.glob("*.zip"))
    
    info = {
        'total_zips': len(zip_files),
        'total_size_mb': sum(f.stat().st_size for f in zip_files) / (1024 * 1024),
        'zip_details': []
    }
    
    for zip_file in zip_files:
        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                file_count = len(zip_ref.namelist())
                size_mb = zip_file.stat().st_size / (1024 * 1024)
                
                info['zip_details'].append({
                    'name': zip_file.name,
                    'size_mb': round(size_mb, 2),
                    'file_count': file_count,
                    'status': 'OK'
                })
        except zipfile.BadZipFile:
            info['zip_details'].append({
                'name': zip_file.name,
                'size_mb': round(zip_file.stat().st_size / (1024 * 1024), 2),
                'file_count': 0,
                'status': 'Corrupto'
            })
    
    return info


def clean_extracted_directory(extract_dir: Path) -> bool:
    """
    Limpia el directorio de archivos extraídos.
    
    Args:
        extract_dir: Directorio a limpiar
    
    Returns:
        bool: True si se limpió correctamente
    """
    try:
        if extract_dir.exists():
            import shutil
            shutil.rmtree(extract_dir)
        return True
    except Exception:
        return False


def get_supported_files_from_extracted(extract_dir: Path) -> List[Path]:
    """
    Obtiene todos los archivos soportados de un directorio extraído.
    
    Args:
        extract_dir: Directorio extraído
    
    Returns:
        List[Path]: Lista de archivos soportados
    """
    supported_files = []
    
    for ext in ['*.doc', '*.docx', '*.pdf', '*.txt']:
        supported_files.extend(extract_dir.rglob(ext))
    
    return sorted(supported_files)
