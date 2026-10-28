"""Swittched Station 1 (SS1) launcher. Put this file in D:\\ss1 and run it. this is also the source code only"""
import hashlib, json, os, re, subprocess, sys, threading, time
import tkinter as tk
from tkinter import messagebox
try:
    from PIL import Image, ImageTk   # optional: only needed for .jpg covers
except ImportError:
    Image = None

ROOT = os.path.dirname(os.path.abspath(__file__))
GAMES = os.path.join(ROOT, "games")
COVERS = os.path.join(ROOT, "games_cover")
MODS = os.path.join(ROOT, "external_mods")
DATA = os.path.join(ROOT, "library.json")
MAX_MB = 15
CW = CH = 150
BG, CARD, FG, ACC, WARN, DIM = "#14141f", "#22223a", "#e8e8f0", "#6c5ce7", "#ff6b6b", "#8888aa"
RUNNERS = ("love.exe", "lua.exe", "lua54.exe", "luajit.exe")   # looked for in D:\ss1

# ---------------------------------------------------------------- security scanner
# HIGH = can harm your PC. INFO = normal but worth knowing.
HIGH = [
    (r'\bos\s*\.\s*execute\b', "runs system commands (os.execute)"),
    (r'\bio\s*\.\s*popen\b', "runs system commands (io.popen)"),
    (r'\bos\s*\.\s*(remove|rename)\b', "deletes or renames files (os.remove / os.rename)"),
    (r'\bffi\b', "uses FFI (can call any Windows function)"),
    (r'\bpackage\s*\.\s*loadlib\b', "loads native libraries (package.loadlib)"),
    (r'\bsocket\b|require\s*\(?\s*["\']https?["\']', "network access (socket / http)"),
    (r'\b(loadstring|dofile|loadfile)\b|(?<![.\w])load\s*\(', "loads code at runtime (can hide code)"),
    (r'\b_G\s*\[', "indirect global access (can hide code)"),
]
INFO = [
    (r'\bio\s*\.\s*open\b', "reads or writes files (io.open)"),
    (r'\blove\s*\.\s*system\s*\.\s*openURL\b', "opens web links (love.system.openURL)"),
]
NATIVE = {".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".scr", ".jar", ".com", ".msi", ".lnk"}
HIGH = [(re.compile(p), d) for p, d in HIGH]
INFO = [(re.compile(p), d) for p, d in INFO]
_cache = {}

def walk_files(folder, lua_only=False):
    out = []
    for r, _, fs in os.walk(folder):
        for f in fs:
            if lua_only and not f.lower().endswith(".lua"): continue
            p = os.path.join(r, f)
            try:
                st = os.stat(p); out.append((p, st.st_size, st.st_mtime))
            except OSError: pass
    return out

def inspect(folder):
    """Returns {'size': MB, 'high': [...], 'info': [...]} (cached until files change)."""
    gfiles, mfiles = walk_files(folder), walk_files(MODS, lua_only=True)
    sig = tuple(sorted(gfiles + mfiles))
    hit = _cache.get(folder)
    if hit and hit[0] == sig: return hit[1]
    high, info = {}, {}
    def add(d, key, path): d.setdefault(key, set()).add(os.path.relpath(path, ROOT))
    for p, size, _ in gfiles + mfiles:
        ext = os.path.splitext(p)[1].lower()
        if ext in NATIVE and (p, size) in [(q, s) for q, s, _ in gfiles]:
            add(high, "contains a program file (" + ext + ")", p)
        if ext == ".lua":
            try:
                with open(p, encoding="utf-8", errors="ignore") as f: text = f.read(2_000_000)
            except OSError: continue
            for rx, d in HIGH:
                if rx.search(text): add(high, d, p)
            for rx, d in INFO:
                if rx.search(text): add(info, d, p)
    fmt = lambda d: [f"{k}  [{', '.join(sorted(v)[:3])}{'...' if len(v) > 3 else ''}]" for k, v in sorted(d.items())]
    rep = {"size": sum(s for _, s, _ in gfiles) / 1048576, "high": fmt(high), "info": fmt(info)}
    _cache[folder] = (sig, rep)
    return rep

def fingerprint(folder):
    """Hash of the game's files + the mods it can load. If anything changes, the game is re-checked."""
    h = hashlib.sha256()
    for p, _, _ in sorted(walk_files(folder) + walk_files(MODS, lua_only=True)):
        h.update(os.path.relpath(p, ROOT).encode())
        try:
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
        except OSError: pass
    return h.hexdigest()

# ---------------------------------------------------------------- library
def load():
    try:
        with open(DATA, encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return {}

def save(d):
    with open(DATA, "w", encoding="utf-8") as f: json.dump(d, f, indent=2)

def find_cover(gid):
    for ext in (".png", ".gif", ".jpg", ".jpeg"):
        p = os.path.join(COVERS, f"{gid}_cover{ext}")
        if os.path.isfile(p) and (Image or ext in (".png", ".gif")): return p

def find_runner():
    for exe in RUNNERS:
        p = os.path.join(ROOT, exe)
        if os.path.isfile(p): return p

def scan():
    out = []
    for gid in sorted(os.listdir(GAMES)):
        folder = os.path.join(GAMES, gid)
        if not os.path.isdir(folder): continue
        name = gid
        try:   # optional: name.txt inside the game folder holds the display name
            with open(os.path.join(folder, "name.txt"), encoding="utf-8") as f: name = f.readline().strip() or gid
        except OSError: pass
        rep = inspect(folder)
        out.append({"id": gid, "name": name, "folder": folder, "size": rep["size"],
                    "high": rep["high"], "info": rep["info"], "cover": find_cover(gid)})
    return out

class App:
    def __init__(self, root):
        self.root, self.data, self.imgs = root, load(), []
        root.title("Swittched Station 1"); root.geometry("860x600"); root.configure(bg=BG)
        bar = tk.Frame(root, bg=BG); bar.pack(fill="x", padx=14, pady=10)
        tk.Label(bar, text="SS1", font=("Segoe UI", 20, "bold"), bg=BG, fg=ACC).pack(side="left")
        tk.Label(bar, text=" Swittched Station 1", font=("Segoe UI", 11), bg=BG, fg=FG).pack(side="left")
        tk.Button(bar, text="Rescan", command=self.render, bg=ACC, fg="white", relief="flat", padx=10).pack(side="right", padx=4)
        self.fav_only = tk.BooleanVar()
        tk.Checkbutton(bar, text="Favorites", variable=self.fav_only, command=self.render, bg=BG, fg=FG,
                       selectcolor=CARD, activebackground=BG, activeforeground=FG).pack(side="right", padx=8)
        self.canvas = tk.Canvas(root, bg=BG, highlightthickness=0); self.canvas.pack(fill="both", expand=True, padx=10)
        self.grid_f = tk.Frame(self.canvas, bg=BG)
        self.canvas.create_window(0, 0, window=self.grid_f, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.render())
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))
        self.status = tk.Label(root, bg=BG, fg=DIM, anchor="w"); self.status.pack(fill="x", padx=14, pady=4)
        self.render()

    def stat(self, g): return self.data.setdefault(g["id"], {"secs": 0, "fav": False})

    def cover(self, parent, g):
        c = tk.Canvas(parent, width=CW, height=CH, bg="#2e2e50", highlightthickness=0)
        img = None
        try:
            if g["cover"]:
                img = ImageTk.PhotoImage(Image.open(g["cover"]).resize((CW, CH))) if Image else tk.PhotoImage(file=g["cover"])
        except Exception: img = None
        if img: self.imgs.append(img); c.create_image(0, 0, image=img, anchor="nw")
        else: c.create_text(CW // 2, CH // 2, text=g["name"][:1].upper(), font=("Segoe UI", 48, "bold"), fill=ACC)
        return c

    def render(self):
        for w in self.grid_f.winfo_children(): w.destroy()
        self.imgs.clear()
        games = [g for g in scan() if not self.fav_only.get() or self.stat(g)["fav"]]
        cols = max(1, (self.canvas.winfo_width() - 10) // (CW + 24))
        for i, g in enumerate(games):
            s = self.stat(g)
            card = tk.Frame(self.grid_f, bg=CARD, padx=6, pady=6)
            card.grid(row=i // cols, column=i % cols, padx=8, pady=8)
            self.cover(card, g).pack()
            tk.Label(card, text=g["name"], bg=CARD, fg=FG, font=("Segoe UI", 10, "bold"), wraplength=CW).pack(pady=(4, 0))
            h = s["secs"] / 3600
            tk.Label(card, text=f"{h:.1f} h played" if h >= .1 else "Not played yet", bg=CARD, fg=DIM, font=("Segoe UI", 8)).pack()
            over = g["size"] > MAX_MB
            tk.Label(card, text=f"{g['size']:.1f} MB" + (" - OVER 15 MB" if over else ""), bg=CARD,
                     fg=WARN if over else DIM, font=("Segoe UI", 8)).pack()
            if g["high"]:
                tk.Label(card, text=f"! SUSPICIOUS CODE ({len(g['high'])})", bg=CARD, fg=WARN, font=("Segoe UI", 8, "bold")).pack()
            row = tk.Frame(card, bg=CARD); row.pack(pady=(4, 0))
            tk.Button(row, text="PLAY", command=lambda g=g: self.play(g), bg=ACC, fg="white", relief="flat", padx=14).pack(side="left")
            tk.Button(row, text="Fav" if s["fav"] else "+Fav", command=lambda g=g: self.fav(g), bg=CARD, fg="#ffd166",
                      relief="flat").pack(side="left", padx=4)
        self.grid_f.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.status.config(text=f"{len(games)} game(s) - {ROOT}")

    def fav(self, g):
        s = self.stat(g); s["fav"] = not s["fav"]; save(self.data); self.render()

    def approve(self, g):
        """Ask before running a game we haven't approved yet (or whose files changed)."""
        s = self.stat(g)
        fp = fingerprint(g["folder"])
        if s.get("trusted") == fp: return True
        if g["high"]:
            lines = "\n".join("- " + x for x in g["high"][:8])
            more = f"\n...and {len(g['high']) - 8} more" if len(g["high"]) > 8 else ""
            ok = messagebox.askyesno("SS1 - WARNING",
                f"'{g['name']}' contains code that can affect your PC:\n\n{lines}{more}\n\n"
                "Only run it if you fully trust whoever made it.\nRun anyway?",
                icon="warning", default="no")
        else:
            note = ("\n\nNormal things it does:\n" + "\n".join("- " + x for x in g["info"][:5])) if g["info"] else ""
            ok = messagebox.askyesno("SS1 - first run",
                f"'{g['name']}' is a Lua game. Games can run any code on your PC, so only run games "
                f"from people you trust.\n\nNo suspicious code was found, but the scanner can't catch everything.{note}\n\nRun it?",
                default="yes")
        if ok:
            s["trusted"] = fp; save(self.data)
        return ok

    def play(self, g):
        runner = find_runner()
        if not runner:
            messagebox.showerror("SS1", "No Lua runner found.\nPut lua.exe (or love.exe) in:\n" + ROOT); return
        if not os.path.isfile(os.path.join(g["folder"], "main.lua")):
            messagebox.showerror("SS1", f"{g['id']} has no main.lua"); return
        if not self.approve(g): return
        is_love = os.path.basename(runner).lower() == "love.exe"
        cmd = [runner, g["folder"]] if is_love else [runner, "main.lua"]
        env = dict(os.environ, LUA_PATH=os.path.join(MODS, "?.lua") + ";" + os.path.join(MODS, "?", "init.lua") + ";;")
        flags = 0 if is_love else getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
        try: proc = subprocess.Popen(cmd, cwd=g["folder"], env=env, creationflags=flags)
        except OSError as e: messagebox.showerror("SS1", str(e)); return
        self.status.config(text=f"Playing {g['name']}...")
        def wait():
            t0 = time.time(); proc.wait()
            self.stat(g)["secs"] += time.time() - t0; save(self.data); self.root.after(0, self.render)
        threading.Thread(target=wait, daemon=True).start()

if __name__ == "__main__":
    for d in (GAMES, COVERS, MODS): os.makedirs(d, exist_ok=True)
    root = tk.Tk(); App(root); root.mainloop()
