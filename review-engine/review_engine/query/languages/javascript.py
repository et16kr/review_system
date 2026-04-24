from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="javascript",
    display_name="JavaScript",
    default_focus="async error handling, runtime type assumptions, DOM safety, module-side effects, and Next.js boundary safety",
    pattern_specs=(
        PatternSpec(
            "eval_usage",
            r"\beval\s*\(",
            "eval usage detected; review code injection risk and safer parsing alternatives.",
            1.0,
        ),
        PatternSpec(
            "function_constructor",
            r"(?:\bnew\s+Function\s*\(|(?<![\w.])(?<!function\s)Function\s*\()",
            "Function constructor detected; review dynamic code compilation and safer dispatch alternatives.",
            0.98,
        ),
        PatternSpec(
            "innerhtml",
            r"\.innerHTML\s*=",
            "innerHTML assignment detected; review DOM injection and escaping boundaries.",
            0.95,
        ),
        PatternSpec(
            "loose_equality",
            r"[^=!]==[^=]|!=[^=]",
            "Loose equality detected; review coercion risk and intent clarity.",
            0.72,
        ),
        PatternSpec(
            "promise_without_await",
            r"\.then\s*\(",
            "Promise chaining detected; review error propagation and async readability.",
            0.72,
        ),
        PatternSpec(
            "document_write",
            r"document\.write\s*\(",
            "document.write detected; review raw HTML injection and page mutation safety.",
            0.98,
        ),
        PatternSpec(
            "settimeout_string",
            r"\b(?:setTimeout|setInterval)\s*\(\s*[\"']",
            "String-based timer callback detected; review dynamic execution and safer function references.",
            0.92,
        ),
        PatternSpec(
            "next_route_request_json",
            r"(?is)export\s+async\s+function\s+(?:POST|PUT|PATCH)\s*\([^)]*request[^)]*\)[\s\S]{0,500}await\s+request\.json\s*\(",
            "Next.js route handler reads request.json() directly; review schema validation at the HTTP boundary.",
            0.94,
        ),
        PatternSpec(
            "next_server_action_formdata",
            r"(?is)['\"]use server['\"];?[\s\S]{0,500}\bformData\.get\s*\(",
            "Next.js server action reads FormData directly; review validation and coercion at the action boundary.",
            0.9,
        ),
        PatternSpec(
            "next_client_secret_env",
            r"(?is)['\"]use client['\"];?[\s\S]{0,500}\bprocess\.env\.(?!NEXT_PUBLIC_)",
            "Client component accesses a non-public env var; review server/client secret boundary leakage.",
            0.99,
        ),
        PatternSpec(
            "next_server_component_browser_api",
            r"(?is)^(?![\s\S]*['\"]use client['\"]).*?\b(?:window|document|localStorage|sessionStorage)\.",
            "Browser API detected without a visible use client boundary; review server/client component split.",
            0.92,
        ),
    ),
    hinted_rules={
        "eval_usage": ("JS.1", "JS.4"),
        "function_constructor": ("JS.6",),
        "innerhtml": ("JS.2", "JS.3"),
        "loose_equality": ("JS.NODE.2", "JS.NODE.4"),
        "promise_without_await": ("JS.NODE.1", "JS.NODE.3"),
        "document_write": ("JS.5",),
        "settimeout_string": ("JS.NODE.5",),
        "next_route_request_json": ("JS.NEXT.1",),
        "next_server_action_formdata": ("JS.NEXT.2",),
        "next_client_secret_env": ("JS.NEXT.3",),
        "next_server_component_browser_api": ("JS.NEXT.4", "JS.NEXT.REF.2"),
    },
    direct_hint_patterns={
        "eval_usage",
        "function_constructor",
        "innerhtml",
        "loose_equality",
        "promise_without_await",
        "document_write",
        "settimeout_string",
        "next_route_request_json",
        "next_server_action_formdata",
        "next_client_secret_env",
        "next_server_component_browser_api",
    },
)
