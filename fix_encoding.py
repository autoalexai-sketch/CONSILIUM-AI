#!/usr/bin/env python3
"""
fix_encoding.py -- One-time encoding + language fix for CONSILIUM AI v3.0

Run from project root:
    pip install ftfy
    python fix_encoding.py

Fixes:
  1. Double-encoded UTF-8 (mojibake) in index.html -> clean English UI
  2. database.py  -- rewrite with English-only comments
  3. knowledge.py -- fix docstrings
  4. context_gateway.py -- fix docstrings
  5. main.py -- add knowledge router if missing
"""

import re, sys, os

try:
    import ftfy
except ImportError:
    print("ERROR: run  pip install ftfy  first")
    sys.exit(1)

ROOT = os.path.dirname(os.path.abspath(__file__))

def fix_file(path, transform_fn):
    with open(path, 'rb') as f:
        raw = f.read()
    if raw.startswith(b'\xef\xbb\xbf'):
        raw = raw[3:]
    text = raw.decode('utf-8')
    result = transform_fn(text)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(result)
    remaining = re.findall(r'[\u0400-\u04FF]+', result)
    status = f"OK (Cyrillic left: {len(remaining)})" if remaining else "OK (clean)"
    print(f"  FIXED [{status}]: {os.path.relpath(path, ROOT)}")

