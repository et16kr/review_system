from __future__ import annotations

import httpx

from app.config import Settings

CPP_CORE_GUIDELINES_URL = "https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines"


def fetch_cpp_core_guidelines(settings: Settings, force_refresh: bool = False) -> str:
    if settings.cpp_core_html_cache.exists() and not force_refresh:
        return settings.cpp_core_html_cache.read_text(encoding="utf-8")

    response = httpx.get(CPP_CORE_GUIDELINES_URL, follow_redirects=True, timeout=60.0)
    response.raise_for_status()
    settings.cpp_core_html_cache.parent.mkdir(parents=True, exist_ok=True)
    settings.cpp_core_html_cache.write_text(response.text, encoding="utf-8")
    return response.text
