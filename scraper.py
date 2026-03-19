"""
Book Scraper - scrapes book listings from books.toscrape.com
Extracts: Title, Price, Rating, Availability
Saves results to books.csv
"""

import requests                          # HTTP library to fetch web pages
from bs4 import BeautifulSoup           # HTML parser to extract data from pages
import csv                               # Built-in module to write CSV files
import time                              # Built-in module to add delays between requests

# ── Constants ────────────────────────────────────────────────────────────────

BASE_URL = "https://books.toscrape.com/catalogue/"   # Base URL for all catalogue pages
START_URL = "https://books.toscrape.com/catalogue/page-1.html"  # First page to start scraping

OUTPUT_FILE = "books.csv"                # Name of the CSV file to save results

# Map word-based ratings to numbers (the site stores rating as a CSS class word)
RATING_MAP = {
    "One":   1,
    "Two":   2,
    "Three": 3,
    "Four":  4,
    "Five":  5,
}

# HTTP headers to mimic a real browser request (avoids being blocked by some sites)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── Helper functions ──────────────────────────────────────────────────────────

def fetch_page(url):
    """
    Fetch the HTML content of a URL.
    Returns a BeautifulSoup object on success, or None on failure.
    """
    try:
        # Send a GET request with a 10-second timeout so we don't hang forever
        response = requests.get(url, headers=HEADERS, timeout=10)

        # Raise an exception for HTTP error codes like 404 or 500
        response.raise_for_status()

        # Parse the HTML response body with BeautifulSoup's built-in HTML parser
        return BeautifulSoup(response.text, "html.parser")

    except requests.exceptions.ConnectionError:
        # Fired when the site is unreachable (no internet, DNS failure, etc.)
        print(f"  [ERROR] Cannot connect to {url}. Check your internet connection.")
        return None

    except requests.exceptions.Timeout:
        # Fired when the server takes too long to respond
        print(f"  [ERROR] Request timed out for {url}.")
        return None

    except requests.exceptions.HTTPError as err:
        # Fired for 4xx / 5xx HTTP status codes
        print(f"  [ERROR] HTTP error for {url}: {err}")
        return None


def parse_books(soup):
    """
    Extract all book data from a single page's BeautifulSoup object.
    Returns a list of dicts, one dict per book.
    """
    books = []   # Accumulator list for book records

    # Find every <article> tag with class "product_pod" — each one is a book card
    articles = soup.find_all("article", class_="product_pod")

    for article in articles:                          # Iterate over each book card
        # ── Title ──────────────────────────────────────────────────────────────
        # The title lives in an <a> tag inside <h3>; full title is in the 'title' attribute
        # because the visible text is often truncated with "..."
        h3 = article.find("h3")                       # Locate the <h3> heading element
        title_tag = h3.find("a") if h3 else None      # Get the <a> link inside <h3>

        # Use the 'title' attribute for the full title; fall back to "N/A" if missing
        title = title_tag["title"] if title_tag and title_tag.get("title") else "N/A"

        # ── Price ──────────────────────────────────────────────────────────────
        # Price is inside <p class="price_color">
        price_tag = article.find("p", class_="price_color")

        # Strip whitespace; default to "N/A" if tag not found
        price = price_tag.text.strip() if price_tag else "N/A"

        # ── Rating ─────────────────────────────────────────────────────────────
        # Rating is encoded as a CSS class on <p class="star-rating One/Two/...">
        rating_tag = article.find("p", class_="star-rating")

        if rating_tag:
            # The second CSS class on the element is the word rating (e.g. "Three")
            # rating_tag["class"] returns a list like ["star-rating", "Three"]
            rating_word = rating_tag["class"][1]

            # Convert the word to a number using our map; default 0 if unexpected word
            rating = RATING_MAP.get(rating_word, 0)
        else:
            rating = "N/A"   # Element not found at all

        # ── Availability ───────────────────────────────────────────────────────
        # Availability text is inside <p class="instock availability">
        availability_tag = article.find("p", class_="instock availability")

        # Strip whitespace (there is often extra indentation in the raw HTML)
        availability = availability_tag.text.strip() if availability_tag else "N/A"
        breadcrumb = soup.find("ul", class_="breadcrumb")
        # Append the collected data as a dictionary to our list
        books.append({
            "Title":        title,
            "Price":        price,
            "Rating":       rating,
            "Availability": availability,
        })

    return books   # Return all books found on this page


def get_next_page_url(soup):
    """
    Find the URL for the 'next' page button.
    Returns the full URL string, or None if we're on the last page.
    """
    # The "next" button is an <li class="next"> containing an <a> tag
    next_li = soup.find("li", class_="next")

    if not next_li:
        return None   # No next button means we've reached the last page

    # Get the href from the <a> tag inside the next <li>
    next_href = next_li.find("a")["href"]

    # Combine the base catalogue URL with the relative href (e.g. "page-2.html")
    return BASE_URL + next_href


def save_to_csv(books, filename):
    """
    Write a list of book dicts to a CSV file.
    """
    # Define column order; must match the keys used in parse_books()
    fieldnames = ["Title", "Price", "Rating", "Availability"]

    # Open file in write mode; newline="" prevents blank rows on Windows
    with open(filename, mode="w", newline="", encoding="utf-8") as csvfile:

        # DictWriter maps dict keys to CSV columns automatically
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()    # Write the header row with column names
        writer.writerows(books) # Write all book rows at once


# ── Main scraping loop ────────────────────────────────────────────────────────

def main():
    all_books  = []          # Master list that will hold every book across all pages
    current_url = START_URL  # Start from page 1
    page_number  = 1         # Counter used only for progress messages

    print("=" * 55)
    print("  📚  books.toscrape.com Scraper")
    print("=" * 55)

    while current_url:   # Loop until there are no more pages (get_next_page_url returns None)

        print(f"\n[Page {page_number}] Fetching: {current_url}")

        soup = fetch_page(current_url)   # Download and parse the page

        if soup is None:
            # fetch_page already printed the error; stop scraping gracefully
            print("  Stopping due to fetch error.")
            break

        # Extract books from the parsed HTML of this page
        page_books = parse_books(soup)
        
        # Report how many books were found on this page
        print(f"  ✔ Found {len(page_books)} books on page {page_number}")

        for book in page_books:
            if book["Rating"] >= 3:
                all_books.append(book)  # Add this page's books to the master list

        # Look for a "next" page link to continue the loop
        current_url = get_next_page_url(soup)

        page_number += 1   # Increment page counter for progress display

        # Be polite: wait 0.5 seconds between requests to avoid hammering the server
        if current_url:
            time.sleep(0.5)

    # ── Save results ──────────────────────────────────────────────────────────

    if all_books:
        save_to_csv(all_books, OUTPUT_FILE)
        print(f"\n{'=' * 55}")
        print(f"  ✅  Done! {len(all_books)} books saved to '{OUTPUT_FILE}'")
        print(f"{'=' * 55}\n")
    else:
        # Nothing was scraped — could be a connection problem on the very first page
        print("\n  ⚠  No books were scraped. Check the error messages above.")


# Run main() only when this script is executed directly (not when imported)
if __name__ == "__main__":
    main()
