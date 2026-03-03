"""Output formatters: human-readable, JSON, SARIF 2.1.0, and HTML report."""
from __future__ import annotations

import html as html_mod
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


# ═══════════════════════════════════════════════════════════════════════════════
# Human-readable
# ═══════════════════════════════════════════════════════════════════════════════

def emit_human(results: Dict[str, Any]) -> str:
    """Return a human-readable report string."""
    lines: List[str] = []
    a = lines.append

    a("")
    a("=" * 80)
    a("CODE QUALITY ANALYSIS REPORT")
    a("=" * 80)
    a(f"Target:         {results['target_path']}")
    a(f"Timestamp:      {results['timestamp']}")
    a(f"Files analysed: {results['summary']['total_files']}")
    a(f"Total issues:   {results['summary']['total_issues']}")
    a(f"  Critical: {results['summary']['critical_issues']}")
    a(f"  Warnings: {results['summary']['warning_issues']}")
    a(f"  Info:     {results['summary']['info_issues']}")

    issues = results.get("issues", [])
    if not issues:
        a("\n✅ No issues found! Your code looks clean!")
        return "\n".join(lines)

    a("")
    a("-" * 80)
    a("DETAILED ISSUES:")
    a("-" * 80)

    by_file: Dict[str, List[Dict[str, Any]]] = {}
    for issue in issues:
        by_file.setdefault(issue["file"], []).append(issue)

    severity_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}

    for file_path, file_issues in by_file.items():
        a(f"\n📁 {file_path}")
        for iss in file_issues:
            icon = severity_icon.get(iss["severity"], "⚪")
            a(f"  {icon} Line {iss['line']}: {iss['message']}")
            if iss.get("suggestion"):
                a(f"     💡 Suggestion: {iss['suggestion']}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# JSON
# ═══════════════════════════════════════════════════════════════════════════════

def emit_json(results: Dict[str, Any]) -> str:
    """Return canonical JSON string."""
    return json.dumps(results, indent=2, sort_keys=False, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════════
# SARIF 2.1.0  (GitHub Code Scanning / VS Code compatible)
# ═══════════════════════════════════════════════════════════════════════════════

_SARIF_SEVERITY_MAP = {
    "critical": "error",
    "warning": "warning",
    "info": "note",
}

def emit_sarif(results: Dict[str, Any]) -> str:
    """Return a SARIF 2.1.0 JSON string."""
    rules: Dict[str, Dict[str, Any]] = {}
    sarif_results: List[Dict[str, Any]] = []

    for issue in results.get("issues", []):
        rule_id = issue.get("check", "unknown")
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "shortDescription": {"text": rule_id},
                "defaultConfiguration": {
                    "level": _SARIF_SEVERITY_MAP.get(issue.get("severity", "info"), "note")
                },
            }

        result_obj: Dict[str, Any] = {
            "ruleId": rule_id,
            "level": _SARIF_SEVERITY_MAP.get(issue.get("severity", "info"), "note"),
            "message": {"text": issue.get("message", "")},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": issue.get("file", "").replace("\\", "/"),
                        },
                        "region": {
                            "startLine": issue.get("line", 1),
                        },
                    }
                }
            ],
        }
        if issue.get("suggestion"):
            result_obj["fixes"] = [
                {
                    "description": {"text": issue["suggestion"]},
                }
            ]
        sarif_results.append(result_obj)

    sarif: Dict[str, Any] = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "CodeQualityAnalyzer",
                        "version": "2.0.0",
                        "informationUri": "https://github.com/your-org/code-quality-analyzer",
                        "rules": list(rules.values()),
                    }
                },
                "results": sarif_results,
            }
        ],
    }
    return json.dumps(sarif, indent=2, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════════
# HTML report  (self-contained, no external deps)
# ═══════════════════════════════════════════════════════════════════════════════

def _svg_pie(critical: int, warning: int, info: int, size: int = 200) -> str:
    """Return an inline SVG pie chart for severity distribution."""
    total = critical + warning + info
    if total == 0:
        return '<svg width="200" height="200"></svg>'

    colours = [("#e74c3c", critical), ("#f39c12", warning), ("#3498db", info)]
    r = size // 2
    cx = cy = r
    slices: List[str] = []
    start_angle = -90.0  # start at top

    for colour, count in colours:
        if count == 0:
            continue
        sweep = (count / total) * 360.0
        end_angle = start_angle + sweep
        large = 1 if sweep > 180 else 0

        sx = cx + r * math.cos(math.radians(start_angle))
        sy = cy + r * math.sin(math.radians(start_angle))
        ex = cx + r * math.cos(math.radians(end_angle))
        ey = cy + r * math.sin(math.radians(end_angle))

        if abs(sweep - 360.0) < 0.01:
            # Full circle – draw two half-arcs
            mx = cx + r * math.cos(math.radians(start_angle + 180))
            my = cy + r * math.sin(math.radians(start_angle + 180))
            slices.append(
                f'<path d="M {cx},{cy} L {sx:.1f},{sy:.1f} '
                f'A {r},{r} 0 0 1 {mx:.1f},{my:.1f} '
                f'A {r},{r} 0 0 1 {sx:.1f},{sy:.1f} Z" fill="{colour}"/>'
            )
        else:
            slices.append(
                f'<path d="M {cx},{cy} L {sx:.1f},{sy:.1f} '
                f'A {r},{r} 0 {large} 1 {ex:.1f},{ey:.1f} Z" fill="{colour}"/>'
            )
        start_angle = end_angle

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">'
        + "".join(slices)
        + "</svg>"
    )


