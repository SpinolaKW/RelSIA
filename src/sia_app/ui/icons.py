"""Ícones vetoriais desenhados localmente, sem arquivos ou fontes externos."""

import customtkinter as ctk
from PIL import Image, ImageDraw


def icon(name: str, color: str = "#697C8E", size: int = 20) -> ctk.CTkImage:
    """Produz imagens antialiasadas e compatíveis com a escala do Windows."""
    scale = 4
    image = Image.new("RGBA", (24 * scale, 24 * scale))
    draw = ImageDraw.Draw(image)

    def line(points, width=1.7):
        draw.line([(round(x * scale), round(y * scale)) for x, y in points],
                  fill=color, width=round(width * scale), joint="curve")

    def box(bounds, radius=1.5):
        draw.rounded_rectangle(tuple(round(v * scale) for v in bounds),
                               radius=round(radius * scale), outline=color, width=6)

    def ellipse(bounds):
        draw.ellipse(tuple(round(v * scale) for v in bounds), outline=color, width=6)

    if name == "dashboard":
        for bounds in ((3, 3, 10, 10), (14, 3, 21, 7), (3, 14, 10, 21), (14, 11, 21, 21)):
            box(bounds, 1)
    elif name == "upload":
        line([(4, 15), (4, 20), (20, 20), (20, 15)])
        line([(12, 16), (12, 3)])
        line([(7, 8), (12, 3), (17, 8)])
    elif name == "filter":
        line([(3, 4), (21, 4), (14, 12), (14, 19), (10, 21), (10, 12), (3, 4)])
    elif name in {"report", "production", "brand"}:
        box((4, 3, 20, 21), 2)
        if name == "report":
            for y in (8, 12, 16):
                line([(8, y), (16, y)])
        else:
            line([(8, 16), (8, 13)])
            line([(12, 16), (12, 8)])
            line([(16, 16), (16, 11)])
    elif name == "building":
        box((5, 3, 19, 21), 1)
        for x in (9, 15):
            for y in (7, 11, 15):
                line([(x, y), (x, y + 1)])
        line([(10, 21), (10, 18), (14, 18), (14, 21)])
    elif name == "database":
        ellipse((3, 3, 21, 9))
        line([(3, 6), (3, 18)])
        line([(21, 6), (21, 18)])
        for y in (9, 15):
            draw.arc((3*scale, y*scale, 21*scale, (y+6)*scale), 0, 180, fill=color, width=6)
    elif name == "settings":
        for y, x in ((6, 8), (12, 16), (18, 10)):
            line([(3, y), (21, y)])
            draw.ellipse(((x-2)*scale, (y-2)*scale, (x+2)*scale, (y+2)*scale),
                         fill=color)
    elif name == "refresh":
        draw.arc((4*scale, 4*scale, 20*scale, 20*scale), 35, 310, fill=color, width=6)
        line([(20, 4), (20, 10), (14, 10)])
    elif name == "logout":
        line([(10, 4), (4, 4), (4, 20), (10, 20)])
        line([(9, 12), (21, 12)])
        line([(16, 7), (21, 12), (16, 17)])
    elif name == "info":
        ellipse((3, 3, 21, 21))
        line([(12, 11), (12, 17)])
        line([(12, 7), (12, 8)])
    elif name == "check":
        line([(5, 12), (10, 17), (20, 6)], 2)
    elif name == "money":
        box((3, 5, 21, 19), 2)
        ellipse((9, 8, 15, 16))
        line([(6, 11), (6, 13)])
        line([(18, 11), (18, 13)])
    elif name == "download":
        line([(12, 3), (12, 16)])
        line([(7, 11), (12, 16), (17, 11)])
        line([(4, 17), (4, 21), (20, 21), (20, 17)])
    elif name == "search":
        ellipse((3, 3, 16, 16))
        line([(15, 15), (21, 21)])
    elif name == "chevron_right":
        line([(9, 5), (16, 12), (9, 19)])
    elif name == "chevron_left":
        line([(15, 5), (8, 12), (15, 19)])
    elif name == "arrow":
        line([(4, 12), (20, 12)])
        line([(14, 6), (20, 12), (14, 18)])
    elif name == "close":
        line([(6, 6), (18, 18)])
        line([(18, 6), (6, 18)])
    elif name == "lock":
        box((5, 10, 19, 21), 2)
        draw.arc((8*scale, 2*scale, 16*scale, 16*scale), 180, 360, fill=color, width=6)
        line([(12, 14), (12, 17)])
    else:
        raise ValueError(f"Ícone desconhecido: {name}")

    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
