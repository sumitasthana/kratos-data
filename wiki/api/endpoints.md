# API Endpoints Reference

## Base URL

```
http://localhost:8000
```

## Endpoints

### Health Check

**GET** `/api/health`

Returns backend health status.

**Response:**
```json
{
  "status": "ok"
}
```

---

### Schema Extraction

**POST** `/agents/extract-schema`

Extract table schemas from PostgreSQL database.

**Request Body:**
```json
{
  "connection_string": "postgresql://user:pass@host:5432/dbname",
  "schema": "public",
  "tables": ["table1", "table2"]
}
```

**Response:**
```json
{
  "status": "success",
  "schema_graph": {
    "tables": [...],
    "relationships": [...]
  },
  "output_path": "outputs/schema_graph.json"
}
```

---

### Schema Analysis

**POST** `/analyze-schema`

Analyze schema using LLM to infer field distributions.

**Request Body:**
```json
{
  "schema_graph": {...},
  "sample_rows": {...}
}
```

**Response:**
```json
{
  "status": "success",
  "distribution_spec": {...}
}
```

---

### Pilot Generation

**POST** `/agents/pilot`

Generate synthetic data from schema graph and distribution spec.

**Request Body:**
```json
{
  "schema_graph": {
    "tables": [...],
    "relationships": [...]
  },
  "distribution_spec": {
    "tables": [...]
  },
  "output_dir": "outputs/pilot",
  "row_counts": {
    "table1": 100,
    "table2": 500
  }
}
```

**Response:**
```json
{
  "status": "success",
  "output_dir": "outputs/pilot",
  "files_created": ["table1.csv", "table2.csv"],
  "summary": {
    "tables_generated": 2,
    "total_rows": 600
  }
}
```

**Error Response:**
```json
{
  "status": "error",
  "error": "Error message"
}
```

---

### Quality Evaluation

**POST** `/agents/eval`

Evaluate generated data quality.

**Request Body:**
```json
{
  "csv_dir": "outputs/pilot",
  "distribution_spec_file": "<file_upload>",
  "eval_config_file": "<file_upload>"
}
```

**Content-Type:** `multipart/form-data`

**Fields:**
- `csv_dir` (string): Path to CSV directory
- `distribution_spec_file` (file): distribution_spec.json
- `eval_config_file` (file, optional): eval_config.json

**Response:**
```json
{
  "status": "success",
  "pass_signal": true,
  "report": {
    "run_id": "uuid",
    "status": "pass",
    "stages": {...},
    "summary": {...}
  }
}
```

---

## Error Codes

| Status | Meaning |
|--------|---------|
| 200 | Success |
| 400 | Bad Request - Invalid parameters |
| 422 | Validation Error |
| 500 | Internal Server Error |

## Common Response Fields

All responses include:
```json
{
  "status": "success|error"
}
```

Error responses include:
```json
{
  "status": "error",
  "error": "Detailed error message"
}
```
