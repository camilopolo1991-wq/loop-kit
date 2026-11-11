---
name: public-job-board-harvest
description: Use when harvesting public job boards. Endpoints and traps.
version: 1.0.1
author: hermes
license: internal
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [jobs, scraping, apis, harvest]
    related_skills: [blocked-page-recovery, grounded-citations]
---

# Public job-board harvest (no login, no key)

Harvest listings into one JSON artefact, filter in Python, dedupe by normalised url.
Every row carries `provenance: "measured <source> <YYYY-MM-DD>"` and its url.

## When to Use

- Collecting open roles or contracts from remote job boards with no key and no login.
- A harvest returned far fewer rows than the board visibly holds (check the date-format
  and pagination traps below before widening queries).
- A job-board fetch is blocked and you need to know which walls are real.

## Source facts (measured 2026-10-23)

| source | endpoint | shape | gotcha |
|---|---|---|---|
| remoteok | `https://remoteok.com/api` and `?tag=<t>` | JSON list, element 0 is a legal notice, skip rows without `position` | `epoch` is the date. Tags `ai`, `api`, `python`, `react` return ~100 each. Tags `automation`, `n8n`, `integration` return **0** |
| remotive | `https://remotive.com/api/remote-jobs?search=<q>` | `{"jobs": [...]}` | `publication_date` is `2026-10-17T16:04:29`, **no timezone**. A parser lacking `%Y-%m-%dT%H:%M:%S` silently drops every row. Results are loosely matched and mostly off-topic |
| himalayas | `https://himalayas.app/jobs/api?limit=100&offset=<n>` | `{"jobs": [...]}` | `limit=100` is ignored, it always returns **20**. Page with `offset += len(jobs)`. `pubDate` is a unix epoch. 120k+ rows, so stop on the first page whose oldest date passes the cutoff, not on a fixed page count. `guid` is the public url |
| weworkremotely | `https://weworkremotely.com/categories/<cat>.rss` | RSS, parse with `xml.etree` | `<title>` is `Company: Role`, split on the first colon. `pubDate` is RFC 822 |
| jobicy | `https://jobicy.com/api/v2/remote-jobs?count=50&<filters>` | `{"jobs": [...]}` | invalid filter values return **HTTP 400**, not an empty list. Valid: `industry=dev|engineering|data-science|technical-support|hr|business`, `geo=usa|anywhere|latam|canada|emea`, `tag=automation|python|...`. `industry=devops|product|it` and `tag=ai` are **400** |
| linkedin | `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=<q>&location=<loc>&f_WT=2&f_TPR=r2592000&start=<n>` | HTML `<li>` fragment | works logged out, 10 per page, `start` steps by 10. By far the richest source for automation titles. `f_WT=2` is remote, `f_TPR=r2592000` is last 30 days |
| linkedin detail | `https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/<jobId>` | HTML | `jobId` is the trailing digit run of the `/jobs/view/...` url. Gives the full description logged out. ~85% return real text |
| upwork | `https://www.upwork.com/nx/search/jobs/?q=...` | - | **Cloudflare blocks a logged-out browser**: "Sorry, you have been blocked". Record it as blocked, do not retry variants |

## Browser pitfalls

- Do **not** `fetch()` the LinkedIn guest endpoint from inside `js()`: the active tab's
  origin is usually something else and it dies with `TypeError: Failed to fetch` (CORS).
  `goto_url(url)` + `wait_for_load()` + parse the DOM instead. 48 navigations ran clean.
- Never put a literal `%20` in a string you then `%`-format. `"...%20States...start=%d" % n`
  raises `ValueError: unsupported format character 'S'`. Concatenate `str(n)` instead.

## Filtering that actually holds

- Two title regexes: an include set, and an exclude set for
  senior/staff/principal/lead/architect/manager/director plus QA, test-automation, SDET,
  tester, intern. Roman numerals: exclude `\bii+\b` and `\b(iii|iv)\b`.
- Generic titles (`software engineer`, `backend engineer`, `full-stack engineer`,
  `solutions engineer`) only count when an **edge regex** matches the tags or body
  (`n8n|zapier|webhooks|integrations|openai|llm|applicant tracking|...`). Without this
  gate a harvest fills with unrelated SWE reqs.
- Years-of-experience exclusion runs on the **first ~4000 chars** of the body only;
  the tail is boilerplate and produces false rejects.
- Keep reject counters per reason (`title`, `date`, `nodate`, `senior_body`, `dupe`,
  `no_edge`) and print them. `nodate` spiking to a round number is the date-format bug.

## Two-stage dedupe

1. Primary: normalised url (strip query string, strip trailing slash, lowercase).
2. Secondary flag, not a delete: LinkedIn republishes one req per metro area under
   distinct job ids. Mark `is_primary_posting=false` + `same_posting_as=<url>` when
   company+title already appeared. Keep the rows, exclude them from any shortlist.
   Measured: 186 unique urls collapsed to 164 distinct postings.

## Shortlisting

Score from weighted regex hits over title + tags + description, store the hit list in
`match_signals` so the ranking is auditable. Flag location locks from the text
(`NEW YORK ONLY`, `remote in CA`, `must reside in`, `hybrid`, `security clearance`,
`TS/SCI`) and drop those from the shortlist for an offshore candidate.

## Liveness probe caveat

A bare `urllib` GET of a shortlisted url returns 403 on himalayas and 429 on linkedin
under any speed. That is a bot wall, **not** a dead listing. Say so beside the number
rather than reporting the listing as gone.

## Runtime

Full run across six sources, ~7000 raw rows: about 5 minutes with 0.6-1s between fetches.
Run it as a background process redirected to a log, then poll, and read the log with
`read_file`. A foreground call over 600s is promoted to background anyway, and piping
the run through a pager hides all progress until it exits.
