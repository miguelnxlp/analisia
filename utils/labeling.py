import json
import os
from typing import Any


def label_from_text(text: str, model: str = "gpt-4o-mini") -> dict[str, Any]:
    """
    Generate labels for a decision based on its text using OpenAI.
    Returns JSON with keys like: categorias, temas, decisiones, partes, error.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        try:
            import streamlit as st  # type: ignore
            if hasattr(st, 'secrets'):
                secret_key = st.secrets.get("OPENAI_API_KEY")  # type: ignore[attr-defined]
                if secret_key:
                    api_key = str(secret_key)
                    os.environ["OPENAI_API_KEY"] = api_key
        except Exception as e:
            print(f"Error cargando st.secrets: {e}")
            pass
    if not api_key:
        return {"error": "OPENAI_API_KEY no configurada"}
    try:
        from openai import OpenAI
    except Exception:
        return {"error": "Libreria openai no instalada"}

    client = OpenAI(api_key=api_key)

    system_prompt = (
        "Eres un asistente jurídico. Devuelves JSON con etiquetas para sentencias. "
        "Esquema: { categorias: string[], temas: string[], decisiones: string[], partes: string[] }."
    )
    user_prompt = (
        "Etiqueta la siguiente sentencia con categorias, temas, decisiones y partes. "
        "Devuelve solo JSON. Texto:\n\n" + text[:200000]
    )
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
        data = json.loads(content)
        # normalize arrays
        def as_list(v: Any) -> list[str]:
            if v is None:
                return []
            if isinstance(v, list):
                return [str(x) for x in v]
            return [str(v)]

        return {
            "categorias": as_list(data.get("categorias")),
            "temas": as_list(data.get("temas")),
            "decisiones": as_list(data.get("decisiones")),
            "partes": as_list(data.get("partes")),
            "error": "",
        }
    except Exception as e:
        return {"error": str(e)}




