from itertools import pairwise
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 1800, 1100
image = Image.new("RGB", (WIDTH, HEIGHT), "#f8fafc")
draw = ImageDraw.Draw(image)

font_candidates = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/SFNS.ttf",
]
font_path = next((path for path in font_candidates if Path(path).exists()), None)
font = ImageFont.truetype(font_path, 30) if font_path else ImageFont.load_default()
small = ImageFont.truetype(font_path, 24) if font_path else ImageFont.load_default()
title_font = ImageFont.truetype(font_path, 46) if font_path else ImageFont.load_default()

navy = "#172554"
blue = "#2563eb"
green = "#047857"
orange = "#c2410c"
gray = "#475569"

draw.text((70, 45), "SignalSweep architecture", fill=navy, font=title_font)
draw.text(
    (72, 105),
    "Traceable CSV quality workflow with optional authenticated Gemini orchestration",
    fill=gray,
    font=small,
)


def box(x, y, w, h, label, fill, outline=navy, text_fill="white"):
    draw.rounded_rectangle((x, y, x + w, y + h), radius=22, fill=fill, outline=outline, width=4)
    lines = label.split("\n")
    heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    total = sum(heights) + (len(lines) - 1) * 8
    cursor = y + (h - total) / 2
    for line, line_height in zip(lines, heights):
        width = draw.textbbox((0, 0), line, font=font)[2]
        draw.text((x + (w - width) / 2, cursor), line, fill=text_fill, font=font)
        cursor += line_height + 8


def arrow(start, end, color=gray):
    draw.line((start, end), fill=color, width=5)
    x1, _ = start
    x2, y2 = end
    if x2 >= x1:
        points = [(x2, y2), (x2 - 18, y2 - 11), (x2 - 18, y2 + 11)]
    else:
        points = [(x2, y2), (x2 + 18, y2 - 11), (x2 + 18, y2 + 11)]
    draw.polygon(points, fill=color)


# Main workflow.
box(80, 260, 230, 115, "User\nuploads CSV", blue)
box(390, 260, 250, 115, "Streamlit\nUI", blue)
box(720, 260, 300, 115, "Local deterministic\nTaskmaster workflow", green)
box(1100, 190, 270, 115, "Findings +\nnormalized copy", green)
box(1100, 355, 270, 115, "Human review\ngate", orange)
arrow((310, 317), (390, 317), blue)
arrow((640, 317), (720, 317), blue)
arrow((1020, 297), (1100, 247), green)
arrow((1020, 337), (1100, 412), orange)

# Local tool chain.
draw.text((80, 505), "Deterministic Python tools", fill=navy, font=font)
tool_x = [80, 360, 640, 920, 1200, 1480]
tool_labels = [
    "Profile",
    "Quality\nchecks",
    "Anomaly\ndetection",
    "Route next\naction",
    "Export +\nreport",
    "Append-only\ntrace",
]
for x, label in zip(tool_x, tool_labels):
    box(x, 570, 220, 105, label, "#0f766e", outline="#115e59")
for left, right in pairwise(tool_x):
    arrow((left + 220, 622), (right, 622), "#0f766e")

# Optional cloud path.
draw.rounded_rectangle((70, 760, 1730, 995), radius=28, fill="#eff6ff", outline="#93c5fd", width=4)
draw.text((100, 790), "Optional authenticated cloud path", fill=navy, font=font)
box(120, 850, 280, 100, "Private Cloud Run\nADK agent", blue)
box(520, 850, 280, 100, "Vertex AI /\nGemini", "#7c3aed")
box(920, 850, 320, 100, "Taskmaster\nworkflow tool", green)
box(1360, 850, 260, 100, "Local result\nis source of truth", orange)
arrow((400, 900), (520, 900), blue)
arrow((800, 900), (920, 900), "#7c3aed")
arrow((1240, 900), (1360, 900), green)

draw.text(
    (100, 1015),
    "Cloud failure fallback: the local deterministic workflow still returns the result.",
    fill=gray,
    font=small,
)

image.save(ROOT / "architecture_diagram.png", optimize=True)
