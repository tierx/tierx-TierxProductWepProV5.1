import json
import os
from datetime import datetime
import os.path
from pathlib import Path

# ไฟล์จัดเก็บข้อมูล
SCRIPT_DIR = Path(__file__).parent.absolute()
COUNTRIES_FILE = SCRIPT_DIR / "countries.json"
PRODUCTS_FILE = SCRIPT_DIR / "products.json"
HISTORY_FILE = SCRIPT_DIR / "history.json"
QRCODE_CONFIG_FILE = SCRIPT_DIR / "qrcode_config.json"
THANK_YOU_CONFIG_FILE = SCRIPT_DIR / "thank_you_config.json"

# นำเข้า MongoDB collections ถ้าเป็นไปได้
try:
    from mongodb_config import (
        products_collection,
        countries_collection, 
        history_collection,
        configs_collection
    )
    MONGODB_AVAILABLE = True
    print("✅ พร้อมใช้งาน MongoDB สำหรับจัดเก็บข้อมูล")
except (ImportError, AttributeError):
    # หากไม่สามารถนำเข้าได้ หรือมีค่าเป็น None
    products_collection = None
    countries_collection = None
    history_collection = None
    configs_collection = None
    MONGODB_AVAILABLE = False
    print("⚠️ ไม่สามารถเชื่อมต่อกับ MongoDB - จะใช้ไฟล์ JSON ท้องถิ่นแทน")

# ================================
# ฟังก์ชันจัดการข้อมูลประเทศ
# ================================

async def load_countries():
    """โหลดข้อมูลประเทศจาก MongoDB หรือไฟล์ JSON"""
    
    # พยายามโหลดจาก MongoDB ก่อน
    if MONGODB_AVAILABLE and countries_collection is not None:
        try:
            country_data = countries_collection.find_one({})
            if country_data:
                # ส่งคืนเป็นข้อมูลทั้งหมดเพื่อให้สามารถเขียนลงไฟล์ได้ง่าย
                if "_id" in country_data:
                    del country_data["_id"]  # ลบ _id ออกเพื่อให้เก็บลงไฟล์ได้ง่าย
                return country_data
        except Exception as e:
            print(f"ไม่สามารถโหลดข้อมูลประเทศจาก MongoDB: {str(e)}")
            
    # สำหรับคำสั่ง load_countries อื่นๆ ที่ส่งคืนแบบเดิม
    return load_countries_tuple()

def load_countries_tuple():
    """โหลดข้อมูลประเทศในรูปแบบ tuple สำหรับใช้ในโค้ดเดิม"""
    
    # พยายามโหลดจาก MongoDB ก่อน
    if MONGODB_AVAILABLE and countries_collection is not None:
        try:
            country_data = countries_collection.find_one({})
            if country_data:
                return country_data.get("countries", []), country_data.get("country_names", {}), country_data.get("country_emojis", {}), country_data.get("country_codes", {})
        except Exception as e:
            print(f"ไม่สามารถโหลดข้อมูลประเทศจาก MongoDB: {str(e)}")
    
    # โหลดจากไฟล์ JSON
    try:
        with open(COUNTRIES_FILE, 'r', encoding='utf-8') as f:
            country_data = json.load(f)
            return country_data.get("countries", []), country_data.get("country_names", {}), country_data.get("country_emojis", {}), country_data.get("country_codes", {})
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ไม่สามารถโหลดข้อมูลประเทศจากไฟล์: {str(e)}")
        
    # ค่าเริ่มต้นถ้าไม่สามารถโหลดข้อมูลได้จากทั้งสองแหล่ง
    return [], {}, {}, {}