def emit_html(results: Dict[str, Any], output_path: Path) -> None:
    """Write a self-contained HTML report to *output_path*."""
    s = results["summary"]
    pie = _svg_pie(s["critical_issues"], s["warning_issues"], s["info_issues"])

    sev_class = {"critical": "sev-critical", "warning": "sev-warning", "info": "sev-info"}

    rows: List[str] = []
    for iss in results.get("issues", []):
        cls = sev_class.get(iss["severity"], "")
        rows.append(
            f'<tr class="{cls}">'
            f'<td>{html_mod.escape(iss["severity"])}</td>'
            f'<td>{html_mod.escape(iss["file"])}</td>'
            f'<td>{iss["line"]}</td>'
            f'<td>{html_mod.escape(iss["check"])}</td>'
            f'<td>{html_mod.escape(iss["message"])}</td>'
            f'<td>{html_mod.escape(iss.get("suggestion", ""))}</td>'
            f"</tr>"
        )

    # Group by file for hotspot section
    by_file: Dict[str, int] = {}
    for iss in results.get("issues", []):
        by_file[iss["file"]] = by_file.get(iss["file"], 0) + 1
    hotspot_rows = sorted(by_file.items(), key=lambda x: x[1], reverse=True)[:10]
    hotspot_html = "".join(
        f"<tr><td>{html_mod.escape(f)}</td><td>{c}</td></tr>" for f, c in hotspot_rows
    )

    page = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Code Quality Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         margin: 2em; background: #fafafa; color: #333; }}
  h1 {{ border-bottom: 2px solid #333; padding-bottom: .3em; }}
  .summary {{ display: flex; gap: 2em; align-items: center; margin: 1em 0; }}
  .stat {{ padding: .5em 1em; border-radius: .4em; text-align: center; }}
  .stat b {{ display: block; font-size: 2em; }}
  .stat-critical {{ background: #fce4e4; color: #c0392b; }}
  .stat-warning  {{ background: #fef5e7; color: #e67e22; }}
  .stat-info     {{ background: #eaf2f8; color: #2980b9; }}
  table {{ border-collapse: collapse; width: 100%; margin-top: 1em; }}
  th, td {{ text-align: left; padding: .4em .6em; border-bottom: 1px solid #ddd; font-size: .9em; }}
  th {{ background: #ecf0f1; position: sticky; top: 0; }}
  .sev-critical td:first-child {{ color: #c0392b; font-weight: bold; }}
  .sev-warning  td:first-child {{ color: #e67e22; }}
  .sev-info     td:first-child {{ color: #2980b9; }}
  .hotspot {{ max-width: 500px; }}
</style>
</head>
<body>
<h1>Code Quality Report</h1>
<p><b>Target:</b> {html_mod.escape(results['target_path'])}<br/>
   <b>Timestamp:</b> {html_mod.escape(results['timestamp'])}<br/>
   <b>Files analysed:</b> {s['total_files']}</p>

<div class="summary">
  <div class="stat stat-critical"><b>{s['critical_issues']}</b>Critical</div>
  <div class="stat stat-warning"><b>{s['warning_issues']}</b>Warnings</div>
  <div class="stat stat-info"><b>{s['info_issues']}</b>Info</div>
  {pie}
</div>

<h2>Hotspot Files (most issues)</h2>
<table class="hotspot">
<tr><th>File</th><th>Issues</th></tr>
{hotspot_html}
</table>

<h2>All Issues ({s['total_issues']})</h2>
<table>
<tr><th>Severity</th><th>File</th><th>Line</th><th>Check</th><th>Message</th><th>Suggestion</th></tr>
{"".join(rows)}
</table>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(page, encoding="utf-8")
