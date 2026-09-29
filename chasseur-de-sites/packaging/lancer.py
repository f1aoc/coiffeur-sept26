"""Point d'entrée de l'application installée (PyInstaller).

Double-clic : une petite fenêtre « Chasseur de sites » s'ouvre (pas de console noire). Elle télécharge
Chromium au premier lancement (une seule fois), démarre l'interface sur http://127.0.0.1:8765/, ouvre
le navigateur, et arrête tout quand on clique sur « Quitter » ou qu'on la ferme.

Avec des arguments, se comporte comme la commande « chasseur » :
    ChasseurDeSites.exe scan prospects.csv

Variables utiles (tests, dépannage) : CHASSEUR_SANS_INSTALLATION=1 (ne pas télécharger Chromium),
CHASSEUR_SANS_NAVIGATEUR=1 (ne pas ouvrir le navigateur), CHASSEUR_SANS_FENETRE=1 (serveur seul).
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import urllib.request
import webbrowser
from pathlib import Path

NOM = "Chasseur de sites"
PORT = 8765
ADRESSE = f"http://127.0.0.1:{PORT}/"
ACCENT, ACCENT_FONCE, FOND, ENCRE, GRIS = "#1f5fbf", "#174a96", "#f5f7fb", "#1b2433", "#5b6576"


def dossier_donnees() -> Path:
    return Path(os.environ.get("CHASSEUR_DONNEES") or Path.home() / ".chasseur-de-sites")


def ressource(nom: str) -> Path:
    """Fichier livré dans l'application (icône…)."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / nom


def rediriger_sorties() -> None:
    """Application sans console (Windows) : les messages vont dans <données>/console.log."""
    if sys.stdout is None or sys.stderr is None:
        dossier = dossier_donnees()
        dossier.mkdir(parents=True, exist_ok=True)
        fichier = open(dossier / "console.log", "w", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stdout or fichier
        sys.stderr = sys.stderr or fichier


# --- Chromium ------------------------------------------------------------------------------------


def chromium_a_installer() -> bool:
    if os.environ.get("CHASSEUR_SANS_INSTALLATION") or os.environ.get("CHASSEUR_CHROMIUM"):
        return False
    return not (Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]) / ".chromium-installe").exists()


def installer_chromium() -> bool:
    """Télécharge Chromium via le pilote Playwright embarqué. Renvoie True si c'est fait."""
    from playwright._impl._driver import compute_driver_executable, get_driver_env

    pilote = compute_driver_executable()
    commande = [*pilote, "install", "chromium"] if isinstance(pilote, (tuple, list)) else [str(pilote), "install", "chromium"]
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    resultat = subprocess.run(commande, env={**os.environ, **get_driver_env()}, check=False,
                              stdout=sys.stdout, stderr=sys.stderr, **options)
    if resultat.returncode != 0:
        return False
    marqueur = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"]) / ".chromium-installe"
    marqueur.parent.mkdir(parents=True, exist_ok=True)
    marqueur.touch()
    return True


# --- Serveur -------------------------------------------------------------------------------------


def deja_lance() -> bool:
    """Vrai si Chasseur de sites répond déjà sur le port (application ouverte deux fois)."""
    try:
        with urllib.request.urlopen(ADRESSE + "a-propos", timeout=2) as r:
            return NOM.encode() in r.read(20000)
    except OSError:
        return False


def creer_serveur():
    import uvicorn

    from chasseur.db import Stockage
    from chasseur.web.app import HOTES_LOCAUX, creer_app

    app = creer_app(Stockage(), hotes=HOTES_LOCAUX)
    serveur = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning", log_config=None))
    serveur.install_signal_handlers = lambda: None  # tourne dans un fil secondaire
    return serveur


def ouvrir_navigateur() -> None:
    if not os.environ.get("CHASSEUR_SANS_NAVIGATEUR"):
        webbrowser.open(ADRESSE)


# --- Fenêtre -------------------------------------------------------------------------------------


