from __future__ import annotations

from types import SimpleNamespace

from solution_gen.domain import Chapter, DocType, Job, JobStatus, Profile
from solution_gen.skills.document import export_docx
from solution_gen.workers.prose import extract_model_text, is_chapter_prose, is_exportable_body


def test_extract_ignores_empty_final_response_dump() -> None:
    dump = (
        "RunResult(session_id='session-1', final_response='', finish_reason='max-tokens', "
        "events=[{'type': 'assistant/chunk'}])"
    )
    assert extract_model_text(dump) == ""
    assert is_chapter_prose(dump) is False


def test_writing_guide_is_not_exportable_body() -> None:
    guide = "写概述，覆盖：项目名称、建设目标、建设地点、建设内容收口。"
    assert is_exportable_body(guide) is False
    assert is_exportable_body("青岛市低空经济基础设施建设项目概述如下。建设周期24个月，总投资3000万元。") is True


def test_extract_uses_assistant_text_block_not_reasoning() -> None:
    result = SimpleNamespace(
        final_response="",
        events=[
            {
                "type": "assistant/message",
                "data": {
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "reasoning", "text": "Let me think"},
                            {"type": "text", "text": "固安县低空经济基础设施建设项目概述如下。建设周期24个月。"},
                        ],
                    }
                },
            }
        ],
    )
    text = extract_model_text(result)
    assert "概述如下" in text
    assert "Let me think" not in text
    assert "RunResult" not in text


def test_extract_assembles_text_deltas() -> None:
    result = SimpleNamespace(
        final_response="",
        events=[
            {"type": "assistant/chunk", "data": {"chunk": {"type": "reasoning-delta", "text": "hmm"}}},
            {"type": "assistant/chunk", "data": {"chunk": {"type": "text-delta", "text": "项目在固安县实施低空经济基础设施"}}},
            {"type": "assistant/chunk", "data": {"chunk": {"type": "text-delta", "text": "建设，建设周期二十四个月。"}}},
        ],
    )
    assert "项目在固安县实施" in extract_model_text(result)


def test_export_docx_skips_runresult_dump(tmp_path) -> None:
    job = Job(
        id="jdump",
        doc_type=DocType.SOLUTION,
        status=JobStatus.DELIVERED,
        profile=Profile(place="固安", industry="低空经济", project_name="固安项目"),
        chapters=[
            Chapter(
                id="c1",
                title="概述",
                brief="交代范围。",
                content="RunResult(session_id='x', final_response='', events=[{'type': 'assistant/chunk'}])",
            )
        ],
    )
    path = tmp_path / "out.docx"
    export_docx(job, path)
    from docx import Document

    texts = [p.text for p in Document(str(path)).paragraphs]
    blob = "\n".join(texts)
    assert "RunResult" not in blob
    assert "assistant/chunk" not in blob
    assert "交代范围。" not in blob
