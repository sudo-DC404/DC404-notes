#!/usr/bin/env python3
# DC404 Notes – clean build
import json
import os
import random
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

APP_NAME = "DC404 Notes"
STATE_FILE = os.path.join(os.path.expanduser("~"), ".dc404notes_state.json")

TEMPLATES = {
    "Recon / Scoping": """# Recon & Scoping
Target(s): 
Scope:
Out of scope:
Contacts:
Rules of engagement:

## Passive Recon
- WHOIS:
- DNS:
- ASN / IP ranges:

## Active Recon
- Port scan:
- Services / versions:
- Web tech:

## Risks & Constraints
- Rate limits:
- Time windows:
- Data handling:
""",
    "Web App": """# Web App Notes
URL:
Auth:
Roles:

## Endpoints
-

## Findings
- [ ] IDOR: 
- [ ] XSS:
- [ ] CSRF:
- [ ] SQLi:
- [ ] SSRF:
- [ ] RCE:

Proof:
Impact:
Remediation:
""",
    "Engagement Summary": """# Engagement Summary
Client:
Dates:
Team:

## High Risk
-

## Medium
-

## Low
-

Recommendations:
Next Steps:
"""
}

THEMES = {
    "Dark": {
        "bg": "#0f1115",
        "fg": "#e6e6e6",
        "accent": "#7aa2f7",
        "text_bg": "#0f1115",
        "insert": "#7aa2f7",
        "sel_bg": "#1f2335",
        "glitch_colors": ["#ff2d55", "#00e5ff", "#ffd400"]
    },
    "Light": {
        "bg": "#fafafa",
        "fg": "#0f1115",
        "accent": "#3a5ccc",
        "text_bg": "#ffffff",
        "insert": "#3a5ccc",
        "sel_bg": "#e7ecff",
        "glitch_colors": ["#ff4d4f", "#36cfc9", "#fadb14"]
    },
    "Dark Glitch": {
        "bg": "#05060a",
        "fg": "#d7dae0",
        "accent": "#ff2d55",
        "text_bg": "#05060a",
        "insert": "#ff2d55",
        "sel_bg": "#141623",
        "glitch_colors": ["#ff2d55", "#06d6a0", "#00e5ff", "#ffd400"]
    }
}

def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass

