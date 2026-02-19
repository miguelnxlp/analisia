import json
import os
from pathlib import Path
from typing import Any


def classify_tutela(
    text: str,
    model: str = "gpt-4o-mini",
) -> dict[str, Any]:
    """
    Classify whether the decision is a "Tutela contra providencia judicial".

    Returns a dict with keys:
    - is_tutela_contra_providencia: bool | None
    - confidence: float | None (0..1)
    - reason: str
    - error: str (if any)
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # Intento de cargar desde st.secrets si estamos bajo Streamlit
        try:
            import streamlit as st  # type: ignore
            # Verificar si st.secrets está disponible
            if hasattr(st, 'secrets'):
                secret_key = st.secrets.get("OPENAI_API_KEY")  # type: ignore[attr-defined]
                if secret_key:
                    api_key = str(secret_key)
                    os.environ["OPENAI_API_KEY"] = api_key
        except Exception as e:
            # Debug: imprimir el error para diagnóstico
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
        "Eres un asistente jurídico. Devuelves JSON estrictamente con el siguiente esquema: "
        "{ is_tutela_contra_providencia: boolean, confidence: number, reason: string }."
        " La confianza es un número entre 0 y 1."
    )
    user_prompt = (
        "¿La siguiente sentencia es una Tutela contra providencia judicial? "
        "Responde solo con JSON. Texto:\n\n" + text[:200000]
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = resp.choices[0].message.content or "{}"
        parsed = json.loads(content)
        # Normalize fields
        is_tc = parsed.get("is_tutela_contra_providencia")
        confidence = parsed.get("confidence")
        reason = parsed.get("reason") or ""
        if isinstance(is_tc, str):
            is_tc = is_tc.strip().lower() in {"true", "sí", "si", "yes", "1"}
        try:
            confidence = float(confidence) if confidence is not None else None
        except Exception:
            confidence = None
        return {
            "is_tutela_contra_providencia": bool(is_tc) if is_tc is not None else None,
            "confidence": confidence,
            "reason": str(reason),
            "error": "",
        }
    except Exception as e:
        return {"error": str(e)}


def read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")




