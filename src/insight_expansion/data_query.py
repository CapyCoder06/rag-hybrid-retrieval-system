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
