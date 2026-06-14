
import sys
import os
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QPainter, QColor, QLinearGradient, QFont, QPen
from PyQt6.QtCore import QPointF, Qt, QRectF

def ensure_assets_dir():
    assets_dir = Path(__file__).resolve().parents[1] / "assets"
    assets_dir.mkdir(exist_ok=True)
    return str(assets_dir)

def create_sidebar_image(path):
    # 164x314 (Inno Setup WizardImageFile default/typical size, but can be larger)
    # Recommended: 164x314 or compatible ratio. Let's make it high quality.
    width, height = 164, 314
    image = QImage(width, height, QImage.Format.Format_RGB32)
    
    painter = QPainter(image)
    
    # Background: Linear Gradient (Nord Polar Night #2E3440 -> #3B4252)
    gradient = QLinearGradient(0, 0, width, height)
    gradient.setColorAt(0.0, QColor("#2E3440"))
    gradient.setColorAt(1.0, QColor("#4C566A"))
    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRect(0, 0, width, height)
    
    # Decorative elements: Frost accents
    painter.setPen(QPen(QColor("#88C0D0"), 2))
    painter.drawLine(20, height - 60, width - 20, height - 60)
    
    # Text: YDManager
    font = QFont("Segoe UI", 16, QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor("#ECEFF4"))
    
    # Draw rotated text or just simple placement
    # Let's put it at the bottom
    rect = QRectF(0, height - 100, width, 40)
    painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "YDManager")
    
    # Icon placeholder (Simple geometric shape)
    # Circle
    painter.setBrush(QColor("#5E81AC"))
    painter.setPen(Qt.PenStyle.NoPen)
    center_x, center_y = width // 2, height // 2 - 20
    painter.drawEllipse(QPointF(center_x, center_y), 40, 40)
    
    # Play triangle
    painter.setBrush(QColor("#ECEFF4"))
    triangle = [
        QPointF(center_x - 10, center_y - 15),
        QPointF(center_x - 10, center_y + 15),
        QPointF(center_x + 15, center_y),
    ]
    painter.drawPolygon(triangle)

    painter.end()
    image.save(path)
    print(f"Created sidebar image: {path}")

def create_header_image(path):
    # 55x55 (Inno Setup WizardSmallImageFile typical is 55x55 or larger width)
    # Standard: 55x55 (icon) OR usually the header image is attached to the right.
    # Actually, WizardSmallImageFile is displayed in the upper right corner. Max size 55x55.
    # Wait, modern style might support larger or it's just the logo.
    # Let's check docs: "WizardSmallImageFile... maximum size is 55x55 pixels."
    # IF we want a full header, we can't easily do it without custom ISS code.
    # BUT, "WizardImageFile" is the big one on the welcome page (164x314).
    # Let's stick to 55x55 for the small image to avoid issues, or 64x64 scaled down.
    
    width, height = 55, 55
    image = QImage(width, height, QImage.Format.Format_RGB32)
    painter = QPainter(image)
    
    # Background: Transparent or matching the header color. 
    # Inno Setup header is usually white. Let's make a icon with transparent bg look?
    # BMP doesn't support transparency well in Inno (magenta mask usually).
    # Let's make it fully colored background to match Nord Theme if possible, or just white bg.
    # Safer to make it White background because standard wizard header is white.
    painter.fillRect(0, 0, width, height, QColor("#FFFFFF"))
    
    # Draw Logo
    box_size = 45
    off = (width - box_size) / 2
    
    # Rounded Rect
    painter.setBrush(QColor("#5E81AC"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(off, off, box_size, box_size), 10, 10)
    
    # Y letter
    painter.setPen(QPen(QColor("#ECEFF4"), 3))
    font = QFont("Segoe UI", 24, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(QRectF(0, 0, width, height), Qt.AlignmentFlag.AlignCenter, "Y")

    painter.end()
    image.save(path)
    print(f"Created header image: {path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    assets = ensure_assets_dir()
    create_sidebar_image(os.path.join(assets, "installer_sidebar.bmp"))
    create_header_image(os.path.join(assets, "installer_header.bmp"))
    print("Images generated successfully.")
