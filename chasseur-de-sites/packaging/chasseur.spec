# PyInstaller : exécutable « ChasseurDeSites » (Windows, macOS, Linux).
#   pip install -e . pyinstaller
#   pyinstaller packaging/chasseur.spec --noconfirm
# Résultat : dist/ChasseurDeSites/ (dossier à zipper et distribuer).
# WeasyPrint est exclu (il demande GTK sous Windows) : les PDF passent par Chromium.
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

RACINE = Path(SPECPATH).parent

donnees = [
    (str(RACINE / "config.yaml"), "."),
    (str(RACINE / "signatures.yaml"), "."),
    (str(RACINE / "chasseur" / "web" / "templates"), "chasseur/web/templates"),
    (str(RACINE / "chasseur" / "web" / "static"), "chasseur/web/static"),
    (str(RACINE / "chasseur" / "reports" / "templates"), "chasseur/reports/templates"),
]
donnees += collect_data_files("whois")

caches = (
    collect_submodules("uvicorn")
    + collect_submodules("chasseur")
    + ["whois", "sqlmodel", "multipart", "python_multipart", "PIL.WebPImagePlugin", "email.mime.text"]
)

a = Analysis(
    [str(RACINE / "packaging" / "lancer.py")],
    pathex=[str(RACINE)],
    datas=donnees,
    hiddenimports=caches,
    excludes=["weasyprint", "tkinter", "pytest", "respx"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ChasseurDeSites",
    console=True,  # la fenêtre affiche l'adresse de l'interface ; la fermer arrête l'application
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="ChasseurDeSites")
