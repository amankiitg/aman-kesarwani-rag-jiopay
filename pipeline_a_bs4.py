# pipeline_a_bs4.py
import time, json, re, math
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

START_URLS = [
    "https://www.jio.com/business/",            # FAQs live here (server-rendered)
    # Add any deep links found under jio.com/business
]
ALLOWED_HOSTS = {"www.jio.com", "jio.com"}

HEADERS = {"User-Agent": "research-bot/1.0 (+contact: you@example.com)"}
TIMEOUT = 20

def is_allowed(url):
    host = urlparse(url).netloc.lower()
    return host in ALLOWED_HOSTS

def extract_main_text(html):
    soup = BeautifulSoup(html, "html.parser")
    # remove script/style/nav/footer
    for tag in soup(["script","style","noscript","svg"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    return text

def tokenize(s):  # simple token approximation (~word count)
    return len(re.findall(r"\w+", s))

def crawl(urls, max_pages=200):
    seen, results = set(), []
    q = list(urls)
    t0 = time.time()
    while q and len(results) < max_pages:
        url = q.pop(0)
        if url in seen or not is_allowed(url): continue
        seen.add(url)
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            ok = (r.status_code == 200 and "text/html" in r.headers.get("Content-Type",""))
            if not ok:
                results.append({"url": url, "status": r.status_code, "error": "non-html", "tokens": 0, "noise_ratio": None})
                continue
            raw = r.text
            clean = extract_main_text(raw)
            tokens = tokenize(clean)
            noise_ratio = (len(raw) - len(clean)) / max(len(raw),1)
            results.append({"url": url, "status": 200, "tokens": tokens, "noise_ratio": round(noise_ratio,3)})

            # enqueue links
            soup = BeautifulSoup(raw, "html.parser")
            for a in soup.find_all("a", href=True):
                nxt = urljoin(url, a["href"])
                if is_allowed(nxt):
                    q.append(nxt.split("#")[0])
        except Exception as e:
            results.append({"url": url, "status": None, "error": str(e), "tokens": 0, "noise_ratio": None})
    t1 = time.time()
    return results, (t1 - t0)

if __name__ == "__main__":
    results, elapsed = crawl(START_URLS)
    pages_ok = [r for r in results if r.get("status")==200 and r.get("tokens",0)>0]
    throughput = len(results) / max(elapsed,1e-6)
    report = {
        "pipeline": "requests+bs4",
        "pages_total": len(results),
        "pages_ok": len(pages_ok),
        "tokens_total": sum(r["tokens"] for r in pages_ok),
        "avg_noise_ratio": round(sum(r["noise_ratio"] for r in pages_ok)/max(len(pages_ok),1),3),
        "throughput_pages_per_sec": round(throughput,2),
        "failures": [r for r in results if r.get("status")!=200 or r.get("tokens",0)==0]
    }
    print(json.dumps(report, indent=2))