# ── RU -> EN map (longest strings first) ─────────────────────────────────
RU_EN = [
    ('CONSILIUM \u00b7 9 \u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u043e\u0432 \u00b7 Knowledge Gate \u00b7 IWE v3.0',
     'CONSILIUM \u00b7 9 directors \u00b7 Knowledge Gate \u00b7 IWE v3.0'),
    ('\u0412\u043e\u0439\u0442\u0438 \u2192 \u0421\u043e\u0432\u0435\u0442 \u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u043e\u0432', 'Sign In \u2192 Board of Directors'),
    ('\u0412\u043e\u0439\u0442\u0438 \u0432 \u0434\u0435\u043c\u043e-\u0440\u0435\u0436\u0438\u043c ((\u0431\u0435\u0437 \u0441\u0435\u0440\u0432\u0435\u0440\u0430))', 'Demo Mode (no server)'),
    ('\u26a1 \u0414\u0435\u043c\u043e-\u0440\u0435\u0436\u0438\u043c (\u0431\u0435\u0437 \u0441\u0435\u0440\u0432\u0435\u0440\u0430)', '\u26a1 Demo mode (no server)'),
    ('\u0417\u0430\u0434\u0430\u0439\u0442\u0435 \u0432\u043e\u043f\u0440\u043e\u0441 \u0421\u043e\u0432\u0435\u0442\u0443 \u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u043e\u0432...', 'Ask the Board of Directors...'),
    ('\u041f\u0440\u043e\u0432\u0435\u0434\u0438 \u0441\u0442\u0440\u0430\u0442\u0435\u0433\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u0430\u043d\u0430\u043b\u0438\u0437 \u0442\u0435\u043a\u0443\u0449\u0435\u0433\u043e \u043f\u0440\u043e\u0435\u043a\u0442\u0430',
     'Run a strategic analysis of the current project'),
    ('\u041f\u043e\u043c\u043e\u0433\u0438 \u043f\u0440\u0438\u043d\u044f\u0442\u044c \u0440\u0435\u0448\u0435\u043d\u0438\u0435 \u043f\u043e \u0430\u0440\u0445\u0438\u0442\u0435\u043a\u0442\u0443\u0440\u0435 \u0441\u0438\u0441\u0442\u0435\u043c\u044b',
     'Help make an architecture decision'),
    ('\u0421\u0434\u0435\u043b\u0430\u0439 \u0440\u0435\u0442\u0440\u043e\u0441\u043f\u0435\u043a\u0442\u0438\u0432\u0443 \u043f\u0440\u043e\u0448\u043b\u043e\u0439 \u043d\u0435\u0434\u0435\u043b\u0438', "Run last week's retrospective"),
    ('\u041e\u0446\u0435\u043d\u0438 \u0440\u0438\u0441\u043a\u0438 \u0438 \u0441\u043e\u0437\u0434\u0430\u0439 \u043f\u043b\u0430\u043d \u0434\u0435\u0439\u0441\u0442\u0432\u0438\u0439', 'Assess risks and create action plan'),
    ('\u0420\u0435\u0448\u0435\u043d\u0438\u044f \u043f\u043e\u044f\u0432\u044f\u0442\u0441\u044f \u043f\u043e\u0441\u043b\u0435 \u0434\u0435\u043b\u0438\u0431\u0435\u0440\u0430\u0446\u0438\u0438', 'Decisions will appear after deliberation'),
    ('\u041a\u043e\u0433\u043d\u0438\u0442\u0438\u0432\u043d\u044b\u0435 \u0438\u0437\u043c\u0435\u0440\u0435\u043d\u0438\u044f', 'Cognitive dimensions'),
    ('1. Single point of failure \u0432 API-\u0437\u0430\u0432\u0438\u0441\u0438\u043c\u043e\u0441\u0442\u0438', '1. Single point of failure in API dependency'),
    ('2. \u0412\u0440\u0435\u043c\u0435\u043d\u043d\u044b\u0435 \u043e\u0446\u0435\u043d\u043a\u0438 \u043c\u043e\u0433\u0443\u0442 \u0431\u044b\u0442\u044c \u0437\u0430\u043d\u0438\u0436\u0435\u043d\u044b \u043d\u0430 30-40%',
     '2. Time estimates may be underestimated by 30-40%'),
    ('\u2713 Knowledge Gate: 7/7 \u043f\u0440\u043e\u0432\u0435\u0440\u043e\u043a \u043f\u0440\u043e\u0439\u0434\u0435\u043d\u043e', '\u2713 Knowledge Gate: 7/7 checks passed'),
    ('\u2713 \u041f\u0440\u0438\u043d\u0446\u0438\u043f\u044b \u00b7 \u2713 DRY \u00b7 \u2713 YAGNI \u00b7 \u2713', '\u2713 Principles \u00b7 \u2713 DRY \u00b7 \u2713 YAGNI \u00b7 \u2713'),
    ('MVP \u043a\u043e\u043c\u043f\u043e\u043d\u0435\u043d\u0442\u0430 A \u0432 \u0442\u0435\u0447\u0435\u043d\u0438\u0435 2 \u043d\u0435\u0434\u0435\u043b\u044c.', 'MVP component A within 2 weeks.'),
    ('\u0418\u0441\u0441\u043b\u0435\u0434\u043e\u0432\u0430\u043d\u0438\u0435 \u0430\u043b\u044c\u0442\u0435\u0440\u043d\u0430\u0442\u0438\u0432\u044b B \u043f\u0430\u0440\u0430\u043b\u043b\u0435\u043b\u044c\u043d\u043e.', 'Research alternative B in parallel.'),
    ('\u0420\u0438\u0441\u043a\u0438 Advocate \u0432\u043a\u043b\u044e\u0447\u0435\u043d\u044b \u0432 \u043f\u043b\u0430\u043d \u043c\u0438\u0442\u0438\u0433\u0430\u0446\u0438\u0438.',
     'Advocate risks included in mitigation plan.'),
    ('\u0421\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0439 \u0448\u0430\u0433: \u0441\u043e\u0433\u043b\u0430\u0441\u043e\u0432\u0430\u0442\u044c \u0440\u0435\u0441\u0443\u0440\u0441\u044b \u0434\u043e \u043f\u044f\u0442\u043d\u0438\u0446\u044b.',
     'Next step: coordinate resources by Friday.'),
    ('MVP \u043a\u043e\u043c\u043f\u043e\u043d\u0435\u043d\u0442\u0430 A \u00b7 \u0441\u0440\u043e\u043a 2 \u043d\u0435\u0434.', 'MVP component A \u00b7 deadline 2w'),
    ('\u0421\u043e\u0433\u043b\u0430\u0441\u043e\u0432\u0430\u0442\u044c \u0440\u0435\u0441\u0443\u0440\u0441\u044b \u0434\u043e \u043f\u044f\u0442\u043d\u0438\u0446\u044b', 'Coordinate resources by Friday'),
    ('\u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c fallback-\u043c\u0435\u0445\u0430\u043d\u0438\u0437\u043c API', 'Add API fallback mechanism'),
    ('\u0421\u0431\u043e\u0440 \u0434\u0430\u043d\u043d\u044b\u0445 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d \u00b7 \u0423\u0440\u043e\u0432\u0435\u043d\u044c \u0443\u0432\u0435\u0440\u0435\u043d\u043d\u043e\u0441\u0442\u0438: <span style="color:var(--green)">',
     'Data collection complete \u00b7 Confidence: <span style="color:var(--green)">'),
    ('\u041d\u0430\u0439\u0434\u0435\u043d\u043e 4 \u0440\u0435\u043b\u0435\u0432\u0430\u043d\u0442\u043d\u044b\u0445 \u0438\u0441\u0442\u043e\u0447\u043d\u0438\u043a\u0430. \u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442 \u0438\u0437 Personal Vault \u043f\u043e\u0434\u0433\u0440\u0443\u0436\u0435\u043d: 2 \u043f\u0440\u0438\u043d\u0446\u0438\u043f\u0430, 1 \u043f\u043e\u0445\u043e\u0436\u0435\u0435 \u0440\u0435\u0448\u0435\u043d\u0438\u0435.',
     '4 relevant sources found. Context from Personal Vault loaded: 2 principles, 1 past decision.'),
    ('CoT-\u0430\u043d\u0430\u043b\u0438\u0437 \u0432\u044b\u044f\u0432\u0438\u043b 3 \u043a\u043b\u044e\u0447\u0435\u0432\u044b\u0445 \u043f\u0430\u0442\u0442\u0435\u0440\u043d\u0430. \u0417\u0430\u0434\u0430\u0447\u0430 \u043a\u043b\u0430\u0441\u0441\u0438\u0444\u0438\u0446\u0438\u0440\u043e\u0432\u0430\u043d\u0430 \u043a\u0430\u043a <strong>COMPLEX + FUTURE</strong>. \u0414\u0435\u043a\u043e\u043c\u043f\u043e\u0437\u0438\u0446\u0438\u044f \u043d\u0430 4 \u043d\u0435\u0437\u0430\u0432\u0438\u0441\u0438\u043c\u044b\u0445 \u043f\u043e\u0434\u0437\u0430\u0434\u0430\u0447\u0438 \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d\u0430.',
     'CoT analysis identified 3 key patterns. Task classified as <strong>COMPLEX + FUTURE</strong>. Decomposed into 4 independent subtasks.'),
    ('MVP-first \u0430\u0440\u0445\u0438\u0442\u0435\u043a\u0442\u0443\u0440\u0430 \u043f\u0440\u0435\u0434\u043b\u043e\u0436\u0435\u043d\u0430. 3 \u043c\u043e\u0434\u0443\u043b\u044c\u043d\u044b\u0445 \u043a\u043e\u043c\u043f\u043e\u043d\u0435\u043d\u0442\u0430, \u043e\u0431\u0440\u0430\u0442\u043d\u0430\u044f \u0441\u043e\u0432\u043c\u0435\u0441\u0442\u0438\u043c\u043e\u0441\u0442\u044c \u043e\u0431\u0435\u0441\u043f\u0435\u0447\u0435\u043d\u0430. \u0414\u0432\u0430 \u0430\u043b\u044c\u0442\u0435\u0440\u043d\u0430\u0442\u0438\u0432\u043d\u044b\u0445 \u043f\u043e\u0434\u0445\u043e\u0434\u0430 \u0432\u044b\u0434\u0435\u043b\u0435\u043d\u044b \u0434\u043b\u044f \u0441\u0440\u0430\u0432\u043d\u0435\u043d\u0438\u044f.',
     'MVP-first architecture proposed. 3 modular components, backward compatibility ensured. Two alternative approaches highlighted.'),
    ('\u0421\u0438\u043d\u0442\u0435\u0437 \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d.', 'Synthesis complete.'),
    ('VETO \u043d\u0435 \u0430\u043a\u0442\u0438\u0432\u0438\u0440\u043e\u0432\u0430\u043d. \u041f\u043e\u0437\u0438\u0446\u0438\u0438 Scout \u0438 Architect \u0441\u043e\u0433\u043b\u0430\u0441\u043e\u0432\u0430\u043d\u044b.',
     'VETO not activated. Scout and Architect positions aligned.'),
    ('\u0420\u0435\u0448\u0435\u043d\u0438\u0435 \u041f\u0440\u0435\u0434\u0441\u0435\u0434\u0430\u0442\u0435\u043b\u044f:', "Chairman's Decision:"),
    ('\u0420\u0435\u043a\u043e\u043c\u0435\u043d\u0434\u0443\u044e:', 'Recommendation:'),
    ('${name} \u0434\u0443\u043c\u0430\u0435\u0442...', '${name} thinking...'),
    ('\u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u043e\u0445\u0440\u0430\u043d\u0435\u043d\u0438\u044f \u0441\u0442\u0430\u0442\u0443\u0441\u0430', 'Status save error'),
    ('\u0421\u0442\u0440\u0430\u0442\u0435\u0433\u0438\u0447\u0435\u0441\u043a\u0438\u0439 \u0430\u043d\u0430\u043b\u0438\u0437', 'Strategic analysis'),
    ('\u0410\u0440\u0445\u0438\u0442\u0435\u043a\u0442\u0443\u0440\u043d\u043e\u0435 \u0440\u0435\u0448\u0435\u043d\u0438\u0435', 'Architecture decision'),
    ('\u0427\u0430\u0442 / \u0414\u0435\u043b\u0438\u0431\u0435\u0440\u0430\u0446\u0438\u044f', 'Chat / Deliberation'),
    ('Standard \u2014 6 \u0444\u0430\u0437', 'Standard \u2014 6 phases'),
    ('Strategy \u2014 SWOT + \u0441\u0446\u0435\u043d\u0430\u0440\u0438\u0438', 'Strategy \u2014 SWOT + scenarios'),
    ('Crisis \u2014 \u0431\u044b\u0441\u0442\u0440\u043e', 'Crisis \u2014 fast'),
    ('Reflection \u2014 \u0440\u0435\u0442\u0440\u043e', 'Reflection \u2014 retro'),
    ('Planning \u2014 \u0446\u0435\u043b\u0438 + \u043f\u043b\u0430\u043d', 'Planning \u2014 goals + plan'),
    ('Deep Analysis \u2014 \u0440\u0430\u0441\u0448\u0438\u0440\u0435\u043d\u043d\u044b\u0439', 'Deep Analysis \u2014 extended'),
    ("'\u0418\u0441\u0442\u043e\u0440\u0438\u044f \u2014 \u0441\u043a\u043e\u0440\u043e'", "'History \u2014 coming soon'"),
    ("'\u0414\u0430\u0448\u0431\u043e\u0440\u0434 \u2014 \u0441\u043a\u043e\u0440\u043e'", "'Dashboard \u2014 coming soon'"),
    ("'\u0420\u0435\u0448\u0435\u043d\u0438\u044f \u2014 \u0441\u043a\u043e\u0440\u043e'", "'Decisions \u2014 coming soon'"),
    ("'\u041f\u0440\u0438\u043d\u0446\u0438\u043f\u044b \u2014 \u0441\u043a\u043e\u0440\u043e'", "'Principles \u2014 coming soon'"),
    ("'Wiki \u2014 \u0441\u043a\u043e\u0440\u043e'", "'Wiki \u2014 coming soon'"),
    ("'\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438'", "'Settings'"),
    ("'\u041d\u0435\u0432\u0435\u0440\u043d\u044b\u0435 \u0434\u0430\u043d\u043d\u044b\u0435'", "'Invalid credentials'"),
    ("'\u041d\u0435\u0432\u0435\u0440\u043d\u044b\u0439 \u0442\u043e\u043a\u0435\u043d'", "'Invalid token'"),
    ("'\u0421\u0435\u0440\u0432\u0435\u0440 \u043f\u0440\u043e\u0441\u044b\u043f\u0430\u0435\u0442\u0441\u044f (cold start) \u2014 \u043f\u043e\u0434\u043e\u0436\u0434\u0438\u0442\u0435 10 \u0441\u0435\u043a \u0438 \u043f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0441\u043d\u043e\u0432\u0430'",
     "'Server is starting (cold start) \u2014 wait 10 sec and try again'"),
    ("'\u0412\u0432\u0435\u0434\u0438\u0442\u0435 email \u0438 \u043f\u0430\u0440\u043e\u043b\u044c'", "'Enter email and password'"),
    ("'\u0417\u0430\u043f\u043e\u043b\u043d\u0438\u0442\u0435 \u0432\u0441\u0435 \u043f\u043e\u043b\u044f'", "'Fill in all fields'"),
    ("'\u0414\u0435\u043c\u043e-\u0440\u0435\u0436\u0438\u043c \u0430\u043a\u0442\u0438\u0432\u0438\u0440\u043e\u0432\u0430\u043d'", "'Demo mode activated'"),
    ("'\u0410\u043a\u043a\u0430\u0443\u043d\u0442 \u0441\u043e\u0437\u0434\u0430\u043d!'", "'Account created!'"),
    ("'\u0410\u043a\u043a\u0430\u0443\u043d\u0442 \u0441\u043e\u0437\u0434\u0430\u043d! \u0412\u0445\u043e\u0434\u0438\u043c...'", "'Account created! Signing in...'"),
    ("'\u0421\u0435\u0440\u0432\u0435\u0440 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d. \u041f\u043e\u043f\u0440\u043e\u0431\u0443\u0439\u0442\u0435 \u0434\u0435\u043c\u043e-\u0440\u0435\u0436\u0438\u043c.'",
     "'Server unavailable. Try demo mode.'"),
    ("'\u041f\u0430\u0440\u043e\u043b\u044c \u043c\u0438\u043d\u0438\u043c\u0443\u043c 6 \u0441\u0438\u043c\u0432\u043e\u043b\u043e\u0432'", "'Password must be at least 6 chars'"),
    ("'\u041f\u0430\u0440\u043e\u043b\u0438 \u043d\u0435 \u0441\u043e\u0432\u043f\u0430\u0434\u0430\u044e\u0442'", "'Passwords do not match'"),
    ("'\u041e\u0448\u0438\u0431\u043a\u0430 \u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u0438'", "'Registration error'"),
    ("'\u041e\u0448\u0438\u0431\u043a\u0430 \u0441\u0435\u0440\u0432\u0435\u0440\u0430'", "'Server error'"),
    ("'\u041d\u0435\u0442 \u043e\u0442\u0432\u0435\u0442\u0430'", "'No response'"),
    ("'\u041e\u0448\u0438\u0431\u043a\u0430 \u0437\u0430\u043f\u0440\u043e\u0441\u0430: '", "'Request error: '"),
    ("'\u041d\u0435\u0442 \u0434\u0430\u043d\u043d\u044b\u0445'", "'No data'"),
    ("'Synthesizer \u043d\u0435 \u0437\u0430\u043f\u0443\u0449\u0435\u043d'", "'Synthesizer not running'"),
    ("'\u0412\u044b\u0441\u043e\u043a\u0430\u044f \u043a\u043e\u0433\u0435\u0440\u0435\u043d\u0442\u043d\u043e\u0441\u0442\u044c'", "'High coherence'"),
    ("'\u0414\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u0430 \u0441\u043e\u0433\u043b\u0430\u0441\u043e\u0432\u0430\u043d\u044b'", "'Directors aligned'"),
    ("'\u0421\u0440\u0435\u0434\u043d\u044f\u044f'", "'Average'"),
    ("'\u0415\u0441\u0442\u044c \u0440\u0430\u0441\u0445\u043e\u0436\u0434\u0435\u043d\u0438\u044f'", "'Discrepancies found'"),
    ("'\u26a0 VETO \u0430\u043a\u0442\u0438\u0432\u0438\u0440\u043e\u0432\u0430\u043d'", "'\\u26a0 VETO activated'"),
    ("'\u0422\u0440\u0435\u0431\u0443\u0435\u0442 \u043f\u0435\u0440\u0435\u0440\u0430\u0431\u043e\u0442\u043a\u0438'", "'Requires revision'"),
    ("'WebSocket \u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0451\u043d'", "'WebSocket connected'"),
    ("'\u041d\u0435\u0434\u043e\u0441\u0442\u0430\u0442\u043e\u0447\u043d\u043e \u043a\u0440\u0435\u0434\u0438\u0442\u043e\u0432'", "'Insufficient credits'"),
    ("draft: '\ud83d\udcdd \u0427\u0435\u0440\u043d\u043e\u0432\u0438\u043a'", "draft: '\ud83d\udcdd Draft'"),
    ("verified: '\u2713 \u0412\u0435\u0440\u0438\u0444\u0438\u0446\u0438\u0440\u043e\u0432\u0430\u043d'", "verified: '\u2713 Verified'"),
    ("approved: '\u2705 \u0423\u0442\u0432\u0435\u0440\u0436\u0434\u0451\u043d'", "approved: '\u2705 Approved'"),
    ("label.textContent = '\u0421\u0432\u0435\u0442\u043b\u0430\u044f'", "label.textContent = 'Light'"),
    ("label.textContent = '\u0422\u0451\u043c\u043d\u0430\u044f'", "label.textContent = 'Dark'"),
    ("l.textContent = '\u0421\u0432\u0435\u0442\u043b\u0430\u044f'", "l.textContent = 'Light'"),
    ("setConn('demo', 'demo-\u0440\u0435\u0436\u0438\u043c')", "setConn('demo', 'demo-mode')"),
    ("setConn('connecting','\u043f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435...')", "setConn('connecting','connecting...')"),
    ("setConn('offline','\u043e\u0448\u0438\u0431\u043a\u0430')", "setConn('offline','error')"),
    ("btn.textContent = '\u0412\u043e\u0439\u0442\u0438 \u2192 \u0421\u043e\u0432\u0435\u0442 \u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u043e\u0432'",
     "btn.textContent = 'Sign In \u2192 Board of Directors'"),
    ("btn.textContent = '\u0412\u0445\u043e\u0434\u0438\u043c...'", "btn.textContent = 'Signing in...'"),
    ("btn.textContent = '\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u0430\u043a\u043a\u0430\u0443\u043d\u0442'", "btn.textContent = 'Create Account'"),
    ("btn.textContent = '\u0421\u043e\u0437\u0434\u0430\u0451\u043c...'", "btn.textContent = 'Creating...'"),
    ("'\u0423\u0436\u0435 \u0435\u0441\u0442\u044c \u0430\u043a\u043a\u0430\u0443\u043d\u0442? <span onclick=\"showLogin()\">\u0412\u043e\u0439\u0442\u0438</span>'",
     "'Already have an account? <span onclick=\"showLogin()\">Sign In</span>'"),
    ("'\u041d\u0435\u0442 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430? <span onclick=\"showRegister()\">\u0417\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u043e\u0432\u0430\u0442\u044c\u0441\u044f</span>'",
     "'No account? <span onclick=\"showRegister()\">Register</span>'"),
    ("'\u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440 \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d'", "'provider unavailable'"),
    ('`\u26a0 VETO: \u043a\u043e\u0433\u0435\u0440\u0435\u043d\u0442\u043d\u043e\u0441\u0442\u044c ${coherence}% \u00b7 ${reason}`',
     '`\\u26a0 VETO: coherence ${coherence}% \u00b7 ${reason}`'),
    ('`\u0414\u0435\u043b\u0438\u0431\u0435\u0440\u0430\u0446\u0438\u044f \u0437\u0430\u0432\u0435\u0440\u0448\u0435\u043d\u0430 \u00b7 ${used} \u043a\u0440\u0435\u0434 \u00b7 ${(ms/1000).toFixed(1)}\u0441`',
     '`Deliberation complete \u00b7 ${used} credits \u00b7 ${(ms/1000).toFixed(1)}s`'),
    ('`\u041f\u0440\u043e\u0442\u043e\u043a\u043e\u043b: ${name}`', '`Protocol: ${name}`'),
    ('`\u0420\u0435\u0448\u0435\u043d\u0438\u0435: ${labels[state]}`', '`Decision: ${labels[state]}`'),
    ('Backend: FastAPI \u043d\u0430 http://localhost:8000', 'Backend: FastAPI at http://localhost:8000'),
    ('\u041d\u0435 \u0430\u0432\u0442\u043e\u0440\u0438\u0437\u043e\u0432\u0430\u043d', 'Not authorized'),
    ('\u0414\u043e\u0431\u0440\u044b\u0439 \u0434\u0435\u043d\u044c,', 'Good day,'),
    ('\u041d\u0430\u0432\u0438\u0433\u0430\u0446\u0438\u044f', 'Navigation'),
    ('\u0418\u0441\u0442\u043e\u0440\u0438\u044f \u0441\u0435\u0441\u0441\u0438\u0439', 'Session History'),
    ('\u0411\u0430\u0437\u0430 \u0437\u043d\u0430\u043d\u0438\u0439', 'Knowledge Base'),
    ('\u0418\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\u044b', 'Tools'),
    ('\u042d\u043c\u043e\u0446. \u043d\u0430\u0433\u0440\u0443\u0437\u043a\u0430', 'Emotional load'),
    ('\u041a\u043e\u0433\u0435\u0440\u0435\u043d\u0442\u043d\u043e\u0441\u0442\u044c', 'Coherence'),
    ('\u041e\u0436\u0438\u0434\u0430\u043d\u0438\u0435...', 'Waiting...'),
    ('\u0417\u0430\u043f\u0443\u0441\u0442\u0438\u0442\u0435 \u0434\u0435\u043b\u0438\u0431\u0435\u0440\u0430\u0446\u0438\u044e', 'Start deliberation'),
    ('\u0421\u043e\u0432\u0435\u0442 \u0434\u0438\u0440\u0435\u043a\u0442\u043e\u0440\u043e\u0432', 'Board of Directors'),
    ('\u26a0 \u0420\u0438\u0441\u043a\u0438 \u0432\u044b\u044f\u0432\u043b\u0435\u043d\u044b:', '\u26a0 Risks detected:'),
    ('Wiki \u0441\u0442\u0440\u0430\u043d\u0438\u0446', 'Wiki pages'),
    ('\u041f\u0435\u0440\u0435\u043a\u043b\u044e\u0447\u0438\u0442\u044c \u0442\u0435\u043c\u0443', 'Toggle theme'),
    ('\u0410\u043d\u0430\u043b\u0438\u0437 \u0437\u0430\u0434\u0430\u0447\u0438', 'Task analysis'),
    ('\u0421\u0440\u043e\u0447\u043d\u043e\u0441\u0442\u044c', 'Urgency'),
    ('\u0413\u043b\u0443\u0431\u0438\u043d\u0430', 'Depth'),
    ('\u0412\u042b\u0421\u041e\u041a\u0418\u0419', 'HIGH'),
    ('\u0420\u0435\u0433\u0438\u0441\u0442\u0440\u0430\u0446\u0438\u044f', 'Sign Up'),
    ('\u041f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u0435 \u043f\u0430\u0440\u043e\u043b\u044c', 'Confirm Password'),
    ('\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u0430\u043a\u043a\u0430\u0443\u043d\u0442', 'Create Account'),
    ('\u0412\u043e\u0439\u0442\u0438', 'Sign In'),
    ('\u041f\u0430\u0440\u043e\u043b\u044c', 'Password'),
    ('\u041d\u0435\u0442 \u0430\u043a\u043a\u0430\u0443\u043d\u0442\u0430?', 'No account?'),
    ('\u0417\u0430\u0440\u0435\u0433\u0438\u0441\u0442\u0440\u0438\u0440\u043e\u0432\u0430\u0442\u044c\u0441\u044f', 'Register'),
    ('\u0421\u0442\u0440\u0430\u0442\u0435\u0433\u0438\u044f', 'Strategy'),
    ('\u041f\u0440\u043e\u0435\u043a\u0442 \u0410', 'Project A'),
    ('\u041b\u0438\u0447\u043d\u043e\u0435', 'Personal'),
    ('\u0420\u0435\u0442\u0440\u043e\u0441\u043f\u0435\u043a\u0442\u0438\u0432\u0430', 'Retrospective'),
    ('\u041e\u0446\u0435\u043d\u043a\u0430 \u0440\u0438\u0441\u043a\u043e\u0432', 'Risk assessment'),
    ('\u0414\u0430\u0448\u0431\u043e\u0440\u0434', 'Dashboard'),
    ('\u041f\u0440\u0438\u043d\u0446\u0438\u043f\u044b', 'Principles'),
    ('\u0420\u0435\u0448\u0435\u043d\u0438\u044f', 'Decisions'),
    ('\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438', 'Settings'),
    ('\u0424\u0430\u0439\u043b', 'File'),
    ('\u043d\u043e\u0432\u0430\u044f \u0441\u0442\u0440\u043e\u043a\u0430', 'new line'),
    ('\u043e\u0442\u043f\u0440\u0430\u0432\u0438\u0442\u044c \u00b7', 'send \u00b7'),
    ('\u041a\u0440\u0435\u0434\u0438\u0442\u044b:', 'Credits:'),
    ('\u0422\u0451\u043c\u043d\u0430\u044f', 'Dark'),
    ('\u0421\u0432\u0435\u0442\u043b\u0430\u044f', 'Light'),
    ('\u0421\u0435\u0440\u0432\u0435\u0440:', 'Server:'),
    ('\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c', 'User'),
    ('lang="ru"', 'lang="en"'),
]


