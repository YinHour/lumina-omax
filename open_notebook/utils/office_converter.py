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

    Spreadsheets are deliberately excluded. Converting .xls/.xlsx to PDF can split
    wide experimental tables across pages and destroy the row/column structure that
    AI extraction needs.
    """
    ext = file_path.lower().split('.')[-1]
    
    if ext not in ['doc', 'docx', 'ppt', 'pptx']:
        return file_path
        
    outdir = os.path.dirname(file_path)
    logger.info(f"Converting Office file to PDF: {file_path}")
    
    try:
        cmd = get_libreoffice_command()
        subprocess.run([
            cmd, "--headless", "--invisible", "--nodefault", 
            "--convert-to", "pdf", 
            "--outdir", outdir, 
            file_path
        ], check=True, capture_output=True)
        
        # If conversion is successful, return the new file path
        new_file_path = f"{os.path.splitext(file_path)[0]}.pdf"
        if os.path.exists(new_file_path):
            logger.info(f"Successfully converted to {new_file_path}")
            return new_file_path
            
    except subprocess.CalledProcessError as e:
        logger.error(f"LibreOffice conversion failed: {e.stderr.decode()}")
    except Exception as e:
        logger.error(f"Error during office conversion: {str(e)}")
        
    # Fallback to the original path if conversion fails
    return file_path
