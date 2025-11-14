#!/usr/bin/env python3
"""
clout.py
- Generates 3 LinkedIn posts per blog (different angles)
- Streams tokens in terminal while capturing full output
- Saves one row per post into clout_posts.xlsx
- Saves SERP debug into 'serp_debug' sheet
- Safe for Phi-3 q4 on MacBook Air via trimming + n_ctx=2048 + n_gpu_layers=20
"""

import os
import json
import re
import time
from pathlib import Path
from typing import List, Dict

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook, load_workbook
from dotenv import load_dotenv
import validators

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None

# -------------------------
# CONFIG
# -------------------------
PROJECT_ROOT = Path(__file__).parent.resolve()
EXCEL_FILE = PROJECT_ROOT / "clout_posts.xlsx"
load_dotenv(PROJECT_ROOT / ".env")

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
LLAMA_MODEL_PATH = os.getenv("LLAMA_CPP_MODEL_PATH")

HEADERS = {"User-Agent": "Mozilla/5.0"}

# Your blog list (can also be a product page or random article but don't change the variable name)
BLOG_URLS = [
    "https://pallavighxsh.wordpress.com/2025/01/28/ai-tone-consistency-in-brand-aligned-communication/",
    "https://pallavighxsh.wordpress.com/2024/10/22/tone-it-down-can-ai-really-get-your-brand-voices-vibe/",
    "https://pallavighxsh.wordpress.com/2024/07/08/on-generative-ai/",
]

# Variants: label + a short instruction fragment to bias generation
VARIANTS = [
    ("Thought Leadership", "Write a senior thought-leadership piece: big-picture insights, implications, frameworks."),
    ("Story Narrative", "Write a story-driven narrative: open with a concise anecdote or scene, then connect to insights."),
    ("Actionable / Framework", "Write an actionable post with a clear framework or 3–5 tactical steps the reader can apply."),
]


