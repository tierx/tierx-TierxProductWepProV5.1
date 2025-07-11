"""
ฟังก์ชันช่วยเหลือสำหรับการสร้าง QR code สำหรับบอท Discord Shop
ใช้ QR code จากรูปภาพที่อัปโหลดแล้ว แปลงเป็นไฟล์ที่สามารถส่งผ่าน Discord ได้
"""
import io
import discord
from PIL import Image, ImageOps
import os
from pathlib import Path

# ตำแหน่งของรูป QR code
SCRIPT_DIR = Path(__file__).parent.absolute()
QR_IMAGE_PATH = SCRIPT_DIR / "attached_assets" / "ภาพ_1747582947880.png"

async def get_qrcode_discord_file():
    """สร้างไฟล์ Discord จากรูป QR code ที่มีอยู่แล้ว
    
    Returns:
        discord.File: ไฟล์รูปภาพ QR code สำหรับส่งใน Discord
    """
    try:
        # ตรวจสอบว่ารูปภาพมีอยู่จริง
        if not os.path.exists(QR_IMAGE_PATH):
            # ใช้ QR code สำรองถ้าไม่มีรูปภาพตั้งต้น
            return create_fallback_qrcode("DUCKY SHOP\nรหัสชำระเงินตัวอย่าง\n750000฿")

        # เปิดรูปภาพด้วย PIL
        img = Image.open(QR_IMAGE_PATH)
        
        # แปลงรูปเป็น bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        
        # สร้าง Discord File
        return discord.File(img_bytes, filename="qr-payment.png")
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการสร้าง QR code: {e}")
        # ใช้ QR code สำรองถ้าเกิดข้อผิดพลาด
        return create_fallback_qrcode("DUCKY SHOP\nรหัสชำระเงินสำรอง\n750000฿")

def create_fallback_qrcode(data):
    """สร้าง QR code สำรองในกรณีที่ไม่สามารถโหลดรูปภาพได้
    
    Args:
        data (str): ข้อความที่ต้องการแสดงใน QR code
        
    Returns:
        discord.File: ไฟล์รูปภาพ QR code สำหรับส่งใน Discord
    """
    try:
        import qrcode
        
        # สร้าง QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # แปลงรูปเป็น bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        
        # สร้าง Discord File
        return discord.File(img_bytes, filename="qr-payment-backup.png")
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการสร้าง QR code สำรอง: {e}")
        # สร้างรูปภาพเปล่าเป็นตัวสำรองสุดท้าย
        img = Image.new('RGB', (200, 200), color = (73, 109, 137))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        img_bytes.seek(0)
        return discord.File(img_bytes, filename="qr-payment-error.png")