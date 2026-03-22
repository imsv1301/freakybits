"""
FreakyBits Auto Pipeline v4.0
==============================
Stack: Gemini 2.5 Flash + Pexels HD + Edge TTS (fast neural) + FFmpeg subtitles
Style: Dark cinematic, bold word-by-word subtitles, 9:16 vertical, no voice gaps

NICHES (4):
  1. Horror Story   👻  — YouTube + Instagram (EN only)
  2. Comedy Facts   😂  — YouTube only
  3. AI Tools Talk  💬  — YouTube only
  4. Tech Drops     💻  — YouTube + Instagram (EN only, always)

UPLOAD RULES:
  YouTube  → ALL 4 niches → 4 videos/run × 4 runs = 16 videos/day
  Instagram → Tech Drops ONLY → 1 video/run × 4 runs = 4 reels/day

MASTER CONTROLLER SCRIPT STYLE (Tech Drops):
  - Hook in first 3 seconds (VERY strong)
  - Pattern interrupts: "Wait what?", "Bro no way"
  - Short subtitle-friendly lines
  - 20-30 seconds max
  - Sarcastic, witty, slightly dramatic
  - Gen-Z / tech audience
  - Gemini output → validate → improve → add hooks + sarcasm

NOTIFICATIONS: Telegram bot after every run
"""

import os, sys, json, time, pickle, datetime, subprocess, requests, asyncio, re
from pathlib import Path
from google import genai

# ── CONFIG ─────────────────────────────────────────────────────────
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY", "")
PEXELS_API_KEY     = os.environ.get("PEXELS_API_KEY", "")
INSTAGRAM_USERNAME = os.environ.get("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.environ.get("INSTAGRAM_PASSWORD", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8629033019:AAHlDft5_pPVwFs9DZxiUtsM0y_SXhUBhdI")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "7801226290")

VIDEOS_PER_RUN = 4       # 4 niches × 4 runs/day = 16 videos/day on YouTube
VIDEO_W        = 1080
VIDEO_H        = 1920    # 9:16 vertical

