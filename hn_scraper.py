"""Hacker News ফ্রন্ট পেজ থেকে স্টোরি স্ক্র্যাপ করে CSV তে সেভ করার স্ক্রিপ্ট।"""

# HTTP রিকোয়েস্ট পাঠানোর জন্য requests লাইব্রেরি ইমপোর্ট করা হচ্ছে।
import requests
# requests এর retry adapter ব্যবহারের জন্য HTTPAdapter ইমপোর্ট করা হচ্ছে।
from requests.adapters import HTTPAdapter
# network exception গুলো আলাদা করে ধরার জন্য প্রয়োজনীয় exception ইমপোর্ট করা হচ্ছে।
from requests.exceptions import RequestException, SSLError, Timeout
# HTML পার্স করার জন্য BeautifulSoup ইমপোর্ট করা হচ্ছে।
from bs4 import BeautifulSoup
# CSV ফাইলে ডেটা লেখার জন্য csv মডিউল ইমপোর্ট করা হচ্ছে।
import csv
# পেজ রিকোয়েস্টের মাঝে বিরতি দেওয়ার জন্য time মডিউল ইমপোর্ট করা হচ্ছে।
import time
# urllib3 Retry দিয়ে transient error এ auto-retry করার সুবিধা নেওয়া হচ্ছে।
from urllib3.util.retry import Retry
# টাইপ হিন্টের জন্য Optional এবং Dict ব্যবহার করা হচ্ছে।
from typing import Optional, Dict

# Hacker News এর বেস URL একটি কনস্ট্যান্টে রাখা হচ্ছে।
BASE_URL = "https://news.ycombinator.com/news"
# SSL সমস্যা হলে fallback হিসেবে http URL রাখা হচ্ছে।
FALLBACK_URL = "http://news.ycombinator.com/news"
# ব্লক এড়াতে ব্রাউজার-স্টাইল User-Agent হেডার সেট করা হচ্ছে।
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# retry সহ একটি session বানানোর জন্য হেল্পার ফাংশন।
def build_session() -> requests.Session:
    # নতুন requests Session অবজেক্ট তৈরি করা হচ্ছে।
    session = requests.Session()
    # এই session এর সব রিকোয়েস্টে User-Agent হেডার যোগ করা হচ্ছে।
    session.headers.update(HEADERS)
    # সাময়িক network/server error এ retry policy কনফিগার করা হচ্ছে।
    retry_policy = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    # retry policy সহ adapter তৈরি করা হচ্ছে।
    adapter = HTTPAdapter(max_retries=retry_policy)
    # HTTPS রিকোয়েস্টের জন্য adapter attach করা হচ্ছে।
    session.mount("https://", adapter)
    # HTTP রিকোয়েস্টের জন্যও adapter attach করা হচ্ছে।
    session.mount("http://", adapter)
    # কনফিগার করা session রিটার্ন করা হচ্ছে।
    return session


# পুরো স্ক্রিপ্টে reuse করার জন্য একটি shared session তৈরি করা হচ্ছে।
SESSION = build_session()


# টেক্সট থেকে প্রথম সংখ্যাটি int হিসেবে বের করার ছোট হেল্পার ফাংশন।
def extract_number(text: Optional[str]) -> Optional[int]:
    # যদি টেক্সট না থাকে তাহলে None রিটার্ন করা হবে।
    if not text:
        return None
    # কেবল ডিজিট ক্যারেক্টারগুলো নিয়ে একসাথে করা হচ্ছে।
    digits = "".join(ch for ch in text if ch.isdigit())
    # যদি ডিজিট পাওয়া যায় তাহলে int রিটার্ন, না হলে None রিটার্ন করা হচ্ছে।
    return int(digits) if digits else None


