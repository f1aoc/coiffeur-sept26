"""Modèles de messages et textes sans jargon ni chiffres inventés."""

from __future__ import annotations

import re

import pytest

from chasseur.controles import CONTROLE_DU_CODE
from chasseur.reports import messages
from chasseur.reports.textes import TEXTES, date_longue, texte


def test_variables_remplacees():
    valeurs = messages.variables("Salon Léa", "votre site affiche une erreur", "Avignon", "Atelier Web")
    rendu = messages.rendre("{entreprise} à {ville} : {probleme_principal}. — {agence} {inconnue} {ENTREPRISE}", valeurs)
    assert rendu == "Salon Léa à Avignon : votre site affiche une erreur. — Atelier Web {inconnue} {ENTREPRISE}"


def test_valeurs_par_defaut_quand_une_information_manque():
    assert messages.variables("", "", "", "") == {
        "entreprise": "votre entreprise",
        "probleme_principal": "votre site pourrait être modernisé",
        "ville": "votre ville",
        "agence": "[votre agence]",
    }


@pytest.mark.parametrize("modele", messages.MODELES, ids=lambda m: m.id)
def test_modeles_par_defaut(modele):
    utilisees = set(re.findall(r"\{(\w+)\}", modele.defaut))
    assert utilisees <= set(messages.VARIABLES)
    assert {"entreprise", "probleme_principal", "agence"} <= utilisees
    assert re.search(r"non merci|STOP|ne pas vous rappeler", modele.defaut)  # moyen simple de s'opposer (§6.1)
    assert "%" not in modele.defaut and not re.search(r"\d", modele.defaut)  # aucun chiffre ni promesse chiffrée
    rendu = messages.rendre(modele.defaut, messages.variables("Salon Léa", "votre site est lent", "Apt", "Atelier"))
    assert "{" not in rendu and "Salon Léa" in rendu and "votre site est lent" in rendu


def test_sms_court():
    rendu = messages.rendre(messages.PAR_ID["sms"].defaut, messages.variables("Salon Léa", "votre site affiche une erreur", "", "Atelier Web"))
    assert len(rendu) <= 320  # deux SMS au plus


def test_modeles_enregistres_et_retour_au_defaut(stockage):
    with stockage.session() as s:
        assert messages.lire_modeles(s)["sms"] == messages.PAR_ID["sms"].defaut
        messages.ecrire_modele(s, "sms", "Bonjour {entreprise}\r\n")
        s.commit()
        assert messages.lire_modeles(s)["sms"] == "Bonjour {entreprise}"
        messages.ecrire_modele(s, "sms", "   ")  # vide : retour au texte d'origine
        s.commit()
        assert messages.lire_modeles(s)["sms"] == messages.PAR_ID["sms"].defaut


# --- Textes des problèmes ---------------------------------------------------------------


def test_chaque_probleme_a_un_texte():
    assert set(CONTROLE_DU_CODE) - {"URL_INVALIDE"} <= set(TEXTES)


@pytest.mark.parametrize("code", sorted(TEXTES))
def test_textes_sans_jargon_ni_chiffres(code):
    t = TEXTES[code]
    for champ in (t.titre, t.visiteur, t.impact, t.phrase):
        brut = re.sub(r"\{\w+\}", "", champ).replace("années 2000", "")
        assert "%" not in brut and not re.search(r"\d", brut), champ
        for jargon in ("SSL", "HTTP", "DNS", "RDAP", "viewport", "PHP", "jQuery", "meta", "404", "500"):
            assert jargon not in brut, f"{code} : « {jargon} » dans « {champ} »"
        assert champ.strip() and not champ.endswith(" ")


def test_textes_completes_avec_les_mesures():
    mesures = {
        "domaine_expire_le": "2026-08-12", "annee_copyright": "2017", "version_wordpress": "4.9.8",
        "derniere_date": "2018-03-14", "perf_lcp_s": "5.2", "navigateur_url_finale": "https://casino.example/x",
    }
    assert texte("DOMAINE_EXPIRE", mesures).visiteur.startswith("Votre adresse web n'est plus renouvelée depuis le 12 août 2026")
    assert "© 2017" in texte("COPYRIGHT_ANCIEN", mesures).visiteur
    assert "WordPress (4.9.8)" in texte("WORDPRESS_OBSOLETE", mesures).visiteur
    assert "le 14 mars 2018" in texte("ACTUALITES_ANCIENNES", mesures).visiteur
    assert "environ 5,2 secondes" in texte("PERF_LENTE", mesures).visiteur
    assert "(casino.example)" in texte("PIRATAGE_REDIRECTION", mesures).visiteur
    # Sans mesure, les fragments disparaissent proprement
    assert texte("DOMAINE_EXPIRE", {}).visiteur.startswith("Votre adresse web n'est plus renouvelée :")
    assert texte("WORDPRESS_OBSOLETE", {}).visiteur.endswith("version de WordPress.")
    assert texte("SSL_EXPIRE_BIENTOT", {}).visiteur.endswith("expire prochainement.")
    assert texte("INCONNU") is None


@pytest.mark.parametrize("iso, attendu", [("2026-08-12", "12 août 2026"), ("2026-03-01T10:00", "1er mars 2026"), ("", ""), ("n/a", "")])
def test_date_longue(iso, attendu):
    assert date_longue(iso) == attendu
