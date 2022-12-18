from PIL import Image
from glob import glob

for file in glob("masks/*/*.png"):
    print(file)
    img = Image.open(file)
    img = img.convert("L")
    img.save(file, compress_level=9)
