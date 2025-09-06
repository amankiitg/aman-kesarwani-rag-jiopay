import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import time
from playwright.sync_api import sync_playwright

# Seed URLs
seed_urls = [
    {"url": "https://jiopay.com/business", "source": "JioPay Business Website"},
    {"url": "https://jiopay.com/business/help-center", "source": "JioPay Help Center"}
]

# External references
external_pages = [
    {"url": "https://www.jiomoney.com/API-Doc/JM-API-Doc.html", "source": "JioMoney API Documentation"},
    {"url": "https://testpg.rpay.co.in/reliance-webpay/v1.0/", "source": "JioMoney API Documentation"},
    {"url": "https://pp2pay.jiomoney.com/reliance-webpay/v1.0/", "source": "JioMoney API Documentation"},
    {"url": "https://www.npci.org.in/what-we-do/upi-123pay/product-overview",
     "source": "Regulatory and Compliance References"},
    {"url": "https://www.npci.org.in/what-we-do/autopay/list-of-banks-and-apps-live-on-autopay",
     "source": "Regulatory and Compliance References"},
    {"url": "https://www.scribd.com/document/752142998/JioPay-Non-PCI-DSS-Integration-Handbook-v1-4-3-3-1-1",
     "source": "Technical Documentation"},
    {"url": "https://apps.apple.com/in/app/myjio-for-everything-jio/id1074964262", "source": "Related Jio Services"},
    {"url": "https://play.google.com/store/apps/details?id=com.jiopay.business&hl=en_US",
     "source": "Related Jio Services"},
    {"url": "https://pp2pay.jiomoney.com/reliance-webpay/v1.0/termsandconditions",
     "source": "Regulatory and Compliance References"},
]

visited = set()
knowledge_base = []


# Categorize pages
def categorize(url, source):
    if "help-center" in url or "support" in url:
        return "Help Center"
    elif "terms" in url or "privacy" in url or "kyc" in url:
        return "Legal/Policy"
    elif "api" in url or "reliance-webpay" in url:
        return "API/Technical"
    elif "scribd" in url:
        return "Technical Documentation"
    elif "apps.apple" in url or "play.google" in url:
        return "App"
    elif "npci" in url:
        return "Regulatory/Compliance"
    elif "business" in url:
        return "Business"
    else:
        return source


# Extract text and title from HTML
def extract_text_and_title(html, url):
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url
    for script in soup(["script", "style"]):
        script.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = ' '.join(text.split())
    return text, title


# Extract FAQs if present
def extract_faqs(soup):
    faqs = []
    # Adjust selectors based on actual FAQ HTML structure
    for item in soup.select("div.faq-item, div[data-faq]"):
        question = item.select_one("h3, .faq-question")
        answer = item.select_one("p, .faq-answer")
        if question and answer:
            faqs.append({
                "question": question.get_text(strip=True),
                "answer": answer.get_text(strip=True)
            })
    return faqs if faqs else None


# Scrape page with Playwright fallback
def scrape_page(url):
    if url.startswith("mailto:") or url.endswith((".pdf", ".apk", ".doc",
                                                  ".docx")) or "scribd.com" in url or "play.google.com" in url or "apps.apple.com" in url:
        return f"Reference link: {url}", url, None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_load_state("networkidle")
            html = page.content()
            browser.close()
            soup = BeautifulSoup(html, "html.parser")
            text, title = extract_text_and_title(html, url)
            faqs = extract_faqs(soup)
            return text, title, faqs
    except Exception as e:
        print(f"Playwright failed for {url}, falling back to Requests+BeautifulSoup: {e}")
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            text, title = extract_text_and_title(response.text, url)
            soup = BeautifulSoup(response.text, "html.parser")
            faqs = extract_faqs(soup)
            return text, title, faqs
        except Exception as e2:
            print(f"Requests failed for {url}: {e2}")
            return f"Reference link: {url}", url, None


# Extract internal links
def extract_internal_links(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a['href']
        full_url = urljoin(base_url, href).split('#')[0]
        if urlparse(full_url).netloc.endswith("jiopay.com"):
            links.add(full_url)
    return links


# Crawl internal pages
queue = seed_urls.copy()
while queue:
    page_info = queue.pop(0)
    url = page_info['url']
    source = page_info['source']
    if url in visited:
        continue
    visited.add(url)

    print(f"Scraping internal: {url}")
    content, title, faqs = scrape_page(url)
    category = categorize(url, source)

    knowledge_base.append({
        "source": source,
        "category": category,
        "title": title,
        "url": url,
        "content": content,
        "faqs": faqs
    })

    # Extract internal links
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        links = extract_internal_links(response.text, url)
        for link in links:
            if link not in visited:
                queue.append({"url": link, "source": source})
    except Exception as e:
        print(f"Failed to extract links from {url}: {e}")

    time.sleep(1)

# Crawl external pages
for page in external_pages:
    url = page['url']
    source = page['source']
    if url in visited:
        continue
    visited.add(url)

    print(f"Scraping external: {url}")
    content, title, faqs = scrape_page(url)
    category = categorize(url, source)

    knowledge_base.append({
        "source": source,
        "category": category,
        "title": title,
        "url": url,
        "content": content,
        "faqs": faqs
    })

    time.sleep(1)

# Save JSON
with open("jiopay_rag_knowledge_base_faq.json", "w", encoding="utf-8") as f:
    json.dump(knowledge_base, f, ensure_ascii=False, indent=2)

print(f"Scraping completed. Total pages collected: {len(knowledge_base)}")
