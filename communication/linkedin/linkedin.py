"""Bannières LinkedIn VORELIK : page entreprise (1128 × 191) et profil personnel (1584 × 396), français et anglais.
La photo (logo de la page, ou votre photo de profil) recouvre le coin bas gauche : le contenu est placé à droite."""
import sys
from pathlib import Path
sys.argv = sys.argv[:2]
sys.path.insert(0, "/tmp/claude-0/-home-user-audit-express/52f218e2-7736-53dd-a410-3e4060e5517d/scratchpad/facebook")
from facebook import A, BASE, ICONES, LOGO, fond  # noqa: E402

TEXTES = {
    "fr": dict(titre='Des logiciels qui trouvent <span class="aurora">vos prochains clients.</span>',
               sous="Pour créateurs de sites web, agences et freelances", site="vorelik.com",
               apps=(("btl", "BridgeToLeads"), ("cds", "Chasseur de sites"), ("aex", "Audit express"))),
    "en": dict(titre='Software that finds <span class="aurora">your next clients.</span>',
               sous="For web designers, agencies and freelancers", site="vorelik.com/en",
               apps=(("btl", "BridgeToLeads"), ("cds", "Site Hunter"), ("aex", "Audit Express"))),
}

def banniere(langue, largeur, hauteur, echelle, gauche_libre):
    T = TEXTES[langue]
    apps = "".join(f'<span class="app"><img src="{ICONES[k]}">{n}</span>' for k, n in T["apps"])
    e = echelle
    return f"""<!doctype html><html lang="{langue}" data-taille="{largeur}x{hauteur}"><head><meta charset="utf-8">{BASE}<style>
  html, body {{ width: {largeur}px; height: {hauteur}px; }}
  .contenu {{ position: absolute; left: {gauche_libre}px; right: {int(40 * e)}px; top: 0; bottom: 0; display: flex; flex-direction: column;
     justify-content: center; align-items: flex-end; text-align: right; gap: {int(10 * e)}px; }}
  h1 {{ font-size: {int(34 * e)}px; line-height: 1.1; letter-spacing: -.02em; white-space: nowrap; }}
  .ligne {{ display: flex; align-items: center; gap: {int(14 * e)}px; }}
  .sous {{ font-size: {int(15 * e)}px; color: #C3CAE0; font-weight: 600; }}
  .app {{ display: inline-flex; align-items: center; gap: {int(8 * e)}px; font-size: {int(15 * e)}px; font-weight: 800;
     background: rgba(255,255,255,.08); padding: {int(5 * e)}px {int(12 * e)}px {int(5 * e)}px {int(5 * e)}px; border-radius: 999px;
     box-shadow: inset 0 0 0 1px rgba(255,255,255,.16); }}
  .app img {{ width: {int(24 * e)}px; height: {int(24 * e)}px; border-radius: {int(7 * e)}px; }}
  .site {{ font-size: {int(17 * e)}px; font-weight: 800; }}
  .logo {{ height: {int(34 * e)}px; }}
</style></head><body>{fond("vorelik")}
  <div class="contenu">
    <h1>{T["titre"]}</h1>
    <div class="ligne">{apps}</div>
    <div class="ligne"><span class="sous">{T["sous"]}</span><span class="site aurora">{T["site"]}</span></div>
  </div>
</body></html>"""

sortie = Path(sys.argv[1])
for langue in ("fr", "en"):
    # Page entreprise : le logo de la page est sous la bannière (ordinateur) ou la chevauche à gauche (téléphone)
    (sortie / f"vorelik-linkedin-page-entreprise-{langue}.html").write_text(banniere(langue, 1128, 191, 1.0, 300))
    # Profil personnel : la photo ronde recouvre environ le tiers gauche du bas de la bannière
    (sortie / f"vorelik-linkedin-profil-personnel-{langue}.html").write_text(banniere(langue, 1584, 396, 1.6, 520))
print("ok")
