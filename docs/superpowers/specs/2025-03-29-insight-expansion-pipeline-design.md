# Insight Expansion Pipeline Design

> **For agentic workers:** This document describes the design and implementation plan for the insight expansion pipeline. Follow the TDD workflow: write failing tests first, then minimal implementation, then refactor.

---

## Goal

Transform a small set (~10) of validated structured insights into a large dataset (~100) of new structured insights by **data-driven pattern expansion**. All generated insights must be:

- **Grounded in real EDA data** (no hallucination)
- **Structured** (same JSON format as seeds)
- **Scalable** (5-10× expansion per seed)
- **Semantically diverse** (different entities, values, comparisons)

---

## Core Principle

> The system does **not** generate knowledge autonomously.
>
> It **decomposes human-validated patterns** and re-applies them across all entities in the dataset, using **real data values** for each entity.

---

## Pipeline Flow

```
Seed Insights (structured JSON)
  ↓
Pattern Extractor
  ↓
Data Query Engine
  ↓
Insight Generator
  ↓
Deduplicator (semantic similarity ≥ 0.85 removes duplicates)
  ↓
Insight Validator (data grounding + format rules)
  ↓
Expanded Insight Set (100+ structured insights)
```

---

## Component Specifications

### 1. Pattern Extractor

**Purpose:** Extract expansion parameters from a seed insight using `type_hint` as the authoritative guide.

**Input:** Seed insight dictionary with keys:
- `text` (required): Original insight text
- `dimensions` (required): List of dimension column names
- `metrics` (required): List of metric column names
- `type_hint` (required): One of {fact, trend, anomaly, metric, question}
- Optional: `issue`, `possible_cause`, `trend`, etc.

**Output:** Pattern object with:
```python
{
    "primary_dimension": str,       # First dimension from dimensions list
    "metrics": List[str],           # All metrics from seed
    "comparison_type": str,         # Based on type_hint: "rank" | "direction" | "outlier" | "definition" | "question"
    "text_format": str,             # Format string template for generating insight text
    "optional_fields": Dict,        # Copy of issue, possible_cause if present
    "qualifier_rules": Dict,        # Rules for computing qualifier dynamically (rank-based, direction-based, etc.)
    "alternate_dimensions": List[str],  # Other dimensions in dataset where metrics exist (for scaling)
    "original_entity": str,         # Entity value extracted from seed text (for optional field copying)
}
```

**Rules by type_hint:**

| type_hint | comparison_type | qualifier_rules | text_format |
|-----------|-----------------|-----------------|-------------|
| fact | "rank" | {"compute_from": "rank", "thresholds": {"top": 1, "bottom": "last", "above_avg": 1.1, "below_avg": 0.9}} | "{entity} {verb} {qualifier} {metric} of {value}" |
| trend | "direction" | {"compute_from": "time_series", "thresholds": {"min_change": 0.05}} | "{entity} {metric} is {direction}, changing from {start} to {end}" |
| anomaly | "outlier" | {"compute_from": "anomaly_detection", "conditions": ["negative", "low_threshold", "outlier"]} | "{entity} shows {issue}: {metric} of {value}" |
| metric | "definition" | {} (no expansion) | "{metric} definition: {text}" (skip expansion, return as-is) |
| question | "question" | {} (generate question variants) | Generate question variations for all entities |

**Alternate Dimensions Discovery:**

To achieve scaling while staying data-grounded, the Pattern Extractor also determines `alternate_dimensions`:

- Call `query_engine.get_available_dimensions()` to get all dimension columns in the dataset (e.g., `["region", "category", "sub_category"]`)
- For each candidate dimension (excluding primary_dimension), check `query_engine.has_metric_for_dimension(dimension, metric)` for ALL metrics in the seed
- Include dimension in `alternate_dimensions` only if **every** metric in the seed is available for that dimension
- This guarantees that data exists for the alternate dimension; no hallucination

Example:
- Seed: `dimensions=["category"]`, `metrics=["profit", "margin"]`
- Alternate dimensions: `["region"]` if dataset contains region-level profit and margin
- Not included: Any dimension lacking one of the required metrics

**Original Entity Extraction:**

To support correct propagation of optional fields (`issue`, `possible_cause`), the Pattern Extractor identifies the `original_entity` value from the seed text:

- Get all unique values for `primary_dimension` via `query_engine.get_unique_values(primary_dimension)`
- Find the first value that appears in the seed's `text` (case-insensitive substring match)
- That value becomes `original_entity`. If none found, leave empty (optional fields will not be copied to any generated insight)

