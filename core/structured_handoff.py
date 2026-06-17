"""
core/structured_handoff.py -- Universal structured JSON handoff between directors.

Scout returns a domain-agnostic JSON block that ALL subsequent directors
receive as structured input. Works for ANY query type:
finance, tech, business, strategy, health, legal, personal, etc.
"""

import json
import re
from typing import Any, Dict, Optional


# ── Universal JSON schema (domain-agnostic) ───────────────────────────────────
SCOUT_JSON_SCHEMA = """{
  "query_understood": "restate what was asked in 1 sentence",
  "task_type": "informational | strategic | technical | creative | analytical",
  "response_mode": "direct_answer | action_plan | analysis | hybrid",
  "domain": "consilium_ai | finance | real_estate | tech | business | strategy | health | legal | personal | education | other",
  "geo": {
    "country": "detected country or null",
    "city": "detected city or null",
    "currency": "detected currency or null"
  },
  "key_facts": [
    {
      "fact": "specific verifiable statement",
      "value": "concrete number, name, or data (null if unknown)",
      "confidence": "HIGH | MEDIUM | LOW | DISPUTED",
      "source": "source description",
      "freshness": "year or date"
    }
  ],
  "key_metrics": [
    {
      "label": "metric name relevant to this specific query",
      "value": "concrete value",
      "unit": "unit of measurement (PLN, %, months, GB, users, etc.)"
    }
  ],
  "options_and_resources": [
    {
      "name": "option / program / tool / framework / approach name",
      "type": "program | tool | framework | strategy | resource | service",
      "description": "what it is in 1 sentence",
      "benefit": "concrete benefit or advantage",
      "condition": "when/how to use it or who qualifies",
      "active": true
    }
  ],
  "key_constraints": [
    "constraint 1 relevant to this query",
    "constraint 2"
  ],
  "missing_data": [
    {
      "parameter": "what specific data is missing",
      "impact": "HIGH | MEDIUM | LOW",
      "why_needed": "how this changes the answer"
    }
  ],
  "information_gaps": [
    "gap 1 — why it matters"
  ],
  "conflicts": [
    {
      "topic": "what is disputed",
      "version_a": "one version",
      "version_b": "another version"
    }
  ],
  "context_summary": "2-3 sentence summary of all key findings for next directors"
}"""


SCOUT_JSON_PROMPT_SUFFIX = f"""

## CRITICAL: STRUCTURED OUTPUT REQUIRED

At the END of your response, output a JSON block with this universal schema.
Wrap it in triple backticks with json tag:

```json
{SCOUT_JSON_SCHEMA}
```

RULES FOR NEW FIELDS:
- `task_type`: classify the query type:
  * "informational" — user asks WHAT something is, HOW it works, WHO/WHAT/WHEN
  * "strategic" — user needs a plan, decision, or recommendation
  * "technical" — code, architecture, system design
  * "creative" — brainstorming, ideation, content
  * "analytical" — data analysis, comparison, evaluation
- `response_mode`: how Chairman should respond:
  * "direct_answer" — for informational queries: give clear answer, NO action plans
  * "action_plan" — for strategic queries: decision + concrete steps
  * "analysis" — for analytical queries: structured analysis
  * "hybrid" — answer + brief recommendation
- `domain`: use "consilium_ai" when query is about Consilium AI product itself

RULES FOR OTHER FIELDS:
- `key_metrics`: use ONLY metrics relevant to THIS specific query.
  Tech query → versions, performance numbers, resource limits.
  Finance query → amounts, rates, timelines.
  Consilium AI query → directors count, phases, features.
  Leave empty [] if no metrics apply.
- `options_and_resources`: list ALL relevant options found.
- `key_facts`: 3-7 most important verifiable facts, minimum.
- `missing_data`: be honest — list what you truly don't know.
  Impact=HIGH means the answer changes significantly without this data.
- `geo`: only fill if geographic context is DIRECTLY relevant to the query.
  Do NOT add geo for product questions, greetings, or general questions.
- NEVER fabricate data — use null for unknown values.
"""


