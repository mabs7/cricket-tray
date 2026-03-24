"""
create_icon.py
Generates a cricket ball icon:
  - macOS   → icon.icns (via iconutil)
  - Windows → icon.ico  (via Pillow)

Run this once before building the app with PyInstaller.

Usage:
    python3 create_icon.py   (Mac)
    python  create_icon.py   (Windows)
"""

import os
import sys
from PIL import Image, ImageDraw

def draw_cricket_ball(size):
    """Draw a cricket ball at the given pixel size."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = max(2, size // 16)
    # Ball body — dark red
    draw.ellipse([pad, pad, size - pad, size - pad], fill="#8B0000")

    # Lighter red highlight (top-left shine)
    shine_size = size // 3
    draw.ellipse(
        [pad + size // 8, pad + size // 8,
         pad + size // 8 + shine_size, pad + size // 8 + shine_size],
        fill="#C0392B"
    )

    # Seam — horizontal curved line
    seam_pad = size // 5
    draw.arc(
        [seam_pad, seam_pad, size - seam_pad, size - seam_pad],
        start=200, end=340,
        fill="#F5DEB3", width=max(1, size // 20)
    )
    draw.arc(
        [seam_pad, seam_pad, size - seam_pad, size - seam_pad],
        start=20, end=160,
        fill="#F5DEB3", width=max(1, size // 20)
    )

    # Seam stitch dots
    stitch_count = max(3, size // 16)
    for i in range(stitch_count):
        angle_offset = (i / stitch_count) * 120 + 210
        import math
        r = (size - seam_pad * 2) // 2
        cx = size // 2 + int(r * 0.85 * math.cos(math.radians(angle_offset)))
        cy = size // 2 + int(r * 0.85 * math.sin(math.radians(angle_offset)))
        dot = max(1, size // 32)
        draw.ellipse([cx - dot, cy - dot, cx + dot, cy + dot], fill="#F5DEB3")

    return img


def create_icns():
    """Generate icon.icns for macOS using iconutil."""
    import shutil
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    iconset_dir = "icon.iconset"
    os.makedirs(iconset_dir, exist_ok=True)

    for size in sizes:
        img = draw_cricket_ball(size)
        img.save(f"{iconset_dir}/icon_{size}x{size}.png")
        if size <= 512:
            img2x = draw_cricket_ball(size * 2)
            img2x.save(f"{iconset_dir}/icon_{size}x{size}@2x.png")

    result = os.system("iconutil -c icns icon.iconset -o icon.icns")
    if result == 0:
        print("icon.icns created successfully!")
        shutil.rmtree(iconset_dir)
        print("Cleaned up icon.iconset folder")
        print("Now run: pyinstaller --onefile --windowed --icon=icon.icns --name PakCricket main.py")
    else:
        print("❌ iconutil failed.")


def create_ico():
    """Generate icon.ico for Windows using Pillow."""
    # Windows .ico supports multiple sizes in one file
    sizes = [16, 32, 48, 64, 128, 256]
    images = [draw_cricket_ball(size) for size in sizes]

    # Save as .ico with all sizes embedded
    images[0].save(
        "icon.ico",
        format="ICO",
        sizes=[(s, s) for s in sizes],
        append_images=images[1:],
    )
    print("icon.ico created successfully!")
    print("Now run: pyinstaller --onefile --windowed --icon=icon.ico --name PakCricket main.py")


if __name__ == "__main__":
    if sys.platform == "darwin":
        create_icns()
    else:
        create_ico()