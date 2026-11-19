import json
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from scraper import feeds, scrape
from scraper.filters import (any_us, is_restricted, is_software_role, is_us_location, parse_date,
                             strip_html)


class TitleFilter(unittest.TestCase):
    def test_includes(self):
        for t in ["Senior Software Engineer", "Software Development Engineer II", "SDE II",
                  "Backend Engineer, Payments", "Full Stack Developer", "Staff Front-End Engineer",
                  "Data Engineer", "Machine Learning Engineer", "Site Reliability Engineer",
                  "Java Developer", "Engineer, Software (Platform)", "Member of Technical Staff",
                  "Software Engineer, Hardware Integration", "iOS Engineer", "DevOps Engineer",
                  "Software Engineering Intern", "Engineer II - Software Development"]:
            self.assertTrue(is_software_role(t), t)

    def test_excludes(self):
        for t in ["Sales Engineer", "Software Sales Engineer", "Engineering Manager, Software",
                  "Product Manager", "Mechanical Engineer", "Solutions Engineer", "Recruiter",
                  "Developer Advocate", "Business Development Representative", "Data Scientist",
                  "Data Center Engineer", "Director of Software Engineering", "Account Executive",
                  "Customer Support Engineer", "Electrical Engineer", "", None]:
            self.assertFalse(is_software_role(t), t)


class RestrictionFilter(unittest.TestCase):
    def test_restricted(self):
        for s in ["Must be a U.S. citizen.", "Active Secret clearance required",
                  "TS/SCI with polygraph", "US Citizenship is required for this role",
                  "Ability to obtain and maintain a DoD security clearance",
                  "<p>This position requires U.S. citizenship</p>", "Only US citizens may apply"]:
            self.assertTrue(is_restricted(s), s)

    def test_not_restricted(self):
        for s in ["We consider applicants without regard to citizenship status.",
                  "Build clear APIs and keep our secret sauce simple.",
                  "Verification of identity and eligibility to work in the United States.", ""]:
            self.assertFalse(is_restricted(s), s)

    def test_strip_html(self):
        self.assertEqual(strip_html("&lt;p&gt;Hello <b>there</b>&lt;/p&gt;"), "Hello there")


class Locations(unittest.TestCase):
    def test_us(self):
        for l in ["Austin, TX", "San Francisco", "Remote - United States", "US, CA, Santa Clara",
                  "New York, NY, USA"]:
            self.assertIs(is_us_location(l), True, l)
        for l in ["Bengaluru, India", "London", "Toronto, ON, CA", "Remote - Canada"]:
            self.assertIs(is_us_location(l), False, l)
        for l in ["Remote", "2 Locations", ""]:
            self.assertIsNone(is_us_location(l), l)
        self.assertIs(any_us(["London", "Austin, TX"]), True)
        self.assertIs(any_us(["London", "Berlin"]), False)
        self.assertIsNone(any_us([]))


class Dates(unittest.TestCase):
    def test_parse(self):
        today = date(2026, 11, 13)
        self.assertEqual(parse_date("2026-11-10T08:00:00-05:00"), "2026-11-10")
        self.assertEqual(parse_date("Posted Today", today), "2026-11-13")
        self.assertEqual(parse_date("Posted Yesterday", today), "2026-11-12")
        self.assertEqual(parse_date("Posted 30+ Days Ago", today), "2026-10-14")
        self.assertEqual(parse_date("November 10, 2026"), "2026-11-10")
        self.assertEqual(parse_date(1794268800000), "2026-11-10")
        self.assertIsNone(parse_date(None))
        self.assertIsNone(parse_date("soon"))


GREENHOUSE = {"jobs": [
    {"id": 1, "title": "Software Engineer, AI Data", "absolute_url": "https://gh/1",
     "location": {"name": "Austin, TX, USA Remote"}, "first_published": "2026-11-10T10:00:00-05:00",
     "content": "&lt;p&gt;Build things&lt;/p&gt;"},
    {"id": 2, "title": "Software Engineer, AI Data", "absolute_url": "https://gh/2",
     "location": {"name": "Berlin, Germany Remote"}, "updated_at": "2026-11-12T10:00:00-05:00",
     "content": "Build things"},
    {"id": 3, "title": "Software Engineer, Federal", "absolute_url": "https://gh/3",
     "location": {"name": "Arlington, VA"}, "content": "Active Secret clearance required."},
    {"id": 4, "title": "Account Executive", "absolute_url": "https://gh/4",
     "location": {"name": "New York, NY"}, "content": ""}]}
LEVER = [{"id": "a1", "text": "Backend Engineer", "hostedUrl": "https://lever/a1",
          "categories": {"location": "San Francisco", "allLocations": ["San Francisco", "New York"]},
          "createdAt": 1794268800000, "descriptionPlain": "APIs", "workplaceType": "hybrid",
          "lists": [{"content": "<li>Python</li>"}]}]
