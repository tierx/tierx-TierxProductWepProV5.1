import discord
from discord.ext import commands, tasks
from discord.ui import View, Button, Modal, TextInput
import json
import os
import io
import qrcode
from PIL import Image
from datetime import datetime
from pathlib import Path
import re
from admin_examples import create_admin_examples_embed
from db_operations import load_countries, load_products, load_qrcode_url, load_thank_you_message, load_qrcode_url_async, save_qrcode_to_mongodb, load_thank_you_message_async, save_thank_you_message_to_mongodb, load_target_channel_id, save_target_channel_id, load_channel_state, save_channel_state, update_pending_number, sync_channel_numbers
from generate_qrcode import get_qrcode_discord_file

# นำเข้าโมดูลช่วยสำหรับ Render.com
try:
    from render_helper import start_server_in_thread
except ImportError:
    # หากไม่พบโมดูล ให้สร้างฟังก์ชันเปล่า
    def start_server_in_thread():
        pass

# Get the directory of the current script to ensure file paths are correct
SCRIPT_DIR = Path(__file__).parent.absolute()
PRODUCTS_FILE = SCRIPT_DIR / "products.json"
HISTORY_FILE = SCRIPT_DIR / "history.json"
CATEGORIES_DIR = SCRIPT_DIR / "categories"
QRCODE_CONFIG_FILE = SCRIPT_DIR / "qrcode_config.json"

# หมวดประเทศและหมวดสินค้า
COUNTRIES_FILE = SCRIPT_DIR / "countries.json"  # ไฟล์เก็บข้อมูลประเทศ

# โหลดข้อมูลประเทศจากไฟล์ หรือใช้ค่าเริ่มต้นถ้ายังไม่มีไฟล์
try:
    with open(COUNTRIES_FILE, "r", encoding="utf-8") as f:
        country_data = json.load(f)
        COUNTRIES = country_data.get("countries", ["1", "2", "3", "4", "5"])
        COUNTRY_NAMES = country_data.get("country_names", {
            "1": "ไทย",
            "2": "ญี่ปุ่น",
            "3": "อเมริกา",
            "4": "เกาหลี",
            "5": "จีน"
        })
        # รหัสประเทศเดิมเป็นตัวเลข
        COUNTRY_CODES = country_data.get("country_codes", {
            "thailand": "1",
            "japan": "2",
            "usa": "3",
            "korea": "4",
            "china": "5"
        })
except (FileNotFoundError, json.JSONDecodeError):
    # ค่าเริ่มต้นถ้าไม่มีไฟล์หรือไฟล์มีข้อมูลไม่ถูกต้อง
    COUNTRIES = ["1", "2", "3", "4", "5"]  # รหัสประเทศเป็นตัวเลข
    COUNTRY_NAMES = {
        "1": "ไทย",
        "2": "ญี่ปุ่น",
        "3": "อเมริกา",
        "4": "เกาหลี",
        "5": "จีน"
    }
    COUNTRY_CODES = {
        "thailand": "1",
        "japan": "2",
        "usa": "3",
        "korea": "4",
        "china": "5"
    }
    # บันทึกข้อมูลเริ่มต้นลงไฟล์
    with open(COUNTRIES_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "countries": COUNTRIES, 
            "country_names": COUNTRY_NAMES,
            "country_codes": COUNTRY_CODES
        }, f, ensure_ascii=False, indent=4)

# หมวดสินค้า (ปรับเป็นหมวดย่อยภายในประเทศ)
CATEGORIES = ["money", "weapon", "item", "story", "car", "fashion", "rentcar"]

# ตัวแปรสำหรับนับข้อความที่ยังไม่ได้เปลี่ยนชื่อช่อง
# MongoDB-based pending number system - no local counters needed
CATEGORY_NAMES = {
    "money": "เงิน",
    "weapon": "อาวุธ",
    "item": "ไอเทม",
    "story": "ไอเทมต่อสู้",
    "car": "รถยนต์",
    "fashion": "แฟชั่น",
    "rentcar": "เช่ารถ"
}
# อีโมจิสำหรับหมวดสินค้า
CATEGORY_EMOJIS = {
    "money": "💵",
    "weapon": "🔫",
    "item": "🎁",
    "story": "🤼",
    "car": "🚗",
    "fashion": "👕",
    "rentcar": "🚙"
}

# ไฟล์เก็บข้อมูลหมวดหมู่สินค้า
CATEGORIES_CONFIG_FILE = SCRIPT_DIR / "categories_config.json"

def save_categories():
    """บันทึกข้อมูลหมวดหมู่ลงไฟล์"""
    with open(CATEGORIES_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "categories": CATEGORIES, 
            "category_names": CATEGORY_NAMES,
            "category_emojis": CATEGORY_EMOJIS
        }, f, ensure_ascii=False, indent=4)
        
def load_categories():
    """โหลดข้อมูลหมวดหมู่จากไฟล์ หรือใช้ค่าเริ่มต้นถ้ายังไม่มีไฟล์"""
    global CATEGORIES, CATEGORY_NAMES, CATEGORY_EMOJIS
    try:
        with open(CATEGORIES_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            CATEGORIES = config.get("categories", CATEGORIES)
            CATEGORY_NAMES = config.get("category_names", CATEGORY_NAMES)
            CATEGORY_EMOJIS = config.get("category_emojis", CATEGORY_EMOJIS)
    except (FileNotFoundError, json.JSONDecodeError):
        # ถ้าไม่มีไฟล์หรืออ่านไม่ได้ ให้บันทึกค่าเริ่มต้น
        save_categories()
        
def edit_category(category_code, new_emoji=None, new_name=None):
    """แก้ไขอีโมจิและชื่อของหมวดหมู่สินค้า
    
    Args:
        category_code (str): รหัสหมวดหมู่ที่ต้องการแก้ไข (เช่น money, weapon)
        new_emoji (str, optional): อีโมจิใหม่
        new_name (str, optional): ชื่อใหม่
        
    Returns:
        bool: True ถ้าสำเร็จ, False ถ้าไม่พบหมวดหมู่
    """
    global CATEGORY_NAMES, CATEGORY_EMOJIS
    
    # ตรวจสอบว่าหมวดหมู่นี้มีอยู่หรือไม่
    if category_code not in CATEGORIES:
        return False
    
    # อัปเดตชื่อหมวดหมู่ถ้ามีการระบุ
    if new_name:
        CATEGORY_NAMES[category_code] = new_name
    
    # อัปเดตอีโมจิหมวดหมู่ถ้ามีการระบุ
    if new_emoji:
        CATEGORY_EMOJIS[category_code] = new_emoji
    
    # บันทึกข้อมูลหมวดหมู่ลงไฟล์
    save_categories()
    
    return True

# อีโมจิสำหรับประเทศ
COUNTRY_EMOJIS = {
    "1": "🇹🇭",  # ไทย
    "2": "🇯🇵",  # ญี่ปุ่น
    "3": "🇺🇸",  # อเมริกา
    "4": "🇰🇷",  # เกาหลี
    "5": "🇨🇳"   # จีน
}

# Default QR code URL
DEFAULT_QRCODE_URL = "https://media.discordapp.net/attachments/1177559485137555456/1297159106787934249/QRCodeSCB.png?ex=6823d54f&is=682283cf&hm=10acdea9e554c0c107119f230b8a9122498dc5a240e4e24080f3fd7f204c9df9&format=webp&quality=lossless&width=760&height=760"

# Config functions for QR code and thank you message
THANK_YOU_CONFIG_FILE = SCRIPT_DIR / "thank_you_config.json"

# Default thank you message
DEFAULT_THANK_YOU_MESSAGE = (
    "🩷 ขอบคุณมากๆระงับแล้วกลับมาอุดหนุนกันใหม่นะงับ\n"
    "รบกวนฝากกดเครดิตร้าน <:a000:1300517458679037982> ให้หน่อยได้ไหมงับ ขอบคุณมากๆงับ <a:tt03:1245427134093328417>\n"
    "คลิก >>https://discordapp.com/channels/347710783930499073/1300512180638191657 <<"
)

def load_qrcode_url():
    """Load QR code URL from config file"""
    try:
        with open(QRCODE_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config.get("url", DEFAULT_QRCODE_URL)
    except (FileNotFoundError, json.JSONDecodeError):
        # Create the default file if it doesn't exist
        save_qrcode_url(DEFAULT_QRCODE_URL)
        return DEFAULT_QRCODE_URL

# ฟังก์ชันนี้สร้างขึ้นเพื่อให้ทำงานร่วมกับฟังก์ชันที่นำเข้าจาก db_operations
async def load_qrcode_url_async_local():
    """Load QR code URL from MongoDB or fall back to config file (async version)"""
    from db_operations import load_qrcode_url_async
    return await load_qrcode_url_async()

def save_qrcode_url(url):
    """Save QR code URL to config file"""
    with open(QRCODE_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"url": url}, f, ensure_ascii=False, indent=2)
        
def load_thank_you_message():
    """Load thank you message from config file"""
    try:
        with open(THANK_YOU_CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            return config.get("message", DEFAULT_THANK_YOU_MESSAGE)
    except (FileNotFoundError, json.JSONDecodeError):
        # Create the default file if it doesn't exist
        save_thank_you_message(DEFAULT_THANK_YOU_MESSAGE)
        return DEFAULT_THANK_YOU_MESSAGE

def save_thank_you_message(message):
    """Save thank you message to config file"""
    with open(THANK_YOU_CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"message": message}, f, ensure_ascii=False, indent=2)

def save_countries():
    """Save country data to the JSON file"""
    with open(COUNTRIES_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "countries": COUNTRIES, 
            "country_names": COUNTRY_NAMES,
            "country_codes": COUNTRY_CODES,
            "country_emojis": COUNTRY_EMOJIS
        }, f, ensure_ascii=False, indent=4)

def add_country(code, name):
    """Add a new country to the system
    
    Args:
        code (str): Country code (e.g., 'korea', 'china')
        name (str): Country name in Thai (e.g., 'เกาหลี', 'จีน')
    
    Returns:
        bool or tuple: True if successful, or (False, error_message) if failed with error message
    """
    global COUNTRIES, COUNTRY_NAMES
    
    # Convert code to lowercase for consistency
    code = code.lower()
    
    # ตรวจสอบว่าประเทศนี้มีอยู่แล้วหรือไม่
    if code in COUNTRIES:
        return (False, f"ไม่สามารถเพิ่มประเทศได้ เนื่องจากมีประเทศ `{code}` อยู่แล้ว")
    
    # ตรวจสอบว่าจำนวนประเทศเกิน 5 หรือไม่
    if len(COUNTRIES) >= 5:
        return (False, "ไม่สามารถเพิ่มประเทศได้ เนื่องจากจำนวนประเทศสูงสุดคือ 5 ประเทศ")
    
    # เพิ่มประเทศใหม่
    COUNTRIES.append(code)
    COUNTRY_NAMES[code] = name
    
    # สร้างโฟลเดอร์สำหรับประเทศใหม่
    country_dir = CATEGORIES_DIR / code
    country_dir.mkdir(exist_ok=True)
    
    # บันทึกข้อมูลประเทศลงไฟล์
    save_countries()
    
    return True

def edit_country(code, new_name=None, new_emoji=None):
    """Edit a country's name and/or emoji
    
    Args:
        code (str): Country code to edit
        new_name (str, optional): New name for the country
        new_emoji (str, optional): New emoji for the country
    
    Returns:
        bool: True if successful, False if country doesn't exist
    """
    global COUNTRY_NAMES, COUNTRY_EMOJIS
    
    # ตรวจสอบว่าประเทศนี้มีอยู่หรือไม่
    if code not in COUNTRIES:
        return False
    
    # อัปเดตชื่อประเทศถ้ามีการระบุ
    if new_name:
        COUNTRY_NAMES[code] = new_name
    
    # อัปเดตอีโมจิประเทศถ้ามีการระบุ
    if new_emoji:
        COUNTRY_EMOJIS[code] = new_emoji
    
    # บันทึกข้อมูลประเทศลงไฟล์
    save_countries()
    
    return True

def remove_country(code):
    """Remove a country and all its products
    
    Args:
        code (str): Country code to remove
    
    Returns:
        bool or tuple: True if successful, or (False, error_message) if failed with error message
    """
    global COUNTRIES, COUNTRY_NAMES
    
    # Convert code to lowercase for consistency
    code = code.lower()
    
    # ตรวจสอบว่าประเทศนี้มีอยู่หรือไม่
    if code not in COUNTRIES:
        return (False, f"ไม่สามารถลบประเทศได้ เนื่องจากไม่พบประเทศ `{code}` ในระบบ")
    
    # ไม่อนุญาตให้ลบประเทศหลัก (1, 2, 3)
    if code in ["1", "2", "3"] or code in ["thailand", "japan", "usa"]:
        main_country = code
        if code in COUNTRY_CODES:
            main_country = COUNTRY_CODES[code]
        return (False, f"ไม่สามารถลบประเทศ `{COUNTRY_NAMES.get(main_country, code)}` ได้ เนื่องจากเป็นประเทศหลักของระบบ")
    
    # ตรวจสอบจำนวนขั้นต่ำของประเทศ (ควรมีอย่างน้อย 3 ประเทศ)
    if len(COUNTRIES) <= 3:
        return (False, f"ไม่สามารถลบประเทศได้ เนื่องจากต้องมีประเทศอย่างน้อย 3 ประเทศในระบบ (ปัจจุบันมี {len(COUNTRIES)} ประเทศ)")
    
    # แปลงรหัสประเทศเก่าเป็นตัวเลข
    numeric_code = code
    if code in COUNTRY_CODES:
        numeric_code = COUNTRY_CODES[code]
        
    # ลบโฟลเดอร์และไฟล์ทั้งหมดของประเทศนี้
    country_dir = CATEGORIES_DIR / numeric_code
    if country_dir.exists():
        for file in country_dir.glob("*.json"):
            file.unlink()  # ลบไฟล์
        try:
            country_dir.rmdir()  # ลบโฟลเดอร์ (ต้องว่างเปล่า)
        except OSError:
            pass  # ข้ามไปถ้าลบโฟลเดอร์ไม่ได้ (อาจมีไฟล์อื่นที่ไม่ใช่ .json)
    
    # ลบข้อมูลประเทศออกจากลิสต์และดิกชันนารี
    if numeric_code in COUNTRIES:
        COUNTRIES.remove(numeric_code)
    if numeric_code in COUNTRY_NAMES:
        del COUNTRY_NAMES[numeric_code]
    # ลบรหัสเก่าจาก COUNTRY_CODES ถ้ามี
    inv_country_codes = {v: k for k, v in COUNTRY_CODES.items()}
    if numeric_code in inv_country_codes:
        old_code = inv_country_codes[numeric_code]
        if old_code in COUNTRY_CODES:
            del COUNTRY_CODES[old_code]
    
    # บันทึกข้อมูลประเทศลงไฟล์
    save_countries()
    
    return True

# Setup bot with necessary intents
intents = discord.Intents.default()
intents.message_content = True
# ไม่ใช้ privileged intents เพื่อให้ทำงานได้โดยไม่ต้องเปิดใช้งานในพอร์ทัล
# intents.members = True
# intents.presences = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

