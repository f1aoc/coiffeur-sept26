"""Kit Facebook VORELIK : couverture 1640 × 924 (anglais) et visuels de publication 1080 × 1080 (anglais et français)."""
import sys
from pathlib import Path

R = Path("/home/user/coiffeur-sept26")
A = R / "vitrine/assets"
EN = R / "vitrine-en"
POLICE = A / "polices/polices.css"
LOGO = A / "vorelik-logo.png"
ICONES = {"btl": A / "bridgetoleads-icone.png", "cds": A / "chasseur-icone.png", "aex": A / "audit-express-icone.png"}
CAPTURES = {"btl": EN / "bridgetoleads/assets/app-screenshot.png", "cds": EN / "site-hunter/assets/app-screenshot.jpg",
            "aex": EN / "audit-express/assets/app-screenshot.jpg"}
NOMS = {"btl": "BridgeToLeads", "cds": "Site Hunter", "aex": "Audit Express"}
FONDS = {"btl": ("#7C3AED", "#EC4899", "#F97316"), "cds": ("#1F5FBF", "#0EA5E9", "#F97316"),
         "aex": ("#059669", "#0E7490", "#F97316"), "vorelik": ("#7C3AED", "#EC4899", "#0EA5E9")}
BASE = f"""<link href="{POLICE}" rel="stylesheet"><style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ position: relative; overflow: hidden; font-family: "Plus Jakarta Sans", sans-serif; color: #fff; background: #0A0F1F; }}
  .grille {{ position: absolute; inset: 0; background-image: linear-gradient(rgba(255,255,255,.055) 1px, transparent 1px),
     linear-gradient(90deg, rgba(255,255,255,.055) 1px, transparent 1px); background-size: 60px 60px; }}
  .aurora {{ background: linear-gradient(100deg, #A78BFA 0%, #F472B6 32%, #FB923C 58%, #38BDF8 85%); -webkit-background-clip: text; background-clip: text; color: transparent; }}
  .jaune {{ color: #FDE68A; }}
  .fenetre {{ position: absolute; border-radius: 20px; overflow: hidden; background: #fff; box-shadow: 0 40px 80px -25px rgba(0,0,0,.75), 0 0 0 6px rgba(255,255,255,.95); }}
  .fenetre img {{ display: block; width: 100%; }}
  .pastille {{ display: inline-flex; align-items: center; gap: 14px; background: rgba(10,15,31,.72); padding: 10px 22px 10px 10px; border-radius: 999px;
     box-shadow: inset 0 0 0 2px rgba(255,255,255,.18); font-weight: 800; }}
  .pastille img {{ width: 54px; height: 54px; border-radius: 14px; }}
  .bouton {{ display: inline-block; background: #fff; color: #1E1B4B; font-weight: 800; border-radius: 999px; padding: 18px 34px; box-shadow: 0 18px 40px -12px rgba(0,0,0,.6); }}
  .etiquette {{ position: absolute; font-weight: 800; padding: 14px 28px; border-radius: 18px; box-shadow: 0 18px 40px -10px rgba(0,0,0,.6), 0 0 0 5px #fff; }}
</style>"""

def fond(c):
    c1, c2, c3 = FONDS[c]
    return (f'<div style="position:absolute;inset:0;background:radial-gradient(70% 70% at 0% 100%, {c1}, transparent 70%),'
            f'radial-gradient(60% 60% at 100% 0%, {c2}cc, transparent 70%),radial-gradient(45% 45% at 100% 100%, {c3}88, transparent 70%)"></div>'
            '<div class="grille"></div>')

COUVERTURE = {
    "en": dict(apps=(("btl", "BridgeToLeads", "Businesses with no website"), ("cds", "Site Hunter", "Broken or outdated websites"),
                     ("aex", "Audit Express", "Audits that win deals")),
               titre='Software that finds<br><span class="aurora">your next clients.</span>',
               pied='<span class="aurora">vorelik.com/en</span> · Windows &amp; Mac · One-time payment', captures=None),
    "fr": dict(apps=(("btl", "BridgeToLeads", "Les commerces sans site web"), ("cds", "Chasseur de sites", "Les sites cassés ou dépassés"),
                     ("aex", "Audit express", "Un audit qui fait signer")),
               titre='Des logiciels qui trouvent<br><span class="aurora">vos prochains clients.</span>',
               pied='<span class="aurora">vorelik.com</span> · Windows et Mac · Paiement unique', captures="fr"),
}

