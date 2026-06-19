import os
import sys
import time
import json
import uuid
import shutil
import logging
import threading
import subprocess
import webbrowser
from typing import Optional, Any, Callable
from tkinter import messagebox
import customtkinter as ctk
import minecraft_launcher_lib
import requests
import warnings

# --- KONFIGURACJA ---
VERSION_LAUNCHER = "1.01"
UPDATE_URL = "https://raw.githubusercontent.com/smutekkx/Orbit-Client-PL/refs/heads/main/Orbit%20Client.py"
WEBHOOK_URL = "https://discord.com/api/webhooks/1517492582282821636/HOkRsg0_zGjuVkm6HsBJb24T0_E1uerbrBcGb1isjZ39KvGaL6JNG51x5P-t9aWR0PZN"
BANNED_HWIDS = ["hwid"]
# --------------------

# Zabezpieczenia systemowe
def get_hwid():
    try:
        cmd = 'powershell.exe -Command "(Get-CimInstance Win32_BaseBoard).SerialNumber"'
        return subprocess.check_output(cmd, shell=True).decode().strip()
    except:
        return "ERROR_HWID"

def check_ban(current_hwid):
    if current_hwid in BANNED_HWIDS:
        messagebox.showerror("Dostęp zablokowany", "Ten sprzęt ma bana w Orbit Client.")
        sys.exit()

def send_discord_log(nick, hwid):
    try:
        data = {"content": f"🚀 Uruchomienie Orbit | Nick: {nick} | HWID: `{hwid}`"}
        requests.post(WEBHOOK_URL, json=data)
    except: pass

# Sprawdzenie bana przed startem
check_ban(get_hwid())

# Reszta Twojego kodu...
try:
    import win32gui, win32con, win32process, win32api
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32"])
    import win32gui, win32con, win32process, win32api

try:
    from PIL import Image, ImageTk
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageTk

BASE_FOLDER = os.path.expanduser("~/.orbit_client")
BG_DARK, BG_PANEL, ACCENT, TEXT_LIGHT, TEXT_MUTED = "#0d0e11", "#14161d", "#7c3aed", "#f3f4f6", "#6b7280"
INSTANCE_DIR = os.path.join(BASE_FOLDER, "instances", "default")
PACKS_DIR = os.path.join(INSTANCE_DIR, "resourcepacks")

# [Tu wstaw resztę swojego kodu: OrbitConfigManager, OrbitWindowBrandingEngine, OrbitSkinCacheManager, OrbitLogWatcher...]
# (Pamiętaj, aby na początku klasy OrbitLunarLauncher dodać wywołanie logowania):

class OrbitLunarLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        # ... Twoje ustawienia ...
        
        # Wyślij logi na start
        threading.Thread(target=lambda: send_discord_log(self.user_nick, get_hwid()), daemon=True).start()

# ... reszta metod ...

if __name__ == "__main__":
    app = OrbitLunarLauncher()
    app.mainloop()
