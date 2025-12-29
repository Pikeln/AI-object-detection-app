import fitz  # PyMuPDF
from PIL import Image
from pathlib import Path
from datetime import datetime
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction

# --- STATISKA INSTÄLLNINGAR ---
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "model4.0.pt"
DPI = 400
CONF_THRESHOLD = 0.75
SLICE_HEIGHT = 640
SLICE_WIDTH = 640
OVERLAP_RATIO = 0.2

# =======================================================
# == MODELLHANTERING ==
# =======================================================
GLOBAL_MODELS = {} # Cache för modeller: {"cpu": model, "cuda:0": model}

def get_model(device_str):
    """Laddar eller hämtar cachad modell för vald enhet."""
    global GLOBAL_MODELS
    
    if device_str in GLOBAL_MODELS:
        return GLOBAL_MODELS[device_str]
    
    # Ladda ny
    try:
        print(f"Laddar modell till {device_str}...")
        model = AutoDetectionModel.from_pretrained(
            model_type='ultralytics',
            model_path=str(MODEL_PATH),
            confidence_threshold=CONF_THRESHOLD,
            device=device_str
        )
        GLOBAL_MODELS[device_str] = model
        return model
    except Exception as e:
        print(f"FEL vid modelladdning ({device_str}): {e}")
        return None

# =======================================================
# == HÄLPFUNKTIONER ==
# =======================================================

def översätt_koordinater(page, x1_pix, y1_pix, x2_pix, y2_pix, dpi):
    rotation = page.rotation
    W_current = page.rect.width
    H_current = page.rect.height
    S_inv = 72.0 / dpi

    sx1 = x1_pix * S_inv
    sy1 = y1_pix * S_inv
    sx2 = x2_pix * S_inv
    sy2 = y2_pix * S_inv

    if rotation == 0:
        px1, py1 = sx1, sy1
        px2, py2 = sx2, sy2
    elif rotation == 90:
        px1, py1 = sy1, W_current - sx1
        px2, py2 = sy2, W_current - sx2
    elif rotation == 180:
        px1, py1 = W_current - sx1, H_current - sy1
        px2, py2 = W_current - sx2, H_current - sy2
    elif rotation == 270:
        px1, py1 = H_current - sy1, sx1
        px2, py2 = H_current - sy2, sx2
    else:
        px1, py1 = sx1, sy1
        px2, py2 = sx2, sy2

    return fitz.Rect(min(px1, px2), min(py1, py2), max(px1, px2), max(py1, py2))


