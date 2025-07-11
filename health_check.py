#!/usr/bin/env python3
"""
Health check script for Render.com deployment
ใช้สำหรับตรวจสอบสถานะของบอทโดยไม่ต้อง restart ระบบเมื่อเกิด Rate Limit
"""

import os
import sys
import time
import json
import logging
from pathlib import Path

def setup_logging():
    """ตั้งค่า logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger("health_check")

def check_bot_health():
    """ตรวจสอบสถานะของบอท"""
    logger = setup_logging()
    
    # ตรวจสอบ environment variables ที่จำเป็น
    required_env_vars = ['DISCORD_TOKEN', 'MONGODB_URI']
    missing_vars = []
    
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing environment variables: {missing_vars}")
        return False
    
    # ตรวจสอบไฟล์ที่จำเป็น
    required_files = ['shopbot.py', 'db_operations.py', 'render_helper.py']
    missing_files = []
    
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        logger.error(f"Missing required files: {missing_files}")
        return False
    
    logger.info("All health checks passed")
    return True

def create_health_status():
    """สร้างไฟล์สถานะสุขภาพ"""
    status = {
        "timestamp": time.time(),
        "status": "healthy" if check_bot_health() else "unhealthy",
        "environment": "production" if os.getenv("RENDER") else "development"
    }
    
    with open('health_status.json', 'w') as f:
        json.dump(status, f, indent=2)
    
    return status

if __name__ == "__main__":
    status = create_health_status()
    print(json.dumps(status, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if status["status"] == "healthy" else 1)