import os
import shutil
import subprocess
import tempfile
from pathlib import Path
def _is_executable(file_path: Path) -> bool:
    return file_path.exists() and file_path.is_file() and os.access(file_path, os.X_OK)


def _resolve_soffice_path() -> str | None:
    """
    Resolve the soffice binary path with the following precedence:
    1) SOFFICE_PATH env var (must point to executable)
    2) LIBREOFFICE_PATH env var (can be soffice or app dir)
    3) Local virtualenv binaries: .venv/bin/soffice or venv/bin/soffice (relative to this file)
    4) System PATH via shutil.which
    5) macOS default app bundle path
    """
    # 1) Explicit env var
    env_soffice = os.getenv("SOFFICE_PATH")
    if env_soffice:
        candidate = Path(env_soffice).expanduser()
        if _is_executable(candidate):
            return str(candidate)

    # 2) LibreOffice path env var: can be a dir (.app) or the binary
    env_lo = os.getenv("LIBREOFFICE_PATH")
    if env_lo:
        candidate = Path(env_lo).expanduser()
        if candidate.suffix == ".app":
            inside = candidate / "Contents" / "MacOS" / "soffice"
            if _is_executable(inside):
                return str(inside)
        elif _is_executable(candidate):
            return str(candidate)

    # 3) Local virtualenvs near this file
    base = Path(__file__).resolve().parent.parent  # project root (one up from utils)
    for venv_dir_name in (".venv", "venv"):
        venv_candidate = base / venv_dir_name / "bin" / "soffice"
        if _is_executable(venv_candidate):
            return str(venv_candidate)

    # 4) System PATH
    system_soffice = shutil.which("soffice")
    if system_soffice:
        return system_soffice

    # 5) macOS default install path
    mac_bundle = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    if _is_executable(mac_bundle):
        return str(mac_bundle)

    return None



def _read_txt_file(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _write_txt_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(content)


def extract_docx(path: Path) -> str:
    from docx import Document  # type: ignore

    document = Document(str(path))
    return "\n".join(p.text.strip() for p in document.paragraphs if p.text.strip())


def extract_pdf(path: Path) -> str:
    import PyPDF2  # type: ignore

    text_chunks: list[str] = []
    with path.open("rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text_chunks.append(page_text)
    return "\n".join(text_chunks)


def extract_doc_with_soffice(path: Path) -> str:
    """
    Attempt to convert legacy .doc to .txt using LibreOffice (soffice) in headless mode.
    Returns extracted text, or raises if soffice is unavailable/fails.
    """
    soffice_path = _resolve_soffice_path()
    if soffice_path is None:
        venv_bin = Path(__file__).resolve().parents[1] / ".venv" / "bin"
        raise RuntimeError(
            "No se encontró 'soffice'. Puedes enlazarlo dentro del .venv para aislarlo.\n"
            "Opciones (macOS):\n"
            "1) Instalar LibreOffice: brew install --cask libreoffice\n"
            f"2) Crear enlace en .venv: mkdir -p '{venv_bin}' && ln -s '/Applications/LibreOffice.app/Contents/MacOS/soffice' '{venv_bin / 'soffice'}'\n"
            "3) O exportar ruta: export SOFFICE_PATH='/Applications/LibreOffice.app/Contents/MacOS/soffice'\n"
            "También puedes usar /opt/homebrew/bin o /usr/local/bin según tu arquitectura."
        )
    with tempfile.TemporaryDirectory() as tmpdir:
        out_dir = Path(tmpdir)
        cmd = [
            soffice_path,
            "--headless",
            "--convert-to",
            "txt:Text",
            str(path),
            "--outdir",
            str(out_dir),
        ]
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0:
            stderr = proc.stderr.decode(errors="ignore")
            raise RuntimeError(f"soffice fallo con codigo {proc.returncode}: {stderr}")
        converted = out_dir / (path.stem + ".txt")
        if not converted.exists():
            raise RuntimeError("No se encontró el archivo convertido .txt tras ejecutar soffice.")
        return _read_txt_file(converted)


def extract_text_from_path(file_path: Path) -> str:
    """
    Extract text from .txt, .docx, .pdf, and .doc (via soffice) files.
    """
    suffix = file_path.suffix.lower()
    if suffix == ".txt":
        return _read_txt_file(file_path)
    if suffix == ".docx":
        return extract_docx(file_path)
    if suffix == ".pdf":
        return extract_pdf(file_path)
    if suffix == ".doc":
        return extract_doc_with_soffice(file_path)
    raise ValueError(f"Formato no soportado: {suffix}")


def convert_file_to_txt(file_path: Path, target_dir: Path) -> Path:
    """
    Convert a supported file to .txt and save it in target_dir. Returns the new path.
    """
    text = extract_text_from_path(file_path)
    output_path = target_dir / f"{file_path.stem}.txt"
    _write_txt_file(output_path, text)
    return output_path


