"""
FreakyBits Auto Pipeline
========================
Generates 3 cinematic videos per run, uploads to YouTube + Instagram.
Run 4x daily via GitHub Actions = 12 videos/day.

ALL INSTRUCTIONS CHECKLIST:
 [1]  12 videos/day — 3 per run × 4 runs (7AM, 12PM, 6PM, 10PM IST)
 [2]  Auto script generation based on niche
 [3]  Niches: Horror Facts, Comedy Facts, AI & Tech, Storytelling
 [4]  AI animated character (no copyright — anime style)
 [5]  Video minimum 32 seconds (4 × 8s Veo scenes)
 [6]  Extended clips precise — same topic, character, environment
 [7]  Last-frame chaining for visual continuity
 [8]  Bilingual — EN, HI, EN pattern per run
 [9]  Hindi videos fully in Hindi (hashtags stay English)
 [10] Video 3 of Morning = Part 1, Afternoon = Part 2
 [11] Video 3 of Evening = Part 1, Night = Part 2
 [12] Part 1 ends with follow CTA in video's language
 [13] EN: "Follow for Part 2!" / HI: "Part 2 ke liye follow karo!"
 [14] YouTube description has viral caption block
 [15] YouTube description has trending hashtags
 [16] Instagram has viral hook line
 [17] Instagram has 20 trending hashtags
 [18] Platform-specific captions (YT and IG different)
 [19] Trending background song on both platforms
 [20] Song MUTED (volume=0.0) — algorithm boost only
 [21] Song matches niche mood
 [22] Auto upload YouTube — SEO title + description + tags
 [23] Auto upload Instagram as Reels with caption
 [24] Runs on GitHub Actions (free, no PC needed)
 [25] Schedule: 7AM, 12PM, 6PM, 10PM IST
 [26] Channel name: FreakyBits

Stack: Gemini 2.5 Flash (script) + Veo 3.1 Fast (video) + gTTS (voice) + FFmpeg (merge)
"""

import os, sys, json, time, pickle, datetime, subprocess, requests
from pathlib import Path
from gtts import gTTS
from google import genai
from google.genai import types

# ── CONFIG ─────────────────────────────────────────────────────────
GEMINI_API_KEY        = os.environ.get("GEMINI_API_KEY", "")
YOUTUBE_SECRETS_FILE  = "youtube_secrets.json"
INSTAGRAM_TOKEN       = os.environ.get("INSTAGRAM_TOKEN", "")
INSTAGRAM_ACCOUNT_ID  = os.environ.get("INSTAGRAM_ACCOUNT_ID", "")
VIDEOS_PER_RUN        = 3       # 3 videos × 4 runs = 12/day  [1]
TARGET_DURATION_SEC   = 32      # 4 × 8s Veo scenes = 32s     [5]

# ── LANGUAGE CONFIG  [8][9] ────────────────────────────────────────
# Per run pattern: Video 0 → EN, Video 1 → HI, Video 2 → EN
# = 8 English + 4 Hindi per day
LANG_PATTERN = ["en", "hi", "en"]

LANG_CONFIG = {
    "en": {
        "label":        "English",
        "gtts_lang":    "en",
        "follow_part2": "Follow for Part 2!",       # [13]
    },
    "hi": {
        "label":        "Hindi",
        "gtts_lang":    "hi",
        "follow_part2": "Part 2 ke liye follow karo!",  # [13]
    },
}

# ── PART SERIES CONFIG  [10][11] ───────────────────────────────────
# Only video_idx=2 (3rd video) participates in the series
# GitHub cron UTC hours: 1=morning, 6=afternoon, 12=evening, 16=night
PART_SERIES_SCHEDULE = {
    1:  1,   # Morning   → Part 1  [10]
    6:  2,   # Afternoon → Part 2  [10]
    12: 1,   # Evening   → Part 1  [11]
    16: 2,   # Night     → Part 2  [11]
}

