from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="dockerfile",
    display_name="Dockerfile",
    default_focus="base-image pinning, layer hygiene, secret handling, and non-root runtime defaults",
    pattern_specs=(
        PatternSpec(
            "latest_tag",
            r"(?im)^[+-]?\s*FROM\s+\S+:latest\s*$",
            "Mutable latest base image detected; review reproducibility and rollback behavior.",
            0.92,
        ),
        PatternSpec(
            "root_user",
            r"(?im)^[+-]?\s*USER\s+root\s*$",
            "Container configured to run as root; review least-privilege runtime expectations.",
            0.95,
        ),
        PatternSpec(
            "apt_get_update_install_split",
            r"(?im)^[+-]?\s*RUN\s+apt-get\s+update\s*$",
            "apt-get update in its own layer detected; review cache invalidation and stale package indexes.",
            0.85,
        ),
        PatternSpec(
            "copy_dot",
            r"(?im)^[+-]?\s*COPY\s+\.\s+\.",
            "Broad COPY . . detected; review cache scope and accidental secret inclusion.",
            0.82,
        ),
        PatternSpec(
            "add_remote_url",
            r"(?im)^[+-]?\s*ADD\s+https?://",
            "Remote URL ADD detected; review supply-chain visibility and cache behavior.",
            0.94,
        ),
        PatternSpec(
            "apt_upgrade",
            r"(?im)^[+-]?\s*RUN\s+.*apt-get\s+upgrade\b",
            "apt-get upgrade detected in an image build; review reproducibility and unexpected base-image drift.",
            0.78,
        ),
        PatternSpec(
            "curl_pipe_shell_run",
            r"(?im)^[+-]?\s*RUN\s+.*curl\b.*\|\s*(?:bash|sh)\b",
            "curl piped to a shell during image build detected; review provenance, pinning, and explicit verification.",
            0.99,
        ),
    ),
    hinted_rules={
        "latest_tag": ("DOCKER.1", "DOCKER.3"),
        "root_user": ("DOCKER.SEC.1", "DOCKER.SEC.3"),
        "apt_get_update_install_split": ("DOCKER.2",),
        "copy_dot": ("DOCKER.SEC.2", "DOCKER.SEC.4", "DOCKER.4"),
        "add_remote_url": ("DOCKER.5", "DOCKER.SEC.6"),
        "apt_upgrade": ("DOCKER.6",),
        "curl_pipe_shell_run": ("DOCKER.SEC.5",),
    },
    direct_hint_patterns={
        "latest_tag",
        "root_user",
        "apt_get_update_install_split",
        "copy_dot",
        "add_remote_url",
        "apt_upgrade",
        "curl_pipe_shell_run",
    },
)
