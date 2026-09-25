# Lead finder: local businesses without a website

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
python3 tools/prospection/lead_finder_app.pyw
```

On Windows you can also just double-click `lead_finder_app.pyw` (with Python
installed from python.org). Paste your API key, pick an occupation from the
list (or type any), enter cities one per line, click **Search**. Double-click
a result to open it on Google Maps; **Exporter Excel…** saves the list as .xlsx.
"Remember" stores the key in `~/.lead_finder.json` on your computer.

### Windows .exe (no Python needed)

GitHub builds `LeadFinder.exe` automatically whenever this folder changes
(workflow `.github/workflows/lead-finder-exe.yml`). Download it from the
repo's **Releases → Lead Finder (latest Windows build)**, or from the
workflow run's artifacts. The exe is not code-signed, so on first launch
Windows SmartScreen asks: click **More info → Run anyway**.

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
