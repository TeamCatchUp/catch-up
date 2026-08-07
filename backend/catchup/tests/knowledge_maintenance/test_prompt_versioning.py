"""versioned_prompt가 내용 변경을 버전에 반영하는지 구속한다."""

from pathlib import Path

from catchup.knowledge_maintenance.adapters.llm.prompt_versioning import (
    versioned_prompt,
)
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import (
    TEMPLATE_PATH,
)
from catchup.prompts.loader import prompt_loader


def test_versioned_prompt_format() -> None:
    version = versioned_prompt(TEMPLATE_PATH)
    path, _, digest = version.partition("@")
    assert path == TEMPLATE_PATH
    assert len(digest) == 12
    assert all(c in "0123456789abcdef" for c in digest)
    assert len(version) <= 128  # extraction_runs.prompt_version 컬럼 한계


def test_versioned_prompt_stable_for_same_content() -> None:
    assert versioned_prompt(TEMPLATE_PATH) == versioned_prompt(TEMPLATE_PATH)


def test_versioned_prompt_changes_with_content(
    tmp_path: Path, monkeypatch
) -> None:
    template = tmp_path / "sample.j2"
    template.write_text("v1 내용", encoding="utf-8")
    monkeypatch.setattr(prompt_loader, "template_dir", tmp_path)
    versioned_prompt.cache_clear()
    first = versioned_prompt("sample.j2")

    template.write_text("v2 내용", encoding="utf-8")
    versioned_prompt.cache_clear()
    second = versioned_prompt("sample.j2")

    assert first != second
    versioned_prompt.cache_clear()
