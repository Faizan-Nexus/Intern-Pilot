"""
Flask Dashboard for Lead Enrichment Workflow
Routes: /, /upload, /api/leads, /api/stats, /export, /n8n-webhook, /enrich
"""

import os
import io
import json
import threading
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file, redirect
from flask_cors import CORS
from dotenv import load_dotenv
import lead_enricher as le


load_dotenv()
app = Flask(__name__)
CORS(app)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

# Global enrichment state
enrichment_status = {
    "running":   False,
    "current":   0,
    "total":     0,
    "last_name": "",
    "done":      False,
    "error":     "",
}

le.init_db()

# ─────────────────────────────
# PAGES
# ─────────────────────────────
@app.route("/")
def index():
    return render_template("dashboard.html")

# ─────────────────────────────
# CSV UPLOAD
# ─────────────────────────────
@app.route("/upload", methods=["POST"])
def upload_csv():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400

    f = request.files["file"]
    if not f.filename.endswith(".csv"):
        return jsonify({"success": False, "error": "Only CSV files accepted"}), 400

    try:
        df      = pd.read_csv(io.BytesIO(f.read()))
        count   = le.insert_leads_from_df(df)
        return jsonify({"success": True, "inserted": count, "message": f"Inserted {count} leads"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ─────────────────────────────
# TRIGGER ENRICHMENT
# ─────────────────────────────
@app.route("/enrich", methods=["POST"])
def enrich():
    global enrichment_status
    if enrichment_status["running"]:
        return jsonify({"success": False, "error": "Enrichment already running"}), 409

    data = request.get_json(silent=True) or {}
    cv_text = data.get("cv_text", "")

    def run(cv_text):
        global enrichment_status
        enrichment_status["running"] = True
        enrichment_status["done"]    = False
        enrichment_status["error"]   = ""
        enrichment_status["current"] = 0

        def progress(cur, total, name):
            enrichment_status["current"]   = cur
            enrichment_status["total"]     = total
            enrichment_status["last_name"] = name

        try:
            total = le.enrich_all(progress_callback=progress, cv_text=cv_text)
            enrichment_status["done"] = True
        except Exception as e:
            enrichment_status["error"] = str(e)
        finally:
            enrichment_status["running"] = False

    threading.Thread(target=run, args=(cv_text,), daemon=True).start()
    return jsonify({"success": True, "message": "Enrichment started"})

@app.route("/api/enrichment-status")
def enrichment_status_api():
    return jsonify(enrichment_status)

# ─────────────────────────────
# DATA APIs
# ─────────────────────────────
@app.route("/api/leads")
def api_leads():
    leads = le.get_all_leads()
    return jsonify(leads)

@app.route("/api/stats")
def api_stats():
    stats = le.get_stats()
    return jsonify(stats)

@app.route("/api/clear", methods=["POST"])
def api_clear():
    le.clear_all_leads()
    return jsonify({"success": True, "message": "All leads cleared"})

# ─────────────────────────────
# CSV EXPORT
# ─────────────────────────────
@app.route("/export")
def export():
    path = le.export_enriched_csv("internships_ranked.csv")
    if not path:
        return jsonify({"error": "No leads to export"}), 404
    return send_file(
        path, as_attachment=True,
        download_name="internships_ranked.csv",
        mimetype="text/csv",
    )

# ─────────────────────────────
# N8N WEBHOOK
# ─────────────────────────────
@app.route("/n8n-webhook", methods=["POST"])
def n8n_webhook():
    """
    n8n sends lead data here.
    Accepts JSON: { "leads": [...] } or a single lead dict.
    """
    data = request.get_json(silent=True) or {}

    if "leads" in data:
        df    = pd.DataFrame(data["leads"])
        count = le.insert_leads_from_df(df)
        return jsonify({"success": True, "inserted": count})

    elif all(k in data for k in ["title", "company"]):
        df    = pd.DataFrame([data])
        count = le.insert_leads_from_df(df)
        return jsonify({"success": True, "inserted": count})

    stats = le.get_stats()
    return jsonify({"success": True, "stats": stats})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)

