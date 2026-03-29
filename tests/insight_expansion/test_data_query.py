"""Tests for DataQueryEngine."""

import sys
import os
# Add src to path relative to this test file location
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(test_dir))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

print(f"DEBUG: test_dir={test_dir}")
print(f"DEBUG: project_root={project_root}")
print(f"DEBUG: src_path={src_path}")
print(f"DEBUG: sys.path={sys.path}")

from insight_expansion.data_query import DataQueryEngine


def test_data_query_engine_loads_csv_and_returns_unique_categories():
    engine = DataQueryEngine("data/eda_structured.csv")
    categories = engine.get_unique_values("category")
    assert isinstance(categories, list)
    assert len(categories) >= 3
    assert "Technology" in categories
    assert "Furniture" in categories
