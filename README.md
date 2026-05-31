# FreakyBits — AI Video Automation Pipeline

Fully automated short-form video pipeline. Generates and uploads 6 AI-powered videos a day to YouTube Shorts and Instagram Reels. No manual work after setup.

[![Pipeline](https://github.com/imsv1301/freakybits/actions/workflows/buzzBits_daily.yml/badge.svg)](https://github.com/imsv1301/freakybits/actions)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![License](https://img.shields.io/badge/License-MIT-green)

---

## How it works

GitHub Actions triggers at 7AM and 7PM IST every day. Each run produces 3 videos:

```
GitHub Actions (cron: 7AM + 7PM IST)
    │
    ▼
pipeline.py
    │
    ├── Gemini 2.5 Flash → viral script + SEO title + hashtags
    ├── Edge TTS (Microsoft) → neural voiceover
    ├── Pexels API → HD portrait stock clips
    │
    ▼
FFmpeg
    ├── 9:16 vertical crop
    ├── dark cinematic filter
    ├── bold white uppercase subtitles (word-by-word)
    └── muted background music mix
    │
    ▼
Upload
    ├── YouTube Shorts (YouTube Data API v3)
    └── Instagram Reels (Meta Graph API)
```

---

## Features

| What | Details |
|------|---------|
| Script generation | Gemini 2.5 Flash with viral hooks, SEO titles, hashtags |
| Voice | Microsoft Edge TTS — Christopher (EN), Madhur (HI) |
| Video | Pexels HD stock API, 1080x1920, 9:16 portrait |
| Subtitles | FFmpeg burns bold uppercase word-by-word captions |
| Niches | Horror, Comedy, AI & Tech, Storytelling |
| Series format | Part 1 / Part 2 cliffhanger per niche for watch-through |
| Bilingual | EN and HI rotate across runs |
| Deduplication | Tracks last 500 topics — never repeats a script |
| Retry logic | Exponential backoff on upload failures |
| Analytics | Every upload logged to JSON |
| Cost | Runs on GitHub Actions free tier (~1,200 mins/month) |

---

## Setup

### What you need

- GitHub account
- Google AI Studio API key (free) — [aistudio.google.com](https://aistudio.google.com)
- Pexels API key (free) — [pexels.com/api](https://www.pexels.com/api)
- YouTube OAuth credentials via Google Cloud Console

### Steps

1. Fork this repo
2. Add these GitHub Secrets (Settings → Secrets → Actions):

| Secret | What it is |
|--------|-----------|
| `GEMINI_API_KEY` | Google AI Studio key |
| `PEXELS_API_KEY` | Pexels API key |
| `YOUTUBE_CLIENT_SECRETS` | OAuth JSON from Google Cloud |
| `YOUTUBE_TOKEN_B64` | Base64-encoded pickle token |
| `INSTAGRAM_TOKEN` | Meta Graph API token (optional) |
| `INSTAGRAM_ACCOUNT_ID` | Instagram account ID (optional) |

3. Enable GitHub Actions. Pipeline runs automatically.

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Output

- 6 videos per day (3 per run, 2 runs)
- ~32 seconds per video
- 1080x1920px, 9:16 vertical
- 4 English + 2 Hindi per day

---

## Tech stack

| Layer | Tool |
|-------|------|
| Script AI | Google Gemini 2.5 Flash |
| Voice | Microsoft Edge TTS (neural) |
| Video | Pexels HD Stock API |
| Assembly | FFmpeg |
| Upload | YouTube Data API v3, Instagram Graph API |
| CI/CD | GitHub Actions |
| Auth | Google OAuth 2.0 |

---

## Project structure

```
freakybits/
├── pipeline.py                   # main automation pipeline
├── requirements.txt
├── tests/
│   └── test_pipeline.py
├── buzzBits_output/              # generated videos (gitignored)
│   ├── analytics.json            # upload history
│   └── used_topics.json          # deduplication store
└── .github/
    └── workflows/
        └── buzzBits_daily.yml    # cron schedule
```

---

## Roadmap

- [ ] Oracle Cloud VM migration (no GitHub Actions minute cap)
- [ ] Gemini Vision clip relevance scoring
- [ ] Google Sheets analytics dashboard
- [ ] Instagram token auto-refresh
- [ ] Per-niche topic model fine-tuning

---

## Built by

**Mohammad Sahil Vahora** — ECE Final Year, Parul University 2026

GitHub: [@imsv1301](https://github.com/imsv1301) | Instagram: [@freaky_bits](https://instagram.com/freaky_bits)
