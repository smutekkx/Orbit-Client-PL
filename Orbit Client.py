import os
import sys
import time
import requests
import subprocess
import threading
import uuid
import json
import inspect
import warnings
from tkinter import messagebox
import customtkinter as ctk
import minecraft_launcher_lib

# --- KONFIGURACJA ---
VERSION_LAUNCHER = "1.02"
UPDATE_URL = "https://raw.githubusercontent.com/smutekkx/Orbit-Client-PL/refs/heads/main/Orbit%20Client.py"
WEBHOOK_URL = "https://discord.com/api/webhooks/1517492582282821636/HOkRsg0_zGjuVkm6HsBJb24T0_E1uerbrBcGb1isjZ39KvGaL6JNG51x5P-t9aWR0PZN"
BANNED_HWIDS = ""
# --------------------

warnings.simplefilter('ignore', UserWarning)

def get_hwid():
    try:
        cmd = 'wmic csproduct get uuid'
        return subprocess.check_output(cmd, shell=True).decode().split('\n')[1].strip()
    except:
        return "UNKNOWN"

def check_ban(current_hwid):
    if current_hwid in BANNED_HWIDS:
        messagebox.showerror("Błąd", "Orbit Client jest zablokowany dla tego sprzętu.")
        sys.exit()

def send_discord_log(nick, hwid):
    try:
        data = {"content": f"🚀 Uruchomienie Orbit Client | Nick: {nick} | HWID: `{hwid}`"}
        requests.post(WEBHOOK_URL, json=data)
    except: pass

def force_check_updates():
    try:
        resp = requests.get(f"{UPDATE_URL}?t={time.time()}", timeout=5)
        if resp.status_code == 200 and f'VERSION_LAUNCHER = "{VERSION_LAUNCHER}"' not in resp.text:
            with open(os.path.abspath(inspect.getfile(inspect.currentframe())), "w", encoding="utf-8") as f:
                f.write(resp.text)
            os.execl(sys.executable, sys.executable, *sys.argv)
    except: pass

# Start zabezpieczeń
force_check_updates()
hwid = get_hwid()
check_ban(hwid)

class OrbitClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Orbit Client v{VERSION_LAUNCHER}")
        self.geometry("400x250")
        
        self.nick_var = ctk.StringVar(value="_smutek")
        ctk.CTkLabel(self, text="Orbit Client", font=("Impact", 25)).pack(pady=20)
        ctk.CTkEntry(self, textvariable=self.nick_var).pack(pady=10)
        
        ctk.CTkButton(self, text="URUCHOM", command=self.start_app).pack(pady=20)
        
        # Wyślij log na Discorda przy starcie
        threading.Thread(target=lambda: send_discord_log(self.nick_var.get(), hwid), daemon=True).start()

    def start_app(self):
        messagebox.showinfo("Start", f"Uruchamiam grę dla {self.nick_var.get()}")

if __name__ == "__main__":
    app = OrbitClient()
    app.mainloop()
