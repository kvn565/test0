# -*- coding: utf-8 -*-
"""Génère assets/icone.ico (icône de l'application)."""
import os
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, 'assets')
os.makedirs(OUT_DIR, exist_ok=True)

BLEU = (13, 60, 138)
BLEU_CLAIR = (26, 63, 111)
OR = (201, 168, 76)
BLANC = (255, 255, 255)


def draw_icon(size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    radius = int(size * 0.22)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=BLEU)
    # bande inférieure plus foncée
    d.rounded_rectangle([0, int(size * 0.62), size - 1, size - 1],
                        radius=radius, fill=BLEU_CLAIR)
    # liseré or
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius,
                        outline=OR, width=max(1, int(size * 0.03)))
    # lettre "F"
    font_path = r'C:\Windows\Fonts\arialbd.ttf'
    try:
        f = ImageFont.truetype(font_path, int(size * 0.58))
    except Exception:
        f = ImageFont.load_default()
    txt = 'F'
    bbox = d.textbbox((0, 0), txt, font=f)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - w) / 2 - bbox[0]
    y = (size - h) / 2 - bbox[1]
    d.text((x, y - int(size * 0.03)), txt, font=f, fill=BLANC)
    # ligne or sous la lettre (rappel facture)
    lw = max(2, int(size * 0.10))
    ly = int(size * 0.62)
    d.rectangle([int(size * 0.22), ly + int(size * 0.02),
                 int(size * 0.78), ly + int(size * 0.02) + lw], fill=OR)
    return img


sizes = [16, 24, 32, 48, 64, 128, 256]
images = [draw_icon(s) for s in sizes]
icon_path = os.path.join(OUT_DIR, 'icone.ico')
images[-1].save(icon_path, format='ICO', sizes=[(s, s) for s in sizes])
print('Icône générée :', icon_path)
