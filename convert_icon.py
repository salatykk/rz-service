from PIL import Image

src = "icon.png"
dst = "icon.ico"

img = Image.open(src)
img.save(dst, format="ICO", sizes=[(16, 16), (32, 32), (48, 48),
                                   (64, 64), (128, 128), (256, 256)])
print("icon.ico создан из", src)