This ensures optional fields are only copied to insights about the same entity that the seed originally described.

**Important:**
- Do NOT re-parse the original text. Use `type_hint` to determine expansion strategy.
- If `type_hint` missing, fall back to simple text analysis (but all seeds should have it).
- For `fact` type, recompute rank/percentile for each entity from actual data.
- Metric split: if seed has multiple metrics, generate separate insights per metric unless they are intrinsically linked (e.g., profit + margin in a single fact).
- The `text_format` template uses Python `.format()` placeholders: `{entity}`, `{metric}`, `{value}`, `{qualifier}`, `{verb}`, `{issue}`, `{direction}`, `{start}`, `{end}`. Placeholders vary by type_hint.

---

### 2. Data Query Engine

**Purpose:** Load the EDA dataset and provide query methods to fetch real values.

**Implementation:**
- Load `data/eda_structured.csv` once (singleton)
- Use Pandas or standard csv module
- Cache aggregated results for performance

**Required Methods:**

```python
class DataQueryEngine:
    def __init__(self, csv_path: str = "data/eda_structured.csv"):
        """Load dataset and precompute aggregations."""

    def get_unique_values(self, dimension: str) -> List[str]:
        """Return sorted list of unique values for a dimension (e.g., all categories)."""

    def get_entity_metrics(self, dimension: str, entity: str, metrics: List[str]) -> Dict[str, float]:
        """For a specific entity value (e.g., category='Technology'), fetch all requested metrics.
        Returns: {'profit': 664000, 'margin': 14.0}"""

    def get_ranking(self, dimension: str, metric: str) -> List[Tuple[str, float]]:
        """Return list of (entity, value) sorted descending by metric value.
        First element = highest."""

    def get_entity_rank(self, dimension: str, metric: str, entity: str) -> int:
        """Return rank position (1 = highest). Ties get same rank."""

    def get_average(self, dimension: str, metric: str) -> float:
        """Return average of metric across all entities (ignoring dimension grouping)."""

    def detect_outliers(self, dimension: str, metric: str, condition: str, threshold: float = None) -> List[str]:
        """Return entities that satisfy anomaly conditions:
        - condition='negative': metric value < 0
        - condition='below_threshold': metric value < threshold (e.g., margin < 3%)
        - condition='outlier': beyond mean ± 2 standard deviations
        Returns list of entity values meeting the condition."""

    def get_available_dimensions(self) -> List[str]:
        """Return list of all dimension columns in the dataset (categorical columns).
        Typically: ['region', 'category', 'sub_category']"""

    def has_metric_for_dimension(self, dimension: str, metric: str) -> bool:
        """Check whether the dataset contains the given metric aggregated at the specified dimension level.
        Used to determine valid alternate dimensions for expansion."""
```

**Notes:**
- Metric names map to CSV columns: `revenue`, `profit`, `margin`
- Dimensions map to CSV columns: `region`, `category`, (sub_category if present)
- Precompute rankings on load to avoid repeated sorting

---

### 3. Insight Generator

**Purpose:** Generate new insights by applying the pattern to all relevant entities.

