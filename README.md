# LM Studio Local LLM – Excel “Prolong Factor” Analyser

This project helps you classify **prolong factors** from ticket remarks using a local LLM served by **LM Studio**.  

You have two ways to connect:

- **Option A (recommended):** Call LM Studio’s built-in OpenAI-compatible API directly from the Excel script.  
- **Option B (optional):** Run a tiny local proxy that forwards OpenAI-style requests to LM Studio, so your tools can use a stable `http://localhost:8000/v1` endpoint.  

Both options will produce an output Excel file with a new **“Prolong Factor”** column.

---

## 📂 Repository Contents

- `integrate_ai_lmstudio.py` — Excel processing script that calls LM Studio directly.  
- `lmstudio_openai_proxy.py` — Minimal OpenAI-compatible proxy that forwards to LM Studio.  

---

## ✅ Prerequisites

- **LM Studio** installed, with a suitable **instruct model** downloaded and loaded  
  (e.g., *Llama 3.x Instruct*, 7–8B quantised Q4/Q5).  
- **Python 3.9+** recommended.  
- Input Excel file named **`Testing.xlsx`** with these columns:
  - `Activity Export` *(required)*  
  - `Activity Export WO 1` *(optional)*  

---

## 📦 Install Python Dependencies

If you only use **Option A** (direct):  

```bash
pip install requests pandas openpyxl
````

If you may also use **Option B** (proxy):

```bash
pip install requests pandas openpyxl fastapi uvicorn
```

---

## ▶️ Start LM Studio’s Local Server

1. Open **LM Studio**.
2. Load your chosen model.
3. Open **Local Server (OpenAI API compatible)** panel.
4. Set a port (e.g., `1234`) and enable the server.

* Default base URL: `http://localhost:1234`
* API root: `http://localhost:1234/v1`
* API key: optional (if enabled, keep it handy, e.g., `lm-studio-key`).

### Quick Tests

* List models:

  ```bash
  curl http://localhost:1234/v1/models
  ```
* Simple chat:

  ```bash
  curl -s http://localhost:1234/v1/chat/completions \
    -H "Content-Type: application/json" \
    -d '{"model":"local","messages":[{"role":"user","content":"Hello"}]}'
  ```

If you enabled an API key, add:

```bash
-H "Authorization: Bearer lm-studio-key"
```

---

## 🔹 Option A: Direct Connection (Recommended)

The Excel script calls LM Studio’s API directly. This is the **simplest setup**.

### Configuration

Override defaults using environment variables:

| Variable            | Default                 |
| ------------------- | ----------------------- |
| `LMSTUDIO_API_BASE` | `http://localhost:1234` |
| `LMSTUDIO_API_KEY`  | *(empty)*               |
| `LMSTUDIO_MODEL`    | `local`                 |
| `IN_FILE`           | `Testing.xlsx`          |
| `OUT_FILE`          | `Testing_output.xlsx`   |
| `SOURCE_COL`        | `Activity Export`       |
| `WO1_COL`           | `Activity Export WO 1`  |
| `TARGET_COL`        | `Prolong Factor`        |

**Examples:**

* **Bash**

  ```bash
  export LMSTUDIO_API_BASE="http://localhost:1234"
  export LMSTUDIO_API_KEY="lm-studio-key"
  ```
* **PowerShell**

  ```powershell
  $env:LMSTUDIO_API_BASE = "http://localhost:1234"
  $env:LMSTUDIO_API_KEY = "lm-studio-key"
  ```

### Run

```bash
python integrate_ai_lmstudio.py
```

* Place `Testing.xlsx` next to the script.
* The script will create `Testing_output.xlsx` with a new **Prolong Factor** column.

### What the Script Does

* Reads `Activity Export` and `Activity Export WO 1` (if present).
* Normalises Unicode punctuation and whitespace.
* Prompts the local model to output a concise **prolong factor** (≤ 5 words).
* Caches repeated remarks within the same run.
* Writes results to the output file.

---

## 🔹 Option B: Local OpenAI-Compatible Proxy (Optional)

Run a lightweight proxy that forwards OpenAI requests to LM Studio.
Useful if you want a **stable endpoint** like `http://localhost:8000/v1`.

### Configuration

| Variable                    | Default                    |
| --------------------------- | -------------------------- |
| `LMSTUDIO_API_BASE`         | `http://localhost:1234/v1` |
| `LMSTUDIO_API_KEY`          | *(empty)*                  |
| `LMSTUDIO_PROXY_MODEL_NAME` | `lmstudio-proxy`           |
| `PROXY_TIMEOUT`             | `300`                      |

**Examples:**

* **Bash**

  ```bash
  export LMSTUDIO_API_BASE="http://localhost:1234/v1"
  export LMSTUDIO_API_KEY="lm-studio-key"
  ```
* **PowerShell**

  ```powershell
  $env:LMSTUDIO_API_BASE = "http://localhost:1234/v1"
  $env:LMSTUDIO_API_KEY = "lm-studio-key"
  ```

### Run the Proxy

```bash
uvicorn lmstudio_openai_proxy:app --host 0.0.0.0 --port 8000
```

### Test the Proxy

```bash
curl http://localhost:8000/v1/models
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"local","messages":[{"role":"user","content":"Hi"}]}'
```

* Base URL: `http://localhost:8000`
* API path: `/v1`

If your client expects an API key, you can pass any placeholder.
The proxy forwards the real key if set via `LMSTUDIO_API_KEY`.

---

## 📊 Input & Output

* **Input file:** `Testing.xlsx`
* **Required column:** `Activity Export`
* **Optional column:** `Activity Export WO 1`
* **Output file:** `Testing_output.xlsx`
* **New column added:** `Prolong Factor`

If `Activity Export WO 1` is missing, the script will still run using `Activity Export` only.

---

## 🧪 Quick Smoke Tests

**Python direct call:**

```bash
python -c "import os,requests;os.environ['LMSTUDIO_API_BASE']='http://localhost:1234';print(requests.post(f\"{os.environ['LMSTUDIO_API_BASE'].rstrip('/')}/v1/chat/completions\", json={'model':'local','messages':[{'role':'user','content':'Return only one of: Power failure, Fibre cut, Access issue, or Insufficient information. Remarks: site down due to TNB outage'}]}).json())"
```

**Curl direct call:**

```bash
curl -s http://localhost:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"local","messages":[{"role":"user","content":"Return only one of: Power failure, Fibre cut, Access issue, or Insufficient information. Remarks: site down due to TNB outage"}]}'
```

---

## 💡 Tips & Best Practices

* Use **`temperature=0`** for deterministic classification.
* Prefer smaller quantised models (e.g., 7–8B Q4/Q5) for speed; scale up later if needed.
* Increase HTTP timeouts to **180–300s** for larger models.
* Keep caching enabled (already in script).
* Start with a small sample (e.g., 10 rows) before processing the full sheet.

---

## 🛠️ Troubleshooting

* **404 / connection refused** → Check LM Studio’s server is running with the right port.
* **401 unauthorised** → Set `LMSTUDIO_API_KEY` if LM Studio’s key is enabled.
* **KeyError: 'Activity Export'** → Ensure your Excel file has the correct column names (or override via env vars).
* **Slow responses / timeouts** → Use a smaller model or increase timeouts.
* **Garbled / verbose outputs** → The script enforces concise ASCII (≤ 5 words). Adjust prompt if needed.

---

## ⚙️ Customisation

* Override column names and file paths via environment variables.
* Add concurrency (e.g., `concurrent.futures`) for faster batch processing.
* Use a fixed label set by:

  * Constraining the prompt, or
  * Post-filtering free-text into canonical categories.

