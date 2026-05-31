"""
tests/eval_cases.py -- Manual eval test cases for Consilium AI v3.0
Run: pytest tests/eval_cases.py -v
"""

import pytest

# Each case: query, expected_language, expected_geo, must_contain, must_not_contain

EVAL_CASES = [
    # FINANCE / REAL ESTATE
    {
        "id": "fin-01",
        "query": "как собрать деньги на квартиру в Кракове за год, доход 12000 зл, аренда 3500 зл",
        "expected_language": "ru",
        "expected_geo": "Poland",
        "must_contain": ["zl", "Krakow", "2026"],
        "must_not_contain": ["grivn", "Ukraina", "2024", "rekomenduetsya rassmotret"],
        "critic_expected": True,
        "chairman_expected": True,
    },
    {
        "id": "fin-02",
        "query": "ипотека без первого взноса в Польше 700000 зл квартира",
        "expected_language": "ru",
        "expected_geo": "Poland",
        "must_contain": ["PKO", "Pekao", "2026"],
        "must_not_contain": ["2024", "rekomenduetsya"],
        "critic_expected": True,
        "chairman_expected": True,
    },
    {
        "id": "fin-03",
        "query": "jak oszczedzac na mieszkanie w Krakowie dochod 8000 zl",
        "expected_language": "pl",
        "expected_geo": "Poland",
        "must_contain": ["Krakow", "2026"],
        "must_not_contain": ["hrywna", "Ukraina"],
        "critic_expected": True,
        "chairman_expected": True,
    },
    # TECH
    {
        "id": "tech-01",
        "query": "how to migrate FastAPI app from SQLite to PostgreSQL on AWS RDS",
        "expected_language": "en",
        "expected_geo": "Poland",
        "must_contain": ["PostgreSQL", "SQLAlchemy", "DATABASE_URL"],
        "must_not_contain": [],
        "critic_expected": False,
        "chairman_expected": True,
    },
    {
        "id": "tech-02",
        "query": "какой б/у ноутбук купить для работы над ИИ проектом в Польше до 3000 зл",
        "expected_language": "ru",
        "expected_geo": "Poland",
        "must_contain": ["Allegro", "OLX"],
        "must_not_contain": ["dollarov", "Amazon US"],
        "critic_expected": False,
        "chairman_expected": True,
    },
    # BUSINESS
    {
        "id": "biz-01",
        "query": "какое налогообложение в Польше для Sp.z.o.o стартапа",
        "expected_language": "ru",
        "expected_geo": "Poland",
        "must_contain": ["9%", "19%", "CIT", "VAT"],
        "must_not_contain": ["USA", "UK", "rekomenduetsya"],
        "critic_expected": True,
        "chairman_expected": True,
    },
    {
        "id": "biz-02",
        "query": "how to apply for AWS Activate credits for a startup",
        "expected_language": "en",
        "expected_geo": "Poland",
        "must_contain": ["aws.amazon.com", "Founders", "credits"],
        "must_not_contain": [],
        "critic_expected": False,
        "chairman_expected": True,
    },
    # STRATEGY
    {
        "id": "str-01",
        "query": "стоит ли переезжать в Польшу из Украины для работы в ИТ в 2026",
        "expected_language": "ru",
        "expected_geo": "Poland",
        "must_contain": ["2026"],
        "must_not_contain": ["2024", "rekomenduetsya rassmotret"],
        "critic_expected": True,
        "chairman_expected": True,
    },
    # SIMPLE FACTUAL
    {
        "id": "fct-01",
        "query": "какой сейчас год и месяц в Кракове",
        "expected_language": "ru",
        "expected_geo": "Poland",
        "must_contain": ["2026"],
        "must_not_contain": ["2024", "2025"],
        "critic_expected": False,
        "chairman_expected": True,
    },
    {
        "id": "fct-02",
        "query": "what is FastAPI",
        "expected_language": "en",
        "expected_geo": "Poland",
        "must_contain": ["Python", "async", "API"],
        "must_not_contain": [],
        "critic_expected": False,
        "chairman_expected": True,
    },
]


class EvalResult:
    def __init__(self, case_id, passed, score, failures):
        self.case_id = case_id
        self.passed = passed
        self.score = score
        self.failures = failures

    def __repr__(self):
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.case_id} score={self.score:.0%} failures={self.failures}"


def evaluate_response(case: dict, response_text: str,
                      detected_language: str = None,
                      detected_geo: str = None,
                      directors_used: list = None) -> EvalResult:
    """Evaluate a response against expected criteria. Returns EvalResult 0.0-1.0."""
    failures = []
    checks = 0
    passed_checks = 0
    resp_lower = response_text.lower()

    # Language check
    if detected_language and case.get("expected_language"):
        checks += 1
        if detected_language == case["expected_language"]:
            passed_checks += 1
        else:
            failures.append(f"language: got {detected_language}, expected {case['expected_language']}")

    # Geo check
    if detected_geo and case.get("expected_geo"):
        checks += 1
        if case["expected_geo"].lower() in detected_geo.lower():
            passed_checks += 1
        else:
            failures.append(f"geo: got {detected_geo}, expected {case['expected_geo']}")

    # Must contain
    for term in case.get("must_contain", []):
        checks += 1
        if term.lower() in resp_lower:
            passed_checks += 1
        else:
            failures.append(f"missing: '{term}'")

    # Must NOT contain
    for term in case.get("must_not_contain", []):
        checks += 1
        if term.lower() not in resp_lower:
            passed_checks += 1
        else:
            failures.append(f"forbidden: '{term}'")

    # Critic activation check
    if case.get("critic_expected") and directors_used is not None:
        checks += 1
        if "devil" in directors_used or "critic" in directors_used:
            passed_checks += 1
        else:
            failures.append("Critic not activated for financial/risky query")

    # Chairman present
    if case.get("chairman_expected") and directors_used is not None:
        checks += 1
        if "chairman" in directors_used and "Chairman unavailable" not in response_text:
            passed_checks += 1
        else:
            failures.append("Chairman unavailable or not used")

    score = passed_checks / checks if checks > 0 else 0.0
    return EvalResult(
        case_id=case["id"],
        passed=score >= 0.75,
        score=score,
        failures=failures,
    )


# Pytest integration
@pytest.mark.parametrize("case", EVAL_CASES, ids=[c["id"] for c in EVAL_CASES])
def test_eval_case_structure(case):
    """Validates eval cases are well-formed (no API call needed)."""
    assert "id" in case
    assert "query" in case and len(case["query"]) > 5
    assert "expected_language" in case
    assert "must_contain" in case
    assert "must_not_contain" in case


def test_evaluate_response_logic():
    """Unit test for the evaluator itself."""
    case = EVAL_CASES[0]
    good_response = "Квартира в Кракове стоит 700000 zl. В 2026 году ставки 5%. PKO Bank."
    result = evaluate_response(case, good_response, "ru", "Poland", ["devil", "chairman"])
    assert result.score > 0.5

    bad_response = "rekomenduetsya rassmotret vozmozhnost v 2024 godu Ukraina grivn"
    result_bad = evaluate_response(case, bad_response, "uk", "Ukraine", [])
    assert result_bad.score < 0.5


if __name__ == "__main__":
    print(f"Total eval cases: {len(EVAL_CASES)}")
    for c in EVAL_CASES:
        critic = "Critic:YES" if c.get('critic_expected') else "Critic:no"
        print(f"  [{c['id']}] lang={c['expected_language']} {critic}: {c['query'][:60]}")