**Algorithm:**
```python
def generate_insights(seed: Dict, query_engine: DataQueryEngine) -> List[Dict]:
    pattern = PatternExtractor.extract(seed, query_engine)  # Includes alternate_dimensions
    primary_dim = pattern["primary_dimension"]
    alternate_dims = pattern.get("alternate_dimensions", [])

    # Dimensions to iterate: always include primary, then alternates
    dimensions_to_expand = [primary_dim] + alternate_dims

    generated = []
    for current_dim in dimensions_to_expand:
        entities = query_engine.get_unique_values(current_dim)

        for entity in entities:
            # For multi-metric seeds, may split into separate insights
            if len(pattern["metrics"]) > 1 and _should_split_metrics(pattern["metrics"], seed["type_hint"]):
                # Generate separate insight per metric
                for metric in pattern["metrics"]:
                    insight = _generate_single_metric_insight(seed, pattern, entity, metric, current_dim, query_engine)
                    if insight:
                        generated.append(insight)
            else:
                # Generate combined insight with all metrics
                insight = _generate_combined_insight(seed, pattern, entity, current_dim, query_engine)
                if insight:
                    generated.append(insight)

    return generated

def _generate_combined_insight(seed, pattern, entity, current_dim, query_engine):
    """Generate one insight with all metrics."""
    metrics_data = query_engine.get_entity_metrics(current_dim, entity, pattern["metrics"])
    qualifier = compute_qualifier(pattern, entity, metrics_data, query_engine, current_dim)

    # Prepare format parameters
    format_params = {
        "entity": entity,
        "qualifier": qualifier,
        "metric": pattern["metrics"][0] if pattern["metrics"] else "",
        "value": _format_value(metrics_data.get(pattern["metrics"][0], "")),
    }
    # Add additional metrics as needed...

    text = pattern["text_format"].format(**format_params)

    new_insight = {
        "text": text,
        "dimensions": [current_dim],  # Reflect actual dimension used
        "metrics": pattern["metrics"],
        "type_hint": seed["type_hint"],
    }

    # Copy optional fields only if they still apply
    if pattern.get("optional_fields") and _optional_fields_still_valid(pattern["optional_fields"], entity, pattern):
        new_insight.update(pattern["optional_fields"])

    return new_insight

def _generate_single_metric_insight(seed, pattern, entity, metric, current_dim, query_engine):
    """Generate one insight for a single metric (metric splitting case)."""
    metrics_data = query_engine.get_entity_metrics(current_dim, entity, [metric])
    qualifier = compute_qualifier(pattern, entity, metrics_data, query_engine, current_dim)

    format_params = {
        "entity": entity,
        "qualifier": qualifier,
        "metric": metric,
        "value": _format_value(metrics_data.get(metric, "")),
    }

    text = pattern["text_format"].format(**format_params)

    new_insight = {
        "text": text,
        "dimensions": [current_dim],  # Reflect actual dimension used
        "metrics": [metric],
        "type_hint": seed["type_hint"],
    }

    if pattern.get("optional_fields") and _optional_fields_still_valid(pattern["optional_fields"], entity, pattern):
        new_insight.update(pattern["optional_fields"])

    return new_insight

def compute_qualifier(pattern: Dict, entity: str, metrics_data: Dict, query_engine: DataQueryEngine, current_dim: str) -> str:
    """Compute the appropriate qualifier string based on pattern rules and actual data.
    Args:
        pattern: Pattern object from extractor
        entity: The entity value in the current dimension
        metrics_data: Dict of metric values for this entity
        query_engine: DataQueryEngine
        current_dim: The dimension being expanded (primary or alternate)
    """
    comp_type = pattern["comparison_type"]
    metric = pattern["metrics"][0] if pattern["metrics"] else None

    if comp_type == "rank":
        total_entities = len(query_engine.get_unique_values(current_dim))
        rank = query_engine.get_entity_rank(current_dim, metric, entity)
        value = metrics_data.get(metric, 0)
        avg = query_engine.get_average(current_dim, metric)

        if rank == 1:
            return "highest"
        elif rank == total_entities:
            return "lowest"
        elif value > avg * 1.1:
            return "above average"
        elif value < avg * 0.9:
            return "below average"
        else:
            return "around average"  # May be filtered as not meaningful

    elif comp_type == "direction":
        # Requires time-series data; pattern should specify time dimension
        # If time dimension exists (e.g., 'year'), query data for that entity across time points
        # For now (without time data), preserve the seed's original trend indicator if available
        # In full implementation: compute slope or compare first/last values
        return pattern.get("trend", "increasing")  # Default to seed trend

    elif comp_type == "outlier":
        # For anomaly type, check if entity satisfies anomaly condition
        # The generator already filtered entities via detect_outliers, so return anomaly label
        return "negative" if metrics_data.get(metric, 0) < 0 else "outlier"

    else:
        return ""


# --- Helper Functions ---

def _should_split_metrics(metrics: List[str], type_hint: str) -> bool:
    """Determine if metrics should be split into separate insights.
    Returns True for multi-metric facts unless metrics are intrinsically linked.
    For now, split if more than one metric and type_hint is 'fact' or 'anomaly'.
    """
    if len(metrics) <= 1:
        return False
    if type_hint in ["fact", "anomaly"]:
        # Profit and margin are independent; split them
        return True
    # For trend, metric, question: typically single metric already
    return False


def _optional_fields_still_valid(optional_fields: Dict, entity: str, pattern: Dict) -> bool:
    """Check if optional fields (issue, possible_cause) still apply to this generated entity.
    Rule: Copy optional fields only to the original entity that the seed describes.
    To support this, the Pattern object includes `original_entity` (extracted from seed text).
    The generated entity must equal original_entity to receive optional fields.
    Additionally, for anomaly types, could verify that the entity still satisfies the anomaly condition; but that's already enforced by generator filtering.
    """
    return entity == pattern.get("original_entity", "")


def _format_value(value: float) -> str:
    """Format a numeric value for display in insight text.
    Handles currency ($) for profit/revenue and percentages (%) for margin.
    """
    if isinstance(value, (int, float)):
        # Heuristic: if metric is 'margin', format as percentage; else as currency
        # Actually we don't know metric here; caller should pre-format
        # Better: format_value takes metric name as argument
        return f"{value:,.0f}"  # Default
    return str(value)


def _extract_entity_from_text(text: str, dimension: str) -> str:
    """Parse the seed text to find the entity value for the given dimension.
    Example: text="Technology has highest profit", dimension="category" → "Technology"
    Simple heuristic: look for capitalized words or known entity names from dataset.
    """
    # Load dataset entity values for that dimension to match against
    # Implementation in PatternExtractor needs this
    return ""
```

