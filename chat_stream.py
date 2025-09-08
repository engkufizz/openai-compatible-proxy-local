import os
import argparse
import json
import requests

def stream_chat(base, model, system, prompt, key=None, timeout=300):
    url = f"{base.rstrip('/')}/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "temperature": 0.7,
        "top_p": 1.0,
    }
    with requests.post(url, headers=headers, json=payload, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            if line.startswith("data: "):
                data = line[6:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
                if delta:
                    print(delta, end="", flush=True)
    print()  # newline at end

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.getenv("LMSTUDIO_API_BASE", "http://localhost:1234"))
    ap.add_argument("--model", default=os.getenv("LMSTUDIO_MODEL", "local"))
    ap.add_argument("--key", default=os.getenv("LMSTUDIO_API_KEY", ""))
    ap.add_argument("--system", default=os.getenv("SYSTEM_PROMPT", "You are a helpful assistant. Respond concisely in plain text."))
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--timeout", type=int, default=int(os.getenv("TIMEOUT", "300")))
    args = ap.parse_args()

    stream_chat(args.base, args.model, args.system, args.prompt, key=args.key, timeout=args.timeout)

if __name__ == "__main__":
    main()
