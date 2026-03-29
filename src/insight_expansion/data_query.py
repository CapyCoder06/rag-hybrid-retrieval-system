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
