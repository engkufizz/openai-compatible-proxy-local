import os
import re
import json
import time
import math
import hashlib
import unicodedata
import threading
from typing import Dict, Any, List

import requests
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# ----------------- Config (env vars) -----------------
LMSTUDIO_API_BASE = os.getenv("LMSTUDIO_API_BASE", "http://localhost:1234").rstrip("/")
LMSTUDIO_API_KEY = os.getenv("LMSTUDIO_API_KEY", "").strip()
LMSTUDIO_MODEL = os.getenv("LMSTUDIO_MODEL", "local")

IN_FILE = os.getenv("IN_FILE", "Testing.xlsx")
OUT_FILE = os.getenv("OUT_FILE", "Testing_output.xlsx")
SHEET_NAME_ENV = os.getenv("SHEET_NAME", "").strip()  # empty means first sheet
OUTPUT_COL = os.getenv("OUTPUT_COL", "AI Output")

SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are a helpful assistant. Respond concisely in plain text.")
USER_PROMPT_TEMPLATE = os.getenv("USER_PROMPT_TEMPLATE", "").strip()

TEMPERATURE = float(os.getenv("TEMPERATURE", "0.0"))
TOP_P = float(os.getenv("TOP_P", "1.0"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "512"))
WORKERS = max(1, int(os.getenv("WORKERS", "1")))
TRIM_TO_WORDS = max(0, int(os.getenv("TRIM_TO_WORDS", "0")))  # 0 disables trimming
TIMEOUT = int(os.getenv("TIMEOUT", "180"))

RETRIES = max(1, int(os.getenv("RETRIES", "3")))
RETRY_BACKOFF = float(os.getenv("RETRY_BACKOFF", "2.0"))  # seconds multiplier

# ----------------- Utilities -----------------
def norm_ascii(s: str) -> str:
    """Normalise to ASCII-friendly text and trim common odd punctuation."""
    s = unicodedata.normalize("NFKC", s or "")
    replacements = {
        "\u2011": "-", "\u2013": "-", "\u2014": "-",
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\xa0": " "
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s.strip()

PLACEHOLDER_RE = re.compile(r"\{\{([^}|]+)(?:\|([^}]*))?\}\}")

def _safe_cell(v: Any, default: str = "") -> str:
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    return str(v) if v is not None else default

def render_template(template: str, row: Dict[str, Any]) -> str:
    """
    Replace {{Column Name}} or {{Column Name|default}} with row values.
    Special placeholder: {{row_json}} inserts a compact JSON of the row.
    Case-insensitive column fallback if exact name not found.
    """
    def repl(m):
        key = m.group(1).strip()
        default = m.group(2) if m.group(2) is not None else ""
        if key.lower() == "row_json":
            safe_row = {k: _safe_cell(v, "") for k, v in row.items()}
            return json.dumps(safe_row, ensure_ascii=False)
        if key in row:
            val = row[key]
        else:
            matches = [k for k in row.keys() if k.lower() == key.lower()]
            val = row[matches[0]] if matches else default
        return _safe_cell(val, default)
    return PLACEHOLDER_RE.sub(repl, template)

def headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if LMSTUDIO_API_KEY:
        h["Authorization"] = f"Bearer {LMSTUDIO_API_KEY}"
    return h

def call_chat(messages: List[Dict[str, str]]) -> str:
    """Call LM Studio OpenAI-compatible /v1/chat/completions and return content string."""
    url = f"{LMSTUDIO_API_BASE}/v1/chat/completions"
    payload = {
        "model": LMSTUDIO_MODEL,
        "messages": messages,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "max_tokens": MAX_TOKENS,
        "stream": False
    }
    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            r = requests.post(url, headers=headers(), json=payload, timeout=TIMEOUT)
            r.raise_for_status()
            j = r.json()
            content = j["choices"][0]["message"]["content"]
            return content.strip()
        except Exception as e:
            last_err = e
            if attempt < RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)
    raise RuntimeError(f"API call failed after {RETRIES} attempts: {last_err}")

def postprocess(ans: str) -> str:
    """Clean output; optionally limit to N words."""
    a = norm_ascii(ans)
    if TRIM_TO_WORDS > 0:
        parts = a.split()
        if len(parts) > TRIM_TO_WORDS:
            a = " ".join(parts[:TRIM_TO_WORDS])
    return a

def build_messages(prompt: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]

# ----------------- Main processing -----------------
_cache_lock = threading.Lock()

def process_row(row_dict: Dict[str, Any], cache: Dict[str, str]) -> str:
    """Render prompt for a row, call the model, and return post-processed output with caching."""
    prompt = render_template(USER_PROMPT_TEMPLATE, row_dict)
    cache_key = hashlib.sha256((SYSTEM_PROMPT + "\n" + prompt).encode("utf-8")).hexdigest()

    with _cache_lock:
        if cache_key in cache:
            return cache[cache_key]

    try:
        content = call_chat(build_messages(prompt))
        output = postprocess(content)
    except Exception as e:
        output = f"Error: {e}"

    with _cache_lock:
        cache[cache_key] = output
    return output

def _sheet_name_value() -> Any:
    """Return value for pandas sheet_name argument based on SHEET_NAME env."""
    if not SHEET_NAME_ENV:
        return 0  # first sheet
    # Try to parse as integer index if numeric
    if SHEET_NAME_ENV.isdigit():
        try:
            return int(SHEET_NAME_ENV)
        except Exception:
            pass
    return SHEET_NAME_ENV  # sheet by name

def main():
    if not USER_PROMPT_TEMPLATE:
        raise SystemExit("USER_PROMPT_TEMPLATE is required. Example: export USER_PROMPT_TEMPLATE='Summarise: {{Description}}'")

    df = pd.read_excel(IN_FILE, sheet_name=_sheet_name_value())
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)

    records: List[Dict[str, Any]] = df.to_dict(orient="records")

    cache: Dict[str, str] = {}
    outputs: List[str] = [""] * len(records)

    if WORKERS == 1:
        for i, row in enumerate(records):
            outputs[i] = process_row(row, cache)
            if (i + 1) % 25 == 0:
                print(f"Processed {i+1} rows...")
    else:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(process_row, row, cache): idx for idx, row in enumerate(records)}
            done = 0
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    outputs[idx] = fut.result()
                except Exception as e:
                    outputs[idx] = f"Error: {e}"
                done += 1
                if done % 25 == 0:
                    print(f"Processed {done} rows...")

    df[OUTPUT_COL] = outputs
    df.to_excel(OUT_FILE, index=False)
    print(f"Wrote {OUT_FILE} with column '{OUTPUT_COL}'")

if __name__ == "__main__":
    main()
