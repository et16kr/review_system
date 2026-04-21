from __future__ import annotations

from types import SimpleNamespace

from review_bot.providers.openai_provider import OpenAIReviewCommentProvider, ReviewDraftPayload
from review_bot.providers.prompting import PromptComposer


def test_prompt_composer_loads_public_cpp_default_prompt() -> None:
    prompt = PromptComposer().compose(language_id="cpp", profile_id="default")

    assert "공개 C++ 가이드라인" in prompt
    assert "cpp_core" in prompt
    assert "Altibase" not in prompt


def test_openai_provider_uses_composed_prompt_as_system_prompt(monkeypatch) -> None:
    class FakeComposer:
        def compose(self, *, language_id: str, profile_id: str, overlay_refs=None) -> str:
            assert language_id == "cpp"
            assert profile_id == "org-default"
            assert overlay_refs == ["release-branch"]
            return "COMPOSED PROMPT"

    class FakeResponses:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def parse(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                output_parsed=ReviewDraftPayload(
                    title="메모리 소유권이 모호합니다",
                    summary="소유권이 불명확해 누수 가능성이 있습니다.",
                    severity="high",
                    confidence=0.95,
                    line_no=10,
                    suggested_fix="RAII를 사용하세요.",
                    should_publish=True,
                    evidence_snippet="char* ptr = (char*)malloc(32);",
                    auto_fix_lines=["std::vector<char> ptr(32);"],
                )
            )

    class FakeClient:
        def __init__(self) -> None:
            self.responses = FakeResponses()

    monkeypatch.setattr("review_bot.providers.openai_provider.get_prompt_composer", lambda: FakeComposer())

    provider = OpenAIReviewCommentProvider()
    fake_client = FakeClient()
    provider._client = fake_client

    draft = provider.build_draft(
        file_path="src/sample.cpp",
        rule_no="R.10",
        title="직접 메모리 할당 사용",
        summary="malloc 사용이 보입니다.",
        category="memory",
        fix_guidance="표준 컨테이너를 사용하세요.",
        change_snippet="+char* ptr = (char*)malloc(32);",
        line_no=10,
        candidate_line_nos=(10,),
        language_id="cpp",
        profile_id="org-default",
        prompt_overlay_refs=["release-branch"],
    )

    system_prompt = fake_client.responses.calls[0]["input"][0]["content"]
    assert system_prompt.startswith("COMPOSED PROMPT")
    assert "[메모리/수명 관점]" in system_prompt
    assert draft.should_publish is True
    assert draft.auto_fix_lines == ["std::vector<char> ptr(32);"]
