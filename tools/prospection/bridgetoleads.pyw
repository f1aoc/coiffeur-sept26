#!/usr/bin/env python3
"""BridgeToLeads by ptabountchikoff — application de bureau pour trouver les commerces sans site web.

Choisissez un métier et une ou plusieurs villes, cliquez sur Rechercher, puis
exportez les résultats vers Excel. Double-cliquez une ligne pour ouvrir le
commerce sur Google Maps.

    python3 bridgetoleads.pyw     (ou double-clic sur le fichier sous Windows)
"""

import json
import os
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brand_icon import ICON_PNG_B64  # noqa: E402
from find_no_website import PlacesError, clean_api_key, find_leads, write_xlsx  # noqa: E402

# ---------- Brand: change these to rebrand the app ----------

APP_NAME = "BridgeToLeads"
AUTHOR = "ptabountchikoff"
TAGLINE = "Trouvez les commerces sans site web, prêts à devenir vos clients"
KEY_HELP_URL = "https://console.cloud.google.com/apis/library/places.googleapis.com"

GRADIENT = ["#7C3AED", "#EC4899", "#F97316"]  # violet → rose → orange
C = {
    "bg": "#F6F3FF",
    "card": "#FFFFFF",
    "border": "#E9E3FB",
    "ink": "#1E1B4B",
    "muted": "#6B6893",
    "violet": "#7C3AED",
    "violet_dark": "#6D28D9",
    "pink": "#EC4899",
    "pink_dark": "#DB2777",
    "orange": "#F97316",
    "teal": "#0D9488",
    "teal_dark": "#0F766E",
    "disabled": "#C9C3E6",
    "row_none": "#FFF0F7",
    "row_social": "#F3EEFF",
    "select": "#FDE68A",
}

CONFIG_PATH = Path.home() / ".bridgetoleads.json"
OLD_CONFIG_PATH = Path.home() / ".lead_finder.json"  # settings saved by the app's previous name

OCCUPATIONS = [
    "coiffeur", "barbier", "institut de beauté", "onglerie", "esthéticienne",
    "boulangerie", "boucherie", "fleuriste", "restaurant", "pizzeria", "bar",
    "plombier", "électricien", "serrurier", "menuisier", "maçon",
    "peintre en bâtiment", "couvreur", "paysagiste", "garage automobile",
    "carrosserie", "auto-école", "toiletteur", "ostéopathe", "kinésithérapeute",
    "photographe", "cordonnier", "pressing", "tatoueur",
]

COLUMNS = [
    # (key, heading, width, stretch)
    ("name", "Commerce", 170, True),
    ("status", "Site web", 165, False),
    ("phone", "Téléphone", 120, False),
    ("address", "Adresse", 180, True),
    ("rating", "Note", 50, False),
    ("reviews", "Avis", 55, False),
]


def page_name(status):
    """'social_or_directory:facebook.com' -> 'Facebook seulement'."""
    host = status.split(":", 1)[-1]
    return host.split(".")[0].capitalize() + " seulement"


def load_config():
    for path in (CONFIG_PATH, OLD_CONFIG_PATH):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return {}


def save_config(cfg):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg), encoding="utf-8")
    except OSError:
        pass


def hex_to_rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def gradient_at(t):
    """Colour at position t (0..1) along GRADIENT."""
    t = min(max(t, 0.0), 1.0) * (len(GRADIENT) - 1)
    i = min(int(t), len(GRADIENT) - 2)
    a, b = hex_to_rgb(GRADIENT[i]), hex_to_rgb(GRADIENT[i + 1])
    k = t - i
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * k) for x, y in zip(a, b))


def pick_family(root):
    families = set(tkfont.families(root))
    for name in ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Inter", "Liberation Sans", "DejaVu Sans"):
        if name in families:
            return name
    return "TkDefaultFont"


def rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, **kw)


