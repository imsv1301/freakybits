#!/usr/bin/env python3
"""
FreakyBits Complete Pipeline v3.0
===================================
Oracle Cloud VM + n8n deployment — runs 24/7, no PC needed

VIDEOS (12/day):
  - 3 niches: Horror Facts | Comedy Facts | AI Tools Talk
  - 3 videos/run × 4 runs/day (7AM, 12PM, 6PM, 10PM IST)
  - YouTube Shorts + Instagram Reels via n8n

IMAGES (30/day):
  - 3 niches: AI Trends | Harsh Life Truth | Did You Know Facts
  - 10 images/niche as carousel post
  - YouTube Community Tab (10 separate posts) + Instagram Posts (1 carousel)

Stack:
  Gemini 2.5 Flash → scripts + image content
  Pillow           → cinematic image card generation
  Edge TTS         → neural voice (Christopher EN, Madhur HI)
  Pexels API       → HD stock video clips (9:16 portrait)
  FFmpeg           → video assembly + subtitles + color grading
  n8n webhook      → all uploads (YouTube + Instagram)
"""

import os, sys, json, time, re, asyncio, datetime, subprocess, requests
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from google import genai

# ══════════════════════════════════════════════════════════════════
#  CONFIG — loaded from environment variables
# ══════════════════════════════════════════════════════════════════
GEMINI_API_KEY   = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY   = os.environ.get("PEXELS_API_KEY", "")
N8N_VIDEO_WEBHOOK   = os.environ.get("N8N_VIDEO_WEBHOOK", "")    # n8n webhook for video upload
N8N_IMAGE_WEBHOOK   = os.environ.get("N8N_IMAGE_WEBHOOK", "")    # n8n webhook for image post
N8N_COMMUNITY_WEBHOOK = os.environ.get("N8N_COMMUNITY_WEBHOOK", "")  # n8n webhook for YT community

VIDEOS_PER_RUN   = 3
TARGET_DURATION  = 32       # seconds
VIDEO_W, VIDEO_H = 1080, 1920  # 9:16 portrait
IMG_W,   IMG_H   = 1080, 1080  # square for posts
IMAGES_PER_POST  = 10

# Output directories
OUT       = Path("freakybits_output")
IMG_OUT   = OUT / "images"
VID_OUT   = OUT / "videos"
LOG_OUT   = OUT / "logs"
for d in [OUT, IMG_OUT, VID_OUT, LOG_OUT]:
    d.mkdir(parents=True, exist_ok=True)

PART1_TOPIC_FILE = OUT / "part1_topic.json"
USED_TOPICS_FILE = OUT / "used_topics.json"
ANALYTICS_FILE   = OUT / "analytics.json"

client = genai.Client(api_key=GEMINI_API_KEY)


# ══════════════════════════════════════════════════════════════════
#  VIDEO NICHES
# ══════════════════════════════════════════════════════════════════
VIDEO_NICHES = [
    {
        "name":         "horror_facts",
        "label":        "Horror Facts",
        "emoji":        "👻",
        "tone":         "spine-chilling and mysterious, building dread with each fact",
        "script_style": "narrator",
        "color_filter": "curves=all='0/0 100/80 200/160 255/200'",
        "pexels_queries": ["dark abandoned building interior", "foggy forest night dark",
                           "dark stormy sky lightning", "mysterious dark corridor"],
    },
    {
        "name":         "comedy_facts",
        "label":        "Comedy Facts",
        "emoji":        "😂",
        "tone":         "hilarious and shocking, punchline energy on every fact",
        "script_style": "narrator",
        "color_filter": "curves=all='0/0 100/110 200/210 255/255'",
        "pexels_queries": ["colorful confetti explosion", "people laughing fun outdoors",
                           "bright colorful balloons", "funny animals cute"],
    },
    {
        "name":         "ai_tools_talk",
        "label":        "AI Tools Talk",
        "emoji":        "💬",
        "tone":         "two friends casually reacting and discussing trending AI tools — one excited, one skeptical",
        "script_style": "dialogue",
        "color_filter": "colorchannelmixer=rr=0.6:gg=0.8:bb=1.0",
        "pexels_queries": ["gaming setup neon lights dark", "computer screen gaming room",
                           "neon gaming background dark", "esports arena glowing"],
    },
]

