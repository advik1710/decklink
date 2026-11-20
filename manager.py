#!/usr/bin/env python3
"""Small Tk desktop app for managing DeckLink shortcuts and its local host."""
import json
import os
import secrets
import socket
import subprocess
import sys
import uuid
import webbrowser
if os.name == "nt":
    import winreg
else:
    winreg = None
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
PORT = 8765


def read_config():
    with CONFIG_PATH.open("r", encoding="utf-8-sig") as stream:
        config = json.load(stream)
    config.setdefault("name", "DeckLink")
    config.pop("token", None)
    config.setdefault("actions", [])
    if not isinstance(config.get("profiles"), list) or not config["profiles"]:
        config["profiles"] = [{"id": "default", "name": "Default", "pages": [{"id": "page-1", "name": "Page 1", "actions": config["actions"]}]}]
    config.setdefault("activeProfileId", config["profiles"][0].get("id", "default"))
    active = next((p for p in config["profiles"] if p.get("id") == config["activeProfileId"]), config["profiles"][0])
    config["activeProfileId"] = active.setdefault("id", "default")
    if not active.get("pages"):
        active["pages"] = [{"id": "page-1", "name": "Page 1", "actions": config["actions"]}]
    config["actions"] = [a for page in active["pages"] for a in page.get("actions", [])]
    return config


def write_config(config):
    config.pop("token", None)
    temp_path = CONFIG_PATH.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(str(temp_path), str(CONFIG_PATH))


def local_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(1.5)
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