# ── LANGUAGE CONFIG ────────────────────────────────────────────────
LANG_PATTERN = ["en", "hi", "en", "en"]   # 4 slots for 4 niches per run
LANG_CONFIG  = {
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

# ── NICHES (4 active) ──────────────────────────────────────────────
NICHES = [
    {
        "name":             "horror_story",
        "label":            "Horror Story",
        "emoji":            "👻",
        "tone":             "slow, eerie, suspenseful — campfire ghost story that builds dread then delivers a chilling twist",
        "script_style":     "story",
        "music_volume":     "0.30",      # eerie music audible for horror
        "color_filter":     "curves=all='0/0 100/70 200/140 255/180'",
        "pexels_queries":   ["dark foggy forest night", "abandoned house interior dark",
                             "dark corridor horror", "cemetery moonlight fog"],
        "upload_instagram": True,        # uploads to Instagram
        "always_english":   False,       # can be Hindi
    },
    {
        "name":             "comedy_facts",
        "label":            "Comedy Facts",
        "emoji":            "😂",
        "tone":             "hilarious and shocking, punchline energy on every fact",
        "script_style":     "narrator",
        "music_volume":     "0.0",       # muted for algorithm
        "color_filter":     "curves=all='0/0 100/110 200/210 255/255'",
        "pexels_queries":   ["colorful confetti explosion", "people laughing fun outdoors",
                             "bright colorful balloons", "funny animals cute"],
        "upload_instagram": False,       # YouTube only
        "always_english":   False,
    },
    {
        "name":             "ai_tools_talk",
        "label":            "AI Tools Talk",
        "emoji":            "💬",
        "tone":             "two friends casually reacting to trending AI tools — Alex excited, Sam skeptical",
        "script_style":     "dialogue",
        "music_volume":     "0.0",
        "color_filter":     "colorchannelmixer=rr=0.6:gg=0.8:bb=1.0",
        "pexels_queries":   ["gaming setup neon lights dark", "computer screen gaming room",
                             "neon gaming background dark", "esports arena glowing"],
        "upload_instagram": False,       # YouTube only
        "always_english":   True,        # always English
    },
    {
        "name":             "tech_drops",
        "label":            "Tech Drops",
        "emoji":            "💻",
        "tone":             "sarcastic Gen-Z tech bro dropping hidden gems — fast, punchy, slightly dramatic",
        "script_style":     "tech_drops",
        "music_volume":     "0.0",
        "color_filter":     "colorchannelmixer=rr=0.5:gg=0.7:bb=1.2",
        "pexels_queries":   ["neon city cyberpunk dark", "futuristic technology glowing",
                             "hacker dark room screen", "digital matrix code dark"],
        "upload_instagram": True,        # Tech Drops → Instagram Reels
        "always_english":   True,        # always English (Gen-Z tone)
    },
]

# Songs per niche
TRENDING_SONGS_FREE = [
    {"niche": "horror_story",   "url": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3"},
    {"niche": "horror_story",   "url": "https://cdn.pixabay.com/download/audio/2021/09/06/audio_6ded321929.mp3"},
    {"niche": "comedy_facts",   "url": "https://cdn.pixabay.com/download/audio/2022/10/25/audio_946b736e00.mp3"},
    {"niche": "comedy_facts",   "url": "https://cdn.pixabay.com/download/audio/2022/01/20/audio_d0ee71a7e6.mp3"},
    {"niche": "ai_tools_talk",  "url": "https://cdn.pixabay.com/download/audio/2022/08/02/audio_2dde668d05.mp3"},
    {"niche": "ai_tools_talk",  "url": "https://cdn.pixabay.com/download/audio/2021/11/13/audio_cb31e6deb5.mp3"},
    {"niche": "tech_drops",     "url": "https://cdn.pixabay.com/download/audio/2022/08/02/audio_2dde668d05.mp3"},
    {"niche": "tech_drops",     "url": "https://cdn.pixabay.com/download/audio/2021/11/13/audio_cb31e6deb5.mp3"},
]

OUT              = Path("buzzBits_output")
OUT.mkdir(exist_ok=True)
PART1_TOPIC_FILE = OUT / "part1_topic.json"
USED_TOPICS_FILE = OUT / "used_topics.json"
ANALYTICS_FILE   = OUT / "analytics.json"
client           = genai.Client(api_key=GEMINI_API_KEY)


# ══════════════════════════════════════════════════════════════════
#  TOPIC DEDUPLICATION
# ══════════════════════════════════════════════════════════════════
def load_used_topics() -> dict:
    if not USED_TOPICS_FILE.exists():
        return {}
    try:
        with open(USED_TOPICS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_used_topic(topic: str, niche_name: str):
    topics = load_used_topics()
    key    = topic.lower().strip()
    topics[key] = {"niche": niche_name, "used_at": datetime.datetime.utcnow().isoformat()}
    if len(topics) > 500:
        oldest = sorted(topics.items(), key=lambda x: x[1].get("used_at", ""))[:100]
        for k, _ in oldest:
            del topics[k]
    with open(USED_TOPICS_FILE, "w", encoding="utf-8") as f:
        json.dump(topics, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════════
#  ANALYTICS LOGGER
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
        print(f"   📊 Analytics logged ({len(analytics)} total)")
    except Exception as e:
        print(f"   ⚠️  Analytics failed: {e}")


# ══════════════════════════════════════════════════════════════════
#  TELEGRAM NOTIFICATIONS
# ══════════════════════════════════════════════════════════════════
def send_notification(subject: str, body: str):
    """Send Telegram notification after each pipeline run."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        msg  = f"🎬 *{subject}*\n\n{body}"
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=10
        )
        if resp.status_code == 200:
            print("   📱 Telegram notification sent!")
        else:
            print(f"   ⚠️  Telegram failed: {resp.text[:100]}")
    except Exception as e:
        print(f"   ⚠️  Notification error: {e}")


# ══════════════════════════════════════════════════════════════════
#  SELECTORS
# ══════════════════════════════════════════════════════════════════
def pick_niche(video_index: int) -> dict:
    """Pick niche by video index — cycles through all 4 niches."""
    return NICHES[video_index % len(NICHES)]


def pick_language(video_index: int, niche: dict) -> dict:
    """Pick language — force English for niches that require it."""
    if niche.get("always_english"):
        return {"code": "en", **LANG_CONFIG["en"]}
    code = LANG_PATTERN[video_index % len(LANG_PATTERN)]
    return {"code": code, **LANG_CONFIG[code]}


def get_current_part(video_index: int):
    """Part 1/2 series — only for video index 2 (3rd video per run)."""
    if video_index != 2:
        return None
    hour = datetime.datetime.utcnow().hour
    for h in sorted(PART_SERIES_SCHEDULE):
        if hour <= h + 1:
            return PART_SERIES_SCHEDULE[h]
    return PART_SERIES_SCHEDULE[16]


def save_part1_topic(topic: str, niche_name: str, lang_code: str):
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
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════
#  STEP 1 — Generate Script (with web search + master controller)
# ══════════════════════════════════════════════════════════════════
def get_viral_angle(niche_name: str, niche_label: str) -> str:
    """Search web for trending viral angles for this niche."""
    try:
        queries = {
            "horror_story":  "viral horror story shorts reels 2025 trending",
            "comedy_facts":  "viral comedy facts shorts 2025 trending funny",
            "ai_tools_talk": "trending AI tools 2025 free viral shorts",
            "tech_drops":    "viral free GitHub repos AI tools productivity 2025",
        }
        query = queries.get(niche_name, f"viral {niche_label} shorts 2025")
        resp  = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"Accept": "application/json", "Accept-Encoding": "gzip",
                     "X-Subscription-Token": "BSAGzGTrqRiZBXc2KhpLfq9WlHPwORv"},
            params={"q": query, "count": 5},
            timeout=8
        )
        if resp.status_code == 200:
            results  = resp.json().get("web", {}).get("results", [])
            snippets = [r.get("description", "") for r in results[:3] if r.get("description")]
            if snippets:
                return "\nTRENDING CONTEXT (use to inspire your angle):\n" + " | ".join(snippets[:2])[:400]
    except Exception:
        pass

    fallbacks = {
        "horror_story":  "Trending: true paranormal encounters, sleep paralysis, real haunted locations",
        "comedy_facts":  "Trending: weird animal facts, bizarre laws, shocking historical blunders",
        "ai_tools_talk": "Trending: Sora, Gemini 2.5, Claude 3.7, Grok 3, free AI image generators",
        "tech_drops":    "Trending: free GitHub repos, hidden productivity tools, free AI websites no signup",
    }
    return "\nTRENDING CONTEXT: " + fallbacks.get(niche_name, "use the most viral angle possible")


def build_script_instructions(script_style: str, lang: dict, part, part1_data) -> tuple:
    """Build narration instructions, topic, tags, pexels hints per niche style."""

    part_instruction = ""
    if part == 1:
        part_instruction = (
            f'PART SERIES — THIS IS PART 1 of 2. '
            f'Narration MUST end with EXACTLY: "{lang["follow_part2"]}" — '
            f'this is mandatory, last spoken sentence. '
            f'Title ends with (Part 1). End on cliffhanger.'
        )
    elif part == 2:
        prev = part1_data.get("topic", "previous topic") if part1_data else "previous topic"
        part_instruction = (
            f'PART 2 of 2: Continue story from "{prev}". '
            f'Title ends with (Part 2). Give satisfying conclusion.'
        )

    if script_style == "story":
        narration = (
            "HORROR STORY FORMAT:\n"
            "Write like whispering a TRUE story to someone at 3am. Conversational but eerie.\n"
            "Structure:\n"
            "1. HOOK — first 5 words must make skin crawl. No 'Did you know'. Start with dread.\n"
            "2. BUILD — location, person, what they heard/saw — sensory, specific details.\n"
            "3. TWIST — the moment everything changed — delivered calmly, which makes it horrifying.\n"
            "4. HAUNTING END — one final sentence that lingers. Unresolved. Never fully explained.\n"
            "150-170 words. Sound like a true crime podcast host — calm, real, terrifying.\n"
            "ONE continuous paragraph. No line breaks. No filler."
        )
        topic     = "ONE specific real haunted location, true paranormal case, or urban legend. Name the place, year, person."
        tag_ext   = "#HorrorStory #ScaryStory #HorrorShorts #TrueHorror #Paranormal #ghost #haunted #scary #horrortok"
        ig_tags   = "#reels #viral #freakybits #horrorstory #scarystory #horror #ghost #paranormal #haunted #creepy #horrortok #scarytiktok #horrorreels #fyp #trending #explore #truecrime #supernatural #chilling #shorts"
        duration  = "55-65 seconds"
        pexels    = '["dark foggy forest night", "abandoned building interior dark", "cemetery dark fog", "dark corridor horror"]'

    elif script_style == "dialogue":
        narration = (
            "DIALOGUE FORMAT — always English:\n"
            "Two characters: Alex (hyped about AI) and Sam (skeptical, always asks if free).\n"
            "Format: \"Did you know [tool] exists? Alex: bro this AI just [does X]. "
            "Sam: wait is it free? Alex: [yes/no + detail]. Sam: [reaction]. "
            "Alex: Follow FreakyBits for more free AI drops!\"\n"
            "120-140 words. Sound like two friends texting — casual, punchy, funny.\n"
            "ONE continuous string, no line breaks."
        )
        topic     = "ONE specific trending AI tool from 2025 or 2026. Name it, its use, its price (free/paid)."
        tag_ext   = "#AITools #FreeAI #AIUpdates #NewAI #ArtificialIntelligence #TechTalk #AIShorts"
        ig_tags   = "#reels #viral #freakybits #aitools #freeai #artificialintelligence #techtalk #newai #aiupdates #technews #futuretech #shorts #fyp #trending #explore #reelsinstagram #viralreels #tech #airevolution #innovation"
        duration  = "40-50 seconds"
        pexels    = '["gaming setup neon dark", "esports arena glowing", "neon gaming room dark", "computer screen gaming"]'

    elif script_style == "tech_drops":
        narration = (
            "TECH DROPS MASTER CONTROLLER FORMAT — always English:\n"
            "You are an AI Automation Controller generating viral Gen-Z tech content.\n"
            "\nSTEP 1 — GENERATE with Gemini: Pick ONE topic from:\n"
            "  • Free GitHub repositories (AI tools, automation templates, coding hacks)\n"
            "  • Free AI tools & websites (no signup, unlimited)\n"
            "  • Hidden productivity tools most people don't know exist\n"
            "\nSTEP 2 — VALIDATE & IMPROVE the output:\n"
            "  • Add stronger hook in first 3 seconds\n"
            "  • Add sarcasm and humor\n"
            "  • Make it A/B dialogue style (Person A drops knowledge, Person B reacts)\n"
            "  • Ensure fast pacing — every line punchy\n"
            "\nSTEP 3 — WRITE the final script:\n"
            "  Format: A/B dialogue. Example:\n"
            "  \"Bro wait — this GitHub repo just [does X] for FREE. [B: No way]. "
            "  I'm not done — it also [does Y]. [B: Bro no way]. "
            "  And it's open source. [B: Wait what?]. "
            "  Follow FreakyBits — I drop these daily.\"\n"
            "  Use pattern interrupts: 'Wait what?', 'Bro no way', 'Hold on—'\n"
            "  Keep lines SHORT — subtitle friendly.\n"
            "  20-30 seconds max. 60-80 words total.\n"
            "  Tone: sarcastic, witty, slightly dramatic.\n"
            "  Audience: Gen-Z tech people who love free tools.\n"
            "  ONE continuous string, no line breaks."
        )
        topic     = "ONE specific free GitHub repo, free AI website, or hidden productivity tool. Must be real and working."
        tag_ext   = "#TechDrops #FreeTools #GitHub #FreeAI #ProductivityHacks #CodingTips #TechTips #HiddenGems"
        ig_tags   = "#reels #viral #freakybits #techdrops #freetools #github #freeai #productivity #codinglife #techhacks #shortcuts #aitools #devtools #nocode #automation #fyp #trending #explore #genZ #techbro"
        duration  = "20-30 seconds"
        pexels    = '["neon city cyberpunk dark", "futuristic technology glowing", "hacker dark room screen", "digital matrix code"]'

    else:
        # Comedy narrator
        narration = (
            "COMEDY FACTS FORMAT: Start with 'Did you know' — then deliver 4 shocking funny facts "
            "like texting a friend who loves weird trivia. "
            "Add reactions: 'I know right?', 'wait it gets better', 'no seriously'. "
            "120-140 words. ONE continuous string. End with 'Follow FreakyBits for more wild facts!'"
        )
        topic     = "Fresh specific topic — shocking, funny, unbelievable. No overused examples."
        tag_ext   = "#Facts #mindblown #didyouknow #amazingfacts #funnyfacts #comedy"
        ig_tags   = "#reels #viral #freakybits #shorts #fyp #trending #facts #explore #reelsinstagram #reelsviral #mindblown #amazingfacts #didyouknow #funnyfacts #comedy #foryou"
        duration  = "40-50 seconds"
        pexels    = '["colorful confetti explosion", "people laughing outdoors", "bright colorful balloons", "funny animals cute"]'

    return narration, topic, tag_ext, ig_tags, duration, pexels, part_instruction


def generate_content(niche: dict, video_index: int, lang: dict, part=None, part1_data=None) -> dict:
    lang_code  = lang["code"]
    lang_label = lang["label"]
    print(f"\n🤖 [{niche['label']}] [{lang_label}]" + (f" [Part {part}]" if part else ""))

    today        = datetime.datetime.utcnow().strftime("%B %d, %Y")
    script_style = niche.get("script_style", "narrator")

    lang_instruction = (
        "LANGUAGE: Write EVERYTHING in Hindi (Devanagari). Hashtags stay English."
        if lang_code == "hi" else "LANGUAGE: English throughout."
    )

    # Topic dedup
    used      = load_used_topics()
    recent    = list(used.keys())[-10:] if used else []
    avoid_str = (f"\nAVOID these recently used topics: {', '.join(recent)}" if recent else "")

    # Web search for viral angle
    print(f"   🔍 Searching viral angles for [{niche['label']}]...")
    viral_context = get_viral_angle(niche["name"], niche["label"])

    # Build instructions
    narration_instruction, topic_instruction, tag_ext, ig_tags, duration_note, pexels_hint, part_instruction = (
        build_script_instructions(script_style, lang, part, part1_data)
    )

    prompt = f"""You are a world-class viral short-form video scriptwriter AND an AI Automation Controller.
Your scripts feel like a friend excitedly telling you something insane — never robotic.

Niche: {niche['label']} {niche['emoji']} | Date: {today} | Duration: {duration_note}
{lang_instruction}
{part_instruction}
{avoid_str}
{viral_context}

TASK: {topic_instruction}

SCRIPT REQUIREMENTS:
{narration_instruction}

WRITING RULES (CRITICAL):
- Sound like MrBeast or a viral Gen-Z creator — energetic, human, real
- Use short punchy sentences mixed with longer ones
- Conversational words: "Okay so", "Here's the thing", "Wait — it gets worse", "And get this"
- Reactions: "I know, sounds crazy", "No seriously", "That's not even the weirdest part"
- NEVER sound robotic. NEVER list facts dryly.
- Comedy/AI facts: MUST start with "Did you know"
- Horror: start with immediate dread — no "Did you know"
- Tech Drops: start with "Bro wait—" or "Okay real talk—" or similar Gen-Z opener
- End ALWAYS with spoken CTA: facts → "Follow FreakyBits for more!", Part 1 → EXACT follow_part2 phrase
- ONE continuous string for narration — no line breaks, no bullet points

Reply ONLY in valid JSON (no markdown, no extra text):
{{
  "topic": "specific topic/tool/story name",
  "language": "{lang_code}",
  "part": {part if part else "null"},
  "youtube_title": "viral title under 60 chars — curiosity or shock",
  "youtube_description": "3 conversational punchy sentences.\\n\\nSubscribe for daily {niche['label']} {niche['emoji']}!\\n\\n",
  "youtube_viral_caption": "hook under 10 words with emoji",
  "youtube_trending_tags": "#Shorts #Viral #FreakyBits #{niche['name']} {tag_ext} #YouTubeShorts #trending #fyp #shortsvideo #reels #viralvideo",
  "youtube_tags": ["FreakyBits", "Shorts", "Viral", "{niche['name']}", "trending", "fyp", "mindblown", "viral"],
  "instagram_caption": "punchy IG caption 150 chars max with emojis — conversational",
  "instagram_viral_caption": "Reels hook 12 words max 2-3 emojis",
  "instagram_trending_tags": "{ig_tags}",
  "trending_yt_song": "popular song - artist matching niche mood",
  "trending_ig_song": "popular song - artist matching niche mood",
  "narration": "WRITE FULL NARRATION HERE — conversational, human, not robotic",
  "pexels_queries": {pexels_hint}
}}"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            raw      = response.text.strip().replace("```json", "").replace("```", "").strip()
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
#  STEP 2 — Edge TTS voiceover
# ══════════════════════════════════════════════════════════════════
def generate_voiceover(content: dict, video_idx: int, lang: dict, niche: dict) -> Path:
    voice_settings = dict(lang)
    if niche.get("name") == "horror_story":
        voice_settings.update(HORROR_VOICE_OVERRIDE.get(lang["code"], {}))
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
        print(f"   ✅ Voice: {audio_path.name} ({audio_path.stat().st_size // 1024}KB)")
    except Exception as e:
        print(f"   ⚠️  Edge TTS failed: {e} — gTTS fallback")
        from gtts import gTTS
        gTTS(text=narration, lang=lang["code"], slow=False).save(str(audio_path))
        print(f"   ✅ gTTS fallback done")

    return audio_path


# ══════════════════════════════════════════════════════════════════
#  STEP 3 — Subtitles
# ══════════════════════════════════════════════════════════════════
def generate_subtitles(content: dict, audio_path: Path, video_idx: int) -> Path:
    print(f"   📝 Generating subtitles...")
    srt_path = OUT / f"subs_{video_idx:02d}.srt"

    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)
    ], capture_output=True, text=True)
    total_duration = float(probe.stdout.strip() or 32)

    words          = content["narration"].strip().split()
    chunk_size     = 4
    chunks         = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
    chunk_duration = total_duration / max(len(chunks), 1)

    def ts(s: float) -> str:
        h   = int(s // 3600)
        m   = int((s % 3600) // 60)
        sec = int(s % 60)
        ms  = int((s - int(s)) * 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    lines = []
    for i, chunk in enumerate(chunks):
        start = i * chunk_duration
        end   = (i + 1) * chunk_duration - 0.05
        lines += [str(i + 1), f"{ts(start)} --> {ts(end)}", chunk.upper(), ""]

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"   ✅ {len(chunks)} subtitle chunks generated")
    return srt_path


# ══════════════════════════════════════════════════════════════════
#  STEP 4 — Pexels clips
# ══════════════════════════════════════════════════════════════════
def fetch_pexels_clip(query: str, video_idx: int, clip_idx: int) -> Path | None:
    clip_path = OUT / f"clip_{video_idx:02d}_{clip_idx:02d}.mp4"
    print(f"      🔍 '{query}'")
    headers   = {"Authorization": PEXELS_API_KEY}

    for orientation in ["portrait", "landscape"]:
        try:
            resp = requests.get(
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


def fetch_all_clips(content: dict, niche: dict, video_idx: int) -> list:
    queries     = content.get("pexels_queries", [])
    all_queries = (queries + niche["pexels_queries"])[:4]
    while len(all_queries) < 4:
        all_queries = (all_queries * 2)[:4]

    print(f"\n   🎬 Fetching 4 Pexels clips (9:16 portrait)...")
    clips = []
    for i, query in enumerate(all_queries):
        clip = fetch_pexels_clip(query, video_idx, i)
        if not clip:
            clip = fetch_pexels_clip(niche["pexels_queries"][i % len(niche["pexels_queries"])],
                                     video_idx + 10, i)
        if clip:
            clips.append(clip)
        time.sleep(0.3)

    if not clips:
        raise RuntimeError("All Pexels clips failed — check PEXELS_API_KEY")
    print(f"   ✅ {len(clips)}/4 clips ready")
    return clips


# ══════════════════════════════════════════════════════════════════
#  STEP 5 — Trending song
# ══════════════════════════════════════════════════════════════════
def get_trending_song(niche_name: str, video_idx: int) -> Path | None:
    candidates = [s for s in TRENDING_SONGS_FREE if s["niche"] == niche_name] or TRENDING_SONGS_FREE
    song       = candidates[video_idx % len(candidates)]
    song_path  = OUT / f"song_{video_idx:02d}.mp3"
    try:
        r = requests.get(song["url"], timeout=30, stream=True)
        r.raise_for_status()
        with open(song_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        print(f"   ✅ Song ({song_path.stat().st_size // 1024}KB)")
        return song_path
    except Exception as e:
        print(f"   ⚠️  Song failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
#  STEP 6 — Assemble video
# ══════════════════════════════════════════════════════════════════
def process_clip(clip_path: Path, output_path: Path, niche: dict, duration: float = 8.0) -> Path:
    color_filter = niche.get("color_filter", "curves=all='0/0 100/90 200/185 255/240'")
    vf = (
        f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase,"
        f"crop={VIDEO_W}:{VIDEO_H},setsar=1,{color_filter},unsharp=5:5:0.8:3:3:0"
    )
    ret = subprocess.run([
        "ffmpeg", "-y", "-i", str(clip_path), "-t", str(duration),
        "-vf", vf, "-r", "30", "-c:v", "libx264", "-preset", "fast",
        "-crf", "22", "-pix_fmt", "yuv420p", "-an", str(output_path)
    ], capture_output=True)
    if ret.returncode != 0:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(clip_path), "-t", str(duration),
            "-vf", f"scale={VIDEO_W}:{VIDEO_H},setsar=1", "-an", str(output_path)
        ], capture_output=True)
    return output_path


def burn_subtitles(video_path: Path, srt_path: Path, output_path: Path) -> Path:
    sub_filter = (
        f"subtitles={srt_path}:force_style='"
        f"FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00000000,BackColour=&H80000000,"
        f"Bold=1,Outline=3,Shadow=2,Alignment=2,MarginV=80'"
    )
    ret = subprocess.run([
        "ffmpeg", "-y", "-i", str(video_path), "-vf", sub_filter,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "copy", str(output_path)
    ], capture_output=True)
    if ret.returncode == 0:
        print("   ✅ Subtitles burned")
        return output_path
    print("   ⚠️  Subtitle burn failed — using video without subs")
    return video_path


def assemble_video(clip_paths: list, audio_path: Path, srt_path: Path | None,
                   video_idx: int, niche: dict, song_path: Path | None = None) -> Path:
    print("   ✂️  Assembling 9:16 cinematic video...")
    final_path = OUT / f"freakyBits_{video_idx:02d}.mp4"

    # Process clips
    processed = []
    for i, cp in enumerate(clip_paths):
        pp = OUT / f"proc_{video_idx:02d}_{i:02d}.mp4"
        process_clip(cp, pp, niche, 8.0)
        if pp.exists() and pp.stat().st_size > 1000:
            processed.append(pp)

    if not processed:
        raise RuntimeError("No processed clips available")

    while len(processed) < 4:
        processed.append(processed[-1])

    # Concatenate
    concat_file = OUT / f"concat_{video_idx:02d}.txt"
    with open(concat_file, "w") as f:
        for pp in processed:
            f.write(f"file '{pp.resolve()}'\n")

    merged = OUT / f"merged_{video_idx:02d}.mp4"
    ret    = subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file), "-c", "copy", str(merged)
    ], capture_output=True)
    if ret.returncode != 0:
        raise RuntimeError(f"Concat failed: {ret.stderr.decode()[:200]}")

    # Mix audio
    with_audio   = OUT / f"audio_{video_idx:02d}.mp4"
    music_volume = niche.get("music_volume", "0.0")
    if song_path and song_path.exists():
        ret = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(merged), "-i", str(audio_path), "-i", str(song_path),
            "-filter_complex",
            f"[1:a]volume=1.0[vo];[2:a]volume={music_volume}[vs];[vo][vs]amix=inputs=2:duration=first[a]",
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
        raise RuntimeError("Audio mix failed")

    # Burn subtitles (skip for Hindi)
    if srt_path is not None:
        final_path = burn_subtitles(with_audio, srt_path, final_path)
    else:
        final_path = with_audio
        print("   ⏭️  No subtitles for Hindi video")

    # Stats
    probe    = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(final_path)
    ], capture_output=True, text=True)
    duration = float(probe.stdout.strip() or 0)
    size_mb  = Path(final_path).stat().st_size / (1024 * 1024)
    print(f"   ✅ {Path(final_path).name} — {duration:.1f}s, {size_mb:.1f}MB, 9:16 vertical")
    return Path(final_path)


