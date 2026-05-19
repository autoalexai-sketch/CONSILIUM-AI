"""
core/structured_handoff.py -- Structured JSON handoff between directors.

Scout returns a universal JSON context block that all subsequent directors
receive as structured input instead of raw markdown text.

JSON schema is domain-agnostic: works for finance, tech, business, strategy,
personal decisions, or any other query type.
"""

import json
import re
from typing import Any, Dict, Optional


# ── Universal JSON schema ─────────────────────────────────────────────────────
SCOUT_JSON_SCHEMA = """
{
  "query_understood": "restate what was asked in 1 sentence",
  "domain": "finance|real_estate|tech|business|strategy|health|legal|personal|other",
  "geo": {
    "country": "detected country (e.g. Poland)",
    "city": "detected city or null",
    "currency": "PLN / EUR / USD / UAH / etc"
  },
  "key_facts": [
    {
      "fact": "specific verifiable statement",
      "value": "concrete number, name, or data point (not null if known)",
      "confidence": "HIGH | MEDIUM | LOW | DISPUTED",
      "source": "source description",
      "freshness": "2025-2026 or date"
    }
  ],
  "numbers": {
    "note": "fill only what is relevant to the query, leave null if unknown",
    "average_income": null,
    "target_amount": null,
    "timeline_months": null,
    "price_range_min": null,
    "price_range_max": null,
    "rate_or_percent": null,
    "custom_1_label": null,
    "custom_1_value": null,
    "custom_2_label": null,
    "custom_2_value": null
  },
  "programs_or_options": [
    {
      "name": "program/option name",
      "description": "what it is in 1 sentence",
      "eligibility": "who qualifies",
      "benefit": "concrete benefit (amount, percent, condition)",
      "active": true
    }
  ],
  "key_constraints": [
    "constraint 1 (e.g. requires 2 years of work history)",
    "constraint 2"
  ],
  "missing_data": [
    {
      "parameter": "what is missing",
      "impact": "HIGH | MEDIUM | LOW",
      "why_needed": "how it changes the answer"
    }
  ],
  "information_gaps": [
    "gap 1 — why critical",
    "gap 2"
  ],
  "conflicts": [
    {
      "topic": "what is disputed",
      "version_a": "one version",
      "version_b": "another version"
    }
  ],
  "context_summary": "2-3 sentence summary of all key facts for next directors"
}
"""

SCOUT_JSON_PROMPT_SUFFIX = f"""

## CRITICAL OUTPUT REQUIREMENT

You MUST return a JSON block at the END of your response, after your regular analysis.
Wrap it in triple backticks with json tag:

```json
{SCOUT_JSON_SCHEMA}
```

Rules:
- Fill every field you have data for
- Use null for unknown numeric fields, empty [] for unknown lists
- "numbers" block: use whatever fields fit the query, ignore irrelevant ones
- "key_facts": minimum 3, maximum 10 most important facts
- "programs_or_options": list ALL relevant programs/tools/approaches found
- "missing_data": be honest — list what you don't know
- NEVER fabricate numbers — use null if unknown
"""


def extract_scout_json(scout_response: str) -> Optional[Dict[str, Any]]:
    """
    Extract structured JSON from Scout's response.
    Returns parsed dict or None if not found/invalid.
    """
    if not scout_response:
        return None

    # Try to find ```json ... ``` block
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', scout_response)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback: find raw { ... } block (last occurrence, likely the structured one)
    brace_matches = list(re.finditer(r'\{[\s\S]{200,}\}', scout_response))
    if brace_matches:
        try:
            return json.loads(brace_matches[-1].group(0))
        except json.JSONDecodeError:
            pass

    return None


