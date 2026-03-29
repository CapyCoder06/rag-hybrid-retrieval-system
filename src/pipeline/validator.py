"""
Document validation against quality rules.
"""

import re
from typing import Dict, Any, List, TYPE_CHECKING
from .types import DocumentType

if TYPE_CHECKING:
    from .config import Config
from .config import get_config


def semantic_similarity(text1: str, text2: str) -> float:
    """
    Calculate semantic similarity between two texts using keyword overlap
    with synonym normalization and weighted terms.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score between 0.0 and 1.0
    """
    if not text1 or not text2:
        return 0.0

    # Synonym mapping (canonical form)
    SYNONYM_MAP = {
        # Sales synonyms
        'sales': 'revenue',
        'revenue': 'revenue',
        'turnover': 'revenue',
        # Profit synonyms
        'profit': 'profit',
        'earnings': 'profit',
        'income': 'profit',
        'gains': 'profit',
        # Increase synonyms
        'increase': 'increase',
        'increased': 'increase',
        'grew': 'increase',
        'grow': 'increase',
        'rose': 'increase',
        'rise': 'increase',
        'climbed': 'increase',
        # Decrease synonyms
        'decrease': 'decrease',
        'decreased': 'decrease',
        'fell': 'decrease',
        'drop': 'decrease',
        'decline': 'decrease',
        # Highest synonyms
        'highest': 'highest',
        'top': 'highest',
        'best': 'highest',
        'maximum': 'highest',
        'peak': 'highest',
        # Lowest synonyms
        'lowest': 'lowest',
        'worst': 'lowest',
        'minimum': 'lowest',
        # Margin synonyms
        'margin': 'margin',
        'profitability': 'margin',
        'return': 'margin',
        # Category synonyms
        'category': 'category',
        'segment': 'category',
        'class': 'category',
    }

    # Normalize: lowercase, tokenize, map synonyms
    def normalize_terms(text: str) -> dict:
        text = text.lower()

        # Pre-normalization: combine number + percent/percentage
        text = re.sub(r'(\d+(?:\.\d+)?)\s+(?:percent|percentage)\b', r'\1%', text)

        # Tokenize: split on whitespace/punctuation, but keep numbers with % intact
        tokens = re.findall(r'\b[\w$%.]+\b', text)

        term_weights = {}

        for token in tokens:
            # Map to canonical form
            canonical = SYNONYM_MAP.get(token, token)

            weight = 1.0  # default

            # Numbers get high weight
            if re.match(r'[\d,.]+%?|\$[\d,]+K?', canonical):
                weight = 3.0
            elif canonical in ['profit', 'revenue', 'increase', 'highest', 'margin']:
                weight = 2.0
            elif canonical in ['technology', 'canada', 'furniture', 'category', 'year']:
                weight = 1.5
            elif token in ['the', 'a', 'an', 'and', 'with', 'by', 'of', 'has', 'have', 'is', 'are']:
                weight = 0.1  # stop words

            term_weights[canonical] = term_weights.get(canonical, 0) + weight

        return term_weights

    weights1 = normalize_terms(text1)
    weights2 = normalize_terms(text2)

    # Calculate weighted Jaccard similarity
    intersection_sum = 0.0
    union_sum = 0.0

    # Intersection: sum of weights for shared terms
    common_terms = set(weights1.keys()) & set(weights2.keys())
    for term in common_terms:
        intersection_sum += min(weights1[term], weights2[term])  # Use min to be conservative

    # Union: sum of max weights for each term
    all_terms = set(weights1.keys()) | set(weights2.keys())
    for term in all_terms:
        union_sum += max(weights1.get(term, 0), weights2.get(term, 0))

    if union_sum == 0:
        return 0.0

    similarity = intersection_sum / union_sum
    return round(similarity, 3)