class Manager:
    def __init__(self, root):
        self.root = root
        self.root.title("DeckLink Desktop Manager")
        self.root.geometry("780x610")
        self.root.minsize(700, 540)
        self.config = read_config()
        self.host_process = None
        self.selected_id = None
        self._build()
        self.name_var.set(self.config.get("name", "DeckLink"))
        self._refresh_list()
        self._refresh_profiles()
        self._refresh_host_status()

    def _build(self):
        style = ttk.Style()
        try:
            style.theme_use("vista" if os.name == "nt" else "clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Segoe UI", 17, "bold"))
        style.configure("Hint.TLabel", foreground="#626b75")
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        top = ttk.Frame(outer); top.pack(fill="x")
        ttk.Label(top, text="DeckLink", style="Title.TLabel").pack(side="left")
        ttk.Label(top, text="Desktop Manager", style="Hint.TLabel").pack(side="left", padx=(10, 0), pady=(8, 0))
        tools = ttk.Frame(outer); tools.pack(fill="x", pady=(8, 0))
        ttk.Label(tools, text="Profile").pack(side="left")
        self.profile_var = tk.StringVar()
        self.profile_box = ttk.Combobox(tools, textvariable=self.profile_var, state="readonly", width=20)
        self.profile_box.pack(side="left", padx=6); self.profile_box.bind("<<ComboboxSelected>>", self.select_profile)
        ttk.Button(tools, text="New profile", command=self.new_profile).pack(side="left", padx=3)
        ttk.Button(tools, text="Delete profile", command=self.delete_profile).pack(side="left", padx=3)
        ttk.Button(tools, text="Export layout", command=self.export_layout).pack(side="right", padx=3)
        ttk.Button(tools, text="Import layout", command=self.import_layout).pack(side="right", padx=3)
        name_row = ttk.Frame(outer); name_row.pack(fill="x", pady=(15, 12))
        ttk.Label(name_row, text="Dashboard name").pack(side="left")
        self.name_var = tk.StringVar()
        name_entry = ttk.Entry(name_row, textvariable=self.name_var, width=34)
        name_entry.pack(side="left", padx=9)
        name_entry.bind("<FocusOut>", lambda _e: self.save_name())
        ttk.Label(name_row, text="Changes sync to the dashboard while the host is running.", style="Hint.TLabel").pack(side="left", padx=4)

        body = ttk.Frame(outer); body.pack(fill="both", expand=True)
        left = ttk.LabelFrame(body, text="Shortcuts", padding=10); left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right = ttk.LabelFrame(body, text="Button details", padding=10); right.pack(side="left", fill="both", expand=True, padx=(10, 0))

        list_frame = ttk.Frame(left); list_frame.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(list_frame, activestyle="none", exportselection=False, font=("Segoe UI", 10), height=17)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        row = ttk.Frame(left); row.pack(fill="x", pady=(9, 0))
        ttk.Button(row, text="Add new", command=self.clear_form).pack(side="left")
        ttk.Button(row, text="Remove", command=self.remove_action).pack(side="left", padx=5)
        ttk.Button(row, text="Move up", command=lambda: self.move_action(-1)).pack(side="left", padx=5)
        ttk.Button(row, text="Move down", command=lambda: self.move_action(1)).pack(side="left")

        self.label_var = tk.StringVar(); self.icon_var = tk.StringVar(value="•")
        self.type_var = tk.StringVar(value="url"); self.target_var = tk.StringVar()
        self._field(right, "Button label", self.label_var, 0)
        self._field(right, "Icon / symbol", self.icon_var, 1)
        ttk.Label(right, text="Action type").grid(row=2, column=0, sticky="w", pady=5)
        self.type_box = ttk.Combobox(right, textvariable=self.type_var, values=("url", "app"), state="readonly", width=30)
        self.type_box.grid(row=2, column=1, sticky="ew", pady=5); self.type_box.bind("<<ComboboxSelected>>", self.type_changed)
        self.target_label = ttk.Label(right, text="Website URL")
        self.target_label.grid(row=3, column=0, sticky="w", pady=5)
        target_wrap = ttk.Frame(right); target_wrap.grid(row=3, column=1, sticky="ew", pady=5)
        self.target_entry = ttk.Entry(target_wrap, textvariable=self.target_var)
        self.target_entry.pack(side="left", fill="x", expand=True)
        self.browse_button = ttk.Button(target_wrap, text="Browse…", command=self.browse_app)
        self.browse_button.pack(side="left", padx=(5, 0))
        self.args_label = ttk.Label(right, text="App arguments")
        self.args_label.grid(row=4, column=0, sticky="nw", pady=5)
        self.args_text = tk.Text(right, height=4, width=30, wrap="word", font=("Segoe UI", 9))
        self.args_text.grid(row=4, column=1, sticky="ew", pady=5)
        ttk.Label(right, text="One fixed argument per line. The browser cannot change these.", style="Hint.TLabel", wraplength=310).grid(row=5, column=1, sticky="w")
        ttk.Button(right, text="Save button", command=self.save_action).grid(row=6, column=1, sticky="e", pady=(14, 4))
        right.columnconfigure(1, weight=1)
        self.type_changed()

        bottom = ttk.LabelFrame(outer, text="Host connection", padding=9); bottom.pack(fill="x", pady=(14, 0))
        self.status_var = tk.StringVar(value="Host stopped")
        ttk.Label(bottom, textvariable=self.status_var).grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Button(bottom, text="Start host", command=self.start_host).grid(row=0, column=1, padx=3)
        ttk.Button(bottom, text="Stop host", command=self.stop_host).grid(row=0, column=2, padx=3)
        ttk.Button(bottom, text="Open dashboard", command=self.open_dashboard).grid(row=0, column=3, padx=3)
        ttk.Button(bottom, text="Copy PC address", command=self.copy_link).grid(row=0, column=4, padx=3)
        self.link_var = tk.StringVar(value="Start host to show this PC's address and six-digit PIN.")
        ttk.Entry(bottom, textvariable=self.link_var, state="readonly").grid(row=1, column=0, columnspan=5, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(0, weight=1)
        self.startup_var = tk.BooleanVar(value=self._startup_enabled())
        ttk.Checkbutton(bottom, text="Start host when I sign in", variable=self.startup_var, command=self.set_startup).grid(row=2, column=0, sticky="w", pady=(7, 0))
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _field(self, parent, label, variable, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=5)

    def save_name(self):
        value = self.name_var.get().strip() or "DeckLink"
        self.name_var.set(value); self.config["name"] = value; self._save()

    def _active_profile(self):
        return next((p for p in self.config.get("profiles", []) if p.get("id") == self.config.get("activeProfileId")), self.config["profiles"][0])

    def _refresh_profiles(self):
        names = [p.get("name", "Profile") for p in self.config.get("profiles", [])]
        self.profile_box["values"] = names
        active = self._active_profile()
        self.profile_var.set(active.get("name", "Default"))

    def _store_active_actions(self):
        profile = self._active_profile()
        if not profile.get("pages"):
            profile["pages"] = [{"id": "page-1", "name": "Page 1", "actions": []}]
        profile["pages"][0]["actions"] = self.config.get("actions", [])

    def select_profile(self, _event=None):
        chosen = next((p for p in self.config["profiles"] if p.get("name") == self.profile_var.get()), None)
        if not chosen:
            return
        self._store_active_actions(); self.config["activeProfileId"] = chosen["id"]
        self.config["actions"] = chosen["pages"][0].get("actions", [])
        self.selected_id = None; self._save(); self._refresh_list(); self._refresh_profiles()

    def new_profile(self):
        name = simpledialog.askstring("New profile", "Profile name:", parent=self.root)
        if not name or not name.strip():
            return
        self._store_active_actions()
        profile = {"id": uuid.uuid4().hex[:12], "name": name.strip(), "pages": [{"id": "page-1", "name": "Page 1", "actions": []}], "preferences": {}}
        self.config["profiles"].append(profile); self.config["activeProfileId"] = profile["id"]; self.config["actions"] = []
        self.selected_id = None; self._save(); self._refresh_list(); self._refresh_profiles()

    def delete_profile(self):
        if len(self.config["profiles"]) < 2:
            messagebox.showinfo("Keep one profile", "DeckLink needs at least one profile.", parent=self.root); return
        profile = self._active_profile()
        if not messagebox.askyesno("Delete profile", "Delete '{}' and its shortcuts?".format(profile["name"]), parent=self.root):
            return
        self.config["profiles"] = [p for p in self.config["profiles"] if p["id"] != profile["id"]]
        self.config["activeProfileId"] = self.config["profiles"][0]["id"]
        self.config["actions"] = self._active_profile()["pages"][0].get("actions", [])
        self._save(); self._refresh_profiles(); self._refresh_list()

    def export_layout(self):
        self._store_active_actions()
        path = filedialog.asksaveasfilename(parent=self.root, title="Export DeckLink layout", defaultextension=".json", filetypes=(("JSON layout", "*.json"),))
        if not path: return
        data = {"format": "decklink-layout", "schemaVersion": 1, "profiles": self.config["profiles"], "activeProfileId": self.config["activeProfileId"]}
        try:
            Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            messagebox.showinfo("Layout exported", "Your profiles and shortcuts were exported. Pairing tokens are not included.", parent=self.root)
        except OSError as err: messagebox.showerror("Export failed", str(err), parent=self.root)

    def import_layout(self):
        path = filedialog.askopenfilename(parent=self.root, title="Import DeckLink layout", filetypes=(("JSON layout", "*.json"),))
        if not path: return
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            profiles = data.get("profiles")
            if data.get("format") != "decklink-layout" or data.get("schemaVersion") != 1 or not isinstance(profiles, list) or not profiles:
                raise ValueError("This file is not a supported DeckLink layout.")
            for profile in profiles:
                if not isinstance(profile, dict) or not profile.get("id") or not isinstance(profile.get("pages"), list):
                    raise ValueError("A profile is missing its ID or pages.")
                for page in profile["pages"]:
                    if not isinstance(page, dict) or not isinstance(page.get("actions", []), list): raise ValueError("A profile page has invalid shortcuts.")
            if not messagebox.askyesno("Replace layout?", "Import will replace all current profiles and shortcuts. Continue?", parent=self.root): return
            self.config["profiles"] = profiles; self.config["activeProfileId"] = data.get("activeProfileId", profiles[0]["id"])
            self.config["activeProfileId"] = next((p["id"] for p in profiles if p["id"] == self.config["activeProfileId"]), profiles[0]["id"])
            self.config["actions"] = [a for page in self._active_profile()["pages"] for a in page.get("actions", [])]
            self._save(); self._refresh_profiles(); self._refresh_list()
        except (OSError, ValueError, json.JSONDecodeError, KeyError) as err: messagebox.showerror("Import failed", str(err), parent=self.root)

    def _startup_enabled(self):
        if os.name != "nt": return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                winreg.QueryValueEx(key, "DeckLink")
                return True
        except OSError: return False

    def set_startup(self):
        if os.name != "nt":
            messagebox.showinfo("Windows only", "Sign-in startup is available on Windows.", parent=self.root); self.startup_var.set(False); return
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
                if self.startup_var.get():
                    python = sys.executable.replace("python.exe", "pythonw.exe")
                    winreg.SetValueEx(key, "DeckLink", 0, winreg.REG_SZ, '"{}" "{}" --no-open'.format(python, ROOT / "host.py"))
                else:
                    try: winreg.DeleteValue(key, "DeckLink")
                    except FileNotFoundError: pass
        except OSError as err:
            self.startup_var.set(not self.startup_var.get()); messagebox.showerror("Startup setting failed", str(err), parent=self.root)

    def type_changed(self, _event=None):
        is_app = self.type_var.get() == "app"
        self.target_label.configure(text="App executable" if is_app else "Website URL")
        self.browse_button.configure(state="normal" if is_app else "disabled")
        self.args_label.configure(state="normal" if is_app else "disabled")
        self.args_text.configure(state="normal" if is_app else "disabled")

    def browse_app(self):
        filename = filedialog.askopenfilename(title="Choose an app to launch", filetypes=(("Applications", "*.exe"), ("All files", "*.*")))
        if filename:
            self.target_var.set(filename)

    def _refresh_list(self, select_id=None):
        self.listbox.delete(0, "end")
        selected_index = None
        for index, action in enumerate(self.config.get("actions", [])):
            text = "{}  ·  {}".format(action.get("label", "Untitled"), "Website" if action.get("type") == "url" else "App")
            self.listbox.insert("end", text)
            if action.get("id") == (select_id or self.selected_id):
                selected_index = index
        if selected_index is not None:
            self.listbox.selection_set(selected_index); self.listbox.activate(selected_index); self.listbox.see(selected_index)
        if not self.config.get("actions"):
            self.selected_id = None

    def on_select(self, _event=None):
        selected = self.listbox.curselection()
        if not selected:
            return
        action = self.config["actions"][selected[0]]
        self.selected_id = action.get("id")
        self.label_var.set(action.get("label", "")); self.icon_var.set(action.get("icon", "•"))
        self.type_var.set(action.get("type", "url")); self.type_changed()
        self.target_var.set(action.get("url", action.get("executable", "")))
        self.args_text.configure(state="normal"); self.args_text.delete("1.0", "end")
        self.args_text.insert("1.0", "\n".join(action.get("args", [])))
        self.type_changed()

    def clear_form(self):
        self.selected_id = None
        self.listbox.selection_clear(0, "end")
        self.label_var.set(""); self.icon_var.set("•"); self.type_var.set("url"); self.target_var.set("")
        self.args_text.configure(state="normal"); self.args_text.delete("1.0", "end"); self.type_changed()

    def save_action(self):
        label = self.label_var.get().strip(); kind = self.type_var.get(); target = self.target_var.get().strip()
        if not label:
            messagebox.showerror("Button needs a name", "Enter a label for this shortcut.", parent=self.root); return
        if kind == "url" and not target.lower().startswith(("http://", "https://")):
            messagebox.showerror("Invalid website", "Use a full http:// or https:// address.", parent=self.root); return
        if kind == "app" and not target:
            messagebox.showerror("Choose an app", "Enter an executable or use Browse to choose an app.", parent=self.root); return
        args = [line for line in self.args_text.get("1.0", "end").splitlines() if line] if kind == "app" else []
        action = {"id": self.selected_id or uuid.uuid4().hex[:12], "label": label,
                  "icon": self.icon_var.get().strip() or "•", "type": kind}
        if kind == "url": action["url"] = target
        else: action["executable"] = target; action["args"] = args
        actions = self.config.setdefault("actions", [])
        index = next((i for i, item in enumerate(actions) if item.get("id") == self.selected_id), None)
        if index is None: actions.append(action)
        else: actions[index] = action
        self.selected_id = action["id"]
        self._save(); self._refresh_list(self.selected_id)

    def remove_action(self):
        if not self.selected_id:
            messagebox.showinfo("Select a shortcut", "Select a shortcut to remove.", parent=self.root); return
        self.config["actions"] = [a for a in self.config.get("actions", []) if a.get("id") != self.selected_id]
        self.clear_form(); self._save(); self._refresh_list()

    def move_action(self, direction):
        selected = self.listbox.curselection()
        if not selected: return
        index = selected[0]; target = index + direction; actions = self.config["actions"]
        if target < 0 or target >= len(actions): return
        actions[index], actions[target] = actions[target], actions[index]
        self.selected_id = actions[target].get("id")
        self._save(); self._refresh_list(self.selected_id)

    def _save(self):
        try:
            self._store_active_actions()
            write_config(self.config)
            self.status_var.set("Saved · shortcut changes sync to the dashboard")
        except OSError as err:
            messagebox.showerror("Could not save", str(err), parent=self.root)

    def _pairing_link(self):
        return "http://{}:{}".format(local_ip(), PORT)

    def _connection_text(self):
        try: pin = (ROOT / ".decklink.pin").read_text(encoding="ascii").strip()
        except OSError: pin = "------"
        return "PC address: {} · PIN: {}".format(self._pairing_link(), pin)

    def start_host(self):
        if self.host_process and self.host_process.poll() is None:
            self.status_var.set("Host is running")
            self.link_var.set(self._connection_text())
            return
        try:
            probe = socket.create_connection(("127.0.0.1", PORT), timeout=0.35)
            probe.close()
            self.status_var.set("Host is already running")
            self.link_var.set(self._connection_text())
            self.open_dashboard()
            return
        except OSError:
            pass
        flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0
        try:
            self.host_process = subprocess.Popen([sys.executable, str(ROOT / "host.py")], cwd=str(ROOT), creationflags=flags)
            self.link_var.set("PC address: {} · PIN: generating…".format(self._pairing_link()))
            self.status_var.set("Host starting · PIN refreshes on every start")
            self.root.after(900, self.open_dashboard)
        except OSError as err:
            messagebox.showerror("Could not start host", str(err), parent=self.root)

    def stop_host(self):
        if not self.host_process or self.host_process.poll() is not None:
            self.status_var.set("No host started by this manager is running"); return
        host_pid = self.host_process.pid
        self.host_process.terminate()
        try:
            self.host_process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
        self.host_process = None
        try: (ROOT / ".decklink.pin").unlink()
        except OSError: pass
        self._clear_pid_file(host_pid)
        self.status_var.set("Host stopped")

    def _clear_pid_file(self, host_pid):
        pid_path = ROOT / ".decklink.pid"
        try:
            if pid_path.read_text(encoding="ascii").strip() == str(host_pid):
                pid_path.unlink()
        except (OSError, ValueError):
            pass

    def _refresh_host_status(self):
        if self.host_process and self.host_process.poll() is not None:
            self._clear_pid_file(self.host_process.pid)
            self.host_process = None; self.status_var.set("Host stopped")
        if self.host_process and self.host_process.poll() is None:
            try:
                self.link_var.set(self._connection_text())
            except OSError:
                pass
        self.root.after(1500, self._refresh_host_status)

    def open_dashboard(self):
        webbrowser.open(self._pairing_link())

    def copy_link(self):
        link = self._pairing_link()
        self.root.clipboard_clear(); self.root.clipboard_append(link); self.status_var.set("PC address copied")

    def close(self):
        self.save_name()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    Manager(root)
    root.mainloop()
