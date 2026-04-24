"""
html_dashboard.py
Generates a polished, self-contained HTML ATS score report.
No external dependencies – pure HTML/CSS/JS embedded.
"""

import json


def generate_html(result: dict) -> str:
    meta       = result["metadata"]
    composite  = result["composite_score"]
    verdict    = result["verdict"]
    components = result["components"]
    weights    = result["weights_used"]
    explanation= result["explanation"]
    gaps       = result["gaps"]

    candidate  = meta["candidate_name"]
    jd_title   = meta["jd_title"]
    role_type  = meta["role_type"]
    scored_at  = meta["scored_at"]

    verdict_color = verdict["color"]
    verdict_label = verdict["label"]
    verdict_icon  = verdict["icon"]

    # ── Component rows ────────────────────────────────────────────────────────
    comp_rows = ""
    comp_chart_data = []
    comp_colors = ["#6366f1","#06b6d4","#10b981","#f59e0b"]
    color_idx   = 0

    for key, comp in components.items():
        label    = explanation["component_summaries"][key]["label"]
        score    = comp["score"]
        weight   = weights.get(key, 0)
        contrib  = round(score * weight, 1)
        avail    = comp["data_available"]
        note     = explanation["component_summaries"][key]["note"]
        bar_color= comp_colors[color_idx % len(comp_colors)]
        color_idx+= 1

        bar_pct = score
        avail_badge = (
            '<span class="badge badge-ok">Data OK</span>'
            if avail else
            '<span class="badge badge-warn">No Data</span>'
        )

        missing = ", ".join(comp.get("missing_fields", [])) or "—"

        comp_rows += f"""
        <tr>
          <td class="comp-label">{label}</td>
          <td>
            <div class="bar-wrap">
              <div class="bar-fill" style="width:{bar_pct:.1f}%;background:{bar_color}">
                <span class="bar-label">{score:.1f}</span>
              </div>
            </div>
          </td>
          <td class="center">{weight:.0%}</td>
          <td class="center"><b>{contrib:.1f}</b></td>
          <td class="center">{avail_badge}</td>
          <td class="note-cell">{note}</td>
        </tr>"""

        comp_chart_data.append({
            "label": label, "score": score,
            "color": bar_color, "weight": weight
        })

    # ── Gap rows ──────────────────────────────────────────────────────────────
    gap_rows = ""
    severity_colors = {"critical":"#ef4444","missing":"#f97316","moderate":"#f59e0b","low":"#6b7280"}
    for g in gaps:
        sev_color = severity_colors.get(g["severity"], "#6b7280")
        gap_rows += f"""
        <tr>
          <td>{g['section'].replace('_',' ').title()}</td>
          <td class="center">{g['score']:.1f}</td>
          <td><span class="sev-badge" style="background:{sev_color}">{g['severity'].upper()}</span></td>
          <td>{g['recommendation']}</td>
        </tr>"""

    if not gap_rows:
        gap_rows = '<tr><td colspan="4" class="center muted">No critical gaps detected.</td></tr>'

    # ── Tips ──────────────────────────────────────────────────────────────────
    tips_html = ""
    for tip in explanation["improvement_tips"]:
        tips_html += f"""
        <div class="tip-card">
          <div class="tip-num">#{tip['priority']}</div>
          <div>
            <div class="tip-area">{tip['area']} — current: {tip['current_score']:.1f}/100</div>
            <div class="tip-text">{tip['tip']}</div>
          </div>
        </div>"""

    # ── Breakdown JSON for collapsible ────────────────────────────────────────
    breakdown_json = json.dumps(
        {k: v["breakdown"] for k, v in components.items()},
        indent=2
    )

    # ── Gauge arc ─────────────────────────────────────────────────────────────
    # SVG semi-circle gauge: 0-100 mapped to 0-180 degrees
    angle = composite * 1.8  # degrees
    import math
    rad   = math.radians(angle - 90)
    cx, cy, r = 110, 100, 80
    px = cx + r * math.cos(math.radians(angle - 180))
    py = cy + r * math.sin(math.radians(angle - 180))
    large = 1 if angle > 180 else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ATS Score – {candidate}</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root{{
    --bg:#0f1117;--surface:#1a1d27;--surface2:#21253a;--border:#2a2f45;
    --text:#e8eaf6;--muted:#7b82a8;--accent:#6366f1;--accent2:#06b6d4;
    --ok:#10b981;--warn:#f59e0b;--err:#ef4444;
    --verdict:{verdict_color};
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);
        min-height:100vh;padding:2rem 1.5rem}}
  h1,h2,h3{{font-weight:600;letter-spacing:-.02em}}
  .page{{max-width:1100px;margin:0 auto}}

  /* Header */
  .header{{display:flex;align-items:flex-start;justify-content:space-between;
           flex-wrap:wrap;gap:1.5rem;margin-bottom:2.5rem}}
  .header-left h1{{font-size:1.6rem;color:var(--text)}}
  .header-left .subtitle{{color:var(--muted);font-size:.9rem;margin-top:.3rem}}
  .meta-chips{{display:flex;flex-wrap:wrap;gap:.5rem;margin-top:.8rem}}
  .chip{{background:var(--surface2);border:1px solid var(--border);border-radius:20px;
         padding:.25rem .75rem;font-size:.78rem;color:var(--muted)}}
  .chip b{{color:var(--text)}}

  /* Verdict badge */
  .verdict-box{{background:var(--surface);border:2px solid var(--verdict);
               border-radius:12px;padding:1rem 1.5rem;text-align:center;
               min-width:160px}}
  .verdict-icon{{font-size:2rem}}
  .verdict-label{{font-size:1rem;font-weight:700;color:var(--verdict);margin-top:.3rem}}
  .verdict-score{{font-size:2.8rem;font-weight:700;color:var(--verdict);
                  font-family:'DM Mono',monospace;line-height:1}}
  .verdict-max{{font-size:.9rem;color:var(--muted)}}

  /* Gauge */
  .gauge-wrap{{background:var(--surface);border:1px solid var(--border);
               border-radius:12px;padding:1.5rem;display:flex;
               flex-direction:column;align-items:center}}
  .gauge-wrap h3{{color:var(--muted);font-size:.8rem;text-transform:uppercase;
                  letter-spacing:.1em;margin-bottom:1rem}}

  /* Grid layout */
  .top-grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1.5rem;margin-bottom:2rem}}
  @media(max-width:800px){{.top-grid{{grid-template-columns:1fr 1fr}}}}
  @media(max-width:500px){{.top-grid{{grid-template-columns:1fr}}}}

  .summary-card{{background:var(--surface);border:1px solid var(--border);
                 border-radius:12px;padding:1.25rem}}
  .summary-card h3{{font-size:.75rem;text-transform:uppercase;letter-spacing:.1em;
                    color:var(--muted);margin-bottom:.5rem}}
  .summary-card .big{{font-size:2rem;font-weight:700;font-family:'DM Mono',monospace}}
  .summary-card .sub{{font-size:.82rem;color:var(--muted);margin-top:.25rem}}

  /* Section */
  .section{{background:var(--surface);border:1px solid var(--border);
            border-radius:12px;padding:1.5rem;margin-bottom:1.5rem}}
  .section h2{{font-size:1rem;color:var(--text);margin-bottom:1.25rem;
               display:flex;align-items:center;gap:.5rem}}
  .section-icon{{color:var(--accent);font-size:1.1rem}}

  /* Table */
  table{{width:100%;border-collapse:collapse;font-size:.87rem}}
  th{{text-align:left;color:var(--muted);font-size:.75rem;text-transform:uppercase;
      letter-spacing:.08em;padding:.5rem .75rem;border-bottom:1px solid var(--border)}}
  td{{padding:.6rem .75rem;border-bottom:1px solid var(--border);vertical-align:middle}}
  tr:last-child td{{border-bottom:none}}
  .center{{text-align:center}}
  .muted{{color:var(--muted)}}

  /* Bar */
  .bar-wrap{{background:var(--surface2);border-radius:4px;height:22px;
             position:relative;overflow:hidden;min-width:120px}}
  .bar-fill{{height:100%;border-radius:4px;display:flex;align-items:center;
             transition:width .6s ease;min-width:30px;position:relative}}
  .bar-label{{position:absolute;right:6px;font-size:.78rem;font-weight:600;
              color:#fff;font-family:'DM Mono',monospace}}
  .comp-label{{font-weight:500;min-width:150px}}
  .note-cell{{color:var(--muted);font-size:.82rem;max-width:280px}}

  /* Badges */
  .badge{{border-radius:4px;padding:.15rem .5rem;font-size:.72rem;font-weight:600}}
  .badge-ok{{background:rgba(16,185,129,.15);color:#10b981}}
  .badge-warn{{background:rgba(245,158,11,.15);color:#f59e0b}}
  .sev-badge{{border-radius:4px;padding:.2rem .5rem;font-size:.72rem;
              font-weight:700;color:#fff}}

  /* Tips */
  .tip-card{{display:flex;gap:1rem;align-items:flex-start;padding:.9rem;
             background:var(--surface2);border-radius:8px;margin-bottom:.6rem;
             border-left:3px solid var(--accent)}}
  .tip-num{{font-size:1.2rem;font-weight:700;color:var(--accent);font-family:'DM Mono',monospace;
            min-width:30px}}
  .tip-area{{font-weight:600;font-size:.88rem;color:var(--text);margin-bottom:.25rem}}
  .tip-text{{font-size:.83rem;color:var(--muted)}}

  /* Formula */
  .formula-box{{background:var(--surface2);border-radius:8px;padding:1rem 1.25rem;
                font-family:'DM Mono',monospace;font-size:.82rem;color:var(--accent2);
                overflow-x:auto;white-space:pre-wrap;word-break:break-all}}

  /* Summary text */
  .summary-text{{background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.2);
                 border-radius:8px;padding:1rem;font-size:.9rem;line-height:1.6;
                 color:var(--text)}}

  /* Collapsible */
  details summary{{cursor:pointer;color:var(--muted);font-size:.82rem;
                   padding:.4rem 0;list-style:none;user-select:none}}
  details summary::before{{content:"▶ ";font-size:.7rem}}
  details[open] summary::before{{content:"▼ ";}}
  pre{{background:var(--surface2);border-radius:6px;padding:.75rem;
       font-size:.76rem;overflow-x:auto;color:var(--accent2);margin-top:.5rem}}

  .footer{{text-align:center;color:var(--muted);font-size:.78rem;margin-top:2.5rem;
            padding-top:1rem;border-top:1px solid var(--border)}}
</style>
</head>
<body>
<div class="page">

  <!-- HEADER -->
  <div class="header">
    <div class="header-left">
      <h1>ATS Candidate Score Report</h1>
      <div class="subtitle">Transparent, explainable candidate-JD alignment</div>
      <div class="meta-chips">
        <span class="chip">👤 <b>{candidate}</b></span>
        <span class="chip">📋 <b>{jd_title}</b></span>
        <span class="chip">🏷️ Role Type: <b>{role_type}</b></span>
        <span class="chip">🕒 {scored_at[:10]}</span>
      </div>
    </div>
    <div class="verdict-box">
      <div class="verdict-icon">{verdict_icon}</div>
      <div class="verdict-score">{composite:.1f}</div>
      <div class="verdict-max">/100</div>
      <div class="verdict-label">{verdict_label}</div>
    </div>
  </div>

  <!-- TOP CARDS -->
  <div class="top-grid">
    <div class="summary-card">
      <h3>Composite Score</h3>
      <div class="big" style="color:var(--verdict)">{composite:.1f}</div>
      <div class="sub">{verdict_icon} {verdict_label}</div>
    </div>
    <div class="summary-card">
      <h3>Components Scored</h3>
      <div class="big" style="color:var(--accent2)">{len(components)}</div>
      <div class="sub">of 4 dimensions</div>
    </div>
    <div class="summary-card">
      <h3>Critical Gaps</h3>
      <div class="big" style="color:var(--warn)">{sum(1 for g in gaps if g.get('severity') in ['critical','missing'])}</div>
      <div class="sub">require immediate action</div>
    </div>
  </div>

  <!-- SUMMARY -->
  <div class="section">
    <h2><span class="section-icon">💡</span>Score Summary</h2>
    <div class="summary-text">{explanation['summary_text']}</div>
  </div>

  <!-- COMPONENT SCORES -->
  <div class="section">
    <h2><span class="section-icon">📊</span>Component Score Breakdown</h2>
    <table>
      <thead>
        <tr>
          <th>Component</th>
          <th>Score (0–100)</th>
          <th class="center">Weight</th>
          <th class="center">Contribution</th>
          <th class="center">Status</th>
          <th>Explanation</th>
        </tr>
      </thead>
      <tbody>{comp_rows}</tbody>
    </table>
  </div>

  <!-- FORMULA -->
  <div class="section">
    <h2><span class="section-icon">🧮</span>Scoring Formula</h2>
    <div class="formula-box">{explanation['scoring_formula']}</div>
    <p style="margin-top:.75rem;font-size:.82rem;color:var(--muted)">
      Weights are role-specific. Final composite = weighted sum of component scores ÷ total weight.
    </p>
  </div>

  <!-- GAPS -->
  <div class="section">
    <h2><span class="section-icon">⚠️</span>Identified Gaps</h2>
    <table>
      <thead>
        <tr><th>Section</th><th class="center">Score</th><th>Severity</th><th>Recommendation</th></tr>
      </thead>
      <tbody>{gap_rows}</tbody>
    </table>
  </div>

  <!-- IMPROVEMENT TIPS -->
  <div class="section">
    <h2><span class="section-icon">🚀</span>Top Improvement Actions</h2>
    {tips_html}
  </div>

  <!-- RAW BREAKDOWN (collapsible) -->
  <div class="section">
    <h2><span class="section-icon">🔍</span>Raw Score Breakdown</h2>
    <details>
      <summary>Show detailed breakdown JSON</summary>
      <pre>{breakdown_json}</pre>
    </details>
  </div>

  <div class="footer">
    Generated by ATS Scoring Engine · Day 13 · {scored_at[:19].replace('T',' ')} UTC
  </div>
</div>
</body>
</html>"""

    return html
