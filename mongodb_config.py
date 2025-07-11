import os
import json
from pymongo import MongoClient
from dotenv import load_dotenv

# โหลด environment variables
load_dotenv()

# รับ MongoDB URI จาก environment variable
MONGODB_URI = os.getenv("MONGODB_URI", "")

# ระบบอนุญาตให้ทำงานต่อได้แม้ไม่มี MongoDB URI
if not MONGODB_URI:
    print("⚠️ ไม่พบการตั้งค่า MONGODB_URI ในไฟล์ .env หรือ environment variable")
    print("ตัวอย่าง URI: mongodb+srv://username:password@cluster.mongodb.net/")
    print("ระบบจะทำงานต่อโดยใช้ไฟล์ JSON แทน")
    
    # สร้างตัวแปรเปล่าสำหรับการทำงานแบบออฟไลน์
    client = None
    db = None
    products_collection = None
    categories_collection = None
    countries_collection = None
    history_collection = None
    configs_collection = None
else:
    try:
        # เชื่อมต่อกับ MongoDB
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        # ทดสอบการเชื่อมต่อ
        client.server_info()
        # ระบุชื่อ database ที่ต้องการใช้งาน (ถ้าไม่มีจะถูกสร้างอัตโนมัติ)
        db = client["discord_shop_bot"]
        
        # คอลเลกชั่นต่างๆ
        products_collection = db["products"]
        categories_collection = db["categories"]
        countries_collection = db["countries"]
        history_collection = db["history"]
        configs_collection = db["configs"]
        
        print("✅ เชื่อมต่อกับ MongoDB สำเร็จ!")
    except Exception as e:
        print(f"❌ ไม่สามารถเชื่อมต่อกับ MongoDB ได้: {str(e)}")
        print("ระบบจะทำงานต่อโดยใช้ไฟล์ JSON แทน")
        
        # สร้างตัวแปรเปล่าสำหรับการทำงานแบบออฟไลน์
        client = None
        db = None
        products_collection = None
        categories_collection = None
        countries_collection = None
        history_collection = None
        configs_collection = None

# ตัวแปรเหล่านี้ถูกกำหนดไว้แล้วในเงื่อนไข if-else ด้านบน
# จะไม่กำหนดซ้ำอีกเพื่อป้องกันการเขียนทับตัวแปรที่เป็น None
# ในกรณีที่ไม่สามารถเชื่อมต่อกับ MongoDB ได้

