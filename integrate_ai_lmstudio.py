import os
import time
import unicodedata
import requests
import pandas as pd

# --- Config (override via environment variables if needed) ---
LMSTUDIO_API_BASE = os.getenv("LMSTUDIO_API_BASE", "http://localhost:1234")  # LM Studio local server base
LMSTUDIO_API_KEY = os.getenv("LMSTUDIO_API_KEY", "").strip()                  # If you enabled an API key
MODEL = os.getenv("LMSTUDIO_MODEL", "local")                                   # "local" works for LM Studio

IN_FILE = os.getenv("IN_FILE", "Testing.xlsx")
OUT_FILE = os.getenv("OUT_FILE", "Testing_output.xlsx")
SOURCE_COL = os.getenv("SOURCE_COL", "Activity Export")
WO1_COL = os.getenv("WO1_COL", "Activity Export WO 1")
TARGET_COL = os.getenv("TARGET_COL", "Prolong Factor")

PROMPT_TEMPLATE = """Your task is to identify the “prolong factor” based on the incident tickets — the primary reason the ticket exceeded four hours to restore — from free‑form ticket remarks. Output only the factor, no explanations.

If multiple candidate reasons appear, choose the most specific human‑readable cause (e.g., “Fibre cut”, “Power failure”, “Access issue”, “Vendor dependency”, & etc).

Other keywords such as, not specifically but you understanding based on the context:
Power: TNB, SESCO, SESB, power, genset, solar, rectifier, breaker, yellow phase & etc
Fibre cut: rodent, fibre failure, land slide
Hardware/spare: IDU, ODU, modem, AFS, card, port, cable, SFP, patch cord, IF connector, hardware, waveguide, flexi
Access/permit: access issue, skylift, local council, approval, landlord
Performance: reroute, switch, reduce modulation, adjust queue discard, packet loss, intermittent
Microwave: realignment, raised antenna, dish, blocking, RSL low
Theft: vandalism, theft
Plan event: plan, event

If in the remark already mentioned delay due to what, just directly take from the remark

If no reliable reason is found, return: Insufficient information

You will receive ticket remarks below. Based on the remarks, what is the prolong factor? Follow the rules above and answer in not more than 5 words. Output only the factor

Remarks: {TICKET_REMARKS}
"""

def norm_ascii(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    replacements = {
        "\u2011": "-", "\u2013": "-", "\u2014": "-",
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\xa0": " "
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    return s.strip()

def build_messages(remarks: str):
    prompt = PROMPT_TEMPLATE.replace("{TICKET_REMARKS}", remarks or "")
    return [
        {"role": "system", "content": "Answer concisely in plain ASCII. Output only the factor. Maximum 5 words."},
        {"role": "user", "content": prompt}
    ]

def _headers():
    h = {"Content-Type": "application/json"}
    if LMSTUDIO_API_KEY:
        h["Authorization"] = f"Bearer {LMSTUDIO_API_KEY}"
    return h

def ask_extractor(remarks: str, retries: int = 3, timeout: int = 180) -> str:
    messages = build_messages(remarks)
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.0,
        "top_p": 1.0,
        "stream": False
    }
    url = f"{LMSTUDIO_API_BASE.rstrip('/')}/v1/chat/completions"
    for i in range(retries):
        try:
            r = requests.post(url, headers=_headers(), json=payload, timeout=timeout)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()
            return postprocess_answer(content)
        except Exception as e:
            if i == retries - 1:
                return f"Error: {e}"
            time.sleep(2 * (i + 1))

def postprocess_answer(ans: str) -> str:
    a = norm_ascii(ans)
    a = a.strip(" .,:;-/\\|\"'()[]{}")
    parts = a.split()
    if len(parts) > 5:
        a = " ".join(parts[:5])
    return a or "Insufficient information"

def _series_as_str(df: pd.DataFrame, col: str) -> pd.Series:
    if col in df.columns:
        return df[col].fillna("").astype(str)
    return pd.Series([""] * len(df), index=df.index)

def main():
    df = pd.read_excel(IN_FILE)
    if SOURCE_COL not in df.columns:
        raise SystemExit(f"Column '{SOURCE_COL}' not found in {IN_FILE}")

    main_s = _series_as_str(df, SOURCE_COL).str.strip()
    wo1_s = _series_as_str(df, WO1_COL).str.strip()
    combined_series = (main_s + " " + wo1_s).str.replace(r"\s+", " ", regex=True).str.strip()
    remarks_list = [norm_ascii(x) for x in combined_series.tolist()]

    cache = {}
    results = []
    for i, remarks in enumerate(remarks_list, start=1):
        key = remarks.strip()
        if key in cache:
            ans = cache[key]
        else:
            ans = ask_extractor(remarks)
            cache[key] = ans
        results.append(ans)
        if i % 25 == 0:
            print(f"Processed {i} rows...")

    df[TARGET_COL] = results
    df.to_excel(OUT_FILE, index=False)
    print(f"Wrote {OUT_FILE} with column '{TARGET_COL}'")

if __name__ == "__main__":
    main()
