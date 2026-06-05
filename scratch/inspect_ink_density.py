import cv2
import numpy as np

def inspect_ink():
    img = cv2.imread("scratch/extracted_page0.png", cv2.IMREAD_GRAYSCALE)
    if img is None:
        print("Image not found")
        return
        
    print(f"Image dimensions: {img.shape}")
    
    # Let's count pixels that are dark (e.g. gray < 120)
    dark_pixels = np.where(img < 120)
    num_dark = len(dark_pixels[0])
    print(f"Number of dark pixels (< 120): {num_dark}")
    
    # Let's find regions of dark pixels
    # We can cluster them or just count how many dark pixels are in each quadrant
    h, w = img.shape
    quadrants = [
        ("Top-Left", img[0:h//2, 0:w//2]),
        ("Top-Right", img[0:h//2, w//2:w]),
        ("Bottom-Left", img[h//2:h, 0:w//2]),
        ("Bottom-Right", img[h//2:h, w//2:w])
    ]
    for name, quad in quadrants:
        print(f"  {name}: {np.sum(quad < 120)} dark pixels")

if __name__ == "__main__":
    inspect_ink()
