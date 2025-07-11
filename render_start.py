#!/usr/bin/env python3
"""
Render.com startup script with Rate Limit handling
"""
import os
import sys
import time
import random
import subprocess
import signal

def main():
    """Main startup function for Render.com"""
    print("🚀 เริ่มต้นบอทสำหรับ Render.com")
    
    # ตรวจสอบ Environment Variables
    if not os.getenv('DISCORD_TOKEN'):
        print("❌ ไม่พบ DISCORD_TOKEN ใน Environment Variables")
        sys.exit(1)
    
    max_retries = 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            print(f"🔄 เริ่มบอท (ครั้งที่ {retry_count + 1})")
            
            # เพิ่ม random delay เพื่อหลีกเลี่ยง Rate Limiting
            if retry_count > 0:
                delay = random.uniform(30, 60)  # รอ 30-60 วินาที
                print(f"⏳ รอ {delay:.1f} วินาที หลังจาก Rate Limit...")
                time.sleep(delay)
            
            # รันบอท
            result = subprocess.run([sys.executable, "shopbot.py"], 
                                  capture_output=False, 
                                  text=True)
            
            if result.returncode == 0:
                print("✅ บอททำงานเสร็จสิ้นปกติ")
                break
            else:
                print(f"⚠️ บอทหยุดทำงาน (exit code: {result.returncode})")
                retry_count += 1
                
        except KeyboardInterrupt:
            print("👋 บอทถูกปิดโดยผู้ใช้")
            break
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาด: {e}")
            retry_count += 1
            
        if retry_count < max_retries:
            wait_time = min(60 * (2 ** retry_count), 300)  # Exponential backoff, max 5 minutes
            print(f"⏳ รอ {wait_time} วินาที ก่อนลองใหม่...")
            time.sleep(wait_time)
        else:
            print("❌ เกินจำนวนครั้งที่กำหนด - หยุดการทำงาน")
            sys.exit(1)

if __name__ == "__main__":
    main()