def fix_index(text):
    fixed = ftfy.fix_text(text)
    for ru, en in RU_EN:
        fixed = fixed.replace(ru, en)
    # Wipe remaining Cyrillic from CSS/JS comments
    def fix_block(m):
        c = m.group(0)
        return re.sub(r'[\u0400-\u04FF]+', '', c) if any('\u0400' <= ch <= '\u04FF' for ch in c) else c
    def fix_line(m):
        c = m.group(0)
        return re.sub(r'[\u0400-\u04FF]+', '', c) if any('\u0400' <= ch <= '\u04FF' for ch in c) else c
    fixed = re.sub(r'/\*.*?\*/', fix_block, fixed, flags=re.DOTALL)
    fixed = re.sub(r'//[^\n]*', fix_line, fixed)
    return fixed


DATABASE_PY = """\
\"\"\"
app/database.py -- SQLAlchemy engine, metadata, table definitions.
\"\"\"

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String,
    MetaData, Table, inspect, Text, DateTime, Float, Boolean,
)
from loguru import logger

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)
metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("email", String(255), unique=True, nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("credits", Integer, default=10),
    Column("auth_token", String(255), nullable=True),
    Column("created_at", DateTime, default=datetime.utcnow),
)

chat_history = Table(
    "chat_history",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, nullable=False),
    Column("chat_id", String(100), nullable=False),
    Column("title", String(255)),
    Column("messages", Text),
    Column("updated_at", DateTime, default=datetime.utcnow),
)

# -- Experience Layer --------------------------------------------------------
experience_sessions = Table(
    "experience_sessions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, nullable=False),
    Column("chat_id", String(100), nullable=False),
    Column("query_text", Text, nullable=False),
    Column("query_hash", String(64), nullable=False),
    Column("task_type", String(100), nullable=True),
    Column("protocol_used", String(100), nullable=True),
    Column("selected_directors", Text, nullable=True),
    Column("started_at", DateTime, default=datetime.utcnow),
    Column("finished_at", DateTime, nullable=True),
    Column("latency_ms", Integer, nullable=True),
    Column("cost_usd", Float, nullable=True),
    Column("status", String(20), default="running"),
    Column("outcome_label", String(50), nullable=True),
    Column("coherence_score", Float, nullable=True),
    Column("user_rating", Integer, nullable=True),
    Column("helpfulness_score", Float, nullable=True),
    Column("feedback_text", Text, nullable=True),
    Column("followup_required", Boolean, default=False),
)

experience_signals = Table(
    "experience_signals",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("session_id", Integer, nullable=False),
    Column("signal_type", String(100), nullable=False),
    Column("value_num", Float, nullable=True),
    Column("value_text", Text, nullable=True),
    Column("source", String(100), nullable=True),
    Column("weight", Float, default=1.0),
    Column("created_at", DateTime, default=datetime.utcnow),
)

# -- Decision Journal --------------------------------------------------------
decision_journal = Table(
    "decision_journal",
    metadata,
    Column("id",             Integer,      primary_key=True),
    Column("user_id",        Integer,      nullable=False),
    Column("session_id",     Integer,      nullable=True),
    Column("title",          String(255),  nullable=False),
    Column("query_text",     Text,         nullable=False),
    Column("verdict",        Text,         nullable=False),
    Column("council_used",   String(500),  nullable=True),
    Column("outcome_label",  String(50),   nullable=True),
    Column("tags",           String(500),  nullable=True),
    Column("is_pinned",      Boolean,      default=False),
    Column("approval_state", String(20),   default="draft"),  # draft|verified|approved
    Column("created_at",     DateTime,     default=datetime.utcnow),
    Column("updated_at",     DateTime,     default=datetime.utcnow),
)

# -- User Principles ---------------------------------------------------------
user_principles = Table(
    "user_principles",
    metadata,
    Column("id",         Integer,     primary_key=True),
    Column("user_id",    Integer,     nullable=False),
    Column("title",      String(255), nullable=False),
    Column("body",       Text,        nullable=False),
    Column("source",     String(255), nullable=True),
    Column("category",   String(100), nullable=True),
    Column("is_active",  Boolean,     default=True),
    Column("created_at", DateTime,    default=datetime.utcnow),
)


def init_database() -> None:
    \\\"\\\"\\\"Create tables on first run or update schema if outdated.\\\"\\\"\\\"
    inspector = inspect(engine)

    if inspector.has_table("users"):
        columns = [col["name"] for col in inspector.get_columns("users")]
        if "auth_token" not in columns:
            logger.warning("DB schema outdated -- running migration...")
            metadata.drop_all(engine, tables=[users])
            metadata.create_all(engine)
            logger.info("Database updated!")
    else:
        metadata.create_all(engine)

    if not inspector.has_table("chat_history"):
        chat_history.create(engine)

    if not inspector.has_table("experience_sessions"):
        experience_sessions.create(engine)
        logger.info("experience_sessions table created")

    if not inspector.has_table("experience_signals"):
        experience_signals.create(engine)
        logger.info("experience_signals table created")

    if not inspector.has_table("decision_journal"):
        decision_journal.create(engine)
        logger.info("decision_journal table created")

    if not inspector.has_table("user_principles"):
        user_principles.create(engine)
        logger.info("user_principles table created")

    logger.info("Database initialized")
"""


