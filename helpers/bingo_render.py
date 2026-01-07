from  PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from constants import IMAGE_OUTPUT_DIR
import discord
from io import BytesIO
import requests

OUT_PATH = Path(IMAGE_OUTPUT_DIR)

BG_COLOUR = (54, 57, 63)
GRID_COLOUR = (64, 68, 75)
TEXT_COLOUR = (235, 235, 235)
LABEL_COLOUR = (180, 180, 180)
BORDER_COLOUR = (90, 90, 90)
FREE_COLOUR = (240, 200, 90)
COMPLETE_COLOUR = (100, 190, 120)

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def render_bingo_card(card_number: str, grid: list[list[str]], completed_tiles: list[str], member: discord.Member | None) -> Path:
    rows, cols = 5, 5
    padding = 20
    label_space = 30
    title_space = 60
    cell_padding = 14

    font = ImageFont.truetype(FONT_PATH, 22)
    label_font = ImageFont.truetype(FONT_PATH, 20)
    title_font = ImageFont.truetype(FONT_PATH, 32)

    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    max_w = max(dummy.textbbox((0,0), text, font=font)[2] for row in grid for text in row)
    max_h = max(dummy.textbbox((0,0), text, font=font)[3] for row in grid for text in row)

    cell_w = max_w + cell_padding * 2
    cell_h = max_h + cell_padding * 2

    grid_w = cell_w * cols
    grid_h = cell_h * rows

    img_w = grid_w + padding * 2 + label_space
    img_h = grid_h + padding * 2 + title_space + label_space

    img = Image.new("RGB", (img_w, img_h), BG_COLOUR)
    draw = ImageDraw.Draw(img)

    start_x = padding + label_space
    start_y = padding + title_space + label_space

    title = f"Bingo Card #{card_number}"
    tw = draw.textbbox((0,0), title, font=title_font)[2]
    draw.text(((img_w - tw) // 2, padding // 2), title, fill=TEXT_COLOUR, font=title_font)

    if member:
        avatar_size = title_space
        avatar_url = member.display_avatar.url
        avatar_img = Image.open(BytesIO(requests.get(avatar_url).content)).resize((avatar_size, avatar_size))

        name_colour = member.color

        if name_colour.value == 0:
            name_colour = TEXT_COLOUR
        else:
            name_colour = (name_colour.r, name_colour.g, name_colour.b)

        img.paste(
            avatar_img,
            (padding, padding),
            avatar_img if avatar_img.mode == "RGBA" else None
        )

        draw.text(
            (padding + avatar_size + 15, padding + 3 * avatar_size / 4),
            member.display_name,
            fill=name_colour,
            font=label_font,
            anchor="lm"
        )


    for col in range(cols):
        label = chr(ord("A") + col)
        x = start_x + col * cell_w + cell_w // 2
        draw.text((x, start_y - label_space // 2), label, fill=LABEL_COLOUR, font=label_font, anchor="mm")

    for row in range(rows):
        label = str(row + 1)
        y = start_y + row * cell_h + cell_h // 2
        draw.text((start_x - label_space // 2, y), label, fill=LABEL_COLOUR, font=label_font, anchor="mm")

    for row in range(rows):
        for col in range(cols):
            x1 = start_x + col * cell_w
            y1 = start_y + row * cell_h
            x2 = x1 + cell_w
            y2 = y1 + cell_h

            tile_id = f"{chr(ord('A') + col)}{row + 1}"

            if grid[row][col].upper() == "FREE":
                fill = FREE_COLOUR
            elif tile_id in completed_tiles:
                fill = COMPLETE_COLOUR
            else:
                fill = GRID_COLOUR

            draw.rectangle([x1, y1, x2, y2], fill=fill, outline=BORDER_COLOUR)

            text = grid[row][col]
            tb = draw.textbbox((0, 0), text, font=font)
            tx = x1 + (cell_w - tb[2]) // 2
            ty = y1 + (cell_h - tb[3]) // 2
            draw.text(
                (tx, ty),
                text,
                fill="black",
                font=font
            )

    out = OUT_PATH / f"bingo_{card_number}.png"
    img.save(out)
    return out