#!/usr/bin/env python3
"""Lead Finder — desktop app to find local businesses without a website.

Pick an occupation and one or more cities, click Search, then export the
results to Excel. Double-click a row to open the business on Google Maps.

    python3 lead_finder_app.pyw     (or double-click the file on Windows)
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from find_no_website import PlacesError, clean_api_key, find_leads, write_xlsx  # noqa: E402

CONFIG_PATH = Path.home() / ".lead_finder.json"

OCCUPATIONS = [
    "coiffeur", "barbier", "institut de beauté", "onglerie", "esthéticienne",
    "boulangerie", "boucherie", "fleuriste", "restaurant", "pizzeria", "bar",
    "plombier", "électricien", "serrurier", "menuisier", "maçon",
    "peintre en bâtiment", "couvreur", "paysagiste", "garage automobile",
    "carrosserie", "auto-école", "toiletteur", "ostéopathe", "kinésithérapeute",
    "photographe", "cordonnier", "pressing", "tatoueur",
]

COLUMNS = [
    # (key, heading, width)
    ("name", "Business", 220),
    ("status", "Website", 170),
    ("phone", "Phone", 120),
    ("address", "Address", 300),
    ("rating", "Rating", 60),
    ("reviews", "Reviews", 70),
]


def load_config():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg), encoding="utf-8")
    except OSError:
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Lead Finder — businesses without a website")
        self.geometry("1000x640")
        self.minsize(760, 480)

        self.cfg = load_config()
        self.leads = []
        self.events = queue.Queue()
        self.worker = None

        self._build_form()
        self._build_results()
        self.after(100, self._poll_events)

    # ---------- UI ----------

    def _build_form(self):
        form = ttk.Frame(self, padding=12)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Google API key").grid(row=0, column=0, sticky="w", pady=4)
        key_row = ttk.Frame(form)
        key_row.grid(row=0, column=1, sticky="ew", pady=4)
        key_row.columnconfigure(0, weight=1)
        self.api_key = tk.StringVar(value=os.environ.get("GOOGLE_MAPS_API_KEY") or self.cfg.get("api_key", ""))
        self.key_entry = ttk.Entry(key_row, textvariable=self.api_key, show="•")
        self.key_entry.grid(row=0, column=0, sticky="ew")
        self.show_key = tk.BooleanVar(value=False)
        ttk.Checkbutton(key_row, text="Show", variable=self.show_key,
                        command=lambda: self.key_entry.config(show="" if self.show_key.get() else "•")
                        ).grid(row=0, column=1, padx=(8, 0))
        self.remember_key = tk.BooleanVar(value=bool(self.cfg.get("api_key")))
        ttk.Checkbutton(key_row, text="Remember", variable=self.remember_key).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(form, text="Occupation").grid(row=1, column=0, sticky="w", pady=4)
        self.occupation = tk.StringVar(value=self.cfg.get("occupation", "coiffeur"))
        ttk.Combobox(form, textvariable=self.occupation, values=OCCUPATIONS).grid(
            row=1, column=1, sticky="ew", pady=4)

        ttk.Label(form, text="Cities\n(one per line)").grid(row=2, column=0, sticky="nw", pady=4)
        self.cities = tk.Text(form, height=4, wrap="word", font=("TkDefaultFont", 10))
        self.cities.grid(row=2, column=1, sticky="ew", pady=4)
        self.cities.insert("1.0", self.cfg.get("cities", ""))

        opts = ttk.Frame(form)
        opts.grid(row=3, column=1, sticky="w", pady=(4, 0))
        self.strict = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="No website at all (ignore Facebook / Instagram / Planity pages)",
                        variable=self.strict).pack(side="left")

        actions = ttk.Frame(form)
        actions.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.search_btn = ttk.Button(actions, text="Search", command=self.start_search)
        self.search_btn.pack(side="left")
        self.export_btn = ttk.Button(actions, text="Exporter Excel…", command=self.export_xlsx, state="disabled")
        self.export_btn.pack(side="left", padx=8)
        self.progress = ttk.Progressbar(actions, mode="indeterminate", length=140)
        self.progress.pack(side="left", padx=8)
        self.status = tk.StringVar(value="Choose an occupation and at least one city, then click Search.")
        ttk.Label(actions, textvariable=self.status).pack(side="left", padx=8)

    def _build_results(self):
        frame = ttk.Frame(self, padding=(12, 0, 12, 12))
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=[c[0] for c in COLUMNS], show="headings")
        for key, heading, width in COLUMNS:
            self.tree.heading(key, text=heading, command=lambda k=key: self.sort_by(k))
            self.tree.column(key, width=width, anchor="w")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self.open_in_maps)
        ttk.Label(self, text="Tip: double-click a row to open it on Google Maps.",
                  foreground="gray").pack(anchor="w", padx=12, pady=(0, 8))

    # ---------- Actions ----------

    def start_search(self):
        key = clean_api_key(self.api_key.get())
        occupation = self.occupation.get().strip()
        cities = [c.strip() for c in self.cities.get("1.0", "end").replace(",", "\n").splitlines() if c.strip()]
        if not key:
            messagebox.showwarning("Missing API key", "Paste your Google Maps API key first.")
            return
        if not occupation:
            messagebox.showwarning("Missing occupation", "Choose or type an occupation.")
            return
        if not cities:
            messagebox.showwarning("Missing city", "Enter at least one city.")
            return

        self.cfg.update(occupation=occupation, cities="\n".join(cities))
        if self.remember_key.get():
            self.cfg["api_key"] = key
        else:
            self.cfg.pop("api_key", None)
        save_config(self.cfg)

        self.tree.delete(*self.tree.get_children())
        self.leads = []
        self.search_btn.config(state="disabled")
        self.export_btn.config(state="disabled")
        self.progress.start(12)
        self.status.set(f"Searching {occupation} in {len(cities)} city(ies)…")

        queries = [f"{occupation} {c}" for c in cities]
        self.worker = threading.Thread(target=self._run_search, args=(key, queries, self.strict.get()), daemon=True)
        self.worker.start()

    def _run_search(self, key, queries, strict):
        try:
            leads, total = find_leads(
                key, queries, strict=strict,
                progress=lambda q, n: self.events.put(("progress", f"{q}: {n} lead(s)")),
            )
            self.events.put(("done", (leads, total)))
        except PlacesError as e:
            self.events.put(("error", str(e)))
        except Exception as e:  # keep the UI alive whatever happens
            self.events.put(("error", f"Unexpected error: {e}"))

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
                    self.status.set("Search failed.")
                    messagebox.showerror("Search failed", payload)
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _finish(self):
        self.progress.stop()
        self.search_btn.config(state="normal")

    def _show_results(self, leads, total):
        self._finish()
        self.leads = leads
        self._fill_tree()
        self.export_btn.config(state="normal" if leads else "disabled")
        self.status.set(f"{len(leads)} business(es) without a website, out of {total} found.")

    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        for i, lead in enumerate(self.leads):
            status = "None" if lead["status"] == "none" else lead["status"].split(":", 1)[1] + " only"
            values = [status if k == "status" else lead[k] for k, _, _ in COLUMNS]
            self.tree.insert("", "end", iid=str(i), values=values)

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
        default = f"leads_{self.occupation.get().strip().replace(' ', '_') or 'export'}.xlsx"
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=default,
                                            filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        try:
            write_xlsx(self.leads, path)
        except OSError as e:
            messagebox.showerror("Export failed", str(e))
            return
        self.status.set(f"Exported {len(self.leads)} lead(s) to {path}")


if __name__ == "__main__":
    App().mainloop()
