from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from django.core.files import File

def design_visitor_badge(visitor):
    """
    Generates a simple badge image with visitor name and ID.
    Replace this with real badge logic.
    """
    width, height = 400, 250
    image = Image.new('RGB', (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(image)

    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except:
        font = ImageFont.load_default()

    draw.text((20, 40), f"Name: {visitor.full_name}", font=font, fill=(0, 0, 0))
    draw.text((20, 100), f"ID: {visitor.id_number or 'N/A'}", font=font, fill=(0, 0, 0))

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    return File(buffer, name=f"badge_{visitor.id}.png")
