# PyInstaller : application « Chasseur de sites ».
#   pip install -e . pyinstaller pillow
#   python packaging/icone.py
#   pyinstaller packaging/chasseur.spec --noconfirm
# Résultat, comme BridgeToLeads :
#   Windows : dist/ChasseurDeSites.exe (un seul fichier, sans console, écran de démarrage)
#   macOS   : dist/ChasseurDeSites.app (à zipper avec « ditto »)
#   Linux   : dist/ChasseurDeSites/ (dossier)
# WeasyPrint est exclu (il demande GTK sous Windows) : les PDF passent par Chromium.
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

from chasseur import __version__

RACINE = Path(SPECPATH).parent
GENERE = RACINE / "packaging" / "genere"
WINDOWS, MAC = sys.platform == "win32", sys.platform == "darwin"

donnees = [
    (str(RACINE / "config.yaml"), "."),
    (str(RACINE / "signatures.yaml"), "."),
    (str(GENERE / "icone.png"), "."),
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
    excludes=["weasyprint", "pytest", "respx"],
    noarchive=False,
)
pyz = PYZ(a.pure)

if WINDOWS:
    ecran = Splash(str(GENERE / "demarrage.png"), binaries=a.binaries, datas=a.datas, text_pos=None)
    exe = EXE(
        pyz, a.scripts, ecran, ecran.binaries, a.binaries, a.datas, [],
        name="ChasseurDeSites",
        console=False,  # une petite fenêtre remplace la console noire
        icon=str(GENERE / "icone.ico"),
        upx=False,
    )
else:
    exe = EXE(
        pyz, a.scripts, [],
        exclude_binaries=True,
        name="ChasseurDeSites",
        console=not MAC,
        icon=str(GENERE / ("icone-1024.png" if MAC else "icone.ico")),
    )
    dossier = COLLECT(exe, a.binaries, a.datas, name="ChasseurDeSites")
    if MAC:
        app = BUNDLE(
            dossier,
            name="ChasseurDeSites.app",
            icon=str(GENERE / "icone-1024.png"),
            bundle_identifier="com.ptabountchikoff.chasseurdesites",
            version=__version__,
            info_plist={
                "CFBundleDisplayName": "Chasseur de sites",
                "CFBundleName": "Chasseur de sites",
                "NSHighResolutionCapable": True,
                "LSMinimumSystemVersion": "11.0",
            },
        )
