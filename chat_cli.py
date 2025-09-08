import os
import argparse
import requests

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", default=os.getenv("LMSTUDIO_API_BASE", "http://localhost:1234"), help="API base URL (LM Studio or proxy)")
    p.add_argument("--model", default=os.getenv("LMSTUDIO_MODEL", "local"), help="Model name/id")
    p.add_argument("--key", default=os.getenv("LMSTUDIO_API_KEY", ""), help="Bearer API key (optional)")
    p.add_argument("--system", default=os.getenv("SYSTEM_PROMPT", "You are a helpful assistant. Respond concisely in plain text."))
    p.add_argument("--prompt", required=True, help="User prompt")
    p.add_argument("--timeout", type=int, default=int(os.getenv("TIMEOUT", "120")))
    p.add_argument("--temperature", type=float, default=float(os.getenv("TEMPERATURE", "0.7")))
    p.add_argument("--top_p", type=float, default=float(os.getenv("TOP_P", "1.0")))
    p.add_argument("--max_tokens", type=int, default=int(os.getenv("MAX_TOKENS", "512")))
    args = p.parse_args()

    url = f"{args.base.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": args.model,
        "messages": [
            {"role": "system", "content": args.system},
            {"role": "user", "content": args.prompt},
        ],
        "temperature": args.temperature,
        "top_p": args.top_p,
        "max_tokens": args.max_tokens,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if args.key:
        headers["Authorization"] = f"Bearer {args.key}"

    r = requests.post(url, headers=headers, json=payload, timeout=args.timeout)
    r.raise_for_status()
    j = r.json()
    print(j["choices"][0]["message"]["content"].strip())

if __name__ == "__main__":
    main()
