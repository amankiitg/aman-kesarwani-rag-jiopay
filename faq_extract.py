# faq_extract.py (expects HTML or innerText string `page_text`)
import re

def extract_faq_pairs(page_text):
    # naive pattern: lines starting with common question stems
    qs = []
    lines = [l.strip() for l in page_text.splitlines() if l.strip()]
    for i,l in enumerate(lines):
        if re.match(r"(?i)^(what|how|why|can|does|do|is|are)\b", l):
            # join following lines until next question or blank
            ans = []
            for j in range(i+1, min(i+12, len(lines))):
                if re.match(r"(?i)^(what|how|why|can|does|do|is|are)\b", lines[j]): break
                ans.append(lines[j])
            qs.append({"question": l, "answer": " ".join(ans).strip()})
    return qs
