import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os
import sys
import threading
import numpy as np
import cv2  # Krävs för OCR-saxen
import re
# --- 1. IMPORTS ---
# try:
#     from sahi import AutoDetectionModel
#     from sahi.predict import get_sliced_prediction
#     SAHI_AVAILABLE = True
# except ImportError:
#     SAHI_AVAILABLE = False
SAHI_AVAILABLE = False

try:
    import easyocr
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# --- FIX FÖR SÖKVÄGAR ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class DetectionApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mbiz Symbol Detection (+OCR)")
        self.root.geometry("1200x850")
        
        # --- 2. GUI Setup ---
        btn_frame = tk.Frame(root, bg="#eee", pady=10)
        btn_frame.pack(fill=tk.X)

        self.btn_load = tk.Button(btn_frame, text="Ladda Bild", command=self.load_image, font=("Arial", 12))
        self.btn_load.pack(side=tk.LEFT, padx=20)

        # self.btn_detect = tk.Button(btn_frame, text="Hitta Symboler (SAHI)", command=self.detect, state=tk.DISABLED, bg="lightblue", font=("Arial", 12))
        # self.btn_detect.pack(side=tk.LEFT, padx=20)

        # OCR LABEL (Denna saknades i din kod)
        self.lbl_ocr = tk.Label(btn_frame, text="Väntar på ritning...", bg="#fff", font=("Arial", 10, "bold"), padx=10, relief=tk.RIDGE)
        self.lbl_ocr.pack(side=tk.RIGHT, padx=20)

        self.canvas = tk.Canvas(root, bg="#333", width=900, height=600)
        self.canvas.pack(pady=20, expand=True)
        
        self.loading_text_id = self.canvas.create_text(450, 300, text="Initierar...", fill="white", font=("Arial", 20))
        self.status_label = tk.Label(root, text="Startar...", anchor="w", relief=tk.SUNKEN)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

        self.detection_model = None
        self.ocr_reader = None
        self.current_image_path = None
        self.tk_image_ref = None

        # Starta laddning av BÅDA systemen
        self.root.after(100, self.start_loading_threads)

    def start_loading_threads(self):
        # Starta trådar för SAHI och OCR
        # threading.Thread(target=self.load_model_thread, daemon=True).start()
        threading.Thread(target=self.load_ocr_thread, daemon=True).start()

    def load_ocr_thread(self):
        if OCR_AVAILABLE:
            try:
                # gpu=False för att spara minne
                self.ocr_reader = easyocr.Reader(['sv', 'en'], gpu=False) 
                print("OCR: Läsare redo!")
                self.root.after(0, lambda: self.lbl_ocr.config(text="OCR Redo"))
            except Exception as e:
                print(f"OCR Fel: {e}")

    def load_model_thread(self):
        # Säkerställ rätt filnamn
        model_path = resource_path(os.path.join("models", "best_model.pt")) 
        if not os.path.exists(model_path):
             model_path = resource_path(os.path.join("models", "best.pt"))

        if not os.path.exists(model_path):
            self.root.after(0, lambda: self.on_model_loaded(False, f"Fil saknas: {model_path}"))
            return

        try:
            if SAHI_AVAILABLE:
                self.detection_model = AutoDetectionModel.from_pretrained(
                    model_type='yolov8',
                    model_path=model_path,
                    confidence_threshold=0.80, # Justera denna vid behov
                    device="cpu" 
                )
                self.root.after(0, lambda: self.on_model_loaded(True))
            else:
                self.root.after(0, lambda: self.on_model_loaded(False, "SAHI saknas"))
        except Exception as e:
            self.root.after(0, lambda: self.on_model_loaded(False, str(e)))

    def on_model_loaded(self, success, error_msg=""):
        if success:
            self.status_label.config(text="OCR Redo")
            self.canvas.itemconfigure(self.loading_text_id, text="Klar! Ladda en ritning.")
        else:
            self.status_label.config(text="Fel vid start")
            self.canvas.itemconfigure(self.loading_text_id, text=f"FEL:\n{error_msg}", fill="red")
            messagebox.showerror("Fel", error_msg)

    def load_image(self):
        path = filedialog.askopenfilename(filetypes=[("Bilder", "*.png;*.jpg;*.jpeg;*.PNG;*.pdf"), ("Alla filer", "*.*")])
        if not path:
            return
        
        self.current_image_path = path
        self.lbl_ocr.config(text="Läser namnruta...") 
        
        try:
            pil_img = Image.open(path).convert("RGB")
            img_for_ocr = np.array(pil_img)

            pil_img.thumbnail((900, 600))
            self.tk_image_ref = ImageTk.PhotoImage(pil_img)
            self.canvas.delete("all")
            self.canvas.create_image(450, 300, image=self.tk_image_ref, anchor=tk.CENTER)
            self.status_label.config(text=f"Laddad: {os.path.basename(path)}")
            
            if self.detection_model:
                self.btn_detect.config(state=tk.NORMAL)
            
            # Starta OCR-analysen
            threading.Thread(target=self.run_ocr_thread, args=(img_for_ocr,), daemon=True).start()

        except Exception as e:
            messagebox.showerror("Bildfel", str(e))

    def run_ocr_thread(self, img_array):
        # FIX: Om OCR-läsaren inte är redo än, vänta och försök igen om 1 sekund
        if self.ocr_reader is None:
            self.root.after(1000, lambda: self.run_ocr_thread(img_array))
            self.root.after(0, lambda: self.lbl_ocr.config(text="Laddar OCR...", bg="yellow"))
            return

        try:
            # --- SAXEN: Klipp ut botten höger ---
            h, w = img_array.shape[:2]
            crop_h_start = int(h * 0.85) 
            crop_w_start = int(w * 0.70) 
            
            roi = img_array[crop_h_start:h, crop_w_start:w]

            # Läs text
            result = self.ocr_reader.readtext(roi, detail=0)
            full_text = " ".join(result)
            
            # --- SÖK EFTER RITNINGSNUMMER (Metod B) ---
            # Detta mönster letar efter: E - 632 - 1 - 0521 (med eller utan mellanslag)
            pattern = r"([A-Z])\s*-\s*([0-9A-Z]{2,5})\s*-\s*([0-9])\s*-\s*([0-9]{3,5})"
            match = re.search(pattern, full_text)
            
            display_text = ""
            bg_color = "white"

            if match:
                # Snygga till numret (ta bort mellanslag)
                clean_code = f"{match.group(1)}-{match.group(2)}-{match.group(3)}-{match.group(4)}"
                display_text = f"NR: {clean_code}"
                bg_color = "#90ee90" # Ljusgrön färg
                print(f"Hittat nummer: {clean_code}")
            else:
                display_text = "Inget nr hittat"
                bg_color = "#ffcccb" # Ljusröd färg
            
            # Uppdatera GUI
            self.root.after(0, lambda: self.lbl_ocr.config(text=display_text, bg=bg_color))

        except Exception as e:
            print(f"OCR Fel: {e}")
            self.root.after(0, lambda: self.lbl_ocr.config(text="OCR Fel", bg="red"))

    def detect(self):
        if not self.detection_model or not self.current_image_path:
            return
        self.btn_detect.config(state=tk.DISABLED)
        self.status_label.config(text="Kör Slicing...")
        self.canvas.create_text(450, 50, text="Analyserar...", fill="yellow", font=("Arial", 24), tags="status_txt")
        self.root.update()
        threading.Thread(target=self.run_sahi_thread, daemon=True).start()

    def run_sahi_thread(self):
        try:
            # SAHI Prediktion
            result = get_sliced_prediction(
                image=self.current_image_path,
                detection_model=self.detection_model,
                slice_height=640, # Ändra till 1280 om du tränat om modellen
                slice_width=640,
                overlap_height_ratio=0.2,
                overlap_width_ratio=0.2,
                verbose=1
            )
            result.export_visuals(export_dir=".", file_name="temp_result", text_size=0.5, rect_th=2)
            final_img_path = "temp_result.png"
            if os.path.exists(final_img_path):
                self.root.after(0, lambda: self.show_result(final_img_path, len(result.object_prediction_list)))
            else:
                self.root.after(0, lambda: self.show_error("Ingen bild skapades."))
        except Exception as e:
            self.root.after(0, lambda: self.show_error(str(e)))

    def show_result(self, img_path, count):
        pil_img = Image.open(img_path).convert("RGB")
        pil_img.thumbnail((900, 600))
        self.tk_image_ref = ImageTk.PhotoImage(pil_img)
        self.canvas.delete("all")
        self.canvas.create_image(450, 300, image=self.tk_image_ref, anchor=tk.CENTER)
        self.canvas.delete("status_txt")
        self.status_label.config(text=f"Klar! Hittade {count} symboler.")
        self.btn_detect.config(state=tk.NORMAL)
        messagebox.showinfo("Resultat", f"Hittade {count} symboler!")

    def show_error(self, msg):
        self.canvas.delete("status_txt")
        self.btn_detect.config(state=tk.NORMAL)
        messagebox.showerror("Fel", msg)

def main():
    root = tk.Tk()
    app = DetectionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()