def load_products(country=None, category=None):
    """Load product data from the JSON file based on country and category
    
    Args:
        country (str, optional): Country code (1, 2, 3, 4, 5) or legacy code (thailand, japan, usa). Defaults to None.
        category (str, optional): Category code (money, weapon, etc). Defaults to None.
        
    Returns:
        list: List of products matching the criteria
    """
    # แปลงรหัสประเทศเดิมเป็นรหัสใหม่ (ตัวเลข) ถ้าจำเป็น
    if country and country in COUNTRY_CODES:
        country = COUNTRY_CODES[country]
    
    # ถ้าระบุทั้งประเทศและหมวดหมู่
    if country and category:
        if country in COUNTRIES and category in CATEGORIES:
            # สร้างพาธไฟล์: categories/[country]/[category].json
            category_file = CATEGORIES_DIR / country / f"{category}.json"
            try:
                with open(category_file, "r", encoding="utf-8") as f:
                    products = json.load(f)
                    # เพิ่มข้อมูลประเทศและหมวดหมู่ให้แต่ละสินค้า
                    for product in products:
                        product["country"] = country
                        product["category"] = category
                    return products
            except FileNotFoundError:
                print(f"Category file not found at {category_file}, creating empty category file")
                # สร้างโฟลเดอร์ประเทศหากยังไม่มี
                country_dir = CATEGORIES_DIR / country
                country_dir.mkdir(exist_ok=True)
                # สร้างไฟล์หมวดหมู่เปล่า
                with open(category_file, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
                return []
            except json.JSONDecodeError:
                print(f"Invalid JSON in category file at {category_file}, falling back to main products file")
                return []
    
    # ถ้าระบุแค่ประเทศ โหลดสินค้าทั้งหมดจากทุกหมวดในประเทศนั้น
    elif country and country in COUNTRIES:
        all_products = []
        country_dir = CATEGORIES_DIR / country
        country_dir.mkdir(exist_ok=True)  # สร้างโฟลเดอร์ประเทศหากยังไม่มี
        
        # วนลูปอ่านทุกไฟล์ในโฟลเดอร์ประเทศ
        for category in CATEGORIES:
            category_file = country_dir / f"{category}.json"
            try:
                with open(category_file, "r", encoding="utf-8") as f:
                    products = json.load(f)
                    # เพิ่มข้อมูลประเทศและหมวดหมู่ให้แต่ละสินค้า
                    for product in products:
                        product["country"] = country
                        product["category"] = category
                    all_products.extend(products)
            except (FileNotFoundError, json.JSONDecodeError):
                # ข้ามไปหากไม่มีไฟล์หรือไฟล์ไม่ถูกต้อง
                continue
        
        return all_products
    
    # ถ้าระบุแค่หมวดหมู่ โหลดสินค้าในหมวดนั้นจากทุกประเทศ
    elif category and category in CATEGORIES:
        all_products = []
        
        # วนลูปอ่านจากทุกประเทศ
        for country in COUNTRIES:
            country_dir = CATEGORIES_DIR / country
            country_dir.mkdir(exist_ok=True)
            
            category_file = country_dir / f"{category}.json"
            try:
                with open(category_file, "r", encoding="utf-8") as f:
                    products = json.load(f)
                    # เพิ่มข้อมูลประเทศและหมวดหมู่ให้แต่ละสินค้า
                    for product in products:
                        product["country"] = country
                        product["category"] = category
                    all_products.extend(products)
            except (FileNotFoundError, json.JSONDecodeError):
                # ข้ามไปหากไม่มีไฟล์หรือไฟล์ไม่ถูกต้อง
                continue
        
        return all_products
    
    # ถ้าไม่ระบุอะไรเลย โหลดสินค้าทั้งหมด
    else:
        all_products = []
        
        # วนลูปอ่านจากทุกประเทศและทุกหมวดหมู่
        for country in COUNTRIES:
            country_dir = CATEGORIES_DIR / country
            country_dir.mkdir(exist_ok=True)
            
            for category in CATEGORIES:
                category_file = country_dir / f"{category}.json"
                try:
                    with open(category_file, "r", encoding="utf-8") as f:
                        products = json.load(f)
                        # เพิ่มข้อมูลประเทศและหมวดหมู่ให้แต่ละสินค้า
                        for product in products:
                            product["country"] = country
                            product["category"] = category
                        all_products.extend(products)
                except (FileNotFoundError, json.JSONDecodeError):
                    # ข้ามไปหากไม่มีไฟล์หรือไฟล์ไม่ถูกต้อง
                    continue
        
        # ถ้าไม่มีสินค้าในระบบใหม่ ลองโหลดจากไฟล์หลักเดิม (เพื่อการเข้ากันได้กับระบบเก่า)
        if not all_products:
            try:
                with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
                    legacy_products = json.load(f)
                    return legacy_products
            except (FileNotFoundError, json.JSONDecodeError):
                return []
        
        return all_products

def save_products(products, country=None, category=None):
    """Save product data to the JSON file or category file"""
    # บันทึกลงไฟล์หลักเสมอ (backward compatibility)
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    
    # ถ้าระบุทั้งประเทศและหมวดหมู่ บันทึกเฉพาะสินค้าในประเทศและหมวดนั้น
    if country and category:
        if country in COUNTRIES and category in CATEGORIES:
            # กรองสินค้าตามประเทศและหมวดหมู่
            filtered_products = [p for p in products if p.get("country") == country and p.get("category") == category]
            
            # สร้างโฟลเดอร์ประเทศและบันทึกไฟล์
            country_dir = CATEGORIES_DIR / country
            country_dir.mkdir(exist_ok=True)
            
            category_file = country_dir / f"{category}.json"
            with open(category_file, "w", encoding="utf-8") as f:
                # ลบข้อมูล country และ category ก่อนบันทึกลงไฟล์เฉพาะหมวด (ไม่จำเป็นต้องเก็บซ้ำ)
                clean_products = []
                for product in filtered_products:
                    # สร้าง copy ของสินค้าเพื่อไม่ให้กระทบต้นฉบับ
                    clean_product = product.copy()
                    if "country" in clean_product:
                        del clean_product["country"]
                    if "category" in clean_product:
                        del clean_product["category"]
                    clean_products.append(clean_product)
                
                json.dump(clean_products, f, ensure_ascii=False, indent=2)
    
    # ถ้าระบุแค่ประเทศ บันทึกทุกหมวดหมู่ในประเทศนั้น
    elif country and country in COUNTRIES:
        # สร้างโฟลเดอร์ประเทศ
        country_dir = CATEGORIES_DIR / country
        country_dir.mkdir(exist_ok=True)
        
        # แยกสินค้าตามหมวดหมู่และบันทึก
        for category in CATEGORIES:
            # กรองสินค้าในประเทศและหมวดหมู่นี้
            category_products = [p for p in products if p.get("country") == country and p.get("category") == category]
            
            # ถ้ามีสินค้าในหมวดนี้ให้บันทึก
            if category_products:
                category_file = country_dir / f"{category}.json"
                with open(category_file, "w", encoding="utf-8") as f:
                    # ลบข้อมูล country และ category ก่อนบันทึก
                    clean_products = []
                    for product in category_products:
                        clean_product = product.copy()
                        if "country" in clean_product:
                            del clean_product["country"]
                        if "category" in clean_product:
                            del clean_product["category"]
                        clean_products.append(clean_product)
                    
                    json.dump(clean_products, f, ensure_ascii=False, indent=2)
    
    # ถ้าระบุแค่หมวดหมู่ บันทึกหมวดนั้นในทุกประเทศ
    elif category and category in CATEGORIES:
        for country in COUNTRIES:
            # กรองสินค้าในประเทศและหมวดหมู่นี้
            country_products = [p for p in products if p.get("country") == country and p.get("category") == category]
            
            # ถ้ามีสินค้าในประเทศนี้ให้บันทึก
            if country_products:
                # สร้างโฟลเดอร์ประเทศ
                country_dir = CATEGORIES_DIR / country
                country_dir.mkdir(exist_ok=True)
                
                category_file = country_dir / f"{category}.json"
                with open(category_file, "w", encoding="utf-8") as f:
                    # ลบข้อมูล country และ category ก่อนบันทึก
                    clean_products = []
                    for product in country_products:
                        clean_product = product.copy()
                        if "country" in clean_product:
                            del clean_product["country"]
                        if "category" in clean_product:
                            del clean_product["category"]
                        clean_products.append(clean_product)
                    
                    json.dump(clean_products, f, ensure_ascii=False, indent=2)
    
    # ถ้าไม่ระบุอะไรเลย บันทึกทุกสินค้าแยกตามประเทศและหมวดหมู่
    else:
        # จัดกลุ่มสินค้าตามประเทศและหมวดหมู่
        for country in COUNTRIES:
            # สร้างโฟลเดอร์ประเทศ
            country_dir = CATEGORIES_DIR / country
            country_dir.mkdir(exist_ok=True)
            
            for category in CATEGORIES:
                # กรองสินค้าในประเทศและหมวดหมู่นี้
                filtered_products = [p for p in products if p.get("country") == country and p.get("category") == category]
                
                # ถ้ามีสินค้าในประเทศและหมวดหมู่นี้ให้บันทึก
                if filtered_products:
                    category_file = country_dir / f"{category}.json"
                    with open(category_file, "w", encoding="utf-8") as f:
                        # ลบข้อมูล country และ category ก่อนบันทึก
                        clean_products = []
                        for product in filtered_products:
                            clean_product = product.copy()
                            if "country" in clean_product:
                                del clean_product["country"]
                            if "category" in clean_product:
                                del clean_product["category"]
                            clean_products.append(clean_product)
                        
                        json.dump(clean_products, f, ensure_ascii=False, indent=2)
            
def save_product_to_category(product):
    """Save a single product to its category file
    
    Args:
        product: A product dictionary with country, category, name, price, and emoji
    """
    country = product.get("country", "thailand")  # Default to Thailand if no country specified
    category = product.get("category")
    
    # Check if country and category are valid
    if country in COUNTRIES and category in CATEGORIES:
        # Ensure country directory exists
        country_dir = CATEGORIES_DIR / country
        country_dir.mkdir(exist_ok=True)
        
        # Set path to category file
        category_file = country_dir / f"{category}.json"
        
        try:
            # Try to read existing products from the category file
            with open(category_file, "r", encoding="utf-8") as f:
                category_products = json.load(f)
                
            # Remove product with same name if exists
            category_products = [p for p in category_products if p.get("name") != product.get("name")]
            
            # Create a clean version of the product without country and category
            clean_product = product.copy()
            if "country" in clean_product:
                del clean_product["country"]
            if "category" in clean_product:
                del clean_product["category"]
            
            # Add the clean product
            category_products.append(clean_product)
            
            # Save back to category file
            with open(category_file, "w", encoding="utf-8") as f:
                json.dump(category_products, f, ensure_ascii=False, indent=2)
                
        except (FileNotFoundError, json.JSONDecodeError):
            # Create a clean version of the product without country and category
            clean_product = product.copy()
            if "country" in clean_product:
                del clean_product["country"]
            if "category" in clean_product:
                del clean_product["category"]
                
            # Create new category file with the single product
            with open(category_file, "w", encoding="utf-8") as f:
                json.dump([clean_product], f, ensure_ascii=False, indent=2)

def log_purchase(user, items, total_price):
    """Log purchase history to the JSON file"""
    # Create the history file if it doesn't exist
    if not HISTORY_FILE.exists():
        HISTORY_FILE.touch()
        
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        data = {
            "user": str(user),
            "items": items,
            "total": total_price,
            "timestamp": datetime.now().isoformat()
        }
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

def clear_category_products(category, country=None):
    """Delete all products in a specific category
    
    Args:
        category (str): Category name to clear
        country (str, optional): Country name to clear. If None, clears the category in all countries.
    
    Returns:
        bool: True if successful, False otherwise
    """
    if category in CATEGORIES:
        # ถ้าระบุประเทศ ล้างเฉพาะหมวดในประเทศนั้น
        if country and country in COUNTRIES:
            # ล้างไฟล์หมวดหมู่ในประเทศที่ระบุ
            country_dir = CATEGORIES_DIR / country
            category_file = country_dir / f"{category}.json"
            
            # ถ้ามีไฟล์อยู่แล้ว ให้เขียนอาร์เรย์ว่างทับ
            if category_file.exists():
                with open(category_file, "w", encoding="utf-8") as f:
                    json.dump([], f, ensure_ascii=False, indent=2)
            
            # โหลดสินค้าทั้งหมดจากไฟล์หลัก
            all_products = []
            try:
                with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
                    all_products = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            
            # กรองสินค้าออกเฉพาะในประเทศและหมวดที่ต้องการลบ
            filtered_products = [p for p in all_products 
                                 if not (p.get("country") == country and p.get("category") == category)]
            
            # บันทึกกลับไปที่ไฟล์หลัก
            with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
                json.dump(filtered_products, f, ensure_ascii=False, indent=2)
                
        # ถ้าไม่ระบุประเทศ ล้างหมวดนี้ในทุกประเทศ
        else:
            for country in COUNTRIES:
                country_dir = CATEGORIES_DIR / country
                category_file = country_dir / f"{category}.json"
                
                # ถ้ามีไฟล์อยู่แล้ว ให้เขียนอาร์เรย์ว่างทับ
                if category_file.exists():
                    with open(category_file, "w", encoding="utf-8") as f:
                        json.dump([], f, ensure_ascii=False, indent=2)
            
            # โหลดสินค้าทั้งหมดจากไฟล์หลัก
            all_products = []
            try:
                with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
                    all_products = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            
            # กรองสินค้าที่อยู่ในหมวดอื่นออก (เก็บเฉพาะที่ไม่ได้อยู่ในหมวดที่ต้องการลบ)
            filtered_products = [p for p in all_products if p.get("category") != category]
            
            # บันทึกกลับไปที่ไฟล์หลัก
            with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
                json.dump(filtered_products, f, ensure_ascii=False, indent=2)
                
        return True
    return False

def delete_all_products():
    """Delete all products from all categories in all countries completely"""
    
    # ล้างไฟล์ทุกหมวดหมู่ในทุกประเทศโดยสมบูรณ์
    for country in COUNTRIES:
        country_dir = CATEGORIES_DIR / country
        
        # สร้างโฟลเดอร์ประเทศหากยังไม่มี
        country_dir.mkdir(exist_ok=True)
        
        # ล้างทุกหมวดในประเทศนี้
        for category in CATEGORIES:
            category_file = country_dir / f"{category}.json"
            
            # เขียนรายการว่างลงไปในไฟล์
            with open(category_file, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
    
    # ล้างไฟล์หลัก
    with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)
    
    # ล้างไฟล์หมวดหมู่เดิม (สำหรับความเข้ากันได้กับระบบเก่า)
    old_categories = ["money.json", "weapon.json", "item.json", "car.json", "fashion.json", "rentcar.json"]
    for filename in old_categories:
        category_file = CATEGORIES_DIR / filename
        if category_file.exists():
            # เขียนรายการว่างลงไฟล์เก่า
            with open(category_file, "w", encoding="utf-8") as f:
                json.dump([], f, ensure_ascii=False, indent=2)
        
    return True

def add_no_product_placeholders():
    """Add 'ไม่มีสินค้า' placeholder to empty categories in all countries
    
    This function only adds the placeholder product to categories that are completely empty.
    """
    added_count = 0
    # ตรวจสอบและเพิ่มสินค้า placeholder ในทุกหมวดหมู่ของทุกประเทศที่ไม่มีสินค้า
    for country in COUNTRIES:
        country_dir = CATEGORIES_DIR / country
        
        # สร้างโฟลเดอร์ประเทศหากยังไม่มี
        country_dir.mkdir(exist_ok=True)
        
        # ตรวจสอบทุกหมวดในประเทศนี้
        for category in CATEGORIES:
            category_file = country_dir / f"{category}.json"
            
            # อ่านไฟล์หากมีอยู่แล้ว หรือสร้างไฟล์ว่างหากยังไม่มี
            if category_file.exists():
                try:
                    with open(category_file, "r", encoding="utf-8") as f:
                        products = json.load(f)
                except (json.JSONDecodeError, FileNotFoundError):
                    products = []
            else:
                products = []
                
            # เพิ่มสินค้า placeholder เฉพาะถ้าไม่มีสินค้าในหมวดนี้
            if not products:
                products.append({
                    "name": "ไม่มีสินค้า",
                    "price": 0,
                    "emoji": "❌",
                    "category": category,
                    "country": country
                })
                
                # บันทึกกลับไปที่ไฟล์
                with open(category_file, "w", encoding="utf-8") as f:
                    json.dump(products, f, ensure_ascii=False, indent=2)
                    
                added_count += 1
    
    # สำหรับความเข้ากันได้กับระบบเก่า ตรวจสอบไฟล์หมวดหมู่เดิม
    old_categories = ["money.json", "weapon.json", "item.json", "car.json", "fashion.json", "rentcar.json"]
    for filename in old_categories:
        category_file = CATEGORIES_DIR / filename
        category_name = filename.replace(".json", "")
        
        # ตรวจสอบว่าไฟล์มีอยู่หรือไม่ ถ้าไม่มีให้ข้าม
        if category_file.exists():
            try:
                with open(category_file, "r", encoding="utf-8") as f:
                    products = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                products = []
                
            # เพิ่มสินค้า placeholder เฉพาะถ้าไม่มีสินค้าในหมวดนี้
            if not products:
                products.append({
                    "name": "ไม่มีสินค้า",
                    "price": 0,
                    "emoji": "❌",
                    "category": category_name
                })
                
                # บันทึกกลับไปที่ไฟล์
                with open(category_file, "w", encoding="utf-8") as f:
                    json.dump(products, f, ensure_ascii=False, indent=2)
                    
                added_count += 1
                
    return added_count

def batch_add_products(products_data):
    """Add multiple products at once
    
    products_data should be a list of dictionaries with the following keys:
    - name: str
    - price: float
    - emoji: str
    - category: str
    """
    if not products_data or not isinstance(products_data, list):
        return False, "ไม่มีข้อมูลสินค้าที่จะเพิ่ม หรือรูปแบบข้อมูลไม่ถูกต้อง"
    
    added_count = 0
    errors = []
    
    # จัดกลุ่มสินค้าตามประเทศและหมวดหมู่
    products_by_country_category = {}
    
    # Load current products (เฉพาะเพื่อตรวจสอบซ้ำ)
    all_products = load_products()
    
    # Create a set of existing product names for quick lookup
    existing_names = {p["name"] for p in all_products}
    
    for product in products_data:
        # Check if all required fields are present
        if not all(key in product for key in ["name", "price", "emoji", "category"]):
            errors.append(f"ข้อมูลสินค้าไม่ครบถ้วน: {product}")
            continue
            
        # Check if product already exists
        if product["name"] in existing_names:
            errors.append(f"สินค้า '{product['name']}' มีอยู่แล้ว")
            continue
            
        # Validate category using CATEGORIES list
        if product["category"] not in CATEGORIES:
            errors.append(f"หมวดหมู่ '{product['category']}' ไม่ถูกต้องสำหรับสินค้า '{product['name']}' (หมวดที่รองรับ: {', '.join(CATEGORIES)})")
            continue
        
        # Add to existing names to prevent duplicates in the same batch
        existing_names.add(product["name"])
        
        # ตรวจสอบว่ามีการระบุประเทศหรือไม่
        country = product.get("country", "1")  # Default to "1" (Thailand) if no country
        category = product["category"]
        
        # ถ้าหมวดหมู่และประเทศถูกต้อง
        if country in COUNTRIES and category in CATEGORIES:
            # สร้างคีย์สำหรับจัดกลุ่ม
            key = (country, category)
            if key not in products_by_country_category:
                products_by_country_category[key] = []
            products_by_country_category[key].append(product)
            added_count += 1
    
    # Only save if we added anything
    if added_count > 0:
        # อัปเดตไฟล์แต่ละประเทศและหมวดหมู่
        for (country, category), products in products_by_country_category.items():
            # โหลดสินค้าที่มีอยู่แล้วในประเทศและหมวดหมู่นี้
            existing_category_products = load_products(country, category)
            
            # Remove products with the same name that we're going to add
            product_names_to_add = {p["name"] for p in products}
            existing_category_products = [p for p in existing_category_products 
                                         if p.get("name") not in product_names_to_add]
            
            # Add new products
            existing_category_products.extend(products)
            
            # Save just the category file
            save_products(existing_category_products, country, category)
            
            # บันทึกแต่ละสินค้าลงในไฟล์หลักด้วย (เพื่อให้การค้นหาสินค้าทำงานได้ถูกต้อง)
            for product in products:
                # Save each product individually to the appropriate category file
                save_product_to_category(product)
    
    # คืนค่าจำนวนสินค้าที่เพิ่มและข้อผิดพลาด
    if added_count > 0:
        return True, f"เพิ่มสินค้าจำนวน {added_count} รายการเรียบร้อยแล้ว" + (f" มีข้อผิดพลาด {len(errors)} รายการ: {', '.join(errors)}" if errors else "")
    else:
        return False, f"ไม่สามารถเพิ่มสินค้าได้: {', '.join(errors)}"

class QuantityModal(Modal):
    """Modal for entering product quantity"""
    def __init__(self, product_index, product):
        super().__init__(title=f"จำนวน {product['name']}")
        self.product_index = product_index
        self.product = product
        self.quantity = None
        
        # Create text input for quantity
        self.quantity_input = TextInput(
            label=f"ใส่จำนวน {product['name']} ที่ต้องการ",
            placeholder="ใส่จำนวน",
            required=True,
            min_length=1,
            max_length=10,
            default="1"
        )
        self.add_item(self.quantity_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Convert input to integer
            quantity = int(self.quantity_input.value)
            if quantity < 0:
                await interaction.response.send_message("❌ จำนวนต้องมากกว่าหรือเท่ากับ 0", ephemeral=True)
                return
                
            self.quantity = quantity
            await interaction.response.defer()
        except ValueError:
            await interaction.response.send_message("❌ กรุณาใส่จำนวนเป็นตัวเลขเท่านั้น", ephemeral=True)

class PageIndicatorButton(Button):
    """Button that shows current page (disabled - cannot be clicked)"""
    def __init__(self, page, total_pages, row=0, view=None):
        self.page = page
        self.total_pages = total_pages
        self.parent_view = view
        super().__init__(
            label=f"หน้า {page + 1}/{total_pages}",
            style=discord.ButtonStyle.secondary,
            disabled=True,  # Set button to disabled/non-clickable
            row=row
        )

class PageInputModal(Modal):
    """Modal for entering page number"""
    def __init__(self, view, total_pages=1):
        self.view = view
        self.total_pages = total_pages
        super().__init__(title=f"ไปที่หน้า (1-{total_pages})")
        
        self.page_number = TextInput(
            label=f"ระบุเลขหน้า (1-{total_pages})",
            placeholder="เช่น 1, 2, 3",
            min_length=1,
            max_length=10,
            required=True
        )
        self.add_item(self.page_number)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            page_number = int(self.page_number.value)
            if hasattr(self.view, 'go_to_page'):
                await self.view.go_to_page(interaction, page_number)
            else:
                # Fallback if go_to_page is not available
                await interaction.response.send_message(f"กำลังพยายามไปที่หน้า {page_number}", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("กรุณาระบุเลขหน้าเป็นตัวเลขเท่านั้น", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"เกิดข้อผิดพลาด: {str(e)}", ephemeral=True)

class MultiCategoryView(View):
    """View for selecting multiple categories"""
    def __init__(self):
        super().__init__(timeout=None)
        self.selected_categories = []
        
        # Add category buttons with toggleable state
        categories = [
            ("money", "เงิน", "💰", 0),
            ("weapon", "อาวุธ", "🔫", 0),
            ("item", "ไอเทม", "🧪", 0),
            ("car", "รถยนต์", "🚗", 1),
            ("fashion", "แฟชั่น", "👒", 1),
            ("rentcar", "เช่ารถ", "🚙", 1)
        ]
        
        for cat_id, label, emoji, row in categories:
            self.add_item(MultiCategoryButton(cat_id, label, emoji, row))
            
        # Add confirm button to view selected categories
        self.add_item(ViewSelectedCategoriesButton())

class MultiCategoryButton(Button):
    """Button for category selection with toggle state"""
    def __init__(self, category, label, emoji, row=0):
        self.category = category
        self.is_selected = False
        super().__init__(
            label=label, 
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            custom_id=f"category_{category}",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: MultiCategoryView = self.view
        
        # Toggle selection state
        self.is_selected = not self.is_selected
        
        # Update button style based on selection
        if self.is_selected:
            self.style = discord.ButtonStyle.success
            if self.category not in view.selected_categories:
                view.selected_categories.append(self.category)
        else:
            self.style = discord.ButtonStyle.secondary
            if self.category in view.selected_categories:
                view.selected_categories.remove(self.category)
        
        # Update message with current selections
        selected_text = ", ".join([f"`{cat}`" for cat in view.selected_categories]) if view.selected_categories else "ยังไม่ได้เลือกหมวดหมู่"
        
        # ป้องกันข้อความ "การโต้ตอบล้มเหลว"
        await interaction.response.defer()
        
        # ใช้ message.edit แทน response.edit_message เพื่อให้กดหลายครั้งได้
        await interaction.message.edit(
            content=f"📋 เลือกหมวดหมู่สินค้า (กดปุ่มเพื่อเลือก/ยกเลิก):\nหมวดหมู่ที่เลือก: {selected_text}", 
            view=view
        )

class CategoryNavButton(Button):
    """Button to navigate between categories in the shop view"""
    def __init__(self, category, is_active=False, row=0, country="thailand"):
        self.category = category
        self.country = country
        style = discord.ButtonStyle.success if is_active else discord.ButtonStyle.secondary
        # Use category name in Thai if available
        label = CATEGORY_NAMES.get(category, category)
        # ใช้อีโมจิตามหมวดหมู่
        emoji = CATEGORY_EMOJIS.get(category, "")
        super().__init__(
            label=label,
            emoji=emoji,
            style=style,
            custom_id=f"nav_{country}_{category}",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        
        # Create a new view with the same categories but showing this category's products
        new_view = CategoryShopView(
            view.all_categories, 
            current_category=self.category, 
            country=self.country,
            quantities=view.quantities, 
            page=0,
            showing_all_countries=False if hasattr(view, 'showing_all_countries') else False
        )
        
        # Create summary of current cart
        summary_lines = []
        total = 0
        
        if hasattr(view, 'all_products') and view.all_products:
            for product in view.all_products:
                # ตรวจสอบว่ามี id ใน product หรือไม่
                if 'id' in product:
                    qty = view.quantities.get(product['id'], 0)
                    if qty > 0:
                        item_total = product['price'] * qty
                        total += item_total
                        summary_lines.append(f"{product['emoji']} {product['name']} - {product['price']:.2f}฿ x {qty} = {item_total:.2f}฿")
        
        # แสดงชื่อประเทศและหมวดหมู่ในภาษาไทย
        category_thai = CATEGORY_NAMES.get(self.category, self.category)
        country_thai = COUNTRY_NAMES.get(self.country, self.country)
        content = f"🛍️ สินค้าในประเทศ `{country_thai}` หมวด `{category_thai}`:"
        
        if summary_lines:
            content += f"\n\n📝 รายการที่เลือก:\n" + "\n".join(summary_lines) + f"\n\n💵 ยอดรวม: {total:.2f}฿"
        
        # ป้องกันข้อความ "การโต้ตอบล้มเหลว"
        await interaction.response.defer()
        
        # ใช้ message.edit แทน response.edit_message เพื่อให้กดหลายครั้งได้
        await interaction.message.edit(content=content, view=new_view)

class CategoryShopView(View):
    """View for displaying products from a category with navigation to other categories"""
    def __init__(self, all_categories, current_category=None, country="1", quantities=None, page=0, showing_all_countries=True, all_products=None, cart_items=None):
        super().__init__(timeout=None)
        self.all_categories = all_categories
        self.current_category = current_category
        
        # แปลงรหัสประเทศจากชื่อเป็นตัวเลขถ้าจำเป็น
        if country in COUNTRY_CODES:
            country = COUNTRY_CODES[country]
        elif country in ["thailand", "japan", "usa", "korea", "china"]:
            # แปลงชื่อประเทศเดิมเป็นรหัสตัวเลข
            old_to_new = {"thailand": "1", "japan": "2", "usa": "3", "korea": "4", "china": "5"}
            country = old_to_new[country]
            
        self.country = country  # ประเทศที่เลือก (เป็นตัวเลข 1-5)
        self.quantities = quantities or {}  # Dict to store quantities by product ID
        self.page = page
        self.products_per_page = 5  # Number of products shown per page - ปรับจาก 10 เป็น 5
        
        # กำหนดค่าเริ่มต้นสำหรับการแสดงประเทศทั้งหมดหรือเฉพาะที่เลือก
        self.showing_all_countries = showing_all_countries
        
        # รับค่า cart_items จากภายนอก (ถ้ามี)
        self.cart_items = cart_items or {}
        
        # เพิ่มปุ่มเลือกประเทศด้านบนสุด
        self.add_country_buttons()
        
        # ถ้ามีการส่ง all_products มาให้ใช้เลย
        if all_products:
            self.all_products = all_products
        else:
            # Load products from ALL countries and ALL categories (to track cart items from any country/category)
            self.all_products = []
            # ใช้ set เพื่อตรวจสอบไม่ให้เกิดการซ้ำซ้อน
            seen_product_ids = set()
            
            # โหลดสินค้าจากทุกประเทศและทุกหมวดหมู่
            for c_code in COUNTRIES:
                for c_category in all_categories:
                    c_products = load_products(c_code, c_category)  # โหลดสินค้าจากทุกประเทศและหมวดหมู่
                    if c_products:
                        for curr_product in c_products:
                            # Add category, country, and create unique ID
                            curr_product['category'] = c_category
                            curr_product['country'] = c_code
                            curr_product_id = f"{c_code}_{c_category}_{curr_product['name']}"
                            curr_product['id'] = curr_product_id
                            
                            # ตรวจสอบว่ามีสินค้านี้อยู่แล้วหรือไม่
                            if curr_product_id not in seen_product_ids:
                                seen_product_ids.add(curr_product_id)
                                self.all_products.append(curr_product)
                                
                                # Initialize quantity if not already set
                                if curr_product_id not in self.quantities:
                                    self.quantities[curr_product_id] = 0
                                    
                                # นำข้อมูลจำนวนสินค้าจาก cart_items มาใช้ถ้ามี
                                if self.cart_items and curr_product_id in self.cart_items:
                                    self.quantities[curr_product_id] = self.cart_items[curr_product_id]

    
    def add_country_buttons(self):
        """Add buttons for country selection in the top row"""
        # ตรวจสอบว่ามีการกดเลือกประเทศแล้วหรือไม่
        selected_country = self.country
        
        # แสดงข้อมูลดีบัก
        print(f"Current country in add_country_buttons: {selected_country}")
        
        if hasattr(self, 'showing_all_countries') and self.showing_all_countries is False:
            # กรณีที่กดเลือกประเทศแล้ว แสดงเฉพาะประเทศที่เลือก
            country_code = selected_country
            country_name = COUNTRY_NAMES[country_code]
            
            # ใช้อีโมจิธงชาติสำหรับแต่ละประเทศจากตัวแปรกลาง
            country_emoji = COUNTRY_EMOJIS.get(country_code, "🌏")
            
            # เพิ่มปุ่มประเทศที่เลือก (สีน้ำเงิน) อยู่แถว 0
            selected_button = Button(
                label=country_name,
                emoji=country_emoji,
                style=discord.ButtonStyle.blurple,
                custom_id=f"selected_country_{country_code}",
                row=0
            )
            self.add_item(selected_button)
            
            # เพิ่มปุ่มสำหรับกลับไปดูประเทศทั้งหมด อยู่แถว 0 เช่นกัน
            back_button = Button(
                label="เลือกประเทศอื่น",
                emoji="🔄",
                style=discord.ButtonStyle.primary,
                custom_id="show_all_countries",
                row=0
            )
            
            # สร้างฟังก์ชัน back_to_countries สำหรับปุ่มกลับไปเลือกประเทศ
            async def back_to_countries(interaction):
                await interaction.response.defer()
                
                # ตรวจสอบและแปลงรหัสประเทศถ้าจำเป็น
                display_country = selected_country
                if display_country in COUNTRY_CODES:
                    display_country = COUNTRY_CODES[display_country]
                
                # สร้าง view ใหม่โดยใช้ประเทศเดิม แต่แสดงปุ่มประเทศทั้งหมด  
                new_view = CategoryShopView(
                    self.all_categories,
                    current_category=self.current_category,
                    country=display_country,
                    quantities=self.quantities,
                    page=0,
                    showing_all_countries=True
                )
                
                # เตรียมข้อความที่แสดงพร้อมตรวจสอบข้อผิดพลาด
                try:
                    country_name = COUNTRY_NAMES[display_country]
                    category_name = CATEGORY_NAMES[self.current_category]
                    display_message = f"🛍️ สินค้าในประเทศ `{country_name}` หมวด `{category_name}`"
                except KeyError:
                    # กรณีไม่พบประเทศหรือหมวดหมู่ เพิ่มรายละเอียดการดีบัก
                    display_message = f"🛍️ สินค้า (รหัสประเทศ: `{display_country}`, หมวด: `{self.current_category}`)"
                
                # ตรวจสอบสินค้าที่เลือกไว้และแสดงใน content
                summary_lines = []
                total = 0
                
                # โหลดสินค้าทั้งหมดในหมวดหมู่ปัจจุบัน
                all_products = []
                products = load_products(display_country, self.current_category)
                all_products.extend(products)
                
                # สร้างรายการสินค้าที่เลือกไว้
                for product in all_products:
                    if 'id' in product:
                        qty = self.quantities.get(product['id'], 0)
                        if qty > 0:
                            item_total = product['price'] * qty
                            total += item_total
                            summary_lines.append(f"{product['emoji']} {product['name']} - {product['price']:.2f}฿ x {qty} = {item_total:.2f}฿")
                
                # เพิ่มรายการสินค้าที่เลือกไว้ใน content
                if summary_lines:
                    display_message += f"\n\n📝 รายการที่เลือก:\n" + "\n".join(summary_lines) + f"\n\n💵 ยอดรวม: {total:.2f}฿"
                
                await interaction.message.edit(
                    content=display_message, 
                    view=new_view
                )
                
            back_button.callback = back_to_countries
            self.add_item(back_button)
            
        else:
            # กรณีที่ยังไม่ได้กดเลือกประเทศ หรือกดปุ่ม "เลือกประเทศอื่น" แสดงประเทศทั้งหมด
            self.showing_all_countries = True
            
            # สร้างและเพิ่มปุ่มสำหรับแต่ละประเทศ
            for i, country_code in enumerate(COUNTRIES):
                country_name = COUNTRY_NAMES[country_code]
                is_active = (country_code == selected_country)
                
                # กำหนดแถวปุ่มตามลำดับ (โดยให้มีไม่เกิน 5 ปุ่มต่อแถว)
                # ปุ่มประเทศ 1-5 อยู่แถว 0, ปุ่มประเทศ 6-10 อยู่แถว 1
                button_row = 0 if i < 5 else 1
                
                # ใช้อีโมจิธงชาติสำหรับแต่ละประเทศจากตัวแปรกลาง
                country_emoji = COUNTRY_EMOJIS.get(country_code, "🌏")
                
                country_button = Button(
                    label=country_name,
                    emoji=country_emoji,
                    style=discord.ButtonStyle.blurple if is_active else discord.ButtonStyle.primary,
                    custom_id=f"country_{country_code}",
                    row=button_row
                )
                
                # กำหนดตัวแปรเพื่อเก็บค่า country_code สำหรับใช้ใน callback
                current_country = country_code
                
                # สร้าง closure สำหรับเก็บค่า country_code แยกสำหรับแต่ละปุ่ม
                def create_country_callback(country_to_display):
                    async def country_button_callback(interaction):
                        # ป้องกันการแสดงข้อความ "การโต้ตอบล้มเหลว"
                        await interaction.response.defer()
                        
                        # ตรวจสอบว่า country_to_display เป็นรหัสประเทศที่ถูกต้อง
                        # แปลงรหัสประเทศเก่าเป็นเลขถ้าจำเป็น
                        display_country = country_to_display
                        if display_country in COUNTRY_CODES:
                            display_country = COUNTRY_CODES[display_country]
                            
                        # สร้าง view ใหม่โดยเปลี่ยนประเทศ และซ่อนประเทศอื่นๆ
                        new_view = CategoryShopView(
                            self.all_categories,
                            current_category=self.current_category,
                            country=display_country,
                            quantities=self.quantities,
                            page=0,  # กลับไปหน้าแรก
                            showing_all_countries=False
                        )
                        
                        # เตรียมข้อความที่แสดงพร้อมตรวจสอบข้อผิดพลาด
                        try:
                            country_name = COUNTRY_NAMES[display_country]
                            category_name = CATEGORY_NAMES[self.current_category]
                            display_message = f"🛍️ สินค้าในประเทศ `{country_name}` หมวด `{category_name}`"
                        except KeyError:
                            # กรณีไม่พบประเทศหรือหมวดหมู่ เพิ่มรายละเอียดการดีบัก
                            display_message = f"🛍️ สินค้า (รหัสประเทศ: `{display_country}`, หมวด: `{self.current_category}`)"
                        
                        # ตรวจสอบสินค้าที่เลือกไว้และแสดงใน content
                        summary_lines = []
                        total = 0
                        
                        # โหลดสินค้าทั้งหมดในหมวดหมู่ปัจจุบัน
                        all_products = []
                        products = load_products(display_country, self.current_category)
                        all_products.extend(products)
                        
                        # สร้างรายการสินค้าที่เลือกไว้
                        for product in all_products:
                            if 'id' in product:
                                qty = self.quantities.get(product['id'], 0)
                                if qty > 0:
                                    item_total = product['price'] * qty
                                    total += item_total
                                    summary_lines.append(f"{product['emoji']} {product['name']} - {product['price']:.2f}฿ x {qty} = {item_total:.2f}฿")
                        
                        # เพิ่มรายการสินค้าที่เลือกไว้ใน content
                        if summary_lines:
                            display_message += f"\n\n📝 รายการที่เลือก:\n" + "\n".join(summary_lines) + f"\n\n💵 ยอดรวม: {total:.2f}฿"
                        
                        # ใช้ message.edit แทน response.edit_message เพื่อให้กดหลายครั้งได้
                        await interaction.message.edit(
                            content=display_message, 
                            view=new_view
                        )
                    return country_button_callback
                
                # กำหนด callback ให้กับปุ่ม
                country_button.callback = create_country_callback(country_code)
                
                # เพิ่มปุ่มลงใน view
                self.add_item(country_button)
        
        # Add category navigation buttons with maximum 5 buttons per row (Discord limit)
        for i, category in enumerate(self.all_categories):
            is_active = (category == self.current_category)
            # ปุ่มหมวดหมู่ 1-5 อยู่แถว 1, ที่เหลืออยู่แถว 2
            row = 1 if i < 5 else 2
            
            # ถ้ามีหมวดหมู่มากกว่า 10 รายการ ไม่แสดงรายการหลังจากนั้น
            if i >= 10:
                break
                
            self.add_item(CategoryNavButton(category, is_active=is_active, row=row, country=self.country))
        
        # Display products for current category only (all products in the same row)
        if self.current_category:
            # Get products for the current category from current country
            # ตรวจสอบว่า self.all_products มีหรือไม่ก่อนใช้งาน
            if hasattr(self, 'all_products') and self.all_products:
                category_products = [p for p in self.all_products if p.get('category') == self.current_category and p.get('country') == self.country]
            else:
                # ถ้าไม่มี self.all_products ให้โหลดสินค้าใหม่
                category_products = load_products(self.country, self.current_category)
            
            # Calculate start and end indices for pagination
            start_idx = self.page * self.products_per_page
            end_idx = start_idx + self.products_per_page
            
            # Get current page of products
            page_products = category_products[start_idx:end_idx]
            
            # แสดงสินค้าในแถว 3 (เนื่องจากแถว 0-1 ใช้แสดงประเทศและแถว 2 ใช้แสดงหมวดหมู่)
            for i, product in enumerate(page_products):
                if i < 5:  # แสดงไม่เกิน 5 สินค้าต่อหน้า (ข้อจำกัด Discord: ไม่เกิน 5 ปุ่มต่อแถว)
                    button = ProductButton(product)
                    button.row = 3  # แสดงสินค้าในแถวที่ 3 เสมอ
                    self.add_item(button)
            
            # Add pagination buttons if needed
            if len(category_products) > self.products_per_page:
                # Previous page button (left arrow)
                if self.page > 0:
                    prev_button = Button(emoji="⬅️", style=discord.ButtonStyle.secondary, row=4)
                    prev_button.callback = self.prev_page_callback
                    self.add_item(prev_button)
                
                # Page indicator - clickable for page navigation
                total_pages = (len(category_products) - 1) // self.products_per_page + 1
                self.total_pages = total_pages  # Store for callback use
                # Create a PageIndicatorButton instead of a regular Button with callback
                page_indicator = PageIndicatorButton(
                    page=self.page,
                    total_pages=total_pages, 
                    row=4,
                    view=self
                )
                self.add_item(page_indicator)
                
                # Next page button (right arrow)
                if end_idx < len(category_products):
                    next_button = Button(emoji="➡️", style=discord.ButtonStyle.secondary, row=4)
                    next_button.callback = self.next_page_callback
                    self.add_item(next_button)
        
        # Add control buttons at the bottom - use row 4 after pagination buttons
        reset_button = ResetCartButton()
        reset_button.row = 4
        self.add_item(reset_button)
        
        # ตรวจสอบว่า all_products มีการกำหนดค่าและไม่เป็น None ก่อนส่งไปยัง ConfirmButton
        products_to_use = self.all_products if hasattr(self, 'all_products') and self.all_products else []
        
        confirm_button = ConfirmButton(products_to_use)
        confirm_button.row = 4
        self.add_item(confirm_button)
    
    async def go_to_page(self, interaction: discord.Interaction, page_number: int):
        """Navigate to a specific page number"""
        # Validate page number (1-based in UI, 0-based in code)
        page_index = page_number - 1
        if page_index < 0:
            page_index = 0
        if hasattr(self, 'total_pages') and page_index >= self.total_pages:
            page_index = self.total_pages - 1
            
        # ตรวจสอบและแปลงรหัสประเทศถ้าจำเป็น
        display_country = self.country
        if display_country in COUNTRY_CODES:
            display_country = COUNTRY_CODES[display_country]
            
        # ดึงข้อมูลสถานะการแสดงประเทศ
        showing_all_countries = getattr(self, 'showing_all_countries', False)
        
        # สร้าง quantities_copy เพื่อป้องกันการเปลี่ยนแปลงที่ไม่ตั้งใจ
        quantities_copy = {}
        for product_id, qty in self.quantities.items():
            quantities_copy[product_id] = qty
        
        # Create a new view with the requested page
        new_view = CategoryShopView(
            self.all_categories,
            current_category=self.current_category,
            country=display_country,
            quantities=quantities_copy,
            page=page_index,
            showing_all_countries=showing_all_countries,
            all_products=self.all_products,  # ส่งข้อมูลสินค้าทั้งหมดไปด้วย
            cart_items=self.quantities  # ส่งข้อมูลตะกร้าสินค้าแยกต่างหาก
        )
        
        # ช่วยให้แน่ใจว่าการอ้างอิง objects ไม่สูญหาย
        for product_id, qty in self.quantities.items():
            if qty > 0:  # เฉพาะรายการที่มีการเลือก
                new_view.quantities[product_id] = qty
        
        # สร้างข้อความสำหรับแสดงผล
        category_name = CATEGORY_NAMES.get(self.current_category, self.current_category)
        country_name = COUNTRY_NAMES.get(display_country, display_country)
        
        # สร้างข้อความแสดงผลตามสถานะการแสดงประเทศ
        if showing_all_countries:
            content_message = f"🛍️ สินค้าในหมวด `{category_name}`"
        else:
            content_message = f"🛍️ สินค้าในประเทศ `{country_name}` หมวด `{category_name}`"
            
        # สร้างรายการสินค้าที่เลือก
        selected_items = []
        total_price = 0
        
        # จากข้อมูล quantities ตรวจสอบสินค้าที่ถูกเลือกในตะกร้า
        for product in self.all_products:
            if 'id' in product:
                product_id = product['id']
                qty = quantities_copy.get(product_id, 0)
                if qty > 0:
                    item_total = product['price'] * qty
                    total_price += item_total
                    
                    # ดึงชื่อประเทศที่สินค้าอยู่ (ถ้ามี)
                    product_country = product.get('country', '')
                    if product_country in COUNTRY_NAMES:
                        country_name_in_product = COUNTRY_NAMES[product_country]
                        selected_items.append(f"{product['emoji']} {product['name']} ({country_name_in_product}) - {product['price']:.2f}฿ x {qty} = {item_total:.2f}฿")
                    else:
                        selected_items.append(f"{product['emoji']} {product['name']} - {product['price']:.2f}฿ x {qty} = {item_total:.2f}฿")
        
        # เพิ่มรายการสินค้าที่เลือกไว้ใน content
        if selected_items:
            content_message += f"\n\n📝 รายการที่เลือก:\n" + "\n".join(selected_items) + f"\n\n💵 ยอดรวม: {total_price:.2f}฿"
        
        # ตรวจสอบว่า interaction ถูก defer แล้วหรือไม่
        if interaction.response.is_done():
            # ถ้า defer แล้ว ให้ใช้ message.edit ได้เลย
            await interaction.message.edit(content=content_message, view=new_view)
        else:
            # ถ้ายังไม่ได้ defer ให้ใช้ defer ก่อน
            await interaction.response.defer()
            # ใช้ message.edit แทน response.edit_message เพื่อให้กดหลายครั้งได้    
            await interaction.message.edit(content=content_message, view=new_view)
        
    async def prev_page_callback(self, interaction: discord.Interaction):
        """Callback for previous page button"""
        # คำนวณหน้าใหม่
        new_page = max(0, self.page - 1)
        
        # คำนวณหน้ารวม
        total_products = len(load_products(self.country, self.current_category))
        total_pages = (total_products - 1) // self.products_per_page + 1
        
        if interaction.response.is_done():
            # ถ้าตอบกลับไปแล้ว ให้ใช้ Edit Message
            new_view = CategoryShopView(
                self.all_categories,
                current_category=self.current_category,
                country=self.country,
                quantities=self.quantities,
                page=new_page,
                showing_all_countries=self.showing_all_countries,
                all_products=self.all_products  # ส่งข้อมูลสินค้าทั้งหมดไปด้วย
            )
            
            # โอนย้ายข้อมูลสำคัญจาก view ปัจจุบันไปยัง view ใหม่
            self._transfer_data_to_new_view(new_view)
            
            # สร้างข้อความที่จะแสดงพร้อมรายการที่เลือก
            display_message = self._generate_content_with_selected_items(new_view)
            
            await interaction.message.edit(content=display_message, view=new_view)
        else:
            # ถ้ายังไม่ได้ตอบกลับ
            await interaction.response.defer()
            await self.go_to_page(interaction, new_page + 1)  # +1 เพราะ UI นับเริ่มจาก 1 แต่โค้ดนับเริ่มจาก 0
    
    async def next_page_callback(self, interaction: discord.Interaction):
        """Callback for next page button"""
        # คำนวณหน้าใหม่
        total_products = len(load_products(self.country, self.current_category))
        total_pages = (total_products - 1) // self.products_per_page + 1
        new_page = min(self.page + 1, total_pages - 1)
        
        if interaction.response.is_done():
            # ถ้าตอบกลับไปแล้ว ให้ใช้ Edit Message
            new_view = CategoryShopView(
                self.all_categories,
                current_category=self.current_category,
                country=self.country,
                quantities=self.quantities,
                page=new_page,
                showing_all_countries=self.showing_all_countries,
                all_products=self.all_products  # ส่งข้อมูลสินค้าทั้งหมดไปด้วย
            )
            
            # โอนย้ายข้อมูลสำคัญจาก view ปัจจุบันไปยัง view ใหม่
            self._transfer_data_to_new_view(new_view)
            
            # สร้างข้อความที่จะแสดงพร้อมรายการที่เลือก
            display_message = self._generate_content_with_selected_items(new_view)
            
            await interaction.message.edit(content=display_message, view=new_view)
        else:
            # ถ้ายังไม่ได้ตอบกลับ
            await interaction.response.defer()
            await self.go_to_page(interaction, new_page + 1)  # +1 เพราะ UI นับเริ่มจาก 1 แต่โค้ดนับเริ่มจาก 0
    
    def _transfer_data_to_new_view(self, new_view):
        """ส่งต่อข้อมูลสำคัญจาก view ปัจจุบันไปยัง view ใหม่"""
        # ส่งต่อข้อมูลสินค้าทั้งหมด
        if hasattr(self, 'all_products') and self.all_products:
            new_view.all_products = self.all_products
            
        # ส่งต่อข้อมูลปริมาณสินค้าที่เลือก
        if hasattr(self, 'quantities') and self.quantities:
            for product_id, qty in self.quantities.items():
                if qty > 0:  # เฉพาะรายการที่มีการเลือก
                    new_view.quantities[product_id] = qty
        
        return new_view
        
    def _generate_content_with_selected_items(self, view):
        """สร้างข้อความที่จะแสดงพร้อมรายการที่เลือก"""
        # ดึงข้อมูลชื่อหมวดหมู่และประเทศในภาษาไทย
        category_name = CATEGORY_NAMES.get(self.current_category, self.current_category)
        country_name = COUNTRY_NAMES.get(self.country, self.country)
        
        # สร้างข้อความแสดงผลตามสถานะการแสดงประเทศ
        if self.showing_all_countries:
            content_message = f"🛍️ สินค้าในหมวด `{category_name}`"
        else:
            content_message = f"🛍️ สินค้าในประเทศ `{country_name}` หมวด `{category_name}`"
        
        # โหลดสินค้าและตรวจสอบรายการที่เลือกจากทุกประเทศและทุกหมวดหมู่
        selected_item_summary_lines = []
        total_selected = 0
        
        # อ่านประวัติการเลือกสินค้าจากทุกประเทศและทุกหมวดหมู่
        for country_code in COUNTRIES:
            for category in self.all_categories:
                # โหลดสินค้าในประเทศและหมวดหมู่นี้
                country_category_products = load_products(country_code, category)
                
                # ตรวจสอบว่ามีสินค้าที่เลือกในประเทศและหมวดหมู่นี้หรือไม่
                for product in country_category_products:
                    if 'id' in product:
                        qty = self.quantities.get(product['id'], 0)
                        if qty > 0:
                            item_total = product['price'] * qty
                            total_selected += item_total
                            
                            # ดึงชื่อประเทศที่สินค้าอยู่ (ถ้ามี)
                            product_country = product.get('country', '')
                            if product_country in COUNTRY_NAMES:
                                country_name_in_product = COUNTRY_NAMES[product_country]
                                selected_item_summary_lines.append(f"{product['emoji']} {product['name']} ({country_name_in_product}) - {product['price']:.2f}฿ x {qty} = {item_total:.2f}฿")
                            else:
                                selected_item_summary_lines.append(f"{product['emoji']} {product['name']} - {product['price']:.2f}฿ x {qty} = {item_total:.2f}฿")
        
        # เพิ่มรายการสินค้าที่เลือกไว้ใน content
        if selected_item_summary_lines:
            content_message += f"\n\n📝 รายการที่เลือก:\n" + "\n".join(selected_item_summary_lines) + f"\n\n💵 ยอดรวม: {total_selected:.2f}฿"
            
        return content_message

class CategoryLabel(Button):
    """Non-interactive button that serves as a category label"""
    def __init__(self, category, row=0):
        super().__init__(
            label=f"หมวด {category}", 
            style=discord.ButtonStyle.secondary,
            disabled=True,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        pass

class ProductQuantityModal(Modal):
    """Modal for entering product quantity in shop view"""
    def __init__(self, product, view):
        super().__init__(title=f"จำนวน {product['name']}")
        self.product = product
        # ตรวจสอบว่ามี id ใน product หรือไม่
        self.product_id = product.get('id', f"{product.get('country', '')}_"
                                          f"{product.get('category', '')}_"
                                          f"{product['name']}")
        self.shop_view = view
        
        # Create text input for quantity
        self.quantity_input = TextInput(
            label=f"ใส่จำนวน {product['name']} ที่ต้องการ",
            placeholder="ใส่จำนวน",
            required=True,
            min_length=1,
            max_length=10,
            default="1"
        )
        self.add_item(self.quantity_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Convert input to integer
            quantity = int(self.quantity_input.value)
            if quantity < 0:
                await interaction.response.send_message("❌ จำนวนต้องมากกว่าหรือเท่ากับ 0", ephemeral=True)
                return
                
            # Set the quantity in the view
            self.shop_view.quantities[self.product_id] = quantity
            
            # Create summary of selected items - track which products we've already shown
            summary_lines = []
            total = 0
            seen_product_ids = set()
            
            for product in self.shop_view.all_products:
                # ตรวจสอบและสร้าง id ถ้าไม่มี
                if 'id' not in product:
                    product['id'] = f"{product.get('country', '')}_" \
                                   f"{product.get('category', '')}_" \
                                   f"{product['name']}"
                
                # ตรวจสอบว่าเคยแสดงสินค้านี้ไปแล้วหรือไม่
                if product['id'] in seen_product_ids:
                    continue
                
                seen_product_ids.add(product['id'])
                qty = self.shop_view.quantities.get(product['id'], 0)
                if qty > 0:
                    item_total = product['price'] * qty
                    total += item_total
                    
                    # เพิ่มชื่อประเทศในรายการสินค้า
                    country_code = product.get('country', '')
                    # แปลงรหัสประเทศเดิมถ้าจำเป็น
                    if country_code in COUNTRY_CODES:
                        country_code = COUNTRY_CODES[country_code]
                    country_name = COUNTRY_NAMES.get(country_code, '')
                    
                    if country_name:
                        summary_lines.append(f"{product['emoji']} {product['name']} ({country_name}) - {product['price']:.2f}฿ x {qty} = {item_total:.2f}฿")
                    else:
                        summary_lines.append(f"{product['emoji']} {product['name']} - {product['price']:.2f}฿ x {qty} = {item_total:.2f}฿")
            
            # Current category being displayed
            current_category = self.shop_view.current_category
            
            # Update message with current cart
            content = f"🛍️ สินค้าในหมวด `{current_category}`:"
            if summary_lines:
                content += f"\n\n📝 รายการที่เลือก:\n" + "\n".join(summary_lines) + f"\n\n💵 ยอดรวม: {total:.2f}฿"
            
            await interaction.response.edit_message(content=content, view=self.shop_view)
            
        except ValueError:
            await interaction.response.send_message("❌ กรุณาใส่จำนวนเป็นตัวเลขเท่านั้น", ephemeral=True)

class ProductButton(Button):
    """Button for products in shop view"""
    def __init__(self, product, row=0):
        self.product = product
        # ตรวจสอบและสร้าง product id หากไม่มี
        product_id = product.get('id')
        if not product_id:
            product_id = f"{product.get('country', '')}_" \
                        f"{product.get('category', '')}_" \
                        f"{product['name']}"
            product['id'] = product_id
            
        super().__init__(
            label=f"{product['emoji']} {product['name']} - {product['price']:.2f}฿", 
            style=discord.ButtonStyle.primary,
            custom_id=f"product_{product_id}",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        
        # Show modal for quantity input
        modal = ProductQuantityModal(self.product, view)
        await interaction.response.send_modal(modal)

class ResetCartButton(Button):
    """Button to reset the cart in shop view"""
    def __init__(self):
        super().__init__(
            label="🗑️ ล้างตะกร้า", 
            style=discord.ButtonStyle.danger,
            custom_id="reset_cart"
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        # Reset all quantities
        for product_id in view.quantities:
            view.quantities[product_id] = 0
        
        # ตรวจสอบและดึงข้อมูลสำหรับข้อความแสดงผล
        current_category = getattr(view, 'current_category', "ไม่ระบุหมวด")
        country = getattr(view, 'country', "1")
        showing_all_countries = getattr(view, 'showing_all_countries', False)
        
        # ดึงชื่อหมวดหมู่และประเทศในภาษาไทย
        category_name = CATEGORY_NAMES.get(current_category, current_category)
        country_name = COUNTRY_NAMES.get(country, country)
        
        # สร้างข้อความแสดงผลตามสถานะการแสดงประเทศ
        if showing_all_countries:
            content_message = f"🛍️ สินค้าในหมวด `{category_name}`"
        else:
            content_message = f"🛍️ สินค้าในประเทศ `{country_name}` หมวด `{category_name}`"
        
        await interaction.response.edit_message(
            content=content_message, 
            view=view
        )

class ConfirmButton(Button):
    """Button to confirm the purchase"""
    def __init__(self, products):
        self.products = products
        super().__init__(
            label="✅ ยืนยันการซื้อ", 
            style=discord.ButtonStyle.success,
            custom_id="confirm_purchase"
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        
        # ตรวจสอบว่า view มี all_products หรือไม่ (สำหรับ CategoryShopView)
        products_to_check = []
        if hasattr(view, 'all_products') and view.all_products:
            products_to_check = view.all_products  # ใช้สินค้าทั้งหมดจาก view
        else:
            products_to_check = self.products  # ใช้สินค้าที่ส่งเข้ามาตอนสร้าง button
        
        # Calculate total and prepare items list
        total_price = 0
        items = []
        lines = []
        
        # ตรวจสอบว่า view มี attribute quantities หรือไม่
        if not hasattr(view, 'quantities'):
            await interaction.response.send_message("❗ เกิดข้อผิดพลาด: ไม่พบข้อมูลปริมาณสินค้า", ephemeral=True)
            return
            
        for product in products_to_check:
            # ตรวจสอบว่า product มี id หรือไม่
            if 'id' not in product:
                if 'name' in product and ('country' in product or 'category' in product):
                    product['id'] = f"{product.get('country', '')}_" \
                                   f"{product.get('category', '')}_" \
                                   f"{product['name']}"
                else:
                    continue  # ข้ามสินค้าที่ไม่มีข้อมูลเพียงพอ
                    
            qty = view.quantities.get(product['id'], 0)
            
            # Convert qty to int if needed
            try:
                if isinstance(qty, str) and qty.isdigit():
                    qty = int(qty)
                elif not isinstance(qty, int):
                    qty = 0
            except (ValueError, TypeError):
                qty = 0
                
            if qty > 0:
                total = product['price'] * qty
                total_price += total
                
                # ดึงชื่อประเทศจาก product
                country_code = product.get('country', '')
                # แปลงรหัสประเทศเดิมถ้าจำเป็น
                if country_code in COUNTRY_CODES:
                    country_code = COUNTRY_CODES[country_code]
                country_name = COUNTRY_NAMES.get(country_code, '')
                
                # เพิ่มข้อมูลประเทศในการบันทึกและแสดงผล
                items.append({
                    "name": product["name"], 
                    "qty": qty, 
                    "price": product["price"],
                    "country": country_name or country_code
                })
                
                if country_name:
                    lines.append(f"{product['emoji']} {product['name']} ({country_name}) - {product['price']:.2f}฿ x {qty} = {total:.2f}฿")
                else:
                    lines.append(f"{product['emoji']} {product['name']} - {product['price']:.2f}฿ x {qty} = {total:.2f}฿")
        
        # Check if cart is empty
        if total_price == 0:
            await interaction.response.send_message("❗ กรุณาเลือกสินค้าก่อน", ephemeral=True)
            return
            
        # Log purchase and create receipt
        log_purchase(interaction.user, items, total_price)
        summary = "\n".join(lines)
        
        # สร้างข้อมูลประเทศที่ลูกค้าซื้อสินค้า
        countries_purchased = set()
        for product in products_to_check:
            if 'id' in product and 'country' in product:
                # ตรวจจำนวนสินค้าที่เลือก
                product_qty = view.quantities.get(product['id'], 0)
                
                # แปลงเป็น int ถ้าจำเป็น
                try:
                    if isinstance(product_qty, str) and product_qty.isdigit():
                        product_qty = int(product_qty)
                    elif not isinstance(product_qty, int):
                        product_qty = 0
                except (ValueError, TypeError):
                    product_qty = 0
                
                if product_qty > 0:
                    country_code = product.get('country', '')
                    # แปลงรหัสประเทศเดิมถ้าจำเป็น
                    if country_code in COUNTRY_CODES:
                        country_code = COUNTRY_CODES[country_code]
                    # หาชื่อประเทศจาก country code
                    country_name = COUNTRY_NAMES.get(country_code, '')
                    if country_name:
                        countries_purchased.add(country_name)
                    
        countries_text = "ทุกประเทศ" if not countries_purchased else ", ".join(countries_purchased)
        
        # Create receipt embeds
        public_embed = discord.Embed(title="🧾 ใบเสร็จการสั่งซื้อ", color=0x00ff00)
        public_embed.set_author(name=f"ลูกค้า: {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
        public_embed.description = summary
        public_embed.add_field(name="ประเทศ", value=f"🌏 {countries_text}", inline=False)
        public_embed.add_field(name="ยอดรวม", value=f"💵 {total_price:.2f}฿", inline=False)
        
        # โหลด QR Code URL จาก MongoDB หรือไฟล์ config
        qr_code_url = ""
        try:
            # ลองโหลดจากไฟล์ config ก่อน
            with open(QRCODE_CONFIG_FILE, "r", encoding="utf-8") as f:
                qr_code_url = json.load(f).get("url", "")
            
            # ถ้าไม่มีข้อมูลในไฟล์ config ลองโหลดจาก MongoDB
            if not qr_code_url:
                qr_code_url = load_qrcode_url()
                
            # ถ้ายังไม่มีข้อมูล ใช้ค่าเริ่มต้น
            if not qr_code_url:
                qr_code_url = DEFAULT_QRCODE_URL
                
        except Exception as e:
            # ถ้าเกิดข้อผิดพลาดในการโหลด QR code URL ใช้ค่าเริ่มต้น
            print(f"ไม่สามารถโหลด QR Code URL: {str(e)}")
            qr_code_url = DEFAULT_QRCODE_URL
        
        # QR Code for payment
        qr_embed = discord.Embed(
            title="📲 กรุณาสแกน QR Code เพื่อชำระเงิน",
            description=f"**ลูกค้า:** {interaction.user.mention}\n**ยอดชำระ:** 💵 {total_price:.2f}฿",
            color=0x4f0099
        )
        qr_embed.set_image(url=qr_code_url)
        qr_embed.set_footer(text="กรุณาโอนเงินและแคปหลักฐานส่งให้แอดมิน")
        
        # สร้างปุ่ม "ส่งของแล้ว" สำหรับแอดมิน
        class DeliveredButtonNew(Button):
            def __init__(self, customer):
                self.customer = customer
                super().__init__(label="✅ ส่งของแล้ว (สำหรับแอดมิน)", style=discord.ButtonStyle.success)
            
            async def callback(self, interaction):
                # ตรวจสอบว่าเป็นแอดมินหรือไม่
                if interaction.user.guild_permissions.administrator:
                    # โหลดข้อความขอบคุณจากไฟล์คอนฟิก
                    thank_you_message = load_thank_you_message()
                    
                    # ส่งข้อความขอบคุณตามที่กำหนดไว้ในคำสั่ง !ty
                    await interaction.response.send_message(f"{self.customer.mention} {thank_you_message}", ephemeral=False)
                    
                    # ปิดการใช้งานปุ่มหลังจากกดแล้ว
                    self.disabled = True
                    if self.view:
                        await interaction.message.edit(view=self.view)
                else:
                    await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้ปุ่มนี้ (เฉพาะแอดมินเท่านั้น)", ephemeral=True)
        
        # สร้าง View สำหรับปุ่ม
        admin_view = View()
        
        # เพิ่มปุ่มในการแสดงผล
        delivered_button = DeliveredButtonNew(interaction.user)
        
        # เพิ่มปุ่มในแสดงผล
        admin_view.add_item(delivered_button)
        
        # Send receipt with admin button
        await interaction.response.send_message(embeds=[public_embed, qr_embed], view=admin_view)
        
        # Reset cart
        for product_id in view.quantities:
            view.quantities[product_id] = 0
        
        # ตรวจสอบและดึงข้อมูลสำหรับข้อความแสดงผล
        current_category = getattr(view, 'current_category', "ไม่ระบุหมวด")
        country = getattr(view, 'country', "1")
        showing_all_countries = getattr(view, 'showing_all_countries', False)
        
        # ดึงชื่อหมวดหมู่และประเทศในภาษาไทย
        category_name = CATEGORY_NAMES.get(current_category, current_category)
        country_name = COUNTRY_NAMES.get(country, country)
        
        # สร้างข้อความแสดงผลตามสถานะการแสดงประเทศ
        if showing_all_countries:
            content_message = f"🛍️ สินค้าในหมวด `{category_name}`"
        else:
            content_message = f"🛍️ สินค้าในประเทศ `{country_name}` หมวด `{category_name}`"
            
        await interaction.message.edit(content=content_message, view=view)



class ViewSelectedCategoriesButton(Button):
    """Button to view products from selected categories"""
    def __init__(self):
        super().__init__(
            label="ดูสินค้าที่เลือก", 
            style=discord.ButtonStyle.primary,
            custom_id="view_selected",
            row=3
        )
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        
        if not view.selected_categories:
            await interaction.response.send_message("❌ กรุณาเลือกอย่างน้อยหนึ่งหมวดหมู่", ephemeral=True)
            return
        
        # Create a shop view with products from first selected category
        first_category = view.selected_categories[0]
        shop_view = CategoryShopView(CATEGORIES, current_category=first_category)
        
        if not shop_view.all_products:
            await interaction.response.send_message("❌ ไม่มีสินค้าในหมวดหมู่ที่เลือก", ephemeral=True)
            return
            
        # Send new message with product buttons
        await interaction.response.send_message(
            content=f"🛍️ สินค้าในหมวด `{first_category}`", 
            view=shop_view
        )

class CategoryButton(Button):
    """Button for single category selection"""
    def __init__(self, category, label, emoji, row=0):
        self.category = category
        super().__init__(
            label=label, 
            emoji=emoji,
            style=discord.ButtonStyle.secondary,
            custom_id=f"category_{category}",
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        # Create a new view with the selected category
        view = ShopView(category=self.category)
        
        if len(view.products) == 0:
            await interaction.response.send_message(f"❌ ไม่มีสินค้าในหมวด `{self.category}`", ephemeral=True)
            return
            
        await interaction.response.edit_message(
            content=f"🛍️ หมวด `{self.category}` - เลือกสินค้าที่คุณต้องการ:", 
            view=view
        )

class ShopView(View):
    """Main shop view with product buttons"""
    def __init__(self, category=None):
        super().__init__(timeout=None)
        
        self.current_category = category
        
        # Show category buttons if no category is selected
        if category is None:
            # Add category buttons in first row
            self.add_item(CategoryButton("money", "เงิน", "💰", row=0))
            self.add_item(CategoryButton("weapon", "อาวุธ", "🔫", row=0))
            self.add_item(CategoryButton("item", "ไอเทม", "🧪", row=0))
            
            # Add more category buttons in second row
            self.add_item(CategoryButton("car", "รถยนต์", "🚗", row=1)) 
            self.add_item(CategoryButton("fashion", "แฟชั่น", "👒", row=1))
            self.add_item(CategoryButton("rentcar", "เช่ารถ", "🚙", row=1))
        
        # Load products from category file if specified
        self.products = load_products(category)
        self.quantities = [0] * len(self.products)
        
        # Create buttons for each product
        for idx, product in enumerate(self.products):
            self.add_item(LegacyProductButton(idx, self.products))
            
        # Add reset and confirm buttons for shopping cart
        if category is not None:
            self.add_item(ResetButton())
            self.add_item(ConfirmButton(self.products))
            
            # Add back button to return to categories
            self.add_item(BackButton())

class LegacyProductButton(Button):
    """Button for each product in the shop (original implementation)"""
    def __init__(self, index, products):
        self.index = index
        product = products[index]
        label = f"{product['emoji']} {product['name']} - {product['price']:.2f}฿"
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id=f"product_{index}")

    async def callback(self, interaction: discord.Interaction):
        view: ShopView = self.view
        
        # Create modal for quantity input
        modal = QuantityModal(self.index, view.products[self.index])
        await interaction.response.send_modal(modal)
        # Wait for modal to be submitted
        await modal.wait()
        
        if modal.quantity is not None:
            # Update quantity in view
            view.quantities[self.index] = modal.quantity
            
            # Generate summary of selected items
            lines = []
            for i, qty in enumerate(view.quantities):
                if qty > 0:
                    p = view.products[i]
                    lines.append(f"{p['emoji']} {p['name']} - {p['price']:.2f}฿ x {qty} = {p['price'] * qty:.2f}฿")
            
            summary = "\n".join(lines) or "ยังไม่ได้เลือกสินค้า"
            total = sum(view.products[i]['price'] * qty for i, qty in enumerate(view.quantities))
            
            message = f"🛍️ รายการที่เลือก:\n{summary}\n\n💵 ยอดรวม: {total:.2f}฿"
            await interaction.message.edit(content=message, view=view)

class BackButton(Button):
    """Button to go back to category selection"""
    def __init__(self):
        super().__init__(
            label="กลับไปหน้าหมวดหมู่", 
            style=discord.ButtonStyle.secondary,
            custom_id="back_button",
            row=4
        )
    
    async def callback(self, interaction: discord.Interaction):
        # Create a new view with category buttons
        view = ShopView(category=None)
        await interaction.response.edit_message(
            content="📋 เลือกหมวดหมู่สินค้า:", 
            view=view
        )

class ResetButton(Button):
    """Button to reset the cart"""
    def __init__(self):
        super().__init__(label="🗑️ ล้างตะกร้า", style=discord.ButtonStyle.danger, custom_id="reset")

    async def callback(self, interaction: discord.Interaction):
        view: ShopView = self.view
        view.quantities = [0] * len(view.products)
        await interaction.response.edit_message(content="🛍️ รายการที่เลือก:\nยังไม่ได้เลือกสินค้า", view=view)

class LegacyConfirmButton(Button):
    """Button to confirm the purchase (legacy version)"""
    def __init__(self, products):
        super().__init__(label="✅ ยืนยันการซื้อ", style=discord.ButtonStyle.success, custom_id="confirm")
        self.products = products
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        # Use a dictionary-based quantities system for CategoryShopView
        if hasattr(view, 'all_products') and isinstance(view.quantities, dict):
            # This is a CategoryShopView with dictionary quantities
            total_price = 0
            selected_products = []
            
            # Loop through all products
            for product in view.all_products:
                # สร้าง ID สินค้าถ้ายังไม่มี
                if 'id' not in product:
                    product['id'] = f"{product.get('country', '')}_" \
                                   f"{product.get('category', '')}_" \
                                   f"{product['name']}"
                
                product_id = product['id']
                qty = view.quantities.get(product_id, 0)
                
                # Convert qty to int if needed
                try:
                    if isinstance(qty, str) and qty.isdigit():
                        qty = int(qty)
                    elif not isinstance(qty, int):
                        qty = 0
                except (ValueError, TypeError):
                    qty = 0
                
                if qty > 0:  # Check if qty is greater than 0
                    # Convert price to int if needed
                    price = product['price']
                    if isinstance(price, str) and price.isdigit():
                        price = int(price)
                    
                    total_price += price * qty
                    selected_products.append((product, qty))
            
            # No selected products
            if total_price == 0 or not selected_products:
                await interaction.response.send_message("❗ กรุณาเลือกสินค้าก่อน", ephemeral=True)
                return
                
            # Generate lines for receipt
            lines = []
            items = []
            for product, qty in selected_products:
                price = product['price']
                if isinstance(price, str) and price.isdigit():
                    price = int(price)
                
                total = price * qty
                # ดึงชื่อประเทศแบบภาษาไทย
                country_code = product.get('country', '1')  # เปลี่ยนจาก 'thailand' เป็น '1'
                # แปลงรหัสประเทศเดิมถ้าจำเป็น
                if country_code in COUNTRY_CODES:
                    country_code = COUNTRY_CODES[country_code]
                country_thai = COUNTRY_NAMES.get(country_code, country_code)
                
                # เพิ่มชื่อประเทศลงในใบเสร็จ
                lines.append(f"{product['emoji']} {product['name']} ({country_thai}) - {price:.2f}฿ x {qty} = {total:.2f}฿")
                items.append({
                    "name": product["name"], 
                    "qty": qty, 
                    "price": price,
                    "country": country_code,
                    "country_thai": country_thai
                })
        else:
            # Legacy implementation for ShopView with list quantities
            total_price = 0
            for i, qty in enumerate(view.quantities):
                # Try to convert qty to int safely
                try:
                    if isinstance(qty, str) and qty.isdigit():
                        qty_val = int(qty)
                    else:
                        qty_val = qty
                except (ValueError, TypeError):
                    continue  # Skip invalid quantities
                    
                if qty_val > 0:
                    # Convert price safely
                    try:
                        price_str = self.products[i]['price']
                        price = int(price_str) if isinstance(price_str, str) else price_str
                        total_price += price * qty_val
                    except (ValueError, TypeError, IndexError, KeyError):
                        continue  # Skip invalid prices
        
        # Check if cart is empty
        if total_price == 0:
            await interaction.response.send_message("❗ กรุณาเลือกสินค้าก่อน", ephemeral=True)
            return
            
        # Receipt lines and items were already generated in the code above
        
        # Log the purchase and generate receipt
        try:
            log_purchase(interaction.user, items, total_price)
            summary = "\n".join(lines)
            embed = discord.Embed(
                title="🧾 ใบเสร็จรับเงิน",
                description=f"**ลูกค้า:** {interaction.user.mention}\n**วันที่:** {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                color=0x00ff00
            )
            embed.add_field(name="รายการสินค้า", value=summary, inline=False)
            embed.add_field(name="ยอดรวม", value=f"💵 {total_price:.2f}฿", inline=False)
            embed.set_footer(text="ขอบคุณที่ใช้บริการ! 🙏")
            
            # แสดงใบเสร็จสำหรับผู้ซื้อ (แสดงเฉพาะผู้ซื้อเท่านั้น)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # สร้างใบเสร็จสำหรับแสดงในแชทสาธารณะและให้แอดมินเห็น
            public_embed = discord.Embed(
                title="🧾 ใบเสร็จรับเงิน",
                description=f"**ลูกค้า:** {interaction.user.mention}\n**วันที่:** {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                color=0x00ff00
            )
            public_embed.add_field(name="รายการสินค้า", value=summary, inline=False)
            public_embed.add_field(name="ยอดรวม", value=f"💵 {total_price:.2f}฿", inline=False)
            
            # แสดง QR Code สำหรับชำระเงิน
            qr_embed = discord.Embed(
                title="📲 กรุณาสแกน QR Code เพื่อชำระเงิน",
                description=f"**ลูกค้า:** {interaction.user.mention}\n**ยอดชำระ:** 💵 {total_price:.2f}฿",
                color=0x4f0099
            )
            qr_embed.set_footer(text="กรุณาสแกน QR Code ด้านล่างเพื่อชำระเงิน โอนเงินและแคปหลักฐานส่งให้แอดมิน")
            
            # สร้างปุ่ม "ส่งของแล้ว" สำหรับแอดมิน
            class DeliveredButton(Button):
                def __init__(self, customer):
                    self.customer = customer
                    super().__init__(label="✅ ส่งของแล้ว (สำหรับแอดมิน)", style=discord.ButtonStyle.success)
                
                async def callback(self, interaction):
                    # ตรวจสอบว่าเป็นแอดมินหรือไม่
                    if interaction.user.guild_permissions.administrator:
                        # โหลดข้อความขอบคุณจากไฟล์คอนฟิก
                        thank_you_message = load_thank_you_message()
                        
                        # ส่งข้อความขอบคุณตามที่กำหนดไว้ในคำสั่ง !ty
                        await interaction.response.send_message(f"{self.customer.mention} {thank_you_message}", ephemeral=False)
                        
                        # ปิดการใช้งานปุ่มหลังจากกดแล้ว
                        self.disabled = True
                        if self.view:  # ใช้ self.view แทน _view
                            await interaction.message.edit(view=self.view)
                    else:
                        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้ปุ่มนี้ (เฉพาะแอดมินเท่านั้น)", ephemeral=True)
            
            # สร้าง View สำหรับปุ่ม
            admin_view = View()
            
            # เพิ่มปุ่มในการแสดงผล
            delivered_button = DeliveredButton(interaction.user)
            
            # เพิ่มปุ่มในแสดงผล
            admin_view.add_item(delivered_button)
            
            # โหลดไฟล์ QR code จากฟังก์ชันที่เตรียมไว้
            qr_file = await get_qrcode_discord_file()
            
            # ส่งทั้งใบเสร็จสาธารณะและ QR Code ในข้อความเดียวกันพร้อมปุ่มแอดมิน
            print("กำลังส่งข้อความพร้อมปุ่ม ส่งของแล้ว (สำหรับแอดมิน)")
            await interaction.followup.send(embeds=[public_embed, qr_embed], file=qr_file, view=admin_view)
            
            # Reset the cart based on view type
            if hasattr(view, 'products'):
                # Old ShopView with list-based quantities
                view.quantities = [0] * len(view.products)
                await interaction.message.edit(content="🛍️ รายการที่เลือก:\nยังไม่ได้เลือกสินค้า", view=view)
            elif hasattr(view, 'all_products') and isinstance(view.quantities, dict):
                # CategoryShopView with dictionary-based quantities
                for key in list(view.quantities.keys()):
                    view.quantities[key] = 0
                current_category = view.current_category
                await interaction.message.edit(content=f"🛍️ สินค้าในหมวด `{current_category}`", view=view)
        except Exception as e:
            await interaction.response.send_message(f"❌ เกิดข้อผิดพลาด: {str(e)}", ephemeral=True)

async def auto_download_from_mongodb():
    """ดาวน์โหลดข้อมูลจาก MongoDB โดยอัตโนมัติเมื่อเริ่มต้นบอท"""
    try:
        from db_operations import (load_products_async, load_countries, load_categories,
                                 load_qrcode_url_async, load_thank_you_message_async)
        from mongodb_config import client
        
        # ตรวจสอบการเชื่อมต่อ MongoDB
        if client is None:
            print("❌ ไม่สามารถเชื่อมต่อกับ MongoDB ได้")
            return False
        
        print("🔄 กำลังดาวน์โหลดข้อมูลจาก MongoDB อัตโนมัติ...")
        
        # 1. ดาวน์โหลดข้อมูลประเทศ
        countries_data = await load_countries()
        if countries_data:
            # อัพเดตตัวแปรโกลบอล
            global COUNTRIES, COUNTRY_NAMES, COUNTRY_EMOJIS, COUNTRY_CODES
            if "countries" in countries_data:
                COUNTRIES = countries_data["countries"]
            if "country_names" in countries_data:
                COUNTRY_NAMES = countries_data["country_names"]
            if "country_emojis" in countries_data:
                COUNTRY_EMOJIS = countries_data["country_emojis"]
            if "country_codes" in countries_data:
                COUNTRY_CODES = countries_data["country_codes"]
            
            # บันทึกลงไฟล์
            with open(COUNTRIES_FILE, "w", encoding="utf-8") as f:
                json.dump(countries_data, f, ensure_ascii=False, indent=2)
            print("✅ ดาวน์โหลดข้อมูลประเทศสำเร็จ")
        
        # 2. ดาวน์โหลดข้อมูลหมวดหมู่
        categories_data = await load_categories()
        if categories_data:
            # อัพเดตตัวแปรโกลบอล
            global CATEGORY_NAMES, CATEGORY_EMOJIS
            if "category_names" in categories_data:
                CATEGORY_NAMES = categories_data["category_names"]
            if "category_emojis" in categories_data:
                CATEGORY_EMOJIS = categories_data["category_emojis"]
            
            # บันทึกลงไฟล์
            with open(SCRIPT_DIR / "categories_config.json", "w", encoding="utf-8") as f:
                json.dump(categories_data, f, ensure_ascii=False, indent=2)
            print("✅ ดาวน์โหลดข้อมูลหมวดหมู่สำเร็จ")
        
        # 3. ดาวน์โหลดข้อมูลสินค้า
        all_products = await load_products_async()
        if all_products:
            products_count = len(all_products)
            
            # บันทึกลงในไฟล์ products.json
            with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
                json.dump(all_products, f, ensure_ascii=False, indent=2)
            
            # บันทึกลงในโฟลเดอร์ categories แยกตามหมวดหมู่และประเทศ
            # สร้างโครงสร้างข้อมูลสำหรับแยกสินค้าตามประเทศและหมวดหมู่
            categorized_products = {}
            
            for product in all_products:
                country = product.get("country", "1")
                category = product.get("category", "money")
                
                if country not in categorized_products:
                    categorized_products[country] = {}
                
                if category not in categorized_products[country]:
                    categorized_products[country][category] = []
                
                # สร้างสำเนาของสินค้าที่ไม่มี country และ category
                product_copy = product.copy()
                if "country" in product_copy:
                    del product_copy["country"]
                if "category" in product_copy:
                    del product_copy["category"]
                if "_id" in product_copy:
                    del product_copy["_id"]
                
                categorized_products[country][category].append(product_copy)
            
            # บันทึกไฟล์แยกตามประเทศและหมวดหมู่
            categories_dir = SCRIPT_DIR / "categories"
            for country, categories in categorized_products.items():
                country_dir = categories_dir / country
                country_dir.mkdir(parents=True, exist_ok=True)
                
                for category, products in categories.items():
                    category_file = country_dir / f"{category}.json"
                    with open(category_file, "w", encoding="utf-8") as f:
                        json.dump(products, f, ensure_ascii=False, indent=2)
            print(f"✅ ดาวน์โหลดข้อมูลสินค้าสำเร็จ ({products_count} รายการ)")
        
        # 4. ดาวน์โหลด QR Code URL
        try:
            qrcode_url = await load_qrcode_url_async()
            if qrcode_url:
                with open(QRCODE_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump({"url": qrcode_url}, f, ensure_ascii=False, indent=2)
                print("✅ ดาวน์โหลด QR Code URL สำเร็จ")
        except Exception as e:
            print(f"⚠️ ไม่สามารถดาวน์โหลด QR Code URL: {str(e)}")
        
        # 5. ดาวน์โหลดข้อความขอบคุณ
        try:
            thank_you_message = await load_thank_you_message_async()
            if thank_you_message:
                with open(SCRIPT_DIR / "thank_you_config.json", "w", encoding="utf-8") as f:
                    json.dump({"message": thank_you_message}, f, ensure_ascii=False, indent=2)
                print("✅ ดาวน์โหลดข้อความขอบคุณสำเร็จ")
        except Exception as e:
            print(f"⚠️ ไม่สามารถดาวน์โหลดข้อความขอบคุณ: {str(e)}")
            
        print("✅ ดาวน์โหลดข้อมูลจาก MongoDB อัตโนมัติเสร็จสิ้น")
        return True
        
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการดาวน์โหลดข้อมูลอัตโนมัติ: {str(e)}")
        return False

# ฟังก์ชัน task ที่จะทำงานทุก 30 นาที
@tasks.loop(minutes=30)
async def auto_download_task():
    """ทาสค์ที่จะดาวน์โหลดข้อมูลจาก MongoDB ทุก 30 นาที"""
    print(f"⏱️ ทาสค์อัตโนมัติ: กำลังดาวน์โหลดข้อมูลจาก MongoDB... ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    try:
        success = await auto_download_from_mongodb()
        if success:
            print(f"✅ ทาสค์อัตโนมัติ: ดาวน์โหลดข้อมูลสำเร็จ ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        else:
            print(f"⚠️ ทาสค์อัตโนมัติ: ไม่สามารถดาวน์โหลดข้อมูลได้ ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
    except Exception as e:
        print(f"❌ ทาสค์อัตโนมัติ: เกิดข้อผิดพลาด {str(e)} ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")

@bot.event
async def on_ready():
    """Event triggered when the bot is ready"""
    print(f"Bot is ready! Logged in as {bot.user}")
    
    # ดาวน์โหลดข้อมูลจาก MongoDB โดยอัตโนมัติตอนเริ่มต้น
    try:
        success = await auto_download_from_mongodb()
        if success:
            print("🔄 ดาวน์โหลดข้อมูลจาก MongoDB เรียบร้อยแล้ว")
        else:
            print("⚠️ ไม่สามารถดาวน์โหลดข้อมูลจาก MongoDB โดยอัตโนมัติ")
            # โหลดข้อมูลจากไฟล์ท้องถิ่นแทน
            load_categories()
    except Exception as e:
        print(f"⚠️ เกิดข้อผิดพลาดในการดาวน์โหลดอัตโนมัติ: {str(e)}")
        # โหลดข้อมูลจากไฟล์ท้องถิ่นแทนในกรณีที่มีข้อผิดพลาด
        load_categories()
    
    # Create history file if it doesn't exist
    if not HISTORY_FILE.exists():
        HISTORY_FILE.touch()
        print(f"Created history file at {HISTORY_FILE}")
        
    # Create category folders for each country if they don't exist
    for country in COUNTRIES:
        country_dir = CATEGORIES_DIR / country
        if not country_dir.exists():
            country_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created country directory: {country_dir}")
    
    # บันทึก Target Channel ID เริ่มต้นไปยัง MongoDB
    try:
        current_target_id = load_target_channel_id()
        print(f"🎯 โหลด Target Channel ID: {current_target_id}")
    except Exception as e:
        print(f"⚠️ ไม่สามารถโหลด Target Channel ID: {str(e)}")
    
    # เริ่มทาสค์อัตโนมัติสำหรับดาวน์โหลดข้อมูลทุก 30 นาที
    if not auto_download_task.is_running():
        auto_download_task.start()
        print("⏱️ เริ่มทาสค์อัตโนมัติ: ดาวน์โหลดข้อมูลจาก MongoDB ทุก 30 นาที")
            
        # Create empty category files if they don't exist
        for category in CATEGORIES:
            category_file = country_dir / f"{category}.json"
            if not category_file.exists():
                with open(category_file, 'w', encoding='utf-8') as f:
                    f.write('[]')
                print(f"Created empty category file: {category_file}")
    
    # Register slash commands
    try:
        print("Registering slash commands...")
        # Shop Commands
        await bot.tree.sync()
        print("Slash commands registered successfully!")
    except Exception as e:
        print(f"Error registering slash commands: {e}")

@bot.command(name="money")
async def shop_money(ctx):
    """Command to open the money category shop"""
    await shop(ctx, "money")

@bot.command(name="เงิน")
async def shop_money_th(ctx):
    """Command to open the money category shop (Thai)"""
    await shop(ctx, "money")

@bot.command(name="weapon")
async def shop_weapon(ctx):
    """Command to open the weapon category shop"""
    await shop(ctx, "weapon")
    
@bot.command(name="อาวุธ")
async def shop_weapon_th(ctx):
    """Command to open the weapon category shop (Thai)"""
    await shop(ctx, "weapon")

@bot.command(name="item")
async def shop_item(ctx):
    """Command to open the item category shop"""
    await shop(ctx, "item")
    
@bot.command(name="ไอเทม")
async def shop_item_th(ctx):
    """Command to open the item category shop (Thai)"""
    await shop(ctx, "item")

@bot.command(name="story")
async def shop_story(ctx):
    """Command to open the story (combat items) category shop"""
    await shop(ctx, "story")
    
@bot.command(name="ไอเทมต่อสู้", aliases=["ต่อสู้"])
async def shop_story_th(ctx):
    """Command to open the story (combat items) category shop (Thai)"""
    await shop(ctx, "story")

@bot.command(name="car")
async def shop_car(ctx):
    """Command to open the car category shop"""
    await shop(ctx, "car")
    
@bot.command(name="รถ")
async def shop_car_th(ctx):
    """Command to open the car category shop (Thai)"""
    await shop(ctx, "car")

@bot.command(name="fashion")
async def shop_fashion(ctx):
    """Command to open the fashion category shop"""
    await shop(ctx, "fashion")
    
@bot.command(name="แฟชั่น")
async def shop_fashion_th(ctx):
    """Command to open the fashion category shop (Thai)"""
    await shop(ctx, "fashion")

@bot.command(name="เช่ารถ")
async def shop_rentcar(ctx):
    """Command to open the car rental category shop"""
    await shop(ctx, "rentcar")

@bot.command(name="ร้าน", aliases=["สินค้า", "shop"])
async def shop(ctx, ประเทศหรือหมวด: str = None, หมวด: str = None):
    """Command to open the shop
    
    Args:
        ประเทศหรือหมวด: Country or category name
        หมวด: Category name if first argument is country
    """
    # แสดงข้อมูลดีบัก
    print(f"shop command called with: ประเทศหรือหมวด={ประเทศหรือหมวด}, หมวด={หมวด}")
    # กรณีไม่ระบุอะไรเลย ให้แสดงปุ่มเลือกประเทศก่อน
    if ประเทศหรือหมวด is None:
        # สร้าง view แสดงปุ่มเลือกประเทศเท่านั้น
        view = discord.ui.View(timeout=None)
        
        # เพิ่มปุ่มสำหรับแต่ละประเทศ
        for i, country_code in enumerate(COUNTRIES):
            country_name = COUNTRY_NAMES[country_code]
            country_emoji = COUNTRY_EMOJIS.get(country_code, "🌏")
            
            # สร้างปุ่มประเทศ กำหนด row ไม่เกิน 5 ปุ่มต่อแถว
            button_row = 0 if i < 5 else 1
            country_button = discord.ui.Button(
                label=country_name,
                emoji=country_emoji,
                style=discord.ButtonStyle.primary,
                custom_id=f"country_{country_code}",
                row=button_row
            )
            
            # สร้าง closure เพื่อเก็บค่า country_code ให้แยกกันสำหรับแต่ละปุ่ม
            # ย้ายการสร้าง callback เข้าไปในฟังก์ชันอีกชั้นเพื่อแก้ปัญหา closure
            def create_callback_for_country(country_value):
                async def button_callback(interaction):
                    # ป้องกันการแสดงข้อความ "การโต้ตอบล้มเหลว"
                    await interaction.response.defer()
                    
                    # แสดงข้อมูลดีบัก
                    print(f"Selected country: {country_value}")
                    
                    # เรียกคำสั่ง shop อีกครั้งโดยระบุประเทศ
                    await shop(ctx, country_value)
                    
                    # ลบข้อความเดิมที่แสดงปุ่มเลือกประเทศ
                    await interaction.message.delete()
                    
                return button_callback
                
            # กำหนด callback ให้กับปุ่มนี้
            country_button.callback = create_callback_for_country(country_code)
            view.add_item(country_button)
        
        # แสดงข้อความให้เลือกประเทศ
        await ctx.send("🌏 กรุณาเลือกประเทศ:", view=view)
        return
    
    # กำหนดค่าเริ่มต้น
    country = "thailand"  # ประเทศไทยเป็นค่าเริ่มต้น
    category = "item"     # หมวดหมู่ไอเทมเป็นค่าเริ่มต้น
    
    # ตรวจสอบอาร์กิวเมนต์แรก
    if ประเทศหรือหมวด:
        # ถ้าเป็นชื่อประเทศ
        if ประเทศหรือหมวด.lower() in COUNTRIES:
            country = ประเทศหรือหมวด.lower()
            # ถ้ามีการระบุหมวดหมู่ในอาร์กิวเมนต์ที่สอง
            if หมวด and หมวด.lower() in CATEGORIES:
                category = หมวด.lower()
        # ถ้าเป็นชื่อหมวดหมู่
        elif ประเทศหรือหมวด.lower() in CATEGORIES:
            category = ประเทศหรือหมวด.lower()
        # ถ้าเป็นชื่อหมวดหมู่ภาษาไทย
        elif ประเทศหรือหมวด in ["เงิน", "อาวุธ", "ไอเทม", "รถ", "แฟชั่น", "เช่ารถ"]:
            # แปลงชื่อหมวดหมู่ภาษาไทยเป็นภาษาอังกฤษ
            thai_to_eng = {"เงิน": "money", "อาวุธ": "weapon", "ไอเทม": "item", 
                          "รถ": "car", "แฟชั่น": "fashion", "เช่ารถ": "rentcar"}
            category = thai_to_eng[ประเทศหรือหมวด]
        # ถ้าเป็นชื่อประเทศภาษาไทย
        elif ประเทศหรือหมวด in ["ไทย", "ญี่ปุ่น", "อเมริกา", "เกาหลี", "จีน"]:
            # แปลงชื่อประเทศภาษาไทยเป็นภาษาอังกฤษ
            thai_to_eng = {
                "ไทย": "thailand", 
                "ญี่ปุ่น": "japan", 
                "อเมริกา": "usa",
                "เกาหลี": "korea",
                "จีน": "china"
            }
            country = thai_to_eng[ประเทศหรือหมวด]
            # ถ้ามีการระบุหมวดหมู่ในอาร์กิวเมนต์ที่สอง
            if หมวด and หมวด.lower() in CATEGORIES:
                category = หมวด.lower()
        else:
            # แสดงข้อความแนะนำหากระบุอาร์กิวเมนต์ไม่ถูกต้อง
            countries_str = ", ".join([f"`{COUNTRY_NAMES[c]}`" for c in COUNTRIES])
            categories_str = ", ".join([f"`{CATEGORY_NAMES[c]}`" for c in CATEGORIES])
            await ctx.send(f"❌ ไม่พบประเทศหรือหมวดหมู่ที่ระบุ\nประเทศที่มี: {countries_str}\nหมวดหมู่ที่มี: {categories_str}")
            return
    
    # โหลดสินค้าตามประเทศและหมวดหมู่
    products = load_products(country, category)
    
    # ตรวจสอบว่ามีสินค้าในประเทศและหมวดหมู่นี้หรือไม่
    if not products:
        await ctx.send(f"❌ ไม่มีสินค้าในประเทศ `{COUNTRY_NAMES[country]}` หมวด `{CATEGORY_NAMES[category]}`")
        return
    
    # โหลดสินค้าทั้งหมดจากทุกประเทศและทุกหมวดหมู่
    all_products = []
    for c in COUNTRIES:
        for cat in CATEGORIES:
            c_products = load_products(c, cat)
            all_products.extend(c_products)
    
    # สร้าง view ที่แสดงสินค้าพร้อมปุ่มเลือกประเทศและหมวดหมู่
    view = CategoryShopView(CATEGORIES, current_category=category, country=country, showing_all_countries=False)
    
    # กำหนดค่า all_products ให้ view
    view.all_products = all_products
    
    # หากไม่มีสินค้าในร้านทั้งหมด
    if not all_products:
        await ctx.send(f"❌ ไม่มีสินค้าในร้าน")
        return
    
    # หาสินค้าในประเทศและหมวดหมู่ที่เลือก
    current_products = [p for p in all_products if p.get('country') == country and p.get('category') == category]
    
    # ตรวจสอบว่ามีสินค้าในประเทศและหมวดหมู่ที่เลือกหรือไม่
    if not current_products:
        await ctx.send(f"❌ ไม่มีสินค้าในประเทศ `{COUNTRY_NAMES[country]}` หมวด `{CATEGORY_NAMES[category]}`")
        return
    
    # แสดงชื่อร้านและสินค้า
    title = f"🛍️ สินค้าในประเทศ `{COUNTRY_NAMES[country]}` หมวด `{CATEGORY_NAMES[category]}`"
    await ctx.send(title, view=view)

@bot.command(name="เพิ่มสินค้า")
@commands.has_permissions(administrator=True)
async def add_multiple_products(ctx, *, ข้อมูล: str):
    """Command to add multiple products at once, each on a new line (Admin only)"""
    try:
        print(f"🔧 DEBUG: เพิ่มสินค้า called by {ctx.author} with data: {ข้อมูล}")
        
        # Split input by newlines
        lines = ข้อมูล.strip().split("\n")
        print(f"🔧 DEBUG: Split into {len(lines)} lines: {lines}")
        
        # Process each line as a product
        products_to_add = []
        error_lines = []
        
        for line_num, line in enumerate(lines, 1):
            # Skip empty lines
            if not line.strip():
                continue
                
            # Try to parse the line: format should be "emoji ชื่อ ราคา หมวด ประเทศ"
            parts = line.strip().split()
            
            if len(parts) < 3:
                error_lines.append(f"บรรทัดที่ {line_num}: ข้อมูลไม่ครบ ต้องมีอย่างน้อย [อีโมจิ ชื่อ ราคา]")
                continue
                
            # First item is the emoji
            emoji = parts[0]
            
            # Last items might be country and category, if enough parts
            if len(parts) >= 5:
                country = parts[-1]
                category = parts[-2]
                # Extract name as everything between emoji and price/category/country
                name = " ".join(parts[1:-3])
                price_str = parts[-3]
            elif len(parts) >= 4:
                country = "1"  # Default country (1 = ไทย)
                category = parts[-1]
                # Extract name as everything between emoji and price/category
                name = " ".join(parts[1:-2])
                price_str = parts[-2]
            else:
                # Default category and country if not provided
                country = "1"  # เปลี่ยนจาก "thailand" เป็น "1"
                category = "item"
                # Name is everything between emoji and price
                name = " ".join(parts[1:-1])
                price_str = parts[-1]
            
            # Convert price to float (support decimal point)
            try:
                price = float(price_str)
            except ValueError:
                error_lines.append(f"บรรทัดที่ {line_num}: ราคาต้องเป็นตัวเลขเท่านั้น (รองรับทศนิยม เช่น 99.50)")
                continue
                
            # Check if category is valid
            if category not in CATEGORIES:
                error_lines.append(f"บรรทัดที่ {line_num}: หมวดหมู่ '{category}' ไม่ถูกต้อง หมวดหมู่ที่รองรับ: {', '.join(CATEGORIES)}")
                continue
                
            # Create product dictionary
            product = {
                "name": name,
                "price": price,
                "emoji": emoji,
                "category": category,
                "country": country  # ใช้ค่าจากการวิเคราะห์หรือค่าเริ่มต้น
            }
            
            products_to_add.append(product)
        
        # If no valid products, return
        if not products_to_add:
            await ctx.send("❌ ไม่มีสินค้าที่ถูกต้องในข้อมูลที่ส่งมา")
            if error_lines:
                error_msg = "\n".join(error_lines[:10])
                if len(error_lines) > 10:
                    error_msg += f"\n... และอีก {len(error_lines) - 10} ข้อผิดพลาด"
                await ctx.send(f"ข้อผิดพลาด:\n```\n{error_msg}\n```")
            return
            
        # Add products using the batch function
        added_count, errors = batch_add_products(products_to_add)
        
        # Create response message
        if added_count > 0:
            embed = discord.Embed(
                title=f"✅ เพิ่มสินค้าสำเร็จ {added_count} รายการ",
                color=discord.Color.green()
            )
            
            # Add information about the products added
            added_details = []
            for product in products_to_add[:10]:  # Show up to 10 products
                added_details.append(f"{product['emoji']} {product['name']} - {product['price']:.2f}฿ (หมวด: {product['category']})")
                
            if added_details:
                if len(products_to_add) > 10:
                    added_details.append(f"... และอีก {len(products_to_add) - 10} รายการ")
                    
                embed.add_field(
                    name="📋 รายการสินค้าที่เพิ่ม",
                    value="\n".join(added_details),
                    inline=False
                )
            
            # Add error information if any
            if errors or error_lines:
                # Make sure errors is a list before concatenating
                errors_list = errors if isinstance(errors, list) else [errors] if errors else []
                all_errors = error_lines + errors_list
                error_text = "\n".join([f"- {error}" for error in all_errors[:10]])
                if len(all_errors) > 10:
                    error_text += f"\n... และอีก {len(all_errors) - 10} ข้อผิดพลาด"
                    
                embed.add_field(
                    name="⚠️ ข้อผิดพลาดบางส่วน",
                    value=error_text,
                    inline=False
                )
            
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="❌ ไม่สามารถเพิ่มสินค้าได้",
                color=discord.Color.red()
            )
            
            # Add error information
            # Make sure errors is a list before concatenating
            errors_list = errors if isinstance(errors, list) else [errors] if errors else []
            all_errors = error_lines + errors_list
            if all_errors:
                error_text = "\n".join([f"- {error}" for error in all_errors[:10]])
                if len(all_errors) > 10:
                    error_text += f"\n... และอีก {len(all_errors) - 10} ข้อผิดพลาด"
                    
                embed.add_field(
                    name="ข้อผิดพลาด",
                    value=error_text,
                    inline=False
                )
                
            # Add format example
            embed.add_field(
                name="📝 รูปแบบข้อมูลที่ถูกต้อง (แบบแยกบรรทัด)",
                value="```\n🔫 ปืนลูกซอง 15000 weapon\n🚗 รถเบนซ์ 50000 car\n```",
                inline=False
            )
                
            await ctx.send(embed=embed)
            
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

@bot.command(name="ลบสินค้า")
@commands.has_permissions(administrator=True)
async def remove_product(ctx, ชื่อ: str, หมวด: str = None, ประเทศ: str = "1"):
    """Command to remove a product (Admin only)
    
    Args:
        ชื่อ: ชื่อสินค้าที่ต้องการลบ
        หมวด: หมวดหมู่ที่สินค้าอยู่ (ถ้าระบุจะลบเฉพาะในหมวดนี้)
        ประเทศ: ประเทศที่สินค้าอยู่ (ตัวเลข 1-5 หรือรหัสประเทศเดิม)
    """
    try:
        # แปลงหมวดหมู่ภาษาไทยเป็นภาษาอังกฤษ
        if หมวด:
            if หมวด in ["เงิน", "อาวุธ", "ไอเทม", "รถ", "แฟชั่น", "เช่ารถ"]:
                thai_to_eng = {"เงิน": "money", "อาวุธ": "weapon", "ไอเทม": "item", 
                              "รถ": "car", "แฟชั่น": "fashion", "เช่ารถ": "rentcar"}
                หมวด = thai_to_eng.get(หมวด, หมวด)
                
            # ตรวจสอบว่าหมวดถูกต้อง
            if หมวด not in CATEGORIES:
                categories_str = ", ".join([f"`{cat}`" for cat in CATEGORIES])
                await ctx.send(f"❌ หมวดหมู่ '{หมวด}' ไม่ถูกต้อง หมวดหมู่ที่รองรับ: {categories_str}")
                return
        
        # แปลงประเทศภาษาไทยเป็นรหัสประเทศ
        if ประเทศ in ["ไทย", "ญี่ปุ่น", "อเมริกา", "เกาหลี", "จีน"]:
            thai_to_code = {"ไทย": "1", "ญี่ปุ่น": "2", "อเมริกา": "3", "เกาหลี": "4", "จีน": "5"}
            ประเทศ = thai_to_code[ประเทศ]
        # แปลงรหัสประเทศเดิมเป็นตัวเลข
        elif ประเทศ in COUNTRY_CODES:
            ประเทศ = COUNTRY_CODES[ประเทศ]
        
        # ตรวจสอบว่าประเทศถูกต้อง
        if ประเทศ not in COUNTRIES:
            countries_str = ", ".join([f"`{COUNTRY_NAMES[c]}`" for c in COUNTRIES])
            await ctx.send(f"❌ ประเทศไม่ถูกต้อง ประเทศที่รองรับ: {countries_str}")
            return
        
        if หมวด:
            # ถ้าระบุหมวด ให้โหลดสินค้าจากหมวดในประเทศที่ระบุ
            products = load_products(ประเทศ, หมวด)
            
            # ตรวจสอบว่ามีสินค้านี้หรือไม่
            product_to_delete = next((p for p in products if p["name"] == ชื่อ), None)
            if not product_to_delete:
                await ctx.send(f"❌ ไม่พบสินค้า '{ชื่อ}' ในหมวด '{CATEGORY_NAMES.get(หมวด, หมวด)}' ของประเทศ '{COUNTRY_NAMES[ประเทศ]}'")
                return
            
            # ลบสินค้าออกจากรายการ
            products = [p for p in products if p["name"] != ชื่อ]
            
            # บันทึกการเปลี่ยนแปลงลงไฟล์หมวดหมู่
            save_products(products, ประเทศ, หมวด)
            
            # อัปเดตไฟล์ประเทศด้วย (รายการสินค้าทั้งหมดในประเทศ)
            all_products = load_products(ประเทศ)
            all_products = [p for p in all_products if not (p["name"] == ชื่อ and p.get("category") == หมวด)]
            save_products(all_products, ประเทศ)
            
            await ctx.send(f"🗑️ ลบสินค้า '{ชื่อ}' จากหมวด '{CATEGORY_NAMES.get(หมวด, หมวด)}' ในประเทศ '{COUNTRY_NAMES[ประเทศ]}' เรียบร้อยแล้ว")
        else:
            # ถ้าไม่ระบุหมวด ให้โหลดสินค้าทั้งหมดจากประเทศที่ระบุ
            products = load_products(ประเทศ)
            
            # หาสินค้าที่ต้องการลบ
            products_to_delete = [p for p in products if p["name"] == ชื่อ]
            if not products_to_delete:
                await ctx.send(f"❌ ไม่พบสินค้า '{ชื่อ}' ในประเทศ '{COUNTRY_NAMES[ประเทศ]}'")
                return
            
            # รวบรวมรายชื่อหมวดหมู่ที่จะลบ
            categories_to_update = set(p.get("category", "ไม่ระบุหมวด") for p in products_to_delete)
            
            # ลบสินค้าออกจากไฟล์ประเทศ
            updated_products = [p for p in products if p["name"] != ชื่อ]
            save_products(updated_products, ประเทศ)
            
            # อัปเดตไฟล์หมวดหมู่ด้วย
            for category in categories_to_update:
                if category in CATEGORIES:
                    category_products = load_products(ประเทศ, category)
                    category_products = [p for p in category_products if p["name"] != ชื่อ]
                    save_products(category_products, ประเทศ, category)
            
            # สร้างข้อความรายละเอียดเพื่อแสดงหมวดหมู่ที่ลบ
            categories_str = ", ".join([f"'{CATEGORY_NAMES.get(cat, cat)}'" for cat in categories_to_update if cat in CATEGORIES])
            if categories_str:
                await ctx.send(f"🗑️ ลบสินค้า '{ชื่อ}' จำนวน {len(products_to_delete)} รายการจากหมวด {categories_str} ในประเทศ '{COUNTRY_NAMES[ประเทศ]}' เรียบร้อยแล้ว")
            else:
                await ctx.send(f"🗑️ ลบสินค้า '{ชื่อ}' จำนวน {len(products_to_delete)} รายการจากประเทศ '{COUNTRY_NAMES[ประเทศ]}' เรียบร้อยแล้ว")
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

@bot.command(name="แก้ไขสินค้า")
@commands.has_permissions(administrator=True)
async def edit_product(ctx, ชื่อ: str, ประเทศ: str = "1", อีโมจิใหม่: str = None, ชื่อใหม่: str = None, ราคาใหม่: float = None, หมวดใหม่: str = None, ประเทศใหม่: str = None):
    """Command to edit a product (Admin only)
    
    Args:
        ชื่อ: ชื่อสินค้าที่ต้องการแก้ไข
        ประเทศ: ประเทศที่สินค้าอยู่ปัจจุบัน (1=ไทย, 2=ญี่ปุ่น, 3=อเมริกา, 4=เกาหลี, 5=จีน)
        อีโมจิใหม่: อีโมจิใหม่ของสินค้า (ถ้าต้องการเปลี่ยน)
        ชื่อใหม่: ชื่อใหม่ของสินค้า (ถ้าต้องการเปลี่ยน)
        ราคาใหม่: ราคาใหม่ของสินค้า (ถ้าต้องการเปลี่ยน)
        หมวดใหม่: หมวดหมู่ใหม่ของสินค้า (ถ้าต้องการเปลี่ยน)
        ประเทศใหม่: ประเทศใหม่ของสินค้า (ถ้าต้องการย้ายประเทศ)
    """
    try:
        # แปลงประเทศภาษาไทยเป็นรหัสประเทศ
        if ประเทศ in ["ไทย", "ญี่ปุ่น", "อเมริกา", "เกาหลี", "จีน"]:
            thai_to_code = {"ไทย": "1", "ญี่ปุ่น": "2", "อเมริกา": "3", "เกาหลี": "4", "จีน": "5"}
            ประเทศ = thai_to_code[ประเทศ]
        # แปลงรหัสประเทศเดิมเป็นตัวเลข
        elif ประเทศ in COUNTRY_CODES:
            ประเทศ = COUNTRY_CODES[ประเทศ]
        
        # ตรวจสอบว่าประเทศถูกต้อง
        if ประเทศ not in COUNTRIES:
            countries_str = ", ".join([f"`{COUNTRY_NAMES[c]}`" for c in COUNTRIES])
            await ctx.send(f"❌ ประเทศไม่ถูกต้อง ประเทศที่รองรับ: {countries_str}")
            return
            
        # ตรวจสอบประเทศใหม่ (ถ้ามีการระบุ)
        if ประเทศใหม่:
            # แปลงประเทศใหม่ภาษาไทยเป็นรหัสประเทศ
            if ประเทศใหม่ in ["ไทย", "ญี่ปุ่น", "อเมริกา", "เกาหลี", "จีน"]:
                thai_to_code = {"ไทย": "1", "ญี่ปุ่น": "2", "อเมริกา": "3", "เกาหลี": "4", "จีน": "5"}
                ประเทศใหม่ = thai_to_code[ประเทศใหม่]
            # แปลงรหัสประเทศเดิมเป็นตัวเลข
            elif ประเทศใหม่ in COUNTRY_CODES:
                ประเทศใหม่ = COUNTRY_CODES[ประเทศใหม่]
                
            # ตรวจสอบว่าประเทศใหม่ถูกต้อง
            if ประเทศใหม่ not in COUNTRIES:
                countries_str = ", ".join([f"`{COUNTRY_NAMES[c]}`" for c in COUNTRIES])
                await ctx.send(f"❌ ประเทศใหม่ไม่ถูกต้อง ประเทศที่รองรับ: {countries_str}")
                return
        
        # ตรวจสอบหมวดหมู่ใหม่ (ถ้ามีการระบุ)
        if หมวดใหม่:
            # แปลงหมวดหมู่ภาษาไทยเป็นภาษาอังกฤษ
            if หมวดใหม่ in ["เงิน", "อาวุธ", "ไอเทม", "รถ", "แฟชั่น", "เช่ารถ"]:
                thai_to_eng = {"เงิน": "money", "อาวุธ": "weapon", "ไอเทม": "item", 
                              "รถ": "car", "แฟชั่น": "fashion", "เช่ารถ": "rentcar"}
                หมวดใหม่ = thai_to_eng[หมวดใหม่]
                
            # ตรวจสอบว่าหมวดหมู่ใหม่ถูกต้อง
            if หมวดใหม่.lower() not in CATEGORIES:
                categories_str = ", ".join([f"`{CATEGORY_NAMES[c]}`" for c in CATEGORIES])
                await ctx.send(f"❌ หมวดหมู่ใหม่ไม่ถูกต้อง หมวดหมู่ที่รองรับ: {categories_str}")
                return
                
            # ใช้หมวดหมู่ใหม่ที่ระบุ
            หมวดใหม่ = หมวดใหม่.lower()
        
        # โหลดสินค้าจากประเทศที่ระบุ
        products = load_products(ประเทศ)
        
        # ตรวจสอบว่ามีสินค้านี้หรือไม่
        found = False
        for product in products:
            if product["name"] == ชื่อ:
                found = True
                
                # Update product details if provided
                if ชื่อใหม่:
                    product["name"] = ชื่อใหม่
                if ราคาใหม่ is not None:
                    product["price"] = ราคาใหม่
                if อีโมจิใหม่:
                    product["emoji"] = อีโมจิใหม่
                if หมวดใหม่:
                    product["category"] = หมวดใหม่
                # ถ้ามีการระบุประเทศใหม่ ให้คงข้อมูลประเทศเดิมไว้ก่อน
                # เราจะย้ายประเทศในภายหลัง
                
                break
        
        if not found:
            await ctx.send(f"❌ ไม่พบสินค้า '{ชื่อ}' ในประเทศ {COUNTRY_NAMES[ประเทศ]}")
            return
            
        # Get the original category and the new category if changed
        original_product = next((p for p in products if p["name"] == (ชื่อใหม่ if ชื่อใหม่ else ชื่อ)), None)
        if original_product:
            original_category = original_product.get("category", "")
            
            # ถ้ามีการย้ายประเทศ
            if ประเทศใหม่ and ประเทศใหม่ != ประเทศ:
                # 1. ลบสินค้าออกจากประเทศเดิม
                products = [p for p in products if p["name"] != (ชื่อใหม่ if ชื่อใหม่ else ชื่อ)]
                save_products(products, ประเทศ)
                
                # ลบออกจากไฟล์หมวดหมู่ของประเทศเดิม
                if original_category in CATEGORIES:
                    category_products = load_products(ประเทศ, original_category)
                    category_products = [p for p in category_products if p["name"] != ชื่อ]
                    save_products(category_products, ประเทศ, original_category)
                
                # 2. เพิ่มลงในประเทศใหม่
                # โหลดสินค้าจากประเทศใหม่
                new_country_products = load_products(ประเทศใหม่)
                
                # เปลี่ยนประเทศในข้อมูลสินค้า
                original_product["country"] = ประเทศใหม่
                
                # เพิ่มสินค้าลงในรายการสินค้าของประเทศใหม่
                new_country_products.append(original_product)
                
                # บันทึกลงไฟล์ประเทศใหม่
                save_products(new_country_products, ประเทศใหม่)
                
                # บันทึกลงไฟล์หมวดหมู่ในประเทศใหม่
                save_product_to_category(original_product)
                
                # อัปเดตประเทศที่ใช้งานปัจจุบันเป็นประเทศใหม่ (สำหรับแสดงข้อมูล)
                ประเทศ = ประเทศใหม่
            else:
                # ไม่มีการย้ายประเทศ เพียงอัปเดตข้อมูลในประเทศเดิม
                # บันทึกลงไฟล์ประเทศ
                save_products(products, ประเทศ)
                
                # อัปเดตไฟล์หมวดหมู่ถ้าจำเป็น
                if หมวดใหม่ and หมวดใหม่ != original_category:
                    # 1. ลบจากไฟล์หมวดหมู่เดิม
                    if original_category in CATEGORIES:
                        category_products = load_products(ประเทศ, original_category)
                        category_products = [p for p in category_products if p["name"] != ชื่อ]
                        save_products(category_products, ประเทศ, original_category)
                    
                    # 2. เพิ่มลงในไฟล์หมวดหมู่ใหม่
                    if หมวดใหม่ in CATEGORIES:
                        # ตรวจสอบว่ามีหมวดหมู่และประเทศในข้อมูลสินค้า
                        original_product["category"] = หมวดใหม่
                        original_product["country"] = ประเทศ
                        save_product_to_category(original_product)
                else:
                    # หมวดหมู่เดิม เพียงอัปเดตไฟล์
                    if original_category in CATEGORIES:
                        # ตรวจสอบว่ามีหมวดหมู่และประเทศในข้อมูลสินค้า
                        original_product["category"] = original_category
                        original_product["country"] = ประเทศ
                        save_product_to_category(original_product)
        
        product_name = ชื่อใหม่ if ชื่อใหม่ else ชื่อ
        await ctx.send(f"✏️ แก้ไขสินค้า '{ชื่อ}' เรียบร้อย")
        
        # Show updated product details
        # ถ้ามีการย้ายประเทศ ให้โหลดสินค้าจากประเทศใหม่
        if ประเทศใหม่ and ประเทศใหม่ != ประเทศ:
            updated_products = load_products(ประเทศใหม่)
        else:
            updated_products = products
            
        product = next((p for p in updated_products if p["name"] == product_name), None)
        if product:
            embed = discord.Embed(title="✅ ข้อมูลสินค้าที่อัปเดต", color=0x00ff00)
            embed.add_field(name="ชื่อ", value=product["name"], inline=True)
            embed.add_field(name="ราคา", value=f"{product['price']:.2f}฿", inline=True)
            embed.add_field(name="อีโมจิ", value=product["emoji"], inline=True)
            embed.add_field(name="หมวดหมู่", value=CATEGORY_NAMES.get(product.get("category", ""), product.get("category", "ไม่ระบุหมวด")), inline=True)
            embed.add_field(name="ประเทศ", value=COUNTRY_NAMES.get(product.get("country", "thailand"), "ไทย"), inline=True)
            await ctx.send(embed=embed)
            
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

@bot.command(name="สินค้าทั้งหมด")
async def list_products(ctx, หมวด: str = None):
    """Command to list all products"""
    products = load_products(หมวด)
    if not products:
        await ctx.send("❌ ไม่มีสินค้าในร้าน")
        return
    
    # Check if category is valid
    if หมวด and หมวด not in CATEGORIES:
        categories_str = ", ".join([f"`{CATEGORY_NAMES[cat]}`" for cat in CATEGORIES])
        await ctx.send(f"❌ หมวดหมู่ไม่ถูกต้อง หมวดหมู่ที่มี: {categories_str}")
        return
    
    # Filter products by category if specified
    if หมวด:
        filtered_products = [p for p in products if p.get('category', '') == หมวด]
        if not filtered_products:
            await ctx.send(f"❌ ไม่มีสินค้าในหมวด `{หมวด}`")
            return
        products = filtered_products
        embed_title = f"📋 รายการสินค้าในหมวด '{หมวด}'"
    else:
        # Group products by category
        categories = {}
        for product in products:
            category = product.get('category', 'ไม่ระบุหมวด')
            if category not in categories:
                categories[category] = []
            categories[category].append(product)
        
        embed_title = "📋 รายการสินค้าทั้งหมด (แยกตามหมวด)"
        embed = discord.Embed(title=embed_title, color=0x3498db)
        
        # Add category sections
        for category, category_products in categories.items():
            product_list = []
            for product in category_products:
                product_list.append(f"{product['emoji']} {product['name']} - {product['price']:.2f}฿")
            
            # Join products with newlines
            value = "\n".join(product_list) if product_list else "ไม่มีสินค้า"
            
            # Add field for this category
            embed.add_field(
                name=f"🏷️ {category.upper()}",
                value=value,
                inline=False
            )
        
        await ctx.send(embed=embed)
        return
    
    # Show products for a specific category
    embed = discord.Embed(title=embed_title, color=0x3498db)
    
    for product in products:
        embed.add_field(
            name=f"{product['emoji']} {product['name']}",
            value=f"ราคา: {product['price']:.2f}฿",
            inline=True
        )
    
    await ctx.send(embed=embed)

@bot.command(name="ประวัติ")
@commands.has_permissions(administrator=True)
async def history(ctx, จำนวน: int = 5):
    """Command to view purchase history (Admin only)"""
    try:
        if not HISTORY_FILE.exists() or HISTORY_FILE.stat().st_size == 0:
            await ctx.send("❌ ยังไม่มีประวัติการซื้อ")
            return
            
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        if not lines:
            await ctx.send("❌ ยังไม่มีประวัติการซื้อ")
            return
            
        # Get the last N entries
        entries = lines[-จำนวน:] if จำนวน > 0 else lines
            
        embed = discord.Embed(title="📜 ประวัติการซื้อ", color=0x00ff00)
        for line in entries:
            try:
                d = json.loads(line)
                dt = datetime.fromisoformat(d['timestamp'])
                formatted_time = dt.strftime("%d/%m/%Y %H:%M")
                summary = ", ".join([f"{x['name']} x{x['qty']}" for x in d['items']])
                embed.add_field(
                    name=f"👤 {d['user']} ({formatted_time})",
                    value=f"{summary} = {d['total']}฿",
                    inline=False
                )
            except (json.JSONDecodeError, KeyError) as e:
                continue
                
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

@bot.command(name="ลบสินค้าทั้งหมด")
@commands.has_permissions(administrator=True)
async def delete_all_products_command(ctx):
    """Command to delete all products from all categories in all countries completely (Admin only)"""
    try:
        # Create confirmation message
        confirm_embed = discord.Embed(
            title="⚠️ ยืนยันการลบสินค้าทั้งหมด",
            description="คุณกำลังจะลบสินค้าทั้งหมดในทุกหมวดหมู่และทุกประเทศโดยสมบูรณ์\n**การดำเนินการนี้ไม่สามารถเรียกคืนได้**",
            color=discord.Color.red()
        )
        
        # Create confirmation buttons
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)  # Timeout after 60 seconds
                
            @discord.ui.button(label="ยืนยันการลบ", style=discord.ButtonStyle.danger)
            async def confirm_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != ctx.author.id:
                    await button_interaction.response.send_message("❌ คุณไม่ใช่ผู้ใช้คำสั่งนี้", ephemeral=True)
                    return
                    
                success = delete_all_products()
                
                if success:
                    await button_interaction.response.edit_message(
                        content="✅ ลบสินค้าทั้งหมดในทุกหมวดหมู่และทุกประเทศเรียบร้อยแล้ว",
                        embed=None,
                        view=None
                    )
                else:
                    await button_interaction.response.edit_message(
                        content="❌ เกิดข้อผิดพลาดในการลบสินค้าทั้งหมด",
                        embed=None,
                        view=None
                    )
                
            @discord.ui.button(label="ยกเลิก", style=discord.ButtonStyle.secondary)
            async def cancel_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != ctx.author.id:
                    await button_interaction.response.send_message("❌ คุณไม่ใช่ผู้ใช้คำสั่งนี้", ephemeral=True)
                    return
                    
                await button_interaction.response.edit_message(
                    content="❌ ยกเลิกการลบสินค้า",
                    embed=None,
                    view=None
                )
                
        # Send the confirmation message with buttons
        confirm_view = ConfirmView()
        await ctx.send(embed=confirm_embed, view=confirm_view)
            
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

@bot.command(name="ไม่มีสินค้า", aliases=["noitems", "no_items"])
@commands.has_permissions(administrator=True)
async def add_no_product_placeholders_command(ctx):
    """Command to add 'ไม่มีสินค้า' placeholders to empty categories in all countries (Admin only)"""
    try:
        # เพิ่มสินค้า placeholder ในหมวดหมู่ที่ว่างเปล่า
        added_count = add_no_product_placeholders()
        
        if added_count > 0:
            await ctx.send(f"✅ เพิ่มสินค้า 'ไม่มีสินค้า' ในหมวดที่ว่างเปล่าแล้ว {added_count} หมวด")
        else:
            await ctx.send("ℹ️ ไม่มีหมวดที่ว่างเปล่า ทุกหมวดมีสินค้าอยู่แล้ว")
            
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

@bot.command(name="ลบสินค้าหมวด")
@commands.has_permissions(administrator=True)
async def clear_category_command(ctx, *, ข้อมูล: str = None):
    """Command to clear all products from a category (Admin only)
    
    Args:
        ข้อมูล: ข้อมูลหมวดและประเทศที่ต้องการลบ ในรูปแบบ "หมวด ประเทศ" หรือหลายบรรทัด
               หากไม่ระบุประเทศ จะลบในทุกประเทศ
    """
    try:
        if not ข้อมูล:
            await ctx.send("❌ กรุณาระบุหมวดหมู่ที่ต้องการลบ เช่น `!ลบสินค้าหมวด money` หรือ `!ลบสินค้าหมวด money 1`")
            return
        
        # แบ่งข้อมูลเป็นรายบรรทัด
        lines = ข้อมูล.strip().split('\n')
        total_categories = len(lines)
        
        # ตรวจสอบว่ามีหมวดหมู่ที่ไม่ถูกต้องหรือไม่
        invalid_categories = []
        categories_to_clear = []
        
        for line in lines:
            parts = line.strip().split()
            หมวด = parts[0] if parts else ""
            ประเทศ = parts[1] if len(parts) > 1 else None
            
            if หมวด not in CATEGORIES:
                invalid_categories.append(หมวด)
            else:
                if ประเทศ and ประเทศ not in COUNTRIES:
                    await ctx.send(f"❌ ประเทศ `{ประเทศ}` ไม่ถูกต้อง ประเทศที่มี: 1, 2, 3, 4, 5")
                    return
                categories_to_clear.append((หมวด, ประเทศ))
        
        if invalid_categories:
            categories_str = ", ".join([f"`{CATEGORY_NAMES.get(cat, cat)}`" for cat in CATEGORIES])
            await ctx.send(f"❌ หมวดหมู่ `{'`, `'.join(invalid_categories)}` ไม่ถูกต้อง หมวดหมู่ที่มี: {categories_str}")
            return
        
        # สร้างข้อความยืนยันตามจำนวนหมวดหมู่
        description_lines = []
        for หมวด, ประเทศ in categories_to_clear:
            category_name = CATEGORY_NAMES.get(หมวด, หมวด)
            if ประเทศ:
                country_name = COUNTRY_NAMES.get(ประเทศ, ประเทศ)
                description_lines.append(f"- หมวด **{category_name}** ในประเทศ **{country_name}**")
            else:
                description_lines.append(f"- หมวด **{category_name}** ในทุกประเทศ")
        
        # Create confirmation message
        confirm_embed = discord.Embed(
            title="⚠️ ยืนยันการลบสินค้า",
            description=f"คุณกำลังจะลบสินค้าในหมวดต่อไปนี้:\n" + "\n".join(description_lines) + "\n\n**การดำเนินการนี้ไม่สามารถเรียกคืนได้**",
            color=discord.Color.red()
        )
        
        # Create confirmation buttons
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)  # Timeout after 60 seconds
                
            @discord.ui.button(label="ยืนยันการลบ", style=discord.ButtonStyle.danger)
            async def confirm_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != ctx.author.id:
                    await button_interaction.response.send_message("❌ คุณไม่ใช่ผู้ใช้คำสั่งนี้", ephemeral=True)
                    return
                
                success_count = 0
                failed_categories = []
                
                for หมวด, ประเทศ in categories_to_clear:
                    if clear_category_products(หมวด, ประเทศ):
                        success_count += 1
                    else:
                        failed_categories.append((หมวด, ประเทศ))
                
                if success_count == len(categories_to_clear):
                    await button_interaction.response.edit_message(
                        content="✅ ลบสินค้าในทุกหมวดที่เลือกเรียบร้อยแล้ว",
                        embed=None,
                        view=None
                    )
                elif success_count > 0:
                    # สร้างข้อความแสดงหมวดที่ล้มเหลว
                    fail_message = []
                    for หมวด, ประเทศ in failed_categories:
                        category_name = CATEGORY_NAMES.get(หมวด, หมวด)
                        if ประเทศ:
                            country_name = COUNTRY_NAMES.get(ประเทศ, ประเทศ)
                            fail_message.append(f"- หมวด **{category_name}** ในประเทศ **{country_name}**")
                        else:
                            fail_message.append(f"- หมวด **{category_name}** ในทุกประเทศ")
                    
                    await button_interaction.response.edit_message(
                        content=f"⚠️ ลบสินค้าสำเร็จบางส่วน ({success_count}/{len(categories_to_clear)})\n\nไม่สามารถลบ:\n" + "\n".join(fail_message),
                        embed=None,
                        view=None
                    )
                else:
                    await button_interaction.response.edit_message(
                        content="❌ เกิดข้อผิดพลาด ไม่สามารถลบสินค้าในหมวดที่เลือกได้",
                        embed=None,
                        view=None
                    )
                
            @discord.ui.button(label="ยกเลิก", style=discord.ButtonStyle.secondary)
            async def cancel_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != ctx.author.id:
                    await button_interaction.response.send_message("❌ คุณไม่ใช่ผู้ใช้คำสั่งนี้", ephemeral=True)
                    return
                    
                await button_interaction.response.edit_message(
                    content="❌ ยกเลิกการลบสินค้า",
                    embed=None,
                    view=None
                )
        
        # Send confirmation message with buttons
        await ctx.send(embed=confirm_embed, view=ConfirmView())
            
    except Exception as e:
        await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(e)}")

@bot.command(name="ตัวอย่างแอดมิน")
async def admin_examples_command(ctx):
    """Command to display admin command examples"""
    # ตรวจสอบสิทธิ์แอดมิน
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ ต้องการสิทธิ์ผู้ดูแล (Administrator)")
        return
        
    # รับ embeds จากฟังก์ชัน (ตอนนี้ส่งคืนเป็น list ของ embeds)
    embeds = create_admin_examples_embed()
    
    # ส่งแต่ละ embed ทีละตัว
    for i, embed in enumerate(embeds):
        # ส่ง embed แรกแบบปกติ ส่วน embed ถัดไปใช้การตอบกลับแบบใช้ reply
        if i == 0:
            message = await ctx.send(embed=embed)
        else:
            # ส่งข้อความแบบตอบกลับข้อความแรก เพื่อให้ embeds ทั้งหมดอยู่ด้วยกัน
            await ctx.send(embed=embed, reference=message)

@bot.command(name="ช่วยเหลือ")
async def help_command(ctx):
    """Command to display help information"""
    embed = discord.Embed(title="📚 คำสั่งสำหรับร้านค้า", color=0x4f0099)
    
    # General commands
    embed.add_field(
        name="🛒 เปิดร้านค้า",
        value="ใช้คำสั่ง `!ร้าน`, `!shop` หรือ `/ร้าน` เพื่อเปิดร้านค้าและเลือกซื้อสินค้า\nหรือเรียกดูสินค้าตามประเภท: `!ร้าน เงิน`, `!ร้าน อาวุธ`, `!ร้าน ไอเทม`, `!ร้าน ไอเทมต่อสู้`",
        inline=False
    )
    
    embed.add_field(
        name="📋 ดูรายการสินค้า",
        value="ใช้คำสั่ง `!สินค้าทั้งหมด`, `!สินค้า` หรือ `/สินค้าทั้งหมด` เพื่อดูรายการสินค้าทั้งหมด",
        inline=False
    )

    embed.add_field(
        name="📝 สั่งซื้อสินค้าหลายรายการ",
        value=(
            "ใช้คำสั่ง `!สั่งของ` แล้วตามด้วยรายการสินค้าที่ต้องการในรูปแบบ: <ชื่อสินค้า> <จำนวน>\n\n"
            "ตัวอย่าง:\n"
            "```!สั่งของ\n"
            "ชุดเกาะมวยไทย 5\n"
            "ผ้าพันมือมวยไทย 2\n"
            "ชุดกิโมโน 3```\n\n"
            "• ไม่จำเป็นต้องระบุประเทศ ระบบจะค้นหาสินค้าในทุกประเทศให้อัตโนมัติ"
        ),
        inline=False
    )
    
    # Admin commands
    embed.add_field(
        name="💾 สำรองข้อมูล",
        value="ใช้คำสั่ง `!saveall` หรือ `!สำรองข้อมูล` เพื่อสร้างคำสั่งสำหรับกู้คืนข้อมูลทั้งหมด (เฉพาะแอดมิน)",
        inline=False
    )
    
    # Admin commands
    embed.add_field(
        name="👑 คำสั่งสำหรับแอดมิน",
        value=(
            "ใช้คำสั่ง `!ตัวอย่างแอดมิน` เพื่อดูรายละเอียดและตัวอย่างการใช้คำสั่งสำหรับแอดมินทั้งหมด\n"
            "ใช้คำสั่ง `!idview` เพื่อดูหรือเปลี่ยน Target Channel ID สำหรับระบบกดอีโมจิอัตโนมัติ"
        ),
        inline=False
    )
    
    await ctx.send(embed=embed)

# คำสั่งสั่งซื้อสินค้าหลายรายการพร้อมกัน
@bot.command(name="สั่งของ", aliases=["order", "ordermany"])
async def order_many_command(ctx):
    """Command to order multiple items with quantities in text format"""
    # แยกข้อความออกเป็นบรรทัด
    message_content = ctx.message.content
    
    # ตรวจสอบว่ามีข้อความหลังคำสั่งหรือไม่
    command_parts = message_content.split("\n", 1)
    if len(command_parts) < 2:
        # ถ้าไม่มีข้อมูลหลังคำสั่ง ให้แสดงวิธีใช้
        usage_embed = discord.Embed(
            title="📝 วิธีใช้คำสั่งสั่งของ",
            description="ใช้คำสั่ง `!สั่งของ` แล้วตามด้วยรายการสินค้าในบรรทัดถัดไป",
            color=discord.Color.blue()
        )
        
        usage_embed.add_field(
            name="รูปแบบ",
            value=(
                "แต่ละบรรทัดใช้รูปแบบ: `<ชื่อสินค้า> <จำนวน>`\n\n"
                "• <ชื่อสินค้า> ต้องตรงกับชื่อที่มีในร้านค้า\n"
                "• <จำนวน> ระบุจำนวนที่ต้องการซื้อ"
            ),
            inline=False
        )
        
        usage_embed.add_field(
            name="ตัวอย่าง",
            value=(
                "```!สั่งของ\n"
                "ชุดเกาะมวยไทย 5\n"
                "ผ้าพันมือมวยไทย 2\n"
                "ชุดกิโมโน 3```"
            ),
            inline=False
        )
        
        await ctx.send(embed=usage_embed)
        return
    
    # เก็บรายการสั่งซื้อที่สำเร็จและไม่สำเร็จ
    successful_orders = []
    failed_orders = []
    cart_items = []
    total_price = 0
    
    # แยกข้อความเป็นรายการสั่งซื้อ
    order_lines = command_parts[1].strip().split("\n")
    
    for line in order_lines:
        # แยกชื่อสินค้าและจำนวน
        parts = line.strip().rsplit(" ", 1)
        if len(parts) != 2:
            failed_orders.append((line, "รูปแบบไม่ถูกต้อง ต้องเป็น <ชื่อสินค้า> <จำนวน>"))
            continue
        
        product_name = parts[0].strip()
        quantity_str = parts[1].strip()
        
        if not quantity_str.isdigit():
            failed_orders.append((line, f"จำนวนไม่ถูกต้อง: {quantity_str} (ต้องเป็นตัวเลข)"))
            continue
        
        quantity = int(quantity_str)
        if quantity <= 0:
            failed_orders.append((line, f"จำนวนต้องมากกว่า 0"))
            continue
        
        # ค้นหาสินค้าจากชื่อในทุกประเทศ
        found_product = None
        found_country = None
        
        for country in COUNTRIES:
            all_products = load_products(country=country)
            for p in all_products:
                if p["name"].lower() == product_name.lower():
                    found_product = p
                    found_country = country
                    break
            if found_product:
                break
        
        if not found_product:
            failed_orders.append((line, f"ไม่พบสินค้า: {product_name} ในทุกประเทศ"))
            continue
        
        # ตรวจสอบสินค้า placeholder
        if found_product["name"] == "ไม่มีสินค้า":
            failed_orders.append((line, "ไม่สามารถสั่งซื้อสินค้านี้ได้"))
            continue
        
        # เพิ่มสินค้าลงตะกร้า
        item_price = found_product["price"] * quantity
        total_price += item_price
        
        cart_items.append({
            "product": found_product,
            "quantity": quantity,
            "subtotal": item_price,
            "country": found_country
        })
        
        successful_orders.append((
            f"{COUNTRY_EMOJIS.get(found_country, '')} {found_product['emoji']} {found_product['name']} x{quantity} = {item_price:,.2f} บาท"
        ))
    
    if not cart_items:
        # ถ้าไม่มีรายการสั่งซื้อที่สำเร็จ
        error_embed = discord.Embed(
            title="❌ ไม่สามารถสั่งซื้อสินค้าได้",
            description="ไม่พบสินค้าที่ต้องการสั่งซื้อ กรุณาตรวจสอบข้อมูลและลองใหม่อีกครั้ง",
            color=discord.Color.red()
        )
        
        if failed_orders:
            error_list = "\n".join([f"• {order}: {reason}" for order, reason in failed_orders])
            error_embed.add_field(
                name="รายการที่ผิดพลาด",
                value=error_list[:1024],  # จำกัดขนาดข้อความใน field
                inline=False
            )
        
        await ctx.send(embed=error_embed)
        return
    
    # สร้าง embed สำหรับแสดงผลการสั่งซื้อ
    cart_embed = discord.Embed(
        title="🛒 รายการสั่งซื้อของคุณ",
        description="รายการสินค้าที่คุณเลือก",
        color=discord.Color.blue()
    )
    
    # เพิ่มรายการสินค้าที่สั่งซื้อ
    if successful_orders:
        cart_embed.add_field(
            name=f"✅ รายการสั่งซื้อ ({len(successful_orders)} รายการ)",
            value="\n".join(successful_orders)[:1024],
            inline=False
        )
    
    # เพิ่มรายการสินค้าที่ไม่สำเร็จ
    if failed_orders:
        error_list = "\n".join([f"• {order}: {reason}" for order, reason in failed_orders[:5]])
        if len(failed_orders) > 5:
            error_list += f"\n• และอีก {len(failed_orders) - 5} รายการ..."
            
        cart_embed.add_field(
            name=f"❌ รายการที่ผิดพลาด ({len(failed_orders)} รายการ)",
            value=error_list[:1024],
            inline=False
        )
    
    # เพิ่มราคารวม
    cart_embed.add_field(
        name="💰 ราคารวม",
        value=f"{total_price:,.2f} บาท",
        inline=False
    )
    
    # เพิ่มข้อความที่ footer
    cart_embed.set_footer(text="กดปุ่ม 'ชำระเงิน' เพื่อดำเนินการชำระเงิน หรือ 'ยกเลิก' เพื่อยกเลิกการสั่งซื้อ")
    
    # สร้างปุ่มกดสำหรับตะกร้าสินค้า
    class CheckoutView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=600)  # หมดเวลาหลังจาก 10 นาที
        
        @discord.ui.button(label="💳 ชำระเงิน", style=discord.ButtonStyle.green)
        async def checkout_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user.id != ctx.author.id:
                await button_interaction.response.send_message("❌ คุณไม่ใช่ผู้สั่งซื้อสินค้านี้", ephemeral=True)
                return
            
            # สร้าง embed สำหรับการชำระเงิน
            payment_embed = discord.Embed(
                title="💳 ชำระเงิน",
                description=f"กรุณาชำระเงินจำนวน {total_price:,.2f} บาท โดยสแกน QR Code ด้านล่าง",
                color=discord.Color.green()
            )
            
            # เพิ่มรายการสินค้าที่สั่งซื้อ
            items_list = []
            for item in cart_items:
                product = item["product"]
                qty = item["quantity"]
                subtotal = item["subtotal"]
                country_name = COUNTRY_NAMES.get(item["country"], item["country"])
                items_list.append(f"{product['emoji']} {product['name']} x{qty} ({country_name}) = {subtotal:,.2f} บาท")
            
            payment_embed.add_field(
                name=f"🛒 รายการสินค้า ({len(cart_items)} รายการ)",
                value="\n".join(items_list)[:1024],
                inline=False
            )
            
            # เพิ่มราคารวม
            payment_embed.add_field(
                name="💰 ยอดชำระเงินทั้งหมด",
                value=f"{total_price:,.2f} บาท",
                inline=False
            )
            
            # เพิ่ม QR Code
            qr_url = await load_qrcode_url_async_local()
            payment_embed.set_image(url=qr_url)
            
            # เพิ่มคำแนะนำ
            payment_embed.set_footer(text="หลังจากชำระเงินแล้ว รอแอดมินกดปุ่ม 'ส่งของแล้ว' เพื่อยืนยันการสั่งซื้อ")
            
            # สร้างปุ่มสำหรับหน้าชำระเงิน
            class PaymentView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=None)  # ไม่หมดเวลา
                
                @discord.ui.button(label="✅ ส่งของแล้ว (สำหรับแอดมิน)", style=discord.ButtonStyle.green)
                async def confirm_button(self, confirm_interaction: discord.Interaction, confirm_button: discord.ui.Button):
                    # ตรวจสอบว่าเป็นแอดมินหรือไม่
                    if not confirm_interaction.user.guild_permissions.administrator:
                        await confirm_interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้ปุ่มนี้ (เฉพาะแอดมินเท่านั้น)", ephemeral=True)
                        return
                    
                    # บันทึกประวัติการซื้อ
                    purchase_id = log_purchase(ctx.author, cart_items, total_price)
                    
                    # โหลดข้อความขอบคุณ
                    thank_you_message = load_thank_you_message()
                    
                    # สร้าง embed ขอบคุณ
                    thank_you_embed = discord.Embed(
                        title="✅ การสั่งซื้อเสร็จสมบูรณ์",
                        description=thank_you_message,
                        color=discord.Color.green()
                    )
                    
                    thank_you_embed.set_footer(text=f"รหัสคำสั่งซื้อ: {purchase_id}")
                    
                    await confirm_interaction.response.edit_message(embed=thank_you_embed, view=None)
            
            await button_interaction.response.edit_message(embed=payment_embed, view=PaymentView())
        
        @discord.ui.button(label="❌ ยกเลิก", style=discord.ButtonStyle.red)
        async def cancel_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user.id != ctx.author.id:
                await button_interaction.response.send_message("❌ คุณไม่ใช่ผู้สั่งซื้อสินค้านี้", ephemeral=True)
                return
            
            cancel_embed = discord.Embed(
                title="❌ ยกเลิกการสั่งซื้อแล้ว",
                description="คุณได้ยกเลิกการสั่งซื้อสินค้าแล้ว",
                color=discord.Color.red()
            )
            
            await button_interaction.response.edit_message(embed=cancel_embed, view=None)
    
    await ctx.send(embed=cart_embed, view=CheckoutView())

# คำสั่งสำรองข้อมูลทั้งหมดในรูปแบบคำสั่ง
@bot.command(name="saveall", aliases=["สำรองข้อมูล", "backup"])
async def save_all_command(ctx):
    """Command to save all database information in command format for easy restoration"""
    # ตรวจสอบสิทธิ์แอดมิน
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ ต้องการสิทธิ์ผู้ดูแล (Administrator)")
        return
    
    # สร้าง embed แจ้งว่ากำลังประมวลผล
    processing_embed = discord.Embed(
        title="⏳ กำลังประมวลผลข้อมูล...",
        description="กำลังรวบรวมข้อมูลทั้งหมดในระบบ โปรดรอสักครู่",
        color=discord.Color.blue()
    )
    message = await ctx.send(embed=processing_embed)
    
    # ดึงข้อมูลทั้งหมดจากฐานข้อมูล
    # 1. ข้อมูลประเทศ - ใช้ตัวแปรโกลบอลเป็นหลัก เพื่อให้ทำงานได้ทุกสถานการณ์
    countries = COUNTRIES
    country_names = COUNTRY_NAMES
    country_emojis = COUNTRY_EMOJIS
    
    # หากตัวแปรโกลบอลไม่มีข้อมูล ให้พยายามดึงจาก MongoDB
    if not countries:
        try:
            countries, country_names, country_emojis, _ = load_countries()
            processing_embed = discord.Embed(
                title="ℹ️ ใช้ข้อมูลจาก MongoDB",
                description="ดึงข้อมูลจาก MongoDB สำเร็จ",
                color=discord.Color.blue()
            )
            await message.edit(embed=processing_embed)
        except Exception as e:
            # เกิดข้อผิดพลาด แต่ไม่ return เพราะจะใช้ตัวแปรโกลบอลต่อไป
            error_embed = discord.Embed(
                title="⚠️ ไม่สามารถเชื่อมต่อ MongoDB ได้",
                description=f"จะใช้ข้อมูลจากตัวแปรโกลบอลแทน\nError: {str(e)[:100]}...",
                color=discord.Color.gold()
            )
            await message.edit(embed=error_embed)
    
    if not countries:
        await ctx.send("❌ ไม่พบข้อมูลประเทศใดๆ ในระบบ")
        return
    
    # 2. ข้อมูลหมวดหมู่
    category_names = {}
    category_emojis = {}
    try:
        # ใช้ตัวแปรโกลบอล
        category_names = CATEGORY_NAMES
        category_emojis = CATEGORY_EMOJIS
    except Exception as e:
        # แจ้งเตือนแต่ไม่ return
        await ctx.send(f"⚠️ ไม่สามารถโหลดข้อมูลหมวดหมู่: {str(e)[:100]}...")
        
    # 3. ข้อมูลสินค้าทั้งหมด
    all_products = []
    
    # พยายามโหลดจากไฟล์ JSON ก่อน
    try:
        # ใช้ categories directory เพื่อรวบรวมสินค้าทั้งหมด
        categories_dir = SCRIPT_DIR / "categories"
        
        if categories_dir.exists():
            # วนลูปผ่านแต่ละประเทศ
            for country_dir in sorted(categories_dir.iterdir()):
                if country_dir.is_dir():
                    country_code = country_dir.name
                    # วนลูปผ่านแต่ละหมวดหมู่
                    for category_file in sorted(country_dir.iterdir()):
                        if category_file.is_file() and category_file.suffix == '.json':
                            category_code = category_file.stem
                            try:
                                with open(category_file, "r", encoding="utf-8") as f:
                                    category_products = json.load(f)
                                    # เพิ่ม country และ category code สำหรับแต่ละสินค้า
                                    for product in category_products:
                                        if isinstance(product, dict) and "name" in product and product["name"] != "ไม่มีสินค้า":
                                            product["country"] = country_code
                                            product["category"] = category_code
                                            all_products.append(product)
                            except Exception as e:
                                await ctx.send(f"⚠️ ไม่สามารถโหลดข้อมูลสินค้าจากไฟล์ {category_file}: {str(e)[:100]}...")
        
        if all_products:
            processing_embed = discord.Embed(
                title="ℹ️ โหลดข้อมูลสินค้าสำเร็จ",
                description=f"พบสินค้าทั้งหมด {len(all_products)} รายการจากไฟล์ในโฟลเดอร์ categories",
                color=discord.Color.blue()
            )
            await message.edit(embed=processing_embed)
        else:
            # ถ้าไม่มีข้อมูลจากโฟลเดอร์ categories ให้ลองโหลดจาก products.json
            try:
                with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
                    all_products = json.load(f)
                if all_products:
                    processing_embed = discord.Embed(
                        title="ℹ️ โหลดข้อมูลสินค้าสำเร็จ",
                        description=f"พบสินค้าทั้งหมด {len(all_products)} รายการจากไฟล์ JSON",
                        color=discord.Color.blue()
                    )
                    await message.edit(embed=processing_embed)
            except Exception:
                pass
    except Exception as e:
        await ctx.send(f"⚠️ ไม่สามารถโหลดข้อมูลสินค้าจากโฟลเดอร์ categories: {str(e)[:100]}...")
    
    # หากไม่มีข้อมูลจากไฟล์ JSON ให้ลองโหลดจาก MongoDB
    if not all_products:
        try:
            all_products = load_products()
            if all_products:
                processing_embed = discord.Embed(
                    title="ℹ️ โหลดข้อมูลสินค้าสำเร็จ",
                    description=f"พบสินค้าทั้งหมด {len(all_products)} รายการจาก MongoDB",
                    color=discord.Color.blue()
                )
                await message.edit(embed=processing_embed)
        except Exception as e:
            # แจ้งเตือนแต่ไม่ return
            error_embed = discord.Embed(
                title="⚠️ ไม่สามารถโหลดข้อมูลสินค้าจาก MongoDB ได้",
                description=f"จะใช้ข้อมูลจากตัวแปรโกลบอลแทน\nError: {str(e)[:100]}...",
                color=discord.Color.gold()
            )
            await message.edit(embed=error_embed)
    
    # 4. QR Code URL
    qr_code_url = ""
    # พยายามเข้าถึงตัวแปรโกลบอล
    try:
        with open(QRCODE_CONFIG_FILE, "r", encoding="utf-8") as f:
            qr_code_url = json.load(f).get("url", "")
    except Exception:
        pass
    
    # หากไม่สำเร็จ ลองใช้ฟังก์ชันจาก db_operations
    if not qr_code_url:
        try:
            temp_url = load_qrcode_url()
            if temp_url:
                qr_code_url = temp_url
        except Exception as e:
            # แจ้งเตือนแต่ไม่ return
            await ctx.send(f"⚠️ ไม่สามารถโหลด QR Code URL: {str(e)[:100]}...")
    
    # 5. ข้อความขอบคุณ
    thank_you_message = "ขอบคุณที่ใช้บริการ"
    # พยายามเข้าถึงจากไฟล์
    try:
        thank_you_file = SCRIPT_DIR / "thank_you_config.json"
        with open(thank_you_file, "r", encoding="utf-8") as f:
            thank_you_message = json.load(f).get("message", "ขอบคุณที่ใช้บริการ")
    except Exception:
        pass
    
    # หากไม่สำเร็จ ลองใช้ฟังก์ชันจาก db_operations
    if thank_you_message == "ขอบคุณที่ใช้บริการ":
        try:
            temp_msg = load_thank_you_message()
            if temp_msg:
                thank_you_message = temp_msg
        except Exception as e:
            # แจ้งเตือนแต่ไม่ return
            await ctx.send(f"⚠️ ไม่สามารถโหลดข้อความขอบคุณ: {str(e)[:100]}...")
    
    # สร้างข้อความคำสั่งสำหรับกู้คืนข้อมูล
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commands_text = f"# คำสั่งกู้คืนข้อมูลทั้งหมด\n# สร้างเมื่อ: {current_time}\n\n"
    
    # 1. คำสั่งกู้คืนข้อมูลประเทศ
    if countries:
        commands_text += "# คำสั่งกู้คืนข้อมูลประเทศ\n"
        commands_text += "!แก้ไขประเทศ\n"
        for code in countries:
            emoji = country_emojis.get(code, "")
            name = country_names.get(code, "")
            if emoji and name:
                commands_text += f"{code} {emoji} {name}\n"
        commands_text += "\n"
    
    # 2. คำสั่งกู้คืนข้อมูลหมวดหมู่
    if category_names:
        commands_text += "# คำสั่งกู้คืนข้อมูลหมวดหมู่\n"
        commands_text += "!แก้ไขหมวดสินค้า\n"
        for code in category_names:
            emoji = category_emojis.get(code, "")
            name = category_names.get(code, "")
            if emoji and name:
                commands_text += f"{code} {emoji} {name}\n"
        commands_text += "\n"
    
    # 3. คำสั่งกู้คืนข้อมูลสินค้า
    if all_products:
        commands_text += "# คำสั่งกู้คืนข้อมูลสินค้า\n"
        
        # กรองเฉพาะสินค้าที่ไม่ใช่ placeholder
        valid_products = []
        for product in all_products:
            if product["name"] != "ไม่มีสินค้า":
                emoji = product.get("emoji", "")
                name = product.get("name", "")
                price = product.get("price", 0)
                category = product.get("category", "")
                country = product.get("country", "")
                valid_products.append((emoji, name, price, category, country))
        
        # แบ่งสินค้าเป็นชุด ชุดละ 50 รายการ
        product_chunks = [valid_products[i:i+50] for i in range(0, len(valid_products), 50)]
        
        for i, chunk in enumerate(product_chunks):
            commands_text += f"!เพิ่มสินค้า\n"
            for emoji, name, price, category, country in chunk:
                commands_text += f"{emoji} {name} {price:.2f} {category} {country}\n"
            commands_text += "\n"
    
    # 4. คำสั่งกู้คืน QR Code URL
    if qr_code_url:
        commands_text += "# คำสั่งกู้คืน QR Code\n"
        commands_text += f"!qrcode {qr_code_url}\n\n"
    
    # 5. คำสั่งกู้คืนข้อความขอบคุณ
    if thank_you_message:
        commands_text += "# คำสั่งกู้คืนข้อความขอบคุณ\n"
        commands_text += f"!ขอบคุณ {thank_you_message}\n\n"
    
    # เพิ่มคำอธิบายช่วยเหลือ
    commands_text += "# หมายเหตุ:\n"
    commands_text += "# 1. ให้รันคำสั่งตามลำดับเพื่อกู้คืนข้อมูลทั้งหมด\n"
    commands_text += "# 2. สินค้าถูกแบ่งเป็นชุด ชุดละ 50 รายการเพื่อความสะดวกในการนำเข้า\n"
    commands_text += "# 3. หากมีข้อมูลมากเกินกว่าที่ Discord จะส่งได้ อาจจะถูกแบ่งเป็นหลายข้อความ\n"
    
    # ส่งข้อความแสดงคำสั่งทั้งหมด
    # ตรวจสอบความยาวข้อความและแบ่งส่งหากยาวเกินไป
    max_length = 1900  # ข้อความใน Discord จำกัดประมาณ 2000 ตัวอักษร
    
    # แบ่งข้อความออกเป็นส่วน ๆ หากยาวเกินไป
    parts = [commands_text[i:i+max_length] for i in range(0, len(commands_text), max_length)]
    
    # ส่งข้อความแรกโดยการแก้ไขข้อความเดิม
    embed = discord.Embed(
        title="💾 สำรองข้อมูลสำเร็จ",
        description=f"จำนวนประเทศ: {len(countries)} รายการ\nจำนวนหมวดหมู่: {len(category_names)} รายการ\nจำนวนสินค้า: {len(all_products)} รายการ",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"ข้อมูลถูกแบ่งเป็น {len(parts)} ส่วน")
    
    await message.edit(embed=embed)
    
    # ส่งข้อความแต่ละส่วน
    for i, part in enumerate(parts):
        await ctx.send(f"```\n{part}\n```")
    
    # ส่งข้อความสรุป
    summary_embed = discord.Embed(
        title="✅ บันทึกข้อมูลสำเร็จ",
        description=f"ข้อมูลทั้งหมดถูกบันทึกเป็นคำสั่งเรียบร้อยแล้ว\nคัดลอกและเก็บคำสั่งเหล่านี้ไว้เพื่อใช้ในการกู้คืนข้อมูลในอนาคต",
        color=discord.Color.green()
    )
    
    await ctx.send(embed=summary_embed)

@bot.event
async def on_message(message):
    """Event triggered when a message is sent"""
    # ตรวจสอบว่าไม่ใช่ข้อความจากบอทเอง
    if message.author == bot.user:
        return
    
    # โหลด Target Channel ID จาก MongoDB
    TARGET_CHANNEL_ID = load_target_channel_id()
    
    print(f"📨 Message from {message.author.name} in channel {message.channel.id} ({message.channel.name})")
    print(f"🎯 Target channel: {TARGET_CHANNEL_ID}")
    print(f"🔍 Channel ID types: message={type(message.channel.id)}, target={type(TARGET_CHANNEL_ID)}")
    print(f"🔍 Checking: {message.channel.id} == {TARGET_CHANNEL_ID} = {message.channel.id == TARGET_CHANNEL_ID}")
    
    if message.channel.id == TARGET_CHANNEL_ID:
        print("✅ Message in target channel! Processing...")
        print("🚀 Starting reaction and channel name update process...")
        
        # Process message in target channel
        
        try:
            # เพิ่มอีโมจิ 💗 ให้ข้อความ
            await message.add_reaction("💗")
            print("💗 Added reaction successfully")
            
            # ดึงช่องและชื่อปัจจุบัน
            channel = message.channel
            current_name = channel.name
            print(f"🔍 Current channel name: '{current_name}'")
            
            # ซิงค์ตัวเลขจากชื่อช่องจริงก่อน
            sync_channel_numbers(current_name)
            
            # ดึงข้อมูลล่าสุดจาก MongoDB ทุกครั้ง
            channel_state = load_channel_state()
            current_number_from_db = channel_state.get("current_number", 0)
            pending_number_from_db = channel_state.get("pending_number", 0)
            
            # หาตัวเลขจริงจากชื่อช่อง
            import re
            number_match = re.search(r'(\d+)$', current_name)
            actual_current_number = int(number_match.group(1)) if number_match else 0
            
            # ใช้ pending_number จาก MongoDB + 1 เสมอ (ไม่ดูตัวเลขจากชื่อช่อง)
            new_pending_number = pending_number_from_db + 1
            
            print(f"📊 Current state - DB: {current_number_from_db}, Actual: {actual_current_number}, Old Pending: {pending_number_from_db}")
            print(f"📊 New pending number will be: {new_pending_number}")
            
            print(f"🔍 Saving to MongoDB first...")
            # บันทึกตัวเลขใหม่ลง MongoDB ก่อนลองเปลี่ยนชื่อ
            save_result = save_channel_state(
                current_name,
                actual_current_number,
                new_pending_number
            )
            print(f"📊 Saved pending number {new_pending_number} to MongoDB: {save_result}")
            
            # ลองเปลี่ยนชื่อช่อง (Discord จะจัดการ rate limit เอง)
            try:
                # ดึงข้อมูล pending_number ล่าสุดจาก MongoDB ก่อนเปลี่ยนชื่อทุกครั้ง
                fresh_mongodb_state = load_channel_state()
                fresh_pending = fresh_mongodb_state.get("pending_number", 0)
                
                # ดึงตัวเลขปัจจุบันจากชื่อช่องอีกครั้ง (อาจมีการเปลี่ยนแปลงระหว่างรอ)
                fresh_current_name = channel.name
                fresh_number_match = re.search(r'(\d+)$', fresh_current_name)
                fresh_actual_current = int(fresh_number_match.group(1)) if fresh_number_match else 0
                
                print(f"🔄 FRESH CHECK - MongoDB pending: {fresh_pending}, Channel current: {fresh_actual_current}")
                
                # ใช้ pending_number จาก MongoDB โดยตรง (ไม่เปรียบเทียบกับชื่อช่อง)
                if fresh_pending > 0:
                    fresh_new_name = re.sub(r'\d+$', str(fresh_pending), fresh_current_name)
                    print(f"🔄 Applying FRESH MongoDB pending: {fresh_actual_current} → {fresh_pending}")
                    
                    await channel.edit(name=fresh_new_name)
                    print(f"✅ Applied FRESH MongoDB pending number successfully to {fresh_pending}!")
                    
                    # อัปเดต current_number เมื่อเปลี่ยนสำเร็จ แต่รักษา pending_number ไว้
                    current_state = load_channel_state()
                    current_pending = current_state.get("pending_number", fresh_pending)
                    save_channel_state(fresh_new_name, fresh_pending, current_pending)
                    print(f"💾 Updated current number to {fresh_pending}, keeping pending at {current_pending}")
                else:
                    print(f"📝 No valid MongoDB pending number ({fresh_pending})")
                    
            except discord.errors.HTTPException as rate_limit_error:
                if rate_limit_error.status == 429:
                    print(f"⏳ Rate limited - pending number {new_pending_number} saved to MongoDB, will apply when limit clears")
                else:
                    print(f"❌ Error applying pending change: {rate_limit_error}")
            

                
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
    
    # ประมวลผลคำสั่งปกติ
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    """Error handler for bot commands with Rate Limit protection"""
    try:
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, discord.HTTPException) and error.status == 429:
            # ถ้าเกิด Rate Limit ไม่พยายามส่งข้อความ
            print(f"⚠️ Rate limited when trying to handle command error: {error}")
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ ต้องการสิทธิ์ผู้ดูแล (Administrator)")
        elif isinstance(error, commands.MissingRole):
            await ctx.send("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ คำสั่งไม่ถูกต้อง: {str(error)}")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ รูปแบบคำสั่งไม่ถูกต้อง กรุณาตรวจสอบว่าข้อมูลที่ใส่ถูกต้อง")
        else:
            await ctx.send(f"❌ เกิดข้อผิดพลาด: {str(error)}")
            print(f"Command error: {error}")
    except discord.HTTPException as rate_error:
        if rate_error.status == 429:
            print(f"⚠️ Cannot send error message due to rate limit: {rate_error}")
        else:
            print(f"❌ Error sending error message: {rate_error}")
    except Exception as e:
        print(f"❌ Critical error in error handler: {e}")

# Get token from environment variables with fallback to a default value (for testing)
TOKEN = os.getenv("DISCORD_TOKEN", "")

if not TOKEN:
    print("❌ ERROR: Discord bot token not provided. Please set the DISCORD_TOKEN environment variable.")
    exit(1)

@bot.command(name="idview", aliases=["ดูไอดี", "ดูid"])
async def idview_command(ctx, channel_id: int = None):
    """คำสั่งสำหรับดูหรือเปลี่ยน Target Channel ID (เฉพาะแอดมิน)
    
    Args:
        channel_id: ID ของช่องใหม่ที่ต้องการตั้งเป็นเป้าหมาย
        
    ตัวอย่าง:
        !idview                    - ดู ID ปัจจุบัน
        !idview 1234567890123456789  - เปลี่ยน ID เป้าหมาย
    """
    # ตรวจสอบสิทธิ์แอดมิน
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมินเท่านั้น")
        return
    
    # ถ้าไม่มี channel_id แสดงข้อมูลปัจจุบัน
    if channel_id is None:
        current_id = load_target_channel_id()
        try:
            # พยายามดึงข้อมูลช่อง
            channel = bot.get_channel(current_id)
            if channel:
                channel_info = f"#{channel.name} ({channel.id})"
            else:
                channel_info = f"ไม่พบข้อมูลช่อง (ID: {current_id})"
        except:
            channel_info = f"ไม่พบข้อมูลช่อง (ID: {current_id})"
        
        embed = discord.Embed(
            title="🎯 Target Channel ID ปัจจุบัน",
            description=f"**ช่องเป้าหมาย:** {channel_info}",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="การใช้งาน",
            value="```\n!idview [channel_id]  - เปลี่ยน ID เป้าหมายใหม่\n!idview              - ดู ID ปัจจุบัน```",
            inline=False
        )
        embed.set_footer(text="เมื่อมีข้อความในช่องเป้าหมาย บอทจะกดอีโมจิ 💗 และเปลี่ยนชื่อช่องอัตโนมัติ")
        
        await ctx.send(embed=embed)
        return
    
    # ตรวจสอบว่า channel_id ถูกต้องหรือไม่
    if channel_id < 0:
        await ctx.send("❌ Channel ID ต้องเป็นตัวเลขบวก")
        return
    
    # ตรวจสอบว่าช่องนี้มีอยู่จริงหรือไม่
    target_channel = bot.get_channel(channel_id)
    if not target_channel:
        await ctx.send(f"⚠️ ไม่พบช่องที่มี ID: {channel_id}\nโปรดตรวจสอบว่า ID ถูกต้องและบอทสามารถเข้าถึงช่องนั้นได้")
        return
    
    # บันทึก Target Channel ID ใหม่
    success = save_target_channel_id(channel_id)
    
    if success:
        embed = discord.Embed(
            title="✅ เปลี่ยน Target Channel ID สำเร็จ",
            description=f"**ช่องเป้าหมายใหม่:** #{target_channel.name} ({channel_id})",
            color=discord.Color.green()
        )
        embed.set_footer(text="เมื่อมีข้อความในช่องใหม่ บอทจะกดอีโมจิ 💗 และเปลี่ยนชื่อช่องอัตโนมัติ")
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ ไม่สามารถบันทึก Target Channel ID ได้ กรุณาลองใหม่อีกครั้ง")

@bot.command(name="แก้ไขหมวดสินค้า", aliases=["แก้ไขหมวด", "editcategory"])
async def edit_category_command(ctx, *, ข้อมูล: str = None):
    """คำสั่งสำหรับแก้ไขอีโมจิและชื่อของหมวดหมู่สินค้า (เฉพาะแอดมิน)
    
    Args:
        ข้อมูล: ข้อมูลหมวดหมู่ที่ต้องการแก้ไข โดยแบ่งเป็นบรรทัด แต่ละบรรทัด
               ใช้รูปแบบ "รหัสหมวดหมู่ อีโมจิใหม่ ชื่อใหม่" หรือ "รหัสหมวดหมู่ อีโมจิใหม่" หรือ
               "รหัสหมวดหมู่ ชื่อใหม่" ได้
               
    ตัวอย่าง:
        !แก้ไขหมวดรายการ
        money 💰 เงินสด
        weapon 🗡️ อาวุธต่อสู้
        item 📦 ไอเทมทั่วไป
    """
    # ตรวจสอบสิทธิ์แอดมิน
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมินเท่านั้น")
        return
    
    if ข้อมูล is None:
        # แสดงรายการหมวดหมู่ทั้งหมดที่มี
        category_list = "\n".join([f"- {code}: {CATEGORY_EMOJIS.get(code, '❓')} {CATEGORY_NAMES[code]}" for code in CATEGORIES])
        
        embed = discord.Embed(
            title="📋 รายการหมวดหมู่สินค้าทั้งหมด",
            description="ใช้คำสั่ง `!แก้ไขหมวดสินค้า` ตามด้วยข้อมูลในรูปแบบ **รหัสหมวดหมู่ อีโมจิใหม่ ชื่อหมวดหมู่ใหม่** แยกบรรทัดเพื่อแก้หลายหมวดหมู่",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="รายการหมวดหมู่ปัจจุบัน",
            value=category_list,
            inline=False
        )
        
        embed.add_field(
            name="ตัวอย่าง",
            value="```\n!แก้ไขหมวดสินค้า\nmoney 💰 เงินสด\nweapon 🗡️ อาวุธต่อสู้\nitem 📦 ไอเทมทั่วไป```",
            inline=False
        )
        
        await ctx.send(embed=embed)
        return
    
    # แยกข้อมูลเป็นบรรทัด
    lines = ข้อมูล.strip().split('\n')
    edited_categories = []
    failed_categories = []
    
    # ประมวลผลแต่ละบรรทัด
    for line in lines:
        parts = line.strip().split(maxsplit=2)
        
        # ตรวจสอบว่ามีข้อมูลเพียงพอหรือไม่
        if len(parts) < 2:
            failed_categories.append((line, "ข้อมูลไม่เพียงพอ"))
            continue
        
        # แยกข้อมูลหมวดหมู่, อีโมจิ, และชื่อ
        category_code = parts[0]
        
        # ตรวจสอบรูปแบบการป้อนข้อมูล
        if len(parts) == 2:
            # มีแค่รหัสหมวดหมู่และชื่อ/อีโมจิ
            second_part = parts[1]
            # ตรวจสอบว่าเป็นอีโมจิหรือชื่อ
            if len(second_part) <= 2 or any(ord(c) > 127 for c in second_part[:2]):
                # น่าจะเป็นอีโมจิ
                emoji = second_part
                name = None
            else:
                # น่าจะเป็นชื่อหมวดหมู่
                emoji = None
                name = second_part
        else:
            # มีครบทั้งรหัสหมวดหมู่, อีโมจิ, และชื่อ
            emoji = parts[1]
            name = parts[2]
        
        # แก้ไขหมวดหมู่
        result = edit_category(category_code, emoji, name)
        
        if result:
            edited_categories.append(category_code)
        else:
            failed_categories.append((category_code, f"ไม่พบหมวดหมู่ {category_code}"))
    
    # สรุปผลการแก้ไข
    embed = discord.Embed(
        title="🔄 ผลการแก้ไขหมวดหมู่สินค้า",
        color=discord.Color.green() if edited_categories else discord.Color.red()
    )
    
    if edited_categories:
        # แสดงรายการหมวดหมู่ที่แก้ไขสำเร็จ
        success_list = "\n".join([f"- {code}: {CATEGORY_EMOJIS.get(code, '❓')} {CATEGORY_NAMES[code]}" for code in edited_categories])
        embed.add_field(
            name=f"✅ แก้ไขสำเร็จ ({len(edited_categories)} รายการ)",
            value=success_list,
            inline=False
        )
    
    if failed_categories:
        # แสดงรายการที่แก้ไขไม่สำเร็จ
        fail_list = "\n".join([f"- {code}: {reason}" for code, reason in failed_categories])
        embed.add_field(
            name=f"❌ แก้ไขไม่สำเร็จ ({len(failed_categories)} รายการ)",
            value=fail_list,
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.tree.command(name="ร้าน", description="เปิดร้านค้าเพื่อเลือกซื้อสินค้า")
async def shop_slash(interaction: discord.Interaction, ประเทศ: str = None, หมวด: str = None):
    """Slash command to open the shop
    
    Args:
        ประเทศ: Country name (thailand, japan, usa)
        หมวด: Category name (money, weapon, item, car, fashion, rentcar)
    """
    # กำหนดค่าเริ่มต้น
    country = "thailand"  # ประเทศไทยเป็นค่าเริ่มต้น
    category = "item"     # หมวดหมู่ไอเทมเป็นค่าเริ่มต้น
    
    # ตรวจสอบอาร์กิวเมนต์ประเทศ
    if ประเทศ:
        # ถ้าเป็นชื่อประเทศภาษาอังกฤษ
        if ประเทศ.lower() in COUNTRIES:
            country = ประเทศ.lower()
        # ถ้าเป็นชื่อประเทศภาษาไทย
        elif ประเทศ in ["ไทย", "ญี่ปุ่น", "อเมริกา"]:
            # แปลงชื่อประเทศภาษาไทยเป็นภาษาอังกฤษ
            thai_to_eng = {"ไทย": "thailand", "ญี่ปุ่น": "japan", "อเมริกา": "usa"}
            country = thai_to_eng[ประเทศ]
        else:
            # แสดงข้อความแนะนำหากระบุประเทศไม่ถูกต้อง
            countries_str = ", ".join([f"`{COUNTRY_NAMES[c]}`" for c in COUNTRIES])
            await interaction.response.send_message(f"❌ ไม่พบประเทศที่ระบุ\nประเทศที่มี: {countries_str}")
            return
    
    # ตรวจสอบอาร์กิวเมนต์หมวดหมู่
    if หมวด:
        # ถ้าเป็นชื่อหมวดหมู่ภาษาอังกฤษ
        if หมวด.lower() in CATEGORIES:
            category = หมวด.lower()
        # ถ้าเป็นชื่อหมวดหมู่ภาษาไทย
        elif หมวด in ["เงิน", "อาวุธ", "ไอเทม", "รถ", "แฟชั่น", "เช่ารถ"]:
            # แปลงชื่อหมวดหมู่ภาษาไทยเป็นภาษาอังกฤษ
            thai_to_eng = {"เงิน": "money", "อาวุธ": "weapon", "ไอเทม": "item", 
                          "รถ": "car", "แฟชั่น": "fashion", "เช่ารถ": "rentcar"}
            category = thai_to_eng[หมวด]
        else:
            # แสดงข้อความแนะนำหากระบุหมวดหมู่ไม่ถูกต้อง
            categories_str = ", ".join([f"`{CATEGORY_NAMES[c]}`" for c in CATEGORIES])
            await interaction.response.send_message(f"❌ ไม่พบหมวดหมู่ที่ระบุ\nหมวดหมู่ที่มี: {categories_str}")
            return
    
    # โหลดสินค้าตามประเทศและหมวดหมู่
    products = load_products(country, category)
    
    # ตรวจสอบว่ามีสินค้าในประเทศและหมวดหมู่นี้หรือไม่
    if not products:
        await interaction.response.send_message(f"❌ ไม่มีสินค้าในประเทศ `{COUNTRY_NAMES[country]}` หมวด `{CATEGORY_NAMES[category]}`")
        return
    
    # สร้าง view ที่แสดงสินค้าพร้อมปุ่มเลือกประเทศและหมวดหมู่
    view = CategoryShopView(CATEGORIES, current_category=category, country=country)
    
    # หากไม่มีสินค้าในร้านทั้งหมด
    if not view.all_products:
        await interaction.response.send_message(f"❌ ไม่มีสินค้าในร้าน")
        return
    
    # แสดงชื่อร้านและสินค้า
    title = f"🛍️ สินค้าในประเทศ `{COUNTRY_NAMES[country]}` หมวด `{CATEGORY_NAMES[category]}`"
    await interaction.response.send_message(title, view=view)

@bot.tree.command(name="สินค้าทั้งหมด", description="แสดงรายการสินค้าทั้งหมด")
@discord.app_commands.describe(หมวด="หมวดหมู่สินค้าที่ต้องการดู")
@discord.app_commands.choices(หมวด=[
    discord.app_commands.Choice(name="เงิน", value="money"),
    discord.app_commands.Choice(name="อาวุธ", value="weapon"),
    discord.app_commands.Choice(name="ไอเทม", value="item"),
    discord.app_commands.Choice(name="ไอเทมต่อสู้", value="story"),
    discord.app_commands.Choice(name="รถยนต์", value="car"),
    discord.app_commands.Choice(name="แฟชั่น", value="fashion"),
    discord.app_commands.Choice(name="เช่ารถ", value="rentcar")
])
async def list_products_slash(interaction: discord.Interaction, หมวด: str = None):
    """Slash command to list all products"""
    # If category is specified, load products from that category
    if หมวด:
        products = load_products(หมวด)
        title = f"📋 รายการสินค้าหมวด `{หมวด}`"
    else:
        # Otherwise, collect products from all categories
        all_products = []
        categories = ["money", "weapon", "item", "car", "fashion", "rentcar"]
        
        for category in categories:
            products = load_products(category)
            if products:
                # Add category name to each product for display
                for product in products:
                    product['category'] = category
                all_products.extend(products)
        
        products = all_products
        title = "📋 รายการสินค้าทั้งหมด"
    
    if not products:
        if หมวด:
            await interaction.response.send_message(f"❌ ไม่มีสินค้าในหมวด `{หมวด}`")
        else:
            await interaction.response.send_message("❌ ไม่มีสินค้าในร้าน")
        return
        
    embed = discord.Embed(title=title, color=0x3498db)
    
    # Group products by category if showing all products
    if not หมวด:
        # Sort products by category for better organization
        products = sorted(products, key=lambda x: x.get('category', ''))
        
        current_category = None
        for product in products:
            category = product.get('category')
            
            # Add category header when category changes
            if category != current_category:
                embed.add_field(
                    name=f"🔸 หมวด {category}", 
                    value="─────────", 
                    inline=False
                )
                current_category = category
            
            embed.add_field(
                name=f"{product['emoji']} {product['name']}",
                value=f"ราคา: {product['price']:.2f}฿",
                inline=True
            )
    else:
        # Simple list for a specific category
        for product in products:
            embed.add_field(
                name=f"{product['emoji']} {product['name']}",
                value=f"ราคา: {product['price']}฿",
                inline=True
            )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="เพิ่มสินค้า", description="เพิ่มสินค้าใหม่เข้าร้าน (Admin only)")
@discord.app_commands.describe(
    อีโมจิ="อีโมจิที่แสดงหน้าสินค้า (สามารถใช้อีโมจิของเซิร์ฟเวอร์ได้ เช่น :emoji_name:)",
    ชื่อ="ชื่อของสินค้า",
    ราคา="ราคาของสินค้า (ตัวเลขทศนิยมได้ เช่น 99.50)",
    หมวด="หมวดหมู่ของสินค้า (เลือกได้)",
    ประเทศ="ประเทศที่จะเพิ่มสินค้า (เลือกได้)"
)
@discord.app_commands.choices(หมวด=[
    discord.app_commands.Choice(name="เงิน", value="money"),
    discord.app_commands.Choice(name="อาวุธ", value="weapon"),
    discord.app_commands.Choice(name="ไอเทม", value="item"),
    discord.app_commands.Choice(name="ไอเทมต่อสู้", value="story"),
    discord.app_commands.Choice(name="รถยนต์", value="car"),
    discord.app_commands.Choice(name="แฟชั่น", value="fashion"),
    discord.app_commands.Choice(name="เช่ารถ", value="rentcar")
])
@discord.app_commands.choices(ประเทศ=[
    discord.app_commands.Choice(name="ไทย", value="thailand"),
    discord.app_commands.Choice(name="ญี่ปุ่น", value="japan"),
    discord.app_commands.Choice(name="อเมริกา", value="usa")
])
async def add_product_slash(interaction: discord.Interaction, อีโมจิ: str, ชื่อ: str, ราคา: float, หมวด: str = "item", ประเทศ: str = "thailand"):
    """Slash command to add a new product (Admin only)
    
    Args:
        อีโมจิ: อีโมจิของสินค้า
        ชื่อ: ชื่อของสินค้า
        ราคา: ราคาของสินค้า
        หมวด: หมวดหมู่ของสินค้า (money, weapon, item, car, fashion, rentcar)
        ประเทศ: ประเทศที่สินค้าอยู่ (thailand, japan, usa)
    """
    # Check if user has Administrator permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ ต้องการสิทธิ์ผู้ดูแล (Administrator)", ephemeral=True)
        return
        
    try:
        # Parse custom emoji if provided in <:name:id> format
        emoji_to_use = อีโมจิ
        if อีโมจิ.startswith("<") and อีโมจิ.endswith(">"):
            # Already in proper format, use as is
            pass
        elif อีโมจิ.startswith(":") and อีโมจิ.endswith(":"):
            # Convert :emoji_name: to actual emoji
            emoji_name = อีโมจิ.strip(":")
            # Try to find the emoji in the server
            found_emoji = discord.utils.get(interaction.guild.emojis, name=emoji_name)
            if found_emoji:
                emoji_to_use = str(found_emoji)
            else:
                await interaction.response.send_message(f"❌ ไม่พบอีโมจิ '{อีโมจิ}' ในเซิร์ฟเวอร์นี้", ephemeral=True)
                return
        
        # แปลงประเทศภาษาไทยเป็นภาษาอังกฤษ
        if ประเทศ in ["ไทย", "ญี่ปุ่น", "อเมริกา"]:
            thai_to_eng = {"ไทย": "thailand", "ญี่ปุ่น": "japan", "อเมริกา": "usa"}
            ประเทศ = thai_to_eng[ประเทศ]
        
        # ตรวจสอบว่าประเทศถูกต้อง
        if ประเทศ.lower() not in COUNTRIES:
            countries_str = ", ".join([f"`{COUNTRY_NAMES[c]}`" for c in COUNTRIES])
            await interaction.response.send_message(f"❌ ประเทศไม่ถูกต้อง ประเทศที่รองรับ: {countries_str}", ephemeral=True)
            return
        
        # แปลงหมวดหมู่ภาษาไทยเป็นภาษาอังกฤษ
        if หมวด in ["เงิน", "อาวุธ", "ไอเทม", "รถ", "แฟชั่น", "เช่ารถ"]:
            thai_to_eng = {"เงิน": "money", "อาวุธ": "weapon", "ไอเทม": "item", 
                          "รถ": "car", "แฟชั่น": "fashion", "เช่ารถ": "rentcar"}
            หมวด = thai_to_eng[หมวด]
        
        # แปลงหมวดหมู่เป็นตัวอักษรพิมพ์เล็ก
        หมวด = หมวด.lower()
        ประเทศ = ประเทศ.lower()
        
        # โหลดสินค้าที่มีอยู่แล้ว
        products = load_products(ประเทศ, หมวด)
        
        # ตรวจสอบว่ามีสินค้านี้อยู่แล้วหรือไม่
        for product in products:
            if product["name"] == ชื่อ:
                await interaction.response.send_message(f"❌ มีสินค้า `{ชื่อ}` อยู่แล้วในประเทศ `{COUNTRY_NAMES[ประเทศ]}` หมวด `{CATEGORY_NAMES[หมวด]}`", ephemeral=True)
                return
        
        # สร้างสินค้าใหม่
        new_product = {
            "name": ชื่อ, 
            "price": ราคา, 
            "emoji": emoji_to_use, 
            "category": หมวด,
            "country": ประเทศ
        }
        
        # เพิ่มสินค้าใหม่ลงในรายการ
        products.append(new_product)
        
        # บันทึกสินค้าลงไฟล์
        save_products(products, ประเทศ, หมวด)
        
        # บันทึกลงไฟล์หมวดหมู่โดยตรง
        save_product_to_category(new_product)
        
        # แจ้งยืนยันกับผู้ใช้
        await interaction.response.send_message(f"✅ เพิ่มสินค้า: {emoji_to_use} {ชื่อ} - {ราคา:.2f}฿ (ประเทศ: {COUNTRY_NAMES[ประเทศ]}, หมวด: {CATEGORY_NAMES[หมวด]})")
    except Exception as e:
        await interaction.response.send_message(f"❌ เกิดข้อผิดพลาด: {str(e)}", ephemeral=True)

@bot.tree.command(name="ลบสินค้า", description="ลบสินค้าออกจากร้าน (Admin only)")
@discord.app_commands.describe(ชื่อ="ชื่อของสินค้าที่ต้องการลบ")
async def remove_product_slash(interaction: discord.Interaction, ชื่อ: str):
    """Slash command to remove a product (Admin only)"""
    # Check if user has Administrator permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ ต้องการสิทธิ์ผู้ดูแล (Administrator)", ephemeral=True)
        return
        
    try:
        products = load_products()
        original_count = len(products)
        
        # Find product to show category before deletion
        product_to_delete = next((p for p in products if p["name"] == ชื่อ), None)
        if not product_to_delete:
            await interaction.response.send_message(f"❌ ไม่พบสินค้า '{ชื่อ}'", ephemeral=True)
            return
        
        # Remove the product
        products = [p for p in products if p["name"] != ชื่อ]
        save_products(products)
        
        category = product_to_delete.get("category", "ไม่ระบุหมวด")
        await interaction.response.send_message(f"🗑️ ลบสินค้า '{ชื่อ}' จากหมวด '{category}' เรียบร้อย")
    except Exception as e:
        await interaction.response.send_message(f"❌ เกิดข้อผิดพลาด: {str(e)}", ephemeral=True)

@bot.tree.command(name="แก้ไขสินค้า", description="แก้ไขข้อมูลสินค้า (Admin only)")
@discord.app_commands.describe(
    ชื่อ="ชื่อของสินค้าที่ต้องการแก้ไข",
    ชื่อใหม่="ชื่อใหม่ของสินค้า (ไม่ระบุหากไม่ต้องการเปลี่ยน)",
    ราคาใหม่="ราคาใหม่ของสินค้า (ตัวเลขทศนิยมได้ เช่น 99.50, ไม่ระบุหากไม่ต้องการเปลี่ยน)",
    อีโมจิใหม่="อีโมจิใหม่ของสินค้า (ไม่ระบุหากไม่ต้องการเปลี่ยน)",
    หมวดใหม่="หมวดหมู่ใหม่ของสินค้า (ไม่ระบุหากไม่ต้องการเปลี่ยน)"
)
@discord.app_commands.choices(หมวดใหม่=[
    discord.app_commands.Choice(name="เงิน", value="money"),
    discord.app_commands.Choice(name="อาวุธ", value="weapon"),
    discord.app_commands.Choice(name="ไอเทม", value="item"),
    discord.app_commands.Choice(name="ไอเทมต่อสู้", value="story"),
    discord.app_commands.Choice(name="รถยนต์", value="car"),
    discord.app_commands.Choice(name="แฟชั่น", value="fashion"),
    discord.app_commands.Choice(name="เช่ารถ", value="rentcar")
])
async def edit_product_slash(interaction: discord.Interaction, ชื่อ: str, ประเทศ: str = "thailand", อีโมจิใหม่: str = None, ชื่อใหม่: str = None, ราคาใหม่: float = None, หมวดใหม่: str = None, ประเทศใหม่: str = None):
    """Slash command to edit a product (Admin only)"""
    # Check if user has Administrator permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ ต้องการสิทธิ์ผู้ดูแล (Administrator)", ephemeral=True)
        return
        
    # Check if the new category is valid if provided
    if หมวดใหม่ and หมวดใหม่ not in CATEGORIES:
        categories_str = ", ".join([f"`{CATEGORY_NAMES[cat]}`" for cat in CATEGORIES])
        await interaction.response.send_message(f"❌ หมวดหมู่ไม่ถูกต้อง หมวดหมู่ที่มี: {categories_str}", ephemeral=True)
        return
        
    try:
        products = load_products()
        
        # Find the product
        found = False
        for product in products:
            if product["name"] == ชื่อ:
                found = True
                
                # Update product details if provided
                if ชื่อใหม่:
                    product["name"] = ชื่อใหม่
                if ราคาใหม่ is not None:
                    product["price"] = ราคาใหม่
                if อีโมจิใหม่:
                    product["emoji"] = อีโมจิใหม่
                if หมวดใหม่:
                    product["category"] = หมวดใหม่
                
                break
        
        if not found:
            await interaction.response.send_message(f"❌ ไม่พบสินค้า '{ชื่อ}'", ephemeral=True)
            return
            
        save_products(products)
        
        product_name = ชื่อใหม่ if ชื่อใหม่ else ชื่อ
        
        # Show updated product details
        product = next((p for p in products if p["name"] == product_name), None)
        if product:
            embed = discord.Embed(title="✅ ข้อมูลสินค้าที่อัปเดต", color=0x00ff00)
            embed.add_field(name="ชื่อ", value=product["name"], inline=True)
            embed.add_field(name="ราคา", value=f"{product['price']:.2f}฿", inline=True)
            embed.add_field(name="อีโมจิ", value=product["emoji"], inline=True)
            
            # Add category field if present
            if "category" in product:
                category_name = product["category"]
                # ใช้ CATEGORY_NAMES ที่นิยามไว้แล้วแทน dictionary ที่กำหนดใหม่
                category_display = CATEGORY_NAMES.get(category_name, category_name)
                embed.add_field(name="หมวดหมู่", value=category_display, inline=True)
                
            await interaction.response.send_message(embed=embed)
            
    except Exception as e:
        await interaction.response.send_message(f"❌ เกิดข้อผิดพลาด: {str(e)}", ephemeral=True)

@bot.tree.command(name="ประวัติ", description="ดูประวัติการซื้อล่าสุด (Admin only)")
@discord.app_commands.describe(จำนวน="จำนวนรายการที่ต้องการดู (ค่าเริ่มต้นคือ 5)")
async def history_slash(interaction: discord.Interaction, จำนวน: int = 5):
    """Slash command to view purchase history (Admin only)"""
    # Check if user has Administrator permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ ต้องการสิทธิ์ผู้ดูแล (Administrator)", ephemeral=True)
        return
        
    try:
        if not HISTORY_FILE.exists() or HISTORY_FILE.stat().st_size == 0:
            await interaction.response.send_message("❌ ยังไม่มีประวัติการซื้อ", ephemeral=True)
            return
            
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        if not lines:
            await interaction.response.send_message("❌ ยังไม่มีประวัติการซื้อ", ephemeral=True)
            return
            
        # Get the last N entries
        entries = lines[-จำนวน:] if จำนวน > 0 else lines
            
        embed = discord.Embed(title="📜 ประวัติการซื้อ", color=0x00ff00)
        for line in entries:
            try:
                d = json.loads(line)
                dt = datetime.fromisoformat(d['timestamp'])
                formatted_time = dt.strftime("%d/%m/%Y %H:%M")
                summary = ", ".join([f"{x['name']} x{x['qty']}" for x in d['items']])
                embed.add_field(
                    name=f"👤 {d['user']} ({formatted_time})",
                    value=f"{summary} = {d['total']}฿",
                    inline=False
                )
            except (json.JSONDecodeError, KeyError) as e:
                continue
                
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"❌ เกิดข้อผิดพลาด: {str(e)}", ephemeral=True)

@bot.tree.command(name="ช่วยเหลือ", description="แสดงข้อมูลคำสั่งทั้งหมด")
async def help_slash(interaction: discord.Interaction):
    """Slash command to display help information"""
    embed = discord.Embed(title="📚 คำสั่งสำหรับร้านค้า", color=0x4f0099)
    
    # General commands
    embed.add_field(
        name="🛒 เปิดร้านค้า",
        value="ใช้คำสั่ง `!ร้าน` หรือ `/ร้าน` เพื่อเปิดร้านค้าและเลือกซื้อสินค้า",
        inline=False
    )
    
    embed.add_field(
        name="📋 ดูรายการสินค้า",
        value="ใช้คำสั่ง `!สินค้าทั้งหมด` หรือ `/สินค้าทั้งหมด` เพื่อดูรายการสินค้าทั้งหมด",
        inline=False
    )
    
    # Admin commands
    embed.add_field(
        name="👑 คำสั่งสำหรับแอดมิน",
        value="คำสั่งต่อไปนี้ใช้ได้เฉพาะผู้ที่มีสิทธิ์แอดมิน",
        inline=False
    )
    
    embed.add_field(
        name="📥 เพิ่มสินค้า",
        value="ใช้คำสั่ง `!เพิ่มสินค้า` หรือ `/เพิ่มสินค้า` เพื่อเพิ่มสินค้าใหม่เข้าสู่ระบบ",
        inline=False
    )
    
    embed.add_field(
        name="🗑️ ลบสินค้า",
        value="ใช้คำสั่ง `!ลบสินค้า` หรือ `/ลบสินค้า` เพื่อลบสินค้าออกจากระบบ",
        inline=False
    )
    embed.add_field(
        name="✏️ แก้ไขสินค้า",
        value="ใช้คำสั่ง `!แก้ไขสินค้า` หรือ `/แก้ไขสินค้า` เพื่อแก้ไขข้อมูลสินค้าที่มีอยู่แล้ว",
        inline=False
    )
    embed.add_field(
        name="📋 ประวัติการซื้อ",
        value="ใช้คำสั่ง `!ประวัติ` หรือ `/ประวัติ` เพื่อดูประวัติการซื้อล่าสุด",
        inline=False
    )
    
    embed.add_field(
        name="🌏 จัดการประเทศ",
        value="ใช้คำสั่ง `!แก้ไขประเทศ` หรือ `/แก้ไขประเทศ` เพื่อแก้ไขชื่อและอีโมจิของประเทศ",
        inline=False
    )
    
    embed.add_field(
        name="📲 QR Code และข้อความขอบคุณ",
        value="ใช้คำสั่ง `!qrcode` และ `!ขอบคุณ` หรือ `/qrcode` และ `/ขอบคุณ` เพื่อปรับแต่งระบบการชำระเงิน",
        inline=False
    )
    
    embed.add_field(
        name="⚠️ ลบสินค้าทั้งหมด",
        value="ใช้คำสั่ง `!ลบสินค้าทั้งหมด` หรือ `/ลบสินค้าทั้งหมด` เพื่อลบสินค้าทั้งหมดในระบบ",
        inline=False
    )
    
    embed.add_field(
        name="📖 ตัวอย่างคำสั่งแอดมิน",
        value="ใช้คำสั่ง `!ตัวอย่างแอดมิน` เพื่อดูตัวอย่างการใช้คำสั่งสำหรับแอดมินทั้งหมด",
        inline=False
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ลบสินค้าทั้งหมด", description="ลบรายการสินค้าทั้งหมดในทุกหมวดหมู่และทุกประเทศ (Admin only)")
async def delete_all_products_slash(interaction: discord.Interaction):
    """Slash command to delete all products from all categories in all countries completely (Admin only)"""
    # Check if user has Administrator permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ ต้องการสิทธิ์ผู้ดูแล (Administrator)", ephemeral=True)
        return
        
    try:
        # Create confirmation message
        confirm_embed = discord.Embed(
            title="⚠️ ยืนยันการลบสินค้าทั้งหมด",
            description="คุณกำลังจะลบสินค้าทั้งหมดในทุกหมวดหมู่และทุกประเทศโดยสมบูรณ์\n**การดำเนินการนี้ไม่สามารถเรียกคืนได้**",
            color=discord.Color.red()
        )
        
        # Create confirmation buttons
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)  # Timeout after 60 seconds
                
            @discord.ui.button(label="ยืนยันการลบ", style=discord.ButtonStyle.danger)
            async def confirm_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != interaction.user.id:
                    await button_interaction.response.send_message("❌ คุณไม่ใช่ผู้ใช้คำสั่งนี้", ephemeral=True)
                    return
                    
                success = delete_all_products()
                
                if success:
                    await button_interaction.response.edit_message(
                        content="✅ ลบสินค้าทั้งหมดในทุกหมวดหมู่และทุกประเทศเรียบร้อยแล้ว",
                        embed=None,
                        view=None
                    )
                else:
                    await button_interaction.response.edit_message(
                        content="❌ เกิดข้อผิดพลาดในการลบสินค้าทั้งหมด",
                        embed=None,
                        view=None
                    )
                
            @discord.ui.button(label="ยกเลิก", style=discord.ButtonStyle.secondary)
            async def cancel_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != interaction.user.id:
                    await button_interaction.response.send_message("❌ คุณไม่ใช่ผู้ใช้คำสั่งนี้", ephemeral=True)
                    return
                    
                await button_interaction.response.edit_message(
                    content="❌ ยกเลิกการลบสินค้า",
                    embed=None,
                    view=None
                )
                
        # Send the confirmation message with buttons
        await interaction.response.send_message(embed=confirm_embed, view=ConfirmView())
            
    except Exception as e:
        await interaction.response.send_message(f"❌ เกิดข้อผิดพลาด: {str(e)}", ephemeral=True)

@bot.tree.command(name="ลบสินค้าทั้งหมวด", description="ลบรายการสินค้าทั้งหมดในหมวดที่เลือก (Admin only)")
@discord.app_commands.describe(หมวด="หมวดหมู่ที่ต้องการลบสินค้าทั้งหมด")
@discord.app_commands.choices(หมวด=[
    discord.app_commands.Choice(name="เงิน", value="money"),
    discord.app_commands.Choice(name="อาวุธ", value="weapon"),
    discord.app_commands.Choice(name="ไอเทม", value="item"),
    discord.app_commands.Choice(name="ไอเทมต่อสู้", value="story"),
    discord.app_commands.Choice(name="รถยนต์", value="car"),
    discord.app_commands.Choice(name="แฟชั่น", value="fashion"),
    discord.app_commands.Choice(name="เช่ารถ", value="rentcar")
])
async def clear_category_slash(interaction: discord.Interaction, หมวด: str):
    """Slash command to remove all products from a category (Admin only)"""
    # Check if user has Administrator permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ ต้องการสิทธิ์ผู้ดูแล (Administrator)", ephemeral=True)
        return
        
    try:
        # Add confirmation prompt
        confirm_embed = discord.Embed(
            title="⚠️ ยืนยันการลบสินค้าทั้งหมดในหมวด",
            description=f"คุณกำลังจะลบสินค้าทั้งหมดในหมวด **{หมวด}**\nการดำเนินการนี้ไม่สามารถเรียกคืนได้",
            color=discord.Color.red()
        )
        
        # Create confirmation buttons
        class ConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)  # Timeout after 60 seconds
                
            @discord.ui.button(label="ยืนยันการลบ", style=discord.ButtonStyle.danger)
            async def confirm_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != interaction.user.id:
                    await button_interaction.response.send_message("❌ คุณไม่ใช่ผู้ใช้คำสั่งนี้", ephemeral=True)
                    return
                    
                success = clear_category_products(หมวด)
                
                if success:
                    await button_interaction.response.edit_message(
                        content=f"✅ ลบสินค้าทั้งหมดในหมวด **{หมวด}** เรียบร้อยแล้ว",
                        embed=None,
                        view=None
                    )
                else:
                    await button_interaction.response.edit_message(
                        content=f"❌ เกิดข้อผิดพลาดในการลบสินค้าในหมวด **{หมวด}**",
                        embed=None,
                        view=None
                    )
                
            @discord.ui.button(label="ยกเลิก", style=discord.ButtonStyle.secondary)
            async def cancel_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                if button_interaction.user.id != interaction.user.id:
                    await button_interaction.response.send_message("❌ คุณไม่ใช่ผู้ใช้คำสั่งนี้", ephemeral=True)
                    return
                    
                await button_interaction.response.edit_message(
                    content="❌ ยกเลิกการลบสินค้า",
                    embed=None,
                    view=None
                )
        
        # Send confirmation message with buttons
        await interaction.response.send_message(embed=confirm_embed, view=ConfirmView())
        
    except Exception as e:
        await interaction.response.send_message(f"❌ เกิดข้อผิดพลาด: {str(e)}", ephemeral=True)

@bot.tree.command(name="เพิ่มสินค้าเก่า", description="คำสั่งนี้ถูกแทนที่ด้วยคำสั่ง เพิ่มสินค้า แล้ว")
async def batch_add_products_slash_old(interaction: discord.Interaction):
    """Slash command placeholder (deprecated)"""
    await interaction.response.send_message("⚠️ คำสั่งนี้ถูกแทนที่แล้ว กรุณาใช้ `/เพิ่มสินค้า` แทน", ephemeral=True)

# หมายเหตุ: คำสั่งจัดการประเทศถูกลบออกตามคำขอของผู้ใช้ (เดิมคือคำสั่ง เพิ่มประเทศ/addcountry)

@bot.command(name="แก้ไขประเทศ", aliases=["editcountry"])
async def edit_country_command(ctx, *, ข้อมูล: str = None):
    """Command to edit countries' name and emojis (Admin only)
    
    Args:
        ข้อมูล: ข้อมูลประเทศที่ต้องการแก้ไข โดยแบ่งเป็นบรรทัด แต่ละบรรทัด
               ใช้รูปแบบ "รหัสประเทศ อีโมจิ ชื่อประเทศ" หรือ "รหัสประเทศ อีโมจิ" หรือ
               "รหัสประเทศ ชื่อประเทศ" ได้
               
    ตัวอย่าง:
        !แก้ไขประเทศ
        1 🇹🇭 ไทยแลนด์
        2 🌸 ญี่ปุ่น
        3 🦅 อเมริกา
    """
    # Check if user is admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมินเท่านั้น")
        return
    
    # ตรวจสอบว่ามีข้อมูลหรือไม่
    if ข้อมูล is None:
        # แสดงรายการประเทศทั้งหมดที่มี
        country_list = "\n".join([f"- {code}: {COUNTRY_EMOJIS.get(code, '❓')} {COUNTRY_NAMES[code]}" for code in COUNTRIES])
        
        embed = discord.Embed(
            title="🌏 รายการประเทศทั้งหมด",
            description="ใช้คำสั่ง `!แก้ไขประเทศ` ตามด้วยข้อมูลในรูปแบบ **รหัสประเทศ อีโมจิ ชื่อประเทศ** แยกบรรทัดเพื่อแก้หลายประเทศ",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="รายการประเทศปัจจุบัน",
            value=country_list,
            inline=False
        )
        
        embed.add_field(
            name="ตัวอย่าง",
            value="```\n!แก้ไขประเทศ\n1 🇹🇭 ไทยแลนด์\n2 🌸 ญี่ปุ่น\n3 🦅 อเมริกา```",
            inline=False
        )
        
        await ctx.send(embed=embed)
        return
    
    # แยกข้อมูลเป็นบรรทัด
    lines = ข้อมูล.strip().split('\n')
    edited_countries = []
    failed_countries = []
    
    # ประมวลผลแต่ละบรรทัด
    for line in lines:
        parts = line.strip().split(maxsplit=2)
        
        # ตรวจสอบว่ามีข้อมูลเพียงพอหรือไม่
        if len(parts) < 2:
            failed_countries.append((line, "ข้อมูลไม่เพียงพอ"))
            continue
        
        # แยกข้อมูลประเทศ, อีโมจิ, และชื่อ
        country_code = parts[0]
        
        # ตรวจสอบรูปแบบการป้อนข้อมูล
        if len(parts) == 2:
            # มีแค่รหัสประเทศและชื่อ/อีโมจิ
            second_part = parts[1]
            # ตรวจสอบว่าเป็นอีโมจิหรือชื่อ
            if len(second_part) <= 2 or any(ord(c) > 127 for c in second_part[:2]):
                # น่าจะเป็นอีโมจิ
                emoji = second_part
                name = None
            else:
                # น่าจะเป็นชื่อประเทศ
                emoji = None
                name = second_part
        else:
            # มีทั้งรหัสประเทศ, อีโมจิ, และชื่อ
            emoji = parts[1]
            name = parts[2]
        
        # เก็บข้อมูลเดิมไว้แสดงการเปลี่ยนแปลง
        old_name = COUNTRY_NAMES.get(country_code, "ไม่พบชื่อเดิม")
        old_emoji = COUNTRY_EMOJIS.get(country_code, "❓")
        
        # ลองแก้ไขประเทศ
        success = edit_country(country_code, name, emoji)
        
        if success:
            # เก็บข้อมูลประเทศที่แก้ไขสำเร็จ
            edited_info = f"**{country_code}**: "
            changes = []
            
            if emoji:
                changes.append(f"อีโมจิ: {old_emoji} → {emoji}")
            
            if name:
                changes.append(f"ชื่อ: {old_name} → {name}")
                
            edited_info += ", ".join(changes)
            edited_countries.append(edited_info)
        else:
            failed_countries.append((country_code, "ไม่พบรหัสประเทศนี้"))
    
    # สร้าง embed สำหรับแสดงผล
    embed = discord.Embed(title="🌏 ผลการแก้ไขประเทศ", color=discord.Color.green())
    
    # แสดงประเทศที่แก้ไขสำเร็จ
    if edited_countries:
        embed.add_field(
            name=f"✅ แก้ไขสำเร็จ ({len(edited_countries)} ประเทศ)",
            value="\n".join(edited_countries),
            inline=False
        )
    
    # แสดงประเทศที่แก้ไขไม่สำเร็จ
    if failed_countries:
        failed_text = "\n".join([f"- {code}: {reason}" for code, reason in failed_countries])
        embed.add_field(
            name=f"❌ แก้ไขไม่สำเร็จ ({len(failed_countries)} รายการ)",
            value=failed_text,
            inline=False
        )
    
    # แสดงรายการประเทศทั้งหมดในปัจจุบัน
    country_list = "\n".join([f"- {code}: {COUNTRY_EMOJIS.get(code, '❓')} {COUNTRY_NAMES[code]}" for code in COUNTRIES])
    embed.add_field(
        name="รายการประเทศปัจจุบัน",
        value=country_list,
        inline=False
    )
    
    await ctx.send(embed=embed)

# หมายเหตุ: คำสั่งลบประเทศถูกลบออกตามคำขอผู้ใช้ (เดิมคือคำสั่ง ลบประเทศ/removecountry)

# หมายเหตุ: คำสั่งสำหรับจัดการประเทศบางส่วนถูกลบออกตามคำขอของผู้ใช้

# Slash command เพื่อแก้ไขประเทศ
@bot.tree.command(name="แก้ไขประเทศ", description="แก้ไขชื่อและอีโมจิของประเทศ (เฉพาะแอดมิน)")
@discord.app_commands.describe(ข้อมูล="ข้อมูลประเทศที่ต้องการแก้ไข เช่น '1 🇹🇭 ไทยแลนด์' (ถ้าไม่ระบุ จะแสดงรายการประเทศปัจจุบัน)")
async def edit_country_slash(interaction: discord.Interaction, ข้อมูล: str = None):
    """Slash command to edit countries' name and emojis (Admin only)"""
    # Check if user is admin
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมินเท่านั้น", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=False)
    
    # ตรวจสอบว่ามีข้อมูลหรือไม่
    if ข้อมูล is None:
        # แสดงรายการประเทศทั้งหมดที่มี
        country_list = "\n".join([f"- {code}: {COUNTRY_EMOJIS.get(code, '❓')} {COUNTRY_NAMES[code]}" for code in COUNTRIES])
        
        embed = discord.Embed(
            title="🌏 รายการประเทศทั้งหมด",
            description="ใช้คำสั่ง `/แก้ไขประเทศ` ตามด้วยข้อมูลในรูปแบบ **รหัสประเทศ อีโมจิ ชื่อประเทศ**",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="รายการประเทศปัจจุบัน",
            value=country_list,
            inline=False
        )
        
        embed.add_field(
            name="ตัวอย่าง",
            value="```\n/แก้ไขประเทศ ข้อมูล:1 🇹🇭 ไทยแลนด์```\n```\n/แก้ไขประเทศ ข้อมูล:2 🌸 ญี่ปุ่น```\n```\n/แก้ไขประเทศ ข้อมูล:3 🦅 อเมริกา```",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
        return
    
    # แยกข้อมูลเป็นบรรทัด (กรณีใน slash command จะมีแค่บรรทัดเดียว)
    parts = ข้อมูล.strip().split(maxsplit=2)
    
    # ตรวจสอบว่ามีข้อมูลเพียงพอหรือไม่
    if len(parts) < 2:
        await interaction.followup.send("❌ ข้อมูลไม่เพียงพอ โปรดระบุให้ครบถ้วน (รหัสประเทศ อีโมจิ/ชื่อ)")
        return
    
    # แยกข้อมูลประเทศ, อีโมจิ, และชื่อ
    country_code = parts[0]
    
    # ตรวจสอบรูปแบบการป้อนข้อมูล
    if len(parts) == 2:
        # มีแค่รหัสประเทศและชื่อ/อีโมจิ
        second_part = parts[1]
        # ตรวจสอบว่าเป็นอีโมจิหรือชื่อ
        if len(second_part) <= 2 or any(ord(c) > 127 for c in second_part[:2]):
            # น่าจะเป็นอีโมจิ
            emoji = second_part
            name = None
        else:
            # น่าจะเป็นชื่อประเทศ
            emoji = None
            name = second_part
    else:
        # มีทั้งรหัสประเทศ, อีโมจิ, และชื่อ
        emoji = parts[1]
        name = parts[2]
    
    # เก็บข้อมูลเดิมไว้แสดงการเปลี่ยนแปลง
    old_name = COUNTRY_NAMES.get(country_code, "ไม่พบชื่อเดิม")
    old_emoji = COUNTRY_EMOJIS.get(country_code, "❓")
    
    # ลองแก้ไขประเทศ
    success = edit_country(country_code, name, emoji)
    
    if success:
        embed = discord.Embed(title="🌏 ผลการแก้ไขประเทศ", color=discord.Color.green())
        
        changes = []
        if emoji:
            changes.append(f"อีโมจิ: {old_emoji} → {emoji}")
        if name:
            changes.append(f"ชื่อ: {old_name} → {name}")
            
        embed.add_field(
            name=f"✅ แก้ไขประเทศ {country_code} สำเร็จ",
            value="\n".join(changes),
            inline=False
        )
        
        # แสดงรายการประเทศทั้งหมดในปัจจุบัน
        country_list = "\n".join([f"- {code}: {COUNTRY_EMOJIS.get(code, '❓')} {COUNTRY_NAMES[code]}" for code in COUNTRIES])
        embed.add_field(
            name="รายการประเทศปัจจุบัน",
            value=country_list,
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"❌ ไม่พบประเทศที่มีรหัส `{country_code}`")

# Command to view or change QR code
@bot.command(name="qrcode")
async def qrcode_command(ctx, url: str = None):
    """Command to change or view the QR code URL (Admin only)"""
    # Check if user is admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมินเท่านั้น")
        return
    
    if url is None:
        # Show current QR code
        current_url = await load_qrcode_url_async_local()
        embed = discord.Embed(
            title="📲 QR Code ปัจจุบัน",
            description="QR Code ที่ใช้อยู่ในปัจจุบัน",
            color=0x4f0099
        )
        embed.set_image(url=current_url)
        embed.add_field(name="URL", value=f"`{current_url}`", inline=False)
        embed.add_field(
            name="วิธีเปลี่ยน QR Code", 
            value="ใช้คำสั่ง `!qrcode [URL]` โดยแทนที่ [URL] ด้วยลิงก์รูปภาพ QR Code ใหม่", 
            inline=False
        )
        await ctx.send(embed=embed)
    else:
        # Update QR code URL
        old_url = await load_qrcode_url_async_local()
        # ใช้ฟังก์ชัน async สำหรับบันทึกลง MongoDB
        await save_qrcode_to_mongodb(url)
        
        embed = discord.Embed(
            title="✅ เปลี่ยน QR Code สำเร็จ",
            description="QR Code ถูกอัพเดทเรียบร้อยแล้ว",
            color=0x00ff00
        )
        embed.add_field(name="URL เดิม", value=f"`{old_url}`", inline=False)
        embed.add_field(name="URL ใหม่", value=f"`{url}`", inline=False)
        embed.set_image(url=url)
        await ctx.send(embed=embed)

# Slash command to add 'ไม่มีสินค้า' placeholders to empty categories
@bot.tree.command(name="ไม่มีสินค้า", description="เพิ่มรายการ 'ไม่มีสินค้า' ในหมวดหมู่ที่ว่างเปล่าทั้งหมด (Admin only)")
async def add_no_product_placeholders_slash(interaction: discord.Interaction):
    """Slash command to add 'ไม่มีสินค้า' placeholders to empty categories in all countries (Admin only)"""
    # Check if user has Administrator permissions
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ คุณไม่มีสิทธิ์ใช้คำสั่งนี้ ต้องการสิทธิ์ผู้ดูแล (Administrator)", ephemeral=True)
        return
        
    try:
        # เพิ่มสินค้า placeholder ในหมวดหมู่ที่ว่างเปล่า
        added_count = add_no_product_placeholders()
        
        if added_count > 0:
            await interaction.response.send_message(f"✅ เพิ่มสินค้า 'ไม่มีสินค้า' ในหมวดที่ว่างเปล่าแล้ว {added_count} หมวด")
        else:
            await interaction.response.send_message("ℹ️ ไม่มีหมวดที่ว่างเปล่า ทุกหมวดมีสินค้าอยู่แล้ว")
            
    except Exception as e:
        await interaction.response.send_message(f"❌ เกิดข้อผิดพลาด: {str(e)}", ephemeral=True)

# Slash command to view or change QR code
@bot.tree.command(name="qrcode", description="เปลี่ยน QR Code (เฉพาะแอดมิน)")
async def qrcode_slash(interaction: discord.Interaction, url: str = None):
    """Slash command to change or view the QR code URL (Admin only)"""
    # Check if user is admin
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมินเท่านั้น", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=False)
    
    if url is None:
        # Show current QR code
        current_url = await load_qrcode_url_async_local()
        embed = discord.Embed(
            title="📲 QR Code ปัจจุบัน",
            description="QR Code ที่ใช้อยู่ในปัจจุบัน",
            color=0x4f0099
        )
        embed.set_image(url=current_url)
        embed.add_field(name="URL", value=f"`{current_url}`", inline=False)
        embed.add_field(
            name="วิธีเปลี่ยน QR Code", 
            value="ใช้คำสั่ง `/qrcode url:[URL]` โดยแทนที่ [URL] ด้วยลิงก์รูปภาพ QR Code ใหม่", 
            inline=False
        )
        await interaction.followup.send(embed=embed)
    else:
        # Update QR code URL
        old_url = await load_qrcode_url_async_local()
        # ใช้ฟังก์ชัน async สำหรับบันทึกลง MongoDB
        await save_qrcode_to_mongodb(url)
        
        embed = discord.Embed(
            title="✅ เปลี่ยน QR Code สำเร็จ",
            description="QR Code ถูกอัพเดทเรียบร้อยแล้ว",
            color=0x00ff00
        )
        embed.add_field(name="URL เดิม", value=f"`{old_url}`", inline=False)
        embed.add_field(name="URL ใหม่", value=f"`{url}`", inline=False)
        embed.set_image(url=url)
        await interaction.followup.send(embed=embed)

# Command to view or change thank you message
@bot.command(name="ty", aliases=["ขอบคุณ"])
async def ty_command(ctx, *, ข้อความ: str = None):
    """Command to change or view the thank you message (Admin only)"""
    # Check if user is admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมินเท่านั้น")
        return
    
    if ข้อความ is None:
        # Show current thank you message
        current_message = load_thank_you_message()
        embed = discord.Embed(
            title="💌 ข้อความขอบคุณปัจจุบัน",
            description=f"{current_message}",
            color=0x4f0099
        )
        embed.add_field(
            name="วิธีเปลี่ยนข้อความขอบคุณ", 
            value="ใช้คำสั่ง `!ขอบคุณ [ข้อความ]` โดยแทนที่ [ข้อความ] ด้วยข้อความขอบคุณใหม่", 
            inline=False
        )
        await ctx.send(embed=embed)
    else:
        # Update thank you message
        old_message = load_thank_you_message()
        save_thank_you_message(ข้อความ)
        
        embed = discord.Embed(
            title="✅ เปลี่ยนข้อความขอบคุณสำเร็จ",
            color=0x00ff00
        )
        embed.add_field(name="ข้อความเดิม", value=f"{old_message}", inline=False)
        embed.add_field(name="ข้อความใหม่", value=f"{ข้อความ}", inline=False)
        await ctx.send(embed=embed)

# Slash command to view or change thank you message
@bot.tree.command(name="ty", description="เปลี่ยนข้อความขอบคุณ (เฉพาะแอดมิน)")
@discord.app_commands.describe(ข้อความ="ข้อความขอบคุณใหม่")
async def ty_slash(interaction: discord.Interaction, ข้อความ: str = None):
    """Slash command to change or view the thank you message (Admin only)"""
    # Check if user is admin
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมินเท่านั้น", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=False)
    
    if ข้อความ is None:
        # Show current thank you message
        current_message = load_thank_you_message()
        embed = discord.Embed(
            title="💌 ข้อความขอบคุณปัจจุบัน",
            description=f"{current_message}",
            color=0x4f0099
        )
        embed.add_field(
            name="วิธีเปลี่ยนข้อความขอบคุณ", 
            value="ใช้คำสั่ง `/ty ข้อความ:[ข้อความ]` โดยแทนที่ [ข้อความ] ด้วยข้อความขอบคุณใหม่", 
            inline=False
        )
        await interaction.followup.send(embed=embed)
    else:
        # Update thank you message
        old_message = load_thank_you_message()
        save_thank_you_message(ข้อความ)
        
        embed = discord.Embed(
            title="✅ เปลี่ยนข้อความขอบคุณสำเร็จ",
            color=0x00ff00
        )
        embed.add_field(name="ข้อความเดิม", value=f"{old_message}", inline=False)
        embed.add_field(name="ข้อความใหม่", value=f"{ข้อความ}", inline=False)
        await interaction.followup.send(embed=embed)

# ======================================
# คำสั่งจัดการข้อมูล MongoDB
# ======================================

@bot.command(name="upload", aliases=["อัพโหลด", "อัพ"])
async def upload_command(ctx):
    """อัพโหลดข้อมูลทั้งหมดไปยัง MongoDB"""
    # ตรวจสอบว่าผู้ใช้มีสิทธิ์เป็นแอดมิน
    try:
        # วิธีที่ 1: ตรวจสอบด้วย guild_permissions
        if hasattr(ctx.author, 'guild_permissions') and not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมินเท่านั้น")
            return
        
        # วิธีที่ 2: ตรวจสอบตาม ID ของผู้ใช้ที่เป็นแอดมิน
        # กำหนด ID ของแอดมินตรงนี้ (เช่น ID ของคุณเอง)
        admin_ids = [
            347708619132895233,  # ID ของคุณ (เจ้าของบอท)
            # ใส่รายการ ID ของแอดมินที่นี่ เช่น
            # 123456789012345678,
            # 987654321098765432,
        ]
        
        # ถ้ามีการกำหนด admin_ids และผู้ใช้ไม่อยู่ในรายการ
        if admin_ids and ctx.author.id not in admin_ids:
            await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมินเท่านั้น")
            return
    except Exception as e:
        print(f"ข้อผิดพลาดในการตรวจสอบสิทธิ์: {str(e)}")
        # ไม่ส่งข้อความเตือนไปที่ Discord เพื่อป้องกันการสปามมากเกินไป
    
    # แสดงข้อความว่ากำลังอัพโหลด
    processing_message = await ctx.send("⏳ กำลังอัพโหลดข้อมูลไปยัง MongoDB...")
    
    try:
        from db_operations import (save_products_to_mongodb, save_countries_to_mongodb, 
                                  save_categories_to_mongodb, save_qrcode_to_mongodb,
                                  save_thank_you_message_to_mongodb)
        from mongodb_config import client
        
        # ตรวจสอบการเชื่อมต่อ MongoDB
        if client is None:
            await processing_message.edit(content="❌ ไม่สามารถเชื่อมต่อกับ MongoDB ได้")
            return
        
        # 1. อัพโหลดข้อมูลประเทศ
        countries_status = "✅"
        try:
            countries_data = {
                "countries": COUNTRIES,
                "country_names": COUNTRY_NAMES,
                "country_emojis": COUNTRY_EMOJIS,
                "country_codes": COUNTRY_CODES
            }
            await save_countries_to_mongodb(countries_data)
        except Exception as e:
            countries_status = f"❌ ({str(e)[:30]}...)"
        
        # 2. อัพโหลดข้อมูลหมวดหมู่
        categories_status = "✅"
        try:
            categories_data = {
                "category_names": CATEGORY_NAMES,
                "category_emojis": CATEGORY_EMOJIS
            }
            await save_categories_to_mongodb(categories_data)
        except Exception as e:
            categories_status = f"❌ ({str(e)[:30]}...)"
        
        # 3. อัพโหลดข้อมูลสินค้า
        products_status = "✅"
        products_count = 0
        try:
            # โหลดข้อมูลจากโฟลเดอร์ categories
            all_products = []
            categories_dir = SCRIPT_DIR / "categories"
            
            if categories_dir.exists():
                for country_dir in sorted(categories_dir.iterdir()):
                    if country_dir.is_dir():
                        country_code = country_dir.name
                        for category_file in sorted(country_dir.iterdir()):
                            if category_file.is_file() and category_file.suffix == '.json':
                                category_code = category_file.stem
                                with open(category_file, "r", encoding="utf-8") as f:
                                    category_products = json.load(f)
                                    for product in category_products:
                                        if isinstance(product, dict) and "name" in product:
                                            product["country"] = country_code
                                            product["category"] = category_code
                                            all_products.append(product)
            
            products_count = len(all_products)
            if products_count > 0:
                await save_products_to_mongodb(all_products)
            else:
                products_status = "⚠️ (ไม่พบข้อมูลสินค้า)"
        except Exception as e:
            products_status = f"❌ ({str(e)[:30]}...)"
        
        # 4. อัพโหลด QR Code URL
        qrcode_status = "✅"
        try:
            qr_code_url = ""
            try:
                with open(QRCODE_CONFIG_FILE, "r", encoding="utf-8") as f:
                    qr_code_url = json.load(f).get("url", "")
            except:
                pass
            
            if qr_code_url:
                await save_qrcode_to_mongodb(qr_code_url)
            else:
                qrcode_status = "⚠️ (ไม่พบข้อมูล QR Code)"
        except Exception as e:
            qrcode_status = f"❌ ({str(e)[:30]}...)"
        
        # 5. อัพโหลดข้อความขอบคุณ
        thank_you_status = "✅"
        try:
            thank_you_message = load_thank_you_message()
            if thank_you_message:
                await save_thank_you_message_to_mongodb(thank_you_message)
            else:
                thank_you_status = "⚠️ (ไม่พบข้อความขอบคุณ)"
        except Exception as e:
            thank_you_status = f"❌ ({str(e)[:30]}...)"
        
        # สร้าง embed สำหรับแสดงสถานะ
        embed = discord.Embed(
            title="🔄 อัพโหลดข้อมูลไปยัง MongoDB",
            description="สถานะการอัพโหลดข้อมูลไปยังฐานข้อมูล MongoDB",
            color=discord.Color.green()
        )
        
        embed.add_field(name="📊 ข้อมูลประเทศ", value=countries_status, inline=True)
        embed.add_field(name="📂 ข้อมูลหมวดหมู่", value=categories_status, inline=True)
        embed.add_field(name="🛒 ข้อมูลสินค้า", value=f"{products_status} ({products_count} รายการ)", inline=True)
        embed.add_field(name="💵 QR Code", value=qrcode_status, inline=True)
        embed.add_field(name="💬 ข้อความขอบคุณ", value=thank_you_status, inline=True)
        
        embed.set_footer(text=f"อัพโหลดเมื่อ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        await processing_message.edit(content=None, embed=embed)
        
    except Exception as e:
        await processing_message.edit(content=f"❌ เกิดข้อผิดพลาดในการอัพโหลดข้อมูล: {str(e)[:100]}...")

@bot.command(name="download", aliases=["ดาวน์โหลด", "โหลด"])
async def download_command(ctx):
    """ดาวน์โหลดข้อมูลจาก MongoDB มาใช้ในไฟล์ JSON"""
    # ตรวจสอบว่าผู้ใช้มีสิทธิ์เป็นแอดมิน
    try:
        # วิธีที่ 1: ตรวจสอบด้วย guild_permissions
        if hasattr(ctx.author, 'guild_permissions') and not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมินเท่านั้น")
            return
        
        # วิธีที่ 2: ตรวจสอบตาม ID ของผู้ใช้ที่เป็นแอดมิน
        # กำหนด ID ของแอดมินตรงนี้ (เช่น ID ของคุณเอง)
        admin_ids = [
            347708619132895233,  # ID ของคุณ (เจ้าของบอท)
            # ใส่รายการ ID ของแอดมินที่นี่ เช่น
            # 123456789012345678,
            # 987654321098765432,
        ]
        
        # ถ้ามีการกำหนด admin_ids และผู้ใช้ไม่อยู่ในรายการ
        if admin_ids and ctx.author.id not in admin_ids:
            await ctx.send("❌ คำสั่งนี้ใช้ได้เฉพาะแอดมินเท่านั้น")
            return
    except Exception as e:
        print(f"ข้อผิดพลาดในการตรวจสอบสิทธิ์: {str(e)}")
        # ไม่ส่งข้อความเตือนไปที่ Discord เพื่อป้องกันการสปามมากเกินไป
    
    # แสดงข้อความว่ากำลังดาวน์โหลด
    processing_message = await ctx.send("⏳ กำลังดาวน์โหลดข้อมูลจาก MongoDB...")
    
    try:
        from db_operations import (load_products_async, load_countries, load_categories,
                                 load_qrcode_url_async, load_thank_you_message_async)
        from mongodb_config import client
        
        # ตรวจสอบการเชื่อมต่อ MongoDB
        if client is None:
            await processing_message.edit(content="❌ ไม่สามารถเชื่อมต่อกับ MongoDB ได้")
            return
        
        # 1. ดาวน์โหลดข้อมูลประเทศ
        countries_status = "✅"
        try:
            countries_data = await load_countries()
            if countries_data:
                # อัพเดตตัวแปรโกลบอล
                global COUNTRIES, COUNTRY_NAMES, COUNTRY_EMOJIS, COUNTRY_CODES
                if "countries" in countries_data:
                    COUNTRIES = countries_data["countries"]
                if "country_names" in countries_data:
                    COUNTRY_NAMES = countries_data["country_names"]
                if "country_emojis" in countries_data:
                    COUNTRY_EMOJIS = countries_data["country_emojis"]
                if "country_codes" in countries_data:
                    COUNTRY_CODES = countries_data["country_codes"]
                
                # บันทึกลงไฟล์
                with open(COUNTRIES_FILE, "w", encoding="utf-8") as f:
                    json.dump(countries_data, f, ensure_ascii=False, indent=2)
            else:
                countries_status = "⚠️ (ไม่พบข้อมูล)"
        except Exception as e:
            countries_status = f"❌ ({str(e)[:30]}...)"
        
        # 2. ดาวน์โหลดข้อมูลหมวดหมู่
        categories_status = "✅"
        try:
            categories_data = await load_categories()
            if categories_data:
                # อัพเดตตัวแปรโกลบอล
                global CATEGORY_NAMES, CATEGORY_EMOJIS
                if "category_names" in categories_data:
                    CATEGORY_NAMES = categories_data["category_names"]
                if "category_emojis" in categories_data:
                    CATEGORY_EMOJIS = categories_data["category_emojis"]
                
                # บันทึกลงไฟล์
                with open(SCRIPT_DIR / "categories_config.json", "w", encoding="utf-8") as f:
                    json.dump(categories_data, f, ensure_ascii=False, indent=2)
            else:
                categories_status = "⚠️ (ไม่พบข้อมูล)"
        except Exception as e:
            categories_status = f"❌ ({str(e)[:30]}...)"
        
        # 3. ดาวน์โหลดข้อมูลสินค้า
        products_status = "✅"
        products_count = 0
        try:
            all_products = await load_products_async()
            if all_products:
                products_count = len(all_products)
                
                # บันทึกลงในไฟล์ products.json
                with open(PRODUCTS_FILE, "w", encoding="utf-8") as f:
                    json.dump(all_products, f, ensure_ascii=False, indent=2)
                
                # บันทึกลงในโฟลเดอร์ categories แยกตามหมวดหมู่และประเทศ
                # สร้างโครงสร้างข้อมูลสำหรับแยกสินค้าตามประเทศและหมวดหมู่
                categorized_products = {}
                
                for product in all_products:
                    country = product.get("country", "1")
                    category = product.get("category", "money")
                    
                    if country not in categorized_products:
                        categorized_products[country] = {}
                    
                    if category not in categorized_products[country]:
                        categorized_products[country][category] = []
                    
                    # สร้างสำเนาของสินค้าที่ไม่มี country และ category
                    product_copy = product.copy()
                    if "country" in product_copy:
                        del product_copy["country"]
                    if "category" in product_copy:
                        del product_copy["category"]
                    if "_id" in product_copy:
                        del product_copy["_id"]
                    
                    categorized_products[country][category].append(product_copy)
                
                # บันทึกไฟล์แยกตามประเทศและหมวดหมู่
                categories_dir = SCRIPT_DIR / "categories"
                for country, categories in categorized_products.items():
                    country_dir = categories_dir / country
                    country_dir.mkdir(parents=True, exist_ok=True)
                    
                    for category, products in categories.items():
                        category_file = country_dir / f"{category}.json"
                        with open(category_file, "w", encoding="utf-8") as f:
                            json.dump(products, f, ensure_ascii=False, indent=2)
            else:
                products_status = "⚠️ (ไม่พบข้อมูล)"
        except Exception as e:
            products_status = f"❌ ({str(e)[:30]}...)"
        
        # 4. ดาวน์โหลด QR Code URL
        qrcode_status = "✅"
        try:
            qrcode_url = await load_qrcode_url_async_local()
            if qrcode_url:
                with open(QRCODE_CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump({"url": qrcode_url}, f, ensure_ascii=False, indent=2)
            else:
                qrcode_status = "⚠️ (ไม่พบข้อมูล)"
        except Exception as e:
            qrcode_status = f"❌ ({str(e)[:30]}...)"
        
        # 5. ดาวน์โหลดข้อความขอบคุณ
        thank_you_status = "✅"
        try:
            thank_you_message = await load_thank_you_message_async()
            if thank_you_message:
                with open(SCRIPT_DIR / "thank_you_config.json", "w", encoding="utf-8") as f:
                    json.dump({"message": thank_you_message}, f, ensure_ascii=False, indent=2)
            else:
                thank_you_status = "⚠️ (ไม่พบข้อมูล)"
        except Exception as e:
            thank_you_status = f"❌ ({str(e)[:30]}...)"
        
        # สร้าง embed สำหรับแสดงสถานะ
        embed = discord.Embed(
            title="🔄 ดาวน์โหลดข้อมูลจาก MongoDB",
            description="สถานะการดาวน์โหลดข้อมูลจากฐานข้อมูล MongoDB",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="📊 ข้อมูลประเทศ", value=countries_status, inline=True)
        embed.add_field(name="📂 ข้อมูลหมวดหมู่", value=categories_status, inline=True)
        embed.add_field(name="🛒 ข้อมูลสินค้า", value=f"{products_status} ({products_count} รายการ)", inline=True)
        embed.add_field(name="💵 QR Code", value=qrcode_status, inline=True)
        embed.add_field(name="💬 ข้อความขอบคุณ", value=thank_you_status, inline=True)
        
        embed.set_footer(text=f"ดาวน์โหลดเมื่อ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        await processing_message.edit(content=None, embed=embed)
        
    except Exception as e:
        await processing_message.edit(content=f"❌ เกิดข้อผิดพลาดในการดาวน์โหลดข้อมูล: {str(e)[:100]}...")

# Run the bot with simple restart logic
if __name__ == "__main__":
    # เริ่มเว็บเซิร์ฟเวอร์ในเธรดแยกสำหรับ Render.com
    start_server_in_thread()
    
    import time
    import random
    
    try:
        # ตรวจสอบ Token ก่อน
        if not TOKEN or TOKEN == "YOUR_BOT_TOKEN":
            print("❌ Discord Token ไม่ถูกต้อง!")
            print("💡 กรุณาตั้งค่า DISCORD_TOKEN ใน Environment Variables")
            exit(1)
        
        print(f"🔑 Token detected: {TOKEN[:20]}...")
        
        # ตรวจสอบว่าเป็น Render environment หรือไม่
        is_render = os.environ.get("RENDER") is not None
        
        if is_render:
            # สำหรับ Render.com: เพิ่มเวลารอมากขึ้นเพื่อหลีกเลี่ยง Cloudflare Rate Limit
            delay = random.uniform(30, 60)  # เพิ่มเวลารอเป็น 30-60 วินาที
            print(f"⏳ Production mode - รอ {delay:.1f} วินาที เพื่อหลีกเลี่ยง Cloudflare Rate Limiting...")
            time.sleep(delay)
            
            # เริ่มการทำงานของบอทโดยไม่ auto-reconnect
            bot.run(TOKEN, reconnect=False)
        else:
            # สำหรับ development environment
            delay = random.uniform(5, 10)
            print(f"⏳ Development mode - รอ {delay:.1f} วินาที เพื่อหลีกเลี่ยง Rate Limiting...")
            time.sleep(delay)
            
            # เริ่มการทำงานของบอทแบบปกติ
            bot.run(TOKEN, reconnect=True)
        
    except discord.LoginFailure:
        print("❌ ไม่สามารถเข้าสู่ระบบได้ - Token ไม่ถูกต้อง")
        print("💡 กรุณาตรวจสอบ DISCORD_TOKEN ใน Environment Variables")
    except discord.HTTPException as e:
        if e.status == 401:
            print("❌ Discord Token ไม่ถูกต้องหรือหมดอายุ!")
            print("💡 กรุณาสร้าง Token ใหม่ใน Discord Developer Portal")
            if is_render:
                time.sleep(60)  # รอ 1 นาที ก่อน exit เพื่อให้ Render ไม่ restart บ่อย
        elif e.status == 429:
            print("⚠️ Rate Limited - รอการ restart อัตโนมัติ")
            if is_render:
                # สำหรับ Render: รอนานขึ้นเพื่อลด Cloudflare Rate Limit
                print("🔄 Production: ตรวจพบ Cloudflare Rate Limit - รอ 10 นาที ก่อน restart...")
                time.sleep(600)  # รอ 10 นาที
            else:
                time.sleep(60)  # Development: รอ 1 นาที
        else:
            print(f"❌ HTTP Error {e.status}: {e}")
            if is_render:
                time.sleep(30)  # รอสักครู่ก่อน exit
    except KeyboardInterrupt:
        print("👋 บอทถูกปิดโดยผู้ใช้")
    except Exception as e:
        print(f"❌ บอทหยุดทำงานเนื่องจาก: {e}")
        print("💡 แนะนำ: ตรวจสอบ Discord Token หรือการเชื่อมต่ออินเทอร์เน็ต")
        if is_render:
            time.sleep(60)  # รอ 1 นาที ก่อน exit