def extract_scout_json(scout_response: str) -> Optional[Dict[str, Any]]:
    """
    Extract structured JSON from Scout's response.
    Returns parsed dict or None if not found / invalid.
    """
    if not scout_response:
        return None

    # Try ```json ... ``` block first
    json_match = re.search(r'```json\s*([\s\S]*?)\s*```', scout_response)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Fallback: last large { ... } block
    brace_matches = list(re.finditer(r'\{[\s\S]{100,}\}', scout_response))
    if brace_matches:
        try:
            return json.loads(brace_matches[-1].group(0))
        except json.JSONDecodeError:
            pass

    return None


def get_response_mode(scout_json: Optional[Dict[str, Any]], query: str) -> str:
    """
    Determine how Chairman should respond based on Scout's classification.
    Falls back to query-based detection if no JSON available.
    """
    if scout_json:
        mode = scout_json.get("response_mode", "")
        if mode in ("direct_answer", "action_plan", "analysis", "hybrid"):
            return mode
        # Derive from task_type
        task_type = scout_json.get("task_type", "")
        if task_type == "informational":
            return "direct_answer"
        if task_type == "strategic":
            return "action_plan"
        if task_type == "analytical":
            return "analysis"

    # Fallback: simple keyword detection
    q = query.lower()
    info_signals = [
        "what is", "what does", "how does", "tell me", "explain",
        "what can", "describe", "who is",
        "что такое", "что умеет", "расскажи", "объясни", "как работает",
        "co to jest", "co potrafi", "jak dziala",
        "що таке", "що вміє",
        "привет", "hello", "hi",
    ]
    if any(s in q for s in info_signals) or len(query.split()) <= 6:
        return "direct_answer"
    return "action_plan"


