"""One fetcher per job-feed type. Each returns a list of raw job dicts:
{id, title, locations: [str], url, posted, text, remote, detail}
`text` is the posting body when the list endpoint includes it; otherwise `detail`
holds what enrich() needs to fetch it later (only for jobs that pass the title filter).
parse_* functions are pure so they can be tested without the network.
"""
import time

from .filters import is_remote, parse_date

UA = {"User-Agent": "Mozilla/5.0 (compatible; job-board-bot/1.0)", "Accept": "application/json"}
SEARCH_TERMS = ["software engineer", "software developer"]


class Http:
    """Small wrapper so tests can swap in a fake."""

    def __init__(self, timeout=30, retries=2):
        import requests
        self.s = requests.Session()
        self.s.headers.update(UA)
        self.timeout, self.retries = timeout, retries

    def _do(self, method, url, **kw):
        last = None
        for attempt in range(self.retries + 1):
            try:
                r = self.s.request(method, url, timeout=self.timeout, **kw)
                if r.status_code in (429, 500, 502, 503, 504) and attempt < self.retries:
                    time.sleep(2 * (attempt + 1))
                    continue
                r.raise_for_status()
                return r.json()
            except Exception as e:  # noqa: BLE001 - reported per company
                last = e
                time.sleep(1 + attempt)
        raise last

    def get(self, url, params=None):
        return self._do("GET", url, params=params)

    def post(self, url, body):
        return self._do("POST", url, json=body, headers={"Content-Type": "application/json"})


# ---------- Greenhouse ----------
def parse_greenhouse(data):
    out = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name") or ""
        out.append({
            "id": str(j.get("id")), "title": j.get("title", ""), "locations": [loc] if loc else [],
            "url": j.get("absolute_url", ""),
            "posted": parse_date(j.get("first_published") or j.get("updated_at")),
            "text": j.get("content", ""), "remote": is_remote(loc),
        })
    return out


def fetch_greenhouse(c, http):
    return parse_greenhouse(http.get(
        f"https://boards-api.greenhouse.io/v1/boards/{c['token']}/jobs", {"content": "true"}))


# ---------- Lever ----------
def parse_lever(data):
    out = []
    for j in data or []:
        cat = j.get("categories") or {}
        locs = cat.get("allLocations") or ([cat["location"]] if cat.get("location") else [])
        text = " ".join([j.get("descriptionPlain") or "", j.get("additionalPlain") or ""] +
                        [l.get("content", "") for l in j.get("lists") or []])
        out.append({
            "id": str(j.get("id")), "title": j.get("text", ""), "locations": locs,
            "url": j.get("hostedUrl", ""), "posted": parse_date(j.get("createdAt")), "text": text,
            "remote": j.get("workplaceType") == "remote" or is_remote(" ".join(locs)),
        })
    return out


def fetch_lever(c, http):
    return parse_lever(http.get(f"https://api.lever.co/v0/postings/{c['token']}", {"mode": "json"}))


# ---------- Ashby ----------
def parse_ashby(data):
    out = []
    for j in data.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j["location"]] if j.get("location") else []
        locs += [s.get("location") for s in j.get("secondaryLocations") or [] if s.get("location")]
        out.append({
            "id": str(j.get("id")), "title": j.get("title", ""), "locations": locs,
            "url": j.get("jobUrl") or j.get("applyUrl", ""), "posted": parse_date(j.get("publishedAt")),
            "text": j.get("descriptionPlain") or j.get("descriptionHtml") or "",
            "remote": bool(j.get("isRemote")) or is_remote(" ".join(locs)),
        })
    return out


def fetch_ashby(c, http):
    return parse_ashby(http.get(f"https://api.ashbyhq.com/posting-api/job-board/{c['token']}"))


# ---------- SmartRecruiters ----------
def parse_smartrecruiters(data, token):
    out = []
    for j in data.get("content", []):
        l = j.get("location") or {}
        loc = l.get("fullLocation") or ", ".join(
            x for x in [l.get("city"), l.get("region"), (l.get("country") or "").upper()] if x)
        out.append({
            "id": str(j.get("id")), "title": j.get("name", ""), "locations": [loc] if loc else [],
            "url": f"https://jobs.smartrecruiters.com/{token}/{j.get('id')}",
            "posted": parse_date(j.get("releasedDate")), "text": "",
            "remote": bool(l.get("remote")) or is_remote(loc),
            "detail": f"https://api.smartrecruiters.com/v1/companies/{token}/postings/{j.get('id')}",
        })
    return out