def validate_semantic_drift(original_text: str, generated_text: str, threshold: float = None) -> tuple:
    """
    Validate that generated text preserves original meaning.

    Args:
        original_text: Original insight text
        generated_text: Generated document text
        threshold: Minimum similarity required (default from config: 0.65)

    Returns:
        Tuple: (is_valid, similarity_score)
    """
    # Load threshold from config if not provided
    if threshold is None:
        config = get_config()
        threshold = config.get('validation.semantic_similarity_threshold', 0.65)

    # Remove the document header for comparison (keep content only)
    orig_lines = original_text.split('\n')
    gen_lines = generated_text.split('\n')

    # Extract main content (first non-empty line after any header)
    def get_content(lines):
        for line in lines[1:] if lines else []:
            stripped = line.strip()
            if stripped:
                return stripped
        return lines[0] if lines else ""

    orig_content = get_content(orig_lines)
    gen_content = get_content(gen_lines)

    # Calculate similarity
    similarity = semantic_similarity(orig_content, gen_content)

    # Check if it meets threshold
    is_valid = similarity >= threshold

    return is_valid, similarity


class DocumentValidator:
    """Validates generated documents against quality rules."""

    def __init__(self, config: 'Config' = None):
        """
        Initialize validator.

        Args:
            config: Configuration object (loads from config.yaml if None)
        """
        if config is None:
            config = get_config()

        self.config = config
        self.confidence_config = config.get('validation.confidence', {})

    def validate(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a document and update confidence score.

        Args:
            document: Document with 'text' and 'metadata' keys

        Returns:
            Dictionary with:
                - valid: bool
                - issues: list of validation errors
                - warnings: list of warnings
        """
        result = {
            "valid": True,
            "issues": [],
            "warnings": []
        }

        text = document.get("text", "")
        metadata = document.get("metadata", {})

        # Check text exists
        if not text or len(text.strip()) == 0:
            result["valid"] = False
            result["issues"].append("Document text is empty")

        # Check metadata exists
        if not metadata:
            result["valid"] = False
            result["issues"].append("Document metadata is missing")

        # Check type
        doc_type = metadata.get("type")
        if not doc_type:
            result["valid"] = False
            result["issues"].append("Document type is missing in metadata")
        elif doc_type not in [t.value for t in DocumentType]:
            result["valid"] = False
            result["issues"].append(f"Invalid document type: {doc_type}")

        # Check minimum length
        if len(text.split()) < 10:
            result["warnings"].append("Document is very short (<10 words)")

        # Check retrieval terms (dimensions, metrics present)
        dimensions = metadata.get("dimensions", [])
        metrics = metadata.get("metrics", [])

        if not dimensions and not metrics:
            result["warnings"].append("No dimensions or metrics in metadata (affects retrieval)")

        # Validate that all metric concepts referenced in text are covered by metrics list
        self._validate_metric_coverage(text, metrics, result)

        # Check template formatting
        if doc_type:
            expected_prefix = f"[{doc_type.upper()}]"
            if expected_prefix not in text:
                result["issues"].append(f"Document missing expected prefix: {expected_prefix}")
                result["valid"] = False

        # Check for hallucination markers
        hallucination_indicators = [
            "as an AI", "I don't have", "I cannot", "I don't know"
        ]
        for indicator in hallucination_indicators:
            if indicator.lower() in text.lower():
                result["issues"].append(f"Potential hallucination marker: '{indicator}'")
                result["valid"] = False

        # Update confidence score in document metadata based on validation
        self._update_confidence(document, result)

        return result

    def _extract_insight_description(self, text: str) -> str:
        """
        Extract the original insight description from a rendered document.

        The document structure is:
        # [TYPE] Title
        <blank line>
        Description (original insight text)
        <blank line>
        - Dimensions: ...
        - Metrics: ...
        ...

        Args:
            text: Full document text

        Returns:
            The insight description text, or empty string if not found
        """
        if not text:
            return ""

        lines = text.split('\n')

        # Skip the header line (starts with #)
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                start_idx = i
                break

        # Find the first non-empty line after the header
        content_start = None
        for i in range(start_idx + 1, len(lines)):
            if lines[i].strip():
                content_start = i
                break

        if content_start is None:
            return ""

        # The description continues until we hit a line that starts with '-'
        # or another section header or blank line followed by such
        description_lines = []
        for i in range(content_start, len(lines)):
            line = lines[i].strip()
            # Stop at template labels
            if line.startswith('-'):
                break
            # Also stop if we encounter a blank line followed by a label on next line
            if not line and i + 1 < len(lines) and lines[i + 1].strip().startswith('-'):
                break
            if line.startswith('#'):
                break
            description_lines.append(line)

        return ' '.join(description_lines).strip()

    def _validate_metric_coverage(self, text: str, metrics: List[str], result: Dict[str, Any]):
        """
        Validate that all metric concepts referenced in the insight text are present in the metrics list.

        This ensures the insight is properly indexed for retrieval and the metadata
        accurately reflects the metrics discussed in the text.

        Args:
            text: The document text (contains original insight description plus template labels)
            metrics: List of metric names from metadata
            result: Validation result dict to append warnings/issues to
        """
        insight_text = self._extract_insight_description(text)
        if not insight_text:
            return

        # Mapping: canonical metric name -> common textual variants (synonyms)
        METRIC_KEYWORDS = {
            'profit': ['profit', 'earnings', 'income', 'gain', 'gains', 'net income', 'net profit', 'loss', 'losses', 'bottom line'],
            'sales': ['sales', 'revenue', 'turnover', 'business income'],
            'margin': ['margin', 'profitability', 'return', 'returns', 'net margin', 'gross margin'],
            'cagr': ['cagr', 'compound annual growth rate', 'growth rate', 'annual growth'],
        }

        # Build reverse dictionary: variant (lowercase) -> canonical
        variant_to_canonical = {}
        for canonical, variants in METRIC_KEYWORDS.items():
            for v in variants:
                variant_to_canonical[v.lower()] = canonical

        normalized_metrics = set(m.lower().strip() for m in metrics)
        text_lower = insight_text.lower()

        missing = set()
        for variant, canonical in variant_to_canonical.items():
            if ' ' in variant:
                present = variant in text_lower
            else:
                present = re.search(r'\b' + re.escape(variant) + r'\b', text_lower) is not None

            if present and canonical not in normalized_metrics and variant not in normalized_metrics:
                missing.add(canonical)

        if missing:
            result["warnings"].append(
                f"Metrics referenced in text but missing from metadata: {', '.join(sorted(missing))}."
            )

    def _update_confidence(self, document: Dict[str, Any], validation: Dict[str, Any]):
        """
        Update document's confidence score based on validation results.

        Args:
            document: The document being validated (modified in-place)
            validation: Validation result dictionary
        """
        metadata = document.get("metadata", {})

        # Get current confidence or default to 0.5
        current_confidence = metadata.get("confidence", 0.5)

        # Get config values with defaults
        valid_boost = self.confidence_config.get('valid_boost', 0.2)
        invalid_penalty = self.confidence_config.get('invalid_penalty', 0.3)
        issue_penalty = self.confidence_config.get('issue_penalty', 0.1)
        warning_penalty = self.confidence_config.get('warning_penalty', 0.05)

        # Adjust based on validation
        if validation["valid"]:
            # Valid document gets confidence boost
            new_confidence = min(1.0, current_confidence + valid_boost)
        else:
            # Invalid document gets confidence penalty
            new_confidence = max(0.0, current_confidence - invalid_penalty)

        # Additional adjustments based on issues/warnings
        issue_count = len(validation["issues"])
        warning_count = len(validation["warnings"])

        if issue_count > 0:
            new_confidence -= issue_penalty * issue_count
        if warning_count > 0:
            new_confidence -= warning_penalty * warning_count

        # Clamp to 0-1 range
        new_confidence = max(0.0, min(1.0, new_confidence))

        # Update document metadata in-place
        if "metadata" in document:
            document["metadata"]["confidence"] = round(new_confidence, 2)

    def validate_batch(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate a batch of documents.

        Args:
            documents: List of document dictionaries

        Returns:
            Validation summary
        """
        results = {
            "total": len(documents),
            "valid": 0,
            "invalid": 0,
            "documents": []
        }

        for doc in documents:
            validation = self.validate(doc)
            if validation["valid"]:
                results["valid"] += 1
            else:
                results["invalid"] += 1
            results["documents"].append(validation)

        return results
