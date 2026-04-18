#!/usr/bin/env python3
"""Gacha Quest - A Turn-Based RPG with Gacha System"""
import tkinter as tk
from game.screens import GameApp

if __name__ == "__main__":
    root = tk.Tk()
    app = GameApp(root)
    root.mainloop()