# নির্দিষ্ট পেজ নম্বরের Hacker News পেজ থেকে স্টোরি লিস্ট স্ক্র্যাপ করার ফাংশন।
def scrape_page(page_number: int) -> list[Dict[str, Optional[object]]]:
    # প্রথম পেজে খালি suffix, অন্য পেজে pagination suffix সেট করা হচ্ছে।
    page_suffix = "" if page_number == 1 else f"?p={page_number}"
    # প্রথমে HTTPS এবং প্রয়োজনে HTTP fallback দিয়ে URL তালিকা বানানো হচ্ছে।
    candidate_urls = [f"{BASE_URL}{page_suffix}", f"{FALLBACK_URL}{page_suffix}"]

    # response ভ্যারিয়েবল আগে থেকে None রাখা হচ্ছে, পরে সফল রেসপন্স এতে রাখা হবে।
    response = None
    # candidate URL গুলো একে একে চেষ্টা করা হচ্ছে।
    for page_url in candidate_urls:
        try:
            # connect/read আলাদা timeout দিয়ে GET রিকোয়েস্ট পাঠানো হচ্ছে।
            response = SESSION.get(page_url, timeout=(10, 30))
            # HTTP এর যেকোনো এরর থাকলে exception তোলা হবে।
            response.raise_for_status()
            # সফল হলে loop থেকে বের হয়ে যাওয়া হচ্ছে।
            break
        except SSLError:
            # SSL সমস্যা হলে পরের URL (fallback) চেষ্টা করার বার্তা দেখানো হচ্ছে।
            print(f"SSL সমস্যা হয়েছে, fallback চেষ্টা করা হচ্ছে: {page_url}")
        except Timeout:
            # timeout হলে পরের URL চেষ্টা করার বার্তা দেখানো হচ্ছে।
            print(f"রিকোয়েস্ট timeout হয়েছে, আবার চেষ্টা করা হচ্ছে: {page_url}")
        except RequestException as exc:
            # অন্য requests error হলে সেটিও দেখিয়ে পরের URL চেষ্টা করা হচ্ছে।
            print(f"রিকোয়েস্ট ব্যর্থ হয়েছে ({page_url}): {exc}")

    # সব URL চেষ্টা করেও response না পেলে পরিষ্কার error তোলা হচ্ছে।
    if response is None:
        raise RuntimeError(f"Page {page_number} fetch করা যায়নি।")

    # HTML কনটেন্ট BeautifulSoup দিয়ে পার্স করা হচ্ছে।
    soup = BeautifulSoup(response.text, "html.parser")
    # প্রতিটি স্টোরি row (athing) সিলেক্ট করা হচ্ছে।
    story_rows = soup.select("tr.athing")
    # এই পেজের সব স্টোরির ডেটা রাখার জন্য খালি লিস্ট নেওয়া হচ্ছে।
    page_stories = []

    # প্রতিটি স্টোরি row নিয়ে লুপ চালানো হচ্ছে।
    for row in story_rows:
        # র‍্যাঙ্ক এলিমেন্ট খোঁজা হচ্ছে।
        rank_el = row.select_one("span.rank")
        # টাইটেল লিংক এলিমেন্ট খোঁজা হচ্ছে (নতুন HN মার্কআপ অনুযায়ী)।
        title_link = row.select_one("span.titleline a")

        # পরের sibling row সাধারণত subtext row হয়, সেটি নেওয়া হচ্ছে।
        subtext_row = row.find_next_sibling("tr")
        # subtext এর span.subline পাওয়া গেলে রাখা হচ্ছে, নাহলে None রাখা হচ্ছে।
        subline = subtext_row.select_one("span.subline") if subtext_row else None

        # স্কোর এলিমেন্ট (যেমন: 120 points) নেওয়া হচ্ছে, না থাকলে None।
        score_el = subline.select_one("span.score") if subline else None
        # অথর এলিমেন্ট (hnuser) নেওয়া হচ্ছে, না থাকলে None।
        author_el = subline.select_one("a.hnuser") if subline else None
        # টাইম/এজ এলিমেন্ট নেওয়া হচ্ছে, না থাকলে None।
        age_el = subline.select_one("span.age") if subline else None

        # কমেন্ট লিংক বের করতে subline এর সব লিংক নেওয়া হচ্ছে।
        comment_links = subline.select("a") if subline else []
        # সাধারণত শেষ লিংকটিই comment/discuss লিংক, সেটি টেক্সটসহ নেওয়া হচ্ছে।
        comment_text = comment_links[-1].get_text(strip=True) if comment_links else None

        # র‍্যাঙ্ক থেকে সংখ্যা বের করা হচ্ছে (যেমন: "1." -> 1)।
        rank = extract_number(rank_el.get_text(strip=True) if rank_el else None)
        # স্কোর থেকে points সংখ্যা বের করা হচ্ছে।
        points = extract_number(score_el.get_text(strip=True) if score_el else None)
        # comment টেক্সট থেকে কমেন্ট সংখ্যা বের করা হচ্ছে (discuss হলে None হবে)।
        comment_count = extract_number(comment_text)

        # একটি ডিকশনারিতে স্টোরির প্রয়োজনীয় সব ফিল্ড সাজিয়ে রাখা হচ্ছে।
        story_data = {
            "Rank": rank,
            "Title": title_link.get_text(strip=True) if title_link else None,
            "URL": title_link.get("href") if title_link else None,
            "Points": points,
            "Author": author_el.get_text(strip=True) if author_el else None,
            "Comment Count": comment_count,
            "Time Posted": age_el.get_text(strip=True) if age_el else None,
        }
        # প্রস্তুত করা ডেটা লিস্টে যোগ করা হচ্ছে।
        page_stories.append(story_data)

    # এই পেজ থেকে সংগ্রহ করা সব স্টোরি রিটার্ন করা হচ্ছে।
    return page_stories


