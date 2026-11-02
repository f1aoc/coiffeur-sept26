"""Stories Facebook / Instagram VORELIK (anglais et français), 1080 × 1920.
Zone sûre : ni texte ni bouton dans les 260 px du haut (nom de la page) ni les 360 px du bas (barre de réponse)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from facebook import A, BASE, CAPTURES, ICONES, LOGO, NOMS, fond  # noqa: E402

LISTE = {"en": (("btl", "BridgeToLeads", "Businesses with no website"), ("cds", "Site Hunter", "Broken or outdated websites"),
                ("aex", "Audit Express", "Audits that win deals")),
         "fr": (("btl", "BridgeToLeads", "Les commerces sans site web"), ("cds", "Chasseur de sites", "Les sites cassés ou dépassés"),
                ("aex", "Audit express", "Un audit qui fait signer"))}
CAPTURES_FR = {"btl": A / "bridgetoleads-apercu.jpg", "cds": A / "chasseur-apercu.jpg", "aex": A / "audit-express-apercu.jpg"}

def story(couleur, titre, sous, bouton, etiquette=None, capture=None, icone=None, nom=None, liste=False, langue="en"):
    tete = (f'<div class="pastille" style="font-size:34px"><img src="{icone}" style="width:62px;height:62px">{nom}</div>' if icone
            else f'<img src="{LOGO}" style="width:330px;display:block">')
    milieu = ""
    if capture:
        milieu = (f'<div class="cadre"><div class="fenetre" style="position:relative;width:720px;transform:rotate(-3deg)"><img src="{capture}"></div>'
                  + (f'<div class="etiquette" style="right:10px;bottom:-40px;transform:rotate(5deg);background:{etiquette[1]};color:{etiquette[2]};font-size:46px">{etiquette[0]}</div>' if etiquette else "")
                  + "</div>")
    if liste:
        milieu = '<div class="liste">' + "".join(
            f'<div><img src="{ICONES[k]}"><p><b>{n}</b><span>{t}</span></p></div>' for k, n, t in LISTE[langue]) + "</div>"
    return f"""<!doctype html><html lang="{langue}" data-taille="1080x1920"><head><meta charset="utf-8">{BASE}<style>
  html, body {{ width: 1080px; height: 1920px; }}
  .zone {{ position: absolute; left: 70px; right: 70px; top: 270px; bottom: 380px; display: flex; flex-direction: column; gap: 34px; }}
  h1 {{ font-size: 96px; white-space: nowrap; line-height: 1.0; letter-spacing: -.035em; text-shadow: 0 6px 0 rgba(0,0,0,.3), 0 18px 40px rgba(0,0,0,.45); }}
  .sous {{ font-size: 34px; line-height: 1.35; color: #DDE2F2; font-weight: 600; }}
  .cadre {{ position: relative; margin: 4px 0 20px; }}
  .liste {{ display: flex; flex-direction: column; gap: 22px; }}
  .liste div {{ display: flex; align-items: center; gap: 22px; background: rgba(255,255,255,.09); padding: 22px 26px 22px 22px; border-radius: 26px;
     box-shadow: inset 0 0 0 1px rgba(255,255,255,.18); }}
  .liste img {{ width: 84px; height: 84px; border-radius: 20px; }}
  .liste p {{ margin: 0; }} .liste b {{ display: block; font-size: 40px; }} .liste span {{ display: block; font-size: 27px; color: #C3CAE0; }}
  .bas {{ margin-top: auto; display: flex; flex-direction: column; align-items: center; gap: 18px; }}
  .bouton {{ font-size: 38px; padding: 22px 44px; }}
  .indice {{ font-size: 26px; color: #C3CAE0; font-weight: 600; }}
</style></head><body>{fond(couleur)}
  <div class="zone">
    <div>{tete}</div>
    <h1>{titre}</h1>
    <p class="sous">{sous}</p>
    {milieu}
    <div class="bas"><span class="bouton">{bouton}</span></div>
  </div>
</body></html>"""

STORIES = [
    ("vorelik-story-1-presentation", dict(couleur="vorelik", titre='Web designers:<br>find your<br><span class="jaune">next clients.</span>',
        sous="Three simple apps that find local businesses needing a website.", bouton="vorelik.com/en", liste=True)),
    ("vorelik-story-2-bridgetoleads", dict(couleur="btl", titre='10 clients<br><span class="jaune">with no website</span><br>in 2 minutes',
        sous="Local businesses with no website, straight from Google Maps.", bouton="Try it free",
        etiquette=("✖ No website", "#DB2777", "#fff"), capture=CAPTURES["btl"], icone=ICONES["btl"], nom=NOMS["btl"])),
    ("vorelik-story-3-site-hunter", dict(couleur="cds", titre='Their site is<br><span class="jaune">broken.</span><br>Fix it for them',
        sous="Broken, expired or outdated websites, with proof.", bouton="vorelik.com/en",
        etiquette=("⚠ Broken site", "#DC2626", "#fff"), capture=CAPTURES["cds"], icone=ICONES["cds"], nom=NOMS["cds"])),
    ("vorelik-story-4-audit-express", dict(couleur="aex", titre='The audit<br><span class="jaune">that wins deals</span><br>in 1 minute',
        sous="A to F grade and a branded PDF report.", bouton="vorelik.com/en",
        etiquette=("Grade: C", "#DC2626", "#fff"), capture=CAPTURES["aex"], icone=ICONES["aex"], nom=NOMS["aex"])),
    ("vorelik-story-5-essai-gratuit", dict(couleur="btl", titre='Get <span class="jaune">10 leads</span><br>in your city.<br><span class="jaune">Free.</span>',
        sous="We email you the 10 most established businesses with no website.", bouton="Get my free leads",
        etiquette=("100% free", "#FDE68A", "#1E1B4B"), capture=CAPTURES["btl"], icone=ICONES["btl"], nom="Free trial")),
]
STORIES_FR = [
    ("vorelik-story-fr-1-presentation", dict(couleur="vorelik", titre='Trouvez vos<br><span class="jaune">prochains<br>clients.</span>',
        sous="Trois logiciels simples qui trouvent les commerces qui ont besoin d'un site web.", bouton="vorelik.com", liste=True, langue="fr")),
    ("vorelik-story-fr-2-bridgetoleads", dict(couleur="btl", titre='10 clients<br><span class="jaune">sans site web</span><br>en 2 minutes',
        sous="Les commerces sans site web, directement depuis Google Maps.", bouton="Essai gratuit",
        etiquette=("✖ Aucun site", "#DB2777", "#fff"), capture=CAPTURES_FR["btl"], icone=ICONES["btl"], nom="BridgeToLeads", langue="fr")),
    ("vorelik-story-fr-3-chasseur-de-sites", dict(couleur="cds", titre='Leur site est<br><span class="jaune">cassé.</span><br>Refaites-le !',
        sous="Sites cassés, expirés ou dépassés, preuves à l'appui.", bouton="vorelik.com",
        etiquette=("⚠ Site cassé", "#DC2626", "#fff"), capture=CAPTURES_FR["cds"], icone=ICONES["cds"], nom="Chasseur de sites", langue="fr")),
    ("vorelik-story-fr-4-audit-express", dict(couleur="aex", titre="L'audit qui<br><span class=\"jaune\">fait signer</span><br>en 1 minute",
        sous="Une note de A à F et un rapport PDF à votre marque.", bouton="vorelik.com",
        etiquette=("Note : C", "#DC2626", "#fff"), capture=CAPTURES_FR["aex"], icone=ICONES["aex"], nom="Audit express", langue="fr")),
    ("vorelik-story-fr-5-essai-gratuit", dict(couleur="btl", titre='<span class="jaune">10 prospects</span><br>dans votre ville.<br><span class="jaune">Gratuit.</span>',
        sous="Nous vous envoyons par e-mail les 10 commerces sans site web les plus établis.", bouton="Recevoir mes prospects",
        etiquette=("100 % gratuit", "#FDE68A", "#1E1B4B"), capture=CAPTURES_FR["btl"], icone=ICONES["btl"], nom="Essai gratuit", langue="fr")),
]
sortie = Path(sys.argv[1])
for nom, args in STORIES + STORIES_FR:
    (sortie / f"{nom}.html").write_text(story(**args))
print("ok")
