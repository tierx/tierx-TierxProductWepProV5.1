import http.server
import threading
import os
import socketserver
import time
import json
from pathlib import Path
import logging

# ตั้งค่า logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("render_helper")

# คงที่สำหรับไฟล์คอนฟิก
SCRIPT_DIR = Path(__file__).parent.absolute()
QRCODE_CONFIG_FILE = SCRIPT_DIR / "qrcode_config.json"
STATIC_DIR = SCRIPT_DIR / "static"
STATIC_IMAGES_DIR = STATIC_DIR / "images"

# สร้างโฟลเดอร์ static ถ้ายังไม่มี
def ensure_static_folders():
    """สร้างโฟลเดอร์ static ถ้ายังไม่มี"""
    if not STATIC_DIR.exists():
        STATIC_DIR.mkdir()
        logger.info(f"Created directory: {STATIC_DIR}")
    
    if not STATIC_IMAGES_DIR.exists():
        STATIC_IMAGES_DIR.mkdir()
        logger.info(f"Created directory: {STATIC_IMAGES_DIR}")

# ดึง QR Code URL จากไฟล์คอนฟิก
def get_qrcode_url():
    """ดึง QR Code URL จากไฟล์คอนฟิก"""
    try:
        with open(QRCODE_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config.get("url", "")
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(f"Cannot read QR code URL from {QRCODE_CONFIG_FILE}")
        return ""

def get_bot_status():
    """ตรวจสอบสถานะของบอท"""
    # ในกรณีจริง คุณอาจต้องการตรวจสอบสถานะของบอทด้วยวิธีที่เหมาะสม
    # เช่น ตรวจสอบไฟล์ล็อก หรือตรวจสอบว่าบอทกำลังทำงานอยู่หรือไม่
    return {
        "status": "online",
        "uptime": time.time(),  # เวลาที่เริ่มทำงาน
        "discord_connected": True  # สมมติว่าเชื่อมต่อกับ Discord แล้ว
    }

def start_web_server():
    """เริ่มเว็บเซิร์ฟเวอร์สำหรับ Render.com
    เพื่อให้ Render.com สามารถตรวจพบพอร์ตที่กำลังทำงาน"""
    
    # สร้างโฟลเดอร์ static ก่อน
    ensure_static_folders()
    
    class CustomHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            # เส้นทาง URL ต่างๆ
            if self.path == '/':
                # หน้าหลักแสดงสถานะบอท
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                
                qr_url = get_qrcode_url()
                qr_image_html = f'<p><img src="{qr_url}" alt="QR Payment" width="300"></p>' if qr_url else ''
                
                status = get_bot_status()
                
                html = f'''
                <html>
                <head>
                    <title>Discord Shop Bot</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5; }}
                        .container {{ max-width: 800px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                        h1 {{ color: #7289DA; }}
                        .status {{ padding: 10px; margin-top: 20px; border-radius: 4px; }}
                        .online {{ background-color: #43B581; color: white; }}
                        .offline {{ background-color: #F04747; color: white; }}
                        .qr-section {{ margin-top: 20px; text-align: center; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>Discord Shop Bot</h1>
                        <div class="status {'online' if status['discord_connected'] else 'offline'}">
                            Bot is currently {'ONLINE' if status['discord_connected'] else 'OFFLINE'}
                        </div>
                        <div class="qr-section">
                            <h2>QR Code</h2>
                            {qr_image_html}
                        </div>
                    </div>
                </body>
                </html>
                '''
                
                self.wfile.write(html.encode())
                
            elif self.path == '/status':
                # API สำหรับดึงสถานะบอท
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                status = get_bot_status()
                self.wfile.write(json.dumps(status).encode())
                
            elif self.path == '/health':
                # Health check endpoint สำหรับ Render
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
                
            elif self.path.startswith('/static/'):
                # จัดการไฟล์ static เช่น รูปภาพ
                self.path = self.path[1:]  # ตัดเครื่องหมาย / ตัวแรกออก
                return http.server.SimpleHTTPRequestHandler.do_GET(self)
                
            else:
                # ถ้าไม่ตรงกับเส้นทางที่กำหนด ส่ง 404
                self.send_response(404)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b'<html><head><title>404 Not Found</title></head><body><h1>404 Not Found</h1></body></html>')
    
    # กำหนดให้รับรู้ MIME type ของไฟล์รูปภาพ
    CustomHandler.extensions_map.update({
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.webp': 'image/webp',
        '.gif': 'image/gif',
        '.ico': 'image/x-icon',
    })
    
    # ใช้ port จาก environment variable ถ้ามี มิฉะนั้นใช้ port 8080
    port = int(os.environ.get('PORT', 8080))
    server_address = ('0.0.0.0', port)
    
    # ใช้ TCPServer ซึ่งรองรับ HTTP
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        """HTTP Server ที่ใช้ threading เพื่อรับหลายการเชื่อมต่อพร้อมกัน"""
        pass
        
    httpd = ThreadedHTTPServer(server_address, CustomHandler)
    
    logger.info(f"Starting web server on port {port} for Render.com")
    httpd.serve_forever()

def start_server_in_thread():
    """เริ่มเซิร์ฟเวอร์ในเธรดแยก"""
    # เริ่มเซิร์ฟเวอร์ในเธรดแยกเสมอ (ไม่ว่าจะรันบน Render หรือไม่)
    # แต่ถ้าไม่ได้รันบน Render ก็จะไม่มีผลต่อการทำงานของบอท
    if os.environ.get("RENDER") or os.environ.get("START_WEB_SERVER"):
        threading.Thread(target=start_web_server, daemon=True).start()
        logger.info("Web server thread started for Render.com")
    else:
        logger.info("Web server not started (not running on Render.com)")

# สำหรับรันโดยตรง (เช่น python render_helper.py)
if __name__ == "__main__":
    # ถ้ารันไฟล์นี้โดยตรง ให้เริ่มเซิร์ฟเวอร์ในเธรดหลัก (ไม่ใช่เธรดแยก)
    logger.info("Starting web server directly")
    start_web_server()