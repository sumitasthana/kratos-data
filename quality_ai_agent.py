"""
quality_ai_agent.py — Kratos AI Quality Review Agent
=====================================================
Sends a completed quality report to Claude and returns a structured
narrative review that:
  • Distinguishes genuine data errors from config/schema drift
  • Provides a plain-language executive summary
  • Ranks issues by severity and suggests concrete remediation steps
  • Calls out when a "failure" is actually a misconfigured threshold or
    enum mismatch rather than a real data quality problem

Follows the same pattern as stats_engine.py (single async function,
claude-sonnet-4-5, strips markdown fences, returns parsed JSON).
"""

import json
import os
from anthropic import AsyncAnthropic

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are the Kratos Data Quality Review Agent — an expert data engineer and \
FDIC Part 370 / Part 330 compliance analyst.

Your job is to receive a structured data quality report produced by an automated \
metrics engine and produce an intelligent narrative review. The report contains up to \
six dimensions: Completeness, Accuracy, Consistency, Validity, Uniqueness, and Timeliness. \
Each dimension has a status (pass / warn / fail), a measured value, a threshold, and \
optional detail items containing column names and recommendations.

Follow these rules:
1. Distinguish **genuine data errors** (e.g. truly missing values, real duplicates, \
   actual invalid formats) from **false positives caused by config or schema drift** \
   (e.g. enum mismatch where the check value set does not match the live DB schema).
2. For each failed or warned dimension write a concise diagnosis: what is the most \
   likely root cause and is it a data problem or a config/engine problem?
3. Produce an overall verdict: one of "Data is healthy", "Data needs attention", \
   or "Data has critical issues".
4. Prioritise your recommendations — list the single most impactful fix first.
5. Keep your language professional but direct. Do not use filler phrases.

Return ONLY valid JSON with this exact shape — no markdown fences, no extra keys:
{
  "verdict": "<one of: Data is healthy | Data needs attention | Data has critical issues>",
  "executive_summary": "<2-4 sentence plain-language summary>",
  "dimension_reviews": [
    {
      "name": "<dimension name>",
      "status": "<pass|warn|fail>",
      "diagnosis": "<1-2 sentence root-cause analysis — omit for passing dimensions>",
      "is_false_positive": <true|false>,
      "priority": <1-6, 1 = highest>
    }
  ],
  "top_recommendations": [
    "<most impactful actionable recommendation>",
    "<second recommendation>",
    "<third recommendation>"
  ],
  "config_drift_detected": <true|false>,
  "config_drift_explanation": "<explain any detected config/schema drift, or null>"
}
"""

# ---------------------------------------------------------------------------
# Lazy singleton client
# ---------------------------------------------------------------------------

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")
        _client = AsyncAnthropic(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def ai_quality_review(quality_report: dict) -> dict:
    """
    Send *quality_report* (the dict returned by compute_quality) to Claude
    and return a parsed JSON review dict.

    Raises on HTTP or JSON parse errors so the caller can catch and surface
    a meaningful error message.
    """
    client = _get_client()

    # Build a compact but complete representation of the report for the prompt.
    report_text = json.dumps(quality_report, indent=2, default=str)

    user_message = (
        f"Here is the automated quality report to review:\n\n"
        f"```json\n{report_text}\n```\n\n"
        f"Provide your structured review as valid JSON."
    )

    message = await client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if Claude wraps the response anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    return json.loads(raw)