# ฟังก์ชันสำหรับการตั้งค่าครั้งแรก
def initialize_db():
    """ตั้งค่าฐานข้อมูลเริ่มต้นหากยังไม่มีข้อมูล"""
    
    # ตรวจสอบว่ามีการเชื่อมต่อ MongoDB หรือไม่
    if client is None or db is None:
        print("⚠️ ไม่มีการเชื่อมต่อ MongoDB - ข้ามการตั้งค่าฐานข้อมูล")
        return
    
    # ตรวจสอบและตั้งค่าประเทศเริ่มต้น
    if countries_collection.count_documents({}) == 0:
        try:
            with open('countries.json', 'r', encoding='utf-8') as f:
                countries_data = json.load(f)
                if countries_data:
                    countries_collection.insert_one(countries_data)
                    print("✅ นำเข้าข้อมูลประเทศเริ่มต้นสำเร็จ")
        except FileNotFoundError:
            # ข้อมูลประเทศเริ่มต้นหากไม่มีไฟล์
            countries_data = {
                "countries": ["1", "2", "3", "4", "5"],
                "country_names": {
                    "1": "ไทย",
                    "2": "ญี่ปุ่น",
                    "3": "อเมริกา",
                    "4": "เกาหลี",
                    "5": "จีน"
                },
                "country_emojis": {
                    "1": "🇹🇭",
                    "2": "🌸",
                    "3": "🦅",
                    "4": "🇰🇷",
                    "5": "🇨🇳"
                },
                "country_codes": {
                    "thailand": "1",
                    "japan": "2",
                    "usa": "3",
                    "korea": "4",
                    "china": "5"
                }
            }
            countries_collection.insert_one(countries_data)
            print("✅ สร้างข้อมูลประเทศเริ่มต้นสำเร็จ")
    
    # ตรวจสอบการตั้งค่า QR code
    if configs_collection.count_documents({"config_type": "qrcode"}) == 0:
        try:
            with open('qrcode_config.json', 'r', encoding='utf-8') as f:
                qrcode_data = json.load(f)
                qrcode_data["config_type"] = "qrcode"
                configs_collection.insert_one(qrcode_data)
                print("✅ นำเข้าข้อมูล QR code เริ่มต้นสำเร็จ")
        except FileNotFoundError:
            # ข้อมูล QR code เริ่มต้นหากไม่มีไฟล์
            qrcode_data = {
                "config_type": "qrcode",
                "url": "https://promptpay.io/1234567890"
            }
            configs_collection.insert_one(qrcode_data)
            print("✅ สร้างข้อมูล QR code เริ่มต้นสำเร็จ")
    
    # ตรวจสอบการตั้งค่าข้อความขอบคุณ
    if configs_collection.count_documents({"config_type": "thank_you"}) == 0:
        try:
            with open('thank_you_config.json', 'r', encoding='utf-8') as f:
                thank_you_data = json.load(f)
                thank_you_data["config_type"] = "thank_you"
                configs_collection.insert_one(thank_you_data)
                print("✅ นำเข้าข้อความขอบคุณเริ่มต้นสำเร็จ")
        except FileNotFoundError:
            # ข้อความขอบคุณเริ่มต้นหากไม่มีไฟล์
            thank_you_data = {
                "config_type": "thank_you",
                "message": "✅ ขอบคุณสำหรับการสั่งซื้อ! สินค้าจะถูกส่งถึงคุณเร็วๆ นี้"
            }
            configs_collection.insert_one(thank_you_data)
            print("✅ สร้างข้อความขอบคุณเริ่มต้นสำเร็จ")
    
    # นำเข้าข้อมูลสินค้าจากไฟล์ products.json ครั้งแรก (ถ้ามี)
    if products_collection.count_documents({}) == 0:
        try:
            # นำเข้าจากไฟล์ products.json
            with open('products.json', 'r', encoding='utf-8') as f:
                products_data = json.load(f)
                if products_data:
                    for product in products_data:
                        products_collection.insert_one(product)
                    print(f"✅ นำเข้าสินค้าจากไฟล์เริ่มต้นสำเร็จ จำนวน {len(products_data)} รายการ")
        except (FileNotFoundError, json.JSONDecodeError):
            print("ไม่พบไฟล์ products.json หรือไฟล์ไม่ถูกต้อง - ข้ามการนำเข้า")
        
        # นำเข้าจากโฟลเดอร์ categories (ถ้ามี)
        categories_dir = "categories"
        if os.path.exists(categories_dir) and os.path.isdir(categories_dir):
            print("พบโฟลเดอร์ categories - กำลังนำเข้าสินค้าแยกตามหมวดหมู่...")
            
            for country in ["1", "2", "3", "4", "5"]:
                country_dir = os.path.join(categories_dir, country)
                if os.path.exists(country_dir) and os.path.isdir(country_dir):
                    for category_file in os.listdir(country_dir):
                        if category_file.endswith('.json'):
                            category = category_file.replace('.json', '')
                            try:
                                with open(os.path.join(country_dir, category_file), 'r', encoding='utf-8') as f:
                                    category_products = json.load(f)
                                    if category_products:
                                        for product in category_products:
                                            if not product.get('country'):
                                                product['country'] = country
                                            if not product.get('category'):
                                                product['category'] = category
                                            products_collection.insert_one(product)
                                        print(f"✅ นำเข้าสินค้าจากหมวด {category} ประเทศ {country} สำเร็จ จำนวน {len(category_products)} รายการ")
                            except (FileNotFoundError, json.JSONDecodeError) as e:
                                print(f"ข้อผิดพลาดในการนำเข้าไฟล์ {category_file}: {e}")

# เรียกฟังก์ชันเริ่มต้นเมื่อนำเข้าโมดูล
if __name__ == "__main__":
    print("กำลังเริ่มต้นการเชื่อมต่อกับ MongoDB...")
    initialize_db()
    print("เชื่อมต่อกับ MongoDB สำเร็จ!")