def fix_knowledge(text):
    fixed = ftfy.fix_text(text)
    old = 'app/api/knowledge.py \\u2014 Decision Journal + User Principles\\nP0 \\u2014 \\u043f\\u0435\\u0440\\u0441\\u043e\\u043d\\u0430\\u043b\\u044c\\u043d\\u0430\\u044f \\u0431\\u0430\\u0437\\u0430 \\u0440\\u0435\\u0448\\u0435\\u043d\\u0438\\u0439 \\u0438 \\u043f\\u0440\\u0438\\u043d\\u0446\\u0438\\u043f\\u043e\\u0432 \\u043f\\u043e\\u043b\\u044c\\u0437\\u043e\\u0432\\u0430\\u0442\\u0435\\u043b\\u044f'
    new_ = 'app/api/knowledge.py -- Decision Journal + User Principles API\\nCRUD endpoints for decision journal and user principles.'
    fixed = fixed.replace(old, new_)
    fixed = fixed.replace(
        '"""\\u0418\\u0437\\u043c\\u0435\\u043d\\u0438\\u0442\\u044c \\u0441\\u0442\\u0430\\u0442\\u0443\\u0441 \\u0440\\u0435\\u0448\\u0435\\u043d\\u0438\\u044f: draft \\u2192 verified \\u2192 approved."""',
        '"""Update approval state: draft -> verified -> approved."""'
    )
    return fixed


