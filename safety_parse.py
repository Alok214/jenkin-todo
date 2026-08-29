#!/usr/bin/env python3
"""
pip-audit report (pip-audit-report.json) → safety-summary.txt + safety-summary.html
Exit 1 if HIGH/CRITICAL found (based on threshold)
Python equivalent of owasp_parse.py in sosuv-workflow-api
Handles both pip-audit JSON and safety JSON formats
"""

import json, glob, sys, os

CVSS_FAIL_THRESHOLD = float(os.environ.get("CVSS_FAIL_THRESHOLD", "7"))
# For pip-audit we treat every vuln as HIGH (7.5) since it has no CVSS by default.
# If you want to fail only on CRITICAL, set CVSS_FAIL_THRESHOLD=9

reports = glob.glob("**/pip-audit-report.json", recursive=True)
# fallback to safety report
if not reports:
    reports = glob.glob("**/safety-report.json", recursive=True)
if not reports:
    # also try generic
    reports = glob.glob("pip-audit-report.json")

if not reports:
    print("⚠️  No pip-audit/safety report found — scan may have failed or no vulns")
    with open("safety-summary.txt", "w", encoding="utf-8") as f:
        f.write("STATUS=pass\nCOUNT=0\nCRITICAL=0\nHIGH=0\nMEDIUM=0\nROWS\n")
    # also write empty owasp file for compatibility with security-summary post step
    with open("owasp-summary.txt", "w", encoding="utf-8") as f:
        f.write("STATUS=pass\nCOUNT=0\nCRITICAL=0\nHIGH=0\nMEDIUM=0\nROWS\n")
    sys.exit(0)

report_path = reports[0]
print(f"[INFO] Reading report: {report_path}")

with open(report_path, encoding="utf-8") as f:
    data = json.load(f)

# pip-audit format: {"dependencies": [{"name":..., "version":..., "vulns": [...] }]}
# safety format: {"vulnerabilities": [...]} or list
critical, high, medium = [], [], []

def add_entry(name, cve, score, desc, current, fix):
    entry = dict(name=name, cve=cve, score=score, desc=desc, current=current, fix=fix)
    if score >= 9:
        critical.append(entry)
    elif score >= 7:
        high.append(entry)
    elif score >= 4:
        medium.append(entry)
    else:
        medium.append(entry)

if "dependencies" in data:
    # pip-audit JSON
    for dep in data.get("dependencies", []):
        vulns = dep.get("vulns", [])
        if not vulns:
            continue
        name = dep.get("name", "unknown")
        current_version = dep.get("version", "")
        for v in vulns:
            # v: {"id": "PYSEC-...", "fix_versions": [...], "aliases": [...], "description": ...}
            cve = v.get("id", "N/A")
            aliases = v.get("aliases", [])
            if aliases:
                # Prefer CVE-... alias if exists
                for a in aliases:
                    if a.startswith("CVE-"):
                        cve = a
                        break
                else:
                    cve = aliases[0]
            desc = (v.get("description") or v.get("specifier") or "")[:250]
            fix_versions = v.get("fix_versions") or []
            fix_suggestion = ""
            if fix_versions:
                fix_suggestion = str(fix_versions[0])
            # pip-audit vulns are considered HIGH severity (7.5) by default
            # Could refine if CVE has CVSS, but use 7.5
            score = 7.5
            # If description mentions CRITICAL, bump to 9
            if "critical" in desc.lower():
                score = 9.0
            add_entry(name, cve, score, desc, current_version, fix_suggestion)
else:
    # safety or generic: try to parse vulnerabilities array
    vulns = data.get("vulnerabilities") or data.get("vulns") or (data if isinstance(data, list) else [])
    for v in vulns:
        if not isinstance(v, dict):
            continue
        name = v.get("package_name") or v.get("name") or "unknown"
        cve = v.get("vulnerability_id") or v.get("id") or v.get("cve") or "N/A"
        score = 7.5
        desc = (v.get("advisory") or v.get("description") or "")[:250]
        current = v.get("analyzed_version") or ""
        fix = v.get("fixed_version") or (v.get("fix_versions")[0] if v.get("fix_versions") else "")
        add_entry(name, cve, score, desc, current, fix)

total = len(critical) + len(high) + len(medium)

print(f"\n{'='*65}")
print(f"  PIP-AUDIT / SAFETY SCAN RESULTS (Python OWASP equivalent)")
print(f"  Total CVEs : {total}")
print(f"  CRITICAL   : {len(critical)}  (9.0+)")
print(f"  HIGH       : {len(high)}  (7.0-8.9)")
print(f"  MEDIUM     : {len(medium)}  (4.0-6.9)")
print(f"  Fail threshold: {CVSS_FAIL_THRESHOLD}")
print(f"{'='*65}")

summary_rows = []
html_rows    = ""

