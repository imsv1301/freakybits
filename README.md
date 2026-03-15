# 🎬 FreakyBits — AI Video Automation Pipeline

> Fully automated short-form video pipeline that generates and uploads 6 AI-powered videos/day to YouTube Shorts and Instagram Reels — zero manual work.

[![Pipeline](https://github.com/imsv1301/freakybits/actions/workflows/buzzBits_daily.yml/badge.svg)](https://github.com/imsv1301/freakybits/actions)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions (Free)                     │
│                  7AM + 7PM IST — Daily Cron                 │
└──────────────────────────┬──────────────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │   pipeline.py (Main)    │
              └────────────┬────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼──────┐  ┌────────▼───────┐  ┌──────▼───────┐
│ Step 1       │  │ Step 2         │  │ Step 3        │
│ Gemini Flash │  │ Edge TTS       │  │ Pexels API    │
│ Script+Captions│ │ Neural Voice   │  │ HD Stock Video│
│ (Free API)   │  │ (Free)         │  │ (Free API)    │
└───────┬──────┘  └────────┬───────┘  └──────┬───────┘
        │                  │                  │
        └──────────────────▼──────────────────┘
                           │
              ┌────────────▼────────────┐
              │   Step 4: FFmpeg        │
              │ • 9:16 vertical crop    │
              │ • Dark cinematic filter │
              │ • Bold subtitle overlay │
              │ • Muted song mix        │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   Step 5: Upload        │
              │ • YouTube Shorts        │
              │ • Instagram Reels       │
              └─────────────────────────┘
```

---

## ✨ Features

| Feature | Details |
|---------|---------|
| **Auto Script** | Gemini 2.5 Flash generates viral scripts with SEO titles + hashtags |
| **Neural Voice** | Edge TTS (Microsoft) — Christopher (EN) / Madhur (HI) |
| **HD Video** | Pexels API — portrait 9:16 cinematic clips |
| **Bold Subtitles** | FFmpeg burns large white uppercase subtitles word-by-word |
| **Bilingual** | EN → HI → EN pattern per run |
| **4 Niches** | Horror 👻 Comedy 😂 AI&Tech 🤖 Storytelling 📖 |
| **Part Series** | Part 1 / Part 2 cliffhanger format for engagement |
| **Topic Dedup** | Tracks last 500 topics — never repeats |
| **Retry Logic** | Exponential backoff on upload failures |
| **Analytics** | Logs every upload to JSON for tracking |
| **Free Forever** | Runs on GitHub Actions free tier (2x daily = ~1,200 mins/month) |

---

## 🚀 Quick Start

### Prerequisites
- GitHub account
- Google AI Studio API key (free) — [aistudio.google.com](https://aistudio.google.com)
- Pexels API key (free) — [pexels.com/api](https://www.pexels.com/api)
- YouTube OAuth credentials — Google Cloud Console

### Setup
1. Fork this repo
2. Add GitHub Secrets (Settings → Secrets → Actions):

| Secret | Description |
|--------|-------------|
| `GEMINI_API_KEY` | Google AI Studio key |
| `PEXELS_API_KEY` | Pexels API key |
| `YOUTUBE_CLIENT_SECRETS` | OAuth JSON from Google Cloud |
| `YOUTUBE_TOKEN_B64` | Base64-encoded pickle token |
| `INSTAGRAM_TOKEN` | Meta Graph API token (optional) |
| `INSTAGRAM_ACCOUNT_ID` | Instagram account ID (optional) |

3. Enable GitHub Actions — pipeline runs automatically at 7AM + 7PM IST

---

## 🧪 Running Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## 📊 Output Stats

- **6 videos/day** (3 per run × 2 runs)
- **~32 seconds** per video
- **1080×1920px** (9:16 vertical)
- **Bilingual** — 4 EN + 2 HI per day

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Script AI | Google Gemini 2.5 Flash |
| Voice AI | Microsoft Edge TTS (Neural) |
| Video | Pexels HD Stock API |
| Assembly | FFmpeg |
| Upload | YouTube Data API v3, Instagram Graph API |
| CI/CD | GitHub Actions |
| Auth | Google OAuth 2.0 |

---

## 📁 Project Structure

```
freakybits/
├── pipeline.py              # Main automation pipeline
├── requirements.txt         # Python dependencies
├── tests/
│   └── test_pipeline.py     # Unit tests (pytest)
├── buzzBits_output/         # Generated videos (gitignored)
│   ├── analytics.json       # Upload history
│   └── used_topics.json     # Topic deduplication store
└── .github/
    └── workflows/
        └── buzzBits_daily.yml  # Cron schedule
```

---

## 🔮 Roadmap

- [ ] Oracle Cloud VM migration (unlimited runs)
- [ ] Gemini Vision clip relevance scoring
- [ ] Google Sheets analytics dashboard
- [ ] Instagram token integration
- [ ] Fine-tuned topic model per niche

---

## 👨‍💻 Built By

**Mohammad Sahil Vahora** — ECE Final Year, Parul University 2026
- GitHub: [@imsv1301](https://github.com/imsv1301)
- Instagram: [@freaky_bits](https://instagram.com/freaky_bits)

---

*This project demonstrates end-to-end AI pipeline engineering — from LLM prompting to cloud deployment — built entirely for free using open APIs and GitHub Actions.*
