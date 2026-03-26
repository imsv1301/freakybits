"""
FreakyBits Auto Pipeline v4.1
==============================
Stack: Gemini 2.5 Flash + Pexels HD + Edge TTS (fast neural) + FFmpeg subtitles
Style: Dark cinematic, bold word-by-word subtitles, 9:16 vertical, no voice gaps
NICHES (4):
  1. Horror Story   👻  — YouTube ONLY (night run: 10PM IST only)
  2. Comedy Facts   😂  — YouTube ONLY (day runs: 7AM/12PM/6PM, random)
  3. AI Tools Talk  💬  — YouTube ONLY (day runs: 7AM/12PM/6PM, random)
  4. Tech Drops     💻  — YouTube + Instagram (EVERY run, slot 1)
UPLOAD RULES:
  YouTube  → 2 niches/run × 4 runs = 8 videos/day
             Slot 0: Horror (10PM only) | Comedy/AI random (other runs)
             Slot 1: Tech Drops always
  Instagram → Tech Drops ONLY → 1 reel/run × 4 runs = 4 reels/day
IMAGE PIPELINE (python3 pipeline.py image):
  3 niches: AI Trends, Harsh Life Truth, Did You Know
  10 images/day total (run once at 9AM IST via cron)
  YouTube Community Tab → 10 posts/day
  Instagram Posts → same 10 images as carousels
MASTER CONTROLLER SCRIPT STYLE (Tech Drops):
  - Hook in first 3 seconds (VERY strong)
  - Pattern interrupts: "Wait what?", "Bro no way"
  - Short subtitle-friendly lines
  - 20-30 seconds max
  - Sarcastic, witty, slightly dramatic
  - Gen-Z / tech audience
  - Gemini output → validate → improve → add hooks + sarcasm
NOTIFICATIONS: Telegram bot after every run
USAGE:
  python3 pipeline.py video   ← run video pipeline (4 videos)
  python3 pipeline.py image   ← run image pipeline (10 images)
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
VIDEOS_PER_RUN = 2
VIDEO_W        = 1080
VIDEO_H        = 1920
LANG_PATTERN = ["en", "hi", "en", "en"]
LANG_CONFIG  = {
    "en": {
        "label":        "English",
        "edge_voice":   "en-US-AndrewNeural",
        "edge_rate":    "+35%",
        "follow_part2": "Follow for Part 2!",
    },
    "hi": {
        "label":        "Hindi",
        "edge_voice":   "hi-IN-MadhurNeural",
        "edge_rate":    "+25%",
        "follow_part2": "Part 2 ke liye follow karo!",
    },
}
HORROR_VOICE_OVERRIDE = {
    "en": {"edge_voice": "en-US-AndrewNeural", "edge_rate": "+0%"},
    "hi": {"edge_voice": "hi-IN-MadhurNeural", "edge_rate": "-5%"},
}
TWO_VOICE_CONFIG = {
    "dialogue": {
        "voice_a": {"name": "Alex", "edge_voice": "en-US-AndrewNeural",      "edge_rate": "+35%"},
        "voice_b": {"name": "Sam",  "edge_voice": "en-US-ChristopherNeural", "edge_rate": "+30%"},
    },
    "tech_drops": {
        "voice_a": {"name": "Jake", "edge_voice": "en-US-AndrewNeural",      "edge_rate": "+40%"},
        "voice_b": {"name": "Ryan", "edge_voice": "en-US-ChristopherNeural", "edge_rate": "+35%"},
    },
}
PART_SERIES_SCHEDULE = {1: 1, 6: 2, 12: 1, 16: 2}
NICHES = [
    {
        "name":             "horror_story",
        "label":            "Horror Story",
        "emoji":            "👻",
        "tone":             "slow, eerie, suspenseful — campfire ghost story that builds dread then delivers a chilling twist",
        "script_style":     "story",
        "music_volume":     "0.65",
        "color_filter":     "curves=all='0/0 100/70 200/140 255/180'",
        "pexels_queries":   ["dark foggy forest night", "abandoned house interior dark",
                             "dark corridor horror", "cemetery moonlight fog"],
        "upload_instagram": False,
        "always_english":   False,
    },
    {
        "name":             "comedy_facts",
        "label":            "Comedy Facts",
        "emoji":            "😂",
        "tone":             "hilarious and shocking, punchline energy on every fact",
        "script_style":     "narrator",
        "music_volume":     "0.0",
        "color_filter":     "curves=all='0/0 100/110 200/210 255/255'",
        "pexels_queries":   ["colorful confetti explosion", "people laughing fun outdoors",
                             "bright colorful balloons", "funny animals cute"],
        "upload_instagram": False,
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
        "upload_instagram": False,
        "always_english":   True,
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
        "upload_instagram": True,
        "always_english":   True,
    },
]
IMAGE_NICHES = [
    {
        "name":  "ai_trends",
        "label": "AI Trends",
        "emoji": "🤖",
        "count": 4,
        "prompt_style": (
            "Create a bold, viral, eye-catching social media image concept about a trending AI topic in 2026. "
            "Format: ONE attention-grabbing headline (max 8 words, ALL CAPS), "
            "ONE subtext line (max 12 words, sentence case), "
            "and a background description for a dark futuristic aesthetic with neon blue/purple accents. "
            "Make it feel like breaking tech news."
        ),
        "yt_community_prefix": "🤖 AI Trends Update",
        "ig_hashtags": "#AITrends #ArtificialIntelligence #FutureAI #TechNews #AITools #MachineLearning #AIUpdates #TechDrops #FreakyBits #viral #trending #explore #fyp",
    },
    {
        "name":  "harsh_life_truth",
        "label": "Harsh Life Truth",
        "emoji": "💀",
        "count": 3,
        "prompt_style": (
            "Create a bold, viral, motivational/harsh truth social media image concept. "
            "Format: ONE brutal honest truth statement (max 8 words, ALL CAPS), "
            "ONE supporting line (max 12 words, sentence case), "
            "and a background description for a dark minimalist aesthetic with red/orange accents. "
            "Make it feel like something that stops people mid-scroll and hits hard."
        ),
        "yt_community_prefix": "💀 Harsh Truth",
        "ig_hashtags": "#HarshTruth #LifeAdvice #Motivation #RealTalk #MindsetShift #SelfImprovement #HardFacts #FreakyBits #viral #trending #explore #fyp",
    },
    {
        "name":  "did_you_know",
        "label": "Did You Know",
        "emoji": "🤯",
        "count": 3,
        "prompt_style": (
            "Create a bold, viral, mind-blowing 'Did You Know?' social media image concept. "
            "Format: Start with 'DID YOU KNOW?' as the header, "
            "ONE shocking fact statement (max 10 words, mixed case with emphasis), "
            "ONE wow-reaction line (max 10 words), "
            "and a background description for a bright colorful pop aesthetic. "
            "Make it completely unbelievable but real."
        ),
        "yt_community_prefix": "🤯 Mind-Blowing Fact",
        "ig_hashtags": "#DidYouKnow #MindBlown #AmazingFacts #CrazyFacts #WTFFacts #FunFacts #FreakyBits #viral #trending #explore #fyp #facts",
    },
]
TRENDING_SONGS_FREE = [
    {"niche": "horror_story",   "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3"},
    {"niche": "horror_story",   "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3"},
    {"niche": "comedy_facts",   "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-3.mp3"},
    {"niche": "comedy_facts",   "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-4.mp3"},
    {"niche": "ai_tools_talk",  "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-5.mp3"},
    {"niche": "ai_tools_talk",  "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-6.mp3"},
    {"niche": "tech_drops",     "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-7.mp3"},
    {"niche": "tech_drops",     "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-8.mp3"},
]
OUT              = Path("freakybits_output")
OUT.mkdir(exist_ok=True)
(OUT / "logs").mkdir(exist_ok=True)
(OUT / "images").mkdir(exist_ok=True)
PART1_TOPIC_FILE = OUT / "part1_topic.json"
USED_TOPICS_FILE = OUT / "used_topics.json"
ANALYTICS_FILE   = OUT / "analytics.json"
client           = genai.Client(api_key=GEMINI_API_KEY)
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
def send_notification(subject: str, body: str):
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
NICHE_BY_NAME = {n["name"]: n for n in NICHES}
DAY_NICHES      = ["comedy_facts", "ai_tools_talk", "horror_story"]
NIGHT_UTC_HOURS = range(16, 19)

def _is_night_run() -> bool:
    return datetime.datetime.utcnow().hour in NIGHT_UTC_HOURS

def pick_niche(video_index: int) -> dict:
    """
    Slot-based deterministic niche selection:
    Slot 1 (video_index==1): ALWAYS Tech Drops
    Slot 0 (video_index==0): Rotate through ALL 3 niches based on hour
      - 1:30 UTC  (7AM IST)  → Comedy Facts
      - 6:30 UTC  (12PM IST) → AI Tools Talk
      - 12:30 UTC (6PM IST)  → Horror Story
      - 16:30 UTC (10PM IST) → Horror Story (night run)
    """
    if video_index == 1:
        return NICHE_BY_NAME["tech_drops"]
    hour = datetime.datetime.utcnow().hour
    # Deterministic rotation based on UTC hour
    if hour in range(0, 4):      # 7AM IST
        return NICHE_BY_NAME["comedy_facts"]
    elif hour in range(4, 9):    # 12PM IST
        return NICHE_BY_NAME["ai_tools_talk"]
    elif hour in range(9, 14):   # 6PM IST
        return NICHE_BY_NAME["comedy_facts"]
    else:                         # 10PM IST (night)
        return NICHE_BY_NAME["horror_story"]
def pick_language(video_index: int, niche: dict) -> dict:
    if niche.get("always_english"):
        return {"code": "en", **LANG_CONFIG["en"]}
    code = LANG_PATTERN[video_index % len(LANG_PATTERN)]
    return {"code": code, **LANG_CONFIG[code]}
def get_current_part(video_index: int):
    return None
def save_part1_topic(topic: str, niche_name: str, lang_code: str):
    data = {"topic": topic, "niche": niche_name, "lang": lang_code,
            "saved_at": datetime.datetime.utcnow().isoformat()}
    with open(PART1_TOPIC_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
def load_part1_topic():
    if not PART1_TOPIC_FILE.exists():
        return None
    try:
        with open(PART1_TOPIC_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None
def get_viral_angle(niche_name: str, niche_label: str) -> str:
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
def build_script_instructions(script_style, lang, part, part1_data):
    part_instruction = ""
    if part == 1:
        part_instruction = (
            f'PART SERIES — THIS IS PART 1 of 2. '
            f'Narration MUST end with EXACTLY: "{lang["follow_part2"]}" — '
            f'this is mandatory, last spoken sentence. Title ends with (Part 1). End on cliffhanger.'
        )
    elif part == 2:
        prev = part1_data.get("topic", "previous topic") if part1_data else "previous topic"
        part_instruction = f'PART 2 of 2: Continue story from "{prev}". Title ends with (Part 2). Give satisfying conclusion.'
    if script_style == "story":
        narration = (
            "HORROR STORY FORMAT — Write for SPOKEN audio delivery, not reading.\n"
            "Use these TTS emotion markers:\n"
            "  • ... for a chilling pause (use 3-4 times for dramatic effect)\n"
            "  • — for a sudden interruption or realization\n"
            "  • ! for a moment of shock (use sparingly, max 2)\n"
            "  • CAPITALIZE a word for emphasis\n\n"
            "Structure (ONE continuous paragraph, 150-170 words):\n"
            "1. HOOK — 5 words max, immediate dread. Example: 'Nobody checked the basement... ever.'\n"
            "2. BUILD — sensory details, creeping dread. Whisper-paced sentences.\n"
            "3. TWIST — delivered CALMLY which makes it MORE terrifying.\n"
            "4. HAUNTING END — one unresolved sentence that lingers.\n\n"
            "Example opening: 'The babysitter heard breathing... but the children were asleep.'\n"
            "Sound like a true crime podcast host — calm, measured, bone-chilling."
        )
        topic   = "ONE specific real haunted location, true paranormal case, or urban legend."
        tag_ext = "#HorrorStory #ScaryStory #HorrorShorts #TrueHorror #Paranormal #ghost #haunted #scary #horrortok"
        ig_tags = "#reels #viral #freakybits #horrorstory #scarystory #horror #ghost #paranormal #haunted #creepy #horrortok #fyp #trending #explore #truecrime #supernatural #chilling #shorts"
        duration = "55-65 seconds"
        pexels  = '["dark foggy forest night", "abandoned building interior dark", "cemetery dark fog", "dark corridor horror"]'
    elif script_style == "dialogue":
        narration = (
            "DIALOGUE FORMAT — always English.\nTwo characters:\n  [Alex] — hyped, drops wild AI facts\n  [Sam]  — skeptical, always asks 'is it free?'\n\n"
            "RULES:\n1. Mark EVERY line with [Alex] or [Sam]\n2. Lines 8-12 words max\n3. Strictly alternate\n4. Total 100-120 words\n\n"
            "EXAMPLE:\n[Alex] Bro did you know this AI writes entire code?\n[Sam] No way, is it free?\n[Alex] Completely free, no signup.\n[Sam] That can't be real.\n[Alex] Follow FreakyBits, I drop these daily."
        )
        topic   = "ONE specific trending AI tool from 2025 or 2026."
        tag_ext = "#AITools #FreeAI #AIUpdates #NewAI #ArtificialIntelligence #TechTalk #AIShorts"
        ig_tags = "#reels #viral #freakybits #aitools #freeai #artificialintelligence #techtalk #newai #fyp #trending #explore"
        duration = "40-50 seconds"
        pexels  = '["gaming setup neon dark", "esports arena glowing", "neon gaming room dark", "computer screen gaming"]'
    elif script_style == "tech_drops":
        narration = (
            "TECH DROPS MASTER CONTROLLER — always English.\nTwo characters:\n  [Jake] — knows the tool, slightly dramatic\n  [Ryan] — reactive, Gen-Z, short punchy reactions\n\n"
            "RULES:\n1. Mark EVERY line with [Jake] or [Ryan]\n2. Lines 6-10 words max\n3. Strictly alternate\n4. Total 60-80 words, 20-30 seconds\n\n"
            "EXAMPLE:\n[Jake] Bro this GitHub repo does X for free.\n[Ryan] No way.\n[Jake] It also does Y.\n[Ryan] Bro no way.\n[Jake] Open source, zero cost.\n[Ryan] Wait what?\n[Jake] Follow FreakyBits, I drop these daily."
        )
        topic   = "ONE specific free GitHub repo, free AI website, or hidden productivity tool. Must be real."
        tag_ext = "#TechDrops #FreeTools #GitHub #FreeAI #ProductivityHacks #CodingTips #TechTips #HiddenGems"
        ig_tags = "#reels #viral #freakybits #techdrops #freetools #github #freeai #productivity #codinglife #fyp #trending #explore #genZ"
        duration = "20-30 seconds"
        pexels  = '["neon city cyberpunk dark", "futuristic technology glowing", "hacker dark room screen", "digital matrix code"]'
    else:
        narration = (
            "COMEDY FACTS FORMAT — Write for SPOKEN audio delivery with ENERGY!\n"
            "Use these TTS emotion markers:\n"
            "  • ! after every shocking fact for excitement\n"
            "  • ... for comedic pause before punchline\n"
            "  • CAPITALIZE words for emphasis\n"
            "  • — for sudden realizations\n\n"
            "START with: 'Did you know...' (pause effect)\n"
            "DELIVER 4 shocking funny facts with REACTIONS between each:\n"
            "  'Wait — it gets BETTER!', 'I KNOW right?!', 'No seriously!', 'And get THIS!'\n"
            "120-140 words. High energy throughout. End: 'Follow FreakyBits for more WILD facts!'"
        )
        topic   = "Fresh specific topic — shocking, funny, unbelievable."
        tag_ext = "#Facts #mindblown #didyouknow #amazingfacts #funnyfacts #comedy"
        ig_tags = "#reels #viral #freakybits #shorts #fyp #trending #facts #explore #mindblown #amazingfacts #comedy"
        duration = "40-50 seconds"
        pexels  = '["colorful confetti explosion", "people laughing outdoors", "bright colorful balloons", "funny animals cute"]'
    return narration, topic, tag_ext, ig_tags, duration, pexels, part_instruction
def generate_content(niche, video_index, lang, part=None, part1_data=None):
    lang_code  = lang["code"]
    lang_label = lang["label"]
    print(f"\n🤖 [{niche['label']}] [{lang_label}]" + (f" [Part {part}]" if part else ""))
    today        = datetime.datetime.utcnow().strftime("%B %d, %Y")
    script_style = niche.get("script_style", "narrator")
    lang_instruction = (
        "LANGUAGE: Write EVERYTHING in Hindi (Devanagari). Hashtags stay English."
        if lang_code == "hi" else "LANGUAGE: English throughout."
    )
    used      = load_used_topics()
    recent    = list(used.keys())[-10:] if used else []
    avoid_str = (f"\nAVOID these recently used topics: {', '.join(recent)}" if recent else "")
    print(f"   🔍 Searching viral angles for [{niche['label']}]...")
    viral_context = get_viral_angle(niche["name"], niche["label"])
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
WRITING RULES (CRITICAL — FOR SPOKEN AUDIO):
- Write for EARS not eyes — every sentence must sound natural when spoken
- Use emotion markers: ... for pauses, ! for excitement, — for interruptions, CAPS for emphasis
- Sound like MrBeast or a viral Gen-Z creator — ENERGY in every line
- Short punchy sentences mixed with longer dramatic ones
- Comedy/AI facts: MUST start with "Did you know..."
- Horror: start with immediate dread, whisper-paced
- Tech Drops: start with "Bro wait—" or "Okay real talk—"
- End ALWAYS with spoken CTA delivered with ENERGY
- NEVER write flat monotone sentences — every line needs a reason to exist
Reply ONLY in valid JSON (no markdown):
{{
  "topic": "specific topic/tool/story name",
  "language": "{lang_code}",
  "part": {part if part else "null"},
  "youtube_title": "viral title under 60 chars",
  "youtube_description": "3 punchy sentences.\\n\\nSubscribe for daily {niche['label']} {niche['emoji']}!\\n\\n",
  "youtube_viral_caption": "hook under 10 words with emoji",
  "youtube_trending_tags": "#Shorts #Viral #FreakyBits #{niche['name']} {tag_ext} #YouTubeShorts #trending #fyp",
  "youtube_tags": ["FreakyBits", "Shorts", "Viral", "{niche['name']}", "trending", "fyp"],
  "instagram_caption": "punchy IG caption 150 chars max with emojis",
  "instagram_viral_caption": "Reels hook 12 words max 2-3 emojis",
  "instagram_trending_tags": "{ig_tags}",
  "trending_yt_song": "popular song - artist",
  "trending_ig_song": "popular song - artist",
  "narration": "WRITE FULL NARRATION HERE",
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
                raise RuntimeError(f"Content generation failed: {e}")
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
def _tts_segment(text, voice, rate, out_path):
    import edge_tts
    async def _run():
        comm = edge_tts.Communicate(text, voice=voice, rate=rate)
        await comm.save(str(out_path))
    asyncio.run(_run())
def parse_dialogue_segments(narration, script_style):
    two_voice = TWO_VOICE_CONFIG.get(script_style)
    if not two_voice:
        return None
    name_a  = two_voice["voice_a"]["name"]
    name_b  = two_voice["voice_b"]["name"]
    pattern = re.compile(r'^\[(\w+)\]\s*(.+)$', re.MULTILINE)
    matches = pattern.findall(narration)
    if not matches:
        return None
    segments = []
    for speaker_tag, line_text in matches:
        if speaker_tag.lower() == name_a.lower():
            segments.append({"speaker": "a", "text": line_text.strip()})
        elif speaker_tag.lower() == name_b.lower():
            segments.append({"speaker": "b", "text": line_text.strip()})
        else:
            segments.append({"speaker": "a", "text": line_text.strip()})
    return segments if segments else None
def generate_voiceover(content, video_idx, lang, niche):
    script_style = niche.get("script_style", "narrator")
    narration    = content["narration"]
    audio_path   = OUT / f"voice_{video_idx:02d}.mp3"
    two_voice = TWO_VOICE_CONFIG.get(script_style)
    if two_voice:
        segments = parse_dialogue_segments(narration, script_style)
        if segments:
            print(f"   🎙️  Two-voice TTS: {two_voice['voice_a']['name']} + {two_voice['voice_b']['name']}")
            seg_paths = []
            for i, seg in enumerate(segments):
                vc   = two_voice["voice_a"] if seg["speaker"] == "a" else two_voice["voice_b"]
                path = OUT / f"seg_{video_idx:02d}_{i:03d}.mp3"
                _tts_segment(seg["text"], vc["edge_voice"], vc["edge_rate"], path)
                if path.exists() and path.stat().st_size > 500:
                    seg_paths.append(path)
            if seg_paths:
                concat_txt = OUT / f"seg_concat_{video_idx:02d}.txt"
                with open(concat_txt, "w") as f:
                    for p in seg_paths:
                        f.write(f"file '{p.resolve()}'\n")
                ret = subprocess.run([
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_txt), "-c:a", "libmp3lame", "-q:a", "2", str(audio_path)
                ], capture_output=True)
                if ret.returncode == 0 and audio_path.exists() and audio_path.stat().st_size > 1000:
                    print(f"   ✅ Two-voice audio stitched")
                    return audio_path
    voice_settings = dict(lang)
    if niche.get("name") == "horror_story":
        voice_settings.update(HORROR_VOICE_OVERRIDE.get(lang["code"], {}))
    clean_narration = re.sub(r'\[\w+\]\s*', '', narration).strip()
    _tts_segment(clean_narration, voice_settings["edge_voice"], voice_settings["edge_rate"], audio_path)
    if not audio_path.exists() or audio_path.stat().st_size < 1000:
        raise RuntimeError("TTS failed")
    print(f"   ✅ Voiceover: {audio_path.name}")
    return audio_path
def generate_subtitles(content, audio_path, video_idx):
    srt_path  = OUT / f"subs_{video_idx:02d}.srt"
    narration = re.sub(r'\[\w+\]\s*', '', content["narration"]).strip()
    words     = narration.split()
    probe    = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)
    ], capture_output=True, text=True)
    duration = float(probe.stdout.strip() or 30)
    wps        = len(words) / duration
    srt_lines  = []
    idx        = 1
    chunk_size = max(1, round(wps * 0.6))
    for i in range(0, len(words), chunk_size):
        chunk   = words[i:i + chunk_size]
        t_start = i / wps
        t_end   = min((i + chunk_size) / wps, duration)
        s = _fmt_srt_time(t_start)
        e = _fmt_srt_time(t_end)
        srt_lines.append(f"{idx}\n{s} --> {e}\n{' '.join(chunk)}\n")
        idx += 1
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    print(f"   ✅ Subtitles: {idx-1} lines")
    return srt_path
def _fmt_srt_time(seconds):
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
def fetch_clip(query, video_idx, clip_idx):
    clip_path = OUT / f"clip_{video_idx:02d}_{clip_idx:02d}.mp4"
    if clip_path.exists() and clip_path.stat().st_size > 100_000:
        return clip_path
    try:
        resp   = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY},
            params={"query": query, "per_page": 10, "orientation": "portrait"},
            timeout=15
        )
        videos = resp.json().get("videos", [])
        if not videos:
            return None
        video = None
        for v in videos:
            files = [f for f in v.get("video_files", []) if f.get("width", 0) < f.get("height", 1)]
            if files:
                video = v
                break
        if not video:
            video = videos[0]
        files = sorted([f for f in video.get("video_files", []) if f.get("link")], key=lambda f: f.get("width", 0))
        if not files:
            return None
        target = next((f for f in files if 600 <= f.get("width", 0) <= 900), files[-1])
        dl = requests.get(target["link"], stream=True, timeout=60)
        with open(clip_path, "wb") as f:
            for chunk in dl.iter_content(chunk_size=65536):
                f.write(chunk)
        if clip_path.stat().st_size < 100_000:
            clip_path.unlink()
            return None
        print(f"   🎥 Clip {clip_idx+1}: '{query}'")
        return clip_path
    except Exception as e:
        print(f"   ⚠️  Clip failed ({query}): {e}")
        return None
def fetch_all_clips(content, niche, video_idx):
    queries = content.get("pexels_queries") or niche["pexels_queries"]
    if isinstance(queries, str):
        try:
            queries = json.loads(queries)
        except Exception:
            queries = niche["pexels_queries"]
    clips = []
    for i, q in enumerate(queries[:4]):
        p = fetch_clip(q, video_idx, i)
        if p:
            clips.append(p)
    if not clips:
        for i, q in enumerate(niche["pexels_queries"]):
            p = fetch_clip(q, video_idx, i + 4)
            if p:
                clips.append(p)
    return clips
def get_trending_song(niche_name, video_idx):
    songs     = [s for s in TRENDING_SONGS_FREE if s["niche"] == niche_name] or TRENDING_SONGS_FREE
    song_url  = songs[video_idx % len(songs)]["url"]
    song_path = OUT / f"song_{video_idx:02d}.mp3"
    if song_path.exists() and song_path.stat().st_size > 10_000:
        return song_path
    try:
        dl = requests.get(song_url, stream=True, timeout=30)
        with open(song_path, "wb") as f:
            for chunk in dl.iter_content(chunk_size=65536):
                f.write(chunk)
        if song_path.stat().st_size < 10_000:
            song_path.unlink()
            return None
        return song_path
    except Exception as e:
        print(f"   ⚠️  Song failed: {e}")
        return None
def process_clip(clip_path, output_path, niche, duration=8.0):
    color_filter = niche.get("color_filter", "")
    vf_parts     = [f"scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=increase", f"crop={VIDEO_W}:{VIDEO_H}", "fps=30"]
    if color_filter:
        vf_parts.append(color_filter)
    ret = subprocess.run([
        "ffmpeg", "-y", "-i", str(clip_path), "-t", str(duration),
        "-vf", ",".join(vf_parts), "-c:v", "libx264", "-preset", "fast", "-crf", "23", "-an", str(output_path)
    ], capture_output=True)
    if ret.returncode != 0:
        raise RuntimeError(f"Clip processing failed: {ret.stderr.decode()[:200]}")
def burn_subtitles(video_path, srt_path, output_path):
    subtitle_style = "FontName=Arial Black,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&H80000000,Bold=1,Outline=3,Shadow=1,Alignment=2,MarginV=120"
    ret = subprocess.run([
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", f"subtitles={srt_path}:force_style='{subtitle_style}'",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22", "-c:a", "copy", str(output_path)
    ], capture_output=True)
    if ret.returncode != 0:
        print("   ⚠️  Subtitle burn failed")
        return video_path
    print("   ✅ Subtitles burned")
    return output_path
def assemble_video(clip_paths, audio_path, srt_path, video_idx, niche, song_path=None):
    print("   ✂️  Assembling 9:16 cinematic video...")
    processed = []
    for i, cp in enumerate(clip_paths):
        pp = OUT / f"proc_{video_idx:02d}_{i:02d}.mp4"
        process_clip(cp, pp, niche, 8.0)
        if pp.exists() and pp.stat().st_size > 1000:
            processed.append(pp)
    if not processed:
        raise RuntimeError("No processed clips")
    while len(processed) < 4:
        processed.append(processed[-1])
    concat_file = OUT / f"concat_{video_idx:02d}.txt"
    with open(concat_file, "w") as f:
        for pp in processed:
            f.write(f"file '{pp.resolve()}'\n")
    merged = OUT / f"merged_{video_idx:02d}.mp4"
    ret    = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(merged)], capture_output=True)
    if ret.returncode != 0:
        raise RuntimeError(f"Concat failed: {ret.stderr.decode()[:200]}")
    with_audio   = OUT / f"audio_{video_idx:02d}.mp4"
    music_volume = niche.get("music_volume", "0.0")
    if song_path and song_path.exists():
        ret = subprocess.run([
            "ffmpeg", "-y", "-i", str(merged), "-i", str(audio_path), "-i", str(song_path),
            "-filter_complex", f"[1:a]volume=1.0[vo];[2:a]volume={music_volume}[vs];[vo][vs]amix=inputs=2:duration=first[a]",
            "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", str(with_audio)
        ], capture_output=True)
    else:
        ret = subprocess.run([
            "ffmpeg", "-y", "-i", str(merged), "-i", str(audio_path),
            "-c:v", "copy", "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest", str(with_audio)
        ], capture_output=True)
    if ret.returncode != 0:
        raise RuntimeError("Audio mix failed")
    final_with_subs = OUT / f"final_{video_idx:02d}.mp4"
    final_path = burn_subtitles(with_audio, srt_path, final_with_subs) if srt_path else with_audio
    probe    = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(final_path)], capture_output=True, text=True)
    duration = float(probe.stdout.strip() or 0)
    size_mb  = Path(final_path).stat().st_size / (1024 * 1024)
    print(f"   ✅ {Path(final_path).name} — {duration:.1f}s, {size_mb:.1f}MB, 9:16 vertical")
    return Path(final_path)
def upload_youtube(video_path, content):
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
                    "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
                },
                media_body=MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=-1, resumable=True)
            ).execute()
            url = f"https://youtube.com/watch?v={resp['id']}"
            print(f"   ✅ YouTube → {url}")
            return url
        except Exception as e:
            if attempt < 3:
                time.sleep(2 ** attempt)
            else:
                print(f"   ❌ YouTube failed: {e}")
                return None
def upload_instagram(video_path, content):
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        print("   ⚠️  Instagram skipped — set INSTAGRAM_USERNAME + INSTAGRAM_PASSWORD in .env")
        return None
    print("   📸 Uploading to Instagram Reels via instagrapi...")
    session_file = OUT / "ig_session.json"
    try:
        from instagrapi import Client
        from instagrapi.exceptions import LoginRequired, BadPassword, TwoFactorRequired
        cl = Client()
        cl.delay_range = [2, 5]
        cl.set_locale("en_US")
        cl.set_timezone_offset(19800)  # IST +5:30
        # Try loading saved session first
        logged_in = False
        if session_file.exists():
            try:
                cl.load_settings(session_file)
                cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
                cl.get_timeline_feed()
                print("   ✅ Instagram session restored")
                logged_in = True
            except Exception as e:
                print(f"   ⚠️  Session expired ({e}) — fresh login")
                session_file.unlink()
                cl = Client()
                cl.delay_range = [2, 5]
        if not logged_in:
            try:
                cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
                cl.dump_settings(session_file)
                print("   ✅ Instagram fresh login successful")
            except BadPassword:
                print("   ❌ Instagram wrong password — check INSTAGRAM_PASSWORD in .env")
                return None
            except TwoFactorRequired:
                print("   ❌ Instagram 2FA required — disable 2FA on @freaky_bits account")
                return None
            except Exception as e:
                print(f"   ❌ Instagram login failed: {e}")
                return None
        caption = content.get("instagram_caption_final", content.get("instagram_caption", ""))
        # Try all available reel upload methods
        media = None
        for method_name, method_call in [
            ("video_upload_to_reel", lambda: cl.video_upload_to_reel(str(video_path), caption=caption)),
            ("clip_upload",          lambda: cl.clip_upload(str(video_path), caption)),
            ("video_upload",         lambda: cl.video_upload(str(video_path), caption)),
        ]:
            try:
                media = method_call()
                print(f"   ✅ Used method: {method_name}")
                break
            except AttributeError:
                continue
            except Exception as e:
                print(f"   ⚠️  {method_name} failed: {e}")
                continue
        if media:
            url = f"https://www.instagram.com/reel/{media.code}/"
            print(f"   ✅ Instagram Reel → {url}")
            cl.dump_settings(session_file)
            return url
        else:
            print("   ❌ All Instagram upload methods failed")
            return None
    except Exception as e:
        print(f"   ❌ Instagram error: {type(e).__name__}: {e}")
        if session_file.exists():
            session_file.unlink()
        return None
def post_youtube_community(image_path, text):
    print("   📢 Posting to YouTube Community Tab...")
    try:
        from googleapiclient.discovery import build
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
    try:
        yt   = build("youtube", "v3", credentials=creds)
        resp = yt.communityPosts().insert(
            part="snippet",
            body={"snippet": {"textOriginal": text, "type": "imagePost" if image_path else "textPost"}}
        ).execute()
        url = f"https://www.youtube.com/post/{resp.get('id', 'unknown')}"
        print(f"   ✅ Community Tab → {url}")
        return url
    except Exception as e:
        print(f"   ⚠️  Community Tab not available: {e}")
        return None
def post_instagram_image(image_path, caption):
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        print("   ⚠️  Instagram image skipped")
        return None
    print("   📷 Posting image to Instagram...")
    try:
        from instagrapi import Client
        cl = Client()
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        media = cl.photo_upload(str(image_path), caption)
        url   = f"https://www.instagram.com/p/{media.code}/"
        print(f"   ✅ Instagram post → {url}")
        cl.logout()
        return url
    except Exception as e:
        print(f"   ❌ Instagram image failed: {e}")
        return None
def generate_image_content(image_niche, img_idx):
    today     = datetime.datetime.utcnow().strftime("%B %d, %Y")
    used      = load_used_topics()
    recent    = list(used.keys())[-10:] if used else []
    avoid_str = (f"\nAVOID these recently used topics: {', '.join(recent)}" if recent else "")
    prompt = f"""You are a viral social media image content creator for FreakyBits.