def save_countries(countries, country_names, country_emojis, country_codes):
    """บันทึกข้อมูลประเทศลง MongoDB และไฟล์ JSON"""
    country_data = {
        "countries": countries,
        "country_names": country_names,
        "country_emojis": country_emojis,
        "country_codes": country_codes
    }
    
    # บันทึกลงไฟล์ JSON ทุกครั้ง เพื่อให้มีข้อมูลสำรอง
    try:
        with open(COUNTRIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(country_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"ไม่สามารถบันทึกข้อมูลประเทศลงไฟล์: {str(e)}")
    
    # บันทึกลง MongoDB ถ้าเชื่อมต่อได้
    if MONGODB_AVAILABLE and countries_collection is not None:
        try:
            # ตรวจสอบว่ามีข้อมูลอยู่แล้วหรือไม่
            existing_data = countries_collection.find_one({})
            if existing_data:
                countries_collection.replace_one({"_id": existing_data["_id"]}, country_data)
            else:
                countries_collection.insert_one(country_data)
        except Exception as e:
            print(f"ไม่สามารถบันทึกข้อมูลประเทศลง MongoDB: {str(e)}")

async def save_countries_to_mongodb(country_data):
    """บันทึกข้อมูลประเทศ (dict) ลง MongoDB

    Args:
        country_data (dict): ข้อมูลประเทศที่ต้องการบันทึก
            ต้องมีคีย์ "countries", "country_names", "country_emojis", "country_codes"
            
    Returns:
        bool: True ถ้าสำเร็จ
    """
    if not MONGODB_AVAILABLE or countries_collection is None:
        print("ไม่สามารถเชื่อมต่อกับ MongoDB ได้ (save_countries_to_mongodb)")
        return False
    
    try:
        # สร้างสำเนาข้อมูลเพื่อไม่ให้เปลี่ยนแปลงข้อมูลต้นฉบับ
        country_data = country_data.copy()
        
        # ตรวจสอบว่ามีข้อมูลอยู่แล้วหรือไม่
        existing_data = countries_collection.find_one({})
        if existing_data:
            countries_collection.replace_one({"_id": existing_data["_id"]}, country_data)
        else:
            countries_collection.insert_one(country_data)
        return True
    except Exception as e:
        print(f"ไม่สามารถบันทึกข้อมูลประเทศลง MongoDB: {str(e)}")
        return False

def add_country(code, name, emoji=""):
    """เพิ่มประเทศใหม่
    
    Args:
        code (str): รหัสประเทศ (เช่น 'korea', 'china')
        name (str): ชื่อประเทศเป็นภาษาไทย (เช่น 'เกาหลี', 'จีน')
        emoji (str, optional): อีโมจิประเทศ
        
    Returns:
        bool or tuple: True ถ้าสำเร็จ, หรือ (False, error_message) ถ้าล้มเหลวพร้อมข้อความผิดพลาด
    """
    # โหลดข้อมูลประเทศปัจจุบัน
    countries, country_names, country_emojis, country_codes = load_countries()
    
    # ตรวจสอบว่ามีประเทศนี้แล้วหรือไม่
    if code in countries or code in country_codes.values():
        return (False, f"มีประเทศรหัส {code} อยู่แล้ว")
    
    # เพิ่มประเทศใหม่
    countries.append(code)
    country_names[code] = name
    if emoji:
        country_emojis[code] = emoji
    
    # บันทึกข้อมูล
    save_countries(countries, country_names, country_emojis, country_codes)
    return True

def edit_country(code, new_name=None, new_emoji=None):
    """แก้ไขข้อมูลประเทศ
    
    Args:
        code (str): รหัสประเทศที่ต้องการแก้ไข
        new_name (str, optional): ชื่อใหม่สำหรับประเทศ
        new_emoji (str, optional): อีโมจิใหม่สำหรับประเทศ
        
    Returns:
        bool: True ถ้าสำเร็จ, False ถ้าไม่พบประเทศ
    """
    # โหลดข้อมูลประเทศปัจจุบัน
    countries, country_names, country_emojis, country_codes = load_countries()
    
    # ตรวจสอบว่ามีประเทศนี้หรือไม่
    if code not in countries and code not in country_names:
        return False
    
    # แก้ไขข้อมูล
    if new_name:
        country_names[code] = new_name
    if new_emoji:
        country_emojis[code] = new_emoji
    
    # บันทึกข้อมูล
    save_countries(countries, country_names, country_emojis, country_codes)
    return True

def remove_country(code):
    """ลบประเทศและสินค้าทั้งหมดในประเทศนั้น
    
    Args:
        code (str): รหัสประเทศที่ต้องการลบ
        
    Returns:
        bool or tuple: True ถ้าสำเร็จ, หรือ (False, error_message) ถ้าล้มเหลวพร้อมข้อความผิดพลาด
    """
    # โหลดข้อมูลประเทศปัจจุบัน
    countries, country_names, country_emojis, country_codes = load_countries()
    
    # ตรวจสอบว่ามีประเทศนี้หรือไม่
    if code not in countries and code not in country_names:
        return (False, f"ไม่พบประเทศรหัส {code}")
    
    # ลบประเทศออกจากรายการ
    if code in countries:
        countries.remove(code)
    if code in country_names:
        del country_names[code]
    if code in country_emojis:
        del country_emojis[code]
    
    # ลบรหัสประเทศเก่า (ถ้ามี)
    for k, v in list(country_codes.items()):
        if v == code:
            del country_codes[k]
    
    # บันทึกข้อมูลประเทศ
    save_countries(countries, country_names, country_emojis, country_codes)
    
    # ลบสินค้าทั้งหมดในประเทศนี้
    products_collection.delete_many({"country": code})
    
    return True

# ================================
# ฟังก์ชันจัดการข้อมูลสินค้า
# ================================

def load_products(country=None, category=None):
    """โหลดข้อมูลสินค้าจาก MongoDB ตามประเทศและหมวดหมู่
    
    Args:
        country (str, optional): รหัสประเทศ (1, 2, 3, 4, 5) หรือรหัสเก่า (thailand, japan, usa). Default: None.
        category (str, optional): รหัสหมวดหมู่ (money, weapon, item, etc). Default: None.
        
    Returns:
        list: รายการสินค้าที่ตรงกับเงื่อนไข
    """
    query = {}
    
    # กรองตามประเทศ (ถ้าระบุ)
    if country:
        query["country"] = country
    
    # กรองตามหมวดหมู่ (ถ้าระบุ)
    if category:
        query["category"] = category
    
    # ตรวจสอบการเชื่อมต่อกับ MongoDB
    if not MONGODB_AVAILABLE or products_collection is None:
        # ถ้าไม่สามารถเชื่อมต่อ MongoDB ได้ โหลดจากไฟล์ products.json
        try:
            with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                all_products = json.load(f)
                
                # กรองตามเงื่อนไข
                filtered_products = []
                for product in all_products:
                    if country and product.get("country") != country:
                        continue
                    if category and product.get("category") != category:
                        continue
                    filtered_products.append(product)
                
                return filtered_products
        except (FileNotFoundError, json.JSONDecodeError):
            # ถ้าไม่มีไฟล์ products.json หรืออ่านไม่ได้ ส่งคืนรายการว่าง
            return []
    
    try:
        # ดึงข้อมูลจาก MongoDB
        products = list(products_collection.find(query))
        
        # แปลง _id เป็น str เพื่อให้สามารถแปลงเป็น JSON ได้
        for product in products:
            if "_id" in product:
                product["_id"] = str(product["_id"])
        
        return products
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการโหลดสินค้าจาก MongoDB: {str(e)}")
        return []

async def load_products_async(country=None, category=None):
    """โหลดข้อมูลสินค้าจาก MongoDB ตามประเทศและหมวดหมู่ (async version)
    
    Args:
        country (str, optional): รหัสประเทศ (1, 2, 3, 4, 5) หรือรหัสเก่า (thailand, japan, usa). Default: None.
        category (str, optional): รหัสหมวดหมู่ (money, weapon, item, etc). Default: None.
        
    Returns:
        list: รายการสินค้าที่ตรงกับเงื่อนไข
    """
    # เรียกใช้ฟังก์ชันปกติเพราะไม่มีการทำงานแบบ async ใน MongoDB Client
    return load_products(country, category)

def save_product(product):
    """บันทึกสินค้าเดียวลง MongoDB
    
    Args:
        product: ข้อมูลสินค้าที่ต้องการบันทึก ต้องมีฟิลด์ name, price, emoji, country และ category
        
    Returns:
        bool: True ถ้าสำเร็จ
    """
    # ตรวจสอบว่าสินค้ามีข้อมูลครบถ้วน
    required_fields = ["name", "price", "emoji", "country", "category"]
    for field in required_fields:
        if field not in product:
            return False
    
    # ตรวจสอบว่ามีสินค้านี้อยู่แล้วหรือไม่
    existing_product = products_collection.find_one({
        "name": product["name"],
        "country": product["country"],
        "category": product["category"]
    })
    
    if existing_product:
        # อัปเดตสินค้าที่มีอยู่แล้ว
        product_id = existing_product["_id"]
        products_collection.replace_one({"_id": product_id}, product)
    else:
        # เพิ่มสินค้าใหม่
        products_collection.insert_one(product)
    
    return True

def batch_add_products(products_data):
    """เพิ่มสินค้าหลายรายการในครั้งเดียว
    
    Args:
        products_data: รายการข้อมูลสินค้าที่ต้องการเพิ่ม แต่ละรายการต้องมีฟิลด์ name, price, emoji, country และ category
        
    Returns:
        int: จำนวนสินค้าที่เพิ่มสำเร็จ
    """
    success_count = 0
    
    for product in products_data:
        if save_product(product):
            success_count += 1
    
    return success_count

def remove_product(name, category=None, country=None):
    """ลบสินค้า
    
    Args:
        name (str): ชื่อสินค้าที่ต้องการลบ
        category (str, optional): หมวดหมู่ของสินค้า (ถ้าระบุจะลบเฉพาะในหมวดนี้)
        country (str, optional): ประเทศของสินค้า (ถ้าระบุจะลบเฉพาะในประเทศนี้)
        
    Returns:
        bool: True ถ้าสำเร็จ, False ถ้าไม่พบสินค้า
    """
    query = {"name": name}
    
    # เพิ่มเงื่อนไขการค้นหา
    if category:
        query["category"] = category
    if country:
        query["country"] = country
    
    # ลบสินค้า
    result = products_collection.delete_many(query)
    
    return result.deleted_count > 0

def update_product(name, country, new_emoji=None, new_name=None, new_price=None, new_category=None, new_country=None):
    """อัปเดตข้อมูลสินค้า
    
    Args:
        name (str): ชื่อสินค้าที่ต้องการแก้ไข
        country (str): ประเทศของสินค้า
        new_emoji (str, optional): อีโมจิใหม่
        new_name (str, optional): ชื่อใหม่
        new_price (float, optional): ราคาใหม่
        new_category (str, optional): หมวดหมู่ใหม่
        new_country (str, optional): ประเทศใหม่
        
    Returns:
        bool: True ถ้าสำเร็จ, False ถ้าไม่พบสินค้า
    """
    # ค้นหาสินค้า
    product = products_collection.find_one({"name": name, "country": country})
    
    if not product:
        return False
    
    # สร้างข้อมูลที่จะอัปเดต
    updates = {}
    if new_emoji:
        updates["emoji"] = new_emoji
    if new_name:
        updates["name"] = new_name
    if new_price is not None:
        updates["price"] = new_price
    if new_category:
        updates["category"] = new_category
    if new_country:
        updates["country"] = new_country
    
    # ถ้าไม่มีข้อมูลที่จะอัปเดต
    if not updates:
        return True
    
    # อัปเดตสินค้า
    products_collection.update_one({"_id": product["_id"]}, {"$set": updates})
    
    return True

def clear_category_products(category, country=None):
    """ลบสินค้าทั้งหมดในหมวดหมู่
    
    Args:
        category (str): หมวดหมู่ที่ต้องการลบ
        country (str, optional): ประเทศที่ต้องการลบ (ถ้าไม่ระบุจะลบในทุกประเทศ)
        
    Returns:
        int: จำนวนสินค้าที่ลบได้
    """
    query = {"category": category}
    
    # เพิ่มเงื่อนไขประเทศ (ถ้าระบุ)
    if country:
        query["country"] = country
    
    # ลบสินค้า
    result = products_collection.delete_many(query)
    
    return result.deleted_count

def delete_all_products():
    """ลบสินค้าทั้งหมดจากทุกหมวดหมู่ในทุกประเทศ
    
    Returns:
        int: จำนวนสินค้าทั้งหมดที่ถูกลบ
    """
    result = products_collection.delete_many({})
    return result.deleted_count

def add_no_product_placeholders():
    """เพิ่มสินค้า placeholder 'ไม่มีสินค้า' ในหมวดหมู่ที่ว่างเปล่า
    
    Returns:
        int: จำนวนสินค้า placeholder ที่เพิ่ม
    """
    from shopbot import COUNTRIES, CATEGORIES
    
    placeholder_count = 0
    
    # ตรวจสอบแต่ละประเทศและหมวดหมู่
    for country in COUNTRIES:
        for category in CATEGORIES:
            # ตรวจสอบว่ามีสินค้าในหมวดหมู่นี้หรือไม่
            product_count = products_collection.count_documents({
                "country": country,
                "category": category
            })
            
            # ถ้าไม่มีสินค้า ให้เพิ่ม placeholder
            if product_count == 0:
                placeholder = {
                    "name": "ไม่มีสินค้า",
                    "price": 0,
                    "emoji": "❌",
                    "country": country,
                    "category": category
                }
                products_collection.insert_one(placeholder)
                placeholder_count += 1
    
    return placeholder_count

# ================================
# ฟังก์ชันจัดการประวัติการซื้อ
# ================================

def log_purchase(user, items, total_price):
    """บันทึกประวัติการซื้อใน MongoDB
    
    Args:
        user: ข้อมูลผู้ใช้ที่ซื้อสินค้า
        items: รายการสินค้าที่ซื้อ
        total_price: ราคารวม
        
    Returns:
        str: ID ของรายการที่บันทึก
    """
    # สร้างข้อมูลประวัติการซื้อ
    purchase_data = {
        "user_id": str(user.id),
        "user_name": str(user),
        "items": items,
        "total_price": total_price,
        "timestamp": datetime.now().isoformat()
    }
    
    # บันทึกลง MongoDB
    result = history_collection.insert_one(purchase_data)
    
    return str(result.inserted_id)

def get_purchase_history(limit=5):
    """ดึงประวัติการซื้อล่าสุด
    
    Args:
        limit (int): จำนวนรายการที่ต้องการดึง
        
    Returns:
        list: รายการประวัติการซื้อล่าสุด
    """
    # ดึงข้อมูลล่าสุดตามจำนวนที่ระบุ
    history = list(history_collection.find().sort("timestamp", -1).limit(limit))
    
    # แปลง _id เป็น str เพื่อให้สามารถแปลงเป็น JSON ได้
    for record in history:
        if "_id" in record:
            record["_id"] = str(record["_id"])
    
    return history

# ================================
# ฟังก์ชันจัดการการตั้งค่า
# ================================

def load_qrcode_url():
    """โหลด URL QR code จาก MongoDB
    
    Returns:
        str: URL ของ QR code
    """
    if MONGODB_AVAILABLE and configs_collection is not None:
        try:
            config = configs_collection.find_one({"config_type": "qrcode"})
            return config.get("url", "https://promptpay.io/1234567890") if config else "https://promptpay.io/1234567890"
        except Exception as e:
            print(f"ไม่สามารถโหลด QR Code URL จาก MongoDB: {str(e)}")
    
    # ถ้าไม่สามารถโหลดจาก MongoDB ได้ ให้โหลดจากไฟล์
    try:
        with open(QRCODE_CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get("url", "https://promptpay.io/1234567890")
    except:
        return "https://promptpay.io/1234567890"

async def load_qrcode_url_async():
    """โหลด URL QR code จาก MongoDB (async version)
    
    Returns:
        str: URL ของ QR code
    """
    try:
        # ตรวจสอบการเชื่อมต่อกับ MongoDB
        from mongodb_config import client
        
        if client is None:
            print("⚠️ ไม่สามารถเชื่อมต่อกับ MongoDB ได้ - ใช้ไฟล์ local แทน")
            return load_qrcode_url()
        
        # ค้นหา QR Code ใน MongoDB
        db = client["shopbot"]
        collection = db["qrcode"]
        result = collection.find_one({"type": "qrcode"})
        
        if result and "url" in result:
            print("✅ โหลด QR Code จาก MongoDB สำเร็จ!")
            return result["url"]
        else:
            # หากไม่พบข้อมูลใน MongoDB ให้ใช้ข้อมูลจากไฟล์ local
            local_url = load_qrcode_url()
            print(f"⚠️ ไม่พบข้อมูล QR Code ใน MongoDB - ใช้ข้อมูลจากไฟล์ local แทน: {local_url}")
            # บันทึกข้อมูลจาก local ลง MongoDB
            await save_qrcode_to_mongodb(local_url)
            return local_url
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในการโหลด QR Code จาก MongoDB: {e}")
        return load_qrcode_url()

def save_qrcode_url(url):
    """บันทึก URL QR code ลง MongoDB
    
    Args:
        url (str): URL ของ QR code
        
    Returns:
        bool: True ถ้าสำเร็จ
    """
    if not MONGODB_AVAILABLE or configs_collection is None:
        # บันทึกลงไฟล์แทนถ้าไม่มี MongoDB
        with open(QRCODE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"url": url}, f, ensure_ascii=False, indent=2)
        return True

    # ตรวจสอบว่ามีการตั้งค่าอยู่แล้วหรือไม่
    config = configs_collection.find_one({"config_type": "qrcode"})
    
    if config:
        # อัปเดตการตั้งค่าที่มีอยู่
        configs_collection.update_one(
            {"_id": config["_id"]},
            {"$set": {"url": url}}
        )
    else:
        # สร้างการตั้งค่าใหม่
        configs_collection.insert_one({
            "config_type": "qrcode",
            "url": url
        })
    
    # บันทึกลงไฟล์ด้วยเพื่อให้มีข้อมูลสำรอง
    with open(QRCODE_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump({"url": url}, f, ensure_ascii=False, indent=2)
    
    return True
    
async def save_qrcode_to_mongodb(url):
    """บันทึก URL QR code ลง MongoDB (async version)
    
    Args:
        url (str): URL ของ QR code
        
    Returns:
        bool: True ถ้าสำเร็จ
    """
    if not MONGODB_AVAILABLE or configs_collection is None:
        print("ไม่สามารถเชื่อมต่อกับ MongoDB ได้ (save_qrcode_to_mongodb)")
        return False
    
    try:
        # ตรวจสอบว่ามีการตั้งค่าอยู่แล้วหรือไม่
        config = configs_collection.find_one({"config_type": "qrcode"})
        
        if config:
            # อัปเดตการตั้งค่าที่มีอยู่
            configs_collection.update_one(
                {"_id": config["_id"]},
                {"$set": {"url": url}}
            )
        else:
            # สร้างการตั้งค่าใหม่
            configs_collection.insert_one({
                "config_type": "qrcode",
                "url": url
            })
            
        # บันทึกลงไฟล์ด้วยเพื่อให้มีข้อมูลสำรอง
        with open(QRCODE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"url": url}, f, ensure_ascii=False, indent=2)
            
        return True
    except Exception as e:
        print(f"ไม่สามารถบันทึก QR Code URL ลง MongoDB: {str(e)}")
        
        # พยายามบันทึกลงไฟล์แทน
        try:
            with open(QRCODE_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({"url": url}, f, ensure_ascii=False, indent=2)
        except Exception as file_error:
            print(f"ไม่สามารถบันทึก QR Code URL ลงไฟล์: {str(file_error)}")
            
        return False

def load_thank_you_message():
    """โหลดข้อความขอบคุณจาก MongoDB
    
    Returns:
        str: ข้อความขอบคุณ
    """
    default_message = "✅ ขอบคุณสำหรับการสั่งซื้อ! สินค้าจะถูกส่งถึงคุณเร็วๆ นี้"
    
    if MONGODB_AVAILABLE and configs_collection is not None:
        try:
            config = configs_collection.find_one({"config_type": "thank_you"})
            return config.get("message", default_message) if config else default_message
        except Exception as e:
            print(f"ไม่สามารถโหลดข้อความขอบคุณจาก MongoDB: {str(e)}")
    
    # ถ้าไม่สามารถโหลดจาก MongoDB ได้ ให้โหลดจากไฟล์
    try:
        with open(THANK_YOU_CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            return config.get("message", default_message)
    except:
        return default_message

async def load_thank_you_message_async():
    """โหลดข้อความขอบคุณจาก MongoDB (async version)
    
    Returns:
        str: ข้อความขอบคุณ
    """
    return load_thank_you_message()  # ใช้ฟังก์ชันปกติเพราะไม่มีการทำงานแบบ async ใน MongoDB Client

def save_thank_you_message(message):
    """บันทึกข้อความขอบคุณลง MongoDB
    
    Args:
        message (str): ข้อความขอบคุณ
        
    Returns:
        bool: True ถ้าสำเร็จ
    """
    if not MONGODB_AVAILABLE or configs_collection is None:
        # บันทึกลงไฟล์แทนถ้าไม่มี MongoDB
        with open(THANK_YOU_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"message": message}, f, ensure_ascii=False, indent=2)
        return True
        
    # ตรวจสอบว่ามีการตั้งค่าอยู่แล้วหรือไม่
    config = configs_collection.find_one({"config_type": "thank_you"})
    
    if config:
        # อัปเดตการตั้งค่าที่มีอยู่
        configs_collection.update_one(
            {"_id": config["_id"]},
            {"$set": {"message": message}}
        )
    else:
        # สร้างการตั้งค่าใหม่
        configs_collection.insert_one({
            "config_type": "thank_you",
            "message": message
        })
    
    # บันทึกลงไฟล์ด้วยเพื่อให้มีข้อมูลสำรอง
    with open(THANK_YOU_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump({"message": message}, f, ensure_ascii=False, indent=2)
    
    return True
    
async def save_thank_you_message_to_mongodb(message):
    """บันทึกข้อความขอบคุณลง MongoDB (async version)
    
    Args:
        message (str): ข้อความขอบคุณ
        
    Returns:
        bool: True ถ้าสำเร็จ
    """
    if not MONGODB_AVAILABLE or configs_collection is None:
        print("ไม่สามารถเชื่อมต่อกับ MongoDB ได้ (save_thank_you_message_to_mongodb)")
        return False
    
    try:
        # ตรวจสอบว่ามีการตั้งค่าอยู่แล้วหรือไม่
        config = configs_collection.find_one({"config_type": "thank_you"})
        
        if config:
            # อัปเดตการตั้งค่าที่มีอยู่
            configs_collection.update_one(
                {"_id": config["_id"]},
                {"$set": {"message": message}}
            )
        else:
            # สร้างการตั้งค่าใหม่
            configs_collection.insert_one({
                "config_type": "thank_you",
                "message": message
            })
            
        # บันทึกลงไฟล์ด้วยเพื่อให้มีข้อมูลสำรอง
        with open(THANK_YOU_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump({"message": message}, f, ensure_ascii=False, indent=2)
            
        return True
    except Exception as e:
        print(f"ไม่สามารถบันทึกข้อความขอบคุณลง MongoDB: {str(e)}")
        
        # พยายามบันทึกลงไฟล์แทน
        try:
            with open(THANK_YOU_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump({"message": message}, f, ensure_ascii=False, indent=2)
        except Exception as file_error:
            print(f"ไม่สามารถบันทึกข้อความขอบคุณลงไฟล์: {str(file_error)}")
            
        return False
    
async def load_categories():
    """โหลดข้อมูลหมวดหมู่จาก MongoDB
    
    Returns:
        dict: ข้อมูลหมวดหมู่
    """
    if MONGODB_AVAILABLE and configs_collection is not None:
        try:
            config = configs_collection.find_one({"config_type": "categories"})
            if config:
                if "_id" in config:
                    del config["_id"]
                    del config["config_type"]
                return config
        except Exception as e:
            print(f"ไม่สามารถโหลดข้อมูลหมวดหมู่จาก MongoDB: {str(e)}")
    
    # ถ้าไม่สามารถโหลดจาก MongoDB ได้ ให้โหลดจากไฟล์
    try:
        with open(SCRIPT_DIR / "categories_config.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {"category_names": {}, "category_emojis": {}}
        
async def save_categories_to_mongodb(categories_data):
    """บันทึกข้อมูลหมวดหมู่ไปยัง MongoDB
    
    Args:
        categories_data (dict): ข้อมูลหมวดหมู่
        
    Returns:
        bool: True ถ้าสำเร็จ
    """
    if not MONGODB_AVAILABLE or configs_collection is None:
        print("ไม่สามารถเชื่อมต่อกับ MongoDB ได้ (save_categories_to_mongodb)")
        return False
    
    try:
        # เพิ่มประเภทของข้อมูล
        categories_data = categories_data.copy()  # สร้างสำเนาเพื่อไม่ให้เปลี่ยนแปลงข้อมูลต้นฉบับ
        categories_data["config_type"] = "categories"
        
        # ตรวจสอบว่ามีข้อมูลอยู่แล้วหรือไม่
        existing_data = configs_collection.find_one({"config_type": "categories"})
    except Exception as e:
        print(f"ไม่สามารถอัพโหลดข้อมูลหมวดหมู่ไปยัง MongoDB: {str(e)}")
        return False
    
    if existing_data:
        # ถ้ามีข้อมูลอยู่แล้ว ให้อัปเดต
        configs_collection.replace_one({"_id": existing_data["_id"]}, categories_data)
    else:
        # ถ้ายังไม่มีข้อมูล ให้เพิ่มใหม่
        configs_collection.insert_one(categories_data)
    
    # บันทึกลงไฟล์ด้วย
    categories_data_copy = categories_data.copy()
    if "config_type" in categories_data_copy:
        del categories_data_copy["config_type"]
    with open(SCRIPT_DIR / "categories_config.json", 'w', encoding='utf-8') as f:
        json.dump(categories_data_copy, f, ensure_ascii=False, indent=2)
    
    return True
    
async def save_products_to_mongodb(products):
    """บันทึกข้อมูลสินค้าไปยัง MongoDB
    
    Args:
        products (list): รายการสินค้า
        
    Returns:
        bool: True ถ้าสำเร็จ
    """
    if not MONGODB_AVAILABLE or products_collection is None:
        raise Exception("ไม่สามารถเชื่อมต่อกับ MongoDB ได้")
    
    # ลบข้อมูลเดิมทั้งหมด
    products_collection.delete_many({})
    
    # เพิ่มข้อมูลใหม่
    for product in products:
        products_collection.insert_one(product)
    
    # บันทึกลงไฟล์ด้วย
    with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    
    return True

def load_target_channel_id():
    """โหลด Target Channel ID จาก MongoDB
    
    Returns:
        int: ID ของช่องเป้าหมาย
    """
    if not MONGODB_AVAILABLE or configs_collection is None:
        print("ไม่สามารถเชื่อมต่อกับ MongoDB ได้ (load_target_channel_id)")
        # โหลดจากไฟล์ท้องถิ่นแทน
        try:
            with open(SCRIPT_DIR / "target_channel_config.json", 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("target_channel_id", 1378803518030217328)
        except:
            return 1378803518030217328
    
    try:
        # ดึงข้อมูลจาก MongoDB
        data = configs_collection.find_one({"config_type": "target_channel"})
        if data:
            return data.get("target_channel_id", 1378803518030217328)
        else:
            return 1378803518030217328
    except Exception as e:
        print(f"ไม่สามารถโหลด Target Channel ID จาก MongoDB: {str(e)}")
        return 1378803518030217328

async def load_target_channel_id_async():
    """โหลด Target Channel ID จาก MongoDB (async version)
    
    Returns:
        int: ID ของช่องเป้าหมาย
    """
    return load_target_channel_id()

def save_target_channel_id(channel_id):
    """บันทึก Target Channel ID ลง MongoDB
    
    Args:
        channel_id (int): ID ของช่องเป้าหมาย
        
    Returns:
        bool: True ถ้าสำเร็จ
    """
    if not MONGODB_AVAILABLE or configs_collection is None:
        print("ไม่สามารถเชื่อมต่อกับ MongoDB ได้ (save_target_channel_id)")
        # บันทึกลงไฟล์ท้องถิ่นแทน
        try:
            with open(SCRIPT_DIR / "target_channel_config.json", 'w', encoding='utf-8') as f:
                json.dump({"target_channel_id": channel_id}, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"ไม่สามารถบันทึก Target Channel ID ลงไฟล์: {str(e)}")
            return False
    
    try:
        # ตรวจสอบว่ามีข้อมูลอยู่แล้วหรือไม่
        existing_data = configs_collection.find_one({"config_type": "target_channel"})
        
        channel_data = {
            "config_type": "target_channel",
            "target_channel_id": channel_id
        }
        
        if existing_data:
            # ถ้ามีข้อมูลอยู่แล้ว ให้อัปเดต
            configs_collection.replace_one({"_id": existing_data["_id"]}, channel_data)
        else:
            # ถ้ายังไม่มีข้อมูล ให้เพิ่มใหม่
            configs_collection.insert_one(channel_data)
        
        # บันทึกลงไฟล์ด้วย
        with open(SCRIPT_DIR / "target_channel_config.json", 'w', encoding='utf-8') as f:
            json.dump({"target_channel_id": channel_id}, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"ไม่สามารถบันทึก Target Channel ID ลง MongoDB: {str(e)}")
        return False

async def save_target_channel_id_to_mongodb(channel_id):
    """บันทึก Target Channel ID ลง MongoDB (async version)
    
    Args:
        channel_id (int): ID ของช่องเป้าหมาย
        
    Returns:
        bool: True ถ้าสำเร็จ
    """
    return save_target_channel_id(channel_id)

def load_channel_state():
    """โหลดสถานะช่องจาก MongoDB
    
    Returns:
        dict: ข้อมูลสถานะช่อง (channel_name, current_number, pending_number)
    """
    if not MONGODB_AVAILABLE or configs_collection is None:
        print("ไม่สามารถเชื่อมต่อกับ MongoDB ได้ (load_channel_state)")
        # โหลดจากไฟล์ท้องถิ่นแทน
        try:
            with open(SCRIPT_DIR / "channel_state.json", 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {"channel_name": "", "current_number": 0, "pending_number": 0}
    
    try:
        # ดึงข้อมูลจาก MongoDB
        data = configs_collection.find_one({"config_type": "channel_state"})
        if data:
            return {
                "channel_name": data.get("channel_name", ""),
                "current_number": data.get("current_number", 0),
                "pending_number": data.get("pending_number", 0)
            }
        else:
            return {"channel_name": "", "current_number": 0, "pending_number": 0}
    except Exception as e:
        print(f"ไม่สามารถโหลดสถานะช่องจาก MongoDB: {str(e)}")
        return {"channel_name": "", "current_number": 0, "pending_number": 0}

def save_channel_state(channel_name, current_number, pending_number):
    """บันทึกสถานะช่องลง MongoDB
    
    Args:
        channel_name (str): ชื่อช่องปัจจุบัน
        current_number (int): ตัวเลขปัจจุบันในชื่อช่อง
        pending_number (int): ตัวเลขที่รอการอัปเดต
        
    Returns:
        bool: True ถ้าสำเร็จ
    """
    if not MONGODB_AVAILABLE or configs_collection is None:
        print("ไม่สามารถเชื่อมต่อกับ MongoDB ได้ (save_channel_state)")
        # บันทึกลงไฟล์ท้องถิ่นแทน
        try:
            state_data = {
                "channel_name": channel_name,
                "current_number": current_number,
                "pending_number": pending_number
            }
            with open(SCRIPT_DIR / "channel_state.json", 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"ไม่สามารถบันทึกสถานะช่องลงไฟล์: {str(e)}")
            return False
    
    try:
        # ตรวจสอบว่ามีข้อมูลอยู่แล้วหรือไม่
        existing_data = configs_collection.find_one({"config_type": "channel_state"})
        
        state_data = {
            "config_type": "channel_state",
            "channel_name": channel_name,
            "current_number": current_number,
            "pending_number": pending_number
        }
        
        if existing_data:
            # ถ้ามีข้อมูลอยู่แล้ว ให้อัปเดต
            configs_collection.replace_one({"_id": existing_data["_id"]}, state_data)
        else:
            # ถ้ายังไม่มีข้อมูล ให้เพิ่มใหม่
            configs_collection.insert_one(state_data)
        
        # บันทึกลงไฟล์ด้วย
        state_data_copy = {
            "channel_name": channel_name,
            "current_number": current_number,
            "pending_number": pending_number
        }
        with open(SCRIPT_DIR / "channel_state.json", 'w', encoding='utf-8') as f:
            json.dump(state_data_copy, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        print(f"ไม่สามารถบันทึกสถานะช่องลง MongoDB: {str(e)}")
        return False

def get_next_channel_number():
    """ดึงตัวเลขถัดไปสำหรับชื่อช่อง
    
    Returns:
        int: ตัวเลขถัดไปที่ควรใช้
    """
    state = load_channel_state()
    return state.get("pending_number", 0)

def update_pending_number():
    """อัปเดตตัวเลขที่รอการอัปเดต (+1)
    
    Returns:
        int: ตัวเลขใหม่ที่อัปเดตแล้ว
    """
    state = load_channel_state()
    new_pending = state.get("pending_number", 0) + 1
    save_channel_state(
        state.get("channel_name", ""),
        state.get("current_number", 0),
        new_pending
    )
    return new_pending

def sync_channel_numbers(actual_channel_name):
    """ซิงค์ตัวเลขจากชื่อช่องจริงกับที่บันทึกไว้
    
    Args:
        actual_channel_name (str): ชื่อช่องจริงจาก Discord
        
    Returns:
        bool: True ถ้ามีการซิงค์
    """
    import re
    
    # หาตัวเลขในชื่อช่องจริง
    number_match = re.search(r'(\d+)$', actual_channel_name)
    if not number_match:
        return False
    
    actual_number = int(number_match.group(1))
    state = load_channel_state()
    
    # ถ้าตัวเลขจริงไม่ตรงกับที่บันทึกไว้ ให้ซิงค์
    if actual_number != state.get("current_number", 0):
        save_channel_state(
            actual_channel_name,
            actual_number,
            actual_number  # ซิงค์ pending_number ด้วย
        )
        print(f"🔄 ซิงค์ตัวเลขช่อง: {state.get('current_number', 0)} → {actual_number}")
        return True
    
    return False