def fetch_smartrecruiters(c, http, max_per_term=300):
    seen, out = set(), []
    for term in ["engineer", "developer"]:
        offset = 0
        while offset < max_per_term:
            data = http.get(f"https://api.smartrecruiters.com/v1/companies/{c['token']}/postings",
                            {"q": term, "limit": 100, "offset": offset})
            page = parse_smartrecruiters(data, c["token"])
            for j in page:
                if j["id"] not in seen:
                    seen.add(j["id"])
                    out.append(j)
            offset += 100
            if not page or offset >= data.get("totalFound", 0):
                break
    return out


def smartrecruiters_detail_text(data):
    sections = ((data.get("jobAd") or {}).get("sections") or {})
    return " ".join((s or {}).get("text", "") for s in sections.values())


# ---------- Workday ----------
def workday_base(c):
    return f"https://{c['tenant']}.{c['dc']}.myworkdayjobs.com"


def parse_workday(data, c):
    base, out = workday_base(c), []
    for j in data.get("jobPostings", []):
        path = j.get("externalPath") or ""
        if not path:
            continue
        loc = j.get("locationsText") or ""
        out.append({
            "id": path.rsplit("/", 1)[-1], "title": j.get("title", ""),
            "locations": [loc] if loc else [], "url": f"{base}/en-US/{c['site']}{path}",
            "posted": parse_date(j.get("postedOn")), "text": "", "remote": is_remote(loc),
            "detail": f"{base}/wday/cxs/{c['tenant']}/{c['site']}{path}",
        })
    return out


def fetch_workday(c, http, max_per_term=200):
    url = f"{workday_base(c)}/wday/cxs/{c['tenant']}/{c['site']}/jobs"
    seen, out = set(), []
    for term in SEARCH_TERMS:
        offset, total = 0, None
        while offset < max_per_term:
            data = http.post(url, {"appliedFacets": {}, "limit": 20, "offset": offset,
                                   "searchText": term})
            if total is None:  # Workday only reports the total on the first page
                total = data.get("total", 0)
            page = parse_workday(data, c)
            for j in page:
                if j["id"] not in seen:
                    seen.add(j["id"])
                    out.append(j)
            offset += 20
            if not page or offset >= total:
                break
    return out


def workday_detail(data):
    """Return (text, locations, posted, remote) from a Workday posting detail payload."""
    info = data.get("jobPostingInfo") or {}
    locs = [info["location"]] if info.get("location") else []
    locs += info.get("additionalLocations") or []
    country = (info.get("country") or {}).get("descriptor")
    if country:
        locs = [l if country.lower() in l.lower() else f"{l}, {country}" for l in locs] or [country]
    remote = "remote" in (info.get("remoteType") or "").lower()
    return info.get("jobDescription", ""), locs, parse_date(info.get("startDate")), remote


# ---------- Amazon ----------
def parse_amazon(data):
    out = []
    for j in data.get("jobs", []):
        loc = j.get("normalized_location") or j.get("location") or ""
        text = " ".join(j.get(k) or "" for k in
                        ("description", "basic_qualifications", "preferred_qualifications"))
        out.append({
            "id": str(j.get("id_icims") or j.get("id")), "title": j.get("title", ""),
            "locations": [loc] if loc else [],
            "url": "https://www.amazon.jobs" + (j.get("job_path") or ""),
            "posted": parse_date(j.get("posted_date")), "text": text, "remote": is_remote(loc),
        })
    return out


def fetch_amazon(c, http, cap=500):
    seen, out = set(), []
    for term in SEARCH_TERMS:
        offset = 0
        while offset < cap:
            data = http.get("https://www.amazon.jobs/en/search.json",
                            {"base_query": term, "country": "USA", "result_limit": 100,
                             "offset": offset, "sort": "recent"})
            page = parse_amazon(data)
            for j in page:
                if j["id"] not in seen:
                    seen.add(j["id"])
                    out.append(j)
            offset += 100
            if not page or offset >= data.get("hits", 0):
                break
    return out


FETCHERS = {
    "greenhouse": fetch_greenhouse, "lever": fetch_lever, "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters, "workday": fetch_workday, "amazon": fetch_amazon,
}


def enrich(job, feed, http):
    """Fetch the posting body for feeds whose list endpoint leaves it out."""
    data = http.get(job["detail"])
    if feed == "workday":
        text, locs, posted, remote = workday_detail(data)
        job["text"] = text
        if locs:
            job["locations"] = locs
        job["posted"] = posted or job["posted"]
        job["remote"] = job["remote"] or remote or is_remote(" ".join(locs))
    elif feed == "smartrecruiters":
        job["text"] = smartrecruiters_detail_text(data)
