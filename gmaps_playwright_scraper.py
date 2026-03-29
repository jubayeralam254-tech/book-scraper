import argparse
import csv
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

CSV_FIELDS = ["category", "city", "name", "address", "phone", "map_url"]


def setup_logging(log_file: str) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def ensure_csv(output_csv: str) -> None:
    if not os.path.exists(output_csv) or os.path.getsize(output_csv) == 0:
        with open(output_csv, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
            writer.writeheader()


def load_seen_urls(output_csv: str) -> set:
    seen_urls = set()
    if not os.path.exists(output_csv):
        return seen_urls

    with open(output_csv, "r", newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            map_url = (row.get("map_url") or "").strip()
            if map_url:
                seen_urls.add(map_url)
    return seen_urls


def append_row(output_csv: str, row: dict) -> None:
    with open(output_csv, "a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writerow(row)


def save_checkpoint(checkpoint_file: str, city: str, category: str, next_index: int) -> None:
    data = {
        "city": city,
        "category": category,
        "next_index": next_index,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(checkpoint_file, "w", encoding="utf-8") as checkpoint:
        json.dump(data, checkpoint, ensure_ascii=False, indent=2)


def load_checkpoint(checkpoint_file: str, city: str, category: str) -> int:
    if not os.path.exists(checkpoint_file):
        return 0

    try:
        with open(checkpoint_file, "r", encoding="utf-8") as checkpoint:
            data = json.load(checkpoint)
    except Exception:
        return 0

    if data.get("city") == city and data.get("category") == category:
        return int(data.get("next_index", 0))
    return 0


def safe_inner_text(locator, timeout_ms: int = 3000) -> str:
    try:
        if locator.count() > 0:
            return locator.first.inner_text(timeout=timeout_ms).strip()
    except Exception:
        return ""
    return ""


def normalize_phone(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""

    match = re.search(r"\+?\d[\d\s().-]{6,}\d", value)
    if match:
        return match.group(0).strip()
    return value


def extract_phone(page) -> str:
    phone = safe_inner_text(page.locator("button[data-item-id^='phone:'] div.fontBodyMedium"))
    if phone:
        return normalize_phone(phone)

    panel_text = safe_inner_text(page.locator("div[role='main']"), timeout_ms=4000)
    return normalize_phone(panel_text)


def try_accept_consent(page) -> None:
    labels = ["Accept all", "I agree", "Reject all"]
    for label in labels:
        try:
            button = page.get_by_role("button", name=label)
            if button.count() > 0:
                button.first.click(timeout=2500)
                page.wait_for_timeout(1000)
                return
        except Exception:
            continue


def open_search(page, city: str, category: str) -> None:
    query = f"{category} in {city}"
    search_url = f"https://www.google.com/maps/search/{quote_plus(query)}?hl=en"
    page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2500)
    try_accept_consent(page)


def load_results_by_scrolling(page, max_results: int) -> int:
    feed = page.locator("div[role='feed']").first
    card_selector = "a.hfpxzc"

    try:
        feed.wait_for(timeout=15000)
    except PlaywrightTimeoutError:
        logging.warning("Result feed found হয়নি. Selector change হয়ে থাকতে পারে.")
        return 0

    last_count = 0
    stale_round = 0

    for _ in range(150):
        count = page.locator(card_selector).count()
        if count >= max_results:
            return max_results

        if count == last_count:
            stale_round += 1
        else:
            stale_round = 0

        if stale_round >= 6:
            break

        try:
            feed.evaluate("node => node.scrollBy(0, node.scrollHeight)")
        except Exception:
            pass

        page.wait_for_timeout(1200)
        last_count = count

    return min(page.locator(card_selector).count(), max_results)


def collect_result_links(page, total_cards: int) -> list:
    card_selector = "a.hfpxzc"
    links = []
    seen = set()

    for idx in range(total_cards):
        try:
            cards = page.locator(card_selector)
            href = cards.nth(idx).get_attribute("href", timeout=5000)
        except Exception:
            href = ""

        if href and href not in seen:
            seen.add(href)
            links.append(href)

    return links


def scrape_maps(city: str, category: str, max_results: int, output_csv: str, checkpoint_file: str, headless: bool, proxy: str = "") -> None:
    ensure_csv(output_csv)
    seen_urls = load_seen_urls(output_csv)
    start_index = load_checkpoint(checkpoint_file, city, category)

    logging.info("Starting scrape | city=%s | category=%s | resume_index=%s", city, category, start_index)

    with sync_playwright() as playwright:
        launch_kwargs = {"headless": headless}
        if proxy:
            launch_kwargs["proxy"] = {"server": proxy}

        browser = playwright.chromium.launch(**launch_kwargs)
        context = browser.new_context(locale="en-US")
        page = context.new_page()

        open_search(page, city, category)
        total_cards = load_results_by_scrolling(page, max_results)
        logging.info("Detected cards: %s", total_cards)

        if total_cards == 0:
            logging.warning("No cards detected. Exiting.")
            context.close()
            browser.close()
            return

        result_links = collect_result_links(page, total_cards)
        logging.info("Collected stable result links: %s", len(result_links))

        for index in range(start_index, len(result_links)):
            success = False
            for attempt in range(1, 4):
                try:
                    result_url = result_links[index]
                    page.goto(result_url, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(1700)

                    name = safe_inner_text(page.locator("h1.DUwDvf"))
                    address = safe_inner_text(page.locator("button[data-item-id='address'] div.fontBodyMedium"))
                    phone = extract_phone(page)
                    map_url = page.url

                    if not name:
                        raise ValueError("Name পাওয়া যায়নি")

                    row = {
                        "category": category,
                        "city": city,
                        "name": name,
                        "address": address,
                        "phone": phone,
                        "map_url": map_url,
                    }

                    if map_url and map_url not in seen_urls:
                        append_row(output_csv, row)
                        seen_urls.add(map_url)
                        logging.info("Saved: %s", name)
                    else:
                        logging.info("Skipped duplicate: %s", name)

                    save_checkpoint(checkpoint_file, city, category, index + 1)
                    success = True
                    break
                except Exception as exc:
                    sleep_ms = 1000 * (2 ** (attempt - 1))
                    logging.warning("index=%s attempt=%s failed: %s", index, attempt, exc)
                    page.wait_for_timeout(sleep_ms)

            if not success:
                logging.error("index=%s failed after retries", index)
                save_checkpoint(checkpoint_file, city, category, index + 1)

            time.sleep(0.5)

        context.close()
        browser.close()


def build_arg_parser() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Google Maps scraper (name/address/phone -> CSV)")
    parser.add_argument("--city", default="Dhaka", help="City name, e.g., Dhaka")
    parser.add_argument("--category", default="restaurant", help="Category, e.g., dentist")
    parser.add_argument("--max-results", type=int, default=30, help="Max listing count")
    parser.add_argument("--output-csv", default="gmaps_leads.csv", help="Output CSV file path")
    parser.add_argument("--checkpoint", default="gmaps_checkpoint.json", help="Checkpoint file path")
    parser.add_argument("--log-file", default="gmaps_scraper.log", help="Log file path")
    parser.add_argument("--headed", action="store_true", help="Run with visible browser")
    parser.add_argument("--proxy", default="", help="Proxy server URL, e.g. http://user:pass@host:port")
    return parser.parse_args()


def main() -> None:
    args = build_arg_parser()
    setup_logging(args.log_file)

    scrape_maps(
        city=args.city,
        category=args.category,
        max_results=args.max_results,
        output_csv=args.output_csv,
        checkpoint_file=args.checkpoint,
        headless=not args.headed,
        proxy=args.proxy,
    )

    logging.info("Done. Output CSV: %s", args.output_csv)


if __name__ == "__main__":
    main()
