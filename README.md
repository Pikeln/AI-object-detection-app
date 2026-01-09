# Schematic Analysis App
## Quick Start

- **IMPORTANT: Install CUDA-enabled PyTorch first to ensure GPU support:**

```bash
pip install torch torchvision torchaudio --index-url [https://download.pytorch.org/whl/cu121](https://download.pytorch.org/whl/cu121)

- Clone the repository: `git clone <repository-url>`
- Create a virtual environment: `python -m venv venv`
- Activate the environment:
  - Windows: `.\venv\Scripts\activate`
  - macOS/Linux: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Run the application: `streamlit run webapp.py`

## Overview
This repository contains the **User Interface and Inference Pipeline** for a Bachelor's Thesis project in Computer Engineering. The application is designed to automate the digitalization of electrical schematics/drawings.

It integrates Machine Learning models to detect electrical symbols and extract text from PDF drawings, presenting the results in a user-friendly web dashboard.

## Key Features
* **Object Detection:** Uses **YOLO** models combined with **SAHI** (Slicing Aided Hyper Inference) to detect small electrical symbols in large high-resolution drawings.
* **OCR Integration:** Extracts text attributes associated with the symbols.
* **PDF Processing:** Converts and processes engineering PDFs using `PyMuPDF`.
* **Interactive UI:** Built with **Streamlit** for easy file upload, visualization, and JSON/PDF export.

## Tech Stack
* **Language:** Python
* **UI Framework:** Streamlit
* **ML/AI:** Ultralytics YOLOv8, SAHI
* **Data Handling:** Pandas, PyMuPDF (fitz)

## Usage
1.  Upload an electrical drawing (PDF).
2.  The app runs the inference pipeline (Symbol Detection + OCR).
3.  View results directly in the browser with bounding boxes.
4.  Download the results as structured JSON data or a marked PDF.

## Model Configuration
The application comes pre-packaged with a default trained model located at `./models/best.pt`. This allows the application to run immediately without additional setup.

### Using a Custom Model
Since training and inference are separated to keep this repository lightweight, you might want to test a newly trained model from your YOLO training repository.

You can switch models in two ways:

1.  **Replace the file (Recommended for distribution):**
    Simply copy your new `best.pt` file from your training results and overwrite the file in the `models/` directory.

2.  **Point to external path (Recommended for development):**
    If you are actively training and testing, you can change the model path directly in the code to point to your training output.
    * Open `backend/detect.py`
    * Update the `MODEL_PATH` variable to point to your local training directory (e.g., `../yolo-repo/runs/detect/train/weights/best.pt`).

---
*Created by Björn Andersson & Alaa Abdulrazzaq as part of our Degree Project in Computer Engineering.*