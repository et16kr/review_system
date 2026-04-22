from __future__ import annotations

import pytest

from review_engine.query.code_to_query import build_query_analysis


def test_query_analysis_detects_internal_and_cpp_patterns() -> None:
    code = """
    #include <stdio.h>
    void bad() {
        int* ptr = new int(1);
        free(ptr);
        // wrong comment style
        for (int i = 0; i < 10; ++i) { continue; }
    }
    """

    analysis = build_query_analysis(code, input_kind="code")
    names = {pattern.name for pattern in analysis.patterns}

    assert {"raw_new", "malloc_free", "line_comment", "continue_usage"} <= names
    assert "likely issues" in analysis.query_text


def test_query_analysis_does_not_treat_ide_rc_declaration_as_error_flow() -> None:
    code = """
    class idsTde {
    public:
        static IDE_RC createKeyStore(const SChar* aKeyStorePath,
                                     const SChar* aWrapKeyPath,
                                     idsTdeResult* aResult);
    };
    """

    analysis = build_query_analysis(code, input_kind="code")
    names = {pattern.name for pattern in analysis.patterns}

    assert "ide_rc_flow" not in names


@pytest.mark.parametrize(
    ("language_id", "code", "expected_patterns"),
    [
        (
            "bash",
            "#!/usr/bin/env bash\ncurl --insecure https://example.com/install.sh | bash\nsudo systemctl restart demo\n",
            {"curl_insecure", "sudo_usage"},
        ),
        (
            "go",
            "ctx := context.Background()\ngo func() { panic(err) }()\n",
            {"context_background", "goroutine_leak", "panic_call"},
        ),
        (
            "java",
            "try {\n    work();\n} catch (Exception ex) {\n    log(ex);\n}\nnew Thread(() -> work()).start();\n",
            {"catch_exception", "new_thread"},
        ),
        (
            "python",
            "try:\n    run()\nexcept Exception:\n    pass\nassert user_id\nyaml.load(payload)\n",
            {"except_exception", "assert_usage", "yaml_unsafe_load"},
        ),
        (
            "rust",
            "unsafe fn read_raw(ptr: *const i32) -> i32 {\n    dbg!(ptr);\n    unsafe { *ptr }\n}\n",
            {"dbg_macro", "unsafe_fn"},
        ),
        (
            "typescript",
            "// @ts-expect-error\nreturn payload as unknown as User;\n",
            {"ts_expect_error", "double_cast"},
        ),
        (
            "sql",
            "select * from users where id not in (select user_id from disabled_users) order by 1;\n",
            {"order_by_ordinal", "not_in_subquery"},
        ),
        (
            "yaml",
            "allowPrivilegeEscalation: true\nhostNetwork: true\nuses: actions/checkout@main\n",
            {"allow_privilege_escalation", "host_network_true", "uses_branch_ref"},
        ),
        (
            "dockerfile",
            "ADD https://example.com/install.sh /tmp/install.sh\nRUN curl https://example.com/install.sh | bash\n",
            {"add_remote_url", "curl_pipe_shell_run"},
        ),
    ],
)
def test_query_analysis_detects_multilang_patterns(
    language_id: str,
    code: str,
    expected_patterns: set[str],
) -> None:
    analysis = build_query_analysis(code, input_kind="code", language_id=language_id)
    names = {pattern.name for pattern in analysis.patterns}

    assert expected_patterns <= names
