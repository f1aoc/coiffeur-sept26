"""Miniatures de vidéos YouTube VORELIK (1280 × 720), dans le style de la bannière.
Chaque miniature = une entrée de MINIATURES : logiciel (couleurs + icône + capture), texte en 2-3 lignes
(le mot entre [crochets] est mis en couleur), et une étiquette posée sur la capture."""
import sys
from pathlib import Path

R = Path("/home/user/coiffeur-sept26")
A = R / "vitrine/assets"
LOGICIELS = {
    "btl": dict(nom={"fr": "BridgeToLeads", "en": "BridgeToLeads"}, icone=A / "bridgetoleads-icone.png",
                fond=("#7C3AED", "#EC4899", "#F97316"), surligne="#FDE68A",
                capture={"fr": A / "bridgetoleads-apercu.jpg", "en": R / "vitrine-en/bridgetoleads/assets/app-screenshot.png"}),
    "cds": dict(nom={"fr": "Chasseur de sites", "en": "Site Hunter"}, icone=A / "chasseur-icone.png",
                fond=("#1F5FBF", "#0EA5E9", "#F97316"), surligne="#FDE68A",
                capture={"fr": A / "chasseur-apercu.jpg", "en": R / "vitrine-en/site-hunter/assets/app-screenshot.jpg"}),
    "aex": dict(nom={"fr": "Audit express", "en": "Audit Express"}, icone=A / "audit-express-icone.png",
                fond=("#059669", "#0E7490", "#F97316"), surligne="#FDE68A",
                capture={"fr": A / "audit-express-apercu.jpg", "en": R / "vitrine-en/audit-express/assets/app-screenshot.jpg"}),
    "vorelik": dict(nom={"fr": "VORELIK", "en": "VORELIK"}, icone=None,
                    fond=("#7C3AED", "#EC4899", "#0EA5E9"), surligne="#FDE68A",
                    capture={"fr": A / "chasseur-apercu.jpg", "en": R / "vitrine-en/site-hunter/assets/app-screenshot.jpg"}),
}
MINIATURES = [
    ("btl-clients-sans-site", "btl",
     {"fr": "10 clients<br>[sans site web]<br>en 2 minutes", "en": "10 clients<br>[with no website]<br>in 2 minutes"},
     {"fr": "✖ Aucun site", "en": "✖ No website"}, "rose"),
    ("cds-sites-casses", "cds",
     {"fr": "Leur site<br>est [cassé.]<br>Refaites-le !", "en": "Their site<br>is [broken.]<br>Fix it for them"},
     {"fr": "⚠ Site cassé", "en": "⚠ Broken site"}, "rouge"),
    ("aex-audit-qui-signe", "aex",
     {"fr": "L'audit qui<br>[fait signer]<br>en 1 minute", "en": "The audit<br>[that wins deals]<br>in 1 minute"},
     {"fr": "Note : C", "en": "Grade: C"}, "rouge"),
    ("vorelik-trouver-clients", "vorelik",
     {"fr": "Trouvez vos<br>[prochains<br>clients]", "en": "Find your<br>[next<br>clients]"},
     {"fr": "+ 3 logiciels", "en": "+ 3 apps"}, "jaune"),
]
ETIQUETTES = {"rose": ("#DB2777", "#fff"), "rouge": ("#DC2626", "#fff"), "jaune": ("#FDE68A", "#1E1B4B")}

def page(cle, logiciel, textes, etiquette, couleur, langue):
    L = LOGICIELS[logiciel]
    c1, c2, c3 = L["fond"]
    texte = textes[langue].replace("[", f'<span class="fort">').replace("]", "</span>")
    fe, te = ETIQUETTES[couleur]
    entete = (f'<img src="{L["icone"]}" alt=""><span>{L["nom"][langue]}</span>' if L["icone"]
              else f'<img class="logo-seul" src="{A / "vorelik-logo.png"}" alt="VORELIK">')
    return f"""<!doctype html><html><head><meta charset="utf-8"><link href="{A / 'polices/polices.css'}" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; }}
  html, body {{ width: 1280px; height: 720px; overflow: hidden; }}
  body {{ position: relative; font-family: "Plus Jakarta Sans", sans-serif; color: #fff; background: #0A0F1F; }}
  .fond {{ position: absolute; inset: 0; background: radial-gradient(900px 700px at 0% 100%, {c1}, transparent 70%),
     radial-gradient(800px 600px at 100% 0%, {c2}cc, transparent 70%), radial-gradient(500px 400px at 100% 100%, {c3}88, transparent 70%); }}
  .grille {{ position: absolute; inset: 0; background-image: linear-gradient(rgba(255,255,255,.06) 1px, transparent 1px),
     linear-gradient(90deg, rgba(255,255,255,.06) 1px, transparent 1px); background-size: 56px 56px; }}
  .capture {{ position: absolute; right: -170px; top: 130px; width: 720px; border-radius: 20px; overflow: hidden; transform: rotate(5deg);
     box-shadow: 0 40px 80px -20px rgba(0,0,0,.75), 0 0 0 6px rgba(255,255,255,.95); background: #fff; }}
  .capture img {{ display: block; width: 100%; }}
  .etiquette {{ position: absolute; right: 50px; top: 480px; transform: rotate(-6deg); background: {fe}; color: {te};
     font-size: 46px; font-weight: 800; padding: 14px 28px; border-radius: 18px; box-shadow: 0 18px 40px -10px rgba(0,0,0,.6), 0 0 0 5px #fff; }}
  .texte {{ position: absolute; left: 56px; top: 150px; width: 640px; }}
  .tete {{ display: inline-flex; align-items: center; gap: 14px; background: rgba(10,15,31,.72); padding: 10px 20px 10px 10px;
     border-radius: 999px; box-shadow: inset 0 0 0 2px rgba(255,255,255,.18); font-size: 30px; font-weight: 800; position: absolute; left: 50px; top: 46px; }}
  .tete img {{ width: 52px; height: 52px; border-radius: 14px; }}
  .tete img.logo-seul {{ width: 210px; height: auto; border-radius: 0; margin-left: 10px; }}
  h1 {{ white-space: nowrap; font-size: 86px; line-height: 1.02; font-weight: 800; letter-spacing: -.035em;
     text-shadow: 0 6px 0 rgba(0,0,0,.35), 0 18px 40px rgba(0,0,0,.45); }}
  .fort {{ color: {L["surligne"]}; }}
  .marque {{ position: absolute; left: 56px; bottom: 40px; width: 190px; opacity: .95; }}
</style></head><body>
  <div class="fond"></div><div class="grille"></div>
  <div class="capture"><img src="{L["capture"][langue]}"></div>
  <div class="etiquette">{etiquette[langue]}</div>
  <div class="tete">{entete}</div>
  <div class="texte"><h1>{texte}</h1></div>
  {'' if not L["icone"] else f'<img class="marque" src="{A / "vorelik-logo.png"}" alt="VORELIK">'}
</body></html>"""

sortie = Path(sys.argv[1])
for cle, logiciel, textes, etiquette, couleur in MINIATURES:
    for langue in ("fr", "en"):
        (sortie / f"{cle}-{langue}.html").write_text(page(cle, logiciel, textes, etiquette, couleur, langue))
print("ok")