def couverture(langue="en"):
    T = COUVERTURE[langue]
    cap = CAPTURES if langue == "en" else {"btl": A / "bridgetoleads-apercu.jpg", "cds": A / "chasseur-apercu.jpg"}
    apps = "".join(f'<div class="app"><img src="{ICONES[k]}"><div><b>{n}</b><span>{t}</span></div></div>' for k, n, t in T["apps"])
    return f"""<!doctype html><html lang="{langue}"><head><meta charset="utf-8">{BASE}<style>
  html, body {{ width: 1640px; height: 924px; }}
  .f1 {{ left: -150px; top: 250px; width: 560px; transform: rotate(-7deg); opacity: .85; }}
  .f2 {{ right: -170px; top: 230px; width: 560px; transform: rotate(6deg); opacity: .85; }}
  .voile {{ position: absolute; inset: 0; background: radial-gradient(ellipse 640px 300px at 50% 50%, rgba(10,15,31,.93), rgba(10,15,31,.6) 70%, transparent); }}
  /* zone sûre : visible sur ordinateur (bande centrale) et sur téléphone */
  .zone {{ position: absolute; left: 330px; right: 330px; top: 190px; bottom: 190px; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }}
  .logo {{ width: 280px; margin-bottom: 18px; }}
  h1 {{ font-size: 70px; line-height: 1.04; letter-spacing: -.03em; }}
  .apps {{ display: flex; gap: 16px; margin-top: 30px; }}
  .app {{ display: flex; align-items: center; gap: 12px; text-align: left; background: rgba(255,255,255,.08); padding: 12px 18px 12px 12px; border-radius: 18px; box-shadow: inset 0 0 0 1px rgba(255,255,255,.16); }}
  .app img {{ width: 48px; height: 48px; border-radius: 12px; }}
  .app b {{ display: block; font-size: 22px; }} .app span {{ display: block; font-size: 15px; color: #C3CAE0; }}
  .site {{ margin-top: 24px; font-size: 26px; font-weight: 800; }}
</style></head><body>{fond("vorelik")}
  <div class="fenetre f1"><img src="{cap['btl']}"></div><div class="fenetre f2"><img src="{cap['cds']}"></div>
  <div class="voile"></div>
  <div class="zone"><img class="logo" src="{LOGO}"><h1>{T["titre"]}</h1>
    <div class="apps">{apps}</div><div class="site">{T["pied"]}</div></div>
</body></html>"""

def publication(cle, couleur, titre, sous, bouton, etiquette=None, capture=None, icone=None, nom=None, liste=False, langue="en"):
    tete = (f'<div class="pastille" style="position:absolute;left:60px;top:60px;font-size:30px"><img src="{icone}">{nom}</div>' if icone
            else f'<img src="{LOGO}" style="position:absolute;left:60px;top:58px;width:250px">')
    fen = f'<div class="fenetre" style="right:-120px;bottom:150px;width:640px;transform:rotate(-4deg)"><img src="{capture}"></div>' if capture else ""
    eti = (f'<div class="etiquette" style="right:70px;bottom:120px;transform:rotate(5deg);background:{etiquette[1]};color:{etiquette[2]};font-size:44px">{etiquette[0]}</div>'
           if etiquette else "")
    return f"""<!doctype html><html><head><meta charset="utf-8">{BASE}<style>
  html, body {{ width: 1080px; height: 1080px; }}
  h1 {{ position: absolute; left: 60px; top: 170px; width: 960px; font-size: 92px; line-height: 1.02; letter-spacing: -.035em;
       text-shadow: 0 6px 0 rgba(0,0,0,.3), 0 18px 40px rgba(0,0,0,.45); }}
  .sous {{ position: absolute; left: 60px; top: 520px; width: 470px; font-size: 30px; line-height: 1.35; color: #DDE2F2; font-weight: 600; }}
  .bas {{ position: absolute; left: 60px; bottom: 60px; display: flex; align-items: center; gap: 24px; }}
  .bouton {{ font-size: 30px; }}
  .marque {{ position: absolute; right: 60px; bottom: 58px; width: 200px; }}
  .liste {{ position: absolute; right: 60px; top: 520px; width: 420px; display: flex; flex-direction: column; gap: 16px; }}
  .liste div {{ display: flex; align-items: center; gap: 16px; background: rgba(255,255,255,.09); padding: 14px 18px 14px 14px; border-radius: 20px;
     box-shadow: inset 0 0 0 1px rgba(255,255,255,.18); }}
  .liste img {{ width: 60px; height: 60px; border-radius: 15px; }}
  .liste b {{ display: block; font-size: 28px; }} .liste span {{ display: block; font-size: 19px; color: #C3CAE0; }}
</style></head><body>{fond(couleur)}{fen}{eti}{tete}{LISTES[langue] if liste else ""}
  <h1>{titre}</h1><p class="sous">{sous}</p>
  <div class="bas"><span class="bouton">{bouton}</span></div>
  {'' if not icone else f'<img class="marque" src="{LOGO}" style="right:auto;left:60px;bottom:150px;width:0">'}
</body></html>"""

def _liste(elements):
    return '<div class="liste">' + "".join(f'<div><img src="{ICONES[k]}"><p><b>{n}</b><span>{t}</span></p></div>' for k, n, t in elements) + "</div>"

LISTES = {
    "en": _liste((("btl", "BridgeToLeads", "Businesses with no website"), ("cds", "Site Hunter", "Broken or outdated websites"),
                  ("aex", "Audit Express", "Audits that win deals"))),
    "fr": _liste((("btl", "BridgeToLeads", "Les commerces sans site web"), ("cds", "Chasseur de sites", "Les sites cassés ou dépassés"),
                  ("aex", "Audit express", "Un audit qui fait signer"))),
}
CAPTURES_FR = {"btl": A / "bridgetoleads-apercu.jpg", "cds": A / "chasseur-apercu.jpg", "aex": A / "audit-express-apercu.jpg"}

