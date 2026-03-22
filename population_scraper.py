import requests  # ওয়েব পেজ থেকে ডাটা আনার জন্য requests ইমপোর্ট করা হচ্ছে।
from bs4 import BeautifulSoup  # HTML পার্স করে টেবিল বের করার জন্য BeautifulSoup ইমপোর্ট করা হচ্ছে।
import pandas as pd  # ডাটা ক্লিনিং এবং CSV সেভ করার জন্য pandas ইমপোর্ট করা হচ্ছে।

URL = "https://www.worldometers.info/world-population/population-by-country/"  # যে পেজটি স্ক্র্যাপ করা হবে সেই URL সেট করা হচ্ছে।
HEADERS = {"User-Agent": "Mozilla/5.0"}  # অনুরোধটি ব্রাউজার থেকে এসেছে বোঝাতে সাধারণ User-Agent সেট করা হচ্ছে।
RAW_FILE = "raw_population.csv"  # কাঁচা ডাটা সংরক্ষণের ফাইলের নাম নির্ধারণ করা হচ্ছে।
CLEAN_FILE = "clean_population.csv"  # পরিষ্কার ডাটা সংরক্ষণের ফাইলের নাম নির্ধারণ করা হচ্ছে।

response = requests.get(URL, headers=HEADERS, timeout=30)  # নির্দিষ্ট URL-এ HTTP GET রিকোয়েস্ট পাঠানো হচ্ছে।
response.raise_for_status()  # রিকোয়েস্ট ব্যর্থ হলে সাথে সাথে ত্রুটি দেখানোর জন্য চেক করা হচ্ছে।
soup = BeautifulSoup(response.text, "html.parser")  # প্রাপ্ত HTML টেক্সটকে BeautifulSoup দিয়ে পার্স করা হচ্ছে।

table = soup.find("table", attrs={"id": "example2"})  # দেশভিত্তিক জনসংখ্যার টেবিলটি id দিয়ে খোঁজা হচ্ছে।
if table is None:  # যদি id দিয়ে টেবিল না পাওয়া যায় তাহলে বিকল্প পদ্ধতি ব্যবহার করা হবে।
    table = soup.find("table")  # পেজের প্রথম টেবিলটিকে fallback হিসেবে নেওয়া হচ্ছে।
if table is None:  # fallback দিয়েও টেবিল না পেলে স্ক্রিপ্ট থামিয়ে ত্রুটি তোলা হবে।
    raise ValueError("Population table not found on the page.")  # টেবিল না পাওয়ার স্পষ্ট বার্তা সহ exception তোলা হচ্ছে।

rows_data = []  # প্রতিটি দেশের কাঁচা সারি এখানে জমা রাখার জন্য ফাঁকা লিস্ট নেওয়া হচ্ছে।
body_rows = table.select("tbody tr")  # টেবিলের body অংশ থেকে সব data row নির্বাচন করা হচ্ছে।

for tr in body_rows:  # প্রতিটি সারির ভেতর থেকে প্রয়োজনীয় কলাম পড়ার জন্য লুপ চালানো হচ্ছে।
    tds = tr.find_all("td")  # বর্তমান সারির সব td সেল একসাথে নেওয়া হচ্ছে।
    if len(tds) < 11:  # প্রত্যাশিত কলাম কম থাকলে সেই সারিটি বাদ দেওয়া হচ্ছে।
        continue  # অসম্পূর্ণ সারি স্কিপ করে পরের সারিতে যাওয়া হচ্ছে।

    country = tds[1].get_text(strip=True)  # দেশের নাম সাধারণত দ্বিতীয় td থেকে নেওয়া হচ্ছে।
    population_2024 = tds[2].get_text(strip=True)  # Population (2024) মান তৃতীয় td থেকে নেওয়া হচ্ছে।
    yearly_change = tds[3].get_text(strip=True)  # Yearly Change মান চতুর্থ td থেকে নেওয়া হচ্ছে।
    world_share = tds[-1].get_text(strip=True)  # World Share (%) মান শেষ td থেকে নেওয়া হচ্ছে।

    rows_data.append(  # সংগ্রহ করা ফিল্ডগুলোকে একটি ডিকশনারি আকারে লিস্টে যোগ করা হচ্ছে।
        {
            "Country": country,
            "Population (2024)": population_2024,
            "Yearly change": yearly_change,
            "World share": world_share,
        }
    )

raw_df = pd.DataFrame(rows_data)  # কাঁচা তালিকাকে pandas DataFrame-এ রূপান্তর করা হচ্ছে।
raw_df.to_csv(RAW_FILE, index=False, encoding="utf-8-sig")  # কাঁচা ডাটাকে raw_population.csv নামে সংরক্ষণ করা হচ্ছে।

clean_df = raw_df.copy()  # কাঁচা ডাটা অক্ষত রাখতে একটি কপি DataFrame তৈরি করা হচ্ছে।
clean_df["World share"] = clean_df["World share"].str.replace("%", "", regex=False)  # World share কলাম থেকে % চিহ্ন সরানো হচ্ছে।
clean_df["Yearly change"] = clean_df["Yearly change"].str.replace("+", "", regex=False)  # Yearly change কলাম থেকে + চিহ্ন সরানো হচ্ছে।
clean_df["Population (2024)"] = clean_df["Population (2024)"].str.replace(",", "", regex=False)  # Population (2024) কলাম থেকে কমা সরানো হচ্ছে।

clean_df.to_csv(CLEAN_FILE, index=False, encoding="utf-8-sig")  # পরিষ্কার ডাটাকে clean_population.csv নামে সংরক্ষণ করা হচ্ছে।
print(f"Done. Raw data saved to {RAW_FILE} and cleaned data saved to {CLEAN_FILE}.")  # কাজ শেষের অবস্থা ও ফাইলের নাম দেখানো হচ্ছে।
import csv

with open("clean_population.csv", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

max_row = max(rows, key=lambda x: int(x["Population (2024)"].replace(",", "")))
print(max_row["Country"])