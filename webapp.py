import sys
import os
import io

# --- STOPPA PYCACHE ---
sys.dont_write_bytecode = True 

import streamlit as st
import json
import fitz  # PyMuPDF
import fitz  # PyMuPDF
from PIL import Image
Image.MAX_IMAGE_PIXELS = None  # Allow large images (drawings)
import time
import torch

# --- LÄS IN CSS FRÅN FIL ---
def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Ladda stilen (förutsätter att style.css ligger i samma mapp)
try:
    load_css("style.css")
except FileNotFoundError:
    st.error("Could not find style.css. Has it been created?")

# --- SÖKVÄGAR ---
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

try:
    from backend.detect import run_detection_process
    # Importera hjälpmoduler (hanterar om de saknas för att undvika krasch)
    try:
        from backend.rules import generera_egenkontroll
    except ImportError as e:
        print(f"Rules import failed: {e}")
        def generera_egenkontroll(obj): return {}

    try:
        from backend.ocr import kör_ocr_på_bild
    except ImportError as e:
        print(f"OCR import failed: {e}")
        def kör_ocr_på_bild(img): return f"OCR-initfel: {e}"

except ImportError as e:
    st.error(f"Could not load backend/detect.py. Error: {e}")
    st.stop()

# --- SIDKONFIGURATION ---
st.set_page_config(page_title="Drawing Analysis AI", layout="wide")


st.title(" AI Drawing Analysis & Self-Inspection")

# --- SESSION STATE ---
# --- SESSION STATE (Högst upp i filen) ---
if 'resultat_pdf' not in st.session_state:
    st.session_state.resultat_pdf = None
if 'resultat_json' not in st.session_state:
    st.session_state.resultat_json = None
if 'ocr_text' not in st.session_state:
    st.session_state.ocr_text = ""
if 'filnamn' not in st.session_state:
    st.session_state.filnamn = "resultat"
# Denna måste finnas här för att inte krascha:
if 'nuvarande_sida' not in st.session_state:
    st.session_state.nuvarande_sida = 0

# --- SIDOFÄLT: UPPLADDNING ---
with st.sidebar:
    st.header("📂 Project")
    uploaded_file = st.file_uploader("Upload Drawing (PDF/PNG)", type=["pdf", "png"])
    
    st.divider()
    
    # --- CHECK GPU STATUS ---
    gpu_available = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if gpu_available else None
    
    if gpu_available:
        st.info(f"✅ GPU: {gpu_name} present")
        # Default to GPU if available
        radio_options = ["GPU", "CPU"]
        default_idx = 0
    else:
        st.warning("⚠️ No GPU detected. Switching to CPU.")
        radio_options = ["CPU"]
        default_idx = 0

    device_choice = st.radio("Select Hardware:", radio_options, index=default_idx, horizontal=True)
    device_str = "cuda:0" if "GPU" in device_choice else "cpu"

    if uploaded_file:
        st.session_state.filnamn = os.path.splitext(uploaded_file.name)[0]
        
        # En större knapp för att vara tydlig
        if st.button("▶ Run Analysis", type="primary", use_container_width=True):
            
            with st.status("Analyzing drawing...", expanded=True) as status:
                try:
                    input_bytes = uploaded_file.read()
                    
                    # Determine file type
                    file_type = "pdf"
                    if uploaded_file.type == "image/png" or uploaded_file.name.lower().endswith(".png"):
                        file_type = "png"
                        st.info("ℹ️ Processing PNG image natively.")

                    st.write(f" Searching for symbols (YOLO) via {device_str}...")
                    
                    t0 = time.time()
                    # Pass raw bytes and file_type
                    res_pdf, res_json = run_detection_process(input_bytes, file_type, device_str)
                    t1 = time.time()
                    dt = t1 - t0
                    st.session_state.resultat_pdf = res_pdf
                    st.session_state.resultat_json = res_json
                    
                    st.write(" Matching against rules...")
                    hittade_objekt = res_json.get('objekt', [])
                    st.session_state.egenkontroll_data = generera_egenkontroll(hittade_objekt)

                    st.write(" Reading text (OCR)...")
                    st.session_state.ocr_text = kör_ocr_på_bild(input_bytes, file_type)
                    
                    status.update(label=f"Analysis complete! (Time: {dt:.2f}s)", state="complete", expanded=False)
                    st.success(f"Analysis completed in {dt:.2f} seconds ({device_str})")
                    
                except Exception as e:
                    st.error(f"An error occurred: {e}")
                    st.stop()

