#!/usr/bin/env python3
"""
Fetch latest Douban activities from user's RSS feed and cache posters locally.
Generates _data/douban.json for Jekyll site rendering.
"""

import os
import re
import json
import email.utils
from datetime import datetime
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

USER_ID = "162112893"
FEED_URL = f"https://www.douban.com/feed/people/{USER_ID}/interests"

# Resolve directories relative to project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_JSON = os.path.join(BASE_DIR, "_data", "douban.json")
IMAGES_DIR = os.path.join(BASE_DIR, "images", "douban")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.douban.com/",
}

RATING_STARS = {
    "力荐": 5,
    "推荐": 4,
    "还行": 3,
    "较差": 2,
    "很差": 1,
}

def parse_action_and_title(raw_title):
    pattern = r"^(看过|想看|在看|读过|想读|在读|听过|想听|在听)(.*)$"
    m = re.match(pattern, raw_title.strip())
    if m:
        action = m.group(1).strip()
        title = m.group(2).strip()
        return action, title
    return "动态", raw_title.strip()

def download_image(url, save_path, referer="https://movie.douban.com/"):
    if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
        return True
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": HEADERS["User-Agent"],
                "Referer": referer,
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp, open(save_path, "wb") as f:
            f.write(resp.read())
        return True
    except Exception as e:
        print(f"Warning: Failed to download poster {url}: {e}")
        return False

def fetch_feed():
    print(f"Fetching Douban feed from {FEED_URL}...")
    req = urllib.request.Request(FEED_URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        xml_content = resp.read()
    return xml_content

def process_feed(xml_content):
    root = ET.fromstring(xml_content)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("Invalid RSS: <channel> element not found")

    items = channel.findall("item")
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)

    results = []

    for item in items:
        raw_title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        pub_date_str = item.findtext("pubDate", "").strip()
        desc = item.findtext("description", "").strip()

        action, title = parse_action_and_title(raw_title)

        # Subject ID
        id_match = re.search(r"/subject/(\d+)/?", link)
        subject_id = id_match.group(1) if id_match else ""

        # Media type
        media_type = "movie"
        if "book.douban.com" in link:
            media_type = "book"
        elif "music.douban.com" in link:
            media_type = "music"

        # Rating extraction
        rating_match = re.search(r"推荐:\s*([^\s<]+)", desc)
        rating_text = rating_match.group(1) if rating_match else ""
        stars = RATING_STARS.get(rating_text, 0)

        # Poster image URL extraction
        poster_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
        poster_url = poster_match.group(1) if poster_match else ""

        # Local poster handling
        local_poster_path = ""
        if poster_url and subject_id:
            filename = f"{subject_id}.jpg"
            target_file = os.path.join(IMAGES_DIR, filename)
            referer = f"https://{media_type}.douban.com/"
            if download_image(poster_url, target_file, referer):
                local_poster_path = f"images/douban/{filename}"

        # Parse date
        formatted_date = ""
        short_date = ""
        if pub_date_str:
            try:
                parsed_tuple = email.utils.parsedate_to_datetime(pub_date_str)
                formatted_date = parsed_tuple.strftime("%Y-%m-%d")
                short_date = parsed_tuple.strftime("%m-%d")
            except Exception:
                formatted_date = pub_date_str

        results.append({
            "title": title or raw_title,
            "raw_title": raw_title,
            "action": action,
            "link": link,
            "subject_id": subject_id,
            "media_type": media_type,
            "rating": rating_text,
            "stars": stars,
            "poster": local_poster_path,
            "poster_url": poster_url,
            "date": formatted_date,
            "short_date": short_date,
        })

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Successfully processed {len(results)} items and saved to {OUTPUT_JSON}")
    return results

if __name__ == "__main__":
    content = fetch_feed()
    items = process_feed(content)
