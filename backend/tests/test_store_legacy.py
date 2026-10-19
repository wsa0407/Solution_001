from __future__ import annotations

import json

from solution_gen.domain import Job
from solution_gen.store import _load, save_job


def test_legacy_payload_loads() -> None:
    raw = json.dumps(
        {
            "id": "old1",
            "doc_type": "solution",
            "status": "profile",
            "owner": "demo",
            "profile": {"place": "成都市", "industry": "低空经济", "words": 20000, "need": "x"},
            "chapters": [],
        }
    )
    job = _load(raw)
    assert job.id == "old1"
    assert job.profile and job.profile.place == "成都市"
    assert job.pending_confirm is None
    assert job.diagram_requests == []
    assert job.chat_log == []


def test_round_trip_new_fields(tmp_path, monkeypatch) -> None:
    from solution_gen import store as store_mod
    from solution_gen.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    job = Job(id="n1")
    job.brief_complete = True
    saved = save_job(job)
    again = store_mod.get_job("n1")
    assert again.brief_complete is True
    assert saved.id == "n1"
