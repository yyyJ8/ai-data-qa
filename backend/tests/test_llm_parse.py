"""LLM 输出解析测试（不发起网络请求）。"""

import pytest

from app.llm.client import LLMFormatError, extract_json


def test_parses_plain_json():
    assert extract_json('{"sql": "SELECT 1"}') == {"sql": "SELECT 1"}


def test_parses_fenced_json():
    text = '```json\n{"sql": "SELECT 1", "chart": "bar"}\n```'
    assert extract_json(text)["chart"] == "bar"


def test_parses_json_with_surrounding_text():
    text = '好的，结果如下：{"sql": "SELECT 1"} 以上。'
    assert extract_json(text)["sql"] == "SELECT 1"


def test_parses_null_sql():
    payload = extract_json('{"sql": null, "chart": "none", "explanation": "缺少数据"}')
    assert payload["sql"] is None


def test_rejects_non_json():
    with pytest.raises(LLMFormatError):
        extract_json("抱歉，我无法回答")


def test_rejects_broken_json():
    with pytest.raises(LLMFormatError):
        extract_json('{"sql": "SELECT 1"')
