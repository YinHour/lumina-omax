import logging
import os
import shutil
import subprocess
import sys
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


def _resolve_libreoffice_command() -> Tuple[str, str]:
    env_candidates = [
        (os.environ.get("SOFFICE_PATH"), "env:SOFFICE_PATH"),
        (os.environ.get("LIBREOFFICE_PATH"), "env:LIBREOFFICE_PATH"),
    ]
    for candidate, source in env_candidates:
        if candidate and os.path.exists(candidate):
            return candidate, source

    if sys.platform == "darwin":  # macOS
        mac_path = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
        if os.path.exists(mac_path):
            return mac_path, "mac-default"
        resolved = shutil.which("soffice") or shutil.which("libreoffice") or mac_path
        return resolved, "path-probe"

    if sys.platform.startswith("win"):
        windows_candidates = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
        for candidate in windows_candidates:
            if os.path.exists(candidate):
                return candidate, "windows-default"

        resolved = (
            shutil.which("soffice.exe")
            or shutil.which("soffice")
            or shutil.which("libreoffice")
            or "soffice"
        )
        return resolved, "path-probe"

    # Linux and other Unix-like systems
    resolved = shutil.which("libreoffice") or shutil.which("soffice") or "libreoffice"
    return resolved, "path-probe"


def get_libreoffice_command() -> str:
    command, _ = _resolve_libreoffice_command()
    return command


def _log_conversion_failure(file_path: str, command: str, reason: str) -> None:
    """Log an actionable failure message for office conversion.

    Keeps the fallback contract (callers receive the original path) while making
    the root cause visible in logs instead of the misleading downstream
    "Unable to determine file type" error.
    """
    logger.error(
        "Office conversion failed for %s using command %r: %s. "
        "Install LibreOffice (e.g. `brew install --cask libreoffice`) or set "
        "SOFFICE_PATH / LIBREOFFICE_PATH, then retry processing the source.",
        file_path,
        command,
        reason,
    )


def get_libreoffice_command_info() -> Dict[str, object]:
    command, source = _resolve_libreoffice_command()
    if os.path.isabs(command):
        if os.path.isfile(command):
            if os.name == "posix":
                available = os.access(command, os.X_OK)
            else:
                available = True
        else:
            available = False
    else:
        available = shutil.which(command) is not None

    return {
        "command": command,
        "source": source,
        "available": available,
    }

def convert_to_modern_office_format(file_path: str) -> str:
    """
    If the file is a document/presentation Office format (.doc, .docx, .ppt, .pptx),
    convert it to PDF using LibreOffice so engines like MinerU can process it.

    Modern spreadsheets are deliberately excluded from PDF conversion. Legacy .xls
    files are converted to .xlsx so the table structure can still be parsed by the
    Excel extraction path.
    """
    ext = file_path.lower().split('.')[-1]
    
    conversion_target = "xlsx" if ext == "xls" else "pdf"

    if ext not in ['doc', 'docx', 'ppt', 'pptx', 'xls']:
        return file_path
        
    outdir = os.path.dirname(file_path)
    logger.info(f"Converting Office file to {conversion_target.upper()}: {file_path}")
    
    try:
        cmd = get_libreoffice_command()
        if not cmd or not os.path.exists(cmd):
            _log_conversion_failure(
                file_path, cmd, "LibreOffice executable not found"
            )
            return file_path
        subprocess.run([
            cmd, "--headless", "--invisible", "--nodefault", 
            "--convert-to", conversion_target,
            "--outdir", outdir, 
            file_path
        ], check=True, capture_output=True)
        
        # If conversion is successful, return the new file path
        new_file_path = f"{os.path.splitext(file_path)[0]}.{conversion_target}"
        if os.path.exists(new_file_path):
            logger.info(f"Successfully converted to {new_file_path}")
            return new_file_path
        _log_conversion_failure(
            file_path, cmd,
            f"command exited 0 but {conversion_target} output was not created",
        )
            
    except FileNotFoundError:
        _log_conversion_failure(
            file_path, cmd, "LibreOffice executable not found"
        )
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b"").decode(errors="replace").strip()
        _log_conversion_failure(file_path, cmd, f"exit code {e.returncode}: {stderr}")
    except Exception as e:
        logger.error(f"Error during office conversion: {str(e)}")
        
    # Fallback to the original path if conversion fails
    return file_path
