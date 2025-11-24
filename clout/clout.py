#!/usr/bin/env python3
"""
- Merges CHUNK-SUMMARY engine + HIGH-END editorial variants
- Resumable via JSON caches
- SERP enrichment + entity extraction + streaming generation
- Saves everything into clout_ultra.xlsx
"""

import os, re, time, json
from pathlib import Path
from typing import List, Dict

import requests, validators
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openpyxl import Workbook, load_workbook

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

# ======================================================
# CONFIG
# ======================================================
ROOT = Path(__file__).parent.resolve()
load_dotenv(ROOT / ".env")

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
MODEL_PATH = os.getenv("LLAMA_CPP_MODEL_PATH")

BLOG_URLS = [
    # ADD ANY URLs HERE
    "https://pallavighxsh.wordpress.com/2025/01/28/ai-tone-consistency-in-brand-aligned-communication/",
]

EXCEL_PATH = ROOT / "clout_ultra.xlsx"

HEADERS = {"User-Agent": "Mozilla/5.0"}

CACHE_MAIN = ROOT / "cache_summary.json"
CACHE_VARIANTS = ROOT / "cache_variants.json"
CACHE_SERP = ROOT / "cache_serp.json"

# 3 long-form variants
VARIANTS = [
    ("Thought Leadership", "Write a senior thought-leadership piece."),
    ("Story Narrative", "Write a story-driven narrative."),
    ("Actionable Framework", "Write a 3–5 step actionable framework."),
]

# ======================================================
# UTILS
# ======================================================
def fetch_paras(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except:
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    return "\n\n".join(
        p.get_text(" ", strip=True)
        for p in soup.find_all("p") if p.get_text(strip=True)
    )

def serp_search(text, n=3):
    if not SERPAPI_KEY: return []
    try:
        r = requests.get(
            "https://serpapi.com/search",
            params={"q": text, "api_key": SERPAPI_KEY, "num": n},
            timeout=20
        ).json()
        return [o.get("link") for o in r.get("organic_results", []) if validators.url(o.get("link",""))][:n]
    except:
        return []

def extract_entities(text):
    return {
        "emails": sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text))),
        "proper_nouns": sorted(set(re.findall(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)*\b", text))),
    }

# ======================================================
# LLM
# ======================================================
def load_llm():
    if not MODEL_PATH or not Path(MODEL_PATH).exists():
        print("❌ Missing or invalid model path")
        return None
    print("🔧 Loading model safely…")
    return Llama(model_path=MODEL_PATH, n_ctx=2048, n_gpu_layers=18, n_threads=4)

def stream_generate(llm, prompt: str, max_toks=700):
    full = ""
    for ch in llm(prompt, max_tokens=max_toks, temperature=0.35, stream=True):
        token = ch.get("choices",[{}])[0].get("text","")
        print(token, end="", flush=True)
        full += token
    return full

# ======================================================
# CACHE HELPERS
# ======================================================
def load_cache(p): return json.load(open(p)) if p.exists() else {}
def save_cache(p,d): json.dump(d, open(p,"w"), indent=2)

# ======================================================
# CHUNK SUMMARIES
# ======================================================
def summarize_chunks(llm, text):
    c = load_cache(CACHE_MAIN)
    chs = [text[i:i+800] for i in range(0, len(text), 800)]
    results=[]
    for i,chunk in enumerate(chs):
        key=f"chunk_{i}"
        if key in c:
            results.append(c[key]); continue
        prompt=f"Summarize clearly, concisely:\n{chunk}\nSummary:"
        try:
            resp=llm(prompt, max_tokens=70, temperature=0.25)
            summ = resp["choices"][0]["text"].strip()
        except: summ="(failed)"
        c[key]=summ; save_cache(CACHE_MAIN,c)
        results.append(summ)
    return "\n".join(results)

# ======================================================
# VARIANT POSTS
# ======================================================
def make_variant(llm, label, instr, base, serp):
    c=load_cache(CACHE_VARIANTS); key=f"{label}_{hash(base) % 99999}"
    if key in c: return c[key]

    prompt=f"""
You are a senior editorial strategist writing long, human LinkedIn posts.

Variant: {label}
Instruction: {instr}

Write a deep, narrative, 700–1000 word post synthesizing:
- This blog context:
{base[:5000]}

- Insights from other sources:
{serp[:7000]}

Rules:
- Human tone, flowing paragraphs, not a summary, expand ideas.
- Do NOT mention you used external data.
- Don't list "sources". 
Format:
###
HEADLINE:
<5–12 words>
POST:
<full post>
###
"""
    print(f"\n🎨 Generating {label}…\n")
    gen = stream_generate(llm, prompt).strip()
    if "POST:" in gen:
        head,body=gen.split("POST:",1)
        out={"label":label,"headline":head.replace("HEADLINE:","").strip(),"body":body.strip()}
    else:
        out={"label":label,"headline":label,"body":gen}
    c[key]=out; save_cache(CACHE_VARIANTS,c)
    return out

# ======================================================
# EXCEL
# ======================================================
def init_excel():
    if not EXCEL_PATH.exists():
        wb=Workbook()
        ws=wb.active; ws.title="posts"
        ws.append(["url","variant","headline","body","emails","proper_nouns","serp_links"])
        wb.save(EXCEL_PATH)

def save_row(d):
    wb=load_workbook(EXCEL_PATH); ws=wb["posts"]
    ws.append([d.get("url"),d.get("variant"),d.get("headline"),d.get("body"),
               ", ".join(d.get("emails",[])),", ".join(d.get("proper_nouns",[])),
               ", ".join(d.get("serp_links",[]))])
    wb.save(EXCEL_PATH)

# ======================================================
# MAIN
# ======================================================
def main():
    init_excel()
    llm=load_llm(); 
    if not llm: return

    for url in BLOG_URLS:
        print(f"\n📰 Scraping {url}")
        text = fetch_paras(url)
        if not text: continue

        print("🔎 SERP Finding…")
        serp_links = serp_search(text[:120],3)

        serp_text=""
        for s in serp_links:
            serp_text+=fetch_paras(s)+"\n\n"; time.sleep(1)

        ents = extract_entities(serp_text)

        print("\n✂️ Chunk Summaries (for context)…")
        base_summary = summarize_chunks(llm,text)

        # generate 3 enriched variants
        for label,instr in VARIANTS:
            out = make_variant(llm,label,instr,base_summary,serp_text)
            save_row({
                "url": url,
                "variant": label,
                "headline": out["headline"],
                "body": out["body"],
                "emails": ents["emails"],
                "proper_nouns": ents["proper_nouns"],
                "serp_links": serp_links
            })
            print(f"\n💾 Saved {label} for {url}")

    print("\n🎉 DONE — saved to", EXCEL_PATH)

if __name__=="__main__":
    main()
