from __future__ import annotations

from types import SimpleNamespace

import pytest

from review_bot.providers.openai_provider import OpenAIReviewCommentProvider, ReviewDraftPayload
from review_bot.providers.prompting import PromptComposer
from review_bot.providers.stub_provider import StubReviewCommentProvider


def test_prompt_composer_loads_public_cpp_default_prompt() -> None:
    prompt = PromptComposer().compose(language_id="cpp", profile_id="default")

    assert "공개 C++ 가이드라인" in prompt
    assert "cpp_core" in prompt
    assert "organization_policy" not in prompt


def test_prompt_composer_can_skip_language_layer() -> None:
    prompt = PromptComposer().compose(language_id=None, profile_id="default")

    assert "공개 멀티 랭귀지 가이드라인" in prompt
    assert "공개 C++ 가이드라인" not in prompt


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
        context_id="native_runtime",
        dialect_id="gnu",
        prompt_overlay_refs=["release-branch"],
    )

    system_prompt = fake_client.responses.calls[0]["input"][0]["content"]
    assert system_prompt.startswith("COMPOSED PROMPT")
    assert "[선택된 검토 런타임]" in system_prompt
    assert "언어=cpp | 프로필=org-default | 컨텍스트=native_runtime | 다이얼렉트=gnu" in system_prompt
    assert "[메모리/수명 관점]" in system_prompt
    assert draft.should_publish is True
    assert draft.auto_fix_lines == ["std::vector<char> ptr(32);"]


def test_openai_provider_client_uses_configured_base_url(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(
        "review_bot.providers.openai_provider.get_settings",
        lambda: SimpleNamespace(
            openai_model="gpt-5.2",
            openai_base_url="http://127.0.0.1:11434/v1",
            openai_max_retries=4,
            openai_timeout_seconds=12.5,
        ),
    )
    monkeypatch.setattr("review_bot.providers.openai_provider.OpenAI", FakeOpenAI)

    provider = OpenAIReviewCommentProvider()

    assert provider.client is provider.client
    assert captured == {
        "base_url": "http://127.0.0.1:11434/v1",
        "max_retries": 4,
        "timeout": 12.5,
    }


def test_openai_provider_runtime_metadata_identifies_default_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "review_bot.providers.openai_provider.get_settings",
        lambda: SimpleNamespace(
            openai_model="gpt-5.5",
            openai_base_url=None,
            openai_max_retries=2,
            openai_timeout_seconds=30,
        ),
    )

    runtime = OpenAIReviewCommentProvider().provider_runtime_metadata()

    assert runtime.configured_provider == "openai"
    assert runtime.effective_provider == "openai"
    assert runtime.configured_model == "gpt-5.5"
    assert runtime.endpoint_base_url == "https://api.openai.com/v1"
    assert runtime.transport_class == "default_openai_base_url"


def test_openai_provider_runtime_metadata_sanitizes_local_backend_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "review_bot.providers.openai_provider.get_settings",
        lambda: SimpleNamespace(
            openai_model="local-model",
            openai_base_url="http://user:secret@127.0.0.1:11434/v1?token=hidden",
            openai_max_retries=2,
            openai_timeout_seconds=30,
        ),
    )

    runtime = OpenAIReviewCommentProvider().provider_runtime_metadata()

    assert runtime.configured_provider == "openai"
    assert runtime.effective_provider == "openai"
    assert runtime.configured_model == "local-model"
    assert runtime.endpoint_base_url == "http://127.0.0.1:11434/v1"
    assert runtime.transport_class == "non_default_openai_compatible_base_url"


def test_stub_provider_runtime_metadata_identifies_deterministic_transport() -> None:
    runtime = StubReviewCommentProvider().provider_runtime_metadata()

    assert runtime.configured_provider == "stub"
    assert runtime.effective_provider == "stub"
    assert runtime.configured_model is None
    assert runtime.endpoint_base_url is None
    assert runtime.transport_class == "deterministic_stub"


