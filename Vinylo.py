import os
import sys
import ctypes
import tkinter as tk
from tkinter import filedialog, colorchooser, messagebox

import numpy as np
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

PRESETS = {
    "Spotify (3000x3000)": 3000,
    "Apple Music (3000x3000)": 3000,
    "YouTube Music (1400x1400)": 1400,
    "Bandcamp (1400x1400)": 1400,
    "SoundCloud (1000x1000)": 1000,
    "Small / Preview (640x640)": 640,
}
FONT_FALLBACKS = ["arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf",
                  "Helvetica.ttc", "LiberationSans-Bold.ttf"]


def resource_path(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


# ---------- rendering ----------
def load_font(path, size):
    for candidate in ([path] if path else []) + FONT_FALLBACKS:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default(size)


def gradient(size, c1, c2, angle):
    a = np.deg2rad(angle)
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float32)
    xs -= size / 2
    ys -= size / 2
    span = size * (abs(np.cos(a)) + abs(np.sin(a)))
    t = np.clip((xs * np.cos(a) + ys * np.sin(a)) / span + 0.5, 0, 1)[..., None]
    c1 = np.array(Image.new("RGB", (1, 1), c1).getpixel((0, 0)), np.float32)
    c2 = np.array(Image.new("RGB", (1, 1), c2).getpixel((0, 0)), np.float32)
    return Image.fromarray((c1 * (1 - t) + c2 * t).astype(np.uint8), "RGB")


def cover_crop(img, size):
    w, h = img.size
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    return img.resize((size, size), Image.LANCZOS)