# -------------------------
# UTILITIES
# -------------------------
def scrape_url(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except:
        return ""
    soup = BeautifulSoup(r.text, "html.parser")
    paras = [p.get_text(" ", strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
    return "\n\n".join(paras)


def serpapi_search(query: str, num: int = 5) -> List[str]:
    if not SERPAPI_KEY:
        return []
    try:
        r = requests.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": SERPAPI_KEY, "num": num},
            timeout=20
        )
        data = r.json()
        links = []
        for item in data.get("organic_results", [])[:num]:
            link = item.get("link")
            if link and validators.url(link):
                links.append(link)
        return links
    except:
        return []


def extract_entities(text: str) -> Dict[str, List[str]]:
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    proper_nouns = re.findall(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)*\b", text)
    # dedupe small lists
    return {"emails": sorted(set(emails)), "proper_nouns": sorted(set(proper_nouns))}


# -------------------------
# LLM
# -------------------------
def load_llm():
    if not LLAMA_MODEL_PATH or not Path(LLAMA_MODEL_PATH).exists():
        print("❌ Model path invalid. Set LLAMA_CPP_MODEL_PATH in .env")
        return None
    if Llama is None:
        print("❌ llama_cpp not installed in this environment.")
        return None

    print("Loading LLaMA model (safe settings)...")
    return Llama(
        model_path=LLAMA_MODEL_PATH,
        n_ctx=2048,        # reduced context for stability
        n_threads=4,
        n_gpu_layers=20    # limited Metal offload
    )


def final_trim_prompt(prompt: str, max_chars: int = 7000) -> str:
    # last-safety: trim characters to keep tokens under context window
    if len(prompt) <= max_chars:
        return prompt
    return prompt[:max_chars]


def generate_one_variant(llm, variant_label: str, variant_instr: str, blog_text: str, serp_text: str) -> Dict[str, str]:
    # LIGHT TRIMS of source materials
    blog_text = blog_text[:5000]   # about ~1700 tokens before tokenization
    serp_text = serp_text[:7000]   # keep SERP context but trimmed

    combined = blog_text + "\n\n" + serp_text

    prompt = f"""
You are a senior editorial content strategist who writes high-impact, human, long-form LinkedIn posts.

Variant: {variant_label}
Style Instruction: {variant_instr}

Write a polished, original, human-sounding LinkedIn post of **700–1000 words** (aim for ~800 words).
This must NOT summarize the blog. Instead, it must:
- Expand on the ideas, frameworks, insights, and themes found in the blog content.
- Integrate and synthesize insights from BOTH the blog and the SERP-scraped external pages.
- Show intellectual depth, critical thinking, and editorial expertise.
- Use **long, flowing, high-quality paragraphs** (5–7 sentences each), not bullet points.
- Use a **LinkedIn-appropriate tone**: engaging, reflective, and expert — not academic or robotic.
- Use narrative openings, transitions, and emotional or strategic framing.
- Offer a clear perspective, interpretation, or actionable direction.
- Avoid lists unless absolutely necessary; rely on narrative explanation and analysis.
- DO NOT repeat the same sentence structures or rephrase the blog.
- DO NOT mention that you're combining sources.

Use this combined text ONLY as background knowledge to enrich arguments, examples, frameworks, and narrative:
========
{combined}
========

Follow this EXACT output structure — this is mandatory:

###
HEADLINE:
<one compelling headline, 5–12 words>

POST:
<full LinkedIn post, 700–1000 words, long paragraphs, deeply synthesizing blog + SERP insights>
###

Do NOT place anything before HEADLINE:
Do NOT place anything after the final ###.
"""


    # FINAL SAFETY TRIM
    prompt = final_trim_prompt(prompt, max_chars=7000)

    # Stream tokens and capture
    full_text = ""
    print(f"\n--- Generating variant: {variant_label} ---\n")
    try:
        for chunk in llm(
            prompt,
            max_tokens=700,   # safe generation length
            temperature=0.35,
            stream=True
        ):
            # chunk is usually a dict like {"choices":[{"text":"..."}]}
            choices = chunk.get("choices") if isinstance(chunk, dict) else None
            if choices and isinstance(choices, list):
                token = choices[0].get("text", "")
                full_text += token
                print(token, end="", flush=True)
    except ValueError as e:
        # token overflow or other LLaMA error
        print("\n\n[LLM ERROR]", e)
        return {"headline": "ERROR", "body": ""}

    print("\n\n--- generation complete ---\n")

    # Parse HEADLINE and POST
    if "POST:" in full_text:
        head_part, post_part = full_text.split("POST:", 1)
        headline = head_part.replace("HEADLINE:", "").strip()
        body = post_part.strip()
    else:
        # best-effort fallback
        headline = "LinkedIn Post"
        body = full_text.strip()

    return {"headline": headline, "body": body}


# -------------------------
# EXCEL
# -------------------------
def init_excel():
    if not EXCEL_FILE.exists():
        wb = Workbook()
        ws = wb.active
        ws.title = "linkedin"
        ws.append([
            "source_url",
            "variant",
            "headline",
            "body",
            "serp_emails",
            "serp_proper_nouns",
            "serp_links"
        ])
        # also create serp_debug sheet
        wb.create_sheet("serp_debug")
        wb.save(EXCEL_FILE)


def append_to_excel_row(row: Dict):
    wb = load_workbook(EXCEL_FILE)
    ws = wb["linkedin"]
    ws.append([
        row.get("source_url", ""),
        row.get("variant", ""),
        row.get("headline", ""),
        row.get("body", ""),
        ", ".join(row.get("serp_emails", [])),
        ", ".join(row.get("serp_proper_nouns", [])),
        ", ".join(row.get("serp_links", [])),
    ])
    wb.save(EXCEL_FILE)


def save_serp_debug(url: str, serp_links: List[str], serp_text: str):
    wb = load_workbook(EXCEL_FILE)
    if "serp_debug" not in wb.sheetnames:
        ws = wb.create_sheet("serp_debug")
        ws.append(["source_url", "serp_links", "serp_text"])
    else:
        ws = wb["serp_debug"]
    ws.append([url, json.dumps(serp_links), serp_text[:5000]])
    wb.save(EXCEL_FILE)


# -------------------------
# MAIN
# -------------------------
def main():
    init_excel()
    llm = load_llm()
    if not llm:
        return

    for url in BLOG_URLS:
        print(f"\n📝 Scraping blog: {url}")
        blog_text = scrape_url(url)
        if not blog_text:
            print("No blog text found — skipping.")
            continue

        print("🔍 Running SERP search...")
        serp_links = serpapi_search(blog_text[:80], num=5)

        print("🌐 Scraping SERP pages...")
        serp_text = ""
        for link in serp_links:
            serp_text += scrape_url(link) + "\n\n"
            time.sleep(1)

        print("📊 Extracting entities from SERP text...")
        entities = extract_entities(serp_text)

        # save SERP debug always
        save_serp_debug(url, serp_links, serp_text)

        # generate 3 variants
        for variant_label, variant_instr in VARIANTS:
            result = generate_one_variant(llm, variant_label, variant_instr, blog_text, serp_text)

            append_to_excel_row({
                "source_url": url,
                "variant": variant_label,
                "headline": result.get("headline", ""),
                "body": result.get("body", ""),
                "serp_emails": entities["emails"],
                "serp_proper_nouns": entities["proper_nouns"],
                "serp_links": serp_links,
            })

            print(f"✅ Saved variant '{variant_label}' for {url} to Excel.\n")

    print("\n🎉 All done. Excel saved to:", EXCEL_FILE)


if __name__ == "__main__":
    main()
