# BridgeToLeads by ptabountchikoff: local businesses without a website

`find_no_website.py` searches Google Maps via the official **Places API (New)**
and exports businesses that have no website (or only a Facebook / Instagram /
Planity / Treatwell page) to a CSV, most-reviewed first.

## Setup

1. In Google Cloud Console, create a project, enable **Places API (New)**,
   and create an API key (restrict it to that API).
2. `export GOOGLE_MAPS_API_KEY=your_key`

Python 3.9+. Excel export needs `pip install openpyxl` (already inside the .exe).

## Desktop app (easiest)

```bash
python3 tools/prospection/bridgetoleads.pyw
```

On Windows you can also just double-click `bridgetoleads.pyw` (with Python
installed from python.org). Paste your API key, pick an occupation from the
list (or type any), enter cities one per line, click **Search**. Double-click
a result to open it on Google Maps; **Exporter Excel…** saves the list as .xlsx.
"Remember" stores the key in `~/.bridgetoleads.json` (settings saved under the old name `~/.lead_finder.json` are picked up automatically) on your computer.

### Look & branding

Colourful interface (violet → pink → orange), fully in French. To rebrand it
for resale, edit the constants at the top of `bridgetoleads.pyw`
(`APP_NAME`, `AUTHOR`, `TAGLINE`, `GRADIENT`, colours `C`), and redraw the icon with
`python3 tools/prospection/assets/make_icon.py` (needs Pillow): it rewrites
`assets/bridgetoleads.ico` (the .exe icon) and `brand_icon.py` (window icon).

### Licence (Stripe + licence server)

Each copy is protected by a licence key (`licence.py`, standard library only, same module as Chasseur de sites).
Customers pay through a Stripe payment link; Stripe redirects them to `site/merci.html`, which shows the key
(`BTL-…`) fetched from the licence server (`serveur-licences/` on branch `claude/kind-volta-486eo6`, a free
Cloudflare Worker that reads Stripe directly — setup guide in its README). On first launch the app asks for the
key; it is re-checked online at startup and every 24 h; offline, the app keeps working 14 days after the last
successful check. After a full **refund** or a dispute in Stripe, the next check blocks searches (results already
on screen can still be exported). 2 computers per licence. "Licence" button in the header: status,
"Vérifier maintenant", "Libérer" (move to another computer). Signed licence file: `~/.bridgetoleads/licence.json`.

Setup: deploy the licence server, then set `SERVEUR` (server address) and `LIEN_ACHAT` (Stripe payment link) in
`licence.py`, and `SERVEUR_LICENCES` in `site/merci.html`.

Running from source with `BRIDGETOLEADS_SANS_LICENCE=1` skips the check (development only; the .exe / .app
always ignore it). The command-line tool `find_no_website.py` has no licence check: it is not part of the
packaged app. This repository is public, so a technical user could rebuild the app without the check; making it
private and hosting the downloads elsewhere closes that gap. Tests: `python -m pytest tools/prospection/tests`.

### Sales page

`site/` holds a static French sales page for BridgeToLeads (`index.html` +
`assets/`) and a post-purchase thank-you page (`merci.html`: download button +
setup guide, not indexed by search engines; point your payment provider's
success redirect to it). No build: upload the folder to any static host (Netlify, Vercel,
GitHub Pages, FTP). Before publishing, edit the lines marked `À MODIFIER` in
`index.html` and `merci.html`: the price and the buy link (Stripe/PayPal payment link or e-mail).

### Windows .exe and Mac app (no Python needed)

GitHub builds `BridgeToLeads.exe` automatically whenever this folder changes
(workflow `.github/workflows/bridgetoleads-exe.yml`). Download it from the
repo's **Releases → BridgeToLeads by ptabountchikoff (latest Windows build)**, which also holds `BridgeToLeads-site.zip`, or from the
workflow run's artifacts. The exe is not code-signed, so on first launch
Windows SmartScreen asks: click **More info → Run anyway**.

The same workflow builds the Mac app on GitHub's macOS runners:
`BridgeToLeads-mac-apple-silicon.zip` (M1–M4) and `BridgeToLeads-mac-intel.zip`,
each smoke-tested (the app must start and stay open). The app is not notarized
by Apple, so the first launch needs System Settings → Privacy & Security →
**Open Anyway**. Signing/notarization needs an Apple Developer account.

## Command line

```bash
python3 find_no_website.py "coiffeur" --city "L'Isle-sur-la-Sorgue" --city Cavaillon --city Avignon
python3 find_no_website.py "coiffeur" --cities-file villes.txt -o leads.csv
python3 find_no_website.py "boulangerie" --city Apt --strict   # no website field at all
```

Each query returns at most 60 results (API limit), so search city by city
(or neighbourhood by neighbourhood in big cities) for full coverage.
Results are deduplicated across queries.

Output: `-o leads.xlsx` (default, Excel) or `-o leads.csv`. CSV columns: `name, status, website, phone, address, category, rating,
reviews, maps_url, place_id, query`. `status` is `none` or
`social_or_directory:<host>`.

## Cost

Requesting `websiteUri` / phone numbers bills Text Search at the Enterprise
tier (check current pricing on Google's Places API pricing page; there is a
monthly free usage allowance). Each page of up to 20 results is one request.
