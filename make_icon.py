from PIL import Image, ImageDraw

SIZE = 256


def make_icon(path):
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, 248, 248], radius=52, fill=(47, 107, 176, 255))
    d.rounded_rectangle([68, 110, 188, 200], radius=22, fill=(245, 245, 245, 255))
    d.rounded_rectangle([88, 56, 168, 126], radius=22, fill=(245, 245, 245, 255),
                        outline=(245, 245, 245, 255), width=26)
    d.ellipse([116, 136, 140, 160], fill=(47, 107, 176, 255))
    d.rectangle([126, 158, 130, 188], fill=(47, 107, 176, 255))
    img.save(path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48),
                                        (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    make_icon("icon.ico")
    print("icon.ico создан")
