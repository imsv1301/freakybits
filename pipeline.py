"""
FreakyBits Auto Pipeline
========================
Stack: Gemini 2.5 Flash (script) + Pexels (free HD video) + Edge TTS (human voice) + FFmpeg
"""

import os, sys, json, time, pickle, datetime, subprocess, requests, asyncio
from pathlib import Path
from google import genai

# ── CONFIG ─────────────────────────────────────────────────────────
GEMINI_API_KEY        = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY        = os.environ.get("PEXELS_API_KEY", "")
YOUTUBE_SECRETS_FILE  = "youtube_secrets.json"
INSTAGRAM_TOKEN       = os.environ.get("INSTAGRAM_TOKEN", "")
INSTAGRAM_ACCOUNT_ID  = os.environ.get("INSTAGRAM_ACCOUNT_ID", "")
VIDEOS_PER_RUN        = 3
TARGET_DURATION_SEC   = 32

# ── LANGUAGE CONFIG ────────────────────────────────────────────────
LANG_PATTERN = ["en", "hi", "en"]
LANG_CONFIG = {
    "en": {
        "label":        "English",
        "edge_voice":   "en-US-ChristopherNeural",   # deep male voice
        "follow_part2": "Follow for Part 2!",
    },
    "hi": {
        "label":        "Hindi",
        "edge_voice":   "hi-IN-MadhurNeural",        # natural Hindi male voice
        "follow_part2": "Part 2 ke liye follow karo!",
    },
}

# ── PART SERIES CONFIG ─────────────────────────────────────────────
PART_SERIES_SCHEDULE = {1: 1, 6: 2, 12: 1, 16: 2}

# ── NICHES ─────────────────────────────────────────────────────────
NICHES = [
    {
        "name":  "horror_facts",
        "label": "Horror Facts",
        "tone":  "spine-chilling and mysterious, building dread with each fact",
        "emoji": "👻",
        "pexels_queries": ["dark abandoned building", "foggy forest night", "cemetery moonlight", "dark shadows horror"],
    },
    {
        "name":  "comedy_facts",
        "label": "Comedy Facts",
        "tone":  "hilarious and shocking, punchline energy on every fact",
        "emoji": "😂",
        "pexels_queries": ["colorful confetti fun", "funny animals", "people laughing outdoors", "bright celebration"],
    },
    {
        "name":  "ai_tech",
        "label": "AI & Tech Facts",
        "tone":  "mind-blowing and futuristic, tech feels like sci-fi",
        "emoji": "🤖",
        "pexels_queries": ["futuristic technology neon city", "digital data visualization", "robot artificial intelligence", "cyberpunk night cityscape"],
    },
    {
        "name":  "storytelling",
        "label": "Storytelling",
        "tone":  "emotionally gripping, narrative-driven, builds tension",
        "emoji": "📖",
        "pexels_queries": ["epic cinematic landscape", "dramatic storm clouds", "adventure mountains sunset", "ancient ruins mysterious"],
    },
]

