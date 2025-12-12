# Insurance Quote + Analytics Demo

Simple Flask app demonstrating two use cases:

- Real-Time Insurance Quote (UI + mock ML/ODS adjustment)
- Annual Pricing Analytics (mock ODS/ML base rates)

Files:

- `app.py` — main Flask application with helper functions and routes
- `templates/base.html` — common layout
- `templates/quote.html` — quote UI
- `templates/analytics.html` — analytics UI
- `requirements.txt` — required Python packages

Run locally:

1. Create a virtualenv and install requirements

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Start the app

```bash
export FLASK_APP=app.py
flask run
```

Open http://127.0.0.1:5000/quote or /analytics

Notes on code structure:

- Helper functions (e.g., `get_plan_details`, `get_ml_adjustment`) are intentionally stubbed/mocked and include docstrings explaining future responsibilities to query OLTP/EDA systems and ODS/ML outputs.
- No DB or external API calls are made in this demo.
