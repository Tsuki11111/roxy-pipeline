from __future__ import annotations

import pytest

from app.providers.llm import extract_json


def test_extract_json_repairs_trailing_commas():
    value = extract_json('```json\n{"shots":[{"line_seq":1,},],}\n```')
    assert value["shots"][0]["line_seq"] == 1


def test_extract_json_rejects_non_object():
    with pytest.raises(ValueError):
        extract_json("[1, 2, 3]")
