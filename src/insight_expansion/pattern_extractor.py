"""Pattern extractor for insight expansion."""

from typing import Dict, List


class PatternExtractor:
    """Extracts expansion patterns from seed insights using type_hint as authoritative."""

    @staticmethod
    def extract(seed: Dict, query_engine) -> Dict:
        """Extract pattern from seed insight."""
        dimensions = seed.get("dimensions", [])
        primary_dimension = dimensions[0] if dimensions else ""

        type_hint = seed.get("type_hint", "")
        text = seed.get("text", "")

        # Define text_format based on type_hint
        if type_hint == "fact":
            text_format = "{entity} {verb} {qualifier} {metric} of {value}"
        elif type_hint == "trend":
            text_format = "{entity} {metric} is {direction}, changing from {start} to {end}"
        elif type_hint == "anomaly":
            text_format = "{entity} shows {issue}: {metric} of {value}"
        elif type_hint == "metric":
            text_format = "{metric} definition: {text}"
        elif type_hint == "question":
            text_format = "Q: {question} about {entity}? A: {answer}"
        else:
            text_format = "{text}"

        pattern = {
            "primary_dimension": primary_dimension,
            "metrics": seed.get("metrics", []),
            "comparison_type": PatternExtractor._get_comparison_type(type_hint),
            "text_format": text_format,
            "optional_fields": {k: v for k, v in seed.items() if k in ["issue", "possible_cause"]},
            "qualifier_rules": PatternExtractor._get_qualifier_rules(type_hint),
            "alternate_dimensions": [],
            "original_entity": ""
        }

        # Compute alternate dimensions if query_engine provided
        if query_engine:
            pattern["alternate_dimensions"] = PatternExtractor._discover_alternate_dimensions(seed, query_engine)
            if primary_dimension:
                pattern["original_entity"] = PatternExtractor._extract_original_entity(text, primary_dimension, query_engine)

        return pattern

    @staticmethod
    def _get_comparison_type(type_hint: str) -> str:
        mapping = {
            "fact": "rank",
            "trend": "direction",
            "anomaly": "outlier",
            "metric": "definition",
            "question": "question"
        }
        return mapping.get(type_hint, "")

    @staticmethod
    def _get_qualifier_rules(type_hint: str) -> Dict:
        if type_hint == "fact":
            return {"compute_from": "rank", "thresholds": {"top": 1, "bottom": "last", "above_avg": 1.1, "below_avg": 0.9}}
        elif type_hint == "trend":
            return {"compute_from": "time_series", "thresholds": {"min_change": 0.05}}
        elif type_hint == "anomaly":
            return {"compute_from": "anomaly_detection", "conditions": ["negative", "low_threshold", "outlier"]}
        elif type_hint == "metric":
            return {}
        elif type_hint == "question":
            return {}
        return {}

    @staticmethod
    def _discover_alternate_dimensions(seed: Dict, query_engine) -> List[str]:
        primary = seed.get("dimensions", [])[0] if seed.get("dimensions") else ""
        all_dims = query_engine.get_available_dimensions()
        metrics = seed.get("metrics", [])
        alternates = []
        for dim in all_dims:
            if dim == primary:
                continue
            all_exist = all(query_engine.has_metric_for_dimension(dim, m) for m in metrics)
            if all_exist:
                alternates.append(dim)
        return alternates

    @staticmethod
    def _extract_original_entity(text: str, dimension: str, query_engine) -> str:
        entities = query_engine.get_unique_values(dimension)
        text_lower = text.lower()
        for ent in entities:
            if ent.lower() in text_lower:
                return ent
        return ""
