# LM Studio – Excel-to-AI Analyzer

## Overview

This project lets you run AI prompts over rows in an Excel file using a local model served by **LM Studio**.

* You supply a **prompt template** that can reference any Excel column via `{{Column Name}}` placeholders.
* The script writes the AI’s reply to an output column in a new Excel file.

### Two integration options

* **Option A (recommended):** Call LM Studio directly.
* **Option B (optional):** Use a small local proxy that forwards OpenAI-style calls to LM Studio (`http://localhost:8000/v1`).

---

## Files

* `excel_ai_analyzer.py` — Excel-to-AI analyzer that talks to LM Studio’s local API.
* `lmstudio_openai_proxy.py` — Optional proxy that forwards to LM Studio.

---

## Prerequisites

* **LM Studio** installed, with an **instruct model** loaded
  (e.g., Llama 3.x Instruct, 7–8B quantised Q4/Q5 for speed).
* Python 3.9+ recommended.
* An input Excel file (default: `Testing.xlsx`).

---

## Install Python dependencies

**Option A only:**

```bash
pip install requests pandas openpyxl
```

**Option B (proxy) as well:**

```bash
pip install requests pandas openpyxl fastapi uvicorn
```

---

## Start LM Studio’s local server

1. Open LM Studio.
2. Load your chosen model.
3. Open the **Local Server (OpenAI-compatible)** panel.
4. Set a port (e.g., `1234`) and enable the server.

   * Base URL: `http://localhost:1234`
   * API root: `http://localhost:1234/v1`
5. API key is optional. If enabled, note it (e.g., `lm-studio-key`).

### Quick test

```bash
curl http://localhost:1234/v1/models
curl -s http://localhost:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"local","messages":[{"role":"user","content":"Hello"}]}'
```

If you enabled an API key, add:

```bash
-H "Authorization: Bearer lm-studio-key"
```

---

## Option A: Direct connection (recommended)

Use `excel_ai_analyzer.py` to run a prompt over your Excel rows.

### Key features

* **Templating** with `{{Column Name}}` placeholders.
* Optional defaults: `{{Column Name|default text}}`.
* Use `{{row_json}}` to include the entire row as JSON.
* **Caching** identical prompts within a run.
* Optional concurrency for speed.
* Configurable **system prompt, temperature, top\_p, max tokens**.

### Configuration (environment variables)

| Variable               | Default                          | Description                       |
| ---------------------- | -------------------------------- | --------------------------------- |
| `LMSTUDIO_API_BASE`    | `http://localhost:1234`          | API base URL                      |
| `LMSTUDIO_API_KEY`     | *(empty)*                        | API key if enabled                |
| `LMSTUDIO_MODEL`       | `local`                          | Model name                        |
| `IN_FILE`              | `Testing.xlsx`                   | Input Excel file                  |
| `OUT_FILE`             | `Testing_output.xlsx`            | Output Excel file                 |
| `SHEET_NAME`           | first sheet                      | Target sheet                      |
| `OUTPUT_COL`           | `AI Output`                      | Column to write results           |
| `SYSTEM_PROMPT`        | `You are a helpful assistant...` | System prompt                     |
| `USER_PROMPT_TEMPLATE` | *(required)*                     | User prompt template              |
| `TEMPERATURE`          | `0.0`                            | Sampling temperature              |
| `TOP_P`                | `1.0`                            | Nucleus sampling                  |
| `MAX_TOKENS`           | `512`                            | Max output tokens                 |
| `WORKERS`              | `1`                              | Concurrency                       |
| `TRIM_TO_WORDS`        | `0`                              | Limit output words (0 = disabled) |

### Examples

* **Classification**

  ```bash
  export USER_PROMPT_TEMPLATE="Return only one label from [Bug, Inquiry, Task]. Text: {{Description}}"
  ```
* **Summarisation**

  ```bash
  export USER_PROMPT_TEMPLATE="Summarise the following in 3 bullet points:\n\n{{Ticket Details}}"
  ```
* **Extraction to JSON**

  ```bash
  export USER_PROMPT_TEMPLATE="Extract site_id and outage_start from the text. Reply as JSON with keys site_id and outage_start. Text: {{Remarks}}"
  ```
* **Multi-field JSON**

  ```bash
  export USER_PROMPT_TEMPLATE="Given the row: {{row_json}}, return a JSON with keys cause, severity, owner. Be concise."
  ```

### Run (direct)

**Bash**

```bash
export LMSTUDIO_API_BASE="http://localhost:1234"
export USER_PROMPT_TEMPLATE="Summarise: {{Activity Export}}"
python excel_ai_analyzer.py
```

**PowerShell**

```powershell
$env:LMSTUDIO_API_BASE = "http://localhost:1234"
$env:USER_PROMPT_TEMPLATE = "Summarise: {{Activity Export}}"
python excel_ai_analyzer.py
```

The script writes `OUT_FILE` with a new `OUTPUT_COL` containing AI results.

---

## Tips

* Start with a **small sample** to verify outputs.
* For faster runs:

  * Use a **smaller quantised model**.
  * Increase `WORKERS` to 2–4 (depends on machine).
* Keep **temperature low (0–0.3)** for deterministic tasks.

---

## Option B: Local proxy (stable endpoint)

Run a small proxy so your tools can always call `http://localhost:8000/v1` regardless of LM Studio port.

### Run the proxy

**Bash**

```bash
export LMSTUDIO_API_BASE="http://localhost:1234/v1"
export LMSTUDIO_API_KEY="lm-studio-key"    # only if enabled
uvicorn lmstudio_openai_proxy:app --host 0.0.0.0 --port 8000
```

**PowerShell**

```powershell
$env:LMSTUDIO_API_BASE = "http://localhost:1234/v1"
$env:LMSTUDIO_API_KEY = "lm-studio-key"
uvicorn lmstudio_openai_proxy:app --host 0.0.0.0 --port 8000
```

### Test

```bash
curl http://localhost:8000/v1/models
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"local","messages":[{"role":"user","content":"Hi"}]}'
```

Use with `excel_ai_analyzer.py`:

```bash
export LMSTUDIO_API_BASE="http://localhost:8000"
```

---

## Troubleshooting

* **Connection refused/404** → Check LM Studio local server is running and port is correct.
* **401 unauthorised** → Set `LMSTUDIO_API_KEY` if enabled.
* **Excel column not found** → Check column names / placeholders.
* **Slow or timeout** → Use a smaller model, increase timeouts, or reduce `WORKERS`.
* **Outputs too long** → Set `TRIM_TO_WORDS` or adjust prompt.

---

## Customisation ideas

* **Multiple outputs** → Craft prompt returning JSON, store it in `OUTPUT_COL`, optionally parse later.
* **Guardrails** → Add regex checks or post-process results.
* **Batch prompts** → Add a context prefix if many rows share info.