# ══════════════════════════════════════════════════════════════════
#  IMAGE NICHES
# ══════════════════════════════════════════════════════════════════
IMAGE_NICHES = [
    {
        "name":       "ai_trends",
        "label":      "AI Trends",
        "emoji":      "🌐",
        "title_template": "10 AI TRENDS THAT WILL BLOW YOUR MIND:",
        "bg_color":   (5, 5, 20),        # deep dark blue
        "accent":     (0, 150, 255),      # electric blue
        "tags": "#AITrends #ArtificialIntelligence #AI2025 #FutureOfAI #TechTrends #AIUpdates #MachineLearning #AIRevolution #FreakyBits #Viral #Shorts #trending #AITools #FutureIsNow #TechNews #mindblown #amazingfacts #didyouknow #AIDaily #innovation",
    },
    {
        "name":       "harsh_life_truth",
        "label":      "Harsh Life Truth",
        "emoji":      "💭",
        "title_template": "10 HARSH TRUTHS ABOUT LIFE NO ONE TELLS YOU:",
        "bg_color":   (10, 5, 5),         # deep dark red
        "accent":     (220, 50, 50),      # crimson red
        "tags": "#HarshTruth #LifeLessons #RealTalk #TruthBombs #LifeAdvice #HardTruths #WakeUpCall #LifeReality #FreakyBits #Viral #mindset #motivation #selfimprovement #truth #reality #lifefacts #deepthoughts #wisdom #grow #trending",
    },
    {
        "name":       "did_you_know",
        "label":      "Did You Know Facts",
        "emoji":      "🤯",
        "title_template": "10 FACTS THAT WILL BLOW YOUR MIND:",
        "bg_color":   (5, 15, 5),         # deep dark green
        "accent":     (0, 200, 100),      # neon green
        "tags": "#DidYouKnow #MindBlowing #AmazingFacts #FunFacts #InterestingFacts #WTFFacts #CrazyFacts #FreakyBits #Viral #Shorts #facts #science #history #psychology #mindblown #didyouknow #amazing #trending #knowledge #learneveryday",
    },
]

# ══════════════════════════════════════════════════════════════════
#  LANGUAGE CONFIG
# ══════════════════════════════════════════════════════════════════
LANG_PATTERN = ["en", "hi", "en"]
LANG_CONFIG = {
    "en": {
        "label":        "English",
        "edge_voice":   "en-US-ChristopherNeural",
        "edge_rate":    "+20%",
        "follow_part2": "Follow for Part 2!",
    },
    "hi": {
        "label":        "Hindi",
        "edge_voice":   "hi-IN-MadhurNeural",
        "edge_rate":    "+15%",
        "follow_part2": "Part 2 ke liye follow karo!",
    },
}
PART_SERIES_SCHEDULE = {1: 1, 6: 2, 12: 1, 16: 2}

# Royalty-free background songs (muted for videos, audible for image posts)
SONGS = {
    "horror_facts":   "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3",
    "comedy_facts":   "https://cdn.pixabay.com/download/audio/2022/10/25/audio_946b736e00.mp3",
    "ai_tools_talk":  "https://cdn.pixabay.com/download/audio/2022/08/02/audio_2dde668d05.mp3",
    "ai_trends":      "https://cdn.pixabay.com/download/audio/2022/08/02/audio_2dde668d05.mp3",
    "harsh_life_truth": "https://cdn.pixabay.com/download/audio/2022/11/22/audio_febc508520.mp3",
    "did_you_know":   "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3",
}


