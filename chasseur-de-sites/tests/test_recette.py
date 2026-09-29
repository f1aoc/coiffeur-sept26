"""Recette §7.2 : 30 sites étiquetés à la main (10 cassés, 10 obsolètes, 10 corrects), ≥ 90 % bien classés.

Les pages sont générées dans un dossier temporaire et servies en local ; les 4 vrais analyseurs
tournent (Chromium compris). Même mécanique que « chasseur recette jeu.csv » sur de vrais sites.
"""

from __future__ import annotations

import shutil
import socket

import pytest

from chasseur.recette import OBJECTIF, afficher, recetter
from serveur_local import PAGES, ServeurLocal

pytestmark = pytest.mark.usefixtures("exige_chromium", "sans_proxy")

METIERS = ["Coiffeur", "Boulangerie", "Plombier", "Fleuriste", "Garage", "Institut", "Pizzeria", "Menuisier", "Opticien", "Librairie"]


def page_correcte(i: int, metier: str) -> str:
    extras = [
        "", '<form action="/contact" method="post"><input name="email"><button>Envoyer</button></form>',
        "<p>Actualité du 12 septembre 2026 : nouveaux horaires d'automne.</p>", "",
    ][i % 4]
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{metier} Martin {i} – Avignon</title>
<meta name="description" content="{metier} à Avignon : accueil du mardi au samedi, devis gratuit, conseils personnalisés.">
<style>body{{font-family:sans-serif;margin:0;padding:1rem}}img{{max-width:100%}}</style></head>
<body><header><h1>{metier} Martin</h1><a href="tel:+33490000{i:03d}">04 90 00 0{i % 10} 00</a></header>
<main><p>Bienvenue chez {metier} Martin, installé à Avignon depuis vingt ans. Notre équipe vous accueille du mardi au
samedi avec ou sans rendez-vous. Nous travaillons avec des fournisseurs locaux et prenons le temps de vous conseiller
pour chaque projet, petit ou grand. Consultez nos tarifs, nos horaires et venez nous rencontrer en boutique.</p>
<p>Horaires : du mardi au vendredi de 9 h à 19 h, le samedi de 9 h à 17 h. Parking gratuit devant la boutique.</p>
{extras}</main><footer>© 2026 {metier} Martin – 12 rue de la République, 84000 Avignon</footer></body></html>"""


def page_obsolete(i: int, metier: str) -> str:
    """Tableaux à largeur fixe, sans viewport, et 1 à 3 autres signes d'âge selon la page.

    Au moins 500 caractères de texte : en dessous, le cahier des charges parle de page blanche (§3.2)."""
    annee = 2009 + i % 6
    jquery = '<script src="js/jquery-1.4.2.min.js"></script>' if i % 2 == 0 else ""
    generateur = '<meta name="generator" content="WordPress 4.9">' if i % 3 == 0 else ""
    description = "" if i % 2 else f'<meta name="description" content="{metier} Dupont, artisan depuis 1985.">'
    return f"""<html><head><title>{metier} Dupont</title>{description}{generateur}{jquery}</head>
