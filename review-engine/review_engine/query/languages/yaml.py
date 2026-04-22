from __future__ import annotations

from review_engine.query.languages.base import LanguageQueryPlugin, PatternSpec


PLUGIN = LanguageQueryPlugin(
    plugin_id="yaml",
    display_name="YAML",
    default_focus="schema intent, CI/CD safety, Kubernetes security defaults, and configuration drift",
    pattern_specs=(
        PatternSpec(
            "latest_tag",
            r"(?im)^[+-]?\s*image:\s*.+:latest\s*$",
            "Mutable latest image tag detected; review reproducibility and deployment rollback safety.",
            0.9,
        ),
        PatternSpec(
            "privileged_true",
            r"(?im)^[+-]?\s*privileged:\s*true\s*$",
            "Privileged container setting detected; review least-privilege expectations.",
            1.0,
        ),
        PatternSpec(
            "permissions_write_all",
            r"(?im)^[+-]?\s*permissions:\s*write-all\s*$",
            "Broad workflow permissions detected; review GitHub Actions token scope.",
            0.98,
        ),
        PatternSpec(
            "run_as_root",
            r"(?im)^[+-]?\s*runAsUser:\s*0\s*$",
            "runAsUser: 0 detected; review container runtime privilege assumptions.",
            0.95,
        ),
        PatternSpec(
            "allow_privilege_escalation",
            r"(?im)^[+-]?\s*allowPrivilegeEscalation:\s*true\s*$",
            "allowPrivilegeEscalation: true detected; review whether the workload really needs privilege expansion.",
            0.96,
        ),
        PatternSpec(
            "host_network_true",
            r"(?im)^[+-]?\s*hostNetwork:\s*true\s*$",
            "hostNetwork: true detected; review pod isolation expectations and whether node network sharing is necessary.",
            0.9,
        ),
        PatternSpec(
            "uses_branch_ref",
            r"(?im)^[+-]?\s*-?\s*uses:\s*[^@\s]+@(main|master)\s*$",
            "GitHub Action branch ref detected; review provenance and whether the action should be pinned more tightly.",
            0.92,
        ),
    ),
    hinted_rules={
        "latest_tag": ("YAML.CI.2", "YAML.CI.4", "YAML.2", "YAML.HELM.2"),
        "privileged_true": ("YAML.K8S.1", "YAML.K8S.3"),
        "permissions_write_all": ("YAML.CI.1", "YAML.CI.3"),
        "run_as_root": ("YAML.K8S.2", "YAML.K8S.4"),
        "allow_privilege_escalation": ("YAML.K8S.5",),
        "host_network_true": ("YAML.K8S.6",),
        "uses_branch_ref": ("YAML.CI.5",),
    },
    direct_hint_patterns={
        "latest_tag",
        "privileged_true",
        "permissions_write_all",
        "run_as_root",
        "allow_privilege_escalation",
        "host_network_true",
        "uses_branch_ref",
    },
)
