#!/usr/bin/env python3
"""Builds the blog for aslanmammadli.com.

Write posts as posts/<slug>.md with a front matter block:

---
title: Post title
date: 2026-11-03
description: One sentence summary shown on cards and in search results.
label: Short cover label
tagline: Bold line under the label on the cover
color: orange | teal | pink | lilac | yellow | sky
---
Markdown body...

Then run:  python3 build.py
It writes site/blog/index.html, site/blog/<slug>/index.html, updates the
latest 3 posts on site/index.html and regenerates site/sitemap.xml.
"""
import html, json, pathlib, re, datetime
import markdown

ROOT = pathlib.Path(__file__).parent
SITE = ROOT / "site"
BASE = "https://aslanmammadli.com"
PAGES = []


def parse(path):
    raw = path.read_text()
    m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    meta = dict(line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)
    meta = {k.strip(): v.strip() for k, v in meta.items()}
    meta["slug"] = path.stem
    meta["body"] = markdown.markdown(m.group(2), extensions=["extra", "sane_lists"])
    meta["dt"] = datetime.date.fromisoformat(meta["date"])
    return meta


def esc(s):
    return html.escape(s, quote=True)


def card(p):
    return f'''        <a class="card" href="/blog/{p["slug"]}/">
          <div class="cover c-{esc(p.get("color", "orange"))}"><span class="pill">{esc(p["label"])}</span><span class="tag">{esc(p["tagline"])}</span></div>
          <h3>{esc(p["title"])}</h3>
          <p>{esc(p["description"])}</p>
        </a>'''


HEADER = '''<header class="top">
    <a class="name" href="/">Aslan Mammadli</a>
    <nav><a href="/about/">About</a><a href="/blog/">Blog</a><a href="/expertise/">Expertise</a><a href="/hobby/">Hobby</a></nav>
  </header>'''


def page(title, desc, url, body, extra_head=""):
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-TJHP44GXYY"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-TJHP44GXYY');
</script>
<meta name="color-scheme" content="light">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{BASE}/aslan-mammadli-large.jpg">
<meta name="twitter:card" content="summary">
<link rel="stylesheet" href="/style.css">
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
{extra_head}</head>
<body>
<div class="wrap">
  {HEADER}
{body}
  <footer>© {datetime.date.today().year} Aslan Mammadli</footer>
</div>
</body>
</html>
'''


def main():
    posts = sorted((parse(p) for p in (ROOT / "posts").glob("*.md")),
                   key=lambda p: (p["dt"], p.get("order", "0")), reverse=True)

    # Post pages
    for p in posts:
        url = f'{BASE}/blog/{p["slug"]}/'
        ld = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": p["title"],
              "description": p["description"], "datePublished": p["date"], "url": url,
              "author": {"@id": f"{BASE}/#person", "@type": "Person", "name": "Aslan Mammadli", "url": BASE + "/"}}
        head = f'<meta property="og:type" content="article">\n<script type="application/ld+json">{json.dumps(ld)}</script>\n'
        body = f'''  <main>
    <article>
      <div class="post-head">
        <h1>{esc(p["title"])}</h1>
        <div class="meta">{p["dt"].strftime("%B %-d, %Y")} · Aslan Mammadli</div>
      </div>
      <div class="prose">
{p["body"]}
      </div>
    </article>
    <a class="back" href="/blog/">← All posts</a>
  </main>'''
        out = SITE / "blog" / p["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page(f'{p["title"]} | Aslan Mammadli', p["description"], url, body, head))

    # Standalone pages (pages/<slug>.md -> /<slug>/)
    for f in (ROOT / "pages").glob("*.md"):
        raw = f.read_text()
        m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
        meta = {k.strip(): v.strip() for k, v in (l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)}
        url = f"{BASE}/{f.stem}/"
        ld = {"@context": "https://schema.org", "@type": "AboutPage" if f.stem == "about" else "WebPage",
              "url": url, "mainEntity": {"@id": f"{BASE}/#person", "@type": "Person", "name": "Aslan Mammadli"}}
        head = f'<script type="application/ld+json">{json.dumps(ld)}</script>\n'
        body = f'''  <main>
    <h1 class="page-title">{esc(meta["title"])}</h1>
    <div class="prose">
{markdown.markdown(m.group(2), extensions=["extra", "sane_lists"])}
    </div>
  </main>'''
        out = SITE / f.stem / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page(f'{meta["title"]} | Aslan Mammadli', meta["description"], url, body, head))
        PAGES.append(url)

    # Blog index
    cards = "\n".join(card(p) for p in posts) or "      <p>No posts yet.</p>"
    body = f'''  <main>
    <h1 class="page-title">Blog</h1>
    <p class="lead">Notes on building AI products, language learning and startups.</p>
    <div class="cards three wide">
{cards}
    </div>
  </main>'''
    (SITE / "blog").mkdir(exist_ok=True)
    (SITE / "blog" / "index.html").write_text(
        page("Blog | Aslan Mammadli", "Posts by Aslan Mammadli on AI, language learning and startups.", f"{BASE}/blog/", body))

    # Latest 3 on the homepage
    home = SITE / "index.html"
    s = home.read_text()
    latest = "\n".join(card(p) for p in posts[:3])
    s = re.sub(r"(<!-- LATEST:START -->).*?(\s*<!-- LATEST:END -->)", lambda m: m.group(1) + "\n" + latest + m.group(2), s, flags=re.S)
    home.write_text(s)

    # Sitemap
    today = datetime.date.today().isoformat()
    urls = [(BASE + "/", today)] + [(u, today) for u in PAGES] + [(BASE + "/blog/", today)] + [(f'{BASE}/blog/{p["slug"]}/', p["date"]) for p in posts]
    sm = "\n".join(f"  <url><loc>{u}</loc><lastmod>{d}</lastmod></url>" for u, d in urls)
    (SITE / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{sm}\n</urlset>\n')
    print(f"built {len(posts)} posts")


if __name__ == "__main__":
    main()
