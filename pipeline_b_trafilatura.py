# pipeline_b_trafilatura.py
import time, json, re
import trafilatura
from trafilatura.sitemaps import sitemap_search

SEEDS = ["https://www.jio.com/business/"]

def tokenize(s):
    return len(re.findall(r"\w+", s))

def crawl(urls, max_pages=200):
    seen, results = set(), []
    t0 = time.time()
    for url in urls:
        # discover from sitemap if available
        for sm_url in sitemap_search(url):
            sm_urls = trafilatura.sitemaps.sitemap_urls_from_robots(sm_url) or []
            for u in sm_urls:
                if len(results) >= max_pages: break
                if u in seen: continue
                seen.add(u)
                downloaded = trafilatura.fetch_url(u)
                if not downloaded:
                    results.append({"url": u, "status": None, "error": "fetch_failed", "tokens": 0, "noise_ratio": None})
                    continue
                extracted = trafilatura.extract(downloaded, include_tables=False, include_links=False)
                if not extracted:
                    results.append({"url": u, "status": 200, "error": "no_main_content", "tokens": 0, "noise_ratio": None})
                    continue
                tokens = tokenize(extracted)
                # Fake a noise metric: 1 - (extracted/raw) length ratio
                noise_ratio = 1 - (len(extracted)/len(downloaded))
                results.append({"url": u, "status": 200, "tokens": tokens, "noise_ratio": round(noise_ratio,3)})
    elapsed = time.time() - t0
    return results, elapsed

if __name__ == "__main__":
    results, elapsed = crawl(SEEDS)
    ok = [r for r in results if r.get("status")==200 and r.get("tokens",0)>0]
    report = {
        "pipeline": "trafilatura",
        "pages_total": len(results),
        "pages_ok": len(ok),
        "tokens_total": sum(r["tokens"] for r in ok),
        "avg_noise_ratio": round(sum(r["noise_ratio"] for r in ok)/max(len(ok),1),3),
        "throughput_pages_per_sec": round(len(results)/max(elapsed,1e-6),2),
        "failures": [r for r in results if r.get("status")!=200 or r.get("tokens",0)==0]
    }
    print(json.dumps(report, indent=2))