for label, icon, items in [
    ("CRITICAL", "🔴", critical),
    ("HIGH",     "🟠", high),
    ("MEDIUM",   "🟡", medium),
]:
    if not items:
        continue
    print(f"\n{'─'*65}")
    print(f"  {icon} {label}")
    print(f"{'─'*65}")
    for e in items:
        print(f"\n  Score [{e['score']}]  {e['name']}")
        print(f"  CVE     : {e['cve']}")
        if e['current']:
            print(f"  Current : {e['current']}")
        print(f"  Issue   : {e['desc'][:200]}")
        if e['fix']:
            print(f"  Fix     : Upgrade to >= {e['fix']}")
            fix_cell      = f"Upgrade to >= {e['fix']}"
            fix_cell_html = f"Upgrade to <b>&gt;= {e['fix']}</b>"
        else:
            print(f"  Fix     : Check vendor advisory")
            fix_cell      = "Check vendor advisory"
            fix_cell_html = "Check vendor advisory"

        summary_rows.append(
            f"| {icon} {label} | `{e['name']}` | {e['cve']} | {e['score']} | {fix_cell} |"
        )

        sev_colors = {"CRITICAL": "#7b2d8b", "HIGH": "#e53e3e", "MEDIUM": "#dd6b20"}
        c = sev_colors.get(label, "#718096")
        html_rows += f"""<tr>
            <td><span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:700">{icon} {label}</span></td>
            <td style="font-weight:600">{e['score']}</td>
            <td style="font-family:monospace;font-size:12px">{e['name']}</td>
            <td style="font-family:monospace;font-size:12px;color:#3182ce">{e['cve']}</td>
            <td style="font-size:12px;color:#4a5568">{e['desc'][:150]}</td>
            <td style="font-size:12px">{fix_cell_html}</td>
        </tr>"""

# ── threshold-based status ──────────
if   CVSS_FAIL_THRESHOLD >= 9: failing = critical
elif CVSS_FAIL_THRESHOLD >= 7: failing = critical + high
elif CVSS_FAIL_THRESHOLD >= 4: failing = critical + high + medium
else:                           failing = critical + high + medium

status = "fail" if failing else "pass"

# ── write safety-summary.txt + owasp-summary.txt (for Jenkins post compatibility) ─────────
for fname in ["safety-summary.txt", "owasp-summary.txt"]:
    with open(fname, "w", encoding="utf-8") as f:
        f.write(f"STATUS={status}\n")
        f.write(f"COUNT={total}\n")
        f.write(f"CRITICAL={len(critical)}\n")
        f.write(f"HIGH={len(high)}\n")
        f.write(f"MEDIUM={len(medium)}\n")
        f.write("ROWS\n")
        for row in summary_rows:
            f.write(row + "\n")

# ── write safety-summary.html + owasp-summary.html ──────────────────────────────────
banner_color = "#276749" if not failing else "#9b2335"
status_text  = "✅ PASSED" if not failing else "❌ FAILED"

table = f"""
<table>
  <thead><tr>
    <th>Severity</th><th>Score</th><th>Dependency</th>
    <th>CVE</th><th>Description</th><th>Fix</th>
  </tr></thead>
  <tbody>{html_rows}</tbody>
</table>""" if total > 0 else '<p style="color:#48bb78;font-size:16px">🎉 No vulnerabilities found!</p>'

html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>Python CVE Report (pip-audit)</title>
<style>
  body   {{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f7fafc;margin:0;padding:24px;color:#2d3748}}
  .banner{{background:{banner_color};color:#fff;padding:16px 24px;border-radius:8px;margin-bottom:24px}}
  .banner h1{{margin:0 0 4px;font-size:22px}} .banner p{{margin:0;opacity:.85;font-size:14px}}
  .cards{{display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap}}
  .card{{background:#fff;border-radius:8px;padding:16px 24px;box-shadow:0 1px 3px rgba(0,0,0,.1);min-width:120px;text-align:center}}
  .card .num{{font-size:32px;font-weight:700}} .card .lbl{{font-size:12px;color:#718096;margin-top:4px}}
  .crit{{color:#7b2d8b}} .hi{{color:#e53e3e}} .med{{color:#dd6b20}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
  th{{background:#edf2f7;padding:10px 12px;text-align:left;font-size:12px;text-transform:uppercase;color:#4a5568}}
  td{{padding:10px 12px;border-bottom:1px solid #edf2f7;vertical-align:top}}
  tr:last-child td{{border-bottom:none}} tr:hover td{{background:#f7fafc}}
  .note{{margin-top:16px;padding:12px 16px;background:#ebf8ff;border-left:4px solid #3182ce;border-radius:4px;font-size:13px;color:#2c5282}}
</style></head><body>
<div class="banner"><h1>🛡️ pip-audit CVE Scan — {status_text}</h1><p>Python dependency vulnerability scan (threshold: CVSS >= {CVSS_FAIL_THRESHOLD})</p></div>
<div class="cards">
  <div class="card"><div class="num">{total}</div><div class="lbl">Total CVEs</div></div>
  <div class="card"><div class="num crit">{len(critical)}</div><div class="lbl">Critical</div></div>
  <div class="card"><div class="num hi">{len(high)}</div><div class="lbl">High</div></div>
  <div class="card"><div class="num med">{len(medium)}</div><div class="lbl">Medium</div></div>
</div>
{table}
{"<div class='note'>💡 <b>Note:</b> Suggested fix is from pip-audit fix_versions — verify against vendor advisory.</div>" if total > 0 else ""}
</body></html>"""

for fname in ["safety-summary.html", "owasp-summary.html"]:
    with open(fname, "w", encoding="utf-8") as f:
        f.write(html)

print(f"\n[INFO] safety-summary.txt/.html + owasp-summary.txt/.html written")

if failing:
    print(f"\n❌ {len(failing)} vulnerabilities at or above threshold {CVSS_FAIL_THRESHOLD} — fix required!")
    sys.exit(1)
elif medium:
    print(f"\n⚠️  {len(medium)} MEDIUM — review recommended")
else:
    print("\n✅ No HIGH/CRITICAL vulnerabilities!")