ASHBY = {"jobs": [
    {"id": "x", "title": "Software Engineer", "location": "San Francisco", "isListed": True,
     "secondaryLocations": [{"location": "Remote - US"}], "isRemote": True,
     "publishedAt": "2026-11-09T00:00:00.000+00:00", "jobUrl": "https://ashby/x",
     "descriptionPlain": "Ship"},
    {"id": "y", "title": "Hidden Engineer", "isListed": False}]}
SMART = {"totalFound": 1, "content": [
    {"id": "744000", "name": "Sr. Software Engineer", "releasedDate": "2026-11-08T12:00:00.000Z",
     "location": {"city": "Austin", "region": "TX", "country": "us", "remote": False}}]}
SMART_DETAIL = {"jobAd": {"sections": {"jobDescription": {"text": "<p>Java</p>"},
                                       "qualifications": {"text": "Must be a US citizen"}}}}
WORKDAY = {"total": 2, "jobPostings": [
    {"title": "Software Engineer III", "externalPath": "/job/Austin-TX/Software-Engineer-III_R1",
     "locationsText": "2 Locations", "postedOn": "Posted Today"},
    {"title": "Store Associate", "externalPath": "/job/x/Store_R2", "locationsText": "Dallas, TX",
     "postedOn": "Posted 3 Days Ago"}]}
WORKDAY_DETAIL = {"jobPostingInfo": {"jobDescription": "<p>Build services</p>", "location": "Austin, TX",
                                     "additionalLocations": ["Bentonville, AR"],
                                     "country": {"descriptor": "United States of America"},
                                     "startDate": "2026-11-12", "remoteType": "Hybrid"}}
AMAZON = {"hits": 1, "jobs": [
    {"id_icims": "999", "title": "Software Development Engineer", "job_path": "/en/jobs/999/sde",
     "normalized_location": "Seattle, Washington, USA", "posted_date": "November 10, 2026",
     "description": "Build", "basic_qualifications": "3+ years", "preferred_qualifications": ""}]}


class Parsers(unittest.TestCase):
    def test_greenhouse(self):
        jobs = feeds.parse_greenhouse(GREENHOUSE)
        self.assertEqual(len(jobs), 4)
        self.assertEqual(jobs[0]["posted"], "2026-11-10")
        self.assertTrue(jobs[0]["remote"])

    def test_lever(self):
        j = feeds.parse_lever(LEVER)[0]
        self.assertEqual((j["title"], j["locations"], j["posted"]),
                         ("Backend Engineer", ["San Francisco", "New York"], "2026-11-10"))
        self.assertIn("Python", j["text"])

    def test_ashby(self):
        jobs = feeds.parse_ashby(ASHBY)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["locations"], ["San Francisco", "Remote - US"])
        self.assertTrue(jobs[0]["remote"])

    def test_smartrecruiters(self):
        j = feeds.parse_smartrecruiters(SMART, "Visa")[0]
        self.assertEqual(j["url"], "https://jobs.smartrecruiters.com/Visa/744000")
        self.assertEqual(j["locations"], ["Austin, TX, US"])
        self.assertTrue(is_restricted(feeds.smartrecruiters_detail_text(SMART_DETAIL)))

    def test_workday(self):
        c = {"tenant": "walmart", "dc": "wd5", "site": "WalmartExternal"}
        j = feeds.parse_workday(WORKDAY, c)[0]
        self.assertEqual(j["url"], "https://walmart.wd5.myworkdayjobs.com/en-US/WalmartExternal"
                                   "/job/Austin-TX/Software-Engineer-III_R1")
        self.assertEqual(j["detail"], "https://walmart.wd5.myworkdayjobs.com/wday/cxs/walmart/"
                                      "WalmartExternal/job/Austin-TX/Software-Engineer-III_R1")
        text, locs, posted, remote = feeds.workday_detail(WORKDAY_DETAIL)
        self.assertEqual(locs, ["Austin, TX, United States of America",
                                "Bentonville, AR, United States of America"])
        self.assertEqual((posted, remote), ("2026-11-12", False))

    def test_amazon(self):
        j = feeds.parse_amazon(AMAZON)[0]
        self.assertEqual((j["id"], j["url"], j["posted"]),
                         ("999", "https://www.amazon.jobs/en/jobs/999/sde", "2026-11-10"))