Date: {today} | Niche: {image_niche['label']} {image_niche['emoji']}
{avoid_str}
{image_niche['prompt_style']}
Reply ONLY in valid JSON:
{{
  "topic": "specific topic/fact",
  "headline": "MAIN HEADLINE — ALL CAPS, max 8 words",
  "subtext": "Supporting line, max 12 words",
  "background_description": "describe background style",
  "youtube_community_text": "{image_niche['yt_community_prefix']}: [2-3 sentences + emoji + question]",
  "instagram_caption": "Punchy caption with emojis, max 150 chars"
}}"""
    for attempt in range(3):
        try:
            response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
            raw      = response.text.strip().replace("```json", "").replace("```", "").strip()
            start    = raw.find("{"); end = raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]
            return json.loads(raw)
        except Exception as e:
            if attempt == 2:
                raise RuntimeError(f"Image content failed: {e}")
            time.sleep(2 ** attempt)
def create_image_with_ffmpeg(content, image_niche, img_idx):
    img_path = OUT / "images" / f"img_{image_niche['name']}_{img_idx:02d}.png"
    headline = content.get("headline", "FREAKYBITS").replace("'", "\\'").replace(":", "\\:")
    subtext  = content.get("subtext", "Follow for more").replace("'", "\\'").replace(":", "\\:")
    color_map = {
        "ai_trends":        ("0x00BFFF", "0x1a1a2e"),
        "harsh_life_truth": ("0xFF4444", "0x0d0d0d"),
        "did_you_know":     ("0xFFD700", "0x1a0a2e"),
    }
    accent_color, bg_color = color_map.get(image_niche["name"], ("0xFFFFFF", "0x000000"))
    ret = subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c={bg_color}:size=1080x1080:rate=1",
        "-vframes", "1",
        "-vf", (
            f"drawtext=text='{headline}':fontcolor={accent_color}:fontsize=72:x=(w-text_w)/2:y=(h-text_h)/2-80:"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf,"
            f"drawtext=text='{subtext}':fontcolor=white:fontsize=36:x=(w-text_w)/2:y=(h-text_h)/2+60:"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf,"
            f"drawtext=text='@freaky_bits':fontcolor=0x888888:fontsize=28:x=(w-text_w)/2:y=h-80:"
            f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
        str(img_path)
    ], capture_output=True)
    if ret.returncode != 0 or not img_path.exists():
        raise RuntimeError(f"Image creation failed: {ret.stderr.decode()[:200]}")
    print(f"   🖼️  Image: {img_path.name}")
    return img_path
def run_image_pipeline():
    print("\n" + "═"*62)
    print(f"  🖼️   FreakyBits Image Pipeline v4.1")
    print(f"  📅  {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("═"*62)
    total_images = 0
    results      = []
    for image_niche in IMAGE_NICHES:
        print(f"\n── {image_niche['label']} {image_niche['emoji']} ──")
        for i in range(image_niche["count"]):
            print(f"\n  Image {i+1}/{image_niche['count']}:")
            try:
                content  = generate_image_content(image_niche, total_images + i)
                img_path = create_image_with_ffmpeg(content, image_niche, total_images + i)
                yt_text  = content.get("youtube_community_text", "")
                yt_url   = post_youtube_community(img_path, yt_text)
                ig_cap   = f"{content.get('instagram_caption', '')}\n\n{image_niche['ig_hashtags']}"
                ig_url   = post_instagram_image(img_path, ig_cap)
                save_used_topic(content.get("topic", ""), image_niche["name"])
                results.append({"niche": image_niche["label"], "topic": content.get("topic", ""), "yt": yt_url, "ig": ig_url})
                send_notification(
                    f"FreakyBits Image ✅ — {image_niche['label']}",
                    f"Topic: {content.get('topic', '')}\nYT: {yt_url or 'Local only'}\nIG: {ig_url or 'Failed'}"
                )
                if i < image_niche["count"] - 1:
                    time.sleep(10)
            except Exception as e:
                print(f"   ❌ Failed: {e}")
        total_images += image_niche["count"]
    print("\n" + "═"*62)
    print(f"  ✅ {len(results)}/10 images done")
    print("═"*62)
    send_notification(
        f"FreakyBits Image Run — {len(results)}/10 ✅",
        f"YT Community: {sum(1 for r in results if r.get('yt'))}\nIG Posts: {sum(1 for r in results if r.get('ig'))}"
    )
def make_one_video(video_idx):
    niche      = pick_niche(video_idx)
    lang       = pick_language(video_idx, niche)
    part       = get_current_part(video_idx)
    part1_data = load_part1_topic() if part == 2 else None
    print(f"\n{'─'*62}")
    print(f"  VIDEO {video_idx+1}/{VIDEOS_PER_RUN}  |  {niche['label']} {niche['emoji']}  |  {lang['label']}")
    print(f"{'─'*62}")
    content = generate_content(niche, video_idx, lang, part, part1_data)
    audio   = generate_voiceover(content, video_idx, lang, niche)
    srt     = None if lang["code"] == "hi" else generate_subtitles(content, audio, video_idx)
    clips   = fetch_all_clips(content, niche, video_idx)
    song    = get_trending_song(niche["name"], video_idx)
    video   = assemble_video(clips, audio, srt, video_idx, niche, song)
    yt_url  = upload_youtube(video, content)
    ig_url  = None
    if niche.get("upload_instagram") and lang["code"] == "en":
        ig_url = upload_instagram(video, content)
    else:
        print(f"   ⏭️  Instagram disabled for {niche['label']}")
    if part == 1:
        save_part1_topic(content["topic"], niche["name"], lang["code"])
    save_used_topic(content["topic"], niche["name"])
    result = {
        "video": str(video), "niche": niche["label"], "language": lang["label"],
        "part": part, "topic": content["topic"], "title": content["youtube_title"],
        "youtube": yt_url, "instagram": ig_url,
    }
    log_analytics(result)
    status = "✅ SUCCESS" if yt_url else "⚠️ PARTIAL"
    send_notification(
        f"FreakyBits {status} — {niche['label']}",
        f"Title: {content['youtube_title']}\nYouTube: {yt_url or 'Failed ❌'}\nInstagram: {ig_url or 'Skipped ⏭️'}\nTime: {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
    )
    return result
def run_video_pipeline():
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY not set!")
        sys.exit(1)
    if not PEXELS_API_KEY:
        print("❌ PEXELS_API_KEY not set!")
        sys.exit(1)
    start             = time.time()
    results, failures = [], []
    print("\n" + "═"*62)
    print(f"  🚀  FreakyBits Auto Pipeline v4.1")
    print(f"  📅  {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  🎬  2 slots/run × 4 runs = 8 YT videos/day")
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
            failures.append({"index": i + 1, "error": str(e)})
    elapsed = round(time.time() - start)
    print("\n" + "═"*62)
    print(f"  ✅  {len(results)}/{VIDEOS_PER_RUN} videos  |  {elapsed//60}m {elapsed%60}s")
    print("═"*62)
    ig_count = sum(1 for r in results if r.get("instagram"))
    send_notification(
        f"FreakyBits Run Complete — {len(results)}/{VIDEOS_PER_RUN} ✅",
        f"YouTube uploads: {len(results)}\nInstagram Reels: {ig_count}\nFailed: {len(failures)}\nTime taken: {elapsed//60}m {elapsed%60}s\nNext run: auto via cron"
    )
    log = OUT / "logs" / f"video_log_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M')}.json"
    with open(log, "w") as f:
        json.dump({"results": results, "failures": failures, "elapsed_s": elapsed}, f, indent=2)
    if failures and len(failures) == VIDEOS_PER_RUN:
        sys.exit(1)
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "video"
    if mode == "image":
        if not GEMINI_API_KEY:
            print("❌ GEMINI_API_KEY not set!")
            sys.exit(1)
        run_image_pipeline()
    elif mode == "video":
        run_video_pipeline()
    else:
        print(f"❌ Unknown mode: {mode}\nUsage: python3 pipeline.py video|image")
        sys.exit(1)
if __name__ == "__main__":
    main()
