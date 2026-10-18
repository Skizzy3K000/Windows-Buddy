"""
Windows Buddy — lightweight Windows desktop assistant.
Version: 0.1.0
Python 3.13 compatible; Tkinter standard library, optional psutil and pystray/Pillow.
"""
from __future__ import annotations

import json
import os
import platform
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser

APP_NAME = "Windows Buddy"
VERSION = "0.1.0"
APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "WindowsBuddy"
SETTINGS_FILE = APP_DIR / "settings.json"
REMINDERS_FILE = APP_DIR / "reminders.json"
DEFAULTS = {
    "theme": "dark", "accent": "#35c9ff", "text_size": 10,
    "spacing": "comfortable", "minimal_animations": True,
    "personality": "Friendly", "custom_personality": "",
    "catchphrase": "I think we're winning the war", "catchphrase_enabled": True,
    "openai_enabled": False, "openai_key": "", "openai_model": "gpt-4.1-mini",
    "gemini_enabled": False, "gemini_key": "", "gemini_model": "gemini-2.5-flash",
    "github_repo": "", "stats_enabled": True, "defender_enabled": True,
    "notifications_enabled": True, "online_ai_enabled": True,
    "performance": "Balanced", "close_to_tray": True
}
PALETTES = {
    "dark": {"bg":"#101827", "panel":"#172438", "panel2":"#203149", "fg":"#e8f3ff", "muted":"#9bb0c7", "entry":"#0b1220"},
    "light": {"bg":"#e9eff6", "panel":"#ffffff", "panel2":"#dbe6f1", "fg":"#142235", "muted":"#52677d", "entry":"#ffffff"}
}
ACCENTS = {"Cyan":"#35c9ff", "Purple":"#b28dff", "Emerald":"#36d399", "Orange":"#ffad5a", "Pink":"#ff78b7"}

def read_json(path: Path, fallback):
    try:
        with path.open("r", encoding="utf-8") as f:
            value = json.load(f)
        return value
    except (OSError, json.JSONDecodeError, TypeError):
        return fallback.copy() if isinstance(fallback, dict) else list(fallback)

def write_json(path: Path, value):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
    tmp.replace(path)

def parse_version(tag):
    """Parse the numeric portion of common tags such as v1.2.3."""
    import re
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", str(tag))
    return tuple(map(int, match.groups())) if match else None

def command_reply(text):
    """Pure offline command helper, used by the GUI and tests."""
    s = text.strip().lower()
    if not s:
        return "Type a message, or enter 'help' to see what I can do."
    if s in {"help", "/help", "commands"}:
        return "Commands: help, time, date, stats, joke, open notepad, open calculator, timer 5m, remind 10m Take a break."
    if s == "time":
        return "It's " + datetime.now().strftime("%H:%M:%S") + "."
    if s == "date":
        return "Today is " + datetime.now().strftime("%A, %d %B %Y") + "."
    if s == "stats":
        return "Open the PC Stats page and press Refresh to view local system information."
    if "joke" in s:
        return random.choice([
            "Why did the computer get cold? It left its Windows open.",
            "I tried to make a belt out of watches. It was a waist of time.",
            "There are 10 kinds of people: those who understand binary and those who don't."
        ])
    if any(x in s for x in ("bad day", "sad", "upset", "stressed", "rough day")):
        return random.choice(["Sorry today has been rough. You don't have to solve everything at once.",
                              "Oof, that sounds difficult. Take a breath and tackle one small thing at a time.",
                              "I'm here to help you think it through, one step at a time."])
    if any(x in s for x in ("hello", "hi buddy", "hey", "yo")):
        return random.choice(["Hey! Buddy's online. What are we doing today?", "Yo! Windows Buddy reporting in.", "Hey there. Ready when you are."])
    if any(x in s for x in ("thank", "cheers")):
        return random.choice(["Anytime!", "You're welcome!", "No worries — that's what I'm here for."])
    return random.choice(["I'm not sure I caught that. Try 'help' to see my offline commands.",
                          "I don't know that one yet, but I can still help with my built-in commands.",
                          "That one's outside my offline toolkit for now. Try rephrasing it?"])

def parse_delay(value):
    """Return seconds from values like 30s, 5m, 2h, or a plain number of minutes."""
    value = value.strip().lower()
    import re
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(s|sec|seconds?|m|min|minutes?|h|hours?)?", value)
    if not m:
        raise ValueError("Use a delay such as 30s, 5m, or 2h.")
    amount = float(m.group(1))
    unit = m.group(2) or "m"
    multiplier = 1 if unit.startswith("s") else (3600 if unit.startswith("h") else 60)
    seconds = int(amount * multiplier)
    if seconds < 1 or seconds > 7 * 24 * 3600:
        raise ValueError("Delay must be between 1 second and 7 days.")
    return seconds