# ── TRENDING SONGS (royalty-free, muted) ──────────────────────────
TRENDING_SONGS_FREE = [
    {"niche": "horror_facts",  "url": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3"},
    {"niche": "horror_facts",  "url": "https://cdn.pixabay.com/download/audio/2021/09/06/audio_6ded321929.mp3"},
    {"niche": "comedy_facts",  "url": "https://cdn.pixabay.com/download/audio/2022/10/25/audio_946b736e00.mp3"},
    {"niche": "comedy_facts",  "url": "https://cdn.pixabay.com/download/audio/2022/01/20/audio_d0ee71a7e6.mp3"},
    {"niche": "ai_tech",       "url": "https://cdn.pixabay.com/download/audio/2022/08/02/audio_2dde668d05.mp3"},
    {"niche": "ai_tech",       "url": "https://cdn.pixabay.com/download/audio/2021/11/13/audio_cb31e6deb5.mp3"},
    {"niche": "storytelling",  "url": "https://cdn.pixabay.com/download/audio/2022/11/22/audio_febc508520.mp3"},
    {"niche": "storytelling",  "url": "https://cdn.pixabay.com/download/audio/2023/01/04/audio_9b6d7c7b30.mp3"},
]

OUT              = Path("buzzBits_output")
OUT.mkdir(exist_ok=True)
PART1_TOPIC_FILE = OUT / "part1_topic.json"

client = genai.Client(api_key=GEMINI_API_KEY)


# ══════════════════════════════════════════════════════════════════
#  SELECTORS
# ══════════════════════════════════════════════════════════════════
def pick_niche(video_index):
    hour = datetime.datetime.utcnow().hour
    return NICHES[(hour // 6 + video_index) % len(NICHES)]

def pick_language(video_index):
    code = LANG_PATTERN[video_index % len(LANG_PATTERN)]
    return {"code": code, **LANG_CONFIG[code]}

def get_current_part(video_index):
    if video_index != 2:
        return None
    hour = datetime.datetime.utcnow().hour
    for h in sorted(PART_SERIES_SCHEDULE):
        if hour <= h + 1:
            return PART_SERIES_SCHEDULE[h]
    return PART_SERIES_SCHEDULE[16]

def save_part1_topic(topic, niche_name, lang_code):
    data = {"topic": topic, "niche": niche_name, "lang": lang_code,
            "saved_at": datetime.datetime.utcnow().isoformat()}
    with open(PART1_TOPIC_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   💾 Part 1 saved: '{topic}'")

def load_part1_topic():
    if not PART1_TOPIC_FILE.exists():
        return None
    try:
        with open(PART1_TOPIC_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None


# ══════════════════════════════════════════════════════════════════
#  STEP 1 — Generate Script + Captions
# ══════════════════════════════════════════════════════════════════
def generate_content(niche, video_index, lang, part=None, part1_data=None):
    lang_label = lang["label"]
    lang_code  = lang["code"]
    print(f"\n🤖 [{niche['label']}] [{lang_label}]" + (f" [Part {part}]" if part else ""))

    today = datetime.datetime.utcnow().strftime("%B %d, %Y")

    if lang_code == "hi":
        lang_instruction = "LANGUAGE: Write EVERYTHING in Hindi (Devanagari). Hashtags stay English."
    else:
        lang_instruction = "LANGUAGE: English throughout."

    part_instruction = ""
    if part == 1:
        part_instruction = f'PART 1 of 2: End narration with exactly: "{lang["follow_part2"]}". Title ends with (Part 1). End on cliffhanger.'
    elif part == 2:
        prev = part1_data.get("topic", "previous topic") if part1_data else "previous topic"
        part_instruction = f'PART 2 of 2: Continue from "{prev}". Title ends with (Part 2). Satisfying conclusion.'

    prompt = f"""You are a viral content creator for FreakyBits — YouTube/Instagram shorts channel.
Niche: {niche['label']} | Tone: {niche['tone']} | Date: {today}
{lang_instruction}
{part_instruction}

Create a 32-second short video script with exactly 4 punchy facts/beats.

Reply ONLY in valid JSON (no markdown):
{{
  "topic": "specific topic",
  "language": "{lang_code}",
  "part": {part if part else "null"},
  "youtube_title": "viral title under 60 chars",
  "youtube_description": "3 punchy sentences about the topic.\\n\\nSubscribe for daily {niche['label']} {niche['emoji']}!\\n\\n",
  "youtube_viral_caption": "hook ≤10 words with emoji",
  "youtube_trending_tags": "#Shorts #Viral #FreakyBits #{niche['name']} #Facts #YouTubeShorts #trending #fyp #shortsvideo #reels #viralvideo #factsinyourface #mindblown #didyouknow #amazingfacts",
  "youtube_tags": ["FreakyBits","Shorts","Viral","Facts","{niche['name']}","trending","fyp","shortsvideo","mindblown","amazingfacts"],
  "instagram_caption": "punchy IG caption ≤150 chars with emojis",
  "instagram_viral_caption": "Reels hook ≤12 words 2-3 emojis",
  "instagram_trending_tags": "#reels #viral #freakybits #shorts #fyp #trending #facts #explore #reelsinstagram #reelsviral #instagram #viralreels #explorepage #shortsvideo #factsoflife #mindblown #amazingfacts #didyouknow #trending2024 #foryou",
  "trending_yt_song": "popular song name - artist",
  "trending_ig_song": "popular song name - artist",
  "narration": "80-100 words. PUNCHY. Hook in first 3 words. 4 facts/beats. No filler. Ends with CTA.",
  "pexels_queries": ["cinematic query matching fact 1", "cinematic query matching fact 2", "cinematic query matching fact 3", "cinematic query matching fact 4"]
}}"""

    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    raw = response.text.strip().replace("```json","").replace("```","").strip()
    start = raw.find("{"); end = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]
    data = json.loads(raw)

    data["youtube_description_final"] = (
        f"{data['youtube_description']}\n{'─'*40}\n"
        f"⚡ {data['youtube_viral_caption']}\n{'─'*40}\n\n"
        f"{data['youtube_trending_tags']}"
    )
    data["instagram_caption_final"] = (
        f"{data['instagram_viral_caption']}\n\n"
        f"{data['instagram_caption']}\n\n"
        f"{data['instagram_trending_tags']}"
    )

    print(f"   ✅ Topic : {data['topic']}")
    print(f"   ✅ Title : {data['youtube_title']}")
    return data


# ══════════════════════════════════════════════════════════════════
#  STEP 2 — Edge TTS Voiceover (human neural voice)
# ══════════════════════════════════════════════════════════════════
def generate_voiceover(content, video_idx, lang):
    print(f"   🎙️  Edge TTS [{lang['label']}] — {lang['edge_voice']}...")
    audio_path = OUT / f"voice_{video_idx:02d}.mp3"

    async def _tts():
        import edge_tts
        communicate = edge_tts.Communicate(
            text=content["narration"],
            voice=lang["edge_voice"],
            rate="+5%",    # slight speed up for energy
            volume="+10%"  # slightly louder
        )
        await communicate.save(str(audio_path))

    try:
        asyncio.run(_tts())
        size_kb = audio_path.stat().st_size // 1024
        print(f"   ✅ {audio_path.name} ({size_kb}KB)")
    except Exception as e:
        print(f"   ⚠️  Edge TTS failed: {e} — falling back to gTTS")
        from gtts import gTTS
        gTTS(text=content["narration"], lang=lang["code"], slow=False).save(str(audio_path))
        print(f"   ✅ gTTS fallback: {audio_path.name}")

    return audio_path


# ══════════════════════════════════════════════════════════════════
#  STEP 3 — Trending Song (muted, for algorithm)
# ══════════════════════════════════════════════════════════════════
def get_trending_song(niche_name, video_idx):
    candidates = [s for s in TRENDING_SONGS_FREE if s["niche"] == niche_name] or TRENDING_SONGS_FREE
    song = candidates[video_idx % len(candidates)]
    song_path = OUT / f"song_{video_idx:02d}.mp3"
    try:
        r = requests.get(song["url"], timeout=30, stream=True)
        r.raise_for_status()
        with open(song_path, "wb") as f:
            for chunk in r.iter_content(8192): f.write(chunk)
        print(f"   ✅ Song downloaded ({song_path.stat().st_size//1024}KB)")
        return song_path
    except Exception as e:
        print(f"   ⚠️  Song failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
#  STEP 4 — Pexels HD Stock Videos
# ══════════════════════════════════════════════════════════════════
def fetch_pexels_clip(query, video_idx, clip_idx):
    clip_path = OUT / f"clip_{video_idx:02d}_{clip_idx:02d}.mp4"
    print(f"      🔍 Pexels: '{query}'")

    try:
        headers = {"Authorization": PEXELS_API_KEY}
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params={"query": query, "per_page": 15, "orientation": "landscape"},
            timeout=20
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])
        if not videos:
            # Try broader fallback query
            niche_fallback = query.split()[0]
            resp2 = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params={"query": niche_fallback, "per_page": 15, "orientation": "landscape"},
                timeout=20
            )
            videos = resp2.json().get("videos", [])

        if not videos:
            raise ValueError(f"No Pexels results for '{query}'")

        # Pick a video (cycle through results)
        video = videos[clip_idx % len(videos)]

        # Get best file: prefer HD (720p), avoid 4K (too large)
        files = video.get("video_files", [])
        # Sort by width, prefer 1280 or 1920
        hd_files = sorted(
            [f for f in files if 720 <= f.get("height", 0) <= 1080 and f.get("file_type") == "video/mp4"],
            key=lambda x: abs(x.get("width", 0) - 1280)
        )
        if not hd_files:
            hd_files = sorted(files, key=lambda x: abs(x.get("width", 0) - 1280))

        file_url = hd_files[0]["link"]
        print(f"      📥 Downloading {hd_files[0].get('width','?')}x{hd_files[0].get('height','?')}...")

        r = requests.get(file_url, timeout=120, stream=True)
        r.raise_for_status()
        with open(clip_path, "wb") as f:
            for chunk in r.iter_content(65536): f.write(chunk)

        size_mb = clip_path.stat().st_size / (1024*1024)
        print(f"      ✅ Clip {clip_idx+1}: {size_mb:.1f}MB")
        return clip_path

    except Exception as e:
        print(f"      ❌ Pexels clip failed: {e}")
        return None


def fetch_all_clips(content, niche, video_idx):
    queries = content.get("pexels_queries", [])
    # Mix AI-generated queries with niche defaults for reliability
    all_queries = (queries + niche["pexels_queries"])[:4]
    if len(all_queries) < 4:
        all_queries = (all_queries * 2)[:4]

    print(f"\n   🎬 Fetching 4 Pexels HD clips...")
    clips = []
    for i, query in enumerate(all_queries):
        clip = fetch_pexels_clip(query, video_idx, i)
        if clip:
            clips.append(clip)
        else:
            # Try niche fallback
            fallback = niche["pexels_queries"][i % len(niche["pexels_queries"])]
            print(f"      🔄 Fallback: '{fallback}'")
            clip2 = fetch_pexels_clip(fallback, video_idx + 10, i)
            if clip2:
                clips.append(clip2)
        time.sleep(0.5)

    if not clips:
        raise RuntimeError("All Pexels clips failed — check PEXELS_API_KEY secret")

    print(f"   ✅ {len(clips)}/4 clips ready")
    return clips


# ══════════════════════════════════════════════════════════════════
#  STEP 5 — Assemble: clips + voiceover + muted song + subtitles overlay
# ══════════════════════════════════════════════════════════════════
def trim_and_normalize(clip_path, output_path, duration=8.0):
    """Trim clip to duration and normalize to 1280x720 portrait-friendly."""
    ret = subprocess.run([
        "ffmpeg", "-y", "-i", str(clip_path),
        "-t", str(duration),
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
               "pad=1280:720:(ow-iw)/2:(oh-ih)/2:black,"
               "setsar=1",
        "-r", "30", "-c:v", "libx264", "-preset", "fast",
        "-crf", "23", "-pix_fmt", "yuv420p",
        "-an", str(output_path)
    ], capture_output=True)
    if ret.returncode != 0:
        # Simple fallback
        subprocess.run([
            "ffmpeg", "-y", "-i", str(clip_path),
            "-t", str(duration),
            "-vf", "scale=1280:720",
            "-an", str(output_path)
        ], capture_output=True)
    return output_path


def assemble_video(clip_paths, audio_path, video_idx, song_path=None):
    print("   ✂️  Assembling video...")
    final_path = OUT / f"freakyBits_{video_idx:02d}.mp4"

    # Trim all clips to 8s and normalize
    trimmed = []
    for i, cp in enumerate(clip_paths):
        tp = OUT / f"trimmed_{video_idx:02d}_{i:02d}.mp4"
        trim_and_normalize(cp, tp, 8.0)
        if tp.exists() and tp.stat().st_size > 1000:
            trimmed.append(tp)

    if not trimmed:
        raise RuntimeError("No trimmed clips available")

    # Pad to 4 clips if fewer
    while len(trimmed) < 4:
        trimmed.append(trimmed[-1])

    # Concatenate
    concat_file = OUT / f"concat_{video_idx:02d}.txt"
    with open(concat_file, "w") as f:
        for tp in trimmed:
            f.write(f"file '{tp.resolve()}'\n")

    merged = OUT / f"merged_{video_idx:02d}.mp4"
    ret = subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file), "-c", "copy", str(merged)
    ], capture_output=True)
    if ret.returncode != 0:
        raise RuntimeError(f"Concat failed: {ret.stderr.decode()[:200]}")

    # Mix audio: voiceover full vol + muted trending song (vol=0 for algorithm)
    if song_path and song_path.exists():
        ret = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(merged), "-i", str(audio_path), "-i", str(song_path),
            "-filter_complex",
            "[1:a]volume=1.0[vo];[2:a]volume=0.0[vs];[vo][vs]amix=inputs=2:duration=first[a]",
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-shortest", str(final_path)
        ], capture_output=True)
    else:
        ret = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(merged), "-i", str(audio_path),
            "-c:v", "copy", "-c:a", "aac",
            "-map", "0:v:0", "-map", "1:a:0", "-shortest", str(final_path)
        ], capture_output=True)

    if ret.returncode != 0:
        # Fallback without song
        ret = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(merged), "-i", str(audio_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-shortest", str(final_path)
        ], capture_output=True)

    if ret.returncode != 0:
        raise RuntimeError(f"Assembly failed: {ret.stderr.decode()[:200]}")

    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(final_path)
    ], capture_output=True, text=True)
    duration = float(probe.stdout.strip() or 0)
    size_mb  = final_path.stat().st_size / (1024*1024)
    print(f"   ✅ {final_path.name} — {duration:.1f}s, {size_mb:.1f}MB")
    return final_path