# ══════════════════════════════════════════════════════════════════
#  STEP 7A — YouTube Upload (all 4 niches)
# ══════════════════════════════════════════════════════════════════
def upload_youtube(video_path: Path, content: dict) -> str | None:
    print("   📺 Uploading to YouTube...")
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.auth.transport.requests import Request
    except ImportError:
        print("   ❌ google libs missing")
        return None

    tok_file = OUT / "yt_token.pickle"
    creds    = None
    if tok_file.exists():
        with open(tok_file, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("   ❌ No valid YouTube token")
            return None
        with open(tok_file, "wb") as f:
            pickle.dump(creds, f)

    yt = build("youtube", "v3", credentials=creds)

    for attempt in range(1, 4):
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
                        "privacyStatus":             "public",
                        "selfDeclaredMadeForKids":   False,
                    }
                },
                media_body=MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=-1, resumable=True)
            ).execute()
            url = f"https://youtube.com/watch?v={resp['id']}"
            print(f"   ✅ YouTube → {url}")
            return url
        except Exception as e:
            if attempt < 3:
                wait = 2 ** attempt
                print(f"   ⚠️  Attempt {attempt} failed: {e} — retry in {wait}s")
                time.sleep(wait)
            else:
                print(f"   ❌ YouTube upload failed: {e}")
                return None


