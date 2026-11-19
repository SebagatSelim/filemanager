"""OpenAI analyser: output validation and fallback (no network: the client is faked)."""
import json
from types import SimpleNamespace

import pytest

from app.services.ai import openai_provider
from app.services.ai.openai_provider import OpenAIAnalyzer

TEXT = "Assignment for Database Systems, Semester 1. ER modelling, normalisation and SQL queries." * 3


class FakeCompletions:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=reply))])


def make_analyzer(replies):
    completions = FakeCompletions(replies)
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    analyzer = OpenAIAnalyzer(api_key="test-key", model="gpt-test", max_chars=4000, client=client)
    return analyzer, completions


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(openai_provider.time, "sleep", lambda seconds: None)


def test_valid_json_is_used_and_cleaned():
    reply = json.dumps({
        "title": "Database Assignment", "summary": "ER and SQL work.", "category": "university",
        "subject": "Database Systems", "document_type": "Assignment", "keywords": ["SQL", "ER", "SQL"],
        "suggested_filename": "Semester1 Database/Assignment", "suggested_folder_path": ["University", "Sem/1"],
        "confidence": 1.7,
    })
    analyzer, calls = make_analyzer([reply])
    result = analyzer.analyze(TEXT, "a.pdf", [["University", "Year 2"]], ".pdf")
    assert calls.calls == 1
    assert result.category == "University"           # case fixed
    assert result.keywords == ["SQL", "ER"]           # duplicates removed
    assert result.suggested_filename == "Semester1_Database_Assignment.pdf"
    assert result.suggested_folder_path == ["University", "Sem-1"]  # no slashes inside folder names
    assert result.confidence == 1.0                   # clamped
    assert result.model == "openai:gpt-test"


def test_bad_output_is_retried_then_falls_back_to_local():
    analyzer, calls = make_analyzer(["not json", RuntimeError("rate limited"), json.dumps({"no": "title"})])
    result = analyzer.analyze(TEXT, "a.pdf", [], ".pdf")
    assert calls.calls == 3
    assert result.model == "local-fallback"
    assert result.category == "University"


def test_short_text_skips_the_api():
    analyzer, calls = make_analyzer([])
    result = analyzer.analyze("tiny", "photo.jpg", [], ".jpg")
    assert calls.calls == 0 and result.category == "Uncategorised"


def gpt_reply(**overrides):
    data = {
        "title": "SQL Lab 5", "summary": "Joins and normal forms.", "category": "University",
        "subject": "Database Systems", "document_type": "Lab Sheet", "keywords": ["SQL", "joins"],
        "suggested_filename": "SQL_Lab_5", "existing_folder": "", "suggested_folder_path": ["University"],
        "folder_reason": "", "confidence": 0.9,
    }
    data.update(overrides)
    return json.dumps(data)


EXISTING = [["University"], ["University", "Year 2"], ["University", "Year 2", "Database Systems"], ["Finance"]]


def test_gpt_picks_an_existing_folder_with_its_real_spelling_and_reason():
    reply = gpt_reply(existing_folder="university/year 2/DATABASE SYSTEMS",
                      suggested_folder_path=["University", "Databases"],
                      folder_reason="Same course as the other Database Systems work.")
    analyzer, _ = make_analyzer([reply])
    result = analyzer.analyze(TEXT, "lab.pdf", EXISTING, ".pdf")
    assert result.suggested_folder_path == ["University", "Year 2", "Database Systems"]
    assert result.folder_reason == "Same course as the other Database Systems work."


def test_gpt_folder_that_does_not_exist_falls_back_to_its_suggested_path():
    reply = gpt_reply(existing_folder="University/Year 9/Made Up", suggested_folder_path=["University", "Networks"])
    analyzer, _ = make_analyzer([reply])
    result = analyzer.analyze(TEXT, "lab.pdf", EXISTING, ".pdf")
    assert result.suggested_folder_path == ["University", "Networks"]


def test_prompt_sends_the_existing_folders_to_gpt():
    analyzer, calls = make_analyzer([gpt_reply()])
    sent = []
    original = calls.create
    calls.create = lambda **kwargs: sent.append(kwargs) or original(**kwargs)
    analyzer.analyze(TEXT, "lab.pdf", EXISTING, ".pdf")
    user_message = sent[0]["messages"][1]["content"]
    assert "University/Year 2/Database Systems" in user_message
