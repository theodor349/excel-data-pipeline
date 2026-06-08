import json

import pytest

import engine.settings as settings


def test_get_default_places_matches_committed_file():
    settings._settings_cache = None
    assert settings.get_default_places() == 2


def test_negative_places_raises(tmp_path, monkeypatch):
    (tmp_path / "settings.json").write_text(json.dumps({"decimal_places": -1}))
    monkeypatch.setattr(settings, "_find_project_root", lambda: tmp_path)
    settings._settings_cache = None
    with pytest.raises(ValueError):
        settings.get_default_places()
    settings._settings_cache = None  # don't leak the bad cache to other tests


def test_missing_places_raises(tmp_path, monkeypatch):
    (tmp_path / "settings.json").write_text(json.dumps({}))
    monkeypatch.setattr(settings, "_find_project_root", lambda: tmp_path)
    settings._settings_cache = None
    with pytest.raises(ValueError):
        settings.get_default_places()
    settings._settings_cache = None
