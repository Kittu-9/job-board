"""Build site/jobs.json and site/status.json from companies.json.

    python -m scraper.scrape              # fetch every feed
    python -m scraper.scrape --offline    # no network: link-only output (first-time placeholder)
    python -m scraper.scrape --only Stripe
"""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from . import feeds
from .filters import any_us, is_restricted, is_software_role, is_us_location

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DETAIL_LIMIT = 80      # per company: postings fetched one by one for the citizenship/clearance check
MAX_PER_COMPANY = 400  # per company: cap on listed roles after merging duplicates


def slug(name):
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in name).strip("-")


def process_company(c, http, detail_limit=DETAIL_LIMIT):
    """Fetch one company. Returns (jobs, stats). Raises on feed failure."""
    feed = c["feed"]
    raw = feeds.FETCHERS[feed](c, http)
    matched = [j for j in raw if is_software_role(j["title"])]
    matched.sort(key=lambda j: j.get("posted") or "", reverse=True)

    kept, restricted, unscreened = [], 0, 0
    for i, j in enumerate(matched):
        screened = True
        if not j.get("text") and j.get("detail"):
            if i < detail_limit:
                try:
                    feeds.enrich(j, feed, http)
                    time.sleep(0.1)
                except Exception:  # noqa: BLE001 - keep the job, mark it unscreened
                    screened = False
            else:
                screened = False
        if is_restricted(j["title"] + " " + (j.get("text") or "")):
            restricted += 1
            continue
        if not screened:
            unscreened += 1
        j["screened"] = screened
        kept.append(j)

    # Merge the same title posted once per city into one row.
    merged = {}
    for j in kept:
        key = " ".join(j["title"].lower().split())
        m = merged.get(key)
        if not m:
            merged[key] = {
                "id": f"{slug(c['name'])}:{j['id']}", "company": c["name"], "category": c["category"],
                "title": " ".join(j["title"].split()), "locations": list(j["locations"]),
                "url": j["url"], "posted": j.get("posted"), "remote": bool(j.get("remote")),
                "screened": j["screened"],
            }
            continue
        for loc in j["locations"]:
            if loc not in m["locations"]:
                m["locations"].append(loc)
        m["remote"] = m["remote"] or bool(j.get("remote"))
        m["screened"] = m["screened"] and j["screened"]
        if (j.get("posted") or "") > (m["posted"] or ""):
            m["posted"] = j["posted"]
        if any_us(j["locations"]) and not any_us(m["locations"][:1]):
            m["url"] = j["url"]
    jobs = list(merged.values())
    for m in jobs:
        m["us"] = any_us(m["locations"])
        m["location_count"] = len(m["locations"])
        m["locations"].sort(key=lambda l: is_us_location(l) is not True)  # US locations first
        m["locations"] = m["locations"][:6]
    jobs.sort(key=lambda m: m["posted"] or "", reverse=True)
    stats = {"fetched": len(raw), "matched": len(matched), "restricted_removed": restricted,
             "unscreened": unscreened, "listed": min(len(jobs), MAX_PER_COMPANY)}
    return jobs[:MAX_PER_COMPANY], stats


def run(companies, http, previous=None, offline=False, now=None):
    now = now or datetime.now(timezone.utc)
    today = now.date().isoformat()
    prev_jobs = (previous or {}).get("jobs", [])
    first_seen = {(j["company"], j["title"].lower()): j.get("first_seen") for j in prev_jobs}
    prev_by_company = {}
    for j in prev_jobs:
        prev_by_company.setdefault(j["company"], []).append(j)

    all_jobs, status = [], []
    for c in companies:
        row = {"name": c["name"], "category": c["category"], "careers_url": c["careers_url"],
               "feed": c["feed"], "verified": bool(c.get("verified")), "state": "link_only",
               "jobs": 0, "error": None}
        if c["feed"] != "none":
            if offline:
                row["state"] = "pending"
            else:
                try:
                    jobs, stats = process_company(c, http)
                    row.update(state="ok", jobs=len(jobs), **stats)
                    all_jobs += jobs
                except Exception as e:  # noqa: BLE001 - one company must never stop the run
                    stale = prev_by_company.get(c["name"], [])
                    for j in stale:
                        j["stale"] = True
                    all_jobs += stale
                    row.update(state="failed", jobs=len(stale),
                               error=f"{type(e).__name__}: {str(e)[:200]}")
                print(f"{row['state']:>9}  {c['name']}: {row['jobs']} roles"
                      + (f"  ({row['error']})" if row["error"] else ""), flush=True)
        status.append(row)

    for j in all_jobs:
        j["first_seen"] = first_seen.get((j["company"], j["title"].lower())) or today
    all_jobs.sort(key=lambda j: (j.get("posted") or j["first_seen"], j["first_seen"]), reverse=True)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    return ({"generated_at": stamp, "count": len(all_jobs), "jobs": all_jobs},
            {"generated_at": stamp, "companies": status})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip the network; write link-only output")
    ap.add_argument("--only", help="fetch a single company by name (others keep previous data)")
    args = ap.parse_args()

    companies = json.loads((ROOT / "companies.json").read_text())["companies"]
    previous = None
    if (SITE / "jobs.json").exists():
        try:
            previous = json.loads((SITE / "jobs.json").read_text())
        except ValueError:
            previous = None
    if args.only:
        companies = [c for c in companies if c["name"].lower() == args.only.lower()]
    http = None if args.offline else feeds.Http()
    jobs, status = run(companies, http, previous, offline=args.offline)
    if args.only:
        print(json.dumps(status["companies"], indent=2))
        print(json.dumps(jobs["jobs"][:5], indent=2))
        return
    SITE.mkdir(exist_ok=True)
    (SITE / "jobs.json").write_text(json.dumps(jobs, separators=(",", ":")))
    (SITE / "status.json").write_text(json.dumps(status, indent=1))
    ok = sum(1 for s in status["companies"] if s["state"] == "ok")
    failed = sum(1 for s in status["companies"] if s["state"] == "failed")
    print(f"\n{jobs['count']} roles from {ok} feeds; {failed} feeds failed.")


if __name__ == "__main__":
    main()
