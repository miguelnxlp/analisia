#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
from pathlib import Path

def generate_txt_from_json(json_file_path: str, output_dir: str = None):
    """
    Genera archivo .txt individual desde un archivo JSON de análisis
    """
    json_path = Path(json_file_path)
    
    if not json_path.exists():
        print(f"❌ Archivo JSON no encontrado: {json_path}")
        return
    
    # Determinar directorio de salida
    if output_dir is None:
        output_dir = json_path.parent / "analisis_individuales"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(exist_ok=True)
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extraer información clave
        radicado = data.get('radicado', json_path.stem.replace('_analisis', ''))
        consejero = data.get('consejero_ponente', 'No consta')
        sala = data.get('sala', 'No consta')
        seccion = data.get('seccion', 'No consta')
        fecha = data.get('fecha', 'No consta')
        analisis_completo = data.get('analisis_completo', 'No se pudo generar análisis')
        
        # Crear contenido del archivo .txt
        content = f"""ANÁLISIS JURÍDICO COMPLETO - SENTENCIA
{'='*60}

RADICADO: {radicado}
CONSEJERO PONENTE: {consejero}
SALA: {sala}
SECCIÓN: {seccion}
FECHA: {fecha}

{'='*60}

{analisis_completo}

{'='*60}
Generado automáticamente por AnalisIA
Análisis jurídico completo con prompt especializado
"""
        
        # Guardar archivo .txt
        txt_filename = f"{radicado}_analisis.txt"
        txt_path = output_dir / txt_filename
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ Archivo generado: {txt_path}")
        
    except json.JSONDecodeError as e:
        print(f"❌ Error leyendo JSON: {e}")
    except Exception as e:
        print(f"❌ Error generando .txt: {e}")

def process_all_json_in_directory(directory: str):
    """
    Procesa todos los archivos JSON en un directorio
    """
    dir_path = Path(directory)
    
    if not dir_path.exists():
        print(f"❌ Directorio no encontrado: {directory}")
        return
    
    json_files = list(dir_path.glob("*_analisis.json"))
    
    if not json_files:
        print(f"❌ No se encontraron archivos *_analisis.json en: {directory}")
        return
    
    print(f"📁 Procesando {len(json_files)} archivos JSON...")
    
    for json_file in json_files:
        generate_txt_from_json(json_file)
    
    print(f"✅ Proceso completado. Revisa la carpeta 'analisis_individuales'")

if __name__ == "__main__":
    # Ejemplo de uso
    import sys
    
    if len(sys.argv) > 1:
        directory = sys.argv[1]
        process_all_json_in_directory(directory)
    else:
        print("Uso: python generate_txt_from_json.py <directorio_con_json>")
        print("Ejemplo: python generate_txt_from_json.py ./cache_analisis")