def wrap(draw, text, font, max_w):
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split():
            test = (line + " " + word).strip()
            if draw.textlength(test, font=font) <= max_w or not line:
                line = test
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def render(cfg, size):
    # background
    if cfg["image"] and os.path.exists(cfg["image"]):
        img = cover_crop(Image.open(cfg["image"]).convert("RGB"), size)
        if cfg["blur"] > 0:
            img = img.filter(ImageFilter.GaussianBlur(cfg["blur"] * size / 1000))
    else:
        img = gradient(size, cfg["c1"], cfg["c2"], cfg["angle"])
    if cfg["darken"] > 0:
        img = ImageEnhance.Brightness(img).enhance(1 - cfg["darken"] / 100)
    if cfg["grain"] > 0:
        arr = np.asarray(img).astype(np.float32)
        arr += np.random.normal(0, cfg["grain"], arr.shape[:2])[..., None]
        img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    # text
    draw = ImageDraw.Draw(img)
    margin = int(size * 0.08)
    max_w = size - 2 * margin
    tfont = load_font(cfg["font"], int(size * cfg["title_size"] / 100))
    afont = load_font(cfg["font"], int(size * cfg["artist_size"] / 100))
    t_lines = wrap(draw, cfg["title"], tfont, max_w) if cfg["title"] else []
    a_lines = wrap(draw, cfg["artist"], afont, max_w) if cfg["artist"] else []
    t_h, a_h = int(tfont.size * 1.15), int(afont.size * 1.15)
    gap = int(size * 0.02) if t_lines and a_lines else 0
    total = len(t_lines) * t_h + gap + len(a_lines) * a_h

    y = {"Top": margin, "Center": (size - total) // 2,
         "Bottom": size - margin - total}[cfg["position"]]
    items = [(l, tfont, t_h) for l in t_lines]
    items += [(l, afont, a_h) for l in a_lines]
    for i, (line, font, h) in enumerate(items):
        if i == len(t_lines) and gap:
            y += gap
        w = draw.textlength(line, font=font)
        x = {"Left": margin, "Center": (size - w) / 2,
             "Right": size - margin - w}[cfg["align"]]
        off = max(2, size // 400)
        if cfg["shadow"]:
            draw.text((x + off, y + off), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=cfg["text_color"])
        y += h
    return img


# ---------- GUI ----------
class App(ctk.CTk):
    def __init__(self):
        # Own taskbar identity so Windows shows our icon, not Python's
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "albumartmaker.app.1")
        except Exception:
            pass
        super().__init__()
        self.title("Album Art Maker")
        self.geometry("980x700")
        # CustomTkinter sets its own icon after startup, so set ours slightly later
        icon = resource_path("icon.ico")
        if os.path.exists(icon):
            self.after(250, lambda: self.iconbitmap(icon))
        ctk.set_appearance_mode("dark")
        self.cfg = dict(title="Song Title", artist="Artist Name", c1="#ff5f6d",
                        c2="#2b1055", angle=45, image="", blur=0, darken=0,
                        grain=0, title_size=11, artist_size=5, position="Bottom",
                        align="Left", font="", text_color="#ffffff", shadow=True)
        self.preview_ref = None
        self.build_ui()
        self.refresh()

    def build_ui(self):
        side = ctk.CTkScrollableFrame(self, width=330)
        side.pack(side="left", fill="y", padx=10, pady=10)
        self.preview = ctk.CTkLabel(self, text="")
        self.preview.pack(side="left", expand=True, padx=10)

        self.entry(side, "Title", "title")
        self.entry(side, "Artist", "artist")

        ctk.CTkLabel(side, text="Background", anchor="w").pack(fill="x", pady=(12, 2))
        row = ctk.CTkFrame(side, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkButton(row, text="Color 1", width=90,
                      command=lambda: self.pick("c1")).pack(side="left", padx=2)
        ctk.CTkButton(row, text="Color 2", width=90,
                      command=lambda: self.pick("c2")).pack(side="left", padx=2)
        ctk.CTkButton(row, text="Image…", width=90,
                      command=self.pick_image).pack(side="left", padx=2)
        ctk.CTkButton(side, text="Clear image", fg_color="gray30",
                      command=self.clear_image).pack(fill="x", pady=2)
        self.slider(side, "Gradient angle", "angle", 0, 360)
        self.slider(side, "Blur (image)", "blur", 0, 40)
        self.slider(side, "Darken %", "darken", 0, 90)
        self.slider(side, "Grain", "grain", 0, 40)

        ctk.CTkLabel(side, text="Text", anchor="w").pack(fill="x", pady=(12, 2))
        self.slider(side, "Title size", "title_size", 4, 25)
        self.slider(side, "Artist size", "artist_size", 2, 15)
        self.option(side, "Position", "position", ["Top", "Center", "Bottom"])
        self.option(side, "Align", "align", ["Left", "Center", "Right"])
        row = ctk.CTkFrame(side, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkButton(row, text="Text color", width=100,
                      command=lambda: self.pick("text_color")).pack(side="left", padx=2)
        ctk.CTkButton(row, text="Font (.ttf)…", width=100,
                      command=self.pick_font).pack(side="left", padx=2)
        sh = ctk.CTkCheckBox(side, text="Text shadow", command=self.toggle_shadow)
        sh.select()
        sh.pack(anchor="w", pady=4)

        ctk.CTkLabel(side, text="Export", anchor="w").pack(fill="x", pady=(12, 2))
        self.preset = ctk.CTkOptionMenu(side, values=list(PRESETS))
        self.preset.pack(fill="x", pady=2)
        self.fmt = ctk.CTkOptionMenu(side, values=["JPG", "PNG"])
        self.fmt.pack(fill="x", pady=2)
        ctk.CTkButton(side, text="Export selected size",
                      command=self.export_one).pack(fill="x", pady=2)
        ctk.CTkButton(side, text="Export ALL platforms",
                      command=self.export_all).pack(fill="x", pady=2)

    # widget helpers
    def entry(self, parent, label, key):
        ctk.CTkLabel(parent, text=label, anchor="w").pack(fill="x", pady=(6, 0))
        e = ctk.CTkEntry(parent)
        e.insert(0, self.cfg[key])
        e.pack(fill="x")
        e.bind("<KeyRelease>", lambda _: self.set(key, e.get()))

    def slider(self, parent, label, key, lo, hi):
        ctk.CTkLabel(parent, text=label, anchor="w").pack(fill="x")
        s = ctk.CTkSlider(parent, from_=lo, to=hi,
                          command=lambda v: self.set(key, float(v)))
        s.set(self.cfg[key])
        s.pack(fill="x")

    def option(self, parent, label, key, values):
        ctk.CTkLabel(parent, text=label, anchor="w").pack(fill="x")
        m = ctk.CTkOptionMenu(parent, values=values,
                              command=lambda v: self.set(key, v))
        m.set(self.cfg[key])
        m.pack(fill="x", pady=2)

    # actions
    def set(self, key, value):
        self.cfg[key] = value
        self.refresh()

    def pick(self, key):
        c = colorchooser.askcolor(color=self.cfg[key])[1]
        if c:
            self.set(key, c)

    def pick_image(self):
        p = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp")])
        if p:
            self.set("image", p)

    def clear_image(self):
        self.set("image", "")

    def pick_font(self):
        p = filedialog.askopenfilename(filetypes=[("Fonts", "*.ttf *.otf")])
        if p:
            self.set("font", p)

    def toggle_shadow(self):
        self.set("shadow", not self.cfg["shadow"])

    def refresh(self):
        img = render(self.cfg, 520)
        self.preview_ref = ctk.CTkImage(light_image=img, size=(520, 520))
        self.preview.configure(image=self.preview_ref)

    def save(self, path, size):
        img = render(self.cfg, size)
        if path.lower().endswith(".png"):
            img.save(path)
        else:
            img.save(path, quality=95, subsampling=0)

    def export_one(self):
        ext = self.fmt.get().lower()
        size = PRESETS[self.preset.get()]
        path = filedialog.asksaveasfilename(
            defaultextension=f".{ext}", initialfile=f"cover_{size}.{ext}",
            filetypes=[(ext.upper(), f"*.{ext}")])
        if path:
            self.save(path, size)
            messagebox.showinfo("Saved", f"Saved {size}x{size}\n{path}")

    def export_all(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        ext = self.fmt.get().lower()
        for name, size in PRESETS.items():
            safe = name.split(" (")[0].replace(" / ", "_").replace(" ", "_")
            self.save(os.path.join(folder, f"{safe}_{size}.{ext}"), size)
        messagebox.showinfo("Done", f"Exported {len(PRESETS)} sizes to\n{folder}")


if __name__ == "__main__":
    App().mainloop()