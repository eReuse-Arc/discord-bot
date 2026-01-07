from  PIL import Image, ImageDraw, ImageFont
from pathlib import Path


CELL_SIZE = 120
GRID_SIZE = 5
LABEL_SPACE = 60
IMG_SIZE = CELL_SIZE * GRID_SIZE + LABEL_SPACE

FONT_PATH = None

def render_bingo_card(card_number: str, grid: list[list[str]]) -> Path:
    img = Image.new("RGB", (IMG_SIZE, IMG_SIZE), "white")
    draw = ImageDraw.Draw(img)

    font = ImageFont.load_default()

    for col in range(GRID_SIZE):
        x = LABEL_SPACE + col * CELL_SIZE + CELL_SIZE // 2
        draw.text((x-5, 10), chr(ord("A") + col), fill="black", font=font)

    for row in range(GRID_SIZE):
        y = LABEL_SPACE + row * CELL_SIZE + CELL_SIZE // 2
        draw.text((10, y-5), str(row + 1), fill="black", font=font)

    for row in range(CELL_SIZE):
        for col in range(CELL_SIZE):
            x1 = LABEL_SPACE + col * CELL_SIZE
            y1 = LABEL_SPACE + row * CELL_SIZE
            x2 = x1 + CELL_SIZE
            y2 = y1 + CELL_SIZE

            draw.rectangle([x1, y1, x2, y2], outline="black", width=2)

            text = grid[row][col]
            w, h = draw.textsize(text, font = font)
            draw.text(
                (x1 + (CELL_SIZE - w) / 2, y1 + (CELL_SIZE - h) / 2),
                text,
                fill="black",
                font=font
            )

    output_path = Path(f"/tmp/bingo_card_{card_number}.png")
    img.save(output_path)
    return output_path