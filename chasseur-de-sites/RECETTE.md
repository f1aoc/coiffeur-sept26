# Recette – critères d'acceptation (§7.2)

Version 1.0.0 · recette du 28/09/2026 · Linux, Python 3.11, Chromium (Playwright), 10 sites en parallèle.

L'environnement de recette n'a pas d'accès Internet direct : tous les sites testés sont **servis en local**
(pages générées, vraies réponses HTTP, vrai Chromium, vraie négociation TLS) ou **simulés** (réponses DNS/HTTP
enregistrées). La même mesure sur de vrais sites se fait avec `chasseur recette jeu.csv` (voir plus bas).

| # | Critère | Résultat | Preuve |
|---|---|---|---|
| 1 | 30 URL connues (10 cassées, 10 obsolètes, 10 correctes) classées correctement à ≥ 90 % | ✅ **100 %** (30/30) : cassés 10/10, obsolètes 10/10, corrects 10/10, en 12 s | `tests/test_recette.py::test_taux_de_bon_classement` : parking, page blanche, erreur PHP, maintenance, spam caché, 404, 500, 410, domaine inexistant, serveur éteint ; 10 sites anciens (tableaux, sans version mobile, copyright 2009-2014, jQuery 1.4, WordPress 4.9) ; 10 sites récents |
| 2a | Domaine inexistant détecté avec sa preuve | ✅ `DNS_INTROUVABLE`, 40 pts, preuve « résolution DNS de … impossible » | `test_reseau.py::test_dns_introuvable_stoppe_l_analyse` ; `.invalid` réel dans la recette n° 1 |
| 2b | Certificat expiré détecté avec sa preuve | ✅ `SSL_EXPIRE`, critique, preuve « certificate has expired » | `test_recette.py::test_certificat_expire_detecte_avec_sa_preuve` (vrai serveur TLS local, certificat expiré le 01/01/2025) ; `test_reseau.py::test_constats_ssl` (simulé) ; `pytest -m reseau` sur expired.badssl.com (Internet requis) |
| 2c | Page parquée détectée avec sa preuve | ✅ `DOMAINE_PARKING`, 40 pts, preuve = adresse + texte trouvé (« domaine à vendre »…) | `test_domain.py::test_page_de_parking_*`, `test_browser.py::test_page_de_parking_est_quasi_vide`, recette n° 1 |
| 3 | Panne temporaire non classée « cassé » après une seule erreur | ✅ 2 essais : 503 puis 200 → aucun constat ; 500 deux fois → cassé | `test_reseau.py::test_erreur_503_passagere`, `test_deuxieme_essai_reussi`, `test_erreur_500_persistante` (2 appels vérifiés) |
| 4 | 500 sites en moins de 30 min, sans plantage, avec reprise après interruption | ✅ **2,8 min** au total ; processus tué (SIGKILL) après 150 sites, reprise des 350 restants ; 500 lignes, aucune « À revérifier » | `pytest -m charge -s` → `test_charge.py` : « interruption après 150 sites (51 s), reprise en 119 s, total 170 s » |
| 5 | Le fichier de l'outil Google Maps s'importe sans retouche | ✅ CSV et Excel reconnus automatiquement | `test_importers_maps.py::test_csv_de_l_outil_google_maps`, `test_excel_de_l_outil_google_maps`, `test_web_routes.py::test_apercu_detecte_l_outil_google_maps` |
| 6 | Rapport PDF lisible par un non-technicien, sans jargon non expliqué | ✅ textes vérifiés sans SSL/HTTP/DNS/PHP/chiffres ; détails techniques à part | `test_messages.py::test_textes_sans_jargon_ni_chiffres` (tous les problèmes), `test_rapport_pdf.py` (3 verdicts, 2 pages), exemples dans `exemples/` |
| 7 | Tests pour chaque analyseur, couverture du scoring à 100 % | ✅ **373 tests** réussis ; scoring **100 %** (instructions et branches) | `pytest --cov=chasseur.scoring --cov-branch` : 49 instructions, 18 branches, 0 manquée |

## Corrigé pendant la recette

- **Faux positif « page blanche »** repéré sur des pages anciennes trop courtes : c'était le jeu de test (moins de
  500 caractères de texte, seuil du cahier des charges §3.2), pas l'outil. Pages de test allongées à la taille d'une
  vraie page d'accueil. À retenir : une page d'accueil **réelle** de moins de 500 caractères sera signalée « page
  presque vide » ; le seuil se règle dans `config.yaml` (`navigateur.texte_min`).
- Les avertissements d'analyse s'affichaient dans la console de `chasseur scan -q` : ils ne vont plus que dans
  `erreurs.log` (interface) et la colonne `non_verifies` du CSV.

## Limites de cette recette

- Les 30 URL sont des pages locales représentatives, pas 30 vrais sites : refaites la mesure sur vos propres cas
  (ci-dessous). Le temps réel de 500 sites dépend surtout du nombre de sites en panne (2 essais × 15 s chacun) et de
  votre connexion ; compter plutôt 10 à 20 min.
- Non vérifiables ici : la vraie API Google Places (réponses simulées), l'image Docker (pas de Docker dans
  l'environnement), les exécutables Windows et macOS (construits par GitHub Actions ; l'exécutable Linux équivalent
  a été construit et testé : interface, scan, PDF).

## Refaire la recette sur de vrais sites

Préparez un CSV avec les colonnes `nom;url;attendu` (attendu = Cassé, Obsolète ou Correct), puis :

```bash
chasseur recette jeu.csv
```

Chaque ligne affiche ✓ ou ✗, l'état obtenu, le score et les constats, puis le taux par catégorie et global
(objectif ≥ 90 %). Code de sortie 0 si l'objectif est atteint.