# সব পেজ স্ক্র্যাপ করে CSV তে সেভ করার মেইন ফাংশন।
def main() -> None:
    # সব পেজের সম্মিলিত ডেটা রাখার জন্য খালি লিস্ট নেওয়া হচ্ছে।
    all_stories = []
    # মোট কত পেজ স্ক্র্যাপ করা হবে তা নির্ধারণ করা হচ্ছে (কমপক্ষে ৩)।
    total_pages = 3

    # ১ থেকে total_pages পর্যন্ত প্রতিটি পেজ নম্বরে লুপ চালানো হচ্ছে।
    for page_number in range(1, total_pages + 1):
        # কোন পেজ স্ক্র্যাপ হচ্ছে তা দেখানোর জন্য কনসোলে বার্তা প্রিন্ট করা হচ্ছে।
        print(f"Scraping page {page_number}...")
        try:
            # নির্দিষ্ট পেজ স্ক্র্যাপ করে পাওয়া স্টোরিগুলো নেওয়া হচ্ছে।
            stories = scrape_page(page_number)
        except Exception as exc:
            # কোনো পেজে সমস্যা হলে সেটি দেখিয়ে পরের পেজে যাওয়া হচ্ছে।
            print(f"Page {page_number} স্ক্র্যাপ করা যায়নি: {exc}")
            # সমস্যা হলেও flow চালু রাখতে খালি লিস্ট নেওয়া হচ্ছে।
            stories = []
        # বর্তমান পেজের স্টোরিগুলো মূল লিস্টে যোগ করা হচ্ছে।
        all_stories.extend(stories)

        # শেষ পেজ না হলে পরের রিকোয়েস্টের আগে ২ সেকেন্ড বিরতি দেওয়া হচ্ছে।
        if page_number < total_pages:
            time.sleep(2)

    # CSV ফাইলের নাম কনস্ট্যান্ট স্ট্রিং হিসেবে সেট করা হচ্ছে।
    output_file = "hn_stories.csv"
    # CSV কলাম হেডারগুলোর ক্রম নির্ধারণ করা হচ্ছে।
    fieldnames = ["Rank", "Title", "URL", "Points", "Author", "Comment Count", "Time Posted"]

    # UTF-8 এনকোডিং সহ CSV ফাইল রাইট মোডে খোলা হচ্ছে।
    with open(output_file, "w", newline="", encoding="utf-8") as csv_file:
        # DictWriter অবজেক্ট তৈরি করা হচ্ছে যাতে ডিকশনারি সরাসরি লেখা যায়।
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        # প্রথম লাইনে হেডার লেখা হচ্ছে।
        writer.writeheader()
        # সব স্টোরি একসাথে CSV তে লেখা হচ্ছে।
        writer.writerows(all_stories)

    # শেষ হলে মোট স্টোরি সংখ্যা ও ফাইল নামসহ সফলতার বার্তা প্রিন্ট করা হচ্ছে।
    print(f"Saved {len(all_stories)} stories to {output_file}")


# স্ক্রিপ্ট সরাসরি রান হলে মেইন ফাংশন কল করা হচ্ছে।
if __name__ == "__main__":
    try:
        # প্রোগ্রামের এন্ট্রি পয়েন্ট থেকে main() চালানো হচ্ছে।
        main()
    except KeyboardInterrupt:
        # ইউজার Ctrl+C দিলে বড় traceback না দেখিয়ে ছোট বার্তা দেওয়া হচ্ছে।
        print("প্রোগ্রাম ইউজার দ্বারা বন্ধ করা হয়েছে।")