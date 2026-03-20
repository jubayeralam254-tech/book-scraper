import csv  # CSV ফাইলে ডাটা লেখার জন্য csv মডিউল ইমপোর্ট করা হচ্ছে।
import requests  # ওয়েবসাইটে HTTP রিকোয়েস্ট পাঠানোর জন্য requests ইমপোর্ট করা হচ্ছে।
from bs4 import BeautifulSoup  # HTML পার্স করার জন্য BeautifulSoup ইমপোর্ট করা হচ্ছে।
from urllib.parse import urljoin  # relative URL থেকে next page এর full URL বানাতে urljoin ইমপোর্ট করা হচ্ছে।

BASE_URL = "https://quotes.toscrape.com/"  # স্ক্র্যাপিং শুরুর জন্য মূল URL সেট করা হচ্ছে।
OUTPUT_FILE = "quotes.csv"  # আউটপুট CSV ফাইলের নাম quotes.csv রাখা হচ্ছে।
HEADERS = {"User-Agent": "Mozilla/5.0"}  # সাধারণ browser user-agent দিয়ে request header সেট করা হচ্ছে।

def fetch_page(url):  # নির্দিষ্ট URL থেকে পেইজ নিয়ে BeautifulSoup অবজেক্ট রিটার্ন করার ফাংশন।
    response = requests.get(url, headers=HEADERS, timeout=10)  # timeout সহ GET request পাঠানো হচ্ছে।
    response.raise_for_status()  # HTTP error (যেমন 404/500) থাকলে exception উঠানো হচ্ছে।
    return BeautifulSoup(response.text, "html.parser")  # HTML টেক্সট পার্স করে soup রিটার্ন করা হচ্ছে।

def parse_quotes(soup):  # একটি পেইজ থেকে quote, author, tags বের করার ফাংশন।
    quotes_data = []  # এই লিস্টে প্রতিটি quote এর ডিকশনারি জমা হবে।
    quote_blocks = soup.find_all("div", class_="quote")  # সব quote card/div একসাথে খোঁজা হচ্ছে।
    for block in quote_blocks:  # প্রতিটি quote block নিয়ে লুপ চালানো হচ্ছে।
        text = block.find("span", class_="text").get_text(strip=True)  # quote text পরিষ্কারভাবে নেওয়া হচ্ছে।
        author = block.find("small", class_="author").get_text(strip=True)  # author নাম নেওয়া হচ্ছে।
        tag_elements = block.find_all("a", class_="tag")  # quote এর সাথে থাকা সব tag element নেওয়া হচ্ছে।
        tags = ", ".join(tag.get_text(strip=True) for tag in tag_elements)  # tags গুলো comma separated string বানানো হচ্ছে।
        quotes_data.append({"Quote text": text, "Author": author, "Tags": tags})  # current quote ডাটা লিস্টে যোগ করা হচ্ছে।
    return quotes_data  # এই পেইজের সব quote ডাটা রিটার্ন করা হচ্ছে।

def find_next_page(soup, current_url):  # pagination এর next page URL বের করার ফাংশন।
    next_li = soup.find("li", class_="next")  # next বাটনের list item খোঁজা হচ্ছে।
    if not next_li:  # যদি next button না পাওয়া যায়, তাহলে আর পেইজ নেই।
        return None  # pagination শেষ, তাই None রিটার্ন করা হচ্ছে।
    next_href = next_li.find("a").get("href")  # next link এর href নেওয়া হচ্ছে।
    return urljoin(current_url, next_href)  # current URL এর সাথে join করে full next URL রিটার্ন করা হচ্ছে।

def save_to_csv(rows, filename):  # সংগ্রহ করা quote ডাটা CSV তে সেভ করার ফাংশন।
    fieldnames = ["Quote text", "Author", "Tags"]  # CSV কলামের সঠিক order সেট করা হচ্ছে।
    with open(filename, "w", newline="", encoding="utf-8") as file:  # UTF-8 এবং newline ঠিক রেখে ফাইল খোলা হচ্ছে।
        writer = csv.DictWriter(file, fieldnames=fieldnames)  # dict ভিত্তিক CSV writer তৈরি করা হচ্ছে।
        writer.writeheader()  # প্রথমে header row লেখা হচ্ছে।
        writer.writerows(rows)  # তারপর সব quote row একসাথে লেখা হচ্ছে।

def main():  # পুরো scraping workflow চালানোর main ফাংশন।
    all_quotes = []  # সব পেইজের quote এক জায়গায় জমা করার জন্য master list।
    current_url = BASE_URL  # scraping শুরু হচ্ছে প্রথম পেইজ থেকে।
    page_number = 1  # progress দেখানোর জন্য page counter রাখা হচ্ছে।
    while current_url:  # যতক্ষণ next page আছে ততক্ষণ লুপ চলবে।
        print(f"Scraping page {page_number}: {current_url}")  # কোন পেইজ scrape হচ্ছে তা console এ দেখানো হচ্ছে।
        soup = fetch_page(current_url)  # current page fetch ও parse করা হচ্ছে।
        page_quotes = parse_quotes(soup)  # current page থেকে quotes extract করা হচ্ছে।
        all_quotes.extend(page_quotes)  # current page এর quotes master list এ যোগ করা হচ্ছে।
        current_url = find_next_page(soup, current_url)  # next page থাকলে তার URL সেট করা হচ্ছে।
        page_number += 1  # পরের iteration এর জন্য page counter বাড়ানো হচ্ছে।
    save_to_csv(all_quotes, OUTPUT_FILE)  # সব quote শেষ হলে CSV ফাইলে সেভ করা হচ্ছে।
    print(f"Done. {len(all_quotes)} quotes saved to {OUTPUT_FILE}")  # মোট কয়টা quote সেভ হলো তা দেখানো হচ্ছে।

if __name__ == "__main__":  # স্ক্রিপ্ট সরাসরি রান হলে main ফাংশন কল করার condition।
    main()  # main ফাংশন চালানো হচ্ছে।