# ══════════════════════════════════════════════════════════════════
#  STEP 7B — Instagram Upload (Tech Drops niche only)
# ══════════════════════════════════════════════════════════════════
def upload_instagram(video_path: Path, content: dict) -> str | None:
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        print("   ⚠️  Instagram skipped — set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in .env")
        return None

    print("   📸 Uploading to Instagram Reels via instagrapi...")
    try:
        from instagrapi import Client
        cl      = Client()
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        caption = content.get("instagram_caption_final", content.get("instagram_caption", ""))
        media   = cl.clip_upload(str(video_path), caption)
        url     = f"https://www.instagram.com/reel/{media.code}/"
        print(f"   ✅ Instagram Reel → {url}")
        cl.logout()
        return url
    except Exception as e:
        print(f"   ❌ Instagram upload failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
#  SINGLE VIDEO PIPELINE
# ══════════════════════════════════════════════════════════════════
def make_one_video(video_idx: int) -> dict:
    niche = pick_niche(video_idx)
    lang  = pick_language(video_idx, niche)
    part  = get_current_part(video_idx)
    part1_data = load_part1_topic() if part == 2 else None

    print(f"\n{'─'*62}")
    print(f"  VIDEO {video_idx+1}/{VIDEOS_PER_RUN}  |  {niche['label']} {niche['emoji']}  |  {lang['label']}"
          + (f"  |  Part {part}" if part else ""))
    print(f"{'─'*62}")

    content = generate_content(niche, video_idx, lang, part, part1_data)
    audio   = generate_voiceover(content, video_idx, lang, niche)

    # Skip subtitles for Hindi
    if lang["code"] == "hi":
        srt = None
        print("   ⏭️  Subtitles skipped for Hindi video")
    else:
        srt = generate_subtitles(content, audio, video_idx)

    clips   = fetch_all_clips(content, niche, video_idx)
    song    = get_trending_song(niche["name"], video_idx)
    video   = assemble_video(clips, audio, srt, video_idx, niche, song)

    # YouTube — ALL 4 niches upload to YouTube
    yt_url  = upload_youtube(video, content)

    # Instagram — ONLY niches with upload_instagram=True AND English
    ig_url = None
    if niche.get("upload_instagram") and lang["code"] == "en":
        ig_url = upload_instagram(video, content)
    elif niche.get("upload_instagram") and lang["code"] != "en":
        print(f"   ⏭️  Instagram skipped for Hindi {niche['label']} video")
    else:
        print(f"   ⏭️  Instagram not enabled for {niche['label']} niche")

    if part == 1:
        save_part1_topic(content["topic"], niche["name"], lang["code"])
    save_used_topic(content["topic"], niche["name"])

    result = {
        "video":     str(video),
        "niche":     niche["label"],
        "language":  lang["label"],
        "part":      part,
        "topic":     content["topic"],
        "title":     content["youtube_title"],
        "youtube":   yt_url,
        "instagram": ig_url,
    }

    log_analytics(result)

    # Telegram notification per video
    status = "✅ SUCCESS" if yt_url else "⚠️ PARTIAL"
    send_notification(
        f"FreakyBits {status} — {niche['label']}",
        f"Title: {content['youtube_title']}\nTopic: {content['topic']}\n"
        f"YouTube: {yt_url or 'Failed ❌'}\nInstagram: {ig_url or 'Skipped ⏭️'}\n"
        f"Time: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    )
    return result


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

    start             = time.time()
    results, failures = [], []

    print("\n" + "═" * 62)
    print(f"  🚀  FreakyBits Auto Pipeline v4.0")
    print(f"  📅  {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  🎬  4 niches × 4 runs/day = 16 YT videos/day")
    print(f"  📸  Tech Drops → Instagram Reels (4/day)")
    print(f"  🎙️  Edge TTS neural | 🎥 Pexels 9:16 | 📝 Bold subtitles")
    print("═" * 62)

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
            failures.append({"index": i + 1, "error": str(e)})

    elapsed = round(time.time() - start)
    print("\n" + "═" * 62)
    print(f"  ✅  {len(results)}/{VIDEOS_PER_RUN} videos  |  {elapsed//60}m {elapsed%60}s")
    print("═" * 62)

    for r in results:
        part_str = f" | Part {r['part']}" if r.get("part") else ""
        print(f"\n  [{r['niche']}][{r['language']}]{part_str} {r['title']}")
        print(f"  📺 {r['youtube']}")
        if r.get("instagram"):
            print(f"  📸 {r['instagram']}")

    if failures:
        print(f"\n  ⚠️  {len(failures)} failed:")
        for f in failures:
            print(f"  Video {f['index']}: {f['error']}")

    # Final Telegram run summary
    success_count = len(results)
    fail_count    = len(failures)
    ig_count      = sum(1 for r in results if r.get("instagram"))
    send_notification(
        f"FreakyBits Run Complete — {success_count}/{VIDEOS_PER_RUN} ✅",
        f"YouTube uploads: {success_count}\nInstagram Reels: {ig_count}\n"
        f"Failed: {fail_count}\nTime taken: {elapsed//60}m {elapsed%60}s\n"
        f"Next run: auto via cron"
    )

    log = OUT / f"log_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M')}.json"
    with open(log, "w") as f:
        json.dump({"results": results, "failures": failures, "elapsed_s": elapsed}, f, indent=2)

    if failures and len(failures) == VIDEOS_PER_RUN:
        sys.exit(1)


if __name__ == "__main__":
    main()