def visuels():
    yield "vorelik-facebook-couverture", couverture(), (1640, 924)
    yield "vorelik-facebook-couverture-fr", couverture("fr"), (1640, 924)
    yield "vorelik-facebook-post-1-presentation", publication("intro", "vorelik",
        'Web designers:<br>find your<br><span class="jaune">next clients.</span>',
        "Three simple apps that find local businesses needing a website, and help you win them over.",
        "vorelik.com/en →", liste=True), (1080, 1080)
    yield "vorelik-facebook-post-2-bridgetoleads", publication("btl", "btl",
        '10 clients<br><span class="jaune">with no website</span><br>in 2 minutes',
        "BridgeToLeads finds local businesses with no website on Google Maps, ready to call.",
        "Try it free →", ("✖ No website", "#DB2777", "#fff"), CAPTURES["btl"], ICONES["btl"], NOMS["btl"]), (1080, 1080)
    yield "vorelik-facebook-post-3-site-hunter", publication("cds", "cds",
        'Their site<br>is <span class="jaune">broken.</span><br>Fix it for them',
        "Site Hunter spots broken, expired or outdated websites, with proof and a PDF report.",
        "vorelik.com/en →", ("⚠ Broken site", "#DC2626", "#fff"), CAPTURES["cds"], ICONES["cds"], NOMS["cds"]), (1080, 1080)
    yield "vorelik-facebook-post-4-audit-express", publication("aex", "aex",
        'The audit<br><span class="jaune">that wins deals</span><br>in 1 minute',
        "Audit Express grades any website from A to F and builds a branded PDF report.",
        "vorelik.com/en →", ("Grade: C", "#DC2626", "#fff"), CAPTURES["aex"], ICONES["aex"], NOMS["aex"]), (1080, 1080)
    yield "vorelik-facebook-post-5-essai-gratuit", publication("trial", "btl",
        'Get <span class="jaune">10 leads</span><br>in your city.<br><span class="jaune">Free.</span>',
        "Pick a business type and a city: we email you the 10 most established businesses with no website.",
        "vorelik.com/en/trial →", ("100% free", "#FDE68A", "#1E1B4B"), CAPTURES["btl"], ICONES["btl"], "Free trial"), (1080, 1080)

def visuels_fr():
    yield "vorelik-facebook-post-fr-1-presentation", publication("intro", "vorelik",
        'Créateurs de sites :<br>trouvez vos<br><span class="jaune">prochains clients.</span>',
        "Trois logiciels simples qui trouvent les commerces qui ont besoin d'un site web, et vous aident à les convaincre.",
        "vorelik.com →", liste=True, langue="fr"), (1080, 1080)
    yield "vorelik-facebook-post-fr-2-bridgetoleads", publication("btl", "btl",
        '10 clients<br><span class="jaune">sans site web</span><br>en 2 minutes',
        "BridgeToLeads trouve sur Google Maps les commerces sans site web, prêts à appeler.",
        "Essai gratuit →", ("✖ Aucun site", "#DB2777", "#fff"), CAPTURES_FR["btl"], ICONES["btl"], "BridgeToLeads", langue="fr"), (1080, 1080)
    yield "vorelik-facebook-post-fr-3-chasseur-de-sites", publication("cds", "cds",
        'Leur site est<br><span class="jaune">cassé.</span><br>Refaites-le !',
        "Chasseur de sites repère les sites en panne, expirés ou dépassés, avec la preuve et un rapport PDF.",
        "vorelik.com →", ("⚠ Site cassé", "#DC2626", "#fff"), CAPTURES_FR["cds"], ICONES["cds"], "Chasseur de sites", langue="fr"), (1080, 1080)
    yield "vorelik-facebook-post-fr-4-audit-express", publication("aex", "aex",
        "L'audit qui<br><span class=\"jaune\">fait signer</span><br>en 1 minute",
        "Audit express note n'importe quel site de A à F et prépare un rapport PDF à votre marque.",
        "vorelik.com →", ("Note : C", "#DC2626", "#fff"), CAPTURES_FR["aex"], ICONES["aex"], "Audit express", langue="fr"), (1080, 1080)
    yield "vorelik-facebook-post-fr-5-essai-gratuit", publication("trial", "btl",
        '<span class="jaune">10 prospects</span><br>dans votre ville.<br><span class="jaune">Gratuit.</span>',
        "Choisissez un métier et une ville : nous vous envoyons les 10 commerces sans site web les plus établis.",
        "vorelik.com/essai →", ("100 % gratuit", "#FDE68A", "#1E1B4B"), CAPTURES_FR["btl"], ICONES["btl"], "Essai gratuit", langue="fr"), (1080, 1080)

sortie = Path(sys.argv[1])
for nom, html, (l, h) in list(visuels()) + list(visuels_fr()):
    (sortie / f"{nom}.html").write_text(html.replace("<html", f'<html data-taille="{l}x{h}"', 1))
print("ok")
