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
COMPLETE_COLOUR = (100, 190,120 )

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = current + (" " if current else "") + word
        w = draw.textbbox((0,0), test, font=font)[2]

        if w <= max_width:
            current = test
        else:
            lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines

def render_bingo_card(card_number: str, grid: list[list[str]], completed_tiles: list[str], member: discord.Member | None) -> Path:
    rows = cols = 5

    TILE_SIZE = 200
    GRID_SIZE = TILE_SIZE * cols
    TILE_PADDING = 5

    SIDE_PADDING = 60
    TOP_PADDING = 40
    BOTTOM_PADDING = 40

    LABEL_SPACE = 50
    TITLE_HEIGHT = 120
    AVATAR_SIZE = 128
    AVATAR_GAP = 6
    NAME_HEIGHT = 48

    HEADER_HEIGHT = max(TITLE_HEIGHT, AVATAR_SIZE + AVATAR_GAP + NAME_HEIGHT)

    font = ImageFont.truetype(FONT_PATH, 22)
    label_font = ImageFont.truetype(FONT_PATH, LABEL_SPACE)
    title_font = ImageFont.truetype(FONT_PATH, TITLE_HEIGHT // 2)
    name_font = ImageFont.truetype(FONT_PATH, NAME_HEIGHT)

    img_w = SIDE_PADDING * 2 + 2 * LABEL_SPACE + GRID_SIZE
    img_h = TOP_PADDING + HEADER_HEIGHT + 2 * LABEL_SPACE + GRID_SIZE + BOTTOM_PADDING

    img = Image.new("RGB", (img_w, img_h), BG_COLOUR)
    draw = ImageDraw.Draw(img)


    # Title
    title = f"Bingo Card #{card_number}"
    # tw = draw.textbbox((0,0), title, font=title_font)[2]
    titlex = (img_w) // 2
    draw.text((titlex, TOP_PADDING + HEADER_HEIGHT // 2), title, fill=TEXT_COLOUR, font=title_font, anchor="mm")


    # Avatar
    if member:
        avatar_url = member.display_avatar.url
        avatar_img = Image.open(BytesIO(requests.get(avatar_url).content)).resize((AVATAR_SIZE, AVATAR_SIZE))

        img.paste(
            avatar_img,
            (SIDE_PADDING, TOP_PADDING),
            avatar_img if avatar_img.mode == "RGBA" else None
        )

        colour = member.color
        if colour.value == 0:
            name_colour = TEXT_COLOUR
        else:
            name_colour = (colour.r, colour.g, colour.b)

        name_y = TOP_PADDING + AVATAR_SIZE + AVATAR_GAP

        draw.text(
            (SIDE_PADDING + AVATAR_SIZE // 2, name_y),
            member.display_name,
            fill=name_colour,
            font=name_font,
            anchor="ma"
        )

    # grid
    grid_x = SIDE_PADDING + LABEL_SPACE
    grid_y = TOP_PADDING + HEADER_HEIGHT + LABEL_SPACE

    for col in range(cols):
        label = chr(ord("A") + col)
        x = grid_x + col * TILE_SIZE + TILE_SIZE // 2
        draw.text((x, grid_y - LABEL_SPACE // 2), label, fill=LABEL_COLOUR, font=label_font, anchor="mm")

    for row in range(rows):
        label = str(row + 1)
        y = grid_y + row * TILE_SIZE + TILE_SIZE // 2
        draw.text((grid_x - LABEL_SPACE // 2, y), label, fill=LABEL_COLOUR, font=label_font, anchor="mm")

    for row in range(rows):
        for col in range(cols):
            x1 = grid_x + col * TILE_SIZE
            y1 = grid_y + row * TILE_SIZE
            x2 = x1 + TILE_SIZE
            y2 = y1 + TILE_SIZE

            tile_id = f"{chr(ord('A') + col)}{row + 1}"

            if grid[row][col].upper() == "FREE":
                fill = FREE_COLOUR
            elif tile_id in completed_tiles:
                fill = COMPLETE_COLOUR
            else:
                fill = GRID_COLOUR

            draw.rectangle([x1, y1, x2, y2], fill=fill, outline=BORDER_COLOUR)


            lines = wrap_text(draw, grid[row][col], font, TILE_SIZE - 2 * TILE_PADDING)
            total_h = len(lines) * (font.size + 4)
            start_y = y1 + (TILE_SIZE - total_h) // 2

            for i, line in enumerate(lines):
                w = draw.textbbox((0,0), line, font=font)[2]
                draw.text(
                    (x1 + TILE_SIZE // 2, start_y + i * (font.size + 4)),
                    line,
                    fill="black",
                    font=font,
                    anchor="ma"
                )

    out = OUT_PATH / f"bingo_{card_number}.png"
    img.save(out)
    return out