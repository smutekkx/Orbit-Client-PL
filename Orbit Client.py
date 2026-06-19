import os
import sys
import time
import requests
import subprocess
import threading
import warnings
from tkinter import messagebox
import customtkinter as ctk

# --- KONFIGURACJA ---
VERSION_LAUNCHER = "1.2" # Wersja 1.2, żebyś widział zmianę
UPDATE_URL = "https://raw.githubusercontent.com/smutekkx/Orbit-Client-PL/refs/heads/main/Orbit%20Client.py"
WEBHOOK_URL = "https://discord.com/api/webhooks/1517492582282821636/HOkRsg0_zGjuVkm6HsBJb24T0_E1uerbrBcGb1isjZ39KvGaL6JNG51x5P-t9aWR0PZN"
BANNED_HWIDS = ["WPISZ_HWID_TUTAJ"] 
# --------------------

warnings.simplefilter('ignore', UserWarning)
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def get_hwid():
    try:
        # Pobieramy numer seryjny płyty głównej (bardziej stabilne)
        cmd = 'wmic baseboard get serialnumber'
        hwid = subprocess.check_output(cmd, shell=True).decode().split('\n')[1].strip()
        return hwid
    except:
        return "UNKNOWN"

def check_ban(current_hwid):
    if current_hwid in BANNED_HWIDS:
        messagebox.showerror("Dostęp zablokowany", "Orbit Client nie jest dostępny dla tego urządzenia.")
        sys.exit()

def send_discord_log(nick, hwid):
    try:
        data = {"content": f"🚀 **Nowe uruchomienie**\n👤 Nick: {nick}\n💻 HWID: `{hwid}`"}
        requests.post(WEBHOOK_URL, json=data)
    except: pass

class OrbitClient(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Orbit Client - Profesjonalny Launcher")
        self.geometry("800x600") # Większe, konkretne okno
        self.resizable(False, False)
        
        # UI
        ctk.CTkLabel(self, text="ORBIT CLIENT", font=("Impact", 60), text_color="#1f6aa5").pack(pady=60)
        
        self.nick_var = ctk.StringVar(value="_smutek")
        ctk.CTkEntry(self, textvariable=self.nick_var, width=400, height=40, font=("Arial", 20)).pack(pady=20)
        
        ctk.CTkButton(self, text="URUCHOM GRĘ", command=self.start_app, width=400, height=60, font=("Impact", 25)).pack(pady=40)
        
        hwid = get_hwid()
        threading.Thread(target=lambda: send_discord_log(self.nick_var.get(), hwid), daemon=True).start()

    def start_app(self):
        messagebox.showinfo("Start", f"Uruchamiam Orbit Client dla: {self.nick_var.get()}")

if __name__ == "__main__":
    check_ban(get_hwid())
    app = OrbitClient()
    app.mainloop()