# --- HUVUDVY ---
# --- HUVUDVY: RESULTAT ---
if st.session_state.resultat_pdf:
    
    # Layout: 75% Ritning (Vänster) | 25% Egenkontroll (Höger)
    col_main, col_side = st.columns([3, 1], gap="medium")
    
    # --- VÄNSTER KOLUMN: RITNING ---
    with col_main:
        st.subheader(f" Drawing: {st.session_state.filnamn}")
        try:
            doc = fitz.open(stream=st.session_state.resultat_pdf, filetype="pdf")
            page = doc[0]
            pix = page.get_pixmap(dpi=150) 
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            st.image(img, use_container_width=True)
            doc.close()
        except Exception:
            st.warning("Could not display drawing.")

        # Export under bilden
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("📄 Download PDF", st.session_state.resultat_pdf, file_name=f"{st.session_state.filnamn}_analyzed.pdf", use_container_width=True)
        with c2:
            json_str = json.dumps(st.session_state.resultat_json, indent=4, ensure_ascii=False)
            st.download_button("💾 Download JSON", json_str, file_name=f"{st.session_state.filnamn}_data.json", use_container_width=True)

  
    # --- HÖGER KOLUMN: EGENKONTROLL ---
    # --- HÖGER KOLUMN: EGENKONTROLL ---
    with col_side:
        st.markdown("### Project Overview")
        
        from backend.rules import hämta_kontroll_mallar, hämta_objekt_för_sida, ALIAS
        
        objekt_lista = st.session_state.resultat_json.get('objekt', [])
        mallar = hämta_kontroll_mallar()
        
        if objekt_lista:
            # 1. SAMMANSTÄLLNING AV DETEKTERINGAR
            totalt_antal = len(objekt_lista)
            st.write(f"**Drawing Number (OCR):** {st.session_state.ocr_text}")
            st.write(f"**Total detected objects:** {totalt_antal}")
            
            # Räkna varje unik typ som hittats
            typer_funna = {}
            for obj in objekt_lista:
                typ = obj['klass'].lower()
                typer_funna[typ] = typer_funna.get(typ, 0) + 1
            
            # Visa en liten snygg lista med hittade typer
            summary_text = ""
            for typ, antal in typer_funna.items():
                summary_text += f"- {typ.capitalize()}: {antal} pcs\n"
            st.markdown(summary_text)
            
            st.divider()
            st.markdown("### Perform Self-Control")

            # 2. VAL AV KATEGORI OCH GRUPPERING
            valt_filter = st.selectbox("Select category to check:", list(mallar.keys()))
            antal_per_sida = st.select_slider("Show count per group:", options=[1, 10, 25, 50], value=10)

            # 3. HÄMTA DATA FÖR GRUPPEN
            urval, totalt_kategori = hämta_objekt_för_sida(objekt_lista, valt_filter, antal_per_sida, st.session_state.nuvarande_sida)
            max_sidor = max(0, (totalt_kategori - 1) // antal_per_sida)

            # 4. NAVIGERING
            c_prev, c_page, c_next = st.columns([1, 2, 1])
            with c_prev:
                if st.button("⬅️", disabled=st.session_state.nuvarande_sida == 0):
                    st.session_state.nuvarande_sida -= 1
                    st.rerun()
            with c_page:
                st.write(f"{st.session_state.nuvarande_sida + 1}/{max_sidor + 1}")
            with c_next:
                if st.button("➡️", disabled=st.session_state.nuvarande_sida >= max_sidor):
                    st.session_state.nuvarande_sida += 1
                    st.rerun()

            st.divider()

            # 5. BATCH-KONTROLL
            if urval:
                start_nr = (st.session_state.nuvarande_sida * antal_per_sida) + 1
                stopp_nr = start_nr + len(urval) - 1
                
                st.info(f"Check: {valt_filter} no {start_nr} to {stopp_nr}")

                with st.container(border=True):
                    all_checked = True
                    for punkt in mallar[valt_filter]['punkter']:
                        if not st.checkbox(f"{punkt}", key=f"p_batch_{st.session_state.nuvarande_sida}_{punkt}"):
                            all_checked = False

                    st.write("---")
                    
                    if st.button(f"Mark as done no {start_nr}-{stopp_nr}", type="primary", use_container_width=True):
                        if all_checked:
                            for obj in urval:
                                obj['utförd'] = True
                            st.success(f"Batch {start_nr}-{stopp_nr} is now DONE!")
                            st.rerun()
                        else:
                            st.error("All points in the list must be checked.")
            else:
                st.info(f"No {valt_filter} found on this drawing.")

            # 6. FRAMSTEGSMÄTARE FÖR KATEGORIN
            # Använd ALIAS för att matcha rätt kategori, precis som i hämta_objekt_för_sida
            utförda = 0
            for o in objekt_lista:
                kategori_namn = ALIAS.get(o['klass'].lower(), o['klass'].lower())
                if kategori_namn == valt_filter.lower() and o.get('utförd'):
                    utförda += 1
            
            st.write(f"**Progress ({valt_filter}):** {utförda} of {totalt_kategori} done")
            st.progress(utförda / totalt_kategori if totalt_kategori > 0 else 0)

        else:
            st.info("No query data available. Run analysis first.")
