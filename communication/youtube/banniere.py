"""Bannière YouTube VORELIK 2560 × 1440 (zone visible partout : 1546 × 423 au centre)."""
import sys
from pathlib import Path
R = Path("/home/user/coiffeur-sept26")
A = R / "vitrine/assets"
TEXTES = {
    "fr": dict(l1="Des logiciels qui trouvent", l2="vos prochains clients.",
               sous="Prospection et audit de sites pour créateurs de sites web, agences et freelances",
               apps=[("bridgetoleads-icone.png", "BridgeToLeads", "Les commerces sans site web"),
                     ("chasseur-icone.png", "Chasseur de sites", "Les sites cassés ou dépassés"),
                     ("audit-express-icone.png", "Audit express", "Un audit qui fait signer")],
               badge="Windows et Mac · Paiement unique",
               captures=[A / "bridgetoleads-apercu.jpg", A / "chasseur-apercu.jpg", A / "audit-express-apercu.jpg"]),
    "en": dict(l1="Software that finds", l2="your next clients.",
               sous="Prospecting and website audits for web designers, agencies and freelancers",
               apps=[("bridgetoleads-icone.png", "BridgeToLeads", "Businesses with no website"),
                     ("chasseur-icone.png", "Site Hunter", "Broken or outdated websites"),
                     ("audit-express-icone.png", "Audit Express", "Audits that win deals")],
               badge="Windows & Mac · One-time payment",
               captures=[R / "vitrine-en/bridgetoleads/assets/app-screenshot.png", R / "vitrine-en/site-hunter/assets/app-screenshot.jpg",
                         R / "vitrine-en/audit-express/assets/app-screenshot.jpg"]),
}
for langue, T in TEXTES.items():
    apps = "\n".join(f'''      <div class="app"><img src="{A / ic}" alt=""><div><b>{nom}</b><span>{txt}</span></div></div>''' for ic, nom, txt in T["apps"])
    c = T["captures"]
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<link href="{A / 'polices/polices.css'}" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; }}
  html, body {{ width: 2560px; height: 1440px; overflow: hidden; }}
  body {{ position: relative; background: #0A0F1F; font-family: "Plus Jakarta Sans", sans-serif; color: #EEF1FA; }}
  .glow {{ position: absolute; border-radius: 50%; filter: blur(140px); }}
  .g1 {{ width: 1100px; height: 900px; background: #7C3AED; opacity: .55; left: -200px; top: 120px; }}
  .g2 {{ width: 1000px; height: 800px; background: #EC4899; opacity: .35; left: 900px; top: 640px; }}
  .g3 {{ width: 1000px; height: 900px; background: #0EA5E9; opacity: .32; right: -220px; top: 160px; }}
  .g4 {{ width: 700px; height: 600px; background: #F97316; opacity: .22; left: 1500px; top: -150px; }}
  .grille {{ position: absolute; inset: 0; background-image: linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px),
     linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px); background-size: 80px 80px;
     -webkit-mask-image: radial-gradient(ellipse at center, #000 30%, transparent 75%); }}
  .capture {{ position: absolute; width: 760px; border-radius: 22px; overflow: hidden; box-shadow: 0 40px 90px -30px rgba(0,0,0,.8), 0 0 0 1px rgba(255,255,255,.12);
     background: #fff; }}
  .capture .barre {{ height: 34px; background: #EEF1FA; display: flex; gap: 10px; align-items: center; padding-left: 16px; }}
  .capture .barre i {{ width: 12px; height: 12px; border-radius: 50%; background: #F87171; }}
  .capture .barre i:nth-child(2) {{ background: #FBBF24; }} .capture .barre i:nth-child(3) {{ background: #34D399; }}
  .capture img {{ display: block; width: 100%; }}
  .c1 {{ left: -360px; top: 470px; transform: rotate(-7deg); opacity: .9; }}
  .c2 {{ right: -380px; top: 430px; transform: rotate(6deg); opacity: .9; }}
  .c3 {{ left: 900px; top: 1030px; transform: rotate(-3deg); width: 820px; opacity: .55; }}
  .voile {{ position: absolute; inset: 0; background: radial-gradient(ellipse 900px 330px at 50% 50%, rgba(10,15,31,.92), rgba(10,15,31,.55) 70%, transparent); }}
  .zone {{ position: absolute; left: 507px; top: 508px; width: 1546px; height: 423px; display: flex; align-items: center; gap: 56px; padding: 0 36px; }}
  .gauche {{ flex: 1; min-width: 0; }}
  .logo {{ width: 300px; display: block; margin-bottom: 14px; }}
  h1 {{ font-size: 62px; white-space: nowrap; line-height: 1.04; font-weight: 800; letter-spacing: -.03em; }}
  .aurora {{ background: linear-gradient(100deg, #A78BFA 0%, #F472B6 32%, #FB923C 58%, #38BDF8 85%); -webkit-background-clip: text; background-clip: text; color: transparent; }}
  .sous {{ margin-top: 16px; font-size: 23px; color: #C3CAE0; font-weight: 500; max-width: 760px; line-height: 1.35; }}
  .droite {{ flex: 0 0 560px; display: flex; flex-direction: column; gap: 16px; }}
  .app {{ display: flex; align-items: center; gap: 20px; padding: 16px 22px; border-radius: 22px; background: rgba(255,255,255,.07);
     box-shadow: inset 0 0 0 1px rgba(255,255,255,.14); backdrop-filter: blur(6px); }}
  .app img {{ width: 64px; height: 64px; border-radius: 16px; }}
  .app b {{ display: block; font-size: 30px; font-weight: 800; letter-spacing: -.01em; }}
  .app span {{ display: block; font-size: 21px; color: #C3CAE0; }}
  .pied {{ display: flex; justify-content: space-between; align-items: center; margin-top: 6px; padding: 0 6px; }}
  .site {{ font-size: 30px; font-weight: 800; letter-spacing: .01em; }}
  .badge {{ font-size: 19px; color: #A7B0C8; font-weight: 600; }}
</style></head><body>
  <div class="glow g1"></div><div class="glow g2"></div><div class="glow g3"></div><div class="glow g4"></div>
  <div class="grille"></div>
  <div class="capture c1"><div class="barre"><i></i><i></i><i></i></div><img src="{c[0]}"></div>
  <div class="capture c2"><div class="barre"><i></i><i></i><i></i></div><img src="{c[1]}"></div>
  <div class="capture c3"><div class="barre"><i></i><i></i><i></i></div><img src="{c[2]}"></div>
  <div class="voile"></div>
  <div class="zone">
    <div class="gauche">
      <img class="logo" src="{A / 'vorelik-logo.png'}" alt="VORELIK">
      <h1>{T['l1']}<br><span class="aurora">{T['l2']}</span></h1>
      <p class="sous">{T['sous']}</p>
    </div>
    <div class="droite">
{apps}
      <div class="pied"><span class="site aurora">vorelik.com</span><span class="badge">{T['badge']}</span></div>
    </div>
  </div>
</body></html>"""
    (Path(sys.argv[1]) / f"banniere-{langue}.html").write_text(html)
print("ok")
