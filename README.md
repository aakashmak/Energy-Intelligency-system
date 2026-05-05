[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/vvE-nkdH)
# CDF Energy AI Hackathon — OilPulse Energy Intelligence System

**Live URL:** https://oilpulse-seven.vercel.app

**Walkthrough Video:** https://www.loom.com/share/457a45b8dca44a8abbc47dd4b20b54cd

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

## 📦 Submission Checklist

Push to your designated repository before the **5-day deadline**. Your repo state at the deadline is your submission.

- [ ] Live deployment URL added at the top of this README — **mandatory**
- [ ] Completed planning document in `planning/PLANNING.md`
- [ ] Working application in `src/`
- [ ] `docs/walkthrough.md` — walkthrough video link filled in
- [ ] `docs/architecture.md` — architecture overview and data flow filled in
- [ ] `docs/kpi_definitions.md` — all KPIs defined with calculation logic
- [ ] `docs/reflection.md` — reflection filled in
- [ ] Clean commit history — see note below

---

## 🎥 Video Requirements

Your 5-minute walkthrough video is mandatory. It must cover:

- What you built and why
- How your system works end to end
- Your forecasting approach and its assumptions
- KPI definitions and how they support business decisions
- System walkthrough including the year selector in action
- How you used AI and what value it adds
- Key insights and any investment recommendations surfaced by the system

Link your video in `docs/walkthrough.md` before the deadline.

---

## 📝 A Note on Commit History

Your git commit history is part of the evaluation. Here is what a clean history looks like:

- **Commit regularly** — at least once per meaningful chunk of work (e.g. "Add EIA data ingestion", "Build forecasting engine", "Surface Projected Production KPI")
- **Write descriptive messages** — not "fix", "update", or "asdf". A good message tells someone what changed and why
- **Do not squash everything into one commit** at the end — we should be able to follow your progress through the history
- **Do not commit API keys, `.env` files, or `node_modules`** — use `.gitignore`

Think of your commit history as a log of how you think and work, not just a save button.

---
