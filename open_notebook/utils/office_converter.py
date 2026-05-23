import os
import sys
import logging
import subprocess

logger = logging.getLogger(__name__)

def get_libreoffice_command():
    if sys.platform == "darwin":  # macOS
        return "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    else:  # Linux (Ubuntu/Debian) etc.
        return "libreoffice"

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