<body bgcolor="#ffffff"><table width="1000" border="0"><tr><td>
<font face="Verdana" size="4">{metier} Dupont, depuis 1985</font>
<table width="1000"><tr><td width="700"><font face="Verdana" size="2">Bienvenue sur notre site internet. Nous vous
proposons nos services de qualité dans toute la région. Notre entreprise familiale est à votre écoute pour tous vos
projets. N'hésitez pas à nous rendre visite dans notre magasin ou à nous téléphoner pour un devis gratuit.
<br><br>Nos services : conseil, vente, installation et dépannage. Nous intervenons à Avignon, Carpentras, Cavaillon,
Orange et dans tous les villages alentour. Ouvert du lundi au samedi de 8 h à 12 h et de 14 h à 18 h 30.
<br><br><b>Nouveau !</b> Découvrez notre catalogue au magasin.</font></td>
<td width="300"><font size="1">Tél : 04 90 00 00 {i:02d}</font></td></tr></table>
<font size="1">Copyright © {annee} {metier} Dupont - Tous droits réservés - Meilleure visualisation en 1024x768</font>
</td></tr></table></body></html>"""


def port_ferme() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def site_recette(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("recette")
    for i, metier in enumerate(METIERS):
        (dossier / f"correct-{i}.html").write_text(page_correcte(i, metier), encoding="utf-8")
        (dossier / f"obsolete-{i}.html").write_text(page_obsolete(i, metier), encoding="utf-8")
    for nom in ("parking.html", "blanche.html", "erreur_php.html", "maintenance.html", "pirate.html"):
        shutil.copy(PAGES / nom, dossier / nom)
    with ServeurLocal(dossier) as serveur:
        yield serveur


def jeu_etiquete(serveur, chemin):
    lignes = [("Domaine parqué", serveur.url("parking.html")), ("Page blanche", serveur.url("blanche.html")),
              ("Erreur PHP", serveur.url("erreur_php.html")), ("En maintenance", serveur.url("maintenance.html")),
              ("Site piraté", serveur.url("pirate.html")), ("Accueil introuvable", serveur.url("disparu.html")),
              ("Erreur serveur", serveur.url("statut/500")), ("Page supprimée", serveur.url("statut/410")),
              ("Domaine inexistant", "http://salon-disparu-recette.invalid/"),
              ("Serveur éteint", f"http://127.0.0.1:{port_ferme()}/")]
    csv = ["nom;url;attendu"] + [f"{nom};{url};Cassé" for nom, url in lignes]
    csv += [f"{m} Dupont;{serveur.url(f'obsolete-{i}.html')};Obsolète" for i, m in enumerate(METIERS)]
    csv += [f"{m} Martin;{serveur.url(f'correct-{i}.html')};Correct" for i, m in enumerate(METIERS)]
    chemin.write_text("\n".join(csv) + "\n", encoding="utf-8")
    return chemin


async def test_taux_de_bon_classement(site_recette, config, tmp_path):
    config.timeout = 5  # le serveur éteint et le domaine inexistant échouent vite de toute façon
    jeu = jeu_etiquete(site_recette, tmp_path / "jeu.csv")
    recette = await recetter(jeu, config)
    print("\n" + afficher(recette))
    assert len(recette.lignes) == 30
    assert recette.taux >= OBJECTIF, afficher(recette)


def test_commande_recette(site_recette, tmp_path, capsys, monkeypatch):
    from chasseur import cli
    from conftest import RACINE

    monkeypatch.chdir(tmp_path)  # les captures vont dans ./captures

    jeu = tmp_path / "petit.csv"
    jeu.write_text(f"nom;url;attendu\nA;{site_recette.url('correct-0.html')};Correct\nB;{site_recette.url('parking.html')};cassé\n",
                   encoding="utf-8")
    assert cli.main(["recette", str(jeu), "-c", str(RACINE / "config.yaml")]) == 0
    sortie = capsys.readouterr().out
    assert "Taux de bon classement : 100 % (2/2)" in sortie and "ATTEINT" in sortie

    jeu.write_text("nom;url\nA;https://a.test\n", encoding="utf-8")
    assert cli.main(["recette", str(jeu)]) == 2
    assert "Colonne « attendu » absente" in capsys.readouterr().err


# --- Certificat expiré : vraie négociation TLS en local (§7.2, 2e critère) ------------------------

def certificats_de_test(dossier):
    """Une autorité de test et un certificat « localhost » expiré depuis le 1er janvier 2025."""
    from datetime import datetime, timezone

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    def nom(cn):
        return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])

    cle_ac, cle = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    ac = (x509.CertificateBuilder().subject_name(nom("AC de test")).issuer_name(nom("AC de test"))
          .public_key(cle_ac.public_key()).serial_number(1)
          .not_valid_before(datetime(2020, 1, 1, tzinfo=timezone.utc)).not_valid_after(datetime(2040, 1, 1, tzinfo=timezone.utc))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(cle_ac, hashes.SHA256()))
    site = (x509.CertificateBuilder().subject_name(nom("localhost")).issuer_name(ac.subject)
            .public_key(cle.public_key()).serial_number(2)
            .not_valid_before(datetime(2023, 1, 1, tzinfo=timezone.utc)).not_valid_after(datetime(2025, 1, 1, tzinfo=timezone.utc))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False).sign(cle_ac, hashes.SHA256()))
    pem = serialization.Encoding.PEM
    (dossier / "ac.pem").write_bytes(ac.public_bytes(pem))
    (dossier / "site.pem").write_bytes(site.public_bytes(pem) + cle.private_bytes(
        pem, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    return dossier / "ac.pem", dossier / "site.pem"


async def test_certificat_expire_detecte_avec_sa_preuve(tmp_path, monkeypatch, config, client):
    import asyncio
    import ssl

    from chasseur.analyzers import reseau
    from chasseur.modeles import Prospect

    ac, site = certificats_de_test(tmp_path)
    contexte_serveur = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    contexte_serveur.load_cert_chain(site)

    async def repondre(lecteur, ecrivain):  # répond « 200 » à toute requête HTTP
        try:
            await lecteur.readuntil(b"\r\n\r\n")
            ecrivain.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: 20\r\nConnection: close\r\n\r\n<h1>Salon Test</h1>\n")
            await ecrivain.drain()
        except (OSError, asyncio.IncompleteReadError, ssl.SSLError):
            pass  # la simple vérification du certificat ferme la connexion sans requête
        ecrivain.close()

    serveur = await asyncio.start_server(repondre, "127.0.0.1", 0, ssl=contexte_serveur)
    port = serveur.sockets[0].getsockname()[1]
    origine = ssl.create_default_context

    def contexte_avec_ac(*args, **kwargs):  # l'AC de test remplace les autorités du système
        contexte = origine(*args, **kwargs)
        contexte.load_verify_locations(ac)
        return contexte

    monkeypatch.setattr(reseau.ssl, "create_default_context", contexte_avec_ac)
    async with serveur:
        info = await reseau.verifier_certificat("localhost", port, timeout=5)
        assert (info.statut, info.expire) == ("invalide", True) and "expired" in info.erreur

        # Même vérification dans l'analyseur complet : constat SSL_EXPIRE avec sa preuve
        analyseur = reseau.AnalyseurReseau(config, verificateur_ssl=lambda h, p, t: reseau.verifier_certificat("localhost", port, t))
        rapport = await analyseur.analyser(Prospect(nom="Salon", url=f"https://localhost:{port}/"), client)
    constat = next((c for c in rapport if c.code == "SSL_EXPIRE"), None)
    assert constat, [(c.code, c.preuve) for c in rapport]
    assert constat.gravite == "critique" and "expired" in constat.preuve
