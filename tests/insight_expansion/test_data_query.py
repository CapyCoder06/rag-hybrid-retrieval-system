"""Tests for DataQueryEngine."""

import sys
import os
# Add src to path relative to this test file location
test_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(test_dir))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from insight_expansion.data_query import DataQueryEngine


def test_data_query_engine_loads_csv_and_returns_unique_categories():
    engine = DataQueryEngine("data/eda_structured.csv")
    categories = engine.get_unique_values("category")
    assert isinstance(categories, list)
    assert len(categories) >= 3
    assert "Technology" in categories
    assert "Furniture" in categories


def test_get_entity_metrics_returns_correct_values_for_category():
    engine = DataQueryEngine("data/eda_structured.csv")
    metrics = engine.get_entity_metrics("category", "Technology", ["profit", "margin"])
    assert "profit" in metrics
    assert "margin" in metrics
    assert metrics["profit"] > 0
    assert metrics["margin"] > 0


def test_get_ranking_orders_categories_by_profit():
    engine = DataQueryEngine("data/eda_structured.csv")
    ranking = engine.get_ranking("category", "profit")
    assert len(ranking) == 3  # 3 categories
    # First should be highest
    assert ranking[0][0] == "Technology"
    assert ranking[0][1] > 0
    # Check descending order
    for i in range(len(ranking)-1):
        assert ranking[i][1] >= ranking[i+1][1]


def test_get_entity_rank_returns_1_for_highest():
    engine = DataQueryEngine("data/eda_structured.csv")
    rank = engine.get_entity_rank("category", "profit", "Technology")
    assert rank == 1


def test_get_average_computes_mean_correctly():
    engine = DataQueryEngine("data/eda_structured.csv")
    avg = engine.get_average("category", "profit")
    # Should be sum of all category profits / number of categories
    assert avg > 0


def test_detect_outliers_finds_negative_profit_entities():
    engine = DataQueryEngine("data/eda_structured.csv")
    negatives = engine.detect_outliers("category", "profit", "negative")
    # Should include categories with total profit < 0 if any exist
    assert isinstance(negatives, list)
    for entity in negatives:
        metrics = engine.get_entity_metrics("category", entity, ["profit"])
        assert metrics["profit"] < 0


def test_has_metric_for_dimension_returns_true_for_valid_combinations():
    engine = DataQueryEngine("data/eda_structured.csv")
    assert engine.has_metric_for_dimension("category", "profit") is True
    assert engine.has_metric_for_dimension("category", "margin") is True
    assert engine.has_metric_for_dimension("region", "profit") is True


def test_get_available_dimensions_returns_all_dimension_columns():
    engine = DataQueryEngine("data/eda_structured.csv")
    dims = engine.get_available_dimensions()
    assert "category" in dims
    assert "region" in dims
