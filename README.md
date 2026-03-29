# RAG Document Pipeline: Insights → Retrieval-Optimized Documents
# 🚀 Hybrid Retrieval System

A semi-automated RAG pipeline that transforms structured insights into a retrieval-optimized document corpus.

## 🔥 Key Highlights

- **Hybrid retrieval** (text + metadata + synonym expansion)
- **Query-aware enrichment** to improve recall
- **Evaluation-driven optimization** (precision vs recall tuning)
- **Metadata-aware ranking** with soft boosting

## 📊 Results

- Precision@1: +22%
- Recall@3: +6.6%
- MRR: +14%

> Achieved balanced retrieval performance through hybrid scoring and iterative tuning.

## 🧠 Core Idea

Traditional semantic search fails due to vocabulary mismatch.

This system solves it by combining:
- Semantic similarity (what it says)
- Metadata query matching (what it means)
- Synonym expansion (how it's phrased)

→ Result: Better ranking at top positions without sacrificing recall

## Overview

This project implements an **automated pipeline** that transforms structured insights into retrieval-optimized documents for Retrieval-Augmented Generation (RAG) systems.

**Pipeline Flow:**
```
Insight (structured JSON)
    ↓
Template Mapping (FACT, TREND, ANOMALY, METRIC, QUESTION)
    ↓
Document Generation (standardized templates)
    ↓
[Optional] Enrichment (query-aware variations)
    ↓
Retrieval Optimization (metadata with queries & synonyms)
    ↓
Validation (semantic drift prevention)
    ↓
Chunking (semantic-aware splitting)
    ↓
Documents & Chunks (ready for embedding → vector DB → RAG)
```

**Goal:** Convert a small set of expert-validated insights into a scalable, high-quality document corpus that maximizes retrieval accuracy.

---

## Hybrid Retrieval Optimization

The system implements a sophisticated hybrid retrieval strategy that combines multiple scoring dimensions to improve document ranking accuracy. This approach addresses the vocabulary mismatch problem inherent in semantic search.

### How It Works

Hybrid retrieval computes a weighted score from three components:

1. **Text Similarity** (weight: 0.5)
   - Direct semantic similarity between query and document text
   - Provides foundation for content matching

2. **Metadata Query Matching** (weight: 0.4)
   - Matches query against metadata.queries (natural language questions generated for each document)
   - Captures intent alignment even when wording differs
   - Includes optional similarity bonus: when metadata similarity exceeds threshold (0.6), apply boost factor (1.1x)

3. **Synonym Expansion** (weight: 0.1)
   - Expands query terms using synonyms from metadata.synonyms
   - Improves recall for alternative phrasings

The final score is normalized to [0, 1] to ensure fair comparison across documents.

### Configuration

The retrieval configuration is defined in `config.yaml` under `retrieval_versions.retrieval_v1_stable`:

```yaml
retrieval_versions:
  retrieval_v1_stable:
    weights:
      text: 0.5
      metadata_query: 0.4
      expanded: 0.1
    metadata_bonus:
      enabled: true
      threshold: 0.6
      boost_factor: 1.1
```

### Evaluation Results

A comprehensive evaluation using 70 test queries compared baseline (text-only) vs optimized (hybrid) retrieval:

**Precision Improvements (Top-k results):**
- Precision@3: +52.2% (0.247 → 0.376)
- Precision@5: +65.6% (0.183 → 0.303)
- Precision@10: +101.0% (0.100 → 0.201)

**Trade-off:**
- Recall decreases slightly (documents become more selective in top positions)
- This trade-off is desirable: higher precision means users see more relevant results first

**Key Insight:**
The hybrid approach successfully surfaces more relevant documents in the top result positions, making it suitable for applications where the first few results matter most (e.g., question answering, chatbots).

### Metadata-Aware Evaluator

The `MetadataAwareRetrievalEvaluator` class implements the hybrid scoring during evaluation. It:
- Builds a global synonym map from all document metadata
- Expands queries with synonyms
- Matches query against document metadata.queries
- Applies the weighted hybrid scoring with normalization

This allows accurate simulation of production retrieval behavior before embedding.

## Data Format

### Input Insight Structure

```json
{
  "text": "Technology has the highest profit",
  "dimensions": ["category"],
  "metrics": ["profit"],
  "type_hint": "fact",      // optional
  "grain": "grouped by category",  // optional, auto-inferred
  "trend": "increasing",    // for TREND type
  "issue": "...",            // for ANOMALY type
  "possible_cause": "...",   // for ANOMALY type
  "definition": "...",       // for METRIC type
  "formula": "...",          // for METRIC type
  "interpretation": "...",   // for METRIC type
  "question": "...",         // for QUESTION type
  "answer": "..."            // for QUESTION type
}
```

### Output Document Structure

```json
{
  "text": "# [FACT] ...\n\n...\n- Dimensions: ...\n- Metrics: ...",
  "metadata": {
    "type": "fact",
    "dimensions": ["category"],
    "metrics": ["profit"],
    "title": "...",
    "grain": "grouped by category"
  }
}
```

### Output Chunk Structure

```json
{
  "text": "chunk content...",
  "metadata": {
    "type": "fact",
    "dimensions": ["category"],
    "metrics": ["profit"],
    "_doc_id": 0,
    "chunk_index": 0,
    "chunk_count": 2
  }
}
```

## Project Structure

```
.
├── src/pipeline/          # Core pipeline modules
│   ├── __init__.py        # DocumentPipeline orchestrator
│   ├── types.py           # DocumentType enum
│   ├── templates.py       # Document templates (FACT, TREND, etc.)
│   ├── template_mapper.py # Insight → type classification
│   ├── document_generator.py # Template rendering + retrieval metadata
│   ├── enrichment.py      # Variation generation & filtering
│   ├── validator.py       # Quality & semantic drift checks
│   ├── chunker.py         # Semantic-aware document splitting
│   ├── config.py          # Configuration loader
│   ├── evaluator.py       # Pre-embedding retrieval evaluation
│   └── metadata_retrieval.py # Hybrid scoring (QueryExpander, HybridScorer)
│
├── tests/                 # Comprehensive test suite (154 passing)
│   ├── test_pipeline.py
│   ├── test_enrichment.py
│   ├── test_metadata_retrieval.py
│   ├── test_metadata_aware_evaluator.py
│   ├── test_semantic_chunking.py
│   ├── test_semantic_drift.py
│   └── ... (15 test files)
│
├── evaluation/            # Evaluation scripts and test queries
│   ├── README.md
│   ├── comparison_evaluator.py
│   ├── full_comparison_evaluator.py
│   └── test_queries.json   # 70 queries with relevance labels
│
├── experiments/           # Experiment snapshots
│   └── retrieval_v1_results.json  # Final metrics & config
│
├── docs/                  # Design docs and planning notes
│   └── superpowers/
│       ├── plans/
│       └── specs/
│
├── eda/                   # (Note) Exploratory data analysis - source of structured insights
│   └── hypothesis_eda.ipynb
│
├── output/                # Generated outputs (demo, evaluation)
│   ├── demo_output.json   # Clean demo showing pipeline output
│   └── full_comparison_results.json
│
├── config.yaml            # Pipeline configuration (retrieval_v1_stable)
├── demo_pipeline.py       # End-to-end demo script
├── evaluation_demo.py     # Evaluation demo
├── insights_sample.json   # Sample insights for testing
├── requirements.txt
└── SYSTEM_DESIGN.md       # System design document (formerly CLAUDE.md)
```

---

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Run Demo

```bash
python demo_pipeline.py
```

This loads sample insights, generates documents, validates them, chunks them, and saves to `output/documents.json` and `output/chunks.json`.

### Use the Pipeline

```python
from pipeline import DocumentPipeline

# Load your structured insights (JSON format)
insights = [
    {
        "text": "Technology has the highest profit",
        "dimensions": ["category"],
        "metrics": ["profit"],
        "type_hint": "fact"
    },
    # ... more insights
]

# Configure pipeline
pipeline = DocumentPipeline(
    enrich=True,              # Enable enrichment (variations)
    enrich_variations=2,      # Keep top 2 variations per document
    optimize_retrieval=True,  # Add query/synonym metadata
    chunk_size=200,
    chunk_overlap=50
)

# Run full pipeline
result = pipeline.run(insights, validate=True, chunk=True)

# Access results
documents = result["documents"]  # Generated documents with metadata
chunks = result["chunks"]        # Chunked documents ready for embedding
```

---

## Document Types

| Type | Purpose | Template |
|------|---------|----------|
| **FACT** | Static facts, rankings, comparisons | `[FACT] Title` + dimensions, metrics, grain |
| **TREND** | Time-series patterns, growth/decline | `[TREND] Title` + dimension, metrics, trend, grain |
| **ANOMALY** | Outliers, negative metrics, problems | `[ANOMALY] Title` + dimension, metric, issue, cause |
| **METRIC** | Definitions and calculations | `[METRIC] name` + definition, formula, interpretation |
| **QUESTION** | Q&A pairs | `[QUESTION] Q: ... A: ...` |

Document types are auto-detected via keyword analysis, or explicitly set via `type_hint`.

---

## Retrieval Optimization

Each document can include metadata fields that enhance retrieval:

- `queries`: Natural language questions users might ask (auto-generated)
- `synonyms`: Key term alternatives (e.g., profit → earnings, income)

Example document metadata:
```json
{
  "type": "fact",
  "dimensions": ["category"],
  "metrics": ["profit"],
  "queries": [
    "Which category has the highest profit?",
    "What is the top performer by margin?"
  ],
  "synonyms": {
    "profit": ["earnings", "income"],
    "highest": ["maximum", "peak"]
  }
}
```

The `MetadataAwareRetrievalEvaluator` uses these fields during retrieval scoring to improve result relevance.

---

## Configuration

All pipeline parameters are defined in `config.yaml`:

```yaml
# Retrieval configuration (stable version)
retrieval_versions:
  retrieval_v1_stable:
    weights:
      text: 0.5
      metadata_query: 0.4
      expanded: 0.1
    metadata_bonus:
      enabled: true
      threshold: 0.6
      boost_factor: 1.1
```

To use a specific version, uncomment the `retrieval.use_version` setting.

---

## Evaluation

The evaluation framework measures retrieval quality **before embedding** using semantic similarity:

```bash
python evaluation_demo.py          # Simple evaluation
python evaluation/full_comparison_evaluator.py  # Full baseline vs enriched vs optimized
```

Metrics computed:
- **Recall@k**: Fraction of relevant documents found in top-k
- **Precision@k**: Accuracy of top-k results
- **MRR**: Mean Reciprocal Rank (first relevant doc position)

See `experiments/retrieval_v1_results.json` for final evaluation results.

---

## Design Principles

- **Insight preservation** – Documents strictly follow input insight; no hallucination
- **Retrieval-first** – Metadata and structure optimized for semantic search
- **Quality assurance** – Semantic drift validation ensures meaning retention
- **Configurability** – All weights, thresholds, and counts adjustable via config.yaml
- **Deterministic** – Same insight → same document (except enrichment randomness)

---

## Integration with RAG Pipeline

This pipeline produces the document corpus. Next steps (handled by integration code):

1. **Embedding** – Convert document text to vectors (e.g., using sentence-transformers)
2. **Upsert** – Store vectors + metadata in Pinecone (or other vector DB)
3. **Retrieval** – Use `MetadataAwareRetrievalEvaluator` logic in production to score and rank documents

---

## Constraints

- No autonomous knowledge generation – all content derived from input insights
- Faithful rendering – templates preserve original meaning and numeric values
- Validation rejects documents below semantic similarity threshold (0.65)
- Enrichment limited to 2 high-quality variations per document to maintain precision

---

## Testing

```bash
pytest tests/ -v
```

All **154 tests** should pass, covering:
- Document generation and validation
- Enrichment quality and constraints
- Metadata ranking and retrieval optimization
- Semantic chunking and drift prevention
- Configuration and integration

---

## EDA: Source of Insights

The `eda/hypothesis_eda.ipynb` notebook performs exploratory data analysis on the Superstore dataset to **generate structured insights**. These insights serve as the input to this pipeline.

This Jupyter notebook is the **manual/hypothesis-driven EDA** step that produces the JSON-formatted insights this pipeline consumes.

---

## License

[Specify license if applicable]
