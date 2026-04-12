#!/usr/bin/env python3
# setup_images.py — ЗАПУСТИ ОДИН РАЗ для установки изображений
# Команда: cd "C:\Users\HP\OneDrive\Рабочий стол\Consilium AI v30"
#          python setup_images.py
# После этого перезапусти сервер: uvicorn main:app --reload --port 8000
import base64, os
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "img")
os.makedirs(IMG_DIR, exist_ok=True)
print(f"Installing images to: {IMG_DIR}")
# NOTE: The actual base64 data will be filled by Claude
# Run this after Claude writes the full version
print("ERROR: Run the full setup_images.py from Claude (this is a stub)")