def pdf_bytes_to_pil_image(pdf_bytes, dpi):
    """Konverterar PDF-bytes direkt till en PIL Image i RAM."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc.load_page(0)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    
    # Skapa PIL Image från minnet
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img

# =======================================================
# == HUVUDFUNKTION (Pure RAM) ==
# =======================================================

import io

def run_detection_process(input_bytes, input_type="pdf", device="cpu"):
    """
    Tar in fil-bytes och filtyp ("pdf" eller "png") samt vald enhet ("cpu" eller "cuda:0").
    Returnerar (pdf_bytes_result, json_dict_result).
    Inga filer skrivs till disk.
    """
    detection_model = get_model(device)
    
    if detection_model is None:
        raise Exception(f"Kunde inte ladda modellen på {device}.")

    pil_image = None
    doc = None

    # Load image and prepare doc for annotation based on input type
    if input_type == "png":
        # 1. Direct Load (No PDF rasterization needed)
        pil_image = Image.open(io.BytesIO(input_bytes))
        pil_image = pil_image.convert("RGB") # Always ensure RGB
        
        # Create a PDF container from the image to allow drawing vector annotations
        # This is much faster than rasterizing a PDF to an image
        pdf_bytes = io.BytesIO()
        pil_image.save(pdf_bytes, format="PDF")
        doc = fitz.open("pdf", pdf_bytes.getvalue()) 

    else:
        # 1. Convert PDF (bytes) -> Image (PIL Image in RAM) - Expensive step
        pil_image = pdf_bytes_to_pil_image(input_bytes, DPI)
        doc = fitz.open(stream=input_bytes, filetype="pdf")

    # 2. Run SAHI (SAHI takes PIL Image directly)
    result = get_sliced_prediction(
        image=pil_image,
        detection_model=detection_model,
        slice_height=SLICE_HEIGHT,
        slice_width=SLICE_WIDTH,
        overlap_height_ratio=OVERLAP_RATIO,
        overlap_width_ratio=OVERLAP_RATIO,
        verbose=0
    )

    # 3. Mark PDF (in RAM)
    page = doc.load_page(0)
    
    predictions = result.object_prediction_list
    collected_data = []

    shape = page.new_shape()
    page_w = page.rect.width
    page_h = page.rect.height
    
    # Create a simple color map for common electrical symbols (RGB values 0-1)
    # Using vibrant colors as requested: Red, Green, Blue, Orange
    
    # Translation map for class names (Model Output -> Display Name)
    NAME_TRANSLATION = {
        "uttag": "Socket",
        "socket": "Socket",
        "armatur": "Lighting",
        "armatur_fyrkant": "Square Lighting",
        "armatur_kryss_v": "Cross Lighting",
        "light": "Lighting",
        "brytare": "Switch",
        "switch": "Switch",
        "brandvarnare": "Smoke Detector",
        "smoke_detector": "Smoke Detector",
        "central": "Distribution Board",
        "distribution_board": "Distribution Board",
        "3-pol": "3-Pole Switch",
        "3_pole_switch": "3-Pole Switch"
    }

    COLOR_MAP = {
        "Socket": (0, 0, 1),        # Blue
        "Lighting": (1, 0.5, 0),    # Orange
        "Square Lighting": (0.9, 0.9, 0), # Yellow
        "Cross Lighting": (0, 0.8, 0),  # Green (Requested)
        "Switch": (0, 1, 1),        # Cyan (Changed from Green to distinguish)
        "Smoke Detector": (1, 0, 1),# Magenta
        "Distribution Board": (1, 0, 0), # Red
        "3-Pole Switch": (0.5, 0, 0.5), # Purple (Changed from Cyan)
        "default": (1, 0, 0)        # Red
    }

    # Dynamic scaling for visibility on large drawings
    # Baseline: 1000px width. If drawing is 5000px, everything should be 5x larger.
    scale_factor = max(1.0, page_w / 1000.0)
    # Extremely thin lines as requested (approximating 1-2 pixels)
    line_width = max(1.0, 0.5 * scale_factor)
    # Text size kept same as previous step
    text_size = max(8.0, 9.0 * scale_factor)

    for i, pred in enumerate(predictions):
        bbox = pred.bbox
        x1, y1, x2, y2 = bbox.minx, bbox.miny, bbox.maxx, bbox.maxy
        raw_class_name = pred.category.name
        score = pred.score.value
        
        # Translate class name to English
        class_name = NAME_TRANSLATION.get(raw_class_name.lower(), raw_class_name)
        if class_name == raw_class_name:
             class_name = class_name.replace("_", " ").title()

        pdf_rect = översätt_koordinater(page, x1, y1, x2, y2, DPI if input_type == "pdf" else 72) 
        
        rel_x1 = pdf_rect.x0 / page_w
        rel_y1 = pdf_rect.y0 / page_h
        rel_x2 = pdf_rect.x1 / page_w
        rel_y2 = pdf_rect.y1 / page_h

        obj_data = {
            "id": i + 1, "klass": class_name, "konfidens": round(score, 4),
            "absolut_pdf": {"x1": round(pdf_rect.x0, 2), "y1": round(pdf_rect.y0, 2), "x2": round(pdf_rect.x1, 2), "y2": round(pdf_rect.y1, 2)},
            "relativ_webb": {"x1": round(rel_x1, 5), "y1": round(rel_y1, 5), "x2": round(rel_x2, 5), "y2": round(rel_y2, 5)}
        }
        collected_data.append(obj_data)

        # Determine color
        color = COLOR_MAP.get(class_name, COLOR_MAP["default"])
        
        shape.draw_rect(pdf_rect)
        shape.finish(color=color, width=line_width) 
        
        text_point = fitz.Point(pdf_rect.x0, pdf_rect.y0 - (5 * scale_factor))
        shape.insert_text(text_point, class_name, fontsize=text_size, color=color)
        shape.commit()

    # shape.finish() was here before, but we moved it into the loop to support different colors per box
    
    # 4. Return data as bytes and dict
    result_pdf_bytes = doc.write() 
    doc.close()

    json_output = {
        "metadata": {"datum": datetime.now().isoformat(), "sid_bredd": page_w, "sid_höjd": page_h, "dpi_använd": DPI if input_type == "pdf" else 72, "device": device},
        "objekt": collected_data
    }

    return result_pdf_bytes, json_output