# ══════════════════════════════════════════════════════════════════
#  STEP 6A — YouTube Upload
# ══════════════════════════════════════════════════════════════════
def upload_youtube(video_path, content):
    print("   📺 Uploading to YouTube...")
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.auth.transport.requests import Request
    except ImportError:
        print("   ❌ google libs missing")
        return "NOT_UPLOADED"

    tok_file = OUT / "yt_token.pickle"
    creds = None
    if tok_file.exists():
        import pickle
        with open(tok_file, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("   ❌ No valid YouTube token — run OAuth locally first")
            return "NO_TOKEN"
        import pickle
        with open(tok_file, "wb") as f:
            pickle.dump(creds, f)

    yt = build("youtube", "v3", credentials=creds)
    resp = yt.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title":       content["youtube_title"],
                "description": content.get("youtube_description_final", content["youtube_description"]),
                "tags":        content["youtube_tags"],
                "categoryId":  "22",   # People & Blogs — better for Shorts
            },
            "status": {
                "privacyStatus":           "public",
                "selfDeclaredMadeForKids": False,
            }
        },
        media_body=MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=-1, resumable=True)
    ).execute()

    url = f"https://youtube.com/watch?v={resp['id']}"
    print(f"   ✅ YouTube → {url}")
    return url


# ══════════════════════════════════════════════════════════════════
#  STEP 6B — Instagram Upload
# ══════════════════════════════════════════════════════════════════
def upload_instagram(video_path, content):
    if not INSTAGRAM_TOKEN or INSTAGRAM_TOKEN == "PLACEHOLDER_ADD_LATER":
        print("   ⚠️  Instagram skipped — add token later")
        return "SKIPPED"

    print("   📸 Uploading to Instagram...")
    try:
        with open(video_path, "rb") as f:
            r = requests.post("https://file.io", files={"file": f}, data={"expires": "14d"}, timeout=120)
        video_url = r.json().get("link")
        if not video_url:
            raise ValueError("No file.io link")
    except Exception as e:
        print(f"   ⚠️  Host failed: {e}")
        return "FAILED"

    base = f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}"
    container = requests.post(f"{base}/media", params={
        "media_type": "REELS", "video_url": video_url,
        "caption": content.get("instagram_caption_final", content["instagram_caption"]),
        "access_token": INSTAGRAM_TOKEN
    }).json()

    cid = container.get("id")
    if not cid:
        print(f"   ❌ Container error: {container}")
        return "FAILED"

    time.sleep(45)
    pub = requests.post(f"{base}/media_publish", params={
        "creation_id": cid, "access_token": INSTAGRAM_TOKEN
    }).json()

    url = f"https://www.instagram.com/reel/{pub.get('id','unknown')}"
    print(f"   ✅ Instagram → {url}")
    return url


