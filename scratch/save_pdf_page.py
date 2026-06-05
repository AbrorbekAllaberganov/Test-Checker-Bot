import sys
from pathlib import Path
import fitz # PyMuPDF
import cv2
import numpy as np

def save_page():
    pdf_path = Path("/tmp/omr_uploads/BQACAgIAAxkBAAO7aiJZI7X4mhb0ueBHibN20fRi3AQAAjuRAAJdmBhJAXBUZkksdIc7BA.pdf")
    if not pdf_path.exists():
        print(f"File not found: {pdf_path}")
        return
        
    doc = fitz.open(pdf_path)
    print(f"Pages: {len(doc)}")
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(200/72, 200/72))
    img_data = np.frombuffer(pix.samples, dtype=np.uint8)
    if pix.n == 3:
        img = cv2.cvtColor(img_data.reshape(pix.h, pix.w, 3), cv2.COLOR_RGB2BGR)
    elif pix.n == 4:
        img = cv2.cvtColor(img_data.reshape(pix.h, pix.w, 4), cv2.COLOR_RGBA2BGR)
    else:
        img = img_data.reshape(pix.h, pix.w)
        
    print(f"Rendered image size: {img.shape}")
    cv2.imwrite("/tmp/extracted_page0.png", img)
    print("Saved /tmp/extracted_page0.png")

if __name__ == "__main__":
    save_page()