class PillButton(tk.Canvas):
    """Rounded, coloured button (Tk buttons can't be rounded or recoloured on Windows)."""

    def __init__(self, parent, text, command, color, hover, font, fg="white",
                 height=42, width=None, parent_bg=None):
        self.text_width = tkfont.Font(font=font).measure(text)
        super().__init__(parent, height=height, width=width or self.text_width + 44,
                         bg=parent_bg or parent["bg"], highlightthickness=0, bd=0, cursor="hand2")
        self.text, self.command, self.font, self.fg = text, command, font, fg
        self.color, self.hover = color, hover
        self.enabled, self.hovered = True, False
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<Button-1>", lambda e: self.enabled and self.command())

    def _set_hover(self, value):
        self.hovered = value
        self._draw()

    def set_enabled(self, value):
        self.enabled = value
        self.config(cursor="hand2" if value else "arrow")
        self._draw()

    def set_text(self, text):
        self.text = text
        self._draw()

    def _draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        fill = C["disabled"] if not self.enabled else (self.hover if self.hovered else self.color)
        rounded_rect(self, 1, 1, w - 1, h - 1, h // 2, fill=fill, outline=fill)
        self.create_text(w // 2, h // 2, text=self.text, fill=self.fg, font=self.font)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} by {AUTHOR} — {TAGLINE}")
        self.geometry("1180x740")
        self.minsize(960, 600)
        self.configure(bg=C["bg"])
        try:
            self._icon = tk.PhotoImage(data=ICON_PNG_B64)
            self.iconphoto(True, self._icon)
        except tk.TclError:
            pass

        family = pick_family(self)
        self.f = {
            "title": (family, 22, "bold"),
            "tagline": (family, 11),
            "byline": (family, 10, "italic"),
            "h2": (family, 13, "bold"),
            "label": (family, 10, "bold"),
            "body": (family, 10),
            "small": (family, 9),
            "stat": (family, 24, "bold"),
            "button": (family, 11, "bold"),
        }

        self.cfg = load_config()
        self.leads = []
        self.events = queue.Queue()
        self.worker = None
        self.api_key = tk.StringVar(value=os.environ.get("GOOGLE_MAPS_API_KEY") or self.cfg.get("api_key", ""))
        self.remember_key = tk.BooleanVar(value=bool(self.cfg.get("api_key")))
        self.show_key = tk.BooleanVar(value=False)

        self._init_styles()
        self._build_header()
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=20, pady=(16, 20))
        self._build_sidebar(body)
        self._build_main(body)
        self._refresh_key_badge()
        self.after(100, self._poll_events)
        if not self.api_key.get():
            self.after(500, self.open_settings)

    # ---------- Styles ----------

    def _init_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TCombobox", fieldbackground="white", background="white", foreground=C["ink"],
                    arrowcolor=C["violet"], bordercolor=C["border"], lightcolor=C["border"],
                    darkcolor=C["border"], padding=8)
        s.map("TCombobox", bordercolor=[("focus", C["violet"])], lightcolor=[("focus", C["violet"])])
        self.option_add("*TCombobox*Listbox.font", self.f["body"])
        self.option_add("*TCombobox*Listbox.selectBackground", C["violet"])
        s.configure("TEntry", fieldbackground="white", foreground=C["ink"], bordercolor=C["border"],
                    lightcolor=C["border"], darkcolor=C["border"], padding=8)
        s.map("TEntry", bordercolor=[("focus", C["violet"])], lightcolor=[("focus", C["violet"])])
        for name, bg in (("Card.TCheckbutton", C["card"]),):
            s.configure(name, background=bg, foreground=C["ink"], font=self.f["body"],
                        indicatorbackground="white", indicatorforeground=C["violet"])
            s.map(name, background=[("active", bg)], indicatorbackground=[("selected", C["violet"])],
                  indicatorforeground=[("selected", "white")])
        s.configure("Leads.Treeview", background="white", fieldbackground="white", foreground=C["ink"],
                    rowheight=34, font=self.f["body"], borderwidth=0, bordercolor=C["border"])
        s.map("Leads.Treeview", background=[("selected", C["select"])], foreground=[("selected", C["ink"])])
        s.configure("Leads.Treeview.Heading", background=C["ink"], foreground="white", font=self.f["label"],
                    relief="flat", padding=(8, 8), bordercolor=C["ink"], lightcolor=C["ink"], darkcolor=C["ink"])
        s.map("Leads.Treeview.Heading", background=[("active", C["violet"])])
        s.layout("Leads.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        s.configure("Pink.Horizontal.TProgressbar", troughcolor=C["border"], background=C["pink"],
                    bordercolor=C["border"], lightcolor=C["pink"], darkcolor=C["pink"], thickness=6)
        s.configure("Vertical.TScrollbar", background=C["border"], troughcolor="white",
                    bordercolor="white", arrowcolor=C["violet"], lightcolor=C["border"], darkcolor=C["border"])

    # ---------- Header ----------

    def _build_header(self):
        self.header = tk.Canvas(self, height=96, highlightthickness=0, bd=0)
        self.header.pack(fill="x")
        self.header_logo = tk.PhotoImage(data=ICON_PNG_B64)
        self.settings_btn = PillButton(self.header, "⚙  Clé API", self.open_settings, color="white",
                                       hover="#FDE68A", fg=C["violet_dark"], font=self.f["label"],
                                       height=36, parent_bg=GRADIENT[-1])
        self.header.bind("<Configure>", lambda e: self._draw_header())

    def _draw_header(self):
        c = self.header
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        step = 4
        for x in range(0, w, step):
            c.create_rectangle(x, 0, x + step, h, fill=gradient_at(x / max(w - 1, 1)), width=0)
        c.create_image(24, h // 2, image=self.header_logo, anchor="w")
        c.create_text(102, h // 2 - 12, text=APP_NAME, fill="white", font=self.f["title"], anchor="w")
        title_w = tkfont.Font(font=self.f["title"]).measure(APP_NAME)
        c.create_text(102 + title_w + 10, h // 2 - 8, text=f"by {AUTHOR}", fill="white",
                      font=self.f["byline"], anchor="w")
        c.create_text(104, h // 2 + 18, text=TAGLINE, fill="white", font=self.f["tagline"], anchor="w")
        edge = gradient_at(1.0)
        self.settings_btn.config(bg=edge)
        c.create_window(w - 24, h // 2, window=self.settings_btn, anchor="e")
        c.create_text(w - 24 - int(self.settings_btn["width"]) - 16, h // 2, text=self._key_badge_text(),
                      fill="white", font=self.f["label"], anchor="e", tags="badge")

    def _key_badge_text(self):
        return "✔ Clé configurée" if self.api_key.get().strip() else "✖ Aucune clé API"

    def _refresh_key_badge(self):
        self.header.itemconfigure("badge", text=self._key_badge_text())

    # ---------- Sidebar (search form) ----------

    def _card(self, parent, **pack):
        card = tk.Frame(parent, bg=C["card"], highlightbackground=C["border"], highlightthickness=1)
        card.pack(**pack)
        return card

    def _build_sidebar(self, body):
        side = self._card(body, side="left", fill="y", padx=(0, 16))
        inner = tk.Frame(side, bg=C["card"], width=300)
        inner.pack(fill="both", expand=True, padx=20, pady=20)

        tk.Label(inner, text="Nouvelle recherche", font=self.f["h2"], bg=C["card"], fg=C["ink"]).pack(anchor="w")
        tk.Frame(inner, bg=C["pink"], height=3, width=48).pack(anchor="w", pady=(6, 16))

        tk.Label(inner, text="MÉTIER", font=self.f["small"], bg=C["card"], fg=C["violet"]).pack(anchor="w")
        self.occupation = tk.StringVar(value=self.cfg.get("occupation", "coiffeur"))
        ttk.Combobox(inner, textvariable=self.occupation, values=OCCUPATIONS, font=self.f["body"],
                     width=28).pack(fill="x", pady=(4, 16))

        tk.Label(inner, text="VILLES", font=self.f["small"], bg=C["card"], fg=C["violet"]).pack(anchor="w")
        tk.Label(inner, text="Une par ligne, ou séparées par des virgules", font=self.f["small"],
                 bg=C["card"], fg=C["muted"]).pack(anchor="w")
        box = tk.Frame(inner, bg=C["border"], padx=1, pady=1)
        box.pack(fill="x", pady=(4, 16))
        self.cities = tk.Text(box, height=6, width=30, wrap="word", font=self.f["body"], relief="flat",
                              fg=C["ink"], bg="white", insertbackground=C["violet"], padx=8, pady=6,
                              highlightthickness=0)
        self.cities.pack(fill="x")
        self.cities.bind("<FocusIn>", lambda e: box.config(bg=C["violet"]))
        self.cities.bind("<FocusOut>", lambda e: box.config(bg=C["border"]))
        self.cities.insert("1.0", self.cfg.get("cities", ""))

        self.strict = tk.BooleanVar(value=False)
        ttk.Checkbutton(inner, text="Aucun site du tout\n(exclure pages Facebook, Planity…)",
                        variable=self.strict, style="Card.TCheckbutton").pack(anchor="w", pady=(0, 20))

        self.search_btn = PillButton(inner, "Rechercher  →", self.start_search, color=C["violet"],
                                     hover=C["violet_dark"], font=self.f["button"], height=46, width=260)
        self.search_btn.pack(fill="x")
        self.progress = ttk.Progressbar(inner, mode="indeterminate", style="Pink.Horizontal.TProgressbar")
        self.progress.pack(fill="x", pady=(12, 0))
        self.progress.pack_forget()

        tk.Frame(inner, bg=C["card"]).pack(fill="both", expand=True)
        tk.Label(inner, text="Astuce : double-cliquez un résultat\npour l'ouvrir sur Google Maps.",
                 font=self.f["small"], bg=C["card"], fg=C["muted"], justify="left").pack(anchor="w")

    # ---------- Main area (stats + table) ----------

    def _build_main(self, body):
        main = tk.Frame(body, bg=C["bg"])
        main.pack(side="left", fill="both", expand=True)

        stats = tk.Frame(main, bg=C["bg"])
        stats.pack(fill="x", pady=(0, 16))
        self.stat_vars = {}
        tiles = [
            ("total", "Commerces analysés", C["violet"], "#EDE6FF"),
            ("none", "Sans aucun site", C["pink"], "#FFE4F1"),
            ("social", "Réseaux / annuaire seulement", C["orange"], "#FFEAD9"),
        ]
        for i, (key, caption, color, tint) in enumerate(tiles):
            tile = tk.Frame(stats, bg=tint)
            tile.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0))
            stats.columnconfigure(i, weight=1, uniform="stats")
            tk.Frame(tile, bg=color, width=6).pack(side="left", fill="y")
            text = tk.Frame(tile, bg=tint)
            text.pack(side="left", fill="both", expand=True, padx=16, pady=12)
            var = tk.StringVar(value="—")
            self.stat_vars[key] = var
            tk.Label(text, textvariable=var, font=self.f["stat"], bg=tint, fg=color).pack(anchor="w")
            tk.Label(text, text=caption, font=self.f["small"], bg=tint, fg=C["ink"]).pack(anchor="w")

        card = self._card(main, fill="both", expand=True)
        top = tk.Frame(card, bg=C["card"])
        top.pack(fill="x", padx=16, pady=(14, 10))
        tk.Label(top, text="Résultats", font=self.f["h2"], bg=C["card"], fg=C["ink"]).pack(side="left")
        self.export_btn = PillButton(top, "⬇  Exporter Excel", self.export_xlsx, color=C["teal"],
                                     hover=C["teal_dark"], font=self.f["label"], height=36)
        self.export_btn.pack(side="right")
        self.export_btn.set_enabled(False)

        table = tk.Frame(card, bg=C["card"])
        table.pack(fill="both", expand=True, padx=16)
        # Small requested width: the stretchable columns grow to fill whatever space the window gives.
        self.tree = ttk.Treeview(table, columns=[c[0] for c in COLUMNS], show="headings", style="Leads.Treeview",
                                 height=8)
        for key, heading, width, stretch in COLUMNS:
            self.tree.heading(key, text=heading, anchor="w", command=lambda k=key: self.sort_by(k))
            self.tree.column(key, width=width, minwidth=width if not stretch else 120, stretch=stretch, anchor="w")
        self.tree.tag_configure("none", background=C["row_none"])
        self.tree.tag_configure("social", background=C["row_social"])
        vsb = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self.open_in_maps)

        self.empty = tk.Label(self.tree, text="Lancez une recherche pour voir\nles commerces sans site web ici.",
                              font=self.f["body"], bg="white", fg=C["muted"], justify="center")
        self.empty.place(relx=0.5, rely=0.5, anchor="center")

        legend = tk.Frame(card, bg=C["card"])
        legend.pack(fill="x", padx=16, pady=10)
        for color, text in ((C["row_none"], "Aucun site"), (C["row_social"], "Réseaux / annuaire seulement")):
            tk.Label(legend, bg=color, width=2, highlightbackground=C["border"], highlightthickness=1
                     ).pack(side="left")
            tk.Label(legend, text=text, font=self.f["small"], bg=C["card"], fg=C["muted"]).pack(side="left", padx=(6, 16))
        self.status = tk.StringVar(value="Choisissez un métier et au moins une ville, puis cliquez sur Rechercher.")
        tk.Label(legend, textvariable=self.status, font=self.f["small"], bg=C["card"], fg=C["violet"]
                 ).pack(side="right")

    # ---------- Settings dialog ----------

    def open_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title("Clé API Google")
        dlg.configure(bg=C["card"])
        dlg.resizable(False, False)
        dlg.transient(self)
        try:
            dlg.iconphoto(False, self._icon)
        except (tk.TclError, AttributeError):
            pass
        pad = tk.Frame(dlg, bg=C["card"])
        pad.pack(padx=28, pady=24)
        tk.Label(pad, text="Votre clé API Google", font=self.f["h2"], bg=C["card"], fg=C["ink"]).pack(anchor="w")
        tk.Frame(pad, bg=C["pink"], height=3, width=48).pack(anchor="w", pady=(6, 12))
        tk.Label(pad, text="Elle permet d'interroger Google Maps. Elle reste sur cet ordinateur.",
                 font=self.f["small"], bg=C["card"], fg=C["muted"]).pack(anchor="w", pady=(0, 10))
        entry = ttk.Entry(pad, textvariable=self.api_key, show="•", width=52, font=self.f["body"])
        entry.pack(fill="x")
        opts = tk.Frame(pad, bg=C["card"])
        opts.pack(fill="x", pady=10)
        ttk.Checkbutton(opts, text="Afficher", variable=self.show_key, style="Card.TCheckbutton",
                        command=lambda: entry.config(show="" if self.show_key.get() else "•")).pack(side="left")
        ttk.Checkbutton(opts, text="Mémoriser sur cet ordinateur", variable=self.remember_key,
                        style="Card.TCheckbutton").pack(side="left", padx=16)
        link = tk.Label(pad, text="Comment obtenir une clé ? →", font=self.f["label"], bg=C["card"],
                        fg=C["pink_dark"], cursor="hand2")
        link.pack(anchor="w", pady=(0, 16))
        link.bind("<Button-1>", lambda e: webbrowser.open(KEY_HELP_URL))

        def save():
            self.api_key.set(clean_api_key(self.api_key.get()))
            self._remember_settings()
            self._refresh_key_badge()
            dlg.destroy()

        PillButton(pad, "Enregistrer", save, color=C["violet"], hover=C["violet_dark"],
                   font=self.f["button"], height=42).pack(anchor="e")
        entry.focus_set()
        dlg.bind("<Return>", lambda e: save())

    def _remember_settings(self):
        if self.remember_key.get() and self.api_key.get():
            self.cfg["api_key"] = self.api_key.get()
        else:
            self.cfg.pop("api_key", None)
        save_config(self.cfg)

    # ---------- Actions ----------

    def start_search(self):
        key = clean_api_key(self.api_key.get())
        occupation = self.occupation.get().strip()
        cities = [c.strip() for c in self.cities.get("1.0", "end").replace(",", "\n").splitlines() if c.strip()]
        if not key:
            messagebox.showwarning("Clé API manquante", "Ajoutez d'abord votre clé API Google (bouton « Clé API »).")
            self.open_settings()
            return
        if not occupation:
            messagebox.showwarning("Métier manquant", "Choisissez ou tapez un métier.")
            return
        if not cities:
            messagebox.showwarning("Ville manquante", "Indiquez au moins une ville.")
            return

        self.cfg.update(occupation=occupation, cities="\n".join(cities))
        self._remember_settings()

        self.tree.delete(*self.tree.get_children())
        self.leads = []
        for var in self.stat_vars.values():
            var.set("…")
        self.search_btn.set_enabled(False)
        self.search_btn.set_text("Recherche en cours…")
        self.export_btn.set_enabled(False)
        self.progress.pack(fill="x", pady=(12, 0), after=self.search_btn)
        self.progress.start(12)
        self.empty.config(text="Recherche en cours…")
        self.empty.place(relx=0.5, rely=0.5, anchor="center")
        villes = "ville" if len(cities) == 1 else "villes"
        self.status.set(f"Recherche « {occupation} » dans {len(cities)} {villes}…")

        queries = [f"{occupation} {c}" for c in cities]
        self.worker = threading.Thread(target=self._run_search, args=(key, queries, self.strict.get()), daemon=True)
        self.worker.start()

    def _run_search(self, key, queries, strict):
        try:
            leads, total = find_leads(
                key, queries, strict=strict,
                progress=lambda q, n: self.events.put(("progress", f"{q} : {n} prospect(s)")),
            )
            self.events.put(("done", (leads, total)))
        except PlacesError as e:
            self.events.put(("error", str(e)))
        except Exception as e:  # keep the UI alive whatever happens
            self.events.put(("error", f"Erreur inattendue : {e}"))

    def _poll_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "progress":
                    self.status.set(payload)
                elif kind == "done":
                    self._show_results(*payload)
                elif kind == "error":
                    self._finish()
                    for var in self.stat_vars.values():
                        var.set("—")
                    self.empty.config(text="La recherche a échoué.")
                    self.status.set("La recherche a échoué.")
                    messagebox.showerror("La recherche a échoué", payload)
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _finish(self):
        self.progress.stop()
        self.progress.pack_forget()
        self.search_btn.set_text("Rechercher  →")
        self.search_btn.set_enabled(True)

    def _show_results(self, leads, total):
        self._finish()
        self.leads = leads
        self._fill_tree()
        none = sum(1 for lead in leads if lead["status"] == "none")
        self.stat_vars["total"].set(str(total))
        self.stat_vars["none"].set(str(none))
        self.stat_vars["social"].set(str(len(leads) - none))
        self.export_btn.set_enabled(bool(leads))
        self.status.set(f"{len(leads)} prospect(s) sans site web sur {total} commerces trouvés.")
        if not leads:
            self.empty.config(text="Tous les commerces trouvés ont déjà un site.\nEssayez une autre ville ou un autre métier.")

    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        if self.leads:
            self.empty.place_forget()
        for i, lead in enumerate(self.leads):
            tag = "none" if lead["status"] == "none" else "social"
            label = "✖  Aucun site" if tag == "none" else "•  " + page_name(lead["status"])
            values = [label if k == "status" else lead[k] for k, _, _, _ in COLUMNS]
            self.tree.insert("", "end", iid=str(i), values=values, tags=(tag,))

    def sort_by(self, key):
        numeric = key in ("rating", "reviews")
        reverse = numeric  # biggest numbers first, text A→Z
        self.leads.sort(key=lambda r: (r[key] or 0) if numeric else str(r[key]).lower(), reverse=reverse)
        self._fill_tree()

    def open_in_maps(self, _event):
        sel = self.tree.focus()
        if sel and self.leads[int(sel)]["maps_url"]:
            webbrowser.open(self.leads[int(sel)]["maps_url"])

    def export_xlsx(self):
        default = f"prospects_{self.occupation.get().strip().replace(' ', '_') or 'export'}.xlsx"
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=default,
                                            filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        try:
            write_xlsx(self.leads, path)
        except OSError as e:
            messagebox.showerror("Export impossible", str(e))
            return
        self.status.set(f"{len(self.leads)} prospect(s) exporté(s) vers {os.path.basename(path)}")


if __name__ == "__main__":
    App().mainloop()