# ══════════════════════════════════════════════════════════════════
#  SINGLE VIDEO
# ══════════════════════════════════════════════════════════════════
def make_one_video(video_idx):
    niche      = pick_niche(video_idx)
    lang       = pick_language(video_idx)
    part       = get_current_part(video_idx)
    part1_data = load_part1_topic() if part == 2 else None

    print(f"\n{'─'*62}")
    print(f"  VIDEO {video_idx+1}/{VIDEOS_PER_RUN}  |  {niche['label']} {niche['emoji']}  |  {lang['label']}"
          + (f"  |  Part {part}" if part else ""))
    print(f"{'─'*62}")

    content    = generate_content(niche, video_idx, lang, part, part1_data)
    audio      = generate_voiceover(content, video_idx, lang)
    clips      = fetch_all_clips(content, niche, video_idx)
    song       = get_trending_song(niche["name"], video_idx)
    video      = assemble_video(clips, audio, video_idx, song)
    yt_url     = upload_youtube(video, content)
    ig_url     = upload_instagram(video, content)

    if part == 1:
        save_part1_topic(content["topic"], niche["name"], lang["code"])

    return {
        "video": str(video), "niche": niche["label"], "language": lang["label"],
        "part": part, "topic": content["topic"], "title": content["youtube_title"],
        "youtube": yt_url, "instagram": ig_url,
    }


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY not set!")
        sys.exit(1)
    if not PEXELS_API_KEY:
        print("❌ PEXELS_API_KEY not set!")
        sys.exit(1)

    start = time.time()
    results, failures = [], []

    print("\n" + "═"*62)
    print(f"  🚀  FreakyBits Auto Pipeline")
    print(f"  📅  {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  🎬  {VIDEOS_PER_RUN} videos × 4 runs/day = 12/day")
    print(f"  🎙️  Voice: Edge TTS (neural) | 🎥 Video: Pexels HD")
    print("═"*62)

    for i in range(VIDEOS_PER_RUN):
        try:
            result = make_one_video(i)
            results.append(result)
            if i < VIDEOS_PER_RUN - 1:
                print(f"\n⏸️  30s cooldown...")
                time.sleep(30)
        except Exception as e:
            import traceback
            print(f"\n❌ Video {i+1} failed: {e}")
            traceback.print_exc()
            failures.append({"index": i+1, "error": str(e)})

    elapsed = round(time.time() - start)
    print("\n" + "═"*62)
    print(f"  ✅  {len(results)}/{VIDEOS_PER_RUN} videos  |  {elapsed//60}m {elapsed%60}s")
    print("═"*62)
    for r in results:
        part_str = f" | Part {r['part']}" if r.get("part") else ""
        print(f"\n  [{r['niche']}][{r['language']}]{part_str} {r['title']}")
        print(f"  📺 {r['youtube']}")
        print(f"  📸 {r['instagram']}")
    if failures:
        print(f"\n  ⚠️  {len(failures)} failed:")
        for f in failures:
            print(f"  Video {f['index']}: {f['error']}")

    log = OUT / f"log_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M')}.json"
    with open(log, "w") as f:
        json.dump({"results": results, "failures": failures, "elapsed_s": elapsed}, f, indent=2)

    if failures and len(failures) == VIDEOS_PER_RUN:
        sys.exit(1)


if __name__ == "__main__":
    main()
