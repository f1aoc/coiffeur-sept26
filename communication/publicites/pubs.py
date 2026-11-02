"""Visuels publicitaires Meta (Facebook / Instagram), français et anglais : carré 1080 × 1080 et vertical 1080 × 1920.
Règles publicitaires de Meta : aucune mention de Facebook ou d'Instagram dans l'image (captures sans « Facebook seulement »),
promesse mesurée (« prospects » et non « clients »)."""
import sys
from pathlib import Path
DOSSIER = Path(__file__).parent
sys.path.insert(0, "/tmp/claude-0/-home-user-audit-express/52f218e2-7736-53dd-a410-3e4060e5517d/scratchpad/facebook")
sortie = Path(sys.argv[1])
sys.argv = sys.argv[:1]
from facebook import ICONES, publication  # noqa: E402
from stories import story  # noqa: E402

CAP = {"fr": DOSSIER / "capture-pub-fr.png", "en": DOSSIER / "capture-pub-en.png"}
PUBS = {
    "fr": [
        ("essai", dict(couleur="btl", titre='<span class="jaune">10 prospects</span><br>dans votre ville.<br><span class="jaune">Gratuit.</span>',
                       sous="Choisissez un métier et une ville : recevez par e-mail les 10 commerces sans site web les plus établis.",
                       bouton="Recevoir mes prospects", etiquette=("100 % gratuit", "#FDE68A", "#1E1B4B"), nom="Essai gratuit")),
        ("sans-site", dict(couleur="btl", titre='10 commerces<br><span class="jaune">sans site web</span><br>en 2 minutes',
                           sous="Par métier et par ville, avec téléphone et adresse, prêts à appeler.",
                           bouton="Essai gratuit", etiquette=("✖ Aucun site", "#DB2777", "#fff"), nom="BridgeToLeads")),
        ("trouver-client", dict(couleur="vorelik", titre='Le plus dur,<br>c\'est de trouver<br><span class="jaune">le client.</span>',
                                sous="Recevez 10 commerces de votre ville qui n'ont pas de site web. Gratuitement.",
                                bouton="Essayer gratuitement", etiquette=("Testez gratuitement", "#FDE68A", "#1E1B4B"), nom="BridgeToLeads")),
    ],
    "en": [
        ("trial", dict(couleur="btl", titre='Get <span class="jaune">10 leads</span><br>in your city.<br><span class="jaune">Free.</span>',
                       sous="Pick a business type and a city: get the 10 most established businesses with no website by email.",
                       bouton="Get my free leads", etiquette=("100% free", "#FDE68A", "#1E1B4B"), nom="Free trial")),
        ("no-website", dict(couleur="btl", titre='10 businesses<br><span class="jaune">with no website</span><br>in 2 minutes',
                            sous="By business type and city, with phone and address, ready to call.",
                            bouton="Free trial", etiquette=("✖ No website", "#DB2777", "#fff"), nom="BridgeToLeads")),
        ("find-client", dict(couleur="vorelik", titre='The hard part<br>is finding<br><span class="jaune">the client.</span>',
                             sous="Get 10 businesses in your city with no website. For free.",
                             bouton="Try it free", etiquette=("Try it free", "#FDE68A", "#1E1B4B"), nom="BridgeToLeads")),
    ],
}
for langue, pubs in PUBS.items():
    for i, (cle, a) in enumerate(pubs, 1):
        commun = dict(couleur=a["couleur"], titre=a["titre"], sous=a["sous"], bouton=a["bouton"] + " →", etiquette=a["etiquette"],
                      capture=CAP[langue], icone=ICONES["btl"], nom=a["nom"])
        carre = publication(cle, langue=langue, hauteur=1080, **commun).replace("<html", '<html data-taille="1080x1080"', 1)
        (sortie / f"vorelik-pub-{langue}-{i}-{cle}-carre.html").write_text(carre)
        commun["bouton"] = a["bouton"]
        (sortie / f"vorelik-pub-{langue}-{i}-{cle}-vertical.html").write_text(story(langue=langue, **commun))
print("ok")
