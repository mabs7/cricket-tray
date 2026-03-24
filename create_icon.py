import os
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
    """Generate icon.icns for macOS from multiple sizes."""
    # Mac requires these specific sizes in an iconset
    sizes = [16, 32, 64, 128, 256, 512, 1024]

    iconset_dir = "icon.iconset"
    os.makedirs(iconset_dir, exist_ok=True)

    for size in sizes:
        img = draw_cricket_ball(size)
        # Standard
        img.save(f"{iconset_dir}/icon_{size}x{size}.png")
        # Retina (@2x) — skip for 1024
        if size <= 512:
            img2x = draw_cricket_ball(size * 2)
            img2x.save(f"{iconset_dir}/icon_{size}x{size}@2x.png")

    # Use macOS iconutil to convert iconset → icns
    result = os.system("iconutil -c icns icon.iconset -o icon.icns")
    if result == 0:
        print("✅ icon.icns created successfully!")
    else:
        print("❌ iconutil failed. Are you on macOS?")
        return

    # Cleanup iconset folder
    import shutil
    shutil.rmtree(iconset_dir)
    print("🧹 Cleaned up icon.iconset folder")
    print("📦 Now rebuild with: pyinstaller --onefile --windowed --icon=icon.icns --name PakCricket main.py")


if __name__ == "__main__":
    create_icns()