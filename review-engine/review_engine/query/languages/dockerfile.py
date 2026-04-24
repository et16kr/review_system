from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="dockerfile",
    display_name="Dockerfile",
    default_focus="base-image pinning, layer hygiene, secret handling, and non-root runtime defaults",
    pattern_specs=(
        PatternSpec(
            "latest_tag",
            r"(?im)^[+-]?\s*FROM\s+(?:--platform=\S+\s+)?\S+:latest(?:\s+AS\s+\S+)?(?:\s+#.*)?\s*$",
            "Mutable latest base image detected; review reproducibility and rollback behavior.",
            0.92,
        ),
        PatternSpec(
            "base_tag_without_digest",
            r"(?im)^[+-]?\s*FROM\s+(?:--platform=\S+\s+)?(?!\S+@sha256:)(?!\S+:latest(?:\s|$))\S+:[^\s@]+(?:\s+AS\s+\S+)?(?:\s+#.*)?\s*$",
            "Version-tagged base image without an immutable digest detected; review reproducibility and supply-chain traceability.",
            0.86,
        ),
        PatternSpec(
            "root_user",
            r"(?im)^[+-]?\s*USER\s+(?:root|0)\s*$",
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
            "copy_from_builder_usr_local",
            r"(?im)^[+-]?\s*COPY\s+(?=[^\n]*--from=\S+)(?:--\S+\s+)+/usr/local/?\s+/usr/local/?(?:\s+#.*)?\s*$",
            "Builder-stage /usr/local tree copied wholesale into runtime image; review whether toolchain residue is leaking past the stage boundary.",
            0.84,
        ),
        PatternSpec(
            "build_secret_arg_env",
            r"(?im)^[+-]?\s*(?:ARG|ENV)\s+[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|PASSWD|API[_-]?KEY|ACCESS[_-]?KEY|SECRET[_-]?KEY)\b",
            "Credential-bearing ARG/ENV detected in Dockerfile; review whether BuildKit secret mounts should carry this instead of image metadata.",
            0.93,
        ),
        PatternSpec(
            "build_secret_arg_env_authenticated_url",
            r"(?im)^[+-]?\s*(?:ARG|ENV)\s+\S+(?:\s*=|\s+)https?://[^/\s:@]+:[^/\s@]+@",
            "Authenticated URL assigned through ARG/ENV detected in Dockerfile; review whether BuildKit secret mounts should carry this instead of image metadata.",
            0.92,
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
        PatternSpec(
            "apt_get_install_unpinned",
            (
                r"(?im)^[+-]?\s*RUN\s+"
                r"(?=[^\n]*\bapt-get\s+install\b)"
                r"(?![^\n]*\bapt-get\s+install\b[^\n]*"
                r"(?:\b[A-Za-z0-9][A-Za-z0-9+.-]*=|\$[{(]|\$[A-Za-z_]))"
                r"[^\n]*\b(?:ca-certificates|curl|git|build-essential|gcc|g\+\+|make|"
                r"openssl|libssl-dev|python3|nodejs|npm)\b[^\n]*$"
            ),
            "Unpinned apt-get package install detected; review image rebuild reproducibility and package provenance.",
            0.82,
        ),
    ),
    hinted_rules={
        "latest_tag": ("DOCKER.1", "DOCKER.3"),
        "base_tag_without_digest": ("DOCKER.3",),
        "root_user": ("DOCKER.SEC.1", "DOCKER.SEC.3"),
        "apt_get_update_install_split": ("DOCKER.2",),
        "copy_dot": ("DOCKER.SEC.2", "DOCKER.SEC.4", "DOCKER.4"),
        "copy_from_builder_usr_local": ("DOCKER.7",),
        "build_secret_arg_env": ("DOCKER.SEC.7",),
        "build_secret_arg_env_authenticated_url": ("DOCKER.SEC.7",),
        "add_remote_url": ("DOCKER.5", "DOCKER.SEC.6"),
        "apt_upgrade": ("DOCKER.6",),
        "curl_pipe_shell_run": ("DOCKER.SEC.5",),
        "apt_get_install_unpinned": ("DOCKER.8",),
    },
    direct_hint_patterns={
        "latest_tag",
        "base_tag_without_digest",
        "root_user",
        "apt_get_update_install_split",
        "copy_dot",
        "copy_from_builder_usr_local",
        "build_secret_arg_env",
        "build_secret_arg_env_authenticated_url",
        "add_remote_url",
        "apt_upgrade",
        "curl_pipe_shell_run",
        "apt_get_install_unpinned",
    },
)
