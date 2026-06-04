"""Scratch probe — read-only, low-volume. Hits the PUBLIC front doors of two
sources to see real Berlin product-role results. Delete when done.

No proxies, no evasion, no auth-bypass: just a single polite GET each against
endpoints a logged-out browser already hits.
"""

import json
import re
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def probe_linkedin(keywords, location):
    print(f"\n=== LinkedIn jobs-guest: '{keywords}' in {location} ===")
    qs = urllib.parse.urlencode({"keywords": keywords, "location": location, "start": 0})
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{qs}"
    try:
        html = get(url)
    except Exception as e:
        print(f"  FAILED: {e}")
        return
    titles = re.findall(r'base-search-card__title">\s*(.*?)\s*</', html, re.DOTALL)
    comps = re.findall(r'base-search-card__subtitle">\s*(.*?)\s*</', html, re.DOTALL)
    print(f"  cards returned on page 1: {len(titles)}")
    for t, c in list(zip(titles, comps))[:12]:
        t = re.sub(r"\s+", " ", t).strip()
        c = re.sub(r"\s+", " ", c).strip()
        print(f"   - {t}  @  {c}")


def probe_arbeitsagentur(was, wo):
    print(f"\n=== Arbeitsagentur API: '{was}' in {wo} (25km) ===")
    qs = urllib.parse.urlencode({"was": was, "wo": wo, "umkreis": 25, "size": 25, "page": 1})
    url = f"https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs?{qs}"
    try:
        data = json.loads(get(url, headers={"X-API-Key": "jobboerse-jobsuche"}))
    except Exception as e:
        print(f"  FAILED: {e}")
        return
    total = data.get("maxErgebnisse", "?")
    jobs = data.get("stellenangebote", []) or []
    print(f"  total matches reported: {total}  |  returned this page: {len(jobs)}")
    for j in jobs[:12]:
        title = j.get("titel", "?")
        emp = j.get("arbeitgeber", "?")
        ort = (j.get("arbeitsort") or {}).get("ort", "?")
        print(f"   - {title}  @  {emp}  ({ort})")


if __name__ == "__main__":
    for kw in ("Head of Product", "Product Manager"):
        probe_linkedin(kw, "Berlin, Germany")
    for w in ("Head of Product", "Product Manager"):
        probe_arbeitsagentur(w, "Berlin")
