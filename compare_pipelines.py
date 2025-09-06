# compare_pipelines.py
import json, subprocess, shutil, csv, os
from collections import Counter

PIPELINES = [
    ("requests+bs4", ["python", "pipeline_a_bs4.py"]),
    ("trafilatura",  ["python", "pipeline_b_trafilatura.py"]),
    ("playwright",   ["python", "pipeline_c_playwright.py"]),
]

def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode!=0:
        return {"pipeline": cmd[-1], "error": p.stderr.strip()}
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"pipeline": cmd[-1], "error": "invalid_json"}

def summarize_failures(failures):
    kinds = []
    for f in failures:
        if f.get("error"):
            kinds.append(f["error"])
        elif f.get("status") and f.get("tokens",0)==0:
            kinds.append(f"no_text_status_{f['status']}")
        else:
            kinds.append("unknown")
    return dict(Counter(kinds).most_common(6))

def write_csv(rows, filename="comparison_report.csv"):
    keys = ["pipeline","pages_total","pages_ok","tokens_total",
            "avg_noise_ratio","throughput_pages_per_sec","top_failures"]
    with open(filename,"w",newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k) for k in keys})

def write_html(rows, filename="comparison_report.html"):
    html = """
    <html><head>
    <title>Pipeline Comparison Report</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 2em; }
      table { border-collapse: collapse; width: 100%; }
      th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
      th { background: #f5f5f5; }
      .err { color: red; font-weight: bold; }
    </style>
    </head><body>
    <h2>Pipeline Comparison Report</h2>
    <table>
      <tr>
        <th>Pipeline</th>
        <th>Pages Total</th>
        <th>Pages OK</th>
        <th>Tokens Total</th>
        <th>Avg Noise Ratio</th>
        <th>Throughput (pages/sec)</th>
        <th>Top Failures</th>
      </tr>
    """
    for row in rows:
        if "error" in row:
            html += f"<tr><td>{row['pipeline']}</td><td colspan=6 class='err'>{row['error']}</td></tr>"
            continue
        html += f"""
        <tr>
          <td>{row['pipeline']}</td>
          <td>{row['pages_total']}</td>
          <td>{row['pages_ok']}</td>
          <td>{row['tokens_total']}</td>
          <td>{row['avg_noise_ratio']}</td>
          <td>{row['throughput_pages_per_sec']}</td>
          <td>{json.dumps(row['top_failures'])}</td>
        </tr>
        """
    html += "</table></body></html>"
    with open(filename,"w") as f:
        f.write(html)

if __name__ == "__main__":
    rows = []
    for name, cmd in PIPELINES:
        if shutil.which(cmd[0]) is None:
            rows.append({"pipeline": name, "error": f"{cmd[0]} not found"})
            continue
        res = run(cmd)
        if "error" in res:
            rows.append({"pipeline": name, "error": res["error"]})
            continue
        rows.append({
            "pipeline": res["pipeline"],
            "pages_total": res["pages_total"],
            "pages_ok": res["pages_ok"],
            "tokens_total": res["tokens_total"],

           "avg_noise_ratio": res["avg_noise_ratio"],
            "throughput_pages_per_sec": res["throughput_pages_per_sec"],
            "top_failures": summarize_failures(res.get("failures",[]))
        })
    # write JSON, CSV, HTML
    with open("comparison_report.json","w") as f: json.dump(rows, f, indent=2)
    write_csv(rows)
    write_html(rows)
    print("Reports written: comparison_report.json, comparison_report.csv, comparison_report.html")
