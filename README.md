<<<<<<< HEAD
# Automated Lead Enrichment Workflow

> **Python + n8n + Groq AI** · Free APIs · Real-Time Dashboard · No paid subscriptions

Reads leads from CSV → validates emails → scores with AI → shows enriched data in a live dashboard → integrates with n8n automation.

---

##  Features

| Feature | Description |
|---|---|
|  **CSV Upload** | Drag & drop or browse to upload lead files |
|  **Email Validation** | Format check + DNS MX record verification (no API needed) |
|  **AI Enrichment** | Groq Llama 3.3 70B scores each lead 1-10, detects industry, company size, recommends action |
|  **Live Dashboard** | Bar chart by industry, donut chart by score, sortable + filterable table |
|  **Export** | Download enriched CSV with all new columns |
|  **n8n Webhook** | Push leads or stats from any n8n workflow |
|  **Auto-schedule** | n8n runs enrichment on schedule (e.g. every hour) |

---

##  Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. API keys are already set in `.env`
Your Groq key is already configured. Optionally add Hunter.io key for email finding.

### 3. Run the dashboard
```bash
python app.py
```
Open: **http://localhost:5001**

### 4. Test with sample data
1. Click **Upload CSV** → select `sample_leads.csv`
2. Click **Start AI Enrichment**
3. Watch the progress bar
4. See results in the table!

---

## Project Structure

```
Auto-Email/
├── app.py                ← Flask dashboard + API endpoints
├── lead_enricher.py      ← Core enrichment engine
├── sample_leads.csv      ← 10 test leads
├── n8n_workflow.json     ← Import this into n8n
├── .env                  ← API keys
├── requirements.txt
├── leads.db              ← SQLite DB (auto-created)
├── enriched_leads.csv    ← Export output
└── templates/
    └── dashboard.html    ← Full web UI
```

---

##  n8n Integration

### Install n8n (free, local, no account needed)
```bash
npx n8n
```
Opens at: **http://localhost:5678**

### Import the workflow
1. Open n8n → **Workflows** → **Import**
2. Select `n8n_workflow.json`
3. Click **Execute Workflow** to test

### What the n8n workflow does
```
[Every Hour] → [GET /api/stats] → [IF hot_leads > 0]
                                        ↓ YES          ↓ NO
                              [POST /enrich]   [POST /n8n-webhook]
```

---

##  API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET  | `/` | Dashboard UI |
| POST | `/upload` | Upload CSV file |
| POST | `/enrich` | Start AI enrichment (async) |
| GET  | `/api/enrichment-status` | Live progress polling |
| GET  | `/api/leads` | All leads as JSON |
| GET  | `/api/stats` | Summary statistics |
| GET  | `/export` | Download enriched CSV |
| POST | `/n8n-webhook` | Receive leads/triggers from n8n |
| POST | `/api/clear` | Clear all leads |

---

##  Enriched CSV Columns

Original columns + these new ones:

| New Column | Example |
|---|---|
| `email_valid` | 1 / 0 |
| `email_status` | valid / invalid_format / no_mx_record |
| `industry` | Technology / Finance / Healthcare… |
| `company_size` | Startup / Small / Medium / Large / Enterprise |
| `company_summary` | "A Pakistan-based software company…" |
| `lead_score` | 8 |
| `score_reason` | "Decision maker at established tech company" |
| `recommended_action` | "Schedule intro call" |

---

##  Free APIs Used

| API | Purpose | Limit |
|---|---|---|
| **Groq (Llama 3.3 70B)** | AI scoring + company research | 14,400 req/day free |
| **DNS MX Check** | Email validation | Unlimited |
| **Hunter.io** *(optional)* | Email finder | 25/month free |

---

*Built with ❤️ · Python + Flask + Groq + n8n*
=======
# Intern-Pilot
AI‑powered internship matcher with n8n workflow automation and Flask dashboard.
>>>>>>> 69a8281dacfc409ca95adf8fd9b334e2cbb74623
