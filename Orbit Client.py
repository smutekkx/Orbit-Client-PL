import sys
from tkinter import messagebox
import tkinter as tk

# Ukrywamy główne okno tkinter, żeby nie było pustej ramki w tle
root = tk.Tk()
root.withdraw()

# Wersja i komunikat
VERSION_LAUNCHER = "1.9.9.9"
messagebox.showerror("Orbit Client", f"Orbit Client v{VERSION_LAUNCHER}\n\nTrwają prace techniczne. Launcher jest obecnie niedostępny.")

# Wyjście z programu
sys.exit()