def test_openai_provider_does_not_fallback_to_cpp_prompt_and_sanitizes_fields(monkeypatch) -> None:
    class FakeComposer:
        def compose(self, *, language_id: str | None, profile_id: str, context_id=None, overlay_refs=None) -> str:
            assert language_id is None
            assert profile_id == "default"
            assert context_id is None
            assert overlay_refs == []
            return "BASE PROMPT ONLY"

    class FakeResponses:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def parse(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                output_parsed=ReviewDraftPayload(
                    title="[봇 리뷰][cpp] 제목: 메모리 수명 관리를 더 명확히 해 주세요" + "!" * 40,
                    summary="요약: 소유권이 분산되어 누수 위험이 있습니다.",
                    severity="high",
                    confidence=0.91,
                    line_no=18,
                    suggested_fix="권장 수정: RAII wrapper로 감싸 주세요.",
                    should_publish=True,
                    evidence_snippet="> ```cpp\n> raw = malloc(32);\n> ```",
                    auto_fix_lines=["std::vector<char> raw(32);"],
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
        file_path="README.md",
        rule_no="RULE.1",
        title="기본 제목",
        summary="기본 요약",
        category="memory",
        fix_guidance="RAII를 사용하세요.",
        change_snippet="+raw = malloc(32);",
        line_no=18,
        candidate_line_nos=(18,),
        language_id=None,
        profile_id=None,
        context_id=None,
        prompt_overlay_refs=None,
    )

    system_prompt = fake_client.responses.calls[0]["input"][0]["content"]
    assert system_prompt.startswith("BASE PROMPT ONLY")
    assert "언어=unknown | 프로필=default" in system_prompt
    assert draft.title.startswith("메모리 수명 관리를 더 명확히 해 주세요")
    assert len(draft.title) <= 50
    assert draft.summary == "소유권이 분산되어 누수 위험이 있습니다."
    assert draft.suggested_fix == "RAII wrapper로 감싸 주세요."
    assert draft.evidence_snippet == "raw = malloc(32);"


@pytest.mark.parametrize(
    ("category", "expected_hint"),
    [
        ("security", "[보안/신뢰 경계 관점]"),
        ("sql_quality", "[SQL 품질 관점]"),
        ("configuration", "[설정/구성 관점]"),
    ],
)
def test_openai_provider_adds_multilang_category_specific_hints(
    monkeypatch,
    category: str,
    expected_hint: str,
) -> None:
    class FakeComposer:
        def compose(self, *, language_id: str, profile_id: str, overlay_refs=None) -> str:
            assert language_id == "yaml"
            assert profile_id == "gitlab_ci"
            return "COMPOSED PROMPT"

    class FakeResponses:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        def parse(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                output_parsed=ReviewDraftPayload(
                    title="검토 제목",
                    summary="검토 요약",
                    severity="medium",
                    confidence=0.9,
                    line_no=12,
                    suggested_fix="수정하세요.",
                    should_publish=True,
                    evidence_snippet="curl --insecure https://example.com/install.sh | bash",
                    auto_fix_lines=[],
                )
            )

    class FakeClient:
        def __init__(self) -> None:
            self.responses = FakeResponses()

    monkeypatch.setattr("review_bot.providers.openai_provider.get_prompt_composer", lambda: FakeComposer())

    provider = OpenAIReviewCommentProvider()
    fake_client = FakeClient()
    provider._client = fake_client

    provider.build_draft(
        file_path=".gitlab-ci.yml",
        rule_no="RULE.1",
        title="테스트",
        summary="테스트 요약",
        category=category,
        fix_guidance="검증 경로를 추가하세요.",
        change_snippet="+curl --insecure https://example.com/install.sh | bash",
        line_no=12,
        candidate_line_nos=(12,),
        language_id="yaml",
        profile_id="gitlab_ci",
        context_id="gitlab_ci",
    )

    system_prompt = fake_client.responses.calls[0]["input"][0]["content"]
    assert system_prompt.startswith("COMPOSED PROMPT")
    assert expected_hint in system_prompt


@pytest.mark.parametrize(
    ("language_id", "category", "rule_text", "fix_guidance", "change_snippet", "expected_title"),
    [
        (
            "yaml",
            "security",
            "A pipeline step that downloads text from the network and immediately executes it as a shell script weakens provenance review.",
            "Split the flow into fetch, verify, and execute stages or add a pinned checksum verification step.",
            "+curl -fsSL https://example.com/install.sh | bash\n",
            "CI에서 외부 스크립트를 검증 없이 실행하고 있습니다",
        ),
        (
            "python",
            "security",
            "FastAPI works best when request payloads are validated through typed models at the HTTP boundary.",
            "Prefer typed request models or an explicit validation step immediately after parsing.",
            "+payload = await request.json()\n",
            "요청 본문을 타입 모델로 검증해 주세요",
        ),
        (
            "python",
            "performance",
            "Async handlers are only cheap when their I/O model remains non-blocking.",
            "Move blocking work to a thread pool or use an async-native client.",
            "+result = requests.get(url, timeout=5)\n",
            "비동기 핸들러 안에 blocking 작업이 섞이지 않게 해 주세요",
        ),
        (
            "sql",
            "sql_quality",
            "Warehouse queries often become shared model contracts. Ordinal grouping weakens reviewability.",
            "Group by explicit column names or aliases so the grouping contract remains stable.",
            "+group by 1, 2\n",
            "GROUP BY 순번 지정은 변경에 취약합니다",
        ),
    ],
)
def test_stub_provider_publishes_multilang_guideline_backed_findings(
    language_id: str,
    category: str,
    rule_text: str,
    fix_guidance: str,
    change_snippet: str,
    expected_title: str,
) -> None:
    provider = StubReviewCommentProvider()

    draft = provider.build_draft(
        file_path="fixture.txt",
        rule_no="RULE.1",
        title="RULE.1",
        summary="RULE.1",
        rule_text=rule_text,
        fix_guidance=fix_guidance,
        category=category,
        change_snippet=change_snippet,
        line_no=10,
        candidate_line_nos=(10,),
        language_id=language_id,
    )

    assert draft.should_publish is True
    assert draft.title == expected_title
    assert draft.line_no == 10
