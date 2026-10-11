"""Discover public model download links from the official character pages.
Reads bounded HTML only; does not execute page scripts or download models.
"""
import json
import urllib.request
import urllib.error
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

PAGES = [
    "https://studio.blender.org/characters/snow/v4/",
    "https://studio.blender.org/characters/rain/v3/",
]

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            self.anchor = [attributes["href"], ""]
            self.links.append(self.anchor)
        for key, value in attrs:
            if value and key != "href" and (".zip" in value.lower() or ".blend" in value.lower()):
                self.links.append([value, key])

    def handle_data(self, text):
        if self.anchor is not None:
            self.anchor[1] += text

    def handle_endtag(self, tag):
        if tag == "a":
            self.anchor = None

for page in PAGES:
    try:
        request = urllib.request.Request(page, headers={"User-Agent": "Coop-AI-Game-Asset-Discovery/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError("PAGE_LIMIT")
            parser = Links()
            parser.feed(data.decode("utf-8", "replace"))
            links = []
            for href, label in parser.links:
                url = urljoin(page, href)
                parsed = urlsplit(url)
                if parsed.scheme != "https" or parsed.username or parsed.password:
                    continue
                if not (".zip" in parsed.path.lower() or ".blend" in parsed.path.lower()
                        or "download" in label.lower()):
                    continue
                item = {"label": label.strip()[:120]}
                # Never log query credentials or signed download URLs.
                if parsed.query or parsed.fragment:
                    item["has_query_or_fragment"] = True
                else:
                    item["url"] = url
                links.append(item)
            print(json.dumps({"page": page, "status": response.status, "download_links": links[:40]}))
    except urllib.error.HTTPError as error:
        print(json.dumps({"page": page, "http_status": error.code}))
    except Exception as error:
        print(json.dumps({"page": page, "error_type": type(error).__name__}))
