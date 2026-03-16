"""
FreakyBits Auto Pipeline
========================
Stack: Gemini 2.5 Flash + Pexels HD + Edge TTS (fast neural) + FFmpeg subtitles
Style: Dark cinematic, bold word-by-word subtitles, 9:16 vertical, no voice gaps
"""

import os, sys, json, time, pickle, datetime, subprocess, requests, asyncio, re
from pathlib import Path
from google import genai

# ── CONFIG ─────────────────────────────────────────────────────────
GEMINI_API_KEY        = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY        = os.environ.get("PEXELS_API_KEY", "")
YOUTUBE_SECRETS_FILE  = "youtube_secrets.json"
INSTAGRAM_TOKEN       = os.environ.get("INSTAGRAM_TOKEN", "")
INSTAGRAM_ACCOUNT_ID  = os.environ.get("INSTAGRAM_ACCOUNT_ID", "")
VIDEOS_PER_RUN        = 3
VIDEO_W, VIDEO_H      = 1080, 1920   # 9:16 vertical

# ── LANGUAGE CONFIG ────────────────────────────────────────────────
LANG_PATTERN = ["en", "hi", "en"]
LANG_CONFIG = {
    "en": {
        "label":        "English",
        "edge_voice":   "en-US-AndrewNeural",
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

# Horror story niche uses slower deeper voice
HORROR_VOICE_OVERRIDE = {
    "en": {"edge_voice": "en-US-AndrewNeural", "edge_rate": "-8%"},
    "hi": {"edge_voice": "hi-IN-MadhurNeural", "edge_rate": "-5%"},
}

PART_SERIES_SCHEDULE = {1: 1, 6: 2, 12: 1, 16: 2}

# ── NICHES (3 active) ──────────────────────────────────────────────
NICHES = [
    {
        "name":         "horror_story",
        "label":        "Horror Story",
        "emoji":        "👻",
        "tone":         "slow, eerie, and suspenseful — like a campfire ghost story that builds dread then delivers a chilling twist",
        "script_style": "story",      # full mini-story: hook → build → twist → end
        "voice_rate":   "-10%",       # slower for dramatic effect
        "music_volume": "0.12",       # eerie music slightly audible (not muted)
        "color_filter": "curves=all='0/0 100/70 200/140 255/180'",  # very dark moody
        "pexels_queries": ["dark foggy forest night", "abandoned house interior dark",
                           "dark corridor horror", "cemetery moonlight fog"],
    },
    {
        "name":         "comedy_facts",
        "label":        "Comedy Facts",
        "emoji":        "😂",
        "tone":         "hilarious and shocking, punchline energy on every fact",
        "script_style": "narrator",
        "voice_rate":   "+20%",
        "music_volume": "0.0",        # muted for algorithm
        "color_filter": "curves=all='0/0 100/110 200/210 255/255'",
        "pexels_queries": ["colorful confetti explosion", "people laughing fun outdoors",
                           "bright colorful balloons", "funny animals cute"],
    },
    {
        "name":         "ai_tools_talk",
        "label":        "AI Tools Talk",
        "emoji":        "💬",
        "tone":         "two friends casually reacting to trending AI tools — Alex excited, Sam skeptical",
        "script_style": "dialogue",
        "voice_rate":   "+15%",
        "music_volume": "0.0",        # muted for algorithm
        "color_filter": "colorchannelmixer=rr=0.6:gg=0.8:bb=1.0",
        "pexels_queries": ["gaming setup neon lights dark", "computer screen gaming room",
                           "neon gaming background dark", "esports arena glowing"],
    },
]

# Songs — horror is audible, others muted
TRENDING_SONGS_FREE = [
    {"niche": "horror_story",   "url": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3"},
    {"niche": "horror_story",   "url": "https://cdn.pixabay.com/download/audio/2021/09/06/audio_6ded321929.mp3"},
    {"niche": "comedy_facts",   "url": "https://cdn.pixabay.com/download/audio/2022/10/25/audio_946b736e00.mp3"},
    {"niche": "comedy_facts",   "url": "https://cdn.pixabay.com/download/audio/2022/01/20/audio_d0ee71a7e6.mp3"},
    {"niche": "ai_tools_talk",  "url": "https://cdn.pixabay.com/download/audio/2022/08/02/audio_2dde668d05.mp3"},
    {"niche": "ai_tools_talk",  "url": "https://cdn.pixabay.com/download/audio/2021/11/13/audio_cb31e6deb5.mp3"},
]

OUT              = Path("buzzBits_output")
OUT.mkdir(exist_ok=True)
PART1_TOPIC_FILE  = OUT / "part1_topic.json"
USED_TOPICS_FILE  = OUT / "used_topics.json"
ANALYTICS_FILE    = OUT / "analytics.json"
client = genai.Client(api_key=GEMINI_API_KEY)


# ══════════════════════════════════════════════════════════════════
#  TOPIC DEDUPLICATION — prevents repeating same topics
# ══════════════════════════════════════════════════════════════════
def load_used_topics() -> dict:
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
    # Keep last 500 topics only
    if len(topics) > 500:
        oldest = sorted(topics.items(), key=lambda x: x[1].get("used_at",""))[:100]
        for k, _ in oldest:
            del topics[k]
    with open(USED_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)

def is_topic_used(topic: str) -> bool:
    topics = load_used_topics()
    return topic.lower().strip() in topics


# ══════════════════════════════════════════════════════════════════
#  ANALYTICS LOGGER — tracks every upload for portfolio metrics
# ══════════════════════════════════════════════════════════════════
def log_analytics(video_result: dict):
    try:
        analytics = []
        if ANALYTICS_FILE.exists():
            with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
                analytics = json.load(f)
        analytics.append({
            "date":      datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "title":     video_result.get("title", ""),
            "niche":     video_result.get("niche", ""),
            "language":  video_result.get("language", ""),
            "youtube":   video_result.get("youtube", ""),
            "instagram": video_result.get("instagram", ""),
            "topic":     video_result.get("topic", ""),
        })
        with open(ANALYTICS_FILE, "w", encoding="utf-8") as f:
            json.dump(analytics, f, ensure_ascii=False, indent=2)
        print(f"   📊 Analytics logged ({len(analytics)} total videos)")
    except Exception as e:
        print(f"   ⚠️  Analytics log failed: {e}")


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
#  STEP 1 — Generate Script
# ══════════════════════════════════════════════════════════════════
def get_viral_angle(niche_name: str, niche_label: str) -> str:
    """Search web for currently trending viral angles for this niche."""
    try:
        search_queries = {
            "horror_story":   f"viral horror story shorts reels 2025 trending",
            "comedy_facts":   f"viral comedy facts shorts 2025 trending funny",
            "ai_tools_talk":  f"trending AI tools 2025 free viral shorts",
        }
        query = search_queries.get(niche_name, f"viral {niche_label} shorts 2025")
        resp  = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"Accept": "application/json",
                     "Accept-Encoding": "gzip",
                     "X-Subscription-Token": "BSAGzGTrqRiZBXc2KhpLfq9WlHPwORv"},
            params={"q": query, "count": 5},
            timeout=8
        )
        if resp.status_code == 200:
            results = resp.json().get("web", {}).get("results", [])
            snippets = [r.get("description", "") for r in results[:3] if r.get("description")]
            if snippets:
                return "\nTRENDING CONTEXT (use this to inspire your angle):\n" + " | ".join(snippets[:2])[:400]
    except Exception:
        pass
    # Fallback: hardcoded trending angles per niche
    fallbacks = {
        "horror_story":  "Trending: true paranormal encounters, sleep paralysis demons, real haunted locations",
        "comedy_facts":  "Trending: weird animal facts, bizarre laws, shocking historical blunders",
        "ai_tools_talk": "Trending: Sora, Gemini 2.5, Claude 3.7, Grok 3, free AI image generators",
    }
    return "\nTRENDING CONTEXT: " + fallbacks.get(niche_name, "use the most viral angle possible")


def generate_content(niche, video_index, lang, part=None, part1_data=None):
    lang_label = lang["label"]
    lang_code  = lang["code"]
    print(f"\n🤖 [{niche['label']}] [{lang_label}]" + (f" [Part {part}]" if part else ""))

    today        = datetime.datetime.utcnow().strftime("%B %d, %Y")
    script_style = niche.get("script_style", "narrator")

    # Language instruction
    lang_instruction = (
        "LANGUAGE: Write EVERYTHING in Hindi (Devanagari). Hashtags stay English."
        if lang_code == "hi" else "LANGUAGE: English throughout."
    )

    # Part series instruction
    part_instruction = ""
    if part == 1:
        part_instruction = (
            f'PART 1 of 2: End narration with exactly: "{lang["follow_part2"]}". '
            f'Title ends with (Part 1). End on a cliffhanger.'
        )
    elif part == 2:
        prev = part1_data.get("topic", "previous topic") if part1_data else "previous topic"
        part_instruction = f'PART 2 of 2: Continue from "{prev}". Title ends with (Part 2). Satisfying conclusion.'

    # Topic deduplication
    used   = load_used_topics()
    recent = list(used.keys())[-10:] if used else []
    avoid_str = (f"\nAVOID these recently used topics: {', '.join(recent)}" if recent else "")

    # Web search for viral trending angle
    print(f"   🔍 Searching viral angles for [{niche['label']}]...")
    viral_context = get_viral_angle(niche["name"], niche["label"])

    # Script format per niche
    if script_style == "story":
        # Horror story — full mini narrative
        narration_instruction = (
            "HORROR STORY FORMAT: \n"
            "Write like you're whispering a true story to someone at 3am. Conversational but eerie.\n"
            "Structure: \n"
            "1. HOOK — first 5 words must make skin crawl (not 'Did you know' — start with dread)\n"
            "2. BUILD — describe the location, the person, what they heard or saw — sensory and specific\n"
            "3. TWIST — the moment everything changed — delivered calmly which makes it more disturbing\n"
            "4. END — ONE final sentence that haunts. Unresolved. Lingers. \n"
            "100-120 words. Use phrases like 'here's what nobody could explain', 'and that's when they noticed'.\n"
            "Sound like a true crime podcast host — calm, real, terrifying.\n"
            "ONE continuous paragraph. No line breaks."
        )
        topic_instruction  = "Pick ONE specific real haunted location, true paranormal case, or terrifying urban legend. Be specific — name the place, year, or person."
        tag_extras         = "#HorrorStory #ScaryStory #HorrorShorts #TrueHorror #Paranormal #CreepyStory #HorrorTok #ghost #haunted #scary"
        ig_tags            = "#reels #viral #freakybits #horrorstory #scarystory #horror #ghost #paranormal #haunted #creepy #horrortok #scarytiktok #horrorreels #fyp #trending #explore #shortsvideo #truecrime #supernatural #chilling"
        duration_note      = "45-55 seconds"
        pexels_hint        = '["dark foggy forest night", "abandoned building interior", "cemetery dark fog", "dark corridor horror"]'

    elif script_style == "dialogue":
        narration_instruction = (
            "DIALOGUE FORMAT (always English): \n"
            "Two characters: Alex (hyped about AI) and Sam (skeptical broke guy who always asks if free).\n"
            "Format: \"Did you know [tool] exists? Alex: bro this AI just [does X]. Sam: wait is it free? "
            "Alex: [yes/no + detail]. Sam: [reaction]. Alex: Follow FreakyBits for more free AI drops!\"\n"
            "80-100 words. Sound like two friends texting — casual, punchy, funny.\n"
            "ONE continuous string, no line breaks."
        )
        topic_instruction  = "Pick ONE specific trending AI tool from 2025 or 2026. Be specific — name it, its main use, its price (free/paid)."
        tag_extras         = "#AITools #FreeAI #AIUpdates #NewAI #ArtificialIntelligence #TechTalk #AIShorts"
        ig_tags            = "#reels #viral #freakybits #aitools #freeai #artificialintelligence #techtalk #newai #aiupdates #technews #futuretech #shorts #fyp #trending #explore #reelsinstagram #viralreels #tech #airevolution #innovation"
        duration_note      = "32 seconds"
        pexels_hint        = '["gaming setup neon dark", "esports arena glowing", "neon gaming room dark", "computer screen gaming"]'''

    else:
        # Comedy narrator
        narration_instruction = (
            "COMEDY FACTS FORMAT: Start with 'Did you know' — then deliver 4 shocking funny facts "
            "in a conversational tone like you're texting a friend who loves weird trivia. "
            "Add reactions like 'I know right?', 'wait it gets better', 'no seriously'. "
            "80-100 words. ONE continuous string. End with 'Follow for more wild facts!'"
        )
        topic_instruction  = "Fresh specific topic — shocking, funny, unbelievable. No overused examples."
        tag_extras         = "#Facts #mindblown #didyouknow #amazingfacts #funnyfacts #comedy"
        ig_tags            = "#reels #viral #freakybits #shorts #fyp #trending #facts #explore #reelsinstagram #reelsviral #viralreels #explorepage #shortsvideo #mindblown #amazingfacts #didyouknow #funnyfacts #comedy #trending2024 #foryou"
        duration_note      = "32 seconds"
        pexels_hint        = '["colorful confetti explosion", "people laughing outdoors", "bright colorful balloons", "funny animals cute"]'''

    prompt = f"""You are a world-class viral short-form video scriptwriter. Your scripts feel like a friend excitedly telling you something insane — not like someone reading off a teleprompter.

Niche: {niche['label']} | Date: {today} | Duration: {duration_note}
{lang_instruction}
{part_instruction}
{avoid_str}
{viral_context}

TASK: {topic_instruction}

SCRIPT STYLE — THIS IS CRITICAL:
Write like you are TALKING to a friend, not reading a script. Use:
- Short punchy sentences mixed with longer ones
- Natural pauses implied by punctuation (comma = breath, period = pause)
- Conversational words: "Okay so", "Here's the thing", "Wait — it gets worse", "And get this"
- Reactions: "I know, sounds crazy", "No seriously", "That's not even the weirdest part"
- Never sound robotic. Never list facts dryly.

{narration_instruction}

WRITING RULES:
- Comedy/AI fact videos MUST start with "Did you know" as first words
- Horror stories start with something that immediately creates dread
- Every sentence must make viewer MORE curious or MORE scared
- Use real names, real places, real years — specifics make stories believable
- End ALWAYS with "Follow for more!" or niche CTA — said naturally, not awkwardly
- Write the narration as ONE continuous string — no line breaks, no bullet points
- Sound like MrBeast or Yes Theory narration style — energetic and human

Reply ONLY in valid JSON (no markdown, no extra text):
{{
  "topic": "specific topic/tool/story name",
  "language": "{lang_code}",
  "part": {part if part else "null"},
  "youtube_title": "viral title under 60 chars — curiosity or shock",
  "youtube_description": "3 conversational punchy sentences.\\n\\nSubscribe for daily {niche['label']} {niche['emoji']}!\\n\\n",
  "youtube_viral_caption": "hook under 10 words with emoji",
  "youtube_trending_tags": "#Shorts #Viral #FreakyBits #{niche['name']} {tag_extras} #YouTubeShorts #trending #fyp #shortsvideo #reels #viralvideo",
  "youtube_tags": ["FreakyBits","Shorts","Viral","{niche['name']}","trending","fyp","mindblown","viral","facts"],
  "instagram_caption": "punchy IG caption 150 chars max with emojis — conversational",
  "instagram_viral_caption": "Reels hook 12 words max 2-3 emojis",
  "instagram_trending_tags": "{ig_tags}",
  "trending_yt_song": "popular song - artist matching niche mood",
  "trending_ig_song": "popular song - artist matching niche mood",
  "narration": "Write the FULL conversational narration here — sounds like talking to a friend, starts with Did you know for facts, energetic and human, no robotic lines",
  "pexels_queries": {pexels_hint}
}}"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            raw      = response.text.strip().replace("```json","").replace("```","").strip()
            start    = raw.find("{"); end = raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]
            data = json.loads(raw)
            break
        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"Content generation failed after 3 attempts: {e}")
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
#  STEP 2 — Edge TTS (fast neural voice, NO gaps between sentences)
# ══════════════════════════════════════════════════════════════════
def generate_voiceover(content, video_idx, lang, niche=None):
    """Generate voiceover with niche-specific voice and rate."""
    # Apply horror voice override (deeper, slower voice)
    voice_settings = dict(lang)
    if niche and niche.get("name") == "horror_story":
        override = HORROR_VOICE_OVERRIDE.get(lang["code"], {})
        voice_settings.update(override)
        print(f"   🎙️  Edge TTS [Horror] {voice_settings['edge_voice']} {voice_settings['edge_rate']} (slow dramatic)")
    else:
        print(f"   🎙️  Edge TTS [{lang['label']}] {voice_settings['edge_voice']} {voice_settings['edge_rate']}")

    audio_path = OUT / f"voice_{video_idx:02d}.mp3"
    narration  = re.sub(r'\s+', ' ', content["narration"]).strip()
    narration  = narration.replace('\n', ' ').replace('\r', ' ')

    async def _tts():
        import edge_tts
        communicate = edge_tts.Communicate(
            text=narration,
            voice=voice_settings["edge_voice"],
            rate=voice_settings["edge_rate"],
            volume="+15%",
            pitch="+0Hz"
        )
        await communicate.save(str(audio_path))

    try:
        asyncio.run(_tts())
        size_kb = audio_path.stat().st_size // 1024
        print(f"   ✅ Voice: {audio_path.name} ({size_kb}KB)")
    except Exception as e:
        print(f"   ⚠️  Edge TTS failed: {e} — gTTS fallback")
        from gtts import gTTS
        gTTS(text=narration, lang=lang["code"], slow=False).save(str(audio_path))
        print(f"   ✅ gTTS fallback done")

    return audio_path


# ══════════════════════════════════════════════════════════════════
#  STEP 3 — Generate Word-by-Word Subtitle SRT
# ══════════════════════════════════════════════════════════════════
def generate_subtitles(content, audio_path, video_idx, lang):
    """Generate SRT subtitles synced to voice duration."""
    print(f"   📝 Generating subtitles...")
    srt_path = OUT / f"subs_{video_idx:02d}.srt"

    # Get audio duration
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)
    ], capture_output=True, text=True)
    total_duration = float(probe.stdout.strip() or 32)

    narration = content["narration"].strip()
    # Split into chunks of 3-4 words for subtitle display
    words = narration.split()
    chunks = []
    chunk_size = 4
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i+chunk_size]))

    # Distribute time evenly across chunks
    chunk_duration = total_duration / max(len(chunks), 1)

    srt_lines = []
    for i, chunk in enumerate(chunks):
        start = i * chunk_duration
        end   = (i + 1) * chunk_duration - 0.05

        def ts(s):
            h = int(s//3600); m = int((s%3600)//60)
            sec = int(s%60); ms = int((s - int(s))*1000)
            return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

        srt_lines.append(f"{i+1}")
        srt_lines.append(f"{ts(start)} --> {ts(end)}")
        srt_lines.append(chunk.upper())
        srt_lines.append("")

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    print(f"   ✅ {len(chunks)} subtitle chunks generated")
    return srt_path


# ══════════════════════════════════════════════════════════════════
#  STEP 4 — Pexels HD clips
# ══════════════════════════════════════════════════════════════════
def fetch_pexels_clip(query, video_idx, clip_idx):
    clip_path = OUT / f"clip_{video_idx:02d}_{clip_idx:02d}.mp4"
    print(f"      🔍 '{query}'")

    try:
        headers = {"Authorization": PEXELS_API_KEY}
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params={"query": query, "per_page": 15, "orientation": "portrait"},
            timeout=20
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])

        # Fallback to landscape if no portrait results
        if not videos:
            resp2 = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params={"query": query, "per_page": 15, "orientation": "landscape"},
                timeout=20
            )
            videos = resp2.json().get("videos", [])

        if not videos:
            raise ValueError(f"No results for '{query}'")

        video = videos[clip_idx % len(videos)]
        files = video.get("video_files", [])
        # Prefer HD files
        hd = sorted(
            [f for f in files if f.get("file_type") == "video/mp4" and f.get("height", 0) >= 720],
            key=lambda x: abs(x.get("height", 0) - 1280)
        )
        url = (hd or files)[0]["link"]

        r = requests.get(url, timeout=120, stream=True)
        r.raise_for_status()
        with open(clip_path, "wb") as f:
            for chunk in r.iter_content(65536): f.write(chunk)

        size_mb = clip_path.stat().st_size / (1024*1024)
        print(f"      ✅ {size_mb:.1f}MB")
        return clip_path

    except Exception as e:
        print(f"      ❌ {e}")
        return None


def fetch_all_clips(content, niche, video_idx):
    queries = content.get("pexels_queries", [])
    all_queries = (queries + niche["pexels_queries"])[:4]
    while len(all_queries) < 4:
        all_queries = (all_queries * 2)[:4]

    print(f"\n   🎬 Fetching 4 Pexels clips (9:16 portrait)...")
    clips = []
    for i, query in enumerate(all_queries):
        clip = fetch_pexels_clip(query, video_idx, i)
        if not clip:
            # Try niche fallback
            clip = fetch_pexels_clip(niche["pexels_queries"][i % len(niche["pexels_queries"])], video_idx + 10, i)
        if clip:
            clips.append(clip)
        time.sleep(0.3)

    if not clips:
        raise RuntimeError("All Pexels clips failed — check PEXELS_API_KEY")
    print(f"   ✅ {len(clips)}/4 clips ready")
    return clips


# ══════════════════════════════════════════════════════════════════
#  STEP 5 — Trending Song
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
        print(f"   ✅ Song ({song_path.stat().st_size//1024}KB)")
        return song_path
    except Exception as e:
        print(f"   ⚠️  Song failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
#  STEP 6 — Assemble: 9:16 + dark filter + bold subtitles
# ══════════════════════════════════════════════════════════════════
def process_clip(clip_path, output_path, niche, duration=8.0):
    """Crop to 9:16, apply dark cinematic filter, trim to duration."""
    color_filter = niche.get("color_filter", "curves=all='0/0 100/90 200/185 255/240'")

    vf = (
        f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_W}:{VIDEO_H},"
        f"setsar=1,"
        f"{color_filter},"
        f"unsharp=5:5:0.8:3:3:0"   # slight sharpen for crispness
    )

    ret = subprocess.run([
        "ffmpeg", "-y", "-i", str(clip_path),
        "-t", str(duration),
        "-vf", vf,
        "-r", "30", "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-an", str(output_path)
    ], capture_output=True)

    if ret.returncode != 0:
        # Simpler fallback
        subprocess.run([
            "ffmpeg", "-y", "-i", str(clip_path),
            "-t", str(duration),
            "-vf", f"scale={VIDEO_W}:{VIDEO_H},setsar=1",
            "-an", str(output_path)
        ], capture_output=True)
    return output_path


def burn_subtitles(video_path, srt_path, output_path):
    """Burn bold white subtitles with black outline onto video."""
    # Font settings: large, bold, white with thick black shadow
    subtitle_filter = (
        f"subtitles={srt_path}:force_style='"
        f"FontName=Arial,"
        f"FontSize=22,"
        f"PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,"
        f"BackColour=&H80000000,"
        f"Bold=1,"
        f"Outline=3,"
        f"Shadow=2,"
        f"Alignment=2,"
        f"MarginV=80'"
    )

    ret = subprocess.run([
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", subtitle_filter,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "copy", str(output_path)
    ], capture_output=True)

    if ret.returncode == 0:
        print(f"   ✅ Subtitles burned")
        return output_path
    else:
        print(f"   ⚠️  Subtitle burn failed — using video without subs")
        return video_path


def assemble_video(clip_paths, audio_path, srt_path, video_idx, niche, song_path=None):
    print("   ✂️  Assembling 9:16 cinematic video...")
    final_path = OUT / f"freakyBits_{video_idx:02d}.mp4"

    # Process all clips: 9:16 + color grade
    processed = []
    for i, cp in enumerate(clip_paths):
        pp = OUT / f"proc_{video_idx:02d}_{i:02d}.mp4"
        process_clip(cp, pp, niche, 8.0)
        if pp.exists() and pp.stat().st_size > 1000:
            processed.append(pp)

    if not processed:
        raise RuntimeError("No processed clips")

    # Pad to 4 clips
    while len(processed) < 4:
        processed.append(processed[-1])

    # Concatenate
    concat_file = OUT / f"concat_{video_idx:02d}.txt"
    with open(concat_file, "w") as f:
        for pp in processed:
            f.write(f"file '{pp.resolve()}'\n")

    merged = OUT / f"merged_{video_idx:02d}.mp4"
    ret = subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file), "-c", "copy", str(merged)
    ], capture_output=True)
    if ret.returncode != 0:
        raise RuntimeError(f"Concat failed: {ret.stderr.decode()[:200]}")

    # Add audio (voice full vol + muted song)
    with_audio = OUT / f"audio_{video_idx:02d}.mp4"
    if song_path and song_path.exists():
        ret = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(merged), "-i", str(audio_path), "-i", str(song_path),
            "-filter_complex",
            "[1:a]volume=1.0[vo];[2:a]volume={music_vol}[vs];[vo][vs]amix=inputs=2:duration=first[a]".format(music_vol=niche.get("music_volume","0.0")),
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-shortest", str(with_audio)
        ], capture_output=True)
    else:
        ret = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(merged), "-i", str(audio_path),
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
        raise RuntimeError(f"Audio mix failed")

    # Burn subtitles
    final_path = burn_subtitles(with_audio, srt_path, final_path)

    # Get stats
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(final_path)
    ], capture_output=True, text=True)
    duration = float(probe.stdout.strip() or 0)
    size_mb  = Path(final_path).stat().st_size / (1024*1024)
    print(f"   ✅ {Path(final_path).name} — {duration:.1f}s, {size_mb:.1f}MB, 9:16 vertical")
    return Path(final_path)


# ══════════════════════════════════════════════════════════════════
#  STEP 7A — YouTube Upload
# ══════════════════════════════════════════════════════════════════
def upload_youtube(video_path, content):
    print("   📺 Uploading to YouTube...")
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.auth.transport.requests import Request
        import pickle
    except ImportError:
        print("   ❌ google libs missing"); return "NOT_UPLOADED"

    tok_file = OUT / "yt_token.pickle"
    creds = None
    if tok_file.exists():
        with open(tok_file, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("   ❌ No valid token"); return "NO_TOKEN"
        with open(tok_file, "wb") as f:
            pickle.dump(creds, f)

    yt = build("youtube", "v3", credentials=creds)

    # Retry logic — exponential backoff (3 attempts)
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            resp = yt.videos().insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title":       content["youtube_title"],
                        "description": content.get("youtube_description_final", content["youtube_description"]),
                        "tags":        content["youtube_tags"],
                        "categoryId":  "22",
                    },
                    "status": {
                        "privacyStatus": "public",
                        "selfDeclaredMadeForKids": False,
                    }
                },
                media_body=MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=-1, resumable=True)
            ).execute()
            url = f"https://youtube.com/watch?v={resp['id']}"
            print(f"   ✅ YouTube → {url}")
            return url
        except Exception as e:
            if attempt < max_retries:
                wait = 2 ** attempt  # 2s, 4s backoff
                print(f"   ⚠️  Upload attempt {attempt} failed: {e} — retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


# ══════════════════════════════════════════════════════════════════
#  STEP 7B — Instagram Upload
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
        print(f"   ⚠️  Host failed: {e}"); return "FAILED"

    base = f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}"
    container = requests.post(f"{base}/media", params={
        "media_type": "REELS", "video_url": video_url,
        "caption": content.get("instagram_caption_final", content["instagram_caption"]),
        "access_token": INSTAGRAM_TOKEN
    }).json()

    cid = container.get("id")
    if not cid:
        print(f"   ❌ Container error: {container}"); return "FAILED"

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
    # AI Tools Talk is always English — override Hindi slot
    if niche["name"] == "ai_tools_talk" and lang["code"] == "hi":
        lang = {"code": "en", **LANG_CONFIG["en"]}
    part       = get_current_part(video_idx)
    part1_data = load_part1_topic() if part == 2 else None

    print(f"\n{'─'*62}")
    print(f"  VIDEO {video_idx+1}/3  |  {niche['label']} {niche['emoji']}  |  {lang['label']}"
          + (f"  |  Part {part}" if part else ""))
    print(f"{'─'*62}")

    content  = generate_content(niche, video_idx, lang, part, part1_data)
    audio    = generate_voiceover(content, video_idx, lang, niche)
    srt      = generate_subtitles(content, audio, video_idx, lang)
    clips    = fetch_all_clips(content, niche, video_idx)
    song     = get_trending_song(niche["name"], video_idx)
    video    = assemble_video(clips, audio, srt, video_idx, niche, song)
    yt_url   = upload_youtube(video, content)
    ig_url   = upload_instagram(video, content)

    if part == 1:
        save_part1_topic(content["topic"], niche["name"], lang["code"])

    # Save used topic to avoid repeats
    save_used_topic(content["topic"], niche["name"])

    result = {
        "video": str(video), "niche": niche["label"], "language": lang["label"],
        "part": part, "topic": content["topic"], "title": content["youtube_title"],
        "youtube": yt_url, "instagram": ig_url,
    }

    # Log analytics
    log_analytics(result)
    return result


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY not set!"); sys.exit(1)
    if not PEXELS_API_KEY:
        print("❌ PEXELS_API_KEY not set!"); sys.exit(1)

    start = time.time()
    results, failures = [], []

    print("\n" + "═"*62)
    print(f"  🚀  FreakyBits Auto Pipeline")
    print(f"  📅  {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  🎬  3 videos × 4 runs/day = 12/day")
    print(f"  🎙️  Edge TTS neural | 🎥 Pexels 9:16 | 📝 Bold subtitles")
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
    print(f"  ✅  {len(results)}/3 videos  |  {elapsed//60}m {elapsed%60}s")
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
