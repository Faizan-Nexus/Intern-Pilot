"""
Internship Enrichment Engine
Reads CSV → enriches against User CV with AI → saves to SQLite
"""

import os
import json
import time
import sqlite3
import logging
import pandas as pd
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DB_PATH     = "leads.db"
GROQ_KEY    = os.environ.get("GROQ_API_KEY", "")
groq_client = Groq(api_key=GROQ_KEY) if GROQ_KEY else None

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DROP TABLE IF EXISTS leads") # Reset DB on init
    conn.execute("""
        CREATE TABLE leads (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            title           TEXT,
            company         TEXT,
            link            TEXT,
            is_paid         TEXT DEFAULT 'Unpaid',
            match_score     INTEGER DEFAULT 0,
            match_reason    TEXT DEFAULT '',
            enriched        INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now')),
            enriched_at     TEXT
        )
    """)
    conn.commit()
    conn.close()

def insert_leads_from_df(df: pd.DataFrame) -> int:
    conn = sqlite3.connect(DB_PATH)
    inserted = 0
    for _, row in df.iterrows():
        title = str(row.get("title", "") or row.get("internship_title", "") or row.get("Job Title", "")).strip()
        company = str(row.get("company", "") or row.get("Company Name", "")).strip()
        link = str(row.get("link", "") or row.get("url", "") or row.get("Apply Link", "")).strip()
        
        if not title and not company:
            continue
            
        conn.execute("""
            INSERT INTO leads (title, company, link) VALUES (?,?,?)
        """, (title, company, link))
        inserted += 1
    conn.commit()
    conn.close()
    return inserted

def get_unenriched_leads():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM leads WHERE enriched = 0").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_lead(lead_id: int, data: dict):
    conn = sqlite3.connect(DB_PATH)
    data["enriched"]    = 1
    data["enriched_at"] = "datetime('now')"
    sets  = ", ".join(f"{k} = ?" for k in data if k != "enriched_at")
    sets += ", enriched_at = datetime('now')"
    vals  = [v for k, v in data.items() if k != "enriched_at"]
    vals.append(lead_id)
    conn.execute(f"UPDATE leads SET {sets} WHERE id = ?", vals)
    conn.commit()
    conn.close()

def get_all_leads():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM leads ORDER BY match_score DESC, created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats():
    conn = sqlite3.connect(DB_PATH)
    stats = {}
    stats["total"]    = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    stats["enriched"] = conn.execute("SELECT COUNT(*) FROM leads WHERE enriched=1").fetchone()[0]
    stats["avg_score"]= conn.execute("SELECT AVG(match_score) FROM leads WHERE enriched=1").fetchone()[0] or 0
    stats["hot_leads"]= conn.execute("SELECT COUNT(*) FROM leads WHERE match_score>=80").fetchone()[0]
    
    stats["by_industry"] = dict(conn.execute(
        "SELECT coalesce(is_paid, 'Unpaid'), COUNT(*) FROM leads WHERE enriched=1 GROUP BY is_paid"
    ).fetchall())
    stats["score_dist"] = dict(conn.execute(
        "SELECT CASE WHEN match_score>=80 THEN 'High Match (80-100)' "
        "WHEN match_score>=50 THEN 'Medium Match (50-79)' ELSE 'Low Match (0-49)' END as cat, "
        "COUNT(*) FROM leads WHERE enriched=1 GROUP BY cat"
    ).fetchall())
    conn.close()
    stats["avg_score"] = round(stats["avg_score"], 1) if stats["avg_score"] else 0
    return stats

def clear_all_leads():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM leads")
    conn.commit()
    conn.close()

# ─────────────────────────────────────────────
# GROQ AI ENRICHMENT
# ─────────────────────────────────────────────
ENRICH_SYSTEM = """You are an expert Technical Recruiter AI matching a candidate to an internship.
Given the candidate's CV and the internship details, return a JSON object evaluating the match.
Return EXACTLY these fields in the JSON:
{
  "match_score": integer 1-100 (100 = perfect skill alignment & timeline match based on graduation date),
  "match_reason": "1-2 short sentences summarizing why this is a good or bad fit relative to their CV skills",
  "is_paid": "one of: Paid or Unpaid"
}
Return ONLY valid JSON, no other text."""

def ai_enrich_lead(lead: dict, cv_text: str) -> dict:
    if not groq_client: return {}

    prompt = f"""Candidate CV:
{cv_text}

---
Internship Details:
- Title: {lead.get('title','Unknown')}
- Company: {lead.get('company','Unknown')}
- Link: {lead.get('link','Unknown')}

Evaluate this internship against the CV."""

    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": ENRICH_SYSTEM},
                {"role": "user",   "content": prompt[:6000]}, # Trim CV if extremely long to avoid token limits
            ],
            temperature=0.2,
            max_tokens=400,
        )
        raw = resp.choices[0].message.content.strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        return json.loads(raw[start:end]) if start != -1 else {}
    except Exception as e:
        logging.warning(f"Groq enrichment failed for lead {lead.get('id')}: {e}")
        return {}

# ─────────────────────────────────────────────
# MAIN ENRICHMENT PIPELINE
# ─────────────────────────────────────────────
def enrich_all(progress_callback=None, cv_text=""):
    leads = get_unenriched_leads()
    total = len(leads)
    if total == 0: return 0

    for idx, lead in enumerate(leads, 1):
        lead_name = f"{lead.get('title','')} at {lead.get('company','')}"
        
        update_data = {}
        ai_data = ai_enrich_lead(lead, cv_text)
        if ai_data:
            update_data["match_score"]  = int(ai_data.get("match_score", 0))
            update_data["match_reason"] = ai_data.get("match_reason", "")
            is_paid_val = ai_data.get("is_paid", "Unpaid")
            if is_paid_val == "Unknown": is_paid_val = "Unpaid"
            update_data["is_paid"]      = is_paid_val

        update_lead(lead["id"], update_data)

        if progress_callback:
            progress_callback(idx, total, lead_name)

        time.sleep(0.3)

    return total

def export_enriched_csv(output_path: str = "internships_ranked.csv"):
    leads = get_all_leads()
    if not leads: return None
    pd.DataFrame(leads).to_csv(output_path, index=False)
    return output_path