class Fenetre:
    def __init__(self, tk):
        from tkinter import ttk

        self.tk = tk
        self.racine = tk.Tk()
        self.racine.title(NOM)
        self.racine.configure(bg=FOND)
        self.racine.resizable(False, False)
        try:
            self.icone = tk.PhotoImage(file=str(ressource("icone.png")))
            self.racine.iconphoto(True, self.icone)
        except (tk.TclError, OSError):
            pass
        cadre = tk.Frame(self.racine, bg=FOND, padx=28, pady=22)
        cadre.pack()
        tk.Label(cadre, text=NOM, bg=FOND, fg=ENCRE, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(cadre, text="Repérez les sites cassés ou obsolètes des entreprises locales", bg=FOND, fg=GRIS,
                 font=("Segoe UI", 10)).pack(anchor="w", pady=(0, 14))
        self.etat = tk.Label(cadre, text="Démarrage…", bg=FOND, fg=ENCRE, font=("Segoe UI", 11), justify="left",
                             wraplength=420)
        self.etat.pack(anchor="w")
        self.barre = ttk.Progressbar(cadre, mode="indeterminate", length=420)
        self.barre.pack(anchor="w", pady=(10, 14))
        boutons = tk.Frame(cadre, bg=FOND)
        boutons.pack(anchor="w", fill="x")
        self.ouvrir = tk.Button(boutons, text="Ouvrir l'interface", command=ouvrir_navigateur, state="disabled",
                                bg=ACCENT, fg="white", activebackground=ACCENT_FONCE, activeforeground="white",
                                relief="flat", padx=16, pady=6, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.ouvrir.pack(side="left")
        tk.Button(boutons, text="Quitter", command=self.quitter, relief="flat", padx=16, pady=6,
                  font=("Segoe UI", 10), cursor="hand2").pack(side="left", padx=(10, 0))
        tk.Label(cadre, text="Gardez cette fenêtre ouverte (vous pouvez la réduire) : la fermer arrête l'application.",
                 bg=FOND, fg=GRIS, font=("Segoe UI", 9), wraplength=420, justify="left").pack(anchor="w", pady=(14, 0))
        self.racine.protocol("WM_DELETE_WINDOW", self.quitter)
        self.serveur = None
        self.messages: queue.Queue = queue.Queue()

    # Seul le fil principal touche à la fenêtre (Tk n'est pas sûr entre fils, notamment sur Mac) :
    # le fil de préparation dépose des messages, relevés toutes les 100 ms.
    def afficher(self, texte: str, occupe: bool) -> None:
        print(texte, flush=True)
        self.messages.put(("etat", texte, occupe))

    def _relever(self) -> None:
        while True:
            try:
                genre, *valeurs = self.messages.get_nowait()
            except queue.Empty:
                break
            if genre == "pret":
                self.ouvrir.configure(state="normal")
                continue
            texte, occupe = valeurs
            self.etat.configure(text=texte)
            if occupe:
                self.barre.start(12)
            else:
                self.barre.stop()
                self.barre.pack_forget()
        self.racine.after(100, self._relever)

    def demarrer(self) -> None:
        self.racine.after(100, self._relever)
        threading.Thread(target=self._preparer, daemon=True).start()
        self.racine.mainloop()

    def _preparer(self) -> None:
        if chromium_a_installer():
            self.afficher("Premier lancement : téléchargement du navigateur d'analyse (environ 150 Mo, une seule "
                          "fois). Cela prend quelques minutes…", True)
            if not installer_chromium():
                self.afficher("⚠ Le navigateur d'analyse n'a pas pu être téléchargé : vérifiez votre connexion "
                              "puis relancez l'application. L'interface démarre quand même.", True)
        else:
            self.afficher("Démarrage de l'interface…", True)
        try:
            self.serveur = creer_serveur()
        except Exception as e:  # noqa: BLE001 — affiché à l'utilisateur
            self.afficher(f"⚠ Impossible de démarrer : {e}", False)
            return
        threading.Thread(target=self.serveur.run, daemon=True).start()
        for _ in range(300):
            if self.serveur.started:
                break
            if self.serveur.should_exit:
                break
            threading.Event().wait(0.1)
        if not self.serveur.started:
            self.afficher(f"⚠ Le port {PORT} est déjà utilisé par un autre programme. Fermez-le, puis relancez.", False)
            return
        self.afficher(f"L'application est prête : {ADRESSE}", False)
        self.messages.put(("pret",))
        ouvrir_navigateur()

    def quitter(self) -> None:
        if self.serveur is not None:
            self.serveur.should_exit = True
        self.racine.destroy()


def sans_fenetre() -> int:
    """Serveur seul, au premier plan (pas d'affichage graphique disponible, ou CHASSEUR_SANS_FENETRE)."""
    if chromium_a_installer():
        print("Premier lancement : téléchargement du navigateur d'analyse (environ 150 Mo, une seule fois)…", flush=True)
        installer_chromium()
    serveur = creer_serveur()
    threading.Timer(1.5, ouvrir_navigateur).start()
    print(f"{NOM} : {ADRESSE}", flush=True)
    serveur.run()
    return 0


def fermer_ecran_de_demarrage() -> None:
    if "_PYI_SPLASH_IPC" not in os.environ:  # écran présent seulement dans l'exécutable Windows
        return
    try:
        import pyi_splash

        pyi_splash.close()
    except Exception:  # noqa: BLE001 — l'écran de démarrage n'est qu'un confort
        pass


def main() -> int:
    rediriger_sorties()
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(dossier_donnees() / "navigateurs"))
    arguments = sys.argv[1:]
    fermer_ecran_de_demarrage()
    if arguments and not arguments[0].startswith("-psn"):  # -psn_… : ajouté par d'anciens macOS au double-clic
        if arguments[0] in ("web", "scan", "rapport", "planifies") and not {"-h", "--help"} & set(arguments):
            if getattr(sys, "frozen", False) and chromium_a_installer():
                print("Premier lancement : téléchargement du navigateur d'analyse (environ 150 Mo)…", flush=True)
                installer_chromium()
        from chasseur.cli import main as cli

        return cli(arguments)

    if deja_lance():
        ouvrir_navigateur()
        return 0
    if os.environ.get("CHASSEUR_SANS_FENETRE"):
        return sans_fenetre()
    try:
        import tkinter as tk

        fenetre = Fenetre(tk)
    except Exception:  # noqa: BLE001 — pas d'affichage graphique : on sert quand même l'interface
        return sans_fenetre()
    fenetre.demarrer()
    return 0


if __name__ == "__main__":
    sys.exit(main())
