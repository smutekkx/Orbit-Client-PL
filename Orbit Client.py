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

VERSION_LAUNCHER = "1.7"
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
        
        self.build_launcher_interface()

    def check_hwid_and_notify(self):
        try:
            # Pobranie UUID przez Get-CimInstance
            cmd = "powershell -Command \"(Get-CimInstance Win32_ComputerSystemProduct).UUID\""
            hwid = subprocess.check_output(cmd, shell=True).decode().strip()
            
            blacklisted_hwids = ["ZBANOWANY_UUID_1"]
            webhook_url = "https://discord.com/api/webhooks/1517492582282821636/HOkRsg0_zGjuVkm6HsBJb24T0_E1uerbrBcGb1isjZ39KvGaL6JNG51x5P-t9aWR0PZN" # prosze nie nukowac, to nie stealer
            
            if hwid in blacklisted_hwids:
                payload = {"content": f"🚫 **BLOCKED ACCESS**\nUUID: `{hwid}`"}
                requests.post(webhook_url, json=payload, timeout=10)
                sys.exit()
            else:
                # Wysłanie powiadomienia
                payload = {"content": f"✅ **LAUNCH ALERT**\nUUID: `{hwid}`"}
                response = requests.post(webhook_url, json=payload, timeout=10)
                
                # Sprawdzenie, czy Discord przyjął wiadomość (kod 200 lub 204 to sukces)
                if response.status_code not in [200, 204]:
                    print(f"Błąd wysyłania: {response.status_code}, {response.text}")
                
        except Exception as e:
            # Teraz zobaczysz błąd w konsoli zamiast cichego zamknięcia
            print(f"DEBUG ERROR: {e}")
                
        except Exception:
            sys.exit()
                
        except Exception:
            sys.exit()

    def check_for_updates(self):
        if "TWÓJ_LINK_DO_PLIKU_Z_KODEM" in UPDATE_URL:
            return  
            
        try:
            response = requests.get(UPDATE_URL, timeout=5)
            if response.status_code == 200:
                remote_code = response.text
                
                for line in remote_code.split("\n"):
                    if "VERSION_LAUNCHER =" in line:
                        remote_version = line.split("=")[1].strip().replace('"', '').replace("'", "")
                        
                        if remote_version != VERSION_LAUNCHER:
                            current_file = os.path.abspath(sys.argv[0])
                            
                            with open(current_file, "w", encoding="utf-8") as f:
                                f.write(remote_code)
                                
                            messagebox.showinfo("Orbit Updater", f"Wykryto nową wersję ({remote_version})! Launcher zaktualizował się automatycznie i uruchomi się ponownie.")
                            
                            subprocess.Popen([sys.executable, current_file])
                            sys.exit()
                        break
        except Exception as e:
            print(f"[Updater] Update failed: {e}")

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
        header = ctk.CTkFrame(self.viewport, height=120, fg_color=BG_PANEL, corner_radius=16)
        header.pack(fill="x", pady=(0, 20))
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="ORBIT CLIENT", font=("Impact", 44), text_color=TEXT_LIGHT).pack(side="left", padx=35, pady=25)
        ctk.CTkLabel(header, text="v1.0 (r)", font=("Segoe UI", 20), text_color=TEXT_LIGHT).pack(side="left", padx=35, pady=25)
        card = ctk.CTkFrame(self.viewport, fg_color=BG_PANEL, corner_radius=16)
        card.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(card, text="Twój nickname", font=("Segoe UI", 13, "bold"), text_color=TEXT_MUTED).pack(pady=(20, 2))
        ctk.CTkEntry(card, width=360, height=45, fg_color=BG_DARK, border_color="#262936", text_color=TEXT_LIGHT, textvariable=self.nick_var).pack(pady=5)

        ctk.CTkLabel(card, text="Wersja gry", font=("Segoe UI", 13, "bold"), text_color=TEXT_MUTED).pack(pady=(15, 2))
        self.v_dropdown = ctk.CTkOptionMenu(card, values=self.all_versions, width=360, height=42, fg_color=BG_DARK, button_color=ACCENT, command=lambda c: setattr(self, 'selected_version', c))
        self.v_dropdown.set(self.selected_version)
        self.v_dropdown.pack(pady=5)

        self.engine_btn = ctk.CTkButton(card, text=f"Silnik startowy: {self.mode}", width=360, height=42, fg_color="#1b1e26", hover_color="#242934", command=self._toggle_loader)
        self.engine_btn.pack(pady=15)

        self.status_bar = ctk.CTkLabel(card, text=f"Gotowy do uruchomienia", font=("Segoe UI", 13, "bold"), text_color="#10b981")
        self.status_bar.pack(pady=5)

        ctk.CTkButton(card, text="URUCHOM ORBIT CLIENT", fg_color=ACCENT, hover_color="#6d28d9", width=400, height=65, font=("Segoe UI", 20, "bold"), corner_radius=14,
                      command=lambda: threading.Thread(target=self.execute_minecraft_engine, daemon=True).start()).pack(pady=20)

    def _toggle_loader(self):
        self.mode = "Fabric" if self.mode == "Vanilla" else "Vanilla"
        self.engine_btn.configure(text=f"Silnik startowy: {self.mode}")

    def render_mods_view(self):
        self.clear_viewport()
        ctk.CTkLabel(self.viewport, text="Menedżer Modyfikacji Fabric", font=("Segoe UI", 26, "bold"), text_color=TEXT_LIGHT).pack(anchor="w", padx=25, pady=20)
        filter_frame = ctk.CTkFrame(self.viewport, fg_color="transparent")
        filter_frame.pack(fill="x", padx=25, pady=5)
        
        search_box = ctk.CTkEntry(filter_frame, placeholder_text="Wpisz nazwę moda i wciśnij Enter...", width=400, height=45, fg_color=BG_PANEL, border_color="#262936")
        search_box.pack(side="left", padx=(0, 15))
        
        mod_v_dropdown = ctk.CTkOptionMenu(filter_frame, values=self.mod_versions_list, width=120, height=42, fg_color=BG_PANEL, button_color=ACCENT, command=lambda c: setattr(self, 'mod_search_version', c))
        mod_v_dropdown.set(self.mod_search_version)
        mod_v_dropdown.pack(side="left")
        
        scroll = ctk.CTkScrollableFrame(self.viewport, fg_color=BG_PANEL, corner_radius=15)
        scroll.pack(fill="both", expand=True, pady=15, padx=25)

        def run_search(e=None):
            for w in scroll.winfo_children(): w.destroy()
            try:
                res = requests.get(f"https://api.modrinth.com/v2/search?query={search_box.get()}&facets=[[\"categories:fabric\"],[\"versions:{self.mod_search_version}\"]]").json()
                for item in res['hits']:
                    row = ctk.CTkFrame(scroll, fg_color=BG_DARK, height=60)
                    row.pack(fill="x", pady=6, padx=6)
                    ctk.CTkLabel(row, text=item['title'], font=("Segoe UI", 14, "bold"), text_color=TEXT_LIGHT).pack(side="left", padx=15)
                    ctk.CTkButton(row, text="Zainstaluj", fg_color=ACCENT, width=100, command=lambda m=item: self._download_mod(m, self.mod_search_version)).pack(side="right", padx=15, pady=10)
            except: pass
        search_box.bind("<Return>", run_search)

    def _download_mod(self, mod, version_str):
        try:
            v_data = requests.get(f"https://api.modrinth.com/v2/project/{mod['project_id']}/version").json()
            for v in v_data:
                if version_str in v['game_versions'] and 'fabric' in v['loaders']:
                    with open(os.path.join(INSTANCE_DIR, "mods", v['files'][0]['filename']), "wb") as f:
                        f.write(requests.get(v['files'][0]['url']).content)
                    messagebox.showinfo("Orbit Mod Engine", f"Dodano {mod['title']}!")
                    return
        except: pass

    def render_packs_view(self):
        self.clear_viewport()
        top_frame = ctk.CTkFrame(self.viewport, fg_color="transparent")
        top_frame.pack(fill="x", padx=25, pady=20)
        
        ctk.CTkLabel(top_frame, text="Menedżer Paczek Zasobów (Txt)", font=("Segoe UI", 26, "bold"), text_color=TEXT_LIGHT).pack(side="left")
        ctk.CTkButton(top_frame, text="📁 Otwórz folder", fg_color="#1b1e26", hover_color="#242934", font=("Segoe UI", 13, "bold"), command=lambda: os.startfile(PACKS_DIR)).pack(side="right", padx=5)
        ctk.CTkButton(top_frame, text="🔄 Odśwież", fg_color=ACCENT, hover_color="#6d28d9", font=("Segoe UI", 13, "bold"), width=100, command=self.render_packs_view).pack(side="right", padx=5)

        self.p_scroll = ctk.CTkScrollableFrame(self.viewport, fg_color=BG_PANEL, corner_radius=15)
        self.p_scroll.pack(fill="both", expand=True, pady=10, padx=25)
        self._load_local_resource_packs()

    def _load_local_resource_packs(self):
        for w in self.p_scroll.winfo_children(): w.destroy()
        if not os.path.exists(PACKS_DIR): os.makedirs(PACKS_DIR, exist_ok=True)
        files = os.listdir(PACKS_DIR)
        if not files:
            ctk.CTkLabel(self.p_scroll, text="Folder resourcepacks jest pusty. Wrzuć tu pliki .zip paczek zasobów!", font=("Segoe UI", 14), text_color=TEXT_MUTED).pack(pady=40)
            return
        for filename in files:
            row = ctk.CTkFrame(self.p_scroll, fg_color=BG_DARK, height=60)
            row.pack(fill="x", pady=6, padx=6)
            row.pack_propagate(False)
            ctk.CTkLabel(row, text="📦", font=("Arial", 20), text_color=ACCENT).pack(side="left", padx=15)
            ctk.CTkLabel(row, text=filename, font=("Segoe UI", 14, "bold"), text_color=TEXT_LIGHT, anchor="w").pack(side="left", fill="x", expand=True)
            ctk.CTkButton(row, text="Usuń", fg_color="#ef4444", hover_color="#dc2626", width=80, height=32, command=lambda f=filename: self._delete_resource_pack(f)).pack(side="right", padx=15)

    def _delete_resource_pack(self, filename):
        if messagebox.askyesno("Orbit Resource Packs", f"Czy na pewno chcesz trwale usunąć paczkę {filename}?"):
            try:
                target_path = os.path.join(PACKS_DIR, filename)
                if os.path.isdir(target_path): shutil.rmtree(target_path)
                else: os.remove(target_path)
                self.render_packs_view()
            except Exception as e: messagebox.showerror("Błąd", f"Nie udało się usunąć pliku: {str(e)}")

    def render_settings_view(self):
        self.clear_viewport()
        ctk.CTkLabel(self.viewport, text="Ustawienia RAM Javy", font=("Segoe UI", 26, "bold"), text_color=TEXT_LIGHT).pack(anchor="w", padx=25, pady=20)
        card = ctk.CTkFrame(self.viewport, fg_color=BG_PANEL, corner_radius=15)
        card.pack(fill="both", expand=True, padx=25, pady=10)
        self.ram_lbl = ctk.CTkLabel(card, text=f"Przydzielony RAM: {self.ram_val} GB", font=("Segoe UI", 15, "bold"), text_color=TEXT_LIGHT)
        self.ram_lbl.pack(anchor="w", padx=30, pady=20)
        slider = ctk.CTkSlider(card, from_=2, to=12, number_of_steps=10, button_color=ACCENT, progress_color=ACCENT, command=self._update_ram)
        slider.set(self.ram_val)
        slider.pack(fill="x", padx=30)

    def _update_ram(self, val):
        self.ram_val = int(val)
        self.ram_lbl.configure(text=f"Przydzielony RAM: {self.ram_val} GB")
        self.config_manager.settings["global_ram"] = self.ram_val
        self.config_manager.save_config()

    def render_console_view(self):
        self.clear_viewport()
        ctk.CTkLabel(self.viewport, text="Konsola błędów (Sprawdź tu, jeśli gra się crashuje)", font=("Segoe UI", 26, "bold"), text_color=TEXT_LIGHT).pack(anchor="w", padx=25, pady=20)
        self.console_text = ctk.CTkTextbox(self.viewport, fg_color=BG_PANEL, text_color="#10b981", font=("Consolas", 12))
        self.console_text.pack(fill="both", expand=True, padx=25, pady=15)

    def append_console_stream(self, text: str, level: str):
        if hasattr(self, 'console_text') and self.console_text.winfo_exists():
            self.console_text.insert("end", f"[{level}] {text}\n")
            self.console_text.see("end")

    def execute_minecraft_engine(self):
        try:
            self.after(0, lambda: self.status_bar.configure(text="Sprawdzanie i pobieranie plików gry...", text_color="#f59e0b"))
            minecraft_launcher_lib.install.install_minecraft_version(self.selected_version, BASE_FOLDER)
            target_runtime = self.selected_version
            if self.mode == "Fabric":
                self.after(0, lambda: self.status_bar.configure(text="Inicjalizacja środowiska Fabric...", text_color="#7c3aed"))
                fab = minecraft_launcher_lib.fabric.get_latest_loader_version()
                minecraft_launcher_lib.fabric.install_fabric(self.selected_version, BASE_FOLDER, loader_version=fab)
                target_runtime = f"fabric-loader-{fab}-{self.selected_version}"

            boost_args = [f"-Xmx{self.ram_val}G", "-XX:+UseG1GC", "-Dminecraft.applet.TargetDirectory=" + INSTANCE_DIR]
            options = {"username": self.user_nick, "uuid": str(uuid.uuid4()), "token": "", "jvmArguments": boost_args, "gameDirectory": INSTANCE_DIR}
            command = minecraft_launcher_lib.command.get_minecraft_command(target_runtime, BASE_FOLDER, options)
            self.after(0, lambda: self.status_bar.configure(text="Uruchamianie procesu gry...", text_color="#10b981"))
            
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            
            # Wysłanie powiadomienia na Discord
            threading.Thread(target=self.send_discord_webhook, args=(f"Użytkownik {self.user_nick} uruchomił grę: {self.selected_version} ({self.mode})",), daemon=True).start()
            
            watcher = OrbitLogWatcher(self.append_console_stream)
            watcher.start_watch(process)
            branding = OrbitWindowBrandingEngine(process.pid, "Orbit Client")
            threading.Thread(target=branding.monitor_target, daemon=True).start()
        except Exception as error_msg:
            err_str = str(error_msg)[:35]
            self.after(0, lambda: self.status_bar.configure(text=f"Blad startu: {err_str}", text_color="#ef4444"))

if __name__ == "__main__":
    app = OrbitLunarLauncher()
    app.mainloop()