def format_handoff_for_director(
    scout_json: Optional[Dict[str, Any]],
    director_role: str,
) -> str:
    """
    Format Scout's JSON into a structured context block for a specific director.
    Universal — works for any domain/query type.
    """
    if not scout_json:
        return ""  # No structured data — directors work from raw text

    geo         = scout_json.get("geo") or {}
    metrics     = scout_json.get("key_metrics") or []
    facts       = scout_json.get("key_facts") or []
    options     = scout_json.get("options_and_resources") or []
    constraints = scout_json.get("key_constraints") or []
    missing     = scout_json.get("missing_data") or []
    summary     = scout_json.get("context_summary", "")
    domain      = scout_json.get("domain", "general")
    task_type   = scout_json.get("task_type", "")
    resp_mode   = scout_json.get("response_mode", "")

    lines = ["\n---\n## STRUCTURED DATA FROM SCOUT"]

    # Domain + task classification
    lines.append(f"**Domain:** {domain} | **Task type:** {task_type} | **Response mode:** {resp_mode}")

    # Geo — only if relevant (not for product/general questions)
    country  = geo.get("country")
    city     = geo.get("city")
    currency = geo.get("currency")
    if country or city:
        geo_str = " · ".join(filter(None, [country, city, currency]))
        lines.append(f"**Geography:** {geo_str}")

    # Summary
    if summary:
        lines.append(f"\n**Summary:** {summary}")

    # Key metrics — fully dynamic, domain-specific
    if metrics:
        lines.append("\n**Key Metrics:**")
        for m in metrics:
            label    = m.get("label", "")
            value    = m.get("value", "")
            unit     = m.get("unit", "")
            unit_str = f" {unit}" if unit else ""
            lines.append(f"  * **{label}:** {value}{unit_str}")

    # Key facts (top 5 by confidence)
    if facts:
        high_facts = [f for f in facts if f.get("confidence") == "HIGH"]
        show_facts = high_facts[:5] if high_facts else facts[:4]
        lines.append("\n**Verified Facts:**")
        for f in show_facts:
            conf    = f.get("confidence", "?")
            text    = f.get("fact", "")
            value   = f.get("value")
            val_str = f" -> **{value}**" if value else ""
            lines.append(f"  * [{conf}] {text}{val_str}")

    # Options / resources / programs / tools
    if options:
        lines.append("\n**Available Options & Resources:**")
        for o in options:
            name     = o.get("name", "")
            benefit  = o.get("benefit", "")
            cond     = o.get("condition", "")
            active   = "[OK]" if o.get("active", True) else "[X]"
            cond_str = f" (when: {cond})" if cond else ""
            lines.append(f"  * {active} **{name}**: {benefit}{cond_str}")

    # Constraints
    if constraints:
        lines.append("\n**Key Constraints:**")
        for c in constraints:
            lines.append(f"  * {c}")

    # HIGH-impact missing data
    high_missing = [m for m in missing if m.get("impact") == "HIGH"]
    if high_missing:
        lines.append("\n**[!] Missing HIGH-impact data:**")
        for m in high_missing:
            lines.append(f"  * **{m.get('parameter')}**: {m.get('why_needed')}")

    # Director-specific instruction based on response_mode
    if director_role == "chairman":
        if resp_mode == "direct_answer":
            lines.append(
                "\n**Chairman instruction:** response_mode=DIRECT_ANSWER. "
                "Give a clear, helpful, complete answer. "
                "NO invented action plans. NO PLN/USD budgets unless asked. "
                "NO deadlines unless relevant. Just answer the question directly."
            )
        elif resp_mode == "action_plan":
            lines.append(
                "\n**Chairman instruction:** response_mode=ACTION_PLAN. "
                "Give a concrete decision + 3-5 actionable steps with real numbers. "
                "Each step: WHAT + HOW specifically + WHEN (deadline). "
                "Use metrics and options from above."
            )
        else:
            lines.append(
                "\n**Chairman instruction:** Respond according to the query type. "
                "Cite specific metrics and options from above. "
                "Generic advice is NOT acceptable."
            )
    elif director_role == "analyst":
        lines.append(
            "\n**Analyst instruction:** Build your analysis around the metrics and facts above. "
            "Identify which missing data most changes the picture."
        )
    elif director_role == "architect":
        lines.append(
            "\n**Architect instruction:** Design your solution using the options and resources listed. "
            "No generic steps — reference specific tools, programs, or approaches from above."
        )
    elif director_role == "devil":
        lines.append(
            "\n**Devil's Advocate instruction:** Attack the HIGH-confidence facts first. "
            "Focus on HIGH-impact missing data as your primary attack vector."
        )

    return "\n".join(lines)


def build_insufficiency_response(
    missing_data: list,
    domain: str,
    geo_context: str,
    language: str,
) -> str:
    """
    Build a clarifying questions response when critical data is missing.
    Universal — works for any domain.
    """
    prefixes = {
        "ru": "Чтобы дать точный ответ, мне нужно уточнить несколько вещей:",
        "uk": "Щоб дати точну відповідь, мені потрібно уточнити кілька речей:",
        "pl": "Żeby dać Ci dokładną odpowiedź, muszę doprecyzować kilka kwestii:",
        "en": "To give you an accurate answer, I need to clarify a few things:",
    }
    suffixes = {
        "ru": "После этого я дам точный план — с конкретными цифрами, а не общими словами.",
        "uk": "Після цього дам точний план — з конкретними цифрами, а не загальними словами.",
        "pl": "Wtedy podam Ci dokładny plan z konkretnymi liczbami, a nie ogólne sformułowania.",
        "en": "Then I can give you a precise plan with specific numbers, not generic advice.",
    }

    prefix = prefixes.get(language, prefixes["en"])
    suffix = suffixes.get(language, suffixes["en"])

    questions = "\n".join(
        f"{i}. **{m.get('parameter')}** — {m.get('why_needed')}"
        for i, m in enumerate(missing_data, 1)
    )

    return f"{prefix}\n\n{questions}\n\n{suffix}"