def fix_gateway(text):
    fixed = ftfy.fix_text(text)
    # Replace Russian docstring with English
    fixed = re.sub(
        r'"""[\s\S]*?core/context_gateway\.py.*?Chairman prompts\.\s*"""',
        '"""\\ncore/context_gateway.py -- Context Gateway for CONSILIUM AI v3.0\\n\\nFetches relevant user context before each deliberation:\\n  1. User principles (user_principles table)\\n  2. Similar past decisions (decision_journal table)\\n\\nContext is injected into Scout and Chairman prompts.\\n"""',
        fixed,
        count=1,
        flags=re.DOTALL,
    )
    fixed = fixed.replace('# 1. \\u041f\\u0440\\u0438\\u043d\\u0446\\u0438\\u043f\\u044b \\u043f\\u043e\\u043b\\u044c\\u0437\\u043e\\u0432\\u0430\\u0442\\u0435\\u043b\\u044f',
                          '# 1. User principles')
    fixed = fixed.replace('# 2. \\u041f\\u043e\\u0445\\u043e\\u0436\\u0438\\u0435 \\u043f\\u0440\\u043e\\u0448\\u043b\\u044b\\u0435 \\u0440\\u0435\\u0448\\u0435\\u043d\\u0438\\u044f \\u2014 \\u043f\\u0440\\u043e\\u0441\\u0442\\u043e\\u0439 \\u0441\\u043a\\u043e\\u0440\\u0438\\u043d\\u0433 \\u043f\\u043e \\u043f\\u0435\\u0440\\u0435\\u0441\\u0435\\u0447\\u0435\\u043d\\u0438\\u044e \\u0441\\u043b\\u043e\\u0432',
                          '# 2. Similar past decisions -- simple word-overlap scoring')
    fixed = fixed.replace('# \\u0413\\u043b\\u043e\\u0431\\u0430\\u043b\\u044c\\u043d\\u044b\\u0439 \\u0441\\u0438\\u043d\\u0433\\u043b\\u0442\\u043e\\u043d',
                          '# Global singleton')
    # strip remaining Cyrillic
    fixed = re.sub(r'[\u0400-\u04FF]+', '', fixed)
    return fixed


