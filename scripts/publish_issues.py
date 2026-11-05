import os
import re
import json
import html
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime, timezone

import markdown
from bs4 import BeautifulSoup

REPOSITORY = os.environ["GH_REPOSITORY"]
TOKEN = os.environ["GH_TOKEN"]

SITE_NAME = "Practical Window Guide"
BASE_PATH = "/practical-window-guide/"
OWNER = REPOSITORY.split("/")[0]
BASE_URL = f"https://{OWNER}.github.io{BASE_PATH}"

ARTICLES_DIR = Path("articles")
ARTICLES_DIR.mkdir(exist_ok=True)

API = f"https://api.github.com/repos/{REPOSITORY}/issues"

ALLOWED_TAGS = {
    "p", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "b", "em", "i", "s", "del",
    "ul", "ol", "li", "blockquote", "hr",
    "a", "img", "pre", "code",
    "table", "thead", "tbody", "tr", "th", "td"
}

REMOVE_TAGS = {
    "script", "style", "iframe", "object", "embed",
    "form", "input", "button", "svg", "math",
    "meta", "link", "base", "template"
}


def safe_html(value):
    return html.escape(str(value or ""), quote=True)


def get_issues():
    issues = []
    page = 1

    while True:
        params = urllib.parse.urlencode({
            "state": "open",
            "per_page": 100,
            "page": page,
            "sort": "created",
            "direction": "desc"
        })

        request = urllib.request.Request(
            f"{API}?{params}",
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "PracticalWindowGuidePublisher"
            }
        )

        with urllib.request.urlopen(
            request, timeout=30
        ) as response:
            data = json.load(response)

        if not data:
            break

        issues.extend(
            item for item in data
            if "pull_request" not in item
        )

        if len(data) < 100:
            break

        page += 1

    return issues


def clean_html(content):
    rendered = markdown.markdown(
        content or "",
        extensions=["extra", "sane_lists", "nl2br"]
    )

    soup = BeautifulSoup(rendered, "html.parser")

    for tag in list(soup.find_all(REMOVE_TAGS)):
        tag.decompose()

    for tag in list(soup.find_all(True)):
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            continue

        if tag.name == "a":
            href = str(tag.get("href", "")).strip()
            parsed = urllib.parse.urlsplit(href)

            if parsed.scheme.lower() not in ("http", "https"):
                tag.unwrap()
                continue

            title = tag.get("title")
            tag.attrs = {"href": href, "rel": "noopener noreferrer"}

            if title:
                tag["title"] = str(title)

        elif tag.name == "img":
            src = str(tag.get("src", "")).strip()
            parsed = urllib.parse.urlsplit(src)

            if parsed.scheme.lower() not in ("http", "https"):
                tag.decompose()
                continue

            alt = str(tag.get("alt", ""))
            tag.attrs = {
                "src": src,
                "alt": alt,
                "loading": "lazy"
            }

        elif tag.name in ("th", "td"):
            tag.attrs = {}

        else:
            tag.attrs = {}

    return str(soup)


def page_template(title, content, date, canonical):
    safe_title = safe_html(title)
    safe_date = safe_html(date)
    safe_name = safe_html(SITE_NAME)
    safe_canonical = safe_html(canonical)
    description = safe_html(title[:155])
    year = datetime.now(timezone.utc).year

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="index, follow">
<meta name="description" content="{description}">
<link rel="canonical" href="{safe_canonical}">
<title>{safe_title} | {safe_name}</title>
<style>
* {{
  box-sizing: border-box;
}}
body {{
  margin: 0;
  background: #f6f5f1;
  color: #343c42;
  font: 16px/1.8 Arial, sans-serif;
}}
header, footer {{
  background: #fff;
  padding: 28px 20px;
  text-align: center;
  border-bottom: 1px solid #e7e5df;
}}
header a {{
  color: #29465b;
  font-size: 22px;
  font-weight: bold;
  text-decoration: none;
}}
main {{
  max-width: 850px;
  margin: 45px auto;
  padding: 35px;
  background: #fff;
  border: 1px solid #e9e7e1;
  border-radius: 12px;
}}
h1, h2, h3, h4 {{
  color: #29465b;
  line-height: 1.4;
}}
h1 {{
  font-size: 32px;
}}
a {{
  color: #29465b;
}}
time {{
  color: #68747c;
  font-size: 14px;
}}
.article-content {{
  overflow-wrap: anywhere;
}}
.article-content p {{
  margin: 16px 0;
}}
.article-content img {{
  display: block;
  max-width: 100%;
  height: auto;
  margin: 20px 0;
  border-radius: 6px;
}}
.article-content blockquote {{
  border-left: 4px solid #a59b84;
  padding: 10px 20px;
  margin: 20px 0;
  background: #f6f5f1;
}}
.article-content pre {{
  overflow-x: auto;
  padding: 16px;
  background: #f6f5f1;
}}
.article-content table {{
  display: block;
  max-width: 100%;
  overflow-x: auto;
  border-collapse: collapse;
}}
.article-content th,
.article-content td {{
  padding: 10px;
  border: 1px solid #ddd;
  text-align: left;
}}
footer {{
  color: #68747c;
  font-size: 14px;
}}
@media (max-width: 600px) {{
  main {{
    margin: 20px 12px;
    padding: 22px;
  }}
  h1 {{
    font-size: 26px;
  }}
}}
</style>
</head>
<body>
<header>
<a href="{BASE_URL}">{safe_name}</a>
</header>
<main>
<article>
<h1>{safe_title}</h1>
<p><time datetime="{safe_date}">{safe_date}</time></p>
<div class="article-content">
{content}
</div>
</article>
</main>
<footer>&copy; {year} {safe_name}</footer>
</body>
</html>"""


def create_article(issue):
    number = issue["number"]
    title = issue.get("title") or f"Article {number}"
    body = issue.get("body") or ""
    date = (issue.get("created_at") or "")[:10]

    filename = f"issue-{number}.html"
    canonical = f"{BASE_URL}articles/{filename}"

    article_html = page_template(
        title,
        clean_html(body),
        date,
        canonical
    )

    (ARTICLES_DIR / filename).write_text(
        article_html,
        encoding="utf-8"
    )

    return {
        "title": title,
        "url": f"{BASE_PATH}articles/{filename}",
        "date": date,
        "number": number
    }


def update_homepage(articles):
    path = Path("index.html")

    soup = BeautifulSoup(
        path.read_text(encoding="utf-8"),
        "html.parser"
    )

    container = soup.select_one(".article-list")

    if container is None:
        raise RuntimeError(
            "Article list not found in index.html"
        )

    container.clear()

    if not articles:
        paragraph = soup.new_tag("p")
        paragraph.string = "No articles published yet."
        container.append(paragraph)

    for article in articles:
        paragraph = soup.new_tag("p")
        link = soup.new_tag(
            "a",
            href=article["url"]
        )
        link.string = article["title"]
        paragraph.append(link)
        container.append(paragraph)

    path.write_text(
        str(soup),
        encoding="utf-8"
    )


def main():
    issues = get_issues()

    active_files = {
        f"issue-{issue['number']}.html"
        for issue in issues
    }

    for file in ARTICLES_DIR.glob("issue-*.html"):
        if file.name not in active_files:
            file.unlink()
            print(f"Removed closed article: {file.name}")

    issues.sort(
        key=lambda item: item.get("created_at", ""),
        reverse=True
    )

    articles = []

    for issue in issues:
        articles.append(create_article(issue))

    update_homepage(articles)

    print(f"Published {len(articles)} articles")


if __name__ == "__main__":
    main()