**Qualifier Computation:**

For `fact` type with rank comparison:
```python
rank = query_engine.get_entity_rank(dimension, metric, entity)
if rank == 1:
    qualifier = "highest"
elif rank == total_entities:
    qualifier = "lowest"
else:
    # Check above/below average
    avg = query_engine.get_average(dimension, metric)
    value = metrics_data[metric]
    if value > avg * 1.1:  # 10% above average
        qualifier = "above average"
    elif value < avg * 0.9:
        qualifier = "below average"
    else:
        qualifier = "average"  # May skip these if not meaningful
```

For `trend` type:
- Need time-based dimension (year, quarter)
- Compute direction: increasing if end > start with sufficient delta, else decreasing/stable

For `anomaly` type:
- Use `detect_outliers()` to find all entities with anomaly conditions
- Only entities that satisfy the anomaly condition are generated

**Metric Splitting:**
- If seed has `metrics: ["profit", "margin"]` and both are independent, generate two insights: one for profit, one for margin.
- Each uses its own value from `metrics_data`.
- Counts as 2 insights toward target.
- Split decision logic: `_should_split_metrics(metrics: List[str], type_hint: str) -> bool` returns True for multi-metric facts unless metrics are intrinsically linked by seed pattern.

**Helper Functions (in insight_generator module):**
- `_should_split_metrics(metrics: List[str], type_hint: str) -> bool`: Determines if metrics should be split into separate insights
- `_extract_entity_from_text(text: str, dimension: str) -> str`: Parse seed text to find the original entity value (e.g., "Technology" from "Technology has highest profit")
- `_optional_fields_still_valid(optional_fields: Dict, entity: str, qualifier: str) -> bool`: Check if optional fields (`issue`, `possible_cause`) still apply to this generated entity (typically only for original entity, not for others)

---

### 4. Deduplicator

**Purpose:** Remove exact and near-duplicate insights.

**Implementation:**
```python
def deduplicate(insights: List[Dict], similarity_threshold: float = 0.85) -> List[Dict]:
    """Remove insights with text similarity >= threshold."""
    unique = []
    for insight in insights:
        text = insight["text"].lower().strip()
        is_duplicate = False
        for existing in unique:
            sim = semantic_similarity(text, existing["text"].lower().strip())
            if sim >= similarity_threshold:
                is_duplicate = True
                break
        if not is_duplicate:
            unique.append(insight)
    return unique
```

**Note:** Reuses existing `semantic_similarity()` from `validator.py`.

---

### 5. Insight Validator (New)

**Purpose:** Lightweight validation focused on data grounding and format correctness.

**Validation Rules:**

1. **All numeric values in `text` must exist in the dataset**
   - Extract all numbers (including currency, percentages) from text
   - Verify each number matches a value in the dataset for that entity+metric combination
   - Allow ±5% tolerance for rounded numbers

2. **Dimensions and metrics fields**
   - Both must be non-empty lists
   - All entries must be valid CSV column names: `region`, `category`, `revenue`, `profit`, `margin`
   - (If sub_category exists, include it)

3. **type_hint must be valid**
   - In set: `fact`, `trend`, `anomaly`, `metric`, `question`

4. **Required fields present**
   - `text`, `dimensions`, `metrics`, `type_hint` all required and non-empty

5. **Anomaly optional fields rule**
   - If `issue` is present, `possible_cause` must also be present (and vice versa)