def fix_main(text):
    fixed = ftfy.fix_text(text)
    if 'knowledge_router' not in fixed:
        fixed = fixed.replace(
            'from app.api.experience import router as experience_router',
            'from app.api.experience import router as experience_router\nfrom app.api.knowledge import router as knowledge_router'
        )
        fixed = fixed.replace(
            'app.include_router(experience_router, tags=["experience"])',
            'app.include_router(experience_router, tags=["experience"])\napp.include_router(knowledge_router, tags=["knowledge"])'
        )
        print("  main.py: knowledge_router added")
    return fixed


# ── Run ────────────────────────────────────────────────────────────────────
print("CONSILIUM AI -- encoding + language fix")
print("=" * 45)

files = [
    (os.path.join(ROOT, 'frontend', 'index.html'),     fix_index),
    (os.path.join(ROOT, 'app', 'api', 'knowledge.py'), fix_knowledge),
    (os.path.join(ROOT, 'core', 'context_gateway.py'), fix_gateway),
    (os.path.join(ROOT, 'main.py'),                    fix_main),
]

for path, fn in files:
    if os.path.exists(path):
        fix_file(path, fn)
    else:
        print(f"  SKIP (not found): {path}")

# database.py -- clean rewrite
db_path = os.path.join(ROOT, 'app', 'database.py')
with open(db_path, 'w', encoding='utf-8') as f:
    f.write(DATABASE_PY)
print(f"  FIXED [OK (clean)]: app/database.py")

print("=" * 45)
print("Done. Next:")
print("  git add -A")
print('  git commit -m "fix: English-only code, fix mojibake in index.html"')
print("  git push origin main")