# ── NICHES  [3] ────────────────────────────────────────────────────
NICHES = [
    {
        "name":  "horror_facts",
        "label": "Horror Facts",
        "style": "dark eerie anime style, haunting atmosphere, deep shadows, red and black tones, moonlit backgrounds",
        "tone":  "spine-chilling and mysterious, building dread with each fact",
        "emoji": "👻",
    },
    {
        "name":  "comedy_facts",
        "label": "Comedy Facts",
        "style": "bright colorful anime style, exaggerated expressions, comedic timing, vibrant saturated colors",
        "tone":  "hilarious and shocking, with punchline energy on every fact",
        "emoji": "😂",
    },
    {
        "name":  "ai_tech",
        "label": "AI & Tech Facts",
        "style": "cyberpunk anime style, neon blue and purple, futuristic HUD elements, glowing circuit patterns",
        "tone":  "mind-blowing and futuristic, making tech feel like sci-fi",
        "emoji": "🤖",
    },
    {
        "name":  "storytelling",
        "label": "Storytelling",
        "style": "cinematic anime style, rich detailed backgrounds, emotionally expressive characters, dramatic warm-cool lighting contrast, painterly textures",
        "tone":  "emotionally gripping, narrative-driven, builds tension scene by scene like a mini-film",
        "emoji": "📖",
    },
]

# ── TRENDING SONGS (royalty-free, muted for algorithm boost) [19][20][21] ──
TRENDING_SONGS_FREE = [
    {"niche": "horror_facts",  "url": "https://cdn.pixabay.com/download/audio/2022/03/10/audio_c8c8a73467.mp3", "name": "Horror Ambience"},
    {"niche": "horror_facts",  "url": "https://cdn.pixabay.com/download/audio/2021/09/06/audio_6ded321929.mp3", "name": "Dark Suspense"},
    {"niche": "comedy_facts",  "url": "https://cdn.pixabay.com/download/audio/2022/10/25/audio_946b736e00.mp3", "name": "Funny Upbeat"},
    {"niche": "comedy_facts",  "url": "https://cdn.pixabay.com/download/audio/2022/01/20/audio_d0ee71a7e6.mp3", "name": "Comedy Pop"},
    {"niche": "ai_tech",       "url": "https://cdn.pixabay.com/download/audio/2022/08/02/audio_2dde668d05.mp3", "name": "Cyberpunk Beat"},
    {"niche": "ai_tech",       "url": "https://cdn.pixabay.com/download/audio/2021/11/13/audio_cb31e6deb5.mp3", "name": "Tech Pulse"},
    {"niche": "storytelling",  "url": "https://cdn.pixabay.com/download/audio/2022/11/22/audio_febc508520.mp3", "name": "Emotional Cinematic"},
    {"niche": "storytelling",  "url": "https://cdn.pixabay.com/download/audio/2023/01/04/audio_9b6d7c7b30.mp3", "name": "Dramatic Story"},
]

OUT              = Path("buzzBits_output")
OUT.mkdir(exist_ok=True)
PART1_TOPIC_FILE = OUT / "part1_topic.json"

client = genai.Client(api_key=GEMINI_API_KEY)