def format_handoff_for_director(
    scout_json: Optional[Dict[str, Any]],
    director_role: str
) -> str:
    """
    Format Scout's JSON into a structured context block for a specific director.
    Each director gets the same data but with role-specific framing.
    """
    if not scout_json:
        return "[No structured data from Scout — working from raw text only]"

    geo = scout_json.get("geo", {})
    numbers = scout_json.get("numbers", {})
    facts = scout_json.get("key_facts", [])
    programs = scout_json.get("programs_or_options", [])
    constraints = scout_json.get("key_constraints", [])
    missing = scout_json.get("missing_data", [])
    gaps = scout_json.get("information_gaps", [])
    summary = scout_json.get("context_summary", "")

    lines = ["## 📦 STRUCTURED CONTEXT FROM SCOUT"]

    # Geo context
    if geo:
        country = geo.get("country", "unknown")
        city = geo.get("city") or "not specified"
        currency = geo.get("currency", "")
        lines.append(f"\n**Geography:** {country}, {city} | Currency: {currency}")

    # Summary
    if summary:
        lines.append(f"\n**Summary:** {summary}")

    # Key numbers (only non-null)
    num_items = {k: v for k, v in numbers.items()
                 if v is not None and k != "note"}
    if num_items:
        lines.append("\n**Key Numbers:**")
        for k, v in num_items.items():
            label = k.replace("_", " ").title()
            lines.append(f"  • {label}: {v}")

    # Key facts (top 5)
    if facts:
        lines.append("\n**Verified Facts:**")
        for f in facts[:5]:
            conf = f.get("confidence", "?")
            fact_text = f.get("fact", "")
            value = f.get("value")
            val_str = f" → **{value}**" if value else ""
            lines.append(f"  • [{conf}] {fact_text}{val_str}")

    # Programs / options
    if programs:
        lines.append("\n**Available Programs/Options:**")
        for p in programs:
            name = p.get("name", "")
            benefit = p.get("benefit", "")
            active = "✅" if p.get("active", True) else "❌"
            lines.append(f"  • {active} **{name}**: {benefit}")

    # Constraints
    if constraints:
        lines.append("\n**Key Constraints:**")
        for c in constraints:
            lines.append(f"  • {c}")

    # Missing data — important for all directors
    high_missing = [m for m in missing if m.get("impact") == "HIGH"]
    if high_missing:
        lines.append("\n**⚠️ Missing HIGH-impact data:**")
        for m in high_missing:
            lines.append(f"  • {m.get('parameter')}: {m.get('why_needed')}")

    # Director-specific instructions
    role_instructions = {
        "analyst": "\n**For Analyst:** Use the numbers above as your baseline. Identify which missing data most affects the analysis. Build your structure around the geo context.",
        "architect": "\n**For Architect:** Design solutions using the programs and options listed. Factor in ALL constraints. Build concrete steps around the verified numbers.",
        "devil": "\n**For Devil's Advocate:** Focus your attacks on the HIGH-confidence facts that could be wrong, and the HIGH-impact missing data. What if the numbers are off by 30%?",
        "chairman": "\n**For Chairman:** Your verdict MUST reference specific numbers, programs, and constraints from above. No generic advice — every recommendation must be grounded in the structured data.",
    }
    if director_role in role_instructions:
        lines.append(role_instructions[director_role])

    return "\n".join(lines)


def build_insufficiency_response(
    missing_data: list,
    domain: str,
    geo_context: str,
    language: str
) -> str:
    """
    Build a clarifying questions response when critical data is missing.
    Called by council.py when Scout reports HIGH-impact missing data.
    """
    lang_prefix = {
        "ru": "Для точного ответа мне нужно уточнить несколько вещей:",
        "uk": "Для точної відповіді мені потрібно уточнити кілька речей:",
        "pl": "Żeby dać Ci dokładną odpowiedź, muszę doprecyzować kilka kwestii:",
        "en": "To give you an accurate answer, I need to clarify a few things:",
    }.get(language, "To give you an accurate answer, I need to clarify:")

    lang_suffix = {
        "ru": "После этого я смогу дать точный план с конкретными цифрами.",
        "uk": "Після цього я зможу дати точний план з конкретними цифрами.",
        "pl": "Po uzyskaniu tych informacji podam Ci dokładny plan z konkretnymi liczbami.",
        "en": "After that I can give you a precise plan with specific numbers.",
    }.get(language, "After that I can give you a precise answer.")

    questions = []
    for i, item in enumerate(missing_data, 1):
        param = item.get("parameter", "")
        why = item.get("why_needed", "")
        questions.append(f"{i}. **{param}** — {why}")

    q_text = "\n".join(questions)

    return f"""{lang_prefix}

{q_text}

{lang_suffix}"""