6. **No copying seed text**
   - Similarity between generated insight text and its seed insight text must be < 0.85
   - Prevents verbatim or near-verbatim copying

**Implementation:**
```python
class InsightValidator:
    def validate(self, insight: Dict, seed_text: str = None) -> Dict:
        result = {"valid": True, "issues": []}

        # Rule 1: Required fields
        for field in ["text", "dimensions", "metrics", "type_hint"]:
            if field not in insight or not insight[field]:
                result["valid"] = False
                result["issues"].append(f"Missing required field: {field}")

        # Rule 2: Valid type_hint
        valid_types = {"fact", "trend", "anomaly", "metric", "question"}
        if insight.get("type_hint") not in valid_types:
            result["valid"] = False
            result["issues"].append(f"Invalid type_hint: {insight.get('type_hint')}")

        # Rule 3: Valid dimensions/metrics
        valid_columns = {"region", "category", "revenue", "profit", "margin", "sub_category"}
        if any(d not in valid_columns for d in insight.get("dimensions", [])):
            result["valid"] = False
            result["issues"].append("Invalid dimension name")
        if any(m not in valid_columns for m in insight.get("metrics", [])):
            result["valid"] = False
            result["issues"].append("Invalid metric name")

        # Rule 4: Numbers grounding (requires DataQueryEngine)
        # Extract numbers from text, verify against dataset
        # Implementation: need dimension value from text and metric from metrics list
        # Steps:
        # 1. Extract numeric values from text (regex for $X, X%, X.X)
        # 2. Identify entity value by looking for a value from the dimension in the text
        #    (e.g., if dimensions=["category"], find "Technology" in text)
        # 3. For each extracted number, infer which metric it likely belongs to by context clues
        #    (presence of words like "profit", "margin", "revenue" near the number)
        # 4. Query DataQueryEngine.get_entity_metrics(dimension, entity, [metric]) to get actual value
        # 5. Allow ±5% tolerance: abs(actual - extracted) / actual <= 0.05
        # If exact mapping unclear, skip check (not fail) but log warning.

        # Rule 5: Anomaly fields consistency
        has_issue = "issue" in insight and insight["issue"]
        has_cause = "possible_cause" in insight and insight["possible_cause"]
        if has_issue != has_cause:
            result["valid"] = False
            result["issues"].append("Anomaly must have both issue and possible_cause or neither")

        # Rule 6: Not copying seed
        if seed_text:
            sim = semantic_similarity(insight["text"], seed_text)
            if sim >= 0.85:
                result["valid"] = False
                result["issues"].append(f"Insight too similar to seed (sim={sim:.2f})")

        return result
```

---

## File Structure

```
src/insight_expansion/
  __init__.py
  pattern_extractor.py     # Extract pattern from seed insight
  data_query.py           # DataQueryEngine singleton
  insight_generator.py   # Generate new insights from pattern + data
  deduplicator.py        # Remove duplicates (similarity ≥ 0.85)
  insight_validator.py   # New lightweight validator
  pipeline.py           # Orchestrate: seed → expansion → dedup → validate → output

tests/
  test_pattern_extractor.py
  test_data_query.py
  test_insight_generator.py
  test_deduplicator.py
  test_insight_validator.py
  test_expansion_pipeline.py

scripts/
  expand_insights.py     # CLI entry point

config.yaml (add):
  expansion:
    target_count: 100
    dedup_threshold: 0.85
    validation:
      require_metric_coverage: true
      number_tolerance: 0.05  # 5% tolerance for rounded numbers
```

---

## Integration with Existing Code

This new pipeline **replaces** the document generation stages (Steps 3-9 in SYSTEM_DESIGN.md):

**Before:**
```
Insight → Template Mapping → Document Generation → Enrichment → Chunking
```

**After:**
```
Seed Insights → Insight Expansion → Deduplication → Validation → Expanded Insight Set (JSON)
```

Output `insights_expanded.json` becomes the input to the existing pipeline (if document generation is still needed downstream). Alternatively, this can be a standalone mode.

---

## Testing Strategy (TDD Order)

### 1. Data Query Engine Tests

```python
def test_loads_csv_successfully()
def test_get_unique_values_returns_all_categories()
def test_get_entity_metrics_returns_correct_values_for_technology()
def test_get_ranking_orders_categories_by_profit_correctly()
def test_get_entity_rank_returns_1_for_highest()
def test_get_average_computes_mean_correctly()
```

### 2. Pattern Extractor Tests

