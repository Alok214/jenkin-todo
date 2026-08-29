#!/usr/bin/env python3
"""
semgrep-report.json → semgrep-summary.txt + semgrep-summary.html
Exit 1 if ERROR found
"""

import json, sys

CWE_FIX_HINTS = {
    "CWE-22":  "Path Traversal — validate and canonicalize user-controlled paths against an allowlist base directory.",
    "CWE-78":  "Command Injection — never concatenate user input into shell commands; pass arguments as list.",
    "CWE-79":  "XSS — encode/escape output, use templating engine's auto-escaping.",
    "CWE-89":  "SQL Injection — use PreparedStatement with bound parameters, never string concatenation.",
    "CWE-326": "Weak Crypto — use AES/GCM/NoPadding with random IV, not ECB or default mode.",
    "CWE-352": "CSRF — enable CSRF token protection; do not disable globally.",
    "CWE-353": "Subresource Integrity missing — add integrity='sha384-...' + crossorigin to CDN tags.",
    "CWE-502": "Insecure Deserialization — avoid Java native serialization on untrusted input.",
    "CWE-611": "XXE — disable external entity processing in XML parsers.",
    "CWE-798": "Hardcoded Credentials — read secrets from environment variables or secrets manager.",
    "CWE-918": "SSRF — validate URL scheme and host against allowlist before fetching.",
    "CWE-939": "Review manually — see Semgrep documentation for this rule.",
}

# ── load report ───────────────────────────────────────────────
try:
    with open("semgrep-report.json", encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    print(f"⚠️  Could not read semgrep report: {e}")
    with open("semgrep-summary.txt", "w", encoding="utf-8") as f:
        f.write("STATUS=error\nCOUNT=0\nERRORS=0\nWARNINGS=0\nROWS\n")
    sys.exit(0)

results = data.get("results", [])
errors  = [r for r in results if r.get("extra", {}).get("severity") == "ERROR"]
warns   = [r for r in results if r.get("extra", {}).get("severity") == "WARNING"]

# ── console log (same as GitHub Actions) ─────────────────────
print(f"\n{'='*65}")
print(f"  SEMGREP SCAN RESULTS")
print(f"  Files scanned : {len(data.get('paths', {}).get('scanned', []))}")
print(f"  Total findings: {len(results)}  |  ERROR: {len(errors)}  |  WARNING: {len(warns)}")
print(f"{'='*65}")

summary_lines = []
html_rows     = ""

for r in results:
    extra = r.get("extra", {}) or {}
    meta  = extra.get("metadata", {}) or {}
    sev   = extra.get("severity", "INFO")
    rid   = (r.get("check_id") or "unknown").split(".")[-1]
    path  = r.get("path", "?")
    line  = r.get("start", {}).get("line", "?")
    msg   = extra.get("message", "")[:200]

    cwe_raw   = meta.get("cwe", ["N/A"])
    cwe       = cwe_raw[0] if isinstance(cwe_raw, list) and cwe_raw else cwe_raw
    owasp_raw = meta.get("owasp", ["N/A"])
    owasp     = owasp_raw[0] if isinstance(owasp_raw, list) and owasp_raw else owasp_raw

    cwe_id = None
    if isinstance(cwe, str):
        for token in cwe.split():
            if token.startswith("CWE-"):
                cwe_id = token.rstrip(":")
                break

    fix_hint = CWE_FIX_HINTS.get(cwe_id, "Review manually — see Semgrep documentation for this rule.")

    icon = "🔴" if sev == "ERROR" else "🟡"
    print(f"\n{icon} {sev} — {rid}")
    print(f"   File  : {path}:{line}")
    print(f"   CWE   : {cwe}")
    print(f"   OWASP : {owasp}")
    print(f"   Issue : {msg}")
    print(f"   Fix   : {fix_hint}")

    # for semgrep-summary.txt (same format as GitHub Actions)
    summary_lines.append(
        f"| {icon} {sev} | `{path}:{line}` | {rid} | {cwe_id or 'N/A'} | {fix_hint[:80]} |"
    )

    # for HTML report
    sev_color = {"ERROR": "#e53e3e", "WARNING": "#dd6b20"}.get(sev, "#718096")
    html_rows += f"""<tr>
        <td><span style="background:{sev_color};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:700">{icon} {sev}</span></td>
        <td style="font-family:monospace;font-size:12px">{path}:<b>{line}</b></td>
        <td style="font-family:monospace;font-size:12px">{rid}</td>
        <td style="font-size:12px">{cwe_id or 'N/A'}</td>
        <td style="font-size:12px">{fix_hint}</td>
    </tr>"""

# ── write semgrep-summary.txt (same as GitHub Actions) ────────
status = "fail" if errors else "pass"
with open("semgrep-summary.txt", "w", encoding="utf-8") as f:
    f.write(f"STATUS={status}\n")
    f.write(f"COUNT={len(results)}\n")
    f.write(f"ERRORS={len(errors)}\n")
    f.write(f"WARNINGS={len(warns)}\n")
    f.write("ROWS\n")
    for row in summary_lines:
        f.write(row + "\n")

# ── write semgrep-summary.html ────────────────────────────────
banner_color = "#276749" if not errors else "#9b2335"
status_text  = "✅ PASSED" if not errors else "❌ FAILED"

table = f"""
<table>
  <thead><tr>
    <th>Severity</th><th>File : Line</th><th>Rule</th><th>CWE</th><th>Fix Hint</th>
  </tr></thead>
  <tbody>{html_rows}</tbody>
</table>""" if results else '<p style="color:#48bb78;font-size:16px">🎉 No findings — clean scan!</p>'

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Semgrep SAST Report</title>
<style>
  body   {{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f7fafc;margin:0;padding:24px;color:#2d3748}}
  .banner{{background:{banner_color};color:#fff;padding:16px 24px;border-radius:8px;margin-bottom:24px}}
  .banner h1{{margin:0 0 4px;font-size:22px}} .banner p{{margin:0;opacity:.85;font-size:14px}}
  .cards{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}}
  .card{{background:#fff;border-radius:8px;padding:16px 24px;box-shadow:0 1px 3px rgba(0,0,0,.1);min-width:120px;text-align:center}}
  .card .num{{font-size:32px;font-weight:700}} .card .lbl{{font-size:12px;color:#718096;margin-top:4px}}
  .err{{color:#e53e3e}} .warn{{color:#dd6b20}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
  th{{background:#edf2f7;padding:10px 12px;text-align:left;font-size:12px;text-transform:uppercase;color:#4a5568}}
  td{{padding:10px 12px;border-bottom:1px solid #edf2f7;vertical-align:top}}
  tr:last-child td{{border-bottom:none}} tr:hover td{{background:#f7fafc}}
</style></head><body>
<div class="banner"><h1>🔒 Semgrep SAST — {status_text}</h1><p>Static analysis security scan</p></div>
<div class="cards">
  <div class="card"><div class="num">{len(results)}</div><div class="lbl">Total</div></div>
  <div class="card"><div class="num err">{len(errors)}</div><div class="lbl">Errors</div></div>
  <div class="card"><div class="num warn">{len(warns)}</div><div class="lbl">Warnings</div></div>
</div>
{table}
</body></html>"""

with open("semgrep-summary.html", "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n[INFO] semgrep-summary.txt + semgrep-summary.html written")

if errors:
    print(f"\n❌ {len(errors)} ERROR(s) — fix required before merge!")
    sys.exit(1)
else:
    print(f"\n✅ No ERROR findings" + (f"  ({len(warns)} warnings)" if warns else ""))
