import requests
from bs4 import BeautifulSoup
import os
import json
import time

CONFIG_FILE = "config.json"
DATA_FILE = "ads_seen.json"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Configuration file '{CONFIG_FILE}' not found.")
        exit(1)
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config


def fetch_ads(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    ads = []

    for tr in soup.find_all("tr", id=lambda x: x and x.startswith("tr_")):
        ad = {}
        try:
            ad_id = tr["id"]
            title_tag = tr.select_one("a.am")
            title = title_tag.get_text(strip=True)
            link = title_tag["href"]
            full_link = "https://www.ss.lv" + link

            ad["id"] = ad_id
            ad["title"] = title
            ad["link"] = full_link

            ads.append(ad)
        except Exception as e:
            print(f"Skipping a row due to error: {e}")
            continue
    return ads


def load_seen_ads():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        seen_ads = json.load(f)
    return seen_ads


def save_seen_ads(seen_ads):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_ads, f, ensure_ascii=False, indent=2)


def send_discord_notification(webhook_url, new_ads, url):
    if not new_ads:
        return

    content = f"Found {len(new_ads)} new advertisement(s) for URL: {url}\n"

    embeds = []
    for ad in new_ads:
        embed = {
            "title": ad.get("title", "No Title"),
            "url": ad.get("link", url),
            "description": f"New ad found: {ad.get('title', 'No Title')}",
        }
        embeds.append(embed)

    # Split embeds into chunks of 10 to comply with Discord's limit
    max_embeds_per_message = 10
    embed_chunks = [
        embeds[i : i + max_embeds_per_message]
        for i in range(0, len(embeds), max_embeds_per_message)
    ]

    for chunk in embed_chunks:
        message = {"content": content, "embeds": chunk}
        try:
            response = requests.post(webhook_url, json=message)
            if response.status_code in (200, 204):
                print(f"Notification sent for {len(chunk)} ads.")
            else:
                print(f"Failed to send notification. Response: {response.text}")
        except Exception as e:
            print(f"Error sending Discord notification: {e}")
        # Delay to prevent hitting rate limits
        time.sleep(0.5)


def main():
    print("Starting advertisement monitor...")

    config = load_config()
    webhook_url = config.get("discord_webhook_url")
    urls_to_track = config.get("urls_to_track", [])

    if not webhook_url or not urls_to_track:
        print("Webhook URL or URLs to track are missing in the configuration file.")
        exit(1)

    seen_ads = load_seen_ads()

    for url in urls_to_track:
        print(f"Checking for new advertisements on URL: {url}")
        ads = fetch_ads(url)
        current_ad_ids = set(ad["id"] for ad in ads)
        url_key = url.replace("https://", "").replace("http://", "").rstrip("/")
        seen_ad_ids = set(seen_ads.get(url_key, {}).keys())
        new_ad_ids = current_ad_ids - seen_ad_ids

        if new_ad_ids:
            print(f"Found {len(new_ad_ids)} new advertisement(s) on {url}.")
            new_ads = [ad for ad in ads if ad["id"] in new_ad_ids]

            send_discord_notification(webhook_url, new_ads, url)

            if url_key not in seen_ads:
                seen_ads[url_key] = {}
            for ad in new_ads:
                seen_ads[url_key][ad["id"]] = {
                    "id": ad["id"],
                    "title": ad["title"],
                    "link": ad["link"],
                }
            save_seen_ads(seen_ads)
        else:
            print(f"No new advertisements found on {url}.")

        # Delay between processing URLs to avoid overloading the server
        time.sleep(1)


if __name__ == "__main__":
    main()
