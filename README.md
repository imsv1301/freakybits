# BuzzBits — Fully Automated Daily Video Pipeline
## 12 cinematic AI videos posted daily to YouTube + Instagram. Zero manual work.

---

## What Happens Every Day (Automatically)

| Time (IST) | Action |
|-----------|--------|
| 7:00 AM   | 3 videos generated + uploaded |
| 12:00 PM  | 3 videos generated + uploaded |
| 6:00 PM   | 3 videos generated + uploaded |
| 10:00 PM  | 3 videos generated + uploaded |
| **Total** | **12 videos/day, 84/week, 360/month** |

Each video is:
- **12-16 seconds** of cinematic Veo 3.1 footage
- Niche auto-rotates: Horror Facts 👻 / Comedy Facts 😂 / AI & Tech 🤖
- AI voiceover matching the script
- Platform-specific captions with trending hashtags
- Auto-uploaded to YouTube + Instagram

---

## One-Time Setup (Do This Once)

### 1. Get Free Gemini API Key
1. Go to **https://aistudio.google.com**
2. Sign in with your Google account
3. Click **"Get API Key"** → **"Create API key in new project"**
4. Copy the key (starts with `AIza...`)

> Free quota: 1000 text requests/day + Veo video generation via your Gemini Pro credits

---

### 2. Set Up YouTube API

**A. Enable the API:**
1. Go to **https://console.cloud.google.com**
2. Create a new project (name it `buzzBits`)
3. Go to **APIs & Services** → **Library**
4. Search **"YouTube Data API v3"** → Click → **Enable**

**B. Create OAuth Credentials:**
1. Go to **APIs & Services** → **Credentials**
2. Click **"+ Create Credentials"** → **"OAuth 2.0 Client ID"**
3. Application type: **Desktop app**
4. Name: `buzzBits`
5. Click **Create** → **Download JSON**
6. This is your `youtube_secrets.json` file — keep it safe!

**C. First-Time Authentication (run once on your PC):**
```bash
# Install dependencies
pip install -r requirements.txt

# Set your Gemini key temporarily
set GEMINI_API_KEY=your_key_here   # Windows
export GEMINI_API_KEY=your_key_here  # Mac/Linux

# Run pipeline once locally — browser will open for Google login
python pipeline.py
```
- Browser opens → Sign in with your YouTube channel Google account → Allow
- This creates `buzzBits_output/yt_token.pickle`

**D. Convert token to base64 for GitHub:**
```powershell
# Windows PowerShell:
$bytes = [System.IO.File]::ReadAllBytes("buzzBits_output\yt_token.pickle")
[System.Convert]::ToBase64String($bytes) | Set-Clipboard
# Token is now in your clipboard
```
```bash
# Mac/Linux:
base64 -w 0 buzzBits_output/yt_token.pickle | pbcopy
```

---

### 3. Set Up Instagram API

1. You need: **Facebook Business Account** + **Instagram Professional account**
2. Go to **https://developers.facebook.com** → **My Apps** → **Create App**
3. Select **Business** type → Continue
4. Add product: **Instagram Graph API**
5. Go to **Tools** → **Graph API Explorer**
6. Generate a **Page Access Token** with these permissions:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
7. Convert to **long-lived token** (valid 60 days):
   ```
   GET https://graph.facebook.com/v18.0/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id=YOUR_APP_ID
     &client_secret=YOUR_APP_SECRET
     &fb_exchange_token=YOUR_SHORT_TOKEN
   ```
8. Find your **Instagram Business Account ID**:
   - Go to Meta Business Suite → Settings → Instagram accounts → copy the numeric ID

---

### 4. Create GitHub Repository

1. Go to **https://github.com/new**
2. Name: `buzzBits` | Type: **Private** | Click **Create repository**
3. Upload all these files to the repo:
   ```
   buzzBits/
   ├── pipeline.py
   ├── requirements.txt
   ├── README.md
   └── .github/
       └── workflows/
           └── buzzBits_daily.yml
   ```

---

### 5. Add GitHub Secrets

Go to your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add each of these:

| Secret Name | Where to Get It | Example |
|-------------|----------------|---------|
| `GEMINI_API_KEY` | aistudio.google.com | `AIzaSy...` |
| `YOUTUBE_CLIENT_SECRETS` | Contents of `youtube_secrets.json` (paste entire JSON) | `{"installed":{"client_id":...}}` |
| `YOUTUBE_TOKEN_B64` | Base64 output from Step 2D | `gASV...` |
| `INSTAGRAM_TOKEN` | From Step 3 | `EAABwz...` |
| `INSTAGRAM_ACCOUNT_ID` | From Step 3 | `17841...` |

---

### 6. Enable GitHub Actions

1. Go to your repo → **Actions** tab
2. Click **"I understand my workflows, go ahead and enable them"**
3. Done! Pipeline will now run automatically at scheduled times.

---

## Test It Manually

1. Go to **Actions** tab in your GitHub repo
2. Click **"BuzzBits Daily Pipeline"** in the left sidebar
3. Click **"Run workflow"** → **"Run workflow"**
4. Watch it run (takes ~45-60 minutes for 3 videos)
5. Check the **Artifacts** section to download generated videos

---

## Customise Your Content

Edit `pipeline.py` to change:

```python
# Change upload times (UTC):
# 7AM IST  = 01:30 UTC
# 12PM IST = 06:30 UTC
# 6PM IST  = 12:30 UTC
# 10PM IST = 16:30 UTC

# Change niches:
NICHES = [
    {"name": "horror_facts", ...},
    {"name": "comedy_facts", ...},
    {"name": "ai_tech", ...},
    # Add more niches here!
]

# Change videos per run:
VIDEOS_PER_RUN = 3  # 3 × 4 runs = 12/day
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `GEMINI_API_KEY not set` | Add the secret in GitHub Settings |
| `Veo timed out` | Retry — Veo can be slow during peak hours |
| `YouTube token expired` | Re-run locally to refresh, update `YOUTUBE_TOKEN_B64` secret |
| `Instagram container error` | Check your access token hasn't expired (renew every 60 days) |
| `FFmpeg not found` | GitHub Actions installs it automatically — only needed locally |
| `Video under 12 seconds` | Veo scene failed — check quota and retry |

---

## Free Quota Summary

| Service | Free Limit | Your Daily Need |
|---------|-----------|----------------|
| Gemini 2.5 Flash | 1000 req/day | ~36 req/day (3 req × 12 videos) |
| Veo 3.1 Fast | Gemini Pro credits | 24 scenes/day (2 × 12 videos) |
| gTTS | Unlimited | 12 req/day |
| YouTube Data API | 10,000 units/day | ~19,200 units/day ⚠️ |
| Instagram Graph API | Unlimited | 12 req/day |
| GitHub Actions | 2,000 min/month | ~1,440 min/month |

> ⚠️ **YouTube API Note:** 1 upload = ~1,600 units. 12 uploads = 19,200 units/day which exceeds
> the free 10,000 unit limit. You'll need to apply for a **YouTube API quota increase** 
> (free, takes 1-3 days): https://console.cloud.google.com → YouTube Data API → Quotas → Request increase