class DC404NotesApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.file_path = None
        self.find_idx = "1.0"
        self._glitch_job = None

        # persistent state
        self.state = load_state()
        geom = self.state.get("geometry")
        if geom:
            self.root.geometry(geom)

        # build UI
        self._build_ui()
        # apply theme
        self._apply_theme(self.state.get("theme", "Dark"))

        # restore content if last open file tracked
        last_file = self.state.get("last_file")
        if last_file and os.path.exists(last_file):
            try:
                self._open_path(last_file)
            except Exception:
                pass

        # glitch toggle
        if self.state.get("glitch_on", False):
            self.glitch_var.set(1)
            self._start_glitch()

    def _build_ui(self):
        # Menu
        menubar = tk.Menu(self.root)  # DO NOT pass any non-integer/boolean junk
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New", command=self._new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Open…", command=self._open_dialog, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self._save, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As…", command=self._save_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Find…", command=self._find, accelerator="Ctrl+F")
        edit_menu.add_command(label="Find Next", command=lambda: self._find(next_only=True), accelerator="F3")
        edit_menu.add_separator()
        self.wrap_var = tk.IntVar(value=1 if self.state.get("wrap", True) else 0)
        edit_menu.add_checkbutton(label="Wrap Lines", variable=self.wrap_var, command=self._toggle_wrap)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        insert_menu = tk.Menu(menubar, tearoff=0)
        for name in TEMPLATES:
            insert_menu.add_command(label=f"Insert: {name}", command=lambda n=name: self._insert_template(n))
        menubar.add_cascade(label="Templates", menu=insert_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        theme_menu = tk.Menu(view_menu, tearoff=0)
        self.theme_var = tk.StringVar(value=self.state.get("theme", "Dark"))
        for t in THEMES.keys():
            theme_menu.add_radiobutton(label=t, value=t, variable=self.theme_var, command=self._on_theme_change)
        view_menu.add_cascade(label="Theme", menu=theme_menu)

        self.glitch_var = tk.IntVar(value=0)
        view_menu.add_checkbutton(label="Glitch Overlay", variable=self.glitch_var, command=self._toggle_glitch)
        menubar.add_cascade(label="View", menu=view_menu)

        # Root layout: main frame
        self.wrap = tk.Frame(self.root, bd=0, highlightthickness=0)
        self.wrap.pack(fill="both", expand=True)

        # Text + scrollbar
        self.text = tk.Text(self.wrap, wrap="word", undo=True, tabs=("1c"))
        self.text.pack(side="left", fill="both", expand=True)
        sb = tk.Scrollbar(self.wrap, command=self.text.yview)
        sb.pack(side="right", fill="y")
        self.text.config(yscrollcommand=sb.set)

        # Overlay frame for glitch
        self.overlay_wrap = tk.Frame(self.wrap, bd=0, highlightthickness=0)
        self.overlay_wrap.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.overlay_wrap.lower(self.text)

        # Glitch canvas (covers whole client area)
        self.glitch_canvas = tk.Canvas(self.overlay_wrap, bd=0, highlightthickness=0)
        self.glitch_canvas.pack(fill="both", expand=True)

        # key bindings
        self.root.bind("<Control-n>", lambda e: self._new_file())
        self.root.bind("<Control-o>", lambda e: self._open_dialog())
        self.root.bind("<Control-s>", lambda e: self._save())
        self.root.bind("<Control-S>", lambda e: self._save_as())
        self.root.bind("<Control-f>", lambda e: self._find())
        self.root.bind("<F3>", lambda e: self._find(next_only=True))
        self.root.bind("<Control-q>", lambda e: self._on_close())

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # initial wrap
        self._toggle_wrap()

    # ---------- File ops ----------
    def _set_title(self):
        name = os.path.basename(self.file_path) if self.file_path else "Untitled"
        self.root.title(f"{APP_NAME} – {name}")

    def _new_file(self):
        if not self._maybe_save_changes():
            return
        self.text.delete("1.0", "end-1c")
        self.file_path = None
        self._set_title()

    def _open_dialog(self):
        path = filedialog.askopenfilename(
            title="Open Note",
            filetypes=[("Text", "*.txt *.md *.note *.log"), ("All files", "*.*")]
        )
        if path:
            self._open_path(path)

    def _open_path(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
            self.text.delete("1.0", "end-1c")
            self.text.insert("1.0", data)
            self.file_path = path
            self._set_title()
            self.state["last_file"] = path
            save_state(self.state)
        except Exception as e:
            messagebox.showerror("Open failed", str(e))

    def _save(self):
        if not self.file_path:
            return self._save_as()
        try:
            txt = self.text.get("1.0", "end-1c")
            with open(self.file_path, "w", encoding="utf-8") as f:
                f.write(txt)
            self._set_title()
        except Exception as e:
            messagebox.showerror("Save failed", str(e))

    def _save_as(self):
        path = filedialog.asksaveasfilename(
            title="Save Note As",
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("Text", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        self.file_path = path
        self._save()
        self.state["last_file"] = path
        save_state(self.state)

    def _maybe_save_changes(self):
        # Simple heuristic – always prompt (or could track a modified flag)
        if messagebox.askyesno("Save", "Save changes first?"):
            self._save()
        return True

    # ---------- Edit / Find ----------
    def _find(self, next_only=False):
        # Ask for query (simple prompt)
        top = tk.Toplevel(self.root)
        top.title("Find")
        top.transient(self.root)
        tk.Label(top, text="Find:").pack(side="left", padx=6, pady=6)
        entry = tk.Entry(top, width=32)
        entry.pack(side="left", padx=6, pady=6)
        entry.focus_set()

        def do_find(next_only=next_only):
            query = entry.get()
            if not query:
                return
            start = self.find_idx if next_only else "1.0"
            idx = self.text.search(query, start, tk.END, nocase=True)
            if idx:
                end = f"{idx}+{len(query)}c"
                self.text.tag_remove("sel", "1.0", tk.END)
                self.text.tag_add("sel", idx, end)
                self.text.mark_set(tk.INSERT, end)
                self.text.see(idx)
                # next start from after current match
                self.find_idx = end
            else:
                messagebox.showinfo("Find", "Not found.")
        tk.Button(top, text="Find", command=lambda: do_find(False)).pack(side="left", padx=6, pady=6)
        tk.Button(top, text="Find Next", command=lambda: do_find(True)).pack(side="left", padx=6, pady=6)

    def _toggle_wrap(self):
        wrap = "word" if self.wrap_var.get() else "none"
        self.text.config(wrap=wrap)
        self.state["wrap"] = (wrap == "word")
        save_state(self.state)

    def _insert_template(self, name):
        self.text.insert(tk.INSERT, TEMPLATES.get(name, ""))

    # ---------- Theme ----------
    def _on_theme_change(self):
        self._apply_theme(self.theme_var.get())

    def _apply_theme(self, theme_name: str):
        cfg = THEMES.get(theme_name, THEMES["Dark"])
        self.root.configure(bg=cfg["bg"])
        self.wrap.configure(bg=cfg["bg"])
        self.text.configure(
            bg=cfg["text_bg"],
            fg=cfg["fg"],
            insertbackground=cfg["insert"],
            selectbackground=cfg["sel_bg"],
            selectforeground=cfg["fg"],
        )
        self.overlay_wrap.configure(bg=cfg["bg"])
        self.glitch_canvas.configure(bg=cfg["bg"])
        self.state["theme"] = theme_name
        save_state(self.state)

    # ---------- Glitch Overlay ----------
    def _toggle_glitch(self):
        on = bool(self.glitch_var.get())
        self.state["glitch_on"] = on
        save_state(self.state)
        if on:
            self._start_glitch()
        else:
            self._stop_glitch()

    def _start_glitch(self):
        # Lift overlay and animate
        self.overlay_wrap.lift()
        self._schedule_glitch()

    def _stop_glitch(self):
        if self._glitch_job is not None:
            try:
                self.root.after_cancel(self._glitch_job)
            except Exception:
                pass
            self._glitch_job = None
        # Clear and lower overlay
        self.glitch_canvas.delete("all")
        self.overlay_wrap.lower(self.text)

    def _schedule_glitch(self):
        # "Louder" glitch: random scanlines + blocks with additive feel
        self._glitch_tick()
        # faster rate for louder vibe
        self._glitch_job = self.root.after(80, self._schedule_glitch)

    def _glitch_tick(self):
        theme = THEMES.get(self.state.get("theme", "Dark"), THEMES["Dark"])
        colors = theme["glitch_colors"]
        w = self.glitch_canvas.winfo_width()
        h = self.glitch_canvas.winfo_height()
        if w <= 2 or h <= 2:
            # Canvas not realized yet; try again shortly
            return

        self.glitch_canvas.delete("all")

        # scanlines
        for _ in range(random.randint(6, 12)):
            y = random.randint(0, max(1, h - 2))
            height = random.randint(1, 3)
            x0 = 0
            x1 = w
            color = random.choice(colors)
            # draw two parallax lines for louder effect
            self.glitch_canvas.create_rectangle(x0, y, x1, y + height, fill=color, width=0, stipple="gray50")
            if random.random() < 0.6:
                offset = random.randint(-6, 6)
                self.glitch_canvas.create_rectangle(x0 + offset, y + 1, x1 + offset, y + height + 1, fill=color, width=0, stipple="gray25")

        # blocks
        for _ in range(random.randint(2, 5)):
            bw = random.randint(max(20, w//10), max(50, w//4))
            bh = random.randint(8, 24)
            x = random.randint(-10, w - bw + 10)
            y = random.randint(0, max(1, h - bh))
            color = random.choice(colors)
            self.glitch_canvas.create_rectangle(x, y, x + bw, y + bh, outline="", fill=color, stipple="gray25")
            if random.random() < 0.7:
                # chromatic split
                ox = random.choice([-6, -3, 3, 6])
                oy = random.choice([-2, -1, 1, 2])
                self.glitch_canvas.create_rectangle(x + ox, y + oy, x + bw + ox, y + bh + oy, outline="", fill=random.choice(colors), stipple="gray50")

        # occasional full flash overlay
        if random.random() < 0.08:
            self.glitch_canvas.create_rectangle(0, 0, w, h, outline="", fill=random.choice(colors), stipple="gray12")

    # ---------- Close ----------
    def _on_close(self):
        self.state["geometry"] = self.root.winfo_geometry()
        save_state(self.state)
        self._stop_glitch()
        self.root.destroy()

def main():
    root = tk.Tk()
    app = DC404NotesApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
