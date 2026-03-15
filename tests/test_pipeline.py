"""
FreakyBits Pipeline — Unit Tests
Run: pytest tests/ -v
"""
import pytest, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["GEMINI_API_KEY"]       = "test_key"
os.environ["PEXELS_API_KEY"]       = "test_key"
os.environ["INSTAGRAM_TOKEN"]      = "PLACEHOLDER_ADD_LATER"
os.environ["INSTAGRAM_ACCOUNT_ID"] = "PLACEHOLDER_ADD_LATER"

class TestNichePicker:
    def test_returns_valid_niche(self):
        from pipeline import pick_niche, NICHES
        assert pick_niche(0) in NICHES

    def test_niche_has_required_keys(self):
        from pipeline import pick_niche
        niche = pick_niche(0)
        for key in ["name","label","tone","emoji","pexels_queries"]:
            assert key in niche

class TestLanguagePicker:
    def test_en_hi_en_pattern(self):
        from pipeline import pick_language
        assert pick_language(0)["code"] == "en"
        assert pick_language(1)["code"] == "hi"
        assert pick_language(2)["code"] == "en"

    def test_lang_has_required_keys(self):
        from pipeline import pick_language
        lang = pick_language(0)
        for key in ["code","label","edge_voice","edge_rate","follow_part2"]:
            assert key in lang

class TestPartSeries:
    def test_non_third_video_no_part(self):
        from pipeline import get_current_part
        assert get_current_part(0) is None
        assert get_current_part(1) is None

    def test_third_video_has_part(self):
        from pipeline import get_current_part
        assert get_current_part(2) in [1, 2]

class TestTopicDeduplication:
    def test_save_load_used_topics(self, tmp_path):
        from pipeline import save_used_topic, is_topic_used
        import pipeline
        pipeline.OUT = tmp_path
        assert not is_topic_used("Black Holes")
        save_used_topic("Black Holes", "horror_facts")
        assert is_topic_used("Black Holes")

    def test_different_topics_not_duplicate(self, tmp_path):
        from pipeline import save_used_topic, is_topic_used
        import pipeline
        pipeline.OUT = tmp_path
        save_used_topic("Topic A", "horror_facts")
        assert not is_topic_used("Topic B")

class TestPartTopicPersistence:
    def test_save_and_load_part1(self, tmp_path):
        from pipeline import save_part1_topic, load_part1_topic
        import pipeline
        pipeline.OUT = tmp_path
        pipeline.PART1_TOPIC_FILE = tmp_path / "part1_topic.json"
        save_part1_topic("Test Topic", "horror_facts", "en")
        loaded = load_part1_topic()
        assert loaded is not None
        assert loaded["topic"] == "Test Topic"

    def test_load_returns_none_if_no_file(self, tmp_path):
        from pipeline import load_part1_topic
        import pipeline
        pipeline.PART1_TOPIC_FILE = tmp_path / "nonexistent.json"
        assert load_part1_topic() is None
