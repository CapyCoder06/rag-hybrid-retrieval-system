"""Data query engine for EDA dataset."""

import csv
from typing import List, Dict
from collections import defaultdict


class DataQueryEngine:
    """Loads CSV and provides queries for entity metrics and rankings."""

    def __init__(self, csv_path: str = "data/eda_structured.csv"):
        self.csv_path = csv_path
        self._data = []
        self._load_csv()

    def _load_csv(self):
        """Load CSV and convert numeric fields."""
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                row['revenue'] = float(row['revenue'])
                row['profit'] = float(row['profit'])
                row['margin'] = float(row['margin'])
                self._data.append(row)

    def get_unique_values(self, dimension: str) -> List[str]:
        """Return sorted list of unique values for a dimension."""
        values = set()
        for row in self._data:
            values.add(row[dimension])
        return sorted(values)

    def get_entity_metrics(self, dimension: str, entity: str, metrics: List[str]) -> Dict[str, float]:
        """Fetch metrics for a given entity, aggregating across all other dimension levels."""
        matches = [row for row in self._data if row[dimension] == entity]
        if not matches:
            return {}

        result = {}
        for metric in metrics:
            if metric in ["revenue", "profit"]:
                total = sum(row[metric] for row in matches)
                result[metric] = total
            elif metric == "margin":
                total_revenue = sum(row['revenue'] for row in matches)
                total_profit = sum(row['profit'] for row in matches)
                result['margin'] = (total_profit / total_revenue * 100) if total_revenue > 0 else 0.0
            else:
                # Unknown metric, skip
                pass
        return result

    def get_ranking(self, dimension: str, metric: str) -> List[tuple]:
        """Return list of (entity, value) sorted descending by aggregated metric."""
        entities = self.get_unique_values(dimension)
        ranked = []
        for entity in entities:
            metrics_data = self.get_entity_metrics(dimension, entity, [metric])
            value = metrics_data.get(metric, 0.0)
            ranked.append((entity, value))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def get_entity_rank(self, dimension: str, metric: str, entity: str) -> int:
        """Return rank position (1 = highest). Ties get same rank (dense ranking)."""
        ranking = self.get_ranking(dimension, metric)
        # Find target entity's value
        target_value = None
        for ent, val in ranking:
            if ent == entity:
                target_value = val
                break
        if target_value is None:
            return len(ranking) + 1  # not found
        # Dense ranking: first occurrence of this value gets rank
        for i, (ent, val) in enumerate(ranking):
            if val == target_value:
                return i + 1
        return len(ranking) + 1

    def get_average(self, dimension: str, metric: str) -> float:
        """Compute average of metric across all entities in dimension."""
        entities = self.get_unique_values(dimension)
        total = 0.0
        count = 0
        for entity in entities:
            metrics_data = self.get_entity_metrics(dimension, entity, [metric])
            total += metrics_data.get(metric, 0.0)
            count += 1
        return total / count if count > 0 else 0.0