class MiniPopup(tk.Toplevel):
    """Small, separate classic-style dialog window; deliberately not a speech bubble."""
    def __init__(self, app, title, body, kind="info", buttons=None, timeout=None, on_close=None):
        super().__init__(app)
        self.app = app
        self.on_close = on_close
        colors = app.colors
        self.title(title)
        self.configure(bg=colors["panel"])
        self.resizable(False, False)
        self.transient(app if app.state() != "withdrawn" else None)
        self.attributes("-topmost", True)
        self.geometry("360x150")
        self.protocol("WM_DELETE_WINDOW", self.close)
        outer = tk.Frame(self, bg=colors["panel"], padx=12, pady=10)
        outer.pack(fill="both", expand=True)
        top = tk.Frame(outer, bg=colors["panel"])
        top.pack(fill="x")
        icon = {"warning":"⚠", "error":"✖", "security":"🛡", "timer":"◷", "info":"ℹ"}.get(kind, "ℹ")
        tk.Label(top, text=icon, bg=colors["panel"], fg=app.settings.get("accent", "#35c9ff"),
                 font=("Segoe UI", 18, "bold"), width=2).pack(side="left", anchor="n")
        tk.Label(top, text=body, bg=colors["panel"], fg=colors["fg"], font=("Segoe UI", 10),
                 justify="left", wraplength=285).pack(side="left", fill="both", expand=True, padx=(8,0))
        bar = tk.Frame(outer, bg=colors["panel"])
        bar.pack(side="bottom", fill="x", pady=(10,0))
        for label, callback in (buttons or [("OK", self.close)]):
            tk.Button(bar, text=label, command=callback, padx=12, pady=3,
                      bg=colors["panel2"], fg=colors["fg"], activebackground=app.settings.get("accent", "#35c9ff"),
                      relief="raised", bd=2).pack(side="right", padx=(6,0))
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        # Stack compact windows upward from the lower-right corner.
        count = len(app.popups)
        self.geometry(f"+{sw-self.winfo_width()-24}+{sh-self.winfo_height()-60-count*22}")
        app.popups.add(self)
        self.bind("<Destroy>", self._destroyed, add="+")
        if timeout:
            self.after(timeout, self.close)

    def _destroyed(self, event):
        if event.widget is self:
            self.app.popups.discard(self)

    def close(self):
        try:
            self.destroy()
        finally:
            if self.on_close:
                cb, self.on_close = self.on_close, None
                cb()

