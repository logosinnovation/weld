#!/usr/bin/env python3
"""Fetch a web page (or PDF) and print its visible text, for exact quoting.

Usage:
  python3 tools/fetch_page.py URL                  # print text (first 60k chars)
  python3 tools/fetch_page.py URL --grep "phrase"  # print lines containing phrase (case-insensitive)
  python3 tools/fetch_page.py URL --browser        # force headless Chromium
  python3 tools/fetch_page.py URL --check "exact quote"  # exit 0 if quote is on the page, 1 if not

Tries a plain HTTPS request first. If that is refused (403/429/503, Cloudflare
challenge) or returns almost no text, it retries in headless Chromium, which is
the project's rule for sites that block plain page fetches.
"""
import re
import subprocess
import sys
import tempfile

import requests
from bs4 import BeautifulSoup

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
SEC_UA = "PathProspectMap research client research@example.com"

PW_JS = r"""
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ userAgent: process.argv[3] });
  let status = 0;
  try {
    const r = await p.goto(process.argv[2], { waitUntil: 'domcontentloaded', timeout: 60000 });
    status = r ? r.status() : 0;
    await p.waitForTimeout(6000);
  } catch (e) { console.error('NAV_ERROR ' + e.message.split('\n')[0]); }
  let t = '';
  for (const f of p.frames()) {
    try { t += '\n' + await f.evaluate(() => document.body ? document.body.innerText : ''); } catch (e) {}
  }
  if (process.argv[4] === 'raw') {
    for (const f of p.frames()) {
      try { t += '\n__RAW_SOURCE__\n' + (await f.content()).replace(/\\\//g, '/').replace(/&quot;/g, '"').replace(/&amp;/g, '&'); } catch (e) {}
    }
  }
  console.log('__STATUS__ ' + status);
  console.log(t);
  await b.close();
})();
"""


def norm(s):
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    s = s.replace("–", "-").replace("—", "-").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip().lower()


def html_to_text(html):
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    text = soup.get_text("\n")
    return "\n".join(l.strip() for l in text.splitlines() if l.strip())


def raw_tail(html):
    """Raw page source with JSON/HTML escapes undone, so quotes taken from
    JSON-LD (datePosted, streetAddress) or itemprop attributes can be checked."""
    h = html.replace("\\/", "/").replace("&quot;", '"').replace("&amp;", "&").replace("&#39;", "'")
    return "\n__RAW_SOURCE__\n" + h


def plain(url, with_raw=False):
    ua = SEC_UA if "sec.gov" in url else UA
    r = requests.get(url, headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"},
                     timeout=45, allow_redirects=True)
    ctype = r.headers.get("content-type", "")
    if "pdf" in ctype or url.lower().endswith(".pdf") or r.content[:5] == b"%PDF-":
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(r.content)
            f.flush()
            out = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True)
            return r.status_code, out.stdout
    return r.status_code, html_to_text(r.text) + (raw_tail(r.text) if with_raw else "")


def browser(url, with_raw=False):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(PW_JS)
        js = f.name
    out = subprocess.run(["node", js, url, UA] + (["raw"] if with_raw else []), capture_output=True, text=True, timeout=150)
    m = re.search(r"__STATUS__ (\d+)", out.stdout)
    status = int(m.group(1)) if m else 0
    text = out.stdout.split("\n", 1)[1] if m else out.stdout
    return status, text


def fetch(url, force_browser=False, with_raw=False):
    if not force_browser:
        try:
            status, text = plain(url, with_raw)
            blocked = status in (401, 403, 406, 429, 503) or "just a moment" in text[:400].lower() \
                or "enable javascript" in text[:600].lower()
            if not blocked and status < 400 and len(text.split("\n__RAW_SOURCE__\n")[0]) > 300:
                return status, text, "plain"
        except Exception as e:  # noqa: BLE001
            print(f"# plain fetch failed: {e}", file=sys.stderr)
    status, text = browser(url, with_raw)
    return status, text, "browser"


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    url = args[0]
    force = "--browser" in args
    # --check always also searches the raw page source (JSON-LD, itemprop attributes);
    # --raw prints it too.
    status, text, how = fetch(url, force, with_raw=("--check" in args or "--raw" in args))
    if "--raw" not in args and "--check" not in args:
        text = text.split("\n__RAW_SOURCE__\n")[0]
    print(f"# status={status} via={how} chars={len(text)}", file=sys.stderr)
    if "--check" in args:
        q = args[args.index("--check") + 1]
        if status >= 400:
            # an error page can carry the string (list-auditor R3-D, 2026-11-17): never report FOUND on one
            print(f"HTTP_ERROR {status}")
            sys.exit(2)
        ok = norm(q) in norm(text)
        print("FOUND" if ok else "NOT_FOUND")
        sys.exit(0 if ok else 1)
    if "--grep" in args:
        q = args[args.index("--grep") + 1].lower()
        for line in text.splitlines():
            if q in line.lower():
                print(line.strip()[:500])
        return
    print(text[:60000])


if __name__ == "__main__":
    main()