```python
def test_extract_fact_pattern_captures_dimension_and_metrics()
def test_extract_trend_pattern_sets_comparison_type_direction()
def test_extract_anomaly_pattern_sets_comparison_type_outlier()
def test_extract_metric_pattern_handles_single_metric()
def test_extract_question_pattern_generates_question_template()
def test_extract_uses_type_hint_not_text_parsing()
```

### 3. Insight Generator Tests

```python
def test_generate_creates_one_insight_per_entity()
def test_generated_insight_text_contains_real_dataset_values()
def test_generated_insight_qualifier_matches_actual_rank()
def test_metric_splitting_generates_separate_insights()
def test_optional_fields_copied_only_when_contextually_valid()
def test_generate_anomaly_only_includes_entities_with_negative_profit()
```

### 4. Deduplicator Tests

```python
def test_deduplicate_removes_exact_duplicates()
def test_deduplicate_removes_near_duplicates_above_threshold()
def test_deduplicate_preserves_distinct_insights()
def test_deduplicate_uses_semantic_similarity()
```

### 5. Insight Validator Tests

```python
def test_validate_accepts_valid_insight()
def test_validate_rejects_missing_required_field()
def test_validate_rejects_invalid_type_hint()
def test_validate_rejects_invalid_dimension_name()
def test_validate_rejects_invalid_metric_name()
def test_validate_rejects_anomaly_with_only_issue()
def test_validate_rejects_insight_too_similar_to_seed()
def test_validate_accepts_insight_with_different_numbers()
```

### 6. Pipeline Integration Tests

```python
def test_pipeline_expands_10_seeds_to_100_insights()
def test_pipeline_all_outputs_passed_validation()
def test_pipeline_removes_duplicates_but_keeps_diversity()
def test_pipeline_no_hallucinated_numbers()
def test_pipeline_runs_in_under_5_seconds()
```

---

## Implementation Order (TDD)

1. **Data Query Engine** (`data_query.py` + tests)
2. **Pattern Extractor** (`pattern_extractor.py` + tests)
3. **Insight Generator** (`insight_generator.py` + tests)
4. **Deduplicator** (`deduplicator.py` + tests) - simple, can test against existing semantic_similarity
5. **Insight Validator** (`insight_validator.py` + tests)
6. **Pipeline Orchestrator** (`pipeline.py` + integration tests)
7. **CLI Script** (`scripts/expand_insights.py`)
8. **Config Updates** (`config.yaml`)

Each step: write failing tests → minimal code → pass tests → refactor → commit.

---

## Edge Cases & Error Handling

- **Empty dataset:** Raise clear error message
- **Missing CSV columns:** Validation error with column list
- **Seed with no expansion potential:** (e.g., metric definition) return as-is, skip expansion
- **All entities filtered out by deduplication:** Return original set (guarantee non-empty)
- **Validation failures:** Collect all issues, report summary; do not fail entire pipeline but mark invalid insights for review

---

## Performance Considerations

- Load CSV once at module import or in singleton DataQueryEngine
- Precompute rankings/averages at init to avoid per-entity repeated calculations
- Deduplication is O(n²) worst-case; with ~100 insights it's fine
- Target output ~100 insights; if overshoot after dedup, truncate to `target_count`

---

## Success Criteria

✅ Output contains ≥100 unique structured insights
✅ All metric values in generated text match dataset values (no fabrication)
✅ All dimensions/metrics are valid column names
✅ No insight is near-duplicate of its seed (similarity < 0.85)
✅ All insights pass InsightValidator checks
✅ Pipeline completes in <5 seconds on dataset of 40 rows
✅ TDD followed: tests written before implementation code

---

## Future Considerations (Out of Scope)

- Parallel expansion for multiple seeds (not needed for 10 seeds)
- Caching dataset queries to disk (over-engineering for 40 rows)
- Advanced qualifier generation (e.g., "second-highest", "top 3")
- Cross-dimensional expansion (e.g., region-category combinations) — violates "expand within seed dimension only"
- Human-in-the-loop review of generated insights (manual outside pipeline)

---

## Related Files

- `data/eda_structured.csv` - Source dataset (40 rows)
- `insights_sample.json` - Seed insights input (~10 items)
- `src/pipeline/validator.py` - Provides `semantic_similarity()` reused by deduplicator
- `config.yaml` - Add `expansion` section

---

**Document Version:** 2025-03-29
**Author:** Claude Code (via superpowers:brainstorming)
**Status:** Draft → Pending User Review