# ══════════════════════════════════════════════════════════════════
#  SELECTORS
# ══════════════════════════════════════════════════════════════════
def pick_niche(video_index: int) -> dict:
    hour = datetime.datetime.utcnow().hour
    return NICHES[(hour // 6 + video_index) % len(NICHES)]


def pick_language(video_index: int) -> dict:       # [8]
    code = LANG_PATTERN[video_index % len(LANG_PATTERN)]
    return {"code": code, **LANG_CONFIG[code]}


def get_current_part(video_index: int) -> int | None:   # [10][11]
    if video_index != 2:
        return None
    hour = datetime.datetime.utcnow().hour
    for sched_hour in sorted(PART_SERIES_SCHEDULE):
        if hour <= sched_hour + 1:
            return PART_SERIES_SCHEDULE[sched_hour]
    return PART_SERIES_SCHEDULE[16]


# ══════════════════════════════════════════════════════════════════
#  PART SERIES HELPERS
# ══════════════════════════════════════════════════════════════════
def save_part1_topic(topic: str, niche_name: str, lang_code: str):
    data = {"topic": topic, "niche": niche_name, "lang": lang_code,
            "saved_at": datetime.datetime.utcnow().isoformat()}
    with open(PART1_TOPIC_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   💾 Part 1 topic saved: '{topic}'")


def load_part1_topic() -> dict | None:
    if not PART1_TOPIC_FILE.exists():
        print("   ⚠️  No Part 1 topic file — generating fresh Part 2")
        return None
    try:
        with open(PART1_TOPIC_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"   📂 Part 2 continuing: '{data['topic']}'")
        return data
    except Exception as e:
        print(f"   ⚠️  Could not load Part 1 topic: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
#  STEP 1 — Generate Script + Captions + 4 Veo Prompts
# ══════════════════════════════════════════════════════════════════
def generate_content(niche: dict, video_index: int,
                     lang: dict, part: int | None = None,
                     part1_data: dict | None = None) -> dict:
    lang_label = lang["label"]
    lang_code  = lang["code"]
    print(f"\n🤖 [{niche['label']}] [{lang_label}]"
          + (f" [Part {part}]" if part else ""))

    today = datetime.datetime.utcnow().strftime("%B %d, %Y")

    # ── Language instruction  [8][9] ──────────────────────────────
    if lang_code == "hi":
        lang_instruction = """
LANGUAGE: Write EVERYTHING in Hindi (Devanagari script).
- narration, youtube_title, youtube_description,
  youtube_viral_caption, instagram_caption, instagram_viral_caption
  → all in Hindi
- hashtags stay in English (perform better on both platforms)
- trending_yt_song / trending_ig_song → popular in India/Hindi content
"""
    else:
        lang_instruction = "LANGUAGE: English throughout."

    # ── Part series instruction  [10][11][12][13] ─────────────────
    part_instruction = ""
    if part == 1:
        part_instruction = f"""
PART SERIES — PART 1 of 2:
- Cover first half of topic with 3 strong facts/story beats
- Narration MUST end with exactly: "{lang['follow_part2']}"
- YouTube title must end with "(Part 1)"
- Instagram caption must include "Part 1 👇"
- End on a cliffhanger — keep viewers wanting Part 2
"""
    elif part == 2:
        prev = part1_data.get("topic", "the previous topic") if part1_data else "the previous topic"
        part_instruction = f"""
PART SERIES — PART 2 of 2:
- CONTINUE directly from Part 1 topic: "{prev}"
- Open with a quick 1-line recap referencing Part 1
- Deliver the second half with 3 MORE facts/story beats
- End with a satisfying conclusion
- YouTube title must end with "(Part 2)"
- Instagram caption must include "Part 2 ✅"
"""

    prompt = f"""You are a viral content creator for FreakyBits — a YouTube/Instagram
channel posting {niche['label']} videos daily.
Channel style: anime-style cinematic visuals, FreakyBits brand.

Date: {today} | Video #{video_index+1} | Niche: {niche['label']}
Tone: {niche['tone']}
Visual style: {niche['style']}

{lang_instruction}
{part_instruction}

TARGET: 32-second video = 4 chained Veo clips × 8s each.
The 4 Veo scenes form ONE continuous visual story — SAME character, SAME location,
SAME lighting throughout. Only the ACTION changes per scene.

CHARACTER LOCK: Gemini will output character_description and environment_description
which will be injected into every Veo prompt to enforce visual consistency.  [6]

STRICT RULES:
- narration: 80-100 words, 4 clear beats (one per scene), hook in first 3 words  [5]
- All 4 veo_prompts: same character + same environment, only action changes        [6][7]
- Each veo_prompt ends with "CONTINUOUS from previous scene, same character and setting"
- youtube_title: number or question format, under 60 chars                         [22]
- youtube_viral_caption: ≤10 words, 1-2 emojis, grabs instant attention           [14]
- youtube_trending_tags: exactly 15 tags, start with #Shorts #Viral #FreakyBits   [15]
- instagram_viral_caption: ≤12 words, 2-3 emojis, native Reels language           [16]
- instagram_trending_tags: exactly 20 tags, mix large + niche                     [17]
- instagram_caption ≠ youtube_description (platform-specific language)            [18]
- trending_yt_song + trending_ig_song: real song names matching niche mood         [19]
- Topics: FRESH only — no black holes, no Einstein, no overused examples

Reply ONLY with valid JSON, no markdown:
{{
  "topic": "Specific topic",
  "character_description": "Detailed single character: hair, clothes, face, body, expression style — used in ALL 4 scenes",
  "environment_description": "Detailed single setting: location, lighting, colors, time of day — used in ALL 4 scenes",
  "language": "{lang_code}",
  "part": {part if part else "null"},
  "youtube_title": "Title with number or question",
  "youtube_description": "3 punchy sentences.\\n\\nSubscribe for daily {niche['label']} {niche['emoji']} — posted morning, afternoon, evening & night!\\n\\n",
  "youtube_viral_caption": "≤10 word hook with emoji",
  "youtube_trending_tags": "#Shorts #Viral #FreakyBits #Facts #{niche['name']} #YouTubeShorts [9 more trending tags]",
  "youtube_tags": ["FreakyBits","Shorts","Viral","Facts","{niche['name']}","tag6","tag7","tag8","tag9","tag10"],
  "instagram_caption": "2-line punchy IG-native caption with emojis, ≤150 chars",
  "instagram_viral_caption": "≤12 word Reels hook with 2-3 emojis",
  "instagram_trending_tags": "#reels #viral #freakybits #shorts #fyp [15 more trending ig tags]",
  "trending_yt_song": "Song Name - Artist",
  "trending_ig_song": "Song Name - Artist",
  "narration": "80-100 word script in {lang_label}. Hook→Beat1→Beat2→Beat3→Beat4/CTA. PUNCHY.",
  "veo_prompts": [
    "Scene 1/4 ESTABLISHING: {niche['style']}, [character_description] in [environment_description], [Beat 1 opening action], wide cinematic shot, dramatic lighting, 8-second clip, 720p. This is Scene 1 — foundation for all following scenes.",
    "Scene 2/4 CONTINUATION: {niche['style']}, EXACT SAME character in EXACT SAME environment, [Beat 2 action progresses story], medium shot moving closer, same lighting, 8-second clip, 720p. CONTINUOUS from previous scene, same character and setting.",
    "Scene 3/4 RISING ACTION: {niche['style']}, EXACT SAME character in EXACT SAME environment, [Beat 3 peak tension/emotion/comedy], close-up reaction, same lighting and palette, 8-second clip, 720p. CONTINUOUS from previous scene, same character and setting.",
    "Scene 4/4 CLIMAX: {niche['style']}, EXACT SAME character in EXACT SAME environment, [Beat 4 conclusion/punchline/revelation], slow dramatic zoom-out, same lighting, 8-second clip, 720p. CONTINUOUS from previous scene, same character and setting."
  ]
}}"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    raw   = response.text.strip().replace("```json","").replace("```","").strip()
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]

    data = json.loads(raw)

    # ── Build final YouTube description  [14][15] ─────────────────
    data["youtube_description_final"] = (
        f"{data['youtube_description']}\n"
        f"{'─'*40}\n"
        f"⚡ {data['youtube_viral_caption']}\n"
        f"{'─'*40}\n\n"
        f"{data['youtube_trending_tags']}"
    )

    # ── Build final Instagram caption  [16][17] ───────────────────
    data["instagram_caption_final"] = (
        f"{data['instagram_viral_caption']}\n\n"
        f"{data['instagram_caption']}\n\n"
        f"{data['instagram_trending_tags']}"
    )

    print(f"   ✅ Topic  : {data['topic']}")
    print(f"   ✅ Title  : {data['youtube_title']}")
    print(f"   ✅ Lang   : {lang_label}" + (f" | Part {part}" if part else ""))
    print(f"   ✅ YT Song: {data.get('trending_yt_song','N/A')}")
    print(f"   ✅ IG Song: {data.get('trending_ig_song','N/A')}")
    return data


# ══════════════════════════════════════════════════════════════════
#  STEP 2 — Voiceover (language-aware)  [8][9]
# ══════════════════════════════════════════════════════════════════
def generate_voiceover(content: dict, video_idx: int, lang: dict) -> Path:
    print(f"   🎙️  Voiceover [{lang['label']}]...")
    audio_path = OUT / f"voice_{video_idx:02d}.mp3"
    gTTS(text=content["narration"], lang=lang["gtts_lang"], slow=False).save(str(audio_path))
    print(f"   ✅ {audio_path.name}")
    return audio_path


# ══════════════════════════════════════════════════════════════════
#  STEP 3 — Trending Song Download (muted)  [19][20][21]
# ══════════════════════════════════════════════════════════════════
def get_trending_song(niche_name: str, video_idx: int, song_name: str) -> Path | None:
    print(f"   🎵 Fetching song: {song_name}...")
    candidates = [s for s in TRENDING_SONGS_FREE if s["niche"] == niche_name] or TRENDING_SONGS_FREE
    song       = candidates[video_idx % len(candidates)]
    song_path  = OUT / f"song_{video_idx:02d}.mp3"
    try:
        r = requests.get(song["url"], timeout=30, stream=True)
        r.raise_for_status()
        with open(song_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        print(f"   ✅ {song['name']} ({song_path.stat().st_size//1024}KB)")
        return song_path
    except Exception as e:
        print(f"   ⚠️  Song download failed: {e}")
        return None


# ══════════════════════════════════════════════════════════════════
#  STEP 4 — Generate 32s Video via Last-Frame Chaining  [5][6][7]
# ══════════════════════════════════════════════════════════════════
def extract_last_frame(video_path: Path, frame_path: Path) -> Path | None:
    """Extract last frame of a clip as reference image for the next Veo scene."""
    try:
        probe = subprocess.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)
        ], capture_output=True, text=True)
        duration  = float(probe.stdout.strip() or 7.5)
        seek_time = max(0, duration - 0.2)

        ret = subprocess.run([
            "ffmpeg", "-y", "-ss", str(seek_time),
            "-i", str(video_path),
            "-frames:v", "1", "-q:v", "2", str(frame_path)
        ], capture_output=True)

        if ret.returncode == 0 and frame_path.exists():
            print(f"      📸 Last frame → {frame_path.name}")
            return frame_path
        return None
    except Exception as e:
        print(f"      ⚠️  Frame extract error: {e}")
        return None


def generate_veo_scene(prompt: str, scene_idx: int, video_idx: int,
                       reference_frame: Path | None,
                       char_desc: str, env_desc: str) -> Path | None:
    """
    Generate one 8-second Veo scene.
    Scenes 2-4 use the last frame of the previous scene as a reference
    image to enforce character + environment continuity.  [6][7]
    """
    scene_path  = OUT / f"scene_{video_idx:02d}_{scene_idx:02d}.mp4"

    # Inject character + environment lock into prompt  [6]
    lock = f" CHARACTER LOCK: {char_desc}. ENVIRONMENT LOCK: {env_desc}." if char_desc else ""
    full_prompt = prompt + lock

    print(f"\n      Scene {scene_idx+1}/4: {prompt[:65]}...")

    try:
        video_config = types.GenerateVideosConfig(
            aspect_ratio="16:9", duration_seconds=8,
            resolution="720p", number_of_videos=1,
        )

        # Upload reference frame for scene continuity  [7]
        uploaded_image = None
        if reference_frame and reference_frame.exists():
            print(f"      🔗 Reference: last frame of Scene {scene_idx}")
            try:
                uploaded_image = client.files.upload(
                    path=str(reference_frame),
                    config={"mime_type": "image/jpeg"}
                )
            except Exception as e:
                print(f"      ⚠️  Frame upload failed: {e} — generating fresh")

        if uploaded_image:
            operation = client.models.generate_videos(
                model="veo-3.1-fast-generate-preview",
                prompt=full_prompt, image=uploaded_image, config=video_config,
            )
        else:
            operation = client.models.generate_videos(
                model="veo-3.1-fast-generate-preview",
                prompt=full_prompt, config=video_config,
            )

        wait = 0
        while not operation.done:
            time.sleep(20); wait += 20
            operation = client.operations.get(operation)
            print(f"      ⏳ {wait//60}m {wait%60}s...")
            if wait > 600:
                raise TimeoutError("Veo timed out")

        video_bytes = client.files.download(operation.response.generated_videos[0].video)
        with open(scene_path, "wb") as f:
            f.write(video_bytes)

        if scene_path.stat().st_size < 1000:
            raise ValueError("Video file too small")

        print(f"      ✅ Scene {scene_idx+1} → {scene_path.name} ({scene_path.stat().st_size//1024}KB)")
        return scene_path

    except Exception as e:
        print(f"      ❌ Scene {scene_idx+1} failed: {e}")
        return None


def generate_all_scenes(content: dict, video_idx: int) -> list[Path]:
    """Generate 4 × 8s chained scenes = 32 seconds total."""  # [5]
    prompts   = content["veo_prompts"]
    char_desc = content.get("character_description", "")
    env_desc  = content.get("environment_description", "")

    print(f"\n   🎬 Generating {len(prompts)} chained scenes ({len(prompts)*8}s total)")

    scene_paths     : list[Path] = []
    last_frame_path : Path | None = None

    for i, veo_prompt in enumerate(prompts):
        scene = generate_veo_scene(
            prompt          = veo_prompt,
            scene_idx       = i,
            video_idx       = video_idx,
            reference_frame = last_frame_path,
            char_desc       = char_desc,
            env_desc        = env_desc,
        )
        if scene:
            scene_paths.append(scene)
            frame_path      = OUT / f"frame_{video_idx:02d}_{i:02d}.jpg"
            last_frame_path = extract_last_frame(scene, frame_path)
        else:
            last_frame_path = None

        if i < len(prompts) - 1:
            print(f"      💤 20s cooldown before Scene {i+2}...")
            time.sleep(20)

    if not scene_paths:
        raise RuntimeError("No scenes generated — check API key and Veo quota")

    print(f"\n   ✅ {len(scene_paths)}/{len(prompts)} scenes = ~{len(scene_paths)*8}s footage")
    return scene_paths


# ══════════════════════════════════════════════════════════════════
#  STEP 5 — Assemble Video (scenes + voiceover + muted song)
# ══════════════════════════════════════════════════════════════════
def assemble_video(scene_paths: list[Path], audio_path: Path,
                   video_idx: int, song_path: Path | None = None) -> Path:
    print("   ✂️  Assembling video with FFmpeg...")
    final_path = OUT / f"freakyBits_{video_idx:02d}.mp4"

    # Concatenate scenes
    if len(scene_paths) == 1:
        merged = scene_paths[0]
    else:
        concat_file = OUT / f"concat_{video_idx:02d}.txt"
        with open(concat_file, "w") as f:
            for sp in scene_paths:
                f.write(f"file '{sp.resolve()}'\n")
        merged = OUT / f"merged_{video_idx:02d}.mp4"
        ret = subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_file), "-c", "copy", str(merged)
        ], capture_output=True)
        if ret.returncode != 0:
            raise RuntimeError(f"FFmpeg concat failed: {ret.stderr.decode()}")

    # Mix audio: voiceover (full vol) + muted trending song (vol=0)  [20]
    if song_path and song_path.exists():
        print("   🎵 Mixing muted trending song (vol=0.0 for algorithm boost)...")
        ret = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(merged),
            "-i", str(audio_path),
            "-i", str(song_path),
            "-filter_complex",
            "[1:a]volume=1.0[vo];[2:a]volume=0.0[vs];[vo][vs]amix=inputs=2:duration=shortest[a]",
            "-map", "0:v:0", "-map", "[a]",
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            str(final_path)
        ], capture_output=True)
    else:
        ret = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(merged), "-i", str(audio_path),
            "-c:v", "copy", "-c:a", "aac",
            "-map", "0:v:0", "-map", "1:a:0", "-shortest",
            str(final_path)
        ], capture_output=True)

    if ret.returncode != 0:
        # Fallback — try without any video audio
        ret = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(merged), "-i", str(audio_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy", "-c:a", "aac", "-shortest",
            str(final_path)
        ], capture_output=True)

    if ret.returncode != 0:
        raise RuntimeError(f"FFmpeg assembly failed: {ret.stderr.decode()}")

    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(final_path)
    ], capture_output=True, text=True)
    duration = float(probe.stdout.strip() or 0)
    size_mb  = final_path.stat().st_size / (1024*1024)
    print(f"   ✅ {final_path.name} — {duration:.1f}s, {size_mb:.1f}MB")

    if duration < 30:
        print(f"   ⚠️  {duration:.1f}s is under 30s target — some Veo scenes may have failed")

    return final_path


# ══════════════════════════════════════════════════════════════════
#  STEP 6A — Upload to YouTube  [22]
# ══════════════════════════════════════════════════════════════════
def upload_youtube(video_path: Path, content: dict) -> str:
    print("   📺 Uploading to YouTube...")
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
    except ImportError:
        print("   ❌ Run: pip install google-api-python-client google-auth-oauthlib")
        return "NOT_UPLOADED"

    tok_file = OUT / "yt_token.pickle"
    creds    = None
    if tok_file.exists():
        with open(tok_file, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow  = InstalledAppFlow.from_client_secrets_file(
                YOUTUBE_SECRETS_FILE, ["https://www.googleapis.com/auth/youtube.upload"])
            creds = flow.run_local_server(port=0)
        with open(tok_file, "wb") as f:
            pickle.dump(creds, f)

    yt   = build("youtube", "v3", credentials=creds)
    resp = yt.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title":       content["youtube_title"],
                "description": content.get("youtube_description_final",
                                           content["youtube_description"]),
                "tags":        content["youtube_tags"],
                "categoryId":  "28",
            },
            "status": {
                "privacyStatus":           "public",
                "selfDeclaredMadeForKids": False,
            }
        },
        media_body=MediaFileUpload(str(video_path), mimetype="video/mp4",
                                   chunksize=-1, resumable=True)
    ).execute()

    url = f"https://youtube.com/watch?v={resp['id']}"
    print(f"   ✅ YouTube → {url}")
    return url


# ══════════════════════════════════════════════════════════════════
#  STEP 6B — Upload to Instagram Reels  [23]
# ══════════════════════════════════════════════════════════════════
def upload_instagram(video_path: Path, content: dict) -> str:
    print("   📸 Uploading to Instagram...")
    if not INSTAGRAM_TOKEN or not INSTAGRAM_ACCOUNT_ID:
        print("   ⚠️  Instagram credentials not set — skipping")
        return "NOT_CONFIGURED"

    try:
        with open(video_path, "rb") as f:
            r = requests.post("https://file.io", files={"file": f},
                              data={"expires": "14d"}, timeout=120)
        video_url = r.json().get("link")
        if not video_url:
            raise ValueError("file.io returned no link")
    except Exception as e:
        print(f"   ⚠️  Hosting failed: {e}")
        return "UPLOAD_FAILED"

    base      = f"https://graph.facebook.com/v18.0/{INSTAGRAM_ACCOUNT_ID}"
    container = requests.post(f"{base}/media", params={
        "media_type":   "REELS",
        "video_url":    video_url,
        "caption":      content.get("instagram_caption_final", content["instagram_caption"]),
        "access_token": INSTAGRAM_TOKEN
    }).json()

    cid = container.get("id")
    if not cid:
        print(f"   ❌ Container error: {container}")
        return "CONTAINER_FAILED"

    print("   ⏳ Waiting 45s for Instagram processing...")
    time.sleep(45)

    pub = requests.post(f"{base}/media_publish", params={
        "creation_id": cid, "access_token": INSTAGRAM_TOKEN
    }).json()

    url = f"https://www.instagram.com/reel/{pub.get('id','unknown')}"
    print(f"   ✅ Instagram → {url}")
    return url


# ══════════════════════════════════════════════════════════════════
#  SINGLE VIDEO PIPELINE
# ══════════════════════════════════════════════════════════════════
def make_one_video(video_idx: int) -> dict:
    niche      = pick_niche(video_idx)
    lang       = pick_language(video_idx)
    part       = get_current_part(video_idx)
    part1_data = load_part1_topic() if part == 2 else None

    print(f"\n{'─'*62}")
    print(f"  VIDEO {video_idx+1}/{VIDEOS_PER_RUN}  |  "
          f"{niche['label']} {niche['emoji']}  |  {lang['label']}"
          + (f"  |  Part {part}" if part else ""))
    print(f"{'─'*62}")

    content     = generate_content(niche, video_idx, lang, part, part1_data)
    audio_path  = generate_voiceover(content, video_idx, lang)
    scene_paths = generate_all_scenes(content, video_idx)
    song_path   = get_trending_song(niche["name"], video_idx,
                                    content.get("trending_yt_song", ""))
    video_path  = assemble_video(scene_paths, audio_path, video_idx, song_path)
    yt_url      = upload_youtube(video_path, content)
    ig_url      = upload_instagram(video_path, content)

    if part == 1:
        save_part1_topic(content["topic"], niche["name"], lang["code"])

    return {
        "video":     str(video_path),
        "niche":     niche["label"],
        "language":  lang["label"],
        "part":      part,
        "topic":     content["topic"],
        "title":     content["youtube_title"],
        "youtube":   yt_url,
        "instagram": ig_url,
    }


# ══════════════════════════════════════════════════════════════════
#  MAIN  [1][24][25]
# ══════════════════════════════════════════════════════════════════
def main():
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY not set! → https://aistudio.google.com")
        sys.exit(1)

    start    = time.time()
    results  = []
    failures = []

    print("\n" + "═"*62)
    print(f"  🚀  FreakyBits Auto Pipeline")           # [26]
    print(f"  📅  {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  🎬  {VIDEOS_PER_RUN} videos this run × 4 runs/day = 12/day")  # [1]
    print(f"  📐  Target duration: {TARGET_DURATION_SEC}s per video")        # [5]
    print(f"  🌐  Languages: EN → HI → EN")                                  # [8]
    print("═"*62)

    for i in range(VIDEOS_PER_RUN):
        try:
            result = make_one_video(i)
            results.append(result)
            if i < VIDEOS_PER_RUN - 1:
                print(f"\n⏸️  30s cooldown before next video...")
                time.sleep(30)
        except Exception as e:
            print(f"\n❌ Video {i+1} failed: {e}")
            failures.append({"index": i+1, "error": str(e)})

    elapsed = round(time.time() - start)
    print("\n" + "═"*62)
    print(f"  ✅  {len(results)}/{VIDEOS_PER_RUN} videos posted  |  {elapsed//60}m {elapsed%60}s")
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
        json.dump({"results": results, "failures": failures,
                   "elapsed_s": elapsed}, f, indent=2)
    print(f"\n  📋 Log → {log.name}")

    if failures and len(failures) == VIDEOS_PER_RUN:
        sys.exit(1)


if __name__ == "__main__":
    main()