class WindowsBuddy(tk.Tk):
    def __init__(self):
        super().__init__()
        self.settings = read_json(SETTINGS_FILE, DEFAULTS)
        for k, v in DEFAULTS.items():
            self.settings.setdefault(k, v)
        self.reminders = read_json(REMINDERS_FILE, [])
        if not isinstance(self.reminders, list):
            self.reminders = []
        self.colors = PALETTES.get(self.settings.get("theme"), PALETTES["dark"]).copy()
        self.colors["accent"] = self.settings.get("accent", "#35c9ff")
        self.popups = set()
        self.tray_icon = None
        self.tray_thread = None
        self._tray_available = False
        self._closing = False
        self._timer_deadlines = []
        self.title(f"{APP_NAME} {VERSION}")
        self.geometry("960x650")
        self.minsize(760, 520)
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)
        self._build_style()
        self._build_layout()
        self.show_page("Home / Chat")
        self._greet()
        self.after(1000, self._tick)
        self.after(1500, self._setup_tray)
        self._save_settings()

    def _build_style(self):
        self.configure(bg=self.colors["bg"])
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure("TFrame", background=self.colors["bg"])
        style.configure("Panel.TFrame", background=self.colors["panel"])
        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["fg"], font=("Segoe UI", self.settings.get("text_size", 10)))
        style.configure("Panel.TLabel", background=self.colors["panel"], foreground=self.colors["fg"])
        style.configure("TButton", padding=6)
        style.configure("TNotebook", background=self.colors["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", padding=(10, 6))

    def _build_layout(self):
        self.root_frame = tk.Frame(self, bg=self.colors["bg"])
        self.root_frame.pack(fill="both", expand=True)
        self.sidebar = tk.Frame(self.root_frame, bg=self.colors["panel"], width=190)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        head = tk.Frame(self.sidebar, bg=self.colors["panel"], padx=12, pady=14)
        head.pack(fill="x")
        tk.Label(head, text="▣ WINDOWS", bg=self.colors["panel"], fg=self.colors["accent"], font=("Consolas", 12, "bold")).pack(anchor="w")
        tk.Label(head, text="B U D D Y", bg=self.colors["panel"], fg=self.colors["fg"], font=("Consolas", 15, "bold")).pack(anchor="w")
        self.collapse_btn = tk.Button(head, text="☰  Collapse menu", command=self.toggle_sidebar, bg=self.colors["panel2"], fg=self.colors["fg"], relief="flat")
        self.collapse_btn.pack(fill="x", pady=(10,0))
        self.nav_frame = tk.Frame(self.sidebar, bg=self.colors["panel"])
        self.nav_frame.pack(fill="x", pady=8)
        self.nav_names = ["Home / Chat", "PC Stats", "Reminders", "Security", "API Keys", "Personalisation", "Permissions", "Updates"]
        self.nav_buttons = {}
        for name in self.nav_names:
            b = tk.Button(self.nav_frame, text="  "+name, anchor="w", command=lambda n=name:self.show_page(n),
                          bg=self.colors["panel"], fg=self.colors["fg"], activebackground=self.colors["panel2"],
                          activeforeground=self.colors["fg"], relief="flat", padx=8, pady=8)
            b.pack(fill="x", padx=6, pady=1)
            self.nav_buttons[name] = b
        self.main = tk.Frame(self.root_frame, bg=self.colors["bg"], padx=18, pady=16)
        self.main.pack(side="left", fill="both", expand=True)
        self.status = tk.StringVar(value="Ready • Offline mode available")
        tk.Label(self, textvariable=self.status, anchor="w", bg=self.colors["panel"], fg=self.colors["muted"], padx=10, pady=5).pack(side="bottom", fill="x")
        self.sidebar_collapsed = False
        self.pages = {}
        for name in self.nav_names:
            self.pages[name] = tk.Frame(self.main, bg=self.colors["bg"])
        self._build_home()
        self._build_stats()
        self._build_reminders()
        self._build_security()
        self._build_api()
        self._build_personalisation()
        self._build_permissions()
        self._build_updates()

    def _heading(self, parent, title, subtitle=""):
        tk.Label(parent, text=title, bg=self.colors["bg"], fg=self.colors["fg"], font=("Segoe UI", 20, "bold")).pack(anchor="w")
        if subtitle: tk.Label(parent, text=subtitle, bg=self.colors["bg"], fg=self.colors["muted"], font=("Segoe UI", 10)).pack(anchor="w", pady=(3,12))

    def _button(self, parent, text, command, **kw):
        return tk.Button(parent, text=text, command=command, bg=self.colors["panel2"], fg=self.colors["fg"],
                         activebackground=self.colors["accent"], relief="raised", bd=2, padx=10, pady=5, **kw)

    def _build_home(self):
        p = self.pages["Home / Chat"]
        self._heading(p, "Home / Chat", "A small desktop sidekick. Offline commands work without an API key.")
        self.chat = tk.Text(p, wrap="word", state="disabled", bg=self.colors["panel"], fg=self.colors["fg"],
                            insertbackground=self.colors["fg"], relief="flat", padx=12, pady=12, font=("Segoe UI", 10))
        self.chat.pack(fill="both", expand=True)
        self.chat.tag_configure("user", foreground=self.colors["accent"], spacing1=6)
        self.chat.tag_configure("buddy", foreground=self.colors["fg"], spacing1=6)
        row = tk.Frame(p, bg=self.colors["bg"])
        row.pack(fill="x", pady=(10,0))
        self.chat_input = tk.Entry(row, bg=self.colors["entry"], fg=self.colors["fg"], insertbackground=self.colors["fg"], relief="flat", font=("Segoe UI", 11))
        self.chat_input.pack(side="left", fill="x", expand=True, ipady=8, padx=(0,8))
        self.chat_input.bind("<Return>", lambda e:self.send_chat())
        self._button(row, "Send", self.send_chat).pack(side="right")
        row2 = tk.Frame(p, bg=self.colors["bg"]); row2.pack(fill="x", pady=(8,0))
        self._button(row2, "Start 5-minute timer", lambda:self.start_timer(300)).pack(side="left")
        self._button(row2, "Quick alert preview", lambda:self.popup("Buddy alert", "This is a classic mini-window alert.", "info")).pack(side="left", padx=8)

    def _build_stats(self):
        p=self.pages["PC Stats"]; self._heading(p,"PC Stats","Read-only local information. Nothing is uploaded.")
        self.stats_text=tk.Text(p,height=12,wrap="word",state="disabled",bg=self.colors["panel"],fg=self.colors["fg"],relief="flat",padx=12,pady=12)
        self.stats_text.pack(fill="x",pady=10)
        self._button(p,"Refresh stats",self.refresh_stats).pack(anchor="w")

    def _build_reminders(self):
        p=self.pages["Reminders"]; self._heading(p,"Reminders","Reminders fire while Windows Buddy is running.")
        form=tk.Frame(p,bg=self.colors["bg"]); form.pack(fill="x",pady=6)
        tk.Label(form,text="Reminder",bg=self.colors["bg"],fg=self.colors["fg"]).grid(row=0,column=0,sticky="w")
        self.reminder_title=tk.Entry(form,bg=self.colors["entry"],fg=self.colors["fg"],insertbackground=self.colors["fg"],width=34)
        self.reminder_title.grid(row=1,column=0,sticky="ew",padx=(0,8),ipady=5)
        tk.Label(form,text="Delay (e.g. 30s, 5m, 2h)",bg=self.colors["bg"],fg=self.colors["fg"]).grid(row=0,column=1,sticky="w")
        self.reminder_delay=tk.Entry(form,bg=self.colors["entry"],fg=self.colors["fg"],insertbackground=self.colors["fg"],width=24)
        self.reminder_delay.grid(row=1,column=1,sticky="ew",ipady=5)
        form.columnconfigure(0,weight=2); form.columnconfigure(1,weight=1)
        self._button(p,"Add reminder",self.add_reminder).pack(anchor="w",pady=8)
        self.reminders_list=tk.Listbox(p,bg=self.colors["panel"],fg=self.colors["fg"],selectbackground=self.colors["accent"],height=12,relief="flat")
        self.reminders_list.pack(fill="both",expand=True,pady=(4,8))
        row=tk.Frame(p,bg=self.colors["bg"]); row.pack(fill="x")
        self._button(row,"Mark selected complete",self.complete_reminder).pack(side="left")
        self._button(row,"Refresh list",self.refresh_reminders).pack(side="left",padx=8)
        self.refresh_reminders()

    def _build_security(self):
        p=self.pages["Security"]; self._heading(p,"Security","Read-only status checks. This is not a virus scanner.")
        self.security_text=tk.Text(p,height=12,wrap="word",state="disabled",bg=self.colors["panel"],fg=self.colors["fg"],relief="flat",padx=12,pady=12)
        self.security_text.pack(fill="x",pady=10)
        self._button(p,"Check Defender status",self.check_defender).pack(anchor="w")
        tk.Label(p,text="For full protection details, open the Windows Security app.",bg=self.colors["bg"],fg=self.colors["muted"]).pack(anchor="w",pady=12)

    def _build_api(self):
        p=self.pages["API Keys"]; self._heading(p,"API Keys","Optional. Buddy works without internet or an API key.")
        self.api_vars={}
        for provider in ("openai","gemini"):
            frame=tk.LabelFrame(p,text=provider.title(),bg=self.colors["bg"],fg=self.colors["fg"],padx=10,pady=8)
            frame.pack(fill="x",pady=6)
            enabled=tk.BooleanVar(value=self.settings.get(provider+"_enabled",False))
            tk.Checkbutton(frame,text="Enable provider",variable=enabled,bg=self.colors["bg"],fg=self.colors["fg"],selectcolor=self.colors["panel"],activebackground=self.colors["bg"]).grid(row=0,column=0,sticky="w")
            key=tk.StringVar(value=self.settings.get(provider+"_key",""))
            ent=tk.Entry(frame,textvariable=key,show="•",bg=self.colors["entry"],fg=self.colors["fg"],insertbackground=self.colors["fg"],width=52)
            ent.grid(row=1,column=0,sticky="ew",pady=4)
            show=tk.BooleanVar(value=False)
            tk.Checkbutton(frame,text="Show key",variable=show,command=lambda e=ent,v=show:e.configure(show="" if v.get() else "•"),bg=self.colors["bg"],fg=self.colors["fg"],selectcolor=self.colors["panel"]).grid(row=1,column=1,padx=8)
            model=tk.StringVar(value=self.settings.get(provider+"_model", "gpt-4.1-mini" if provider=="openai" else "gemini-2.5-flash"))
            tk.Label(frame,text="Model",bg=self.colors["bg"],fg=self.colors["fg"]).grid(row=2,column=0,sticky="w")
            modelent=tk.Entry(frame,textvariable=model,bg=self.colors["entry"],fg=self.colors["fg"],insertbackground=self.colors["fg"])
            modelent.grid(row=3,column=0,sticky="ew")
            frame.columnconfigure(0,weight=1)
            self.api_vars[provider]=(enabled,key,model)
            self._button(frame,"Test connection",lambda pr=provider:self.test_provider(pr)).grid(row=4,column=0,sticky="w",pady=(8,0))
        self._button(p,"Save API settings",self.save_api).pack(anchor="w",pady=8)
        tk.Label(p,text="Keys are stored in your local Windows Buddy settings file. For personal use this is convenient, but not encrypted.",bg=self.colors["bg"],fg=self.colors["muted"],wraplength=650,justify="left").pack(anchor="w",pady=6)

    def _build_personalisation(self):
        p=self.pages["Personalisation"]; self._heading(p,"Personalisation","Make Buddy feel like your desktop.")
        self.theme_var=tk.StringVar(value=self.settings["theme"])
        tk.Label(p,text="Theme",bg=self.colors["bg"],fg=self.colors["fg"]).pack(anchor="w")
        ttk.Combobox(p,textvariable=self.theme_var,values=["dark","light"],state="readonly",width=18).pack(anchor="w",pady=(2,8))
        tk.Label(p,text="Accent colour",bg=self.colors["bg"],fg=self.colors["fg"]).pack(anchor="w")
        row=tk.Frame(p,bg=self.colors["bg"]); row.pack(anchor="w",pady=4)
        for name,color in ACCENTS.items():
            self._button(row,name,lambda c=color:self.set_accent(c)).pack(side="left",padx=(0,5))
        self._button(row,"Custom…",self.pick_accent).pack(side="left")
        self.accent_label=tk.Label(p,text=self.settings["accent"],bg=self.colors["bg"],fg=self.colors["accent"]); self.accent_label.pack(anchor="w",pady=4)
        self.catchphrase_var=tk.BooleanVar(value=self.settings["catchphrase_enabled"])
        tk.Checkbutton(p,text="Use catchphrase in greetings",variable=self.catchphrase_var,bg=self.colors["bg"],fg=self.colors["fg"],selectcolor=self.colors["panel"]).pack(anchor="w",pady=4)
        tk.Label(p,text="Catchphrase",bg=self.colors["bg"],fg=self.colors["fg"]).pack(anchor="w")
        self.catchphrase_entry=tk.Entry(p,bg=self.colors["entry"],fg=self.colors["fg"],insertbackground=self.colors["fg"],width=60)
        self.catchphrase_entry.insert(0,self.settings["catchphrase"]); self.catchphrase_entry.pack(anchor="w",pady=4)
        tk.Label(p,text="Personality",bg=self.colors["bg"],fg=self.colors["fg"]).pack(anchor="w")
        self.personality_var=tk.StringVar(value=self.settings["personality"])
        ttk.Combobox(p,textvariable=self.personality_var,values=["Friendly","Professional","Villager News / chaotic humour","Custom"],state="readonly",width=35).pack(anchor="w",pady=4)
        self.custom_personality=tk.Entry(p,bg=self.colors["entry"],fg=self.colors["fg"],insertbackground=self.colors["fg"],width=60)
        self.custom_personality.insert(0,self.settings.get("custom_personality","")); self.custom_personality.pack(anchor="w",pady=4)
        self._button(p,"Save and apply",self.save_personalisation).pack(anchor="w",pady=8)

    def _build_permissions(self):
        p=self.pages["Permissions"]; self._heading(p,"Permissions","These toggles control Windows Buddy features only.")
        self.permission_vars={}
        options=[("stats_enabled","PC statistics"),("defender_enabled","Read-only Defender checks"),("notifications_enabled","Reminder / popup notifications"),("online_ai_enabled","Optional online AI providers"),("close_to_tray","Minimise to tray when X is clicked")]
        for key,label in options:
            var=tk.BooleanVar(value=self.settings.get(key,True)); self.permission_vars[key]=var
            tk.Checkbutton(p,text=label,variable=var,bg=self.colors["bg"],fg=self.colors["fg"],selectcolor=self.colors["panel"],activebackground=self.colors["bg"]).pack(anchor="w",pady=5)
        tk.Label(p,text="Performance preset",bg=self.colors["bg"],fg=self.colors["fg"]).pack(anchor="w",pady=(12,2))
        self.performance_var=tk.StringVar(value=self.settings.get("performance","Balanced"))
        ttk.Combobox(p,textvariable=self.performance_var,values=["Battery Saver","Balanced","Performance","Custom"],state="readonly",width=24).pack(anchor="w")
        self._button(p,"Save permissions",self.save_permissions).pack(anchor="w",pady=10)
        tk.Label(p,text="No registry, firewall, Windows power plan, or startup settings are changed.",bg=self.colors["bg"],fg=self.colors["muted"]).pack(anchor="w",pady=8)

    def _build_updates(self):
        p=self.pages["Updates"]; self._heading(p,"Updates","Manual release checker. Buddy never silently replaces its own files.")
        tk.Label(p,text=f"Installed version: {VERSION}",bg=self.colors["bg"],fg=self.colors["fg"]).pack(anchor="w",pady=5)
        tk.Label(p,text="Trusted GitHub repository (owner/repository)",bg=self.colors["bg"],fg=self.colors["fg"]).pack(anchor="w")
        self.repo_entry=tk.Entry(p,bg=self.colors["entry"],fg=self.colors["fg"],insertbackground=self.colors["fg"],width=45)
        self.repo_entry.insert(0,self.settings.get("github_repo","")); self.repo_entry.pack(anchor="w",pady=5)
        self.update_result=tk.StringVar(value="Enter your own repository after publishing one.")
        tk.Label(p,textvariable=self.update_result,bg=self.colors["bg"],fg=self.colors["fg"],wraplength=650,justify="left").pack(anchor="w",pady=10)
        self._button(p,"Check latest release",self.check_updates).pack(anchor="w")
        tk.Label(p,text="A release must exist in the configured repository; no repository is assumed.",bg=self.colors["bg"],fg=self.colors["muted"]).pack(anchor="w",pady=8)

    def show_page(self,name):
        for page in self.pages.values(): page.pack_forget()
        self.pages[name].pack(fill="both",expand=True)
        for n,b in self.nav_buttons.items():
            b.configure(bg=self.colors["accent"] if n==name else self.colors["panel"],
                        fg="#07111d" if n==name else self.colors["fg"])
        self.status.set(f"{name} • Windows Buddy {VERSION}")

    def toggle_sidebar(self):
        self.sidebar_collapsed=not self.sidebar_collapsed
        self.sidebar.configure(width=54 if self.sidebar_collapsed else 190)
        for name,b in self.nav_buttons.items():
            b.configure(text=("  "+str(self.nav_names.index(name)+1) if self.sidebar_collapsed else "  "+name))
        self.collapse_btn.configure(text="☰" if self.sidebar_collapsed else "☰  Collapse menu")

    def _append_chat(self, who, text):
        self.chat.configure(state="normal")
        self.chat.insert("end", f"{who}: {text}\n\n", "user" if who=="You" else "buddy")
        self.chat.configure(state="disabled"); self.chat.see("end")

    def _greet(self):
        phrase = (" " + self.settings["catchphrase"]) if self.settings.get("catchphrase_enabled") and self.settings.get("catchphrase") else ""
        self._append_chat("Buddy", "Hey! I'm Windows Buddy. Type 'help' to see what I can do."+phrase)

    def send_chat(self):
        msg=self.chat_input.get().strip()
        if not msg:return
        self.chat_input.delete(0,"end"); self._append_chat("You",msg)
        low=msg.lower()
        if low.startswith("timer "):
            try: sec=parse_delay(msg[6:]); self.start_timer(sec); reply=f"Timer started for {msg[6:].strip()}."
            except ValueError as e: reply=str(e)
        elif low.startswith("remind "):
            try:
                rest=msg[7:].strip()
                delay, _, title=rest.partition(" ")
                sec=parse_delay(delay)
                self._create_reminder(title.strip() or "Reminder",sec); reply=f"Reminder set for {title.strip() or 'Reminder'}."
            except ValueError as e: reply=str(e)
        elif low in {"open notepad","notepad"}:
            reply=self.launch_program("notepad")
        elif low in {"open calculator","calculator","calc"}:
            reply=self.launch_program("calc")
        else:
            reply=command_reply(msg)
        self._append_chat("Buddy",reply)

    def launch_program(self, program):
        try:
            subprocess.Popen([program], shell=False)
            return f"Opening {program.title()}."
        except (OSError, subprocess.SubprocessError) as e:
            return f"Couldn't open {program}: {e}"

    def popup(self,title,body,kind="info",timeout=None):
        if not self.settings.get("notifications_enabled",True):
            self.status.set("Popup suppressed: notifications are disabled.")
            return
        try: MiniPopup(self,title,body,kind,timeout=timeout)
        except tk.TclError: pass

    def start_timer(self,seconds):
        deadline=time.time()+seconds
        self._timer_deadlines.append({"deadline":deadline,"label":f"Timer ({self._duration(seconds)})"})
        self.status.set(f"Timer started • {self._duration(seconds)}")
        self.popup("Timer started",f"Countdown started for {self._duration(seconds)}.","timer",timeout=2200)

    def _duration(self,seconds):
        if seconds>=3600:return f"{seconds//3600}h {(seconds%3600)//60}m"
        if seconds>=60:return f"{seconds//60}m {seconds%60}s" if seconds%60 else f"{seconds//60}m"
        return f"{seconds}s"

    def _create_reminder(self,title,seconds):
        self.reminders.append({"title":title,"due":time.time()+seconds,"done":False,"notified":False})
        write_json(REMINDERS_FILE,self.reminders); self.refresh_reminders()

    def add_reminder(self):
        title=self.reminder_title.get().strip()
        try: seconds=parse_delay(self.reminder_delay.get())
        except ValueError as e: messagebox.showerror("Invalid delay",str(e),parent=self); return
        if not title: messagebox.showerror("Missing title","Enter a reminder title.",parent=self); return
        self._create_reminder(title,seconds)
        self.reminder_title.delete(0,"end"); self.reminder_delay.delete(0,"end")
        self.popup("Reminder saved",f"“{title}” is due in {self._duration(seconds)}.","info",timeout=2200)

    def refresh_reminders(self):
        if not hasattr(self,"reminders_list"): return
        self.reminders_list.delete(0,"end")
        for r in self.reminders:
            due=datetime.fromtimestamp(r["due"]).strftime("%d %b %H:%M")
            mark="✓" if r.get("done") else ("!" if r.get("notified") else "•")
            self.reminders_list.insert("end",f"{mark} {r.get('title','Reminder')} — {due}")

    def complete_reminder(self):
        sel=self.reminders_list.curselection()
        if not sel:return
        try:self.reminders[sel[0]]["done"]=True
        except IndexError:return
        write_json(REMINDERS_FILE,self.reminders); self.refresh_reminders()

    def _tick(self):
        if self._closing:return
        now=time.time()
        keep=[]
        for timer in self._timer_deadlines:
            if timer["deadline"]<=now:
                self.popup("Timer finished",f"{timer['label']} has finished.","timer")
            else: keep.append(timer)
        self._timer_deadlines=keep
        changed=False
        for r in self.reminders:
            if not r.get("done") and not r.get("notified") and r.get("due",now+1)<=now:
                r["notified"]=True; changed=True
                self.popup("Reminder",r.get("title","Reminder"),"info")
        if changed:
            write_json(REMINDERS_FILE,self.reminders); self.refresh_reminders()
        interval={"Battery Saver":3000,"Balanced":1000,"Performance":700,"Custom":1500}.get(self.settings.get("performance"),1000)
        self.after(interval,self._tick)

    def refresh_stats(self):
        if not self.settings.get("stats_enabled",True):
            self._set_text(self.stats_text,"PC statistics are disabled in Permissions."); return
        lines=[f"Operating system: {platform.system()} {platform.release()}",
               f"Machine: {platform.machine()}",f"Python: {platform.python_version()}"]
        try:
            import psutil
            cpu=psutil.cpu_percent(interval=0.25)
            mem=psutil.virtual_memory()
            disk=psutil.disk_usage(str(Path.home().anchor or "/"))
            lines += [f"CPU usage: {cpu:.0f}%",f"RAM: {mem.used/1024**3:.1f} / {mem.total/1024**3:.1f} GB ({mem.percent:.0f}%)",
                      f"Disk: {disk.used/1024**3:.1f} / {disk.total/1024**3:.1f} GB ({disk.percent:.0f}%)"]
        except ImportError:
            lines.append("Install optional psutil for CPU/RAM/disk usage: python -m pip install psutil")
        except Exception as e: lines.append(f"Some statistics could not be read: {e}")
        self._set_text(self.stats_text,"\n".join(lines))

    def check_defender(self):
        if not self.settings.get("defender_enabled",True):
            self._set_text(self.security_text,"Defender status checks are disabled in Permissions."); return
        if os.name!="nt":
            self._set_text(self.security_text,"Defender status checks are only available on Windows. Please open Windows Security directly."); return
        cmd=["powershell","-NoProfile","-NonInteractive","-Command",
             "Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureLastUpdated | ConvertTo-Json -Compress"]
        try:
            result=subprocess.run(cmd,capture_output=True,text=True,timeout=8,check=False)
            if result.returncode!=0 or not result.stdout.strip():
                raise RuntimeError(result.stderr.strip() or "Windows did not return Defender status.")
            data=json.loads(result.stdout)
            lines=[f"Antivirus enabled: {data.get('AntivirusEnabled','Unknown')}",
                   f"Real-time protection: {data.get('RealTimeProtectionEnabled','Unknown')}",
                   f"Signature last updated: {data.get('AntivirusSignatureLastUpdated','Unknown')}"]
            self._set_text(self.security_text,"\n".join(lines))
            if data.get("AntivirusEnabled") is False or data.get("RealTimeProtectionEnabled") is False:
                self.popup("Security warning","Windows Defender reports that a protection setting is disabled. Check Windows Security.","security")
        except Exception as e:
            self._set_text(self.security_text,f"Couldn't read Defender status: {e}\nOpen the Windows Security app to verify protection status.")
            self.popup("Security status unavailable","Buddy couldn't verify Defender status. Open Windows Security to check manually.","warning")

    def _set_text(self,widget,text):
        widget.configure(state="normal"); widget.delete("1.0","end"); widget.insert("1.0",text); widget.configure(state="disabled")

    def save_api(self):
        for pr,(enabled,key,model) in self.api_vars.items():
            self.settings[pr+"_enabled"]=enabled.get(); self.settings[pr+"_key"]=key.get().strip(); self.settings[pr+"_model"]=model.get().strip()
        self._save_settings(); self.popup("Settings saved","API settings saved locally.","info",timeout=2000)

    def test_provider(self,provider):
        if not self.settings.get("online_ai_enabled",True):
            messagebox.showinfo("Provider disabled","Enable optional online AI in Permissions first.",parent=self); return
        self.save_api()
        enabled=self.settings.get(provider+"_enabled"); key=self.settings.get(provider+"_key")
        if not enabled or not key:
            messagebox.showwarning("Missing setup",f"Enable {provider.title()} and enter an API key first.",parent=self); return
        def worker():
            try:
                if provider=="openai":
                    req=urllib.request.Request("https://api.openai.com/v1/models",headers={"Authorization":"Bearer "+key})
                else:
                    req=urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models?key={key}")
                with urllib.request.urlopen(req,timeout=10) as response: code=response.status
                result=f"{provider.title()} connection succeeded (HTTP {code})."
            except Exception as e: result=f"{provider.title()} connection failed: {type(e).__name__}: {e}"
            self.after(0,lambda:messagebox.showinfo("Connection test",result,parent=self))
        threading.Thread(target=worker,daemon=True).start()

    def save_personalisation(self):
        self.settings["theme"]=self.theme_var.get()
        self.settings["catchphrase_enabled"]=self.catchphrase_var.get()
        self.settings["catchphrase"]=self.catchphrase_entry.get().strip()
        self.settings["personality"]=self.personality_var.get()
        self.settings["custom_personality"]=self.custom_personality.get().strip()
        self._save_settings()
        messagebox.showinfo("Saved","Personalisation saved. Some visual changes apply fully after restarting Buddy.",parent=self)

    def set_accent(self,color):
        self.settings["accent"]=color; self.colors["accent"]=color; self.accent_label.configure(text=color,fg=color); self._save_settings()

    def pick_accent(self):
        color=colorchooser.askcolor(color=self.settings.get("accent"),parent=self)[1]
        if color:self.set_accent(color)

    def save_permissions(self):
        for k,v in self.permission_vars.items(): self.settings[k]=v.get()
        self.settings["performance"]=self.performance_var.get()
        self._save_settings(); self.popup("Permissions saved","Windows Buddy preferences have been saved.","info",timeout=2000)

    def check_updates(self):
        repo=self.repo_entry.get().strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",repo):
            self.update_result.set("Enter a valid owner/repository value first."); return
        self.settings["github_repo"]=repo; self._save_settings()
        self.update_result.set("Checking GitHub…")
        def worker():
            try:
                req=urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                    headers={"Accept":"application/vnd.github+json","User-Agent":"Windows-Buddy"})
                with urllib.request.urlopen(req,timeout=12) as response: data=json.loads(response.read().decode("utf-8"))
                tag=data.get("tag_name","")
                url=data.get("html_url","")
                latest=parse_version(tag); current=parse_version(VERSION)
                if latest and current and latest>current: msg=f"Update available: {tag}\\n{url}"
                elif latest and current: msg=f"Latest release: {tag}. "+("You're up to date." if latest<=current else "")+f"\\n{url}"
                else: msg=f"Latest release tag: {tag or '(none)'}\\nRelease page: {url}"
            except urllib.error.HTTPError as e:
                msg="No published release found (404)." if e.code==404 else f"GitHub returned HTTP {e.code}."
            except Exception as e: msg=f"Update check failed: {type(e).__name__}: {e}"
            self.after(0,lambda:self.update_result.set(msg))
        threading.Thread(target=worker,daemon=True).start()

    def _save_settings(self):
        try: write_json(SETTINGS_FILE,self.settings)
        except OSError as e: self.status.set(f"Could not save settings: {e}")

    def _setup_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw
            image=Image.new("RGB",(64,64),(16,24,39))
            draw=ImageDraw.Draw(image); draw.rectangle((8,8,56,56),outline=self.settings.get("accent","#35c9ff"),width=4)
            draw.text((18,18),"WB",fill=self.settings.get("accent","#35c9ff"))
            menu=pystray.Menu(
                pystray.MenuItem("Open Windows Buddy",lambda icon,item:self.after(0,self.restore_from_tray),default=True),
                pystray.MenuItem("Show quick alert",lambda icon,item:self.after(0,lambda:self.popup("Buddy alert","Windows Buddy is running in the background.","info"))),
                pystray.MenuItem("Quit",lambda icon,item:self.after(0,self.quit_app)))
            self.tray_icon=pystray.Icon("windows_buddy",image,APP_NAME,menu)
            self._tray_available=True
            self.tray_thread=threading.Thread(target=self.tray_icon.run,daemon=True); self.tray_thread.start()
            self.status.set("Ready • System tray available")
        except Exception:
            self._tray_available=False
            self.status.set("Ready • Install pystray and Pillow for system tray support")

    def on_window_close(self):
        if self.settings.get("close_to_tray",True) and self._tray_available:
            self.withdraw()
            self.status.set("Running in system tray • Right-click the tray icon to open or quit")
        elif self.settings.get("close_to_tray",True):
            choice=messagebox.askyesnocancel("Windows Buddy","System tray support is unavailable.\\n\\nYes: quit Buddy\\nNo: keep the window open\\nCancel: hide window for this session",parent=self)
            if choice is True:self.quit_app()
            elif choice is None:self.withdraw()
        else:
            self.quit_app()

    def restore_from_tray(self):
        self.deiconify(); self.state("normal"); self.lift(); self.focus_force()

    def quit_app(self):
        self._closing=True
        try:
            if self.tray_icon:self.tray_icon.stop()
        except Exception: pass
        for popup in list(self.popups):
            try:popup.destroy()
            except tk.TclError:pass
        self.destroy()

def main():
    app=WindowsBuddy()
    app.mainloop()

if __name__=="__main__":
    main()
