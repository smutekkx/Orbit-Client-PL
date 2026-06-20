import customtkinter as ctk
import threading
import subprocess
import requests
import sys
import os
from typing import Callable, Optional
from PIL import Image, ImageTk

# --- TUTAJ KLASA ---
class OrbitLunarLauncher(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Orbit Client")
        self.geometry("400x300")
        ctk.CTkLabel(self, text="Działa!").pack()

# --- URUCHOMIENIE ---
if __name__ == "__main__":
    app = OrbitLunarLauncher()
    app.mainloop()
