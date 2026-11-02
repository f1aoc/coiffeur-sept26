"""Capture de BridgeToLeads pour les publicités : uniquement des commerces « Aucun site » (aucune mention de Facebook)."""
import os, runpy, sys
langue = sys.argv[2]
os.environ["BRIDGETOLEADS_LANGUE"] = langue
mod = runpy.run_path("/home/user/coiffeur-btl/tools/prospection/bridgetoleads.pyw", run_name="demo")
app = mod["App"]()
app.geometry("1180x740+0+0")
if langue == "fr":
    villes, metier = "Avignon\nCavaillon", "coiffeur"
    D = [("Salon Léa", "04 90 82 14 20", "12 rue de la République, 84000 Avignon", 4.8, 128),
         ("L'Atelier de Julie", "04 90 71 33 08", "5 place du Marché, 84300 Cavaillon", 4.7, 96),
         ("Coiff'Émoi", "04 90 86 52 41", "38 rue Carreterie, 84000 Avignon", 4.6, 84),
         ("Hair Studio 84", "04 90 78 19 63", "2 cours Gambetta, 84300 Cavaillon", 4.5, 71),
         ("Le Salon de Marie", "04 90 85 27 90", "17 rue des Teinturiers, 84000 Avignon", 4.9, 63),
         ("Instant Beauté", "04 90 71 48 15", "9 avenue de Verdun, 84300 Cavaillon", 4.4, 55),
         ("Coupe & Style", "04 90 82 66 34", "44 rue Joseph Vernet, 84000 Avignon", 4.6, 47),
         ("Studio Nadia", "04 90 76 12 58", "21 rue Raspail, 84300 Cavaillon", 4.7, 39),
         ("Barber Avenue", "04 90 27 93 02", "3 boulevard Raspail, 84000 Avignon", 4.8, 33),
         ("Les Ciseaux d'Or", "04 90 71 05 77", "15 rue Bournissac, 84300 Cavaillon", 4.3, 26),
         ("Tête à Tête", "04 90 86 40 19", "60 rue Bonneterie, 84000 Avignon", 4.5, 18)]
    total = 96
else:
    villes, metier = "Austin TX\nDallas TX", "hair salon"
    D = [("Lone Star Barber Co.", "(512) 555-0142", "1201 S Congress Ave, Austin, TX", 4.8, 212),
         ("Hair by Monica", "(214) 555-0137", "2710 Elm St, Dallas, TX", 4.9, 141),
         ("Glam Lounge", "(512) 555-0163", "3300 Guadalupe St, Austin, TX", 4.5, 83),
         ("Curl Up & Dye", "(512) 555-0186", "1900 E Cesar Chavez St, Austin, TX", 4.6, 52),
         ("Kutz & Kolor", "(512) 555-0104", "6800 Burnet Rd, Austin, TX", 4.4, 29),
         ("The Fade Room", "(214) 555-0175", "1408 Greenville Ave, Dallas, TX", 4.7, 96),
         ("Salon Rouge", "(214) 555-0128", "4501 McKinney Ave, Dallas, TX", 4.3, 64),
         ("Uptown Shears", "(214) 555-0191", "3100 Main St, Dallas, TX", 4.2, 37),
         ("Mane Event", "(214) 555-0158", "5600 Lemmon Ave, Dallas, TX", 4.1, 18),
         ("Bella Nails & Spa", "(512) 555-0199", "88 N Lamar Blvd, Austin, TX", 4.6, 167),
         ("Fresh Cuts Studio", "(512) 555-0110", "500 E 6th St, Austin, TX", 4.4, 118)]
    total = 118
leads = sorted(({"name": n, "status": "none", "website": "", "phone": t, "address": a, "rating": r, "reviews": v, "maps_url": "x"}
                for n, t, a, r, v in D), key=lambda x: -x["reviews"])
def go():
    app.occupation.set(metier)
    app.cities.insert("1.0", villes)
    app._show_results(leads, total)
    app.update()
    app.after(800, lambda: (os.system(f"import -window root -crop 1180x740+0+0 {sys.argv[1]}"), app.destroy()))
app.after(1200, go)
app.mainloop()
