# pipeline_c_playwright.py
# pip install playwright && playwright install
import asyncio, json, re, time
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright

START_URLS = [
    "https://jiopay.com/business/",
    "https://jiopay.com/business/contact",
    "https://jiopay.com/business/privacy-policy",
    "https://jiopay.com/business/terms-conditions",
    "https://www.jiopay.com/business/paymentgateway",
]
ALLOWED_HOSTS = {"jiopay.com","www.jiopay.com"}

def tokenize(s):
    return len(re.findall(r"\w+", s))

async def crawl(max_pages=150, max_depth=2):
    seen, results, queue = set(), [], [(u,0) for u in START_URLS]
    t0 = time.time()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(java_script_enabled=True)
        page = await context.new_page()
        while queue and len(results) < max_pages:
            url, depth = queue.pop(0)
            if url in seen: continue
            seen.add(url)
            host = urlparse(url).netloc.lower()
            if host not in ALLOWED_HOSTS: continue
            try:
                response = await page.goto(url, wait_until="networkidle", timeout=45000)
                status = response.status if response else None
                html = await page.content()
                txt = await page.evaluate("""() => {
                    const kill = s => s && s.remove();
                    document.querySelectorAll('script,style,noscript,svg').forEach(kill);
                    return document.body ? document.body.innerText : '';
                }""")
                tokens = tokenize(txt)
                noise_ratio = (len(html)-len(txt))/max(len(html),1)
                results.append({"url": url, "status": status, "tokens": tokens, "noise_ratio": round(noise_ratio,3)})
                if depth < max_depth:
                    links = await page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
                    for href in links:
                        if not href: continue
                        nxt = urljoin(url, href.split("#")[0])
                        if urlparse(nxt).netloc.lower() in ALLOWED_HOSTS and nxt not in seen:
                            queue.append((nxt, depth+1))
            except Exception as e:
                results.append({"url": url, "status": None, "error": str(e), "tokens": 0, "noise_ratio": None})
        await browser.close()
    elapsed = time.time() - t0
    ok = [r for r in results if r.get("status") and r.get("tokens",0)>0]
    report = {
        "pipeline": "playwright-headless",
        "pages_total": len(results),
        "pages_ok": len(ok),
        "tokens_total": sum(r["tokens"] for r in ok),
        "avg_noise_ratio": round(sum(r["noise_ratio"] for r in ok)/max(len(ok),1),3) if ok else None,
        "throughput_pages_per_sec": round(len(results)/max(elapsed,1e-6),2),
        "failures": [r for r in results if r.get("status") is None or r.get("tokens",0)==0]
    }
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    asyncio.run(crawl())
