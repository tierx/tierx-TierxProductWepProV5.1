import os
from dotenv import load_dotenv
from pymongo import MongoClient
import json

# โหลด environment variables
load_dotenv()

# รับ MongoDB URI จาก environment variable
MONGODB_URI = os.getenv("MONGODB_URI", "")

if not MONGODB_URI:
    print("❌ กรุณาตั้งค่า MONGODB_URI ในไฟล์ .env หรือ environment variable")
    print("ตัวอย่าง URI: mongodb+srv://username:password@cluster.mongodb.net/")
    exit(1)

try:
    # เชื่อมต่อกับ MongoDB
    client = MongoClient(MONGODB_URI)
    
    # ทดสอบการเชื่อมต่อ
    client.admin.command('ping')
    
    print("✅ เชื่อมต่อกับ MongoDB สำเร็จ!")
    print("สามารถใช้ฐานข้อมูล MongoDB แทนไฟล์ JSON ได้")
    
    # แสดงรายการฐานข้อมูลทั้งหมด
    databases = client.list_database_names()
    print(f"รายการฐานข้อมูลที่มีอยู่: {', '.join(databases)}")
    
    # ทดสอบการเข้าถึงฐานข้อมูลของบอท
    db = client["discord_shop_bot"]
    
    # ทดสอบการสร้างคอลเลกชั่น
    test_collection = db["test"]
    test_data = {
        "test": True,
        "message": "ทดสอบการเชื่อมต่อสำเร็จ",
        "timestamp": str(datetime.now())
    }
    
    test_collection.insert_one(test_data)
    print("✅ ทดสอบการบันทึกข้อมูลสำเร็จ")
    
    # ลบข้อมูลทดสอบ
    test_collection.delete_many({"test": True})
    print("✅ ทดสอบการลบข้อมูลสำเร็จ")
    
except Exception as e:
    print(f"❌ เกิดข้อผิดพลาดในการเชื่อมต่อกับ MongoDB: {str(e)}")
    print("กรุณาตรวจสอบ MONGODB_URI ว่าถูกต้องหรือไม่")
    exit(1)