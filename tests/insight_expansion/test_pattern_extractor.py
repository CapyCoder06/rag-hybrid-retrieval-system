"""Tests for PatternExtractor."""

import sys
import os
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(test_dir))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from insight_expansion.pattern_extractor import PatternExtractor


def test_extract_fact_pattern_returns_correct_structure():
    seed = {
        "text": "Technology has highest profit with margin 14%",
        "dimensions": ["category"],
        "metrics": ["profit", "margin"],
        "type_hint": "fact"
    }
    pattern = PatternExtractor.extract(seed, None)
    assert pattern["primary_dimension"] == "category"
    assert pattern["metrics"] == ["profit", "margin"]
    assert pattern["comparison_type"] == "rank"
    assert "{entity}" in pattern["text_format"]


def test_extract_uses_type_hint_not_text():
    seed = {
        "text": "Sales are increasing year over year",
        "dimensions": ["year"],
        "metrics": ["sales"],
        "type_hint": "trend"
    }
    pattern = PatternExtractor.extract(seed, None)
    assert pattern["comparison_type"] == "direction"
    assert "{direction}" in pattern["text_format"]
