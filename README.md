
# CDF Energy AI Hackathon — OilPulse Energy Intelligence System

**Live URL:** https://oilpulse-seven.vercel.app

**AI Tools Used:** Claude (Anthropic) for development, Groq llama-3.3-70b-versatile for in-product AI analyst

Welcome! This is your personal repository for the CDF Energy AI Hackathon. The problem statement is included in this repo — read it carefully before you start.

---

## 📋 Problem Statement
See [`problem_statement.md`](./problem_statement.md) for the full brief.

---

## 🗂️ Repo Structure
```
├── README.md               # This file — live URL and submission checklist
├── PROBLEM_STATEMENT.md    # Full hackathon brief
├── planning/
│   └── PLANNING.md         # Your planning document (fill this out first)
├── src/                    # Your application code goes here
└── docs/
    ├── walkthrough.md      # Link to your 5-minute walkthrough video
    ├── architecture.md     # Your architecture overview and data flow
    ├── kpi_definitions.md  # Definitions and logic for each KPI you built
    └── reflection.md       # What you built, tradeoffs, AI tools used
```

---

## 🚀 Local Development

```bash
# Backend
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Copy `.env.example` to `.env` and fill in your API keys before running locally.

---



## 📝 A Note on Commit History

Your git commit history is part of the evaluation. Here is what a clean history looks like:

- **Commit regularly** — at least once per meaningful chunk of work (e.g. "Add EIA data ingestion", "Build forecasting engine", "Surface Projected Production KPI")
- **Write descriptive messages** — not "fix", "update", or "asdf". A good message tells someone what changed and why
- **Do not squash everything into one commit** at the end — we should be able to follow your progress through the history
- **Do not commit API keys, `.env` files, or `node_modules`** — use `.gitignore`

Think of your commit history as a log of how you think and work, not just a save button.

---