class FakeHttp:
    """Serves the sample payloads above; one feed is broken on purpose."""

    def get(self, url, params=None):
        if "greenhouse.io/v1/boards/broken" in url:
            raise RuntimeError("404 Not Found")
        if "greenhouse" in url:
            return GREENHOUSE
        if "lever" in url:
            return LEVER
        if "ashbyhq" in url:
            return ASHBY
        if "smartrecruiters.com/v1/companies/Visa/postings/" in url:
            return SMART_DETAIL
        if "smartrecruiters" in url:
            return SMART
        if "amazon.jobs" in url:
            return AMAZON
        if "/wday/cxs/" in url:
            return WORKDAY_DETAIL
        raise AssertionError(url)

    def post(self, url, body):
        return WORKDAY if body["offset"] == 0 else {"total": 0, "jobPostings": []}


class Pipeline(unittest.TestCase):
    COMPANIES = [
        {"name": "GH Co", "category": "startup", "careers_url": "u", "feed": "greenhouse", "token": "gh"},
        {"name": "Broken Co", "category": "startup", "careers_url": "u", "feed": "greenhouse", "token": "broken"},
        {"name": "Lever Co", "category": "startup", "careers_url": "u", "feed": "lever", "token": "l"},
        {"name": "Ashby Co", "category": "startup", "careers_url": "u", "feed": "ashby", "token": "a"},
        {"name": "Visa", "category": "fortune500", "careers_url": "u", "feed": "smartrecruiters", "token": "Visa"},
        {"name": "Walmart", "category": "fortune500", "careers_url": "u", "feed": "workday",
         "tenant": "walmart", "dc": "wd5", "site": "WalmartExternal"},
        {"name": "Amazon", "category": "fortune500", "careers_url": "u", "feed": "amazon"},
        {"name": "Link Co", "category": "staffing", "careers_url": "u", "feed": "none"},
    ]

    def test_run(self):
        now = datetime(2026, 11, 13, 3, 0, tzinfo=timezone.utc)
        previous = {"jobs": [{"id": "broken-co:9", "company": "Broken Co", "category": "startup",
                              "title": "Software Engineer", "locations": ["Austin, TX"], "url": "u",
                              "posted": "2026-11-01", "first_seen": "2026-11-02", "us": True}]}
        jobs, status = scrape.run(self.COMPANIES, FakeHttp(), previous, now=now)
        by = {s["name"]: s for s in status["companies"]}
        titles = {(j["company"], j["title"]) for j in jobs["jobs"]}

        # Same title in two cities is one row; clearance role and sales role are gone.
        gh = [j for j in jobs["jobs"] if j["company"] == "GH Co"]
        self.assertEqual(len(gh), 1)
        self.assertEqual((gh[0]["location_count"], gh[0]["us"], gh[0]["posted"]), (2, True, "2026-11-12"))
        self.assertEqual(by["GH Co"]["restricted_removed"], 1)
        # A failing feed is reported and keeps its last good data, marked stale.
        self.assertEqual(by["Broken Co"]["state"], "failed")
        broken = [j for j in jobs["jobs"] if j["company"] == "Broken Co"]
        self.assertTrue(broken[0]["stale"])
        self.assertEqual(broken[0]["first_seen"], "2026-11-02")
        # Detail-screened feeds: the citizenship posting is removed, Workday gets real locations.
        self.assertEqual(by["Visa"]["jobs"], 0)
        self.assertEqual(by["Visa"]["restricted_removed"], 1)
        wd = [j for j in jobs["jobs"] if j["company"] == "Walmart"][0]
        self.assertEqual((wd["us"], wd["posted"], wd["screened"]), (True, "2026-11-12", True))
        self.assertIn(("Amazon", "Software Development Engineer"), titles)
        self.assertIn(("Lever Co", "Backend Engineer"), titles)
        self.assertIn(("Ashby Co", "Software Engineer"), titles)
        self.assertEqual(by["Link Co"]["state"], "link_only")
        self.assertNotIn("text", jobs["jobs"][0])
        dates = [j.get("posted") or j["first_seen"] for j in jobs["jobs"]]
        self.assertEqual(dates, sorted(dates, reverse=True))
        json.dumps(jobs), json.dumps(status)

    def test_offline_and_config(self):
        companies = json.loads((Path(scrape.ROOT) / "companies.json").read_text())["companies"]
        self.assertEqual(len({c["name"] for c in companies}), len(companies))
        for c in companies:
            self.assertIn(c["feed"], set(feeds.FETCHERS) | {"none"})
            if c["feed"] == "workday":
                self.assertTrue(all(c.get(k) for k in ("tenant", "dc", "site")), c["name"])
            elif c["feed"] in ("greenhouse", "lever", "ashby", "smartrecruiters"):
                self.assertTrue(c.get("token"), c["name"])
        jobs, status = scrape.run(companies, None, offline=True)
        self.assertEqual(jobs["count"], 0)
        self.assertEqual({s["state"] for s in status["companies"]}, {"pending", "link_only"})


if __name__ == "__main__":
    unittest.main()