# ══════════════════════════════════════════════════════════════════
#  HELPERS — TOPIC DEDUPLICATION
# ══════════════════════════════════════════════════════════════════
def load_used_topics():
    if not USED_TOPICS_FILE.exists():
        return {}
    try:
        with open(USED_TOPICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_used_topic(topic: str, niche_name: str):
    topics = load_used_topics()
    key = topic.lower().strip()
    topics[key] = {"niche": niche_name, "used_at": datetime.datetime.utcnow().isoformat()}
    if len(topics) > 500:
        oldest = sorted(topics.items(), key=lambda x: x[1].get("used_at", ""))[:100]
        for k, _ in oldest:
            del topics[k]
    with open(USED_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)

def is_topic_used(topic: str) -> bool:
    return topic.lower().strip() in load_used_topics()

def load_part1_topic():
    if not PART1_TOPIC_FILE.exists():
        return None
    try:
        with open(PART1_TOPIC_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None

def save_part1_topic(topic: str, niche_name: str, lang_code: str):
    data = {"topic": topic, "niche": niche_name, "lang": lang_code,
            "saved_at": datetime.datetime.utcnow().isoformat()}
    with open(PART1_TOPIC_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   💾 Part 1 saved: '{topic}'")

def log_analytics(entry: dict):
    try:
        data = []
        if ANALYTICS_FILE.exists():
            with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        entry["date"] = datetime.datetime.utcnow().isoformat()
        data.append(entry)
        with open(ANALYTICS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"   ⚠️  Analytics error: {e}")


# ══════════════════════════════════════════════════════════════════
#  SELECTORS
# ══════════════════════════════════════════════════════════════════
def pick_video_niche(video_index: int) -> dict:
    hour = datetime.datetime.utcnow().hour
    return VIDEO_NICHES[(hour // 6 + video_index) % len(VIDEO_NICHES)]

def pick_language(video_index: int) -> dict:
    code = LANG_PATTERN[video_index % len(LANG_PATTERN)]
    return {"code": code, **LANG_CONFIG[code]}

def get_current_part(video_index: int):
    if video_index != 2:
        return None
    hour = datetime.datetime.utcnow().hour
    for h in sorted(PART_SERIES_SCHEDULE):
        if hour <= h + 1:
            return PART_SERIES_SCHEDULE[h]
    return PART_SERIES_SCHEDULE[16]

def download_song(niche_name: str, prefix: str) -> Path | None:
    url = SONGS.get(niche_name)
    if not url:
        return None
    song_path = OUT / f"song_{prefix}.mp3"
    try:
        r = requests.get(url, timeout=30, stream=True)
        r.raise_for_status()
        with open(song_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return song_path
    except Exception as e:
        print(f"   ⚠️  Song download failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
#  STEP 1 — GENERATE VIDEO SCRIPT
# ══════════════════════════════════════════════════════════════════
def generate_video_content(niche: dict, video_index: int, lang: dict,
                            part=None, part1_data=None) -> dict:
    lang_label = lang["label"]
    lang_code  = lang["code"]
    print(f"\n🤖 [{niche['label']}] [{lang_label}]" + (f" [Part {part}]" if part else ""))

    today = datetime.datetime.utcnow().strftime("%B %d, %Y")

    lang_instruction = (
        "LANGUAGE: Write EVERYTHING in Hindi (Devanagari). Hashtags stay English."
        if lang_code == "hi" else "LANGUAGE: English throughout."
    )

    part_instruction = ""
    if part == 1:
        part_instruction = (
            f'PART 1 of 2: End narration with exactly: "{lang["follow_part2"]}". '
            f'Title ends with (Part 1). Cliffhanger ending.'
        )
    elif part == 2:
        prev = part1_data.get("topic", "previous topic") if part1_data else "previous topic"
        part_instruction = (
            f'PART 2 of 2: Continue from "{prev}". Title ends with (Part 2). Satisfying conclusion.'
        )

    used      = load_used_topics()
    avoid_str = ""
    if used:
        recent = list(used.keys())[-10:]
        avoid_str = f"\nAVOID these recently used topics: {', '.join(recent)}"

    if niche["script_style"] == "dialogue":
        narration_format = (
            'DIALOGUE FORMAT: Two characters — Alex (excited about AI tools) and Sam (skeptical, asks if free).\n'
            'Format: "Alex: [line]. Sam: [line]. Alex: [line]. Sam: [line]."\n'
            '80-100 words. Fast and funny. Mentions ONE specific trending AI tool, its use, and if it is free or paid.\n'
            'Alex delivers the CTA at the end. ONE continuous string, no line breaks.'
        )
        topic_instruction = "Topic = ONE specific trending AI tool released in 2025 or 2026."
        tag_extra = "#AITools #FreeAI #AIUpdates #NewAI #ArtificialIntelligence #TechTalk"
    else:
        narration_format = (
            'ONE continuous paragraph, 80-100 words, ZERO pauses between sentences, '
            'hook in first 3 words, 4 punchy facts, strong CTA at end. No line breaks.'
        )
        topic_instruction = "Fresh specific topic. No overused examples."
        tag_extra = "#Facts #mindblown #didyouknow #amazingfacts #viral"

    prompt = f"""You are a viral content creator for FreakyBits — YouTube/Instagram shorts channel.
Niche: {niche['label']} | Tone: {niche['tone']} | Date: {today}
{lang_instruction}
{part_instruction}
{avoid_str}

{topic_instruction}
{narration_format}

Reply ONLY in valid JSON — no markdown, no extra text:
{{
  "topic": "specific topic or AI tool name",
  "language": "{lang_code}",
  "part": {part if part else "null"},
  "youtube_title": "viral title under 60 chars",
  "youtube_description": "3 punchy sentences about the video.\\n\\nSubscribe for daily {niche['label']} {niche['emoji']}!\\n\\n",
  "youtube_viral_caption": "hook under 10 words with emoji",
  "youtube_trending_tags": "#Shorts #Viral #FreakyBits #{niche['name']} {tag_extra} #YouTubeShorts #trending #fyp #shortsvideo #reels #viralvideo",
  "youtube_tags": ["FreakyBits","Shorts","Viral","{niche['name']}","trending","fyp","mindblown","amazingfacts"],
  "instagram_caption": "punchy IG caption max 150 chars with emojis",
  "instagram_viral_caption": "Reels hook max 12 words 2-3 emojis",
  "instagram_trending_tags": "#reels #viral #freakybits #shorts #fyp #trending #explore #reelsinstagram #reelsviral #viralreels #explorepage #shortsvideo #mindblown #amazingfacts #didyouknow #trending2024 #foryou #instagram #{niche['name']} #facts",
  "trending_yt_song": "popular song - artist",
  "trending_ig_song": "popular song - artist",
  "narration": "write the full narration here as one continuous string",
  "pexels_queries": ["cinematic query 1", "cinematic query 2", "cinematic query 3", "cinematic query 4"]
}}"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            raw = response.text.strip().replace("```json", "").replace("```", "").strip()
            start = raw.find("{"); end = raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]
            data = json.loads(raw)
            break
        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"Gemini script generation failed: {e}")
            time.sleep(2 ** attempt)

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
#  STEP 2 — EDGE TTS VOICEOVER
# ══════════════════════════════════════════════════════════════════
def generate_voiceover(content: dict, prefix: str, lang: dict) -> Path:
    print(f"   🎙️  Edge TTS [{lang['label']}] {lang['edge_voice']}")
    audio_path = VID_OUT / f"voice_{prefix}.mp3"

    narration = re.sub(r'\s+', ' ', content["narration"]).strip()
    narration = narration.replace('\n', ' ').replace('\r', ' ')

    async def _tts():
        import edge_tts
        communicate = edge_tts.Communicate(
            text=narration,
            voice=lang["edge_voice"],
            rate=lang["edge_rate"],
            volume="+15%",
            pitch="+0Hz"
        )
        await communicate.save(str(audio_path))

    try:
        asyncio.run(_tts())
        print(f"   ✅ Voice: {audio_path.name} ({audio_path.stat().st_size // 1024}KB)")
    except Exception as e:
        print(f"   ⚠️  Edge TTS failed: {e} — using gTTS fallback")
        from gtts import gTTS
        gTTS(text=narration, lang=lang["code"], slow=False).save(str(audio_path))
        print(f"   ✅ gTTS fallback done")

    return audio_path


# ══════════════════════════════════════════════════════════════════
#  STEP 3 — GENERATE SUBTITLES (SRT)
# ══════════════════════════════════════════════════════════════════
def generate_subtitles(content: dict, audio_path: Path, prefix: str) -> Path:
    srt_path = VID_OUT / f"subs_{prefix}.srt"

    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)
    ], capture_output=True, text=True)
    total_duration = float(probe.stdout.strip() or 32)

    words  = content["narration"].strip().split()
    chunks = [" ".join(words[i:i+4]) for i in range(0, len(words), 4)]
    chunk_duration = total_duration / max(len(chunks), 1)

    def ts(s):
        h = int(s // 3600); m = int((s % 3600) // 60)
        sec = int(s % 60); ms = int((s - int(s)) * 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    lines = []
    for i, chunk in enumerate(chunks):
        start = i * chunk_duration
        end   = (i + 1) * chunk_duration - 0.05
        lines += [str(i + 1), f"{ts(start)} --> {ts(end)}", chunk.upper(), ""]

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"   ✅ {len(chunks)} subtitle chunks")
    return srt_path


# ══════════════════════════════════════════════════════════════════
#  STEP 4 — FETCH PEXELS CLIPS
# ══════════════════════════════════════════════════════════════════
def fetch_pexels_clip(query: str, prefix: str, clip_idx: int) -> Path | None:
    clip_path = VID_OUT / f"clip_{prefix}_{clip_idx}.mp4"
    print(f"      🔍 '{query}'")

    for orientation in ["portrait", "landscape"]:
        try:
            headers = {"Authorization": PEXELS_API_KEY}
            resp    = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params={"query": query, "per_page": 15, "orientation": orientation},
                timeout=20
            )
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
            if not videos:
                continue

            video = videos[clip_idx % len(videos)]
            files = video.get("video_files", [])
            hd    = sorted(
                [f for f in files if f.get("file_type") == "video/mp4" and f.get("height", 0) >= 720],
                key=lambda x: abs(x.get("height", 0) - 1280)
            )
            url = (hd or files)[0]["link"]

            r = requests.get(url, timeout=120, stream=True)
            r.raise_for_status()
            with open(clip_path, "wb") as f:
                for chunk in r.iter_content(65536):
                    f.write(chunk)

            print(f"      ✅ {clip_path.stat().st_size / (1024*1024):.1f}MB")
            return clip_path
        except Exception as e:
            print(f"      ⚠️  {orientation} failed: {e}")
            continue

    return None


def fetch_all_clips(content: dict, niche: dict, prefix: str) -> list:
    queries     = content.get("pexels_queries", [])
    all_queries = (queries + niche["pexels_queries"])[:4]
    while len(all_queries) < 4:
        all_queries = (all_queries * 2)[:4]

    print(f"\n   🎬 Fetching 4 Pexels clips...")
    clips = []
    for i, query in enumerate(all_queries):
        clip = fetch_pexels_clip(query, prefix, i)
        if not clip:
            clip = fetch_pexels_clip(niche["pexels_queries"][i % len(niche["pexels_queries"])], prefix + "_fb", i)
        if clip:
            clips.append(clip)
        time.sleep(0.3)

    if not clips:
        raise RuntimeError("All Pexels clips failed — check PEXELS_API_KEY")
    print(f"   ✅ {len(clips)}/4 clips ready")
    return clips


# ══════════════════════════════════════════════════════════════════
#  STEP 5 — ASSEMBLE VIDEO
# ══════════════════════════════════════════════════════════════════
def process_clip(clip_path: Path, out_path: Path, niche: dict, duration: float = 8.0) -> Path:
    color_filter = niche.get("color_filter", "curves=all='0/0 100/90 200/185 255/240'")
    vf = (
        f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_W}:{VIDEO_H},setsar=1,{color_filter},"
        f"unsharp=5:5:0.8:3:3:0"
    )
    ret = subprocess.run([
        "ffmpeg", "-y", "-i", str(clip_path), "-t", str(duration),
        "-vf", vf, "-r", "30", "-c:v", "libx264", "-preset", "fast",
        "-crf", "22", "-pix_fmt", "yuv420p", "-an", str(out_path)
    ], capture_output=True)
    if ret.returncode != 0:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(clip_path), "-t", str(duration),
            "-vf", f"scale={VIDEO_W}:{VIDEO_H},setsar=1", "-an", str(out_path)
        ], capture_output=True)
    return out_path


def burn_subtitles(video_path: Path, srt_path: Path, out_path: Path) -> Path:
    sub_filter = (
        f"subtitles={srt_path}:force_style='"
        f"FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,BackColour=&H80000000,"
        f"Bold=1,Outline=3,Shadow=2,Alignment=2,MarginV=80'"
    )
    ret = subprocess.run([
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", sub_filter,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-c:a", "copy",
        str(out_path)
    ], capture_output=True)
    if ret.returncode == 0:
        print("   ✅ Subtitles burned")
        return out_path
    print("   ⚠️  Subtitle burn failed — keeping video without subs")
    return video_path


def assemble_video(clips: list, audio_path: Path, srt_path: Path,
                   prefix: str, niche: dict, song_path: Path = None) -> Path:
    print("   ✂️  Assembling 9:16 cinematic video...")

    # Process clips
    processed = []
    for i, cp in enumerate(clips):
        pp = VID_OUT / f"proc_{prefix}_{i}.mp4"
        process_clip(cp, pp, niche, 8.0)
        if pp.exists() and pp.stat().st_size > 1000:
            processed.append(pp)

    if not processed:
        raise RuntimeError("No processed clips available")

    # Pad to 4 clips
    while len(processed) < 4:
        processed.append(processed[-1])

    # Concatenate
    concat_file = VID_OUT / f"concat_{prefix}.txt"
    with open(concat_file, "w") as f:
        for pp in processed:
            f.write(f"file '{pp.resolve()}'\n")

    merged = VID_OUT / f"merged_{prefix}.mp4"
    ret = subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file), "-c", "copy", str(merged)
    ], capture_output=True)
    if ret.returncode != 0:
        raise RuntimeError(f"Concat failed: {ret.stderr.decode()[:200]}")

    # Mix audio
    with_audio = VID_OUT / f"audio_{prefix}.mp4"
    if song_path and song_path.exists():
        ret = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(merged), "-i", str(audio_path), "-i", str(song_path),
            "-filter_complex",
            "[1:a]volume=1.0[vo];[2:a]volume=0.0[vs];[vo][vs]amix=inputs=2:duration=first[a]",
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-shortest", str(with_audio)
        ], capture_output=True)
    else:
        ret = subprocess.run([
            "ffmpeg", "-y", "-i", str(merged), "-i", str(audio_path),
            "-c:v", "copy", "-c:a", "aac",
            "-map", "0:v:0", "-map", "1:a:0", "-shortest", str(with_audio)
        ], capture_output=True)

    if ret.returncode != 0:
        ret = subprocess.run([
            "ffmpeg", "-y", "-i", str(merged), "-i", str(audio_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-shortest", str(with_audio)
        ], capture_output=True)
    if ret.returncode != 0:
        raise RuntimeError("Audio mix failed")

    # Burn subtitles
    final_path = VID_OUT / f"freakyBits_{prefix}.mp4"
    final_path = burn_subtitles(with_audio, srt_path, final_path)

    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(final_path)
    ], capture_output=True, text=True)
    duration = float(probe.stdout.strip() or 0)
    size_mb  = Path(final_path).stat().st_size / (1024 * 1024)
    print(f"   ✅ {Path(final_path).name} — {duration:.1f}s, {size_mb:.1f}MB, 9:16")
    return Path(final_path)


# ══════════════════════════════════════════════════════════════════
#  STEP 6 — GENERATE IMAGE CONTENT (Gemini)
# ══════════════════════════════════════════════════════════════════
def generate_image_content(niche: dict) -> dict:
    print(f"\n🖼️  Generating image content for [{niche['label']}]...")

    used      = load_used_topics()
    avoid_str = ""
    if used:
        recent = list(used.keys())[-10:]
        avoid_str = f"\nAVOID these recently used topics: {', '.join(recent)}"

    prompt = f"""You are a viral content creator for FreakyBits — Instagram and YouTube.
Niche: {niche['label']} {niche['emoji']}
Date: {datetime.datetime.utcnow().strftime('%B %d, %Y')}
{avoid_str}

Generate content for a 10-image carousel post.
Image 1 = bold title card.
Images 2-10 = one fact/truth/trend per image.

Rules:
- Each fact must be SHOCKING, SPECIFIC, and VIRAL-worthy
- Short and punchy — max 15 words per fact
- For AI Trends: mention real AI tools and their capabilities
- For Harsh Life Truth: raw, relatable, emotionally punchy
- For Did You Know: surprising science/psychology/history facts

Reply ONLY in valid JSON — no markdown:
{{
  "topic": "main topic of this carousel",
  "title_text": "{niche['title_template']}",
  "facts": [
    "FACT 1 — short punchy shocking statement",
    "FACT 2 — short punchy shocking statement",
    "FACT 3 — short punchy shocking statement",
    "FACT 4 — short punchy shocking statement",
    "FACT 5 — short punchy shocking statement",
    "FACT 6 — short punchy shocking statement",
    "FACT 7 — short punchy shocking statement",
    "FACT 8 — short punchy shocking statement",
    "FACT 9 — short punchy shocking statement"
  ],
  "instagram_caption": "viral IG caption 150 chars max with emojis — make it feel like we.think.deeply style",
  "instagram_viral_hook": "first line hook max 12 words 2-3 emojis",
  "youtube_community_caption": "punchy YT community post caption with emojis and question to drive comments",
  "cta_text": "FOLLOW @freakybits FOR MORE!"
}}"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            raw = response.text.strip().replace("```json", "").replace("```", "").strip()
            start = raw.find("{"); end = raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]
            data = json.loads(raw)
            # Ensure exactly 9 facts
            while len(data["facts"]) < 9:
                data["facts"].append("This will change how you see the world.")
            data["facts"] = data["facts"][:9]
            print(f"   ✅ Topic: {data['topic']}")
            return data
        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"Image content generation failed: {e}")
            time.sleep(2 ** attempt)


# ══════════════════════════════════════════════════════════════════
#  STEP 7 — CREATE IMAGE CARDS (Pillow)
# ══════════════════════════════════════════════════════════════════
def get_font(size: int, bold: bool = False):
    """Try to load a system font, fallback to default."""
    font_candidates = [
        f"/usr/share/fonts/truetype/liberation/LiberationSans-{'Bold' if bold else 'Regular'}.ttf",
        f"/usr/share/fonts/truetype/open-sans/OpenSans-{'Bold' if bold else 'Regular'}.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for fp in font_candidates:
        if Path(fp).exists():
            try:
                from PIL import ImageFont
                return ImageFont.truetype(fp, size)
            except:
                continue
    from PIL import ImageFont
    return ImageFont.load_default()


def draw_text_wrapped(draw: ImageDraw, text: str, x: int, y: int, max_w: int,
                       font, fill: tuple, line_spacing: int = 10) -> int:
    """Draw wrapped text and return final y position."""
    words  = text.split()
    lines  = []
    line   = []
    for word in words:
        test = " ".join(line + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_w:
            line.append(word)
        else:
            if line:
                lines.append(" ".join(line))
            line = [word]
    if line:
        lines.append(" ".join(line))

    current_y = y
    for ln in lines:
        draw.text((x, current_y), ln, font=font, fill=fill)
        bbox       = draw.textbbox((0, 0), ln, font=font)
        current_y += (bbox[3] - bbox[1]) + line_spacing
    return current_y


def create_title_image(niche: dict, content: dict, out_path: Path) -> Path:
    """Create the first title card image."""
    img  = Image.new("RGB", (IMG_W, IMG_H), color=niche["bg_color"])
    draw = ImageDraw.Draw(img)
    accent = niche["accent"]

    # Gradient overlay (simulate depth)
    for y in range(IMG_H):
        alpha = int(30 * (1 - y / IMG_H))
        draw.line([(0, y), (IMG_W, y)], fill=(accent[0], accent[1], accent[2]))

    # Re-draw base to keep it dark
    for y in range(0, IMG_H, 4):
        brightness = int(niche["bg_color"][0] + (accent[0] - niche["bg_color"][0]) * (y / IMG_H) * 0.3)
        r = min(255, brightness)
        g = min(255, int(niche["bg_color"][1] + (accent[1] - niche["bg_color"][1]) * (y / IMG_H) * 0.3))
        b = min(255, int(niche["bg_color"][2] + (accent[2] - niche["bg_color"][2]) * (y / IMG_H) * 0.3))
        draw.line([(0, y), (IMG_W, y)], fill=(r, g, b))

    # Top accent bar
    draw.rectangle([(0, 0), (IMG_W, 8)], fill=accent)
    draw.rectangle([(0, IMG_H - 8), (IMG_W, IMG_H)], fill=accent)

    # Emoji / icon area
    emoji_font = get_font(120, bold=True)
    draw.text((IMG_W // 2 - 70, 80), niche["emoji"], font=emoji_font, fill=(255, 255, 255))

    # FreakyBits branding
    brand_font = get_font(32, bold=True)
    draw.text((IMG_W // 2 - 80, 240), "@FREAKYBITS", font=brand_font, fill=accent)

    # Title text
    title_font = get_font(72, bold=True)
    title_text = content["title_text"]
    y_pos = draw_text_wrapped(draw, title_text, 60, 320, IMG_W - 120,
                               title_font, (255, 255, 255), 15)

    # Swipe prompt
    swipe_font = get_font(36)
    draw.text((IMG_W // 2 - 120, IMG_H - 120),
               "SWIPE TO SEE ALL →", font=swipe_font, fill=accent)

    # Bottom accent line
    draw.rectangle([(60, IMG_H - 60), (IMG_W - 60, IMG_H - 56)], fill=accent)

    img.save(str(out_path), quality=95)
    return out_path


def create_fact_image(niche: dict, fact_text: str, index: int,
                       total: int, cta: str, out_path: Path) -> Path:
    """Create a fact/truth image card."""
    img  = Image.new("RGB", (IMG_W, IMG_H), color=niche["bg_color"])
    draw = ImageDraw.Draw(img)
    accent = niche["accent"]

    # Background gradient
    for y in range(IMG_H):
        r = min(255, niche["bg_color"][0] + int((accent[0] - niche["bg_color"][0]) * (y / IMG_H) * 0.2))
        g = min(255, niche["bg_color"][1] + int((accent[1] - niche["bg_color"][1]) * (y / IMG_H) * 0.2))
        b = min(255, niche["bg_color"][2] + int((accent[2] - niche["bg_color"][2]) * (y / IMG_H) * 0.2))
        draw.line([(0, y), (IMG_W, y)], fill=(r, g, b))

    # Top bar
    draw.rectangle([(0, 0), (IMG_W, 8)], fill=accent)

    # Number badge
    num_font = get_font(48, bold=True)
    badge_x, badge_y = 60, 40
    draw.ellipse([(badge_x, badge_y), (badge_x + 80, badge_y + 80)], fill=accent)
    draw.text((badge_x + 18, badge_y + 14), str(index), font=num_font, fill=(255, 255, 255))

    # Progress dots
    dot_spacing = 20
    total_dots_w = total * dot_spacing
    dot_start = (IMG_W - total_dots_w) // 2
    for i in range(total):
        dot_color = accent if i < index else (80, 80, 80)
        draw.ellipse([
            (dot_start + i * dot_spacing, 55),
            (dot_start + i * dot_spacing + 10, 65)
        ], fill=dot_color)

    # Main fact text (large and bold)
    fact_font = get_font(64, bold=True)
    draw_text_wrapped(draw, fact_text.upper(), 60, 200, IMG_W - 120,
                      fact_font, (255, 255, 255), 20)

    # Accent divider
    draw.rectangle([(60, IMG_H - 200), (IMG_W - 60, IMG_H - 196)], fill=accent)

    # CTA at bottom
    cta_font  = get_font(34, bold=True)
    brand_font = get_font(28)
    draw.text((IMG_W // 2 - 160, IMG_H - 175), cta, font=cta_font, fill=accent)
    draw.text((IMG_W // 2 - 100, IMG_H - 120),
               "📱 @FREAKYBITS", font=brand_font, fill=(180, 180, 180))

    # Bottom bar
    draw.rectangle([(0, IMG_H - 8), (IMG_W, IMG_H)], fill=accent)

    img.save(str(out_path), quality=95)
    return out_path


def generate_image_carousel(niche: dict, content: dict, date_str: str) -> list:
    """Generate all 10 image cards for a carousel post."""
    print(f"   🎨 Generating 10 image cards...")
    niche_dir = IMG_OUT / niche["name"] / date_str
    niche_dir.mkdir(parents=True, exist_ok=True)

    images = []

    # Image 1 — Title card
    title_path = niche_dir / "00_title.jpg"
    create_title_image(niche, content, title_path)
    images.append(title_path)
    print(f"   ✅ Title card created")

    # Images 2-9 — Facts
    for i, fact in enumerate(content["facts"]):
        fact_path = niche_dir / f"{i+1:02d}_fact.jpg"
        create_fact_image(niche, fact, i + 1, 9, content["cta_text"], fact_path)
        images.append(fact_path)

    # Image 10 — CTA/Follow card
    cta_path = niche_dir / "10_cta.jpg"
    cta_content = {
        "title_text": f"FOLLOW @FREAKYBITS\nFOR DAILY MIND-BLOWING CONTENT!\n{niche['emoji']}",
    }
    create_title_image(niche, cta_content, cta_path)
    images.append(cta_path)

    print(f"   ✅ {len(images)}/10 images ready")
    return images


# ══════════════════════════════════════════════════════════════════
#  STEP 8 — SEND TO n8n WEBHOOKS
# ══════════════════════════════════════════════════════════════════
def send_to_n8n_video(video_path: Path, content: dict, niche: dict, lang: dict) -> dict:
    """Send video metadata to n8n for YouTube + Instagram upload."""
    if not N8N_VIDEO_WEBHOOK:
        print("   ⚠️  N8N_VIDEO_WEBHOOK not set — skipping upload")
        return {"youtube": "NO_WEBHOOK", "instagram": "NO_WEBHOOK"}

    print("   📡 Sending to n8n (YouTube Shorts + Instagram Reels)...")
    payload = {
        "type":          "video",
        "video_path":    str(video_path.resolve()),
        "niche":         niche["name"],
        "language":      lang["code"],
        "yt_title":      content["youtube_title"],
        "yt_description": content["youtube_description_final"],
        "yt_tags":       content["youtube_tags"],
        "ig_caption":    content["instagram_caption_final"],
        "topic":         content["topic"],
        "timestamp":     datetime.datetime.utcnow().isoformat(),
    }

    for attempt in range(3):
        try:
            resp = requests.post(N8N_VIDEO_WEBHOOK, json=payload, timeout=60)
            resp.raise_for_status()
            result = resp.json() if resp.content else {}
            print(f"   ✅ n8n video webhook sent")
            return result
        except Exception as e:
            if attempt == 2:
                print(f"   ❌ n8n video webhook failed: {e}")
                return {"error": str(e)}
            time.sleep(2 ** attempt)


def send_to_n8n_images(images: list, content: dict, niche: dict) -> dict:
    """Send image paths + captions to n8n for Instagram carousel + YT community."""
    if not N8N_IMAGE_WEBHOOK:
        print("   ⚠️  N8N_IMAGE_WEBHOOK not set — skipping image upload")
        return {"status": "NO_WEBHOOK"}

    print("   📡 Sending to n8n (Instagram Post + YouTube Community)...")
    payload = {
        "type":           "image_carousel",
        "niche":          niche["name"],
        "image_paths":    [str(p.resolve()) for p in images],
        "ig_caption":     (
            f"{content['instagram_viral_hook']}\n\n"
            f"{content['instagram_caption']}\n\n"
            f"{'─'*30}\n"
            f"{niche['tags']}"
        ),
        "yt_community_caption": content["youtube_community_caption"],
        "topic":          content["topic"],
        "timestamp":      datetime.datetime.utcnow().isoformat(),
    }

    for attempt in range(3):
        try:
            resp = requests.post(N8N_IMAGE_WEBHOOK, json=payload, timeout=120)
            resp.raise_for_status()
            result = resp.json() if resp.content else {}
            print(f"   ✅ n8n image webhook sent")
            return result
        except Exception as e:
            if attempt == 2:
                print(f"   ❌ n8n image webhook failed: {e}")
                return {"error": str(e)}
            time.sleep(2 ** attempt)


# ══════════════════════════════════════════════════════════════════
#  SINGLE VIDEO PIPELINE
# ══════════════════════════════════════════════════════════════════
def make_one_video(video_idx: int) -> dict:
    niche      = pick_video_niche(video_idx)
    lang       = pick_language(video_idx)
    part       = get_current_part(video_idx)
    part1_data = load_part1_topic() if part == 2 else None
    prefix     = f"v{datetime.datetime.utcnow().strftime('%H%M')}_{video_idx}"

    print(f"\n{'─'*62}")
    print(f"  VIDEO {video_idx+1}/3 | {niche['label']} {niche['emoji']} | {lang['label']}"
          + (f" | Part {part}" if part else ""))
    print(f"{'─'*62}")

    content  = generate_video_content(niche, video_idx, lang, part, part1_data)
    audio    = generate_voiceover(content, prefix, lang)
    srt      = generate_subtitles(content, audio, prefix)
    clips    = fetch_all_clips(content, niche, prefix)
    song     = download_song(niche["name"], prefix)
    video    = assemble_video(clips, audio, srt, prefix, niche, song)
    result   = send_to_n8n_video(video, content, niche, lang)

    if part == 1:
        save_part1_topic(content["topic"], niche["name"], lang["code"])
    save_used_topic(content["topic"], niche["name"])

    entry = {
        "type": "video", "niche": niche["label"], "language": lang["label"],
        "part": part, "topic": content["topic"], "title": content["youtube_title"],
        "file": str(video), **result,
    }
    log_analytics(entry)
    return entry


# ══════════════════════════════════════════════════════════════════
#  SINGLE IMAGE CAROUSEL PIPELINE
# ══════════════════════════════════════════════════════════════════
def make_image_carousel(niche: dict) -> dict:
    date_str = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M")
    print(f"\n{'─'*62}")
    print(f"  IMAGES | {niche['label']} {niche['emoji']} | 10 cards")
    print(f"{'─'*62}")

    content = generate_image_content(niche)
    images  = generate_image_carousel(niche, content, date_str)
    result  = send_to_n8n_images(images, content, niche)

    save_used_topic(content["topic"], niche["name"])

    entry = {
        "type": "image_carousel", "niche": niche["label"],
        "topic": content["topic"], "images": len(images), **result,
    }
    log_analytics(entry)
    return entry


# ══════════════════════════════════════════════════════════════════
#  MAIN — determines mode from command argument
# ══════════════════════════════════════════════════════════════════
def main():
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY not set"); sys.exit(1)

    mode  = sys.argv[1] if len(sys.argv) > 1 else "video"
    start = time.time()

    print("\n" + "═"*62)
    print(f"  🚀  FreakyBits Pipeline v3.0")
    print(f"  📅  {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  🎯  Mode: {mode.upper()}")
    print("═"*62)

    results  = []
    failures = []

    if mode == "video":
        # Run 3 videos
        if not PEXELS_API_KEY:
            print("❌ PEXELS_API_KEY not set"); sys.exit(1)
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

    elif mode == "images":
        # Run all 3 image niches
        for niche in IMAGE_NICHES:
            try:
                result = make_image_carousel(niche)
                results.append(result)
                time.sleep(5)
            except Exception as e:
                import traceback
                print(f"\n❌ Image carousel [{niche['label']}] failed: {e}")
                traceback.print_exc()
                failures.append({"niche": niche["name"], "error": str(e)})

    else:
        print(f"❌ Unknown mode: {mode}. Use 'video' or 'images'")
        sys.exit(1)

    elapsed = round(time.time() - start)
    print("\n" + "═"*62)
    print(f"  ✅  {len(results)} succeeded | {len(failures)} failed | {elapsed//60}m {elapsed%60}s")
    print("═"*62)

    if failures:
        print("\n  ⚠️  Failures:")
        for f in failures:
            print(f"  {f}")

    # Save run log
    log_file = LOG_OUT / f"run_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M')}.json"
    with open(log_file, "w") as f:
        json.dump({"mode": mode, "results": results, "failures": failures,
                   "elapsed_s": elapsed}, f, indent=2)

    if failures and len(failures) == (VIDEOS_PER_RUN if mode == "video" else len(IMAGE_NICHES)):
        sys.exit(1)


if __name__ == "__main__":
    main()
