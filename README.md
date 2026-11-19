# Software Engineering Jobs

A job board that lists only software engineering roles from 137 companies and refreshes itself
every 6 hours on GitHub, free, with no server.

- `companies.json` lists every company and where its jobs come from.
- `scraper/` fetches the roles, keeps software engineering titles, and drops postings that ask
  for US citizenship or a security clearance.
- `site/` is the website. `site/jobs.json` and `site/status.json` are rewritten on every update.
- `.github/workflows/update.yml` runs the update every 6 hours and publishes the site.

## One-time setup (about 5 minutes)

1. Sign in to GitHub and create a new **public** repository (for example `swe-jobs`). Public
   repositories get GitHub Pages and Actions for free.
2. Upload everything in this folder to the repository, keeping the folder structure.
   - With git: `git init -b main && git add -A && git commit -m "Job board" && git remote add origin <repo url> && git push -u origin main`
   - In the browser: **Add file → Upload files**, then drag all files and folders in. The
     `.github` folder is hidden on most computers, so if it does not upload, choose
     **Add file → Create new file**, name it `.github/workflows/update.yml`, and paste in the
     contents of that file.
3. In the repository, open **Settings → Pages** and set **Source** to **GitHub Actions**.
4. Open **Settings → Actions → General → Workflow permissions**, choose **Read and write
   permissions**, and save.
5. Open the **Actions** tab, choose **Update jobs**, and click **Run workflow**. The first run
   takes 10 to 30 minutes.
6. Your site is at `https://<your-username>.github.io/<repository-name>/`.

After that it updates on its own every 6 hours.

## After the first run

Open the site and scroll to **Sources**, or open `site/status.json`:

- **Live feeds** worked.
- **Feeds that failed** have a wrong address in `companies.json`. Most feed addresses there are
  marked `"verified": false`: they are best guesses that were never tested. Fix the token, or
  set `"feed": "none"` to show that company as a link only. A failed feed never stops the others.
- **Link only** companies have no public job feed, so the site links to their careers page.

## Good to know

- Roles marked "Requirements not checked" could not be screened for citizenship or clearance
  wording (the posting text was unavailable). Read those postings yourself.
- The citizenship and clearance check is a keyword match, so it can miss unusual wording.
- GitHub pauses scheduled runs in repositories with no activity for 60 days. The update commits
  new data each run, which normally counts as activity; if updates stop, run it by hand once.
- Run it on your own computer: `pip install -r requirements.txt`, `python -m scraper.scrape`,
  then `python -m http.server -d site` and open http://localhost:8000.
- Test one company: `python -m scraper.scrape --only Stripe`.
- Run the tests: `python -m unittest`.
