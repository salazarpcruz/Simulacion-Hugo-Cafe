from PIL import Image

image_path = r"c:\Proyectos antigvty\Simulador\Layout.png"
try:
    img = Image.open(image_path)
    print("Image format:", img.format)
    print("Image size (width, height):", img.size)
except Exception as e:
    print("Error opening image:", e)
