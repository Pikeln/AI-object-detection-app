import fitz  # PyMuPDF
from PIL import Image
import numpy as np
import re
import io
import sys

# Lazy loading to avoid heavy startup if not used
_SEARCH_READER = None

def init_ocr():
    global _SEARCH_READER
    if _SEARCH_READER is None:
        try:
            import easyocr
            # We use CPU to assume compatibility, can be changed to gpu=True if CUDA available
            _SEARCH_READER = easyocr.Reader(['sv', 'en'], gpu=False)
            print("OCR: Reader initierad.")
        except ImportError:
            print("OCR: easyocr saknas.")
            _SEARCH_READER = False
        except Exception as e:
            print(f"OCR: Fel vid init: {e}")
            _SEARCH_READER = False
    return _SEARCH_READER

def pdf_bytes_to_numpy_image(pdf_bytes, dpi=200):
    """
    Konverterar första sidan av PDF-bytes till en numpy-array (bild) för OCR.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0)
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        
        # Konvertera direkt till numpy array via PIL för enklare hantering
        img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img_array = np.array(img_pil)
        
        doc.close()
        return img_array
    except Exception as e:
        print(f"OCR Bildkonvertering fel: {e}")
        return None

def kör_ocr_på_bild(input_bytes, input_type="pdf"):
    """
    Huvudfunktion som anropas från webapp.py.
    Tar in filer (bytes), klipper ut namnrutan och returnerar hittat nummer.
    """
    reader = init_ocr()
    if not reader:
        return "OCR not available."

    img_array = None
    if input_type == "png":
         try:
            pil_image = Image.open(io.BytesIO(input_bytes))
            # Force RGB to avoid 2D arrays for grayscale or 4D for RGBA
            pil_image = pil_image.convert("RGB")
            img_array = np.array(pil_image)
         except Exception as e:
            print(f"OCR Image load error: {e}")
            img_array = None
    else:
        img_array = pdf_bytes_to_numpy_image(input_bytes)
        
    if img_array is None:
        return "Could not read image."

    try:
        # --- SAXEN: Klipp ut botten höger (Samma logik som ocrMain.py) ---
        h, w = img_array.shape[:2]
        crop_h_start = int(h * 0.85) 
        crop_w_start = int(w * 0.70) 
        
        roi = img_array[crop_h_start:h, crop_w_start:w]

        # Läs text
        result = reader.readtext(roi, detail=0)
        full_text = " ".join(result)
        
        # --- SÖK EFTER RITNINGSNUMMER ---
        # Mönster: E - 632 - 1 - 0521
        pattern = r"([A-Z])\s*-\s*([0-9A-Z]{2,5})\s*-\s*([0-9])\s*-\s*([0-9]{3,5})"
        match = re.search(pattern, full_text)
        
        if match:
            clean_code = f"{match.group(1)}-{match.group(2)}-{match.group(3)}-{match.group(4)}"
            return f"NO: {clean_code}"
        else:
            return "No No. found"
            
    except Exception as e:
        return f"OCR Error: {str(e)}"
