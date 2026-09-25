#!/usr/bin/env python3
"""Find local businesses on Google Maps that have no website.

Uses the official Google Places API (New) Text Search endpoint — no HTML
scraping. Standard library only.

    export GOOGLE_MAPS_API_KEY=...
    python3 find_no_website.py "coiffeur" --city "L'Isle-sur-la-Sorgue" --city Cavaillon
    python3 find_no_website.py "coiffeur" --cities-file villes.txt -o leads.csv

A business counts as a lead when it has no website at all, or when its
"website" is only a social profile or a booking directory (Facebook,
Instagram, Planity, Treatwell...). Use --strict to keep only businesses with
no website field whatsoever.
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"

FIELDS = [
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.googleMapsUri",
    "places.rating",
    "places.userRatingCount",
    "places.businessStatus",
    "places.primaryTypeDisplayName",
    "nextPageToken",
]

# Hosts that are not a real website of the business itself.
NOT_A_REAL_SITE = {
    "facebook.com", "fb.com", "instagram.com", "tiktok.com", "linkedin.com",
    "twitter.com", "x.com", "youtube.com", "linktr.ee", "wa.me",
    "sites.google.com", "business.site", "g.page",
    "planity.com", "treatwell.fr", "treatwell.com", "kiute.com",
    "booksy.com", "fresha.com", "doctolib.fr", "pagesjaunes.fr",
    "tripadvisor.fr", "tripadvisor.com", "thefork.fr", "lafourchette.com",
    "ubereats.com", "deliveroo.fr", "calendly.com",
}

CSV_COLUMNS = [
    "name", "status", "website", "phone", "address", "category",
    "rating", "reviews", "maps_url", "place_id", "query",
]


class PlacesError(Exception):
    pass


def classify_website(url):
    """Return 'none', 'social_or_directory:<host>' or 'real'."""
    if not url:
        return "none"
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    for bad in NOT_A_REAL_SITE:
        if host == bad or host.endswith("." + bad):
            return f"social_or_directory:{bad}"
    return "real"


def search(api_key, query, language, region, max_pages):
    """Yield raw place dicts for a text query (max 20 per page, 3 pages)."""
    body = {"textQuery": query, "languageCode": language, "regionCode": region, "pageSize": 20}
    for _ in range(max_pages):
        req = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(body).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": ",".join(FIELDS),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            raise PlacesError(f"Places API error {e.code} for {query!r}: {e.read().decode(errors='replace')}")
        except urllib.error.URLError as e:
            raise PlacesError(f"Network error for {query!r}: {e.reason}")
        yield from data.get("places", [])
        token = data.get("nextPageToken")
        if not token:
            return
        body["pageToken"] = token
        time.sleep(2)  # the next page token needs a moment to become valid


def to_row(place, query):
    return {
        "name": place.get("displayName", {}).get("text", ""),
        "status": classify_website(place.get("websiteUri")),
        "website": place.get("websiteUri", ""),
        "phone": place.get("nationalPhoneNumber") or place.get("internationalPhoneNumber", ""),
        "address": place.get("formattedAddress", ""),
        "category": place.get("primaryTypeDisplayName", {}).get("text", ""),
        "rating": place.get("rating", ""),
        "reviews": place.get("userRatingCount", ""),
        "maps_url": place.get("googleMapsUri", ""),
        "place_id": place.get("id", ""),
        "query": query,
    }


def find_leads(api_key, queries, strict=False, include_closed=False,
               language="fr", region="FR", max_pages=3, progress=None):
    """Run every query and return (leads sorted by review count, businesses seen)."""
    seen, leads, total = set(), [], 0
    for q in queries:
        found = 0
        for place in search(api_key, q, language, region, max_pages):
            if place.get("id") in seen:
                continue
            seen.add(place.get("id"))
            total += 1
            if not include_closed and place.get("businessStatus", "OPERATIONAL") != "OPERATIONAL":
                continue
            row = to_row(place, q)
            if row["status"] == "real" or (strict and row["status"] != "none"):
                continue
            leads.append(row)
            found += 1
        if progress:
            progress(q, found)
    # Most-reviewed first: established businesses that are easier to pitch.
    leads.sort(key=lambda r: r["reviews"] or 0, reverse=True)
    return leads, total


def write_csv(leads, path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(leads)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("keyword", help='business type to search, e.g. "coiffeur", "plombier"')
    p.add_argument("--city", action="append", default=[], help="city to search in (repeatable)")
    p.add_argument("--cities-file", help="text file with one city per line")
    p.add_argument("-o", "--output", default="leads.csv", help="CSV output path (default: leads.csv)")
    p.add_argument("--strict", action="store_true", help="only businesses with no website field at all")
    p.add_argument("--include-closed", action="store_true", help="keep temporarily/permanently closed businesses")
    p.add_argument("--language", default="fr")
    p.add_argument("--region", default="FR")
    p.add_argument("--max-pages", type=int, default=3, help="pages of 20 results per query (API max: 3)")
    args = p.parse_args()

    api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        sys.exit("Set the GOOGLE_MAPS_API_KEY environment variable first.")

    cities = list(args.city)
    if args.cities_file:
        with open(args.cities_file, encoding="utf-8") as f:
            cities += [line.strip() for line in f if line.strip() and not line.startswith("#")]
    queries = [f"{args.keyword} {c}" for c in cities] or [args.keyword]

    try:
        leads, total = find_leads(
            api_key, queries, strict=args.strict, include_closed=args.include_closed,
            language=args.language, region=args.region, max_pages=args.max_pages,
            progress=lambda q, n: print(f"{q!r}: {n} lead(s)", file=sys.stderr),
        )
    except PlacesError as e:
        sys.exit(str(e))
    write_csv(leads, args.output)
    print(f"{len(leads)} lead(s) out of {total} businesses -> {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
