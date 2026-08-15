import os
import json
from datetime import datetime
from collections import defaultdict
from lib.lrcat_utils import make_relative_url

def process_timeline(species_list):
    if not species_list:
        return {}, []

    first_date = species_list[0]["date"]
    last_date = species_list[-1]["date"]

    start_dt = datetime.strptime(first_date[:7], "%Y-%m")
    end_dt = datetime.strptime(last_date[:7], "%Y-%m")

    # Group species by month
    monthly_new = defaultdict(list)
    for sp in species_list:
        m = sp["date"][:7]
        monthly_new[m].append(sp)

    # Build continuous month list
    all_months = []
    cur = start_dt
    while cur <= end_dt:
        all_months.append(cur.strftime("%Y-%m"))
        year = cur.year + (cur.month // 12)
        month = (cur.month % 12) + 1
        cur = datetime(year, month, 1)

    cumulative = 0
    timeline = []
    # Ensure targets include every multiple of 100 up to the list length
    milestone_targets = [1] + list(range(100, len(species_list) + 1, 100)) + [len(species_list)]
    milestone_targets = sorted(list(set(milestone_targets)))
    milestones_achieved = {}

    for m in all_months:
        new_sp = monthly_new[m]
        prev_cum = cumulative
        cumulative += len(new_sp)
        
        # Check for milestones crossed in this month
        month_milestones = []
        for mt in milestone_targets:
            if mt not in milestones_achieved and cumulative >= mt:
                # Find the exact species that was milestone #mt
                sp_idx = mt - 1
                if sp_idx < len(species_list):
                    milestone_sp = species_list[sp_idx]
                    milestones_achieved[mt] = {
                        "milestone": mt,
                        "species": milestone_sp["name"],
                        "date": milestone_sp["date"],
                        "location": milestone_sp["location"],
                        "month": m
                    }
                    month_milestones.append(milestones_achieved[mt])

        # Determine trips and locations for new_sp in this month
        trip_counts = defaultdict(int)
        location_counts = defaultdict(int)
        
        for sp in new_sp:
            url = sp.get("url", "")
            rel_url = make_relative_url(url)
            if rel_url.startswith("/Trips/"):
                parts = rel_url.split("/")
                if len(parts) >= 3:
                    trip_name = parts[2]
                    # Prettify trip name, e.g. "Costa-Rica-2012" -> "Costa Rica 2012"
                    trip_name_pretty = trip_name.replace("-", " ")
                    trip_counts[trip_name_pretty] += 1
            
            loc = sp.get("location", "")
            if loc and loc != "Unknown Location" and "Lightroom Capture" not in loc and "Auto selected" not in loc:
                location_counts[loc] += 1
                
        # Sort and select top trip(s)
        sorted_trips = sorted(trip_counts.items(), key=lambda x: x[1], reverse=True)
        top_trips = [t[0] for t in sorted_trips if t[1] >= 2]
        if not top_trips and sorted_trips:
            top_trips = [sorted_trips[0][0]]
            
        # Sort and select top location(s)
        sorted_locs = sorted(location_counts.items(), key=lambda x: x[1], reverse=True)
        top_locations = [l[0] for l in sorted_locs[:2]]

        # Pretty month label: e.g. "Feb 2012"
        dt_obj = datetime.strptime(m, "%Y-%m")
        label = dt_obj.strftime("%b %Y")

        timeline.append({
            "month": m,
            "label": label,
            "year": dt_obj.year,
            "new_count": len(new_sp),
            "cumulative": cumulative,
            "species_names": [s["name"] for s in new_sp],
            "milestones": month_milestones,
            "trips": top_trips,
            "locations": top_locations
        })

    return {
        "total_species": len(species_list),
        "first_photo": species_list[0],
        "latest_photo": species_list[-1],
        "total_months": len(all_months),
        "milestones": list(milestones_achieved.values())
    }, timeline

def build_html(summary, timeline):
    timeline_json = json.dumps(timeline)
    summary_json = json.dumps(summary)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Photographic Species Life List Growth</title>
    <!-- Chart.js and date adapter via CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
    <style>
        :root {{
            --bg-color: #0f1117;
            --card-bg: #161a25;
            --text-color: #e2e8f0;
            --text-muted: #8e99ac;
            --primary: #ff9f43;
            --primary-glow: rgba(255, 159, 67, 0.15);
            --border-color: #262b38;
            --accent: #feca57;
        }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-color);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 30px;
            min-height: 100vh;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}

        h1 {{
            margin: 0;
            font-size: 2.2em;
            background: linear-gradient(135deg, #fff 0%, #a5b1c2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .total-badge {{
            background: var(--primary-glow);
            color: var(--primary);
            border: 1px solid rgba(255, 159, 67, 0.3);
            padding: 8px 18px;
            border-radius: 30px;
            font-size: 1.2em;
            font-weight: bold;
        }}

        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .stat-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}

        .stat-card h3 {{
            margin: 0 0 10px 0;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
        }}

        .stat-card .value {{
            font-size: 1.8em;
            font-weight: bold;
            color: #fff;
        }}

        .stat-card .desc {{
            font-size: 0.85em;
            color: var(--text-muted);
            margin: 8px 0 0 0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}

        .chart-container {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 40px;
            box-shadow: 0 6px 18px rgba(0,0,0,0.15);
            position: relative;
        }}

        .interactive-section {{
            display: grid;
            grid-template-columns: 1fr 400px;
            gap: 30px;
            align-items: start;
        }}

        @media (max-width: 1000px) {{
            .interactive-section {{
                grid-template-columns: 1fr;
            }}
        }}

        .month-detail-panel {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 6px 18px rgba(0,0,0,0.15);
            position: sticky;
            top: 30px;
            min-height: 480px;
            display: flex;
            flex-direction: column;
        }}

        .panel-header {{
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}

        .panel-header h2 {{
            margin: 0;
            font-size: 1.6em;
            color: #fff;
        }}

        .panel-header .subtitle {{
            color: var(--text-muted);
            font-size: 0.9em;
            margin-top: 5px;
        }}

        .panel-stat-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 20px;
        }}

        .panel-stat-box {{
            background-color: rgba(255,255,255,0.03);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 12px;
            text-align: center;
        }}

        .panel-stat-box .lbl {{
            font-size: 0.8em;
            text-transform: uppercase;
            color: var(--text-muted);
            margin-bottom: 5px;
        }}

        .panel-stat-box .val {{
            font-size: 1.4em;
            font-weight: bold;
            color: var(--primary);
        }}

        .species-list-container {{
            flex-grow: 1;
            overflow-y: auto;
            max-height: 250px;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            background-color: rgba(0,0,0,0.2);
            padding: 10px 15px;
        }}

        .species-list-container h4 {{
            margin: 0 0 10px 0;
            font-size: 0.9em;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .species-list-container ul {{
            margin: 0;
            padding: 0;
            list-style: none;
        }}

        .species-list-container li {{
            padding: 6px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-size: 0.95em;
        }}

        .species-list-container li:last-child {{
            border-bottom: none;
        }}

        .species-list-container li a {{
            color: #4db8ff;
            text-decoration: none;
        }}

        .species-list-container li a:hover {{
            text-decoration: underline;
        }}

        .milestone-badge {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(254, 202, 87, 0.12);
            color: var(--accent);
            border: 1px solid rgba(254, 202, 87, 0.3);
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
            text-transform: uppercase;
            margin-left: 8px;
        }}

        .milestone-alert {{
            background: linear-gradient(135deg, rgba(255,159,67,0.15) 0%, rgba(254,202,87,0.05) 100%);
            border: 1px solid rgba(255,159,67,0.3);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 15px;
        }}

        .milestone-alert .medal {{
            font-size: 2.2em;
        }}

        .milestone-alert .msg {{
            font-size: 0.95em;
            line-height: 1.4;
        }}

        .milestone-alert strong {{
            color: var(--accent);
        }}

        .trip-tag {{
            display: inline-block;
            background-color: rgba(77, 184, 255, 0.1);
            color: #4db8ff;
            border: 1px solid rgba(77, 184, 255, 0.25);
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>Photo Life List Growth Timeline</h1>
                <p style="margin: 5px 0 0 0; color: var(--text-muted);">Historical growth tracking of unique photographed bird species.</p>
            </div>
            <div class="total-badge">{summary["total_species"]} Species</div>
        </header>

        <div class="stat-grid">
            <div class="stat-card">
                <h3>First Published Photo</h3>
                <div class="value" style="font-size: 1.5em; color: var(--primary);">{summary["first_photo"]["name"]}</div>
                <div class="desc">{summary["first_photo"]["date"]} @ {summary["first_photo"]["location"]}</div>
            </div>
            <div class="stat-card">
                <h3>Latest Published Photo</h3>
                <div class="value" style="font-size: 1.5em; color: #2ed573;">{summary["latest_photo"]["name"]}</div>
                <div class="desc">{summary["latest_photo"]["date"]} @ {summary["latest_photo"]["location"]}</div>
            </div>
            <div class="stat-card">
                <h3>Span of Lifelist</h3>
                <div class="value">{round(summary["total_months"]/12, 1)} Years</div>
                <div class="desc">Active over {summary["total_months"]} continuous months</div>
            </div>
            <div class="stat-card">
                <h3>Average Growth</h3>
                <div class="value">{round(summary["total_species"]/summary["total_months"], 1)} / mo</div>
                <div class="desc">New species added per month average</div>
            </div>
        </div>

        <div class="chart-container">
            <canvas id="growthChart" style="width: 100%; height: 350px;"></canvas>
        </div>

        <div class="interactive-section">
            <div class="chart-container" style="padding: 20px; min-height: 480px; margin-bottom: 0;">
                <h3 style="margin-top:0; border-bottom: 1px solid var(--border-color); padding-bottom:10px;">🏆 Lifelist Milestones</h3>
                <div id="milestones-timeline-list" style="display: flex; flex-direction: column; gap: 15px; max-height: 430px; overflow-y: auto; padding-right: 10px;">
                    <!-- Milestone Cards will render here -->
                </div>
            </div>

            <div class="month-detail-panel" id="detail-panel">
                <div class="panel-header">
                    <h2 id="panel-month-label">Select a Month</h2>
                    <div class="subtitle" id="panel-month-sub">Click on any point in the chart to inspect details</div>
                </div>
                <div id="panel-content-body" style="display: none; flex-direction: column; flex-grow: 1;">
                    <div class="panel-stat-row">
                        <div class="panel-stat-box">
                            <div class="lbl">New Species</div>
                            <div class="val" id="panel-new-count">0</div>
                        </div>
                        <div class="panel-stat-box">
                            <div class="lbl">Total Species</div>
                            <div class="val" id="panel-cum-count">0</div>
                        </div>
                    </div>
                    
                    <div id="panel-milestone-container"></div>
                    <div id="panel-trip-container" style="margin-bottom: 20px;"></div>

                    <div class="species-list-container">
                        <h4 id="panel-list-header">Species Added</h4>
                        <ul id="panel-species-list">
                            <!-- Species list here -->
                        </ul>
                    </div>
                </div>
                <div id="panel-placeholder" style="flex-grow: 1; display: flex; align-items: center; justify-content: center; color: var(--text-muted); font-style: italic; text-align: center;">
                    Click a point along the chart line above to see which new species were added, milestones crossed, and trips taken in that month.
                </div>
            </div>
        </div>
    </div>

    <script>
        const rawTimeline = {timeline_json};
        const rawSummary = {summary_json};

        // Prepare chart data
        const labels = rawTimeline.map(item => item.label);
        const cumulativeData = rawTimeline.map(item => item.cumulative);
        const monthlyData = rawTimeline.map(item => item.new_count);

        // Chart implementation
        const ctx = document.getElementById('growthChart').getContext('2d');
        
        // Define gradient
        const chartGrad = ctx.createLinearGradient(0, 0, 0, 300);
        chartGrad.addColorStop(0, 'rgba(255, 159, 67, 0.4)');
        chartGrad.addColorStop(1, 'rgba(255, 159, 67, 0.0)');

        const growthChart = new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [
                    {{
                        label: 'Total Species (Cumulative)',
                        data: cumulativeData,
                        borderColor: '#ff9f43',
                        borderWidth: 3,
                        pointBackgroundColor: '#ff9f43',
                        pointBorderColor: '#0f1117',
                        pointBorderWidth: 1.5,
                        pointRadius: function(context) {{
                            const idx = context.dataIndex;
                            if (idx === undefined || idx < 0) return 2;
                            const item = rawTimeline[idx];
                            return (item.milestones && item.milestones.length > 0) ? 6 : 2;
                        }},
                        pointHoverRadius: 8,
                        pointHitRadius: 10,
                        fill: true,
                        backgroundColor: chartGrad,
                        tension: 0.1,
                        yAxisID: 'y'
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                onClick: (event, activeElements) => {{
                    if (activeElements && activeElements.length > 0) {{
                        const idx = activeElements[0].index;
                        showMonthDetails(idx);
                    }}
                }},
                plugins: {{
                    legend: {{
                        display: false
                    }},
                    tooltip: {{
                        backgroundColor: '#161a25',
                        titleColor: '#fff',
                        bodyColor: '#e2e8f0',
                        borderColor: '#262b38',
                        borderWidth: 1,
                        padding: 12,
                        callbacks: {{
                            title: function(context) {{
                                return rawTimeline[context[0].dataIndex].label;
                            }},
                            label: function(context) {{
                                const idx = context.dataIndex;
                                const item = rawTimeline[idx];
                                let lines = [`Total: ${{context.raw}} species`];
                                if (item.new_count > 0) {{
                                    lines.push(`Added +${{item.new_count}} in this month`);
                                }}
                                if (item.milestones && item.milestones.length > 0) {{
                                    item.milestones.forEach(m => {{
                                        lines.push(`🏆 MILESTONE: #${{m.milestone}}!`);
                                    }});
                                }}
                                return lines;
                            }}
                        }}
                    }}
                }},
                scales: {{
                    x: {{
                        grid: {{
                            color: '#222736',
                            drawOnChartArea: true
                        }},
                        ticks: {{
                            color: '#8e99ac',
                            maxTicksLimit: 20
                        }}
                    }},
                    y: {{
                        grid: {{
                            color: '#222736',
                            drawOnChartArea: true
                        }},
                        ticks: {{
                            color: '#8e99ac'
                        }},
                        position: 'left'
                    }}
                }}
            }}
        }});

        // Sidebar detail management
        function showMonthDetails(idx) {{
            const item = rawTimeline[idx];
            
            document.getElementById('panel-placeholder').style.display = 'none';
            document.getElementById('panel-content-body').style.display = 'flex';

            document.getElementById('panel-month-label').innerText = item.label;
            document.getElementById('panel-month-sub').innerText = `Growth summary for month`;
            document.getElementById('panel-new-count').innerText = `+${{item.new_count}}`;
            document.getElementById('panel-cum-count').innerText = item.cumulative;

            // Milestones
            const milestoneContainer = document.getElementById('panel-milestone-container');
            milestoneContainer.innerHTML = '';
            if (item.milestones && item.milestones.length > 0) {{
                item.milestones.forEach(m => {{
                    milestoneContainer.innerHTML += `
                        <div class="milestone-alert">
                            <div class="medal">🏆</div>
                            <div class="msg">
                                Crossed Milestone <strong>#${{m.milestone}}</strong>!<br/>
                                <strong>${{m.species}}</strong> on ${{m.date}} at ${{m.location}}
                            </div>
                        </div>
                    `;
                }});
            }}

            // Trip details
            const tripContainer = document.getElementById('panel-trip-container');
            tripContainer.innerHTML = '';
            if (item.trips && item.trips.length > 0) {{
                tripContainer.innerHTML += `<h5>🚗 Associated Trips / Galleries:</h5>`;
                item.trips.forEach(t => {{
                    tripContainer.innerHTML += `<span class="trip-tag" style="margin-right: 6px;">${{t}}</span>`;
                }});
            }}

            // Species list
            const listHeader = document.getElementById('panel-list-header');
            const speciesList = document.getElementById('panel-species-list');
            speciesList.innerHTML = '';
            if (item.species_names && item.species_names.length > 0) {{
                listHeader.innerText = `Species Added (${{item.new_count}})`;
                item.species_names.forEach(name => {{
                    const url_name = name.replace(" ", "+");
                    speciesList.innerHTML += `<li><a href="/search/?q=${{url_name}}" target="_blank">${{name}}</a></li>`;
                }});
            }} else {{
                listHeader.innerText = 'Species Added';
                speciesList.innerHTML = '<li style="color: var(--text-muted); font-style: italic;">No new species photographed this month</li>';
            }}
        }}

        // Populate Milestone Timeline
        function initMilestones() {{
            const list = document.getElementById('milestones-timeline-list');
            const highlightMilestones = [1, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, rawSummary.total_species];
            const uniqueHighlights = [...new Set(highlightMilestones)].sort((a,b) => a-b);
            
            rawSummary.milestones.forEach(m => {{
                if (uniqueHighlights.includes(m.milestone)) {{
                    const card = document.createElement('div');
                    card.className = 'stat-card';
                    card.style.cursor = 'pointer';
                    card.style.borderColor = 'rgba(255,159,67,0.3)';
                    card.style.position = 'relative';
                    card.onclick = () => {{
                        // Find matching index in rawTimeline
                        const tIdx = rawTimeline.findIndex(t => t.month === m.month);
                        if (tIdx !== -1) {{
                            showMonthDetails(tIdx);
                            // Highlight the element in chart
                            growthChart.setActiveElements([{{ datasetIndex: 0, index: tIdx }}]);
                            growthChart.update();
                        }}
                    }};

                    card.innerHTML = `
                        <div class="value" style="font-size: 1.3em; color: var(--accent); display: flex; align-items: center; justify-content: space-between;">
                            <span>#${{m.milestone}} Sighting</span>
                            <span style="font-size: 0.7em; color: var(--text-muted); font-weight: normal;">${{m.month}}</span>
                        </div>
                        <div class="value" style="font-size: 1.15em; color: #fff; margin-top: 5px;">${{m.species}}</div>
                        <div class="desc" style="font-size: 0.8em; margin-top: 4px;">Captured ${{m.date}} @ ${{m.location}}</div>
                    `;
                    list.appendChild(card);
                }}
            }});
        }}

        initMilestones();
    </script>
</body>
</html>
"""
    return html

def build_svg(summary, timeline):
    max_species = summary["total_species"]
    max_y = ((max_species + 199) // 200) * 200
    
    # Grid lines (horizontal)
    grid_lines = []
    for val in range(0, max_y + 1, 200):
        y_pos = 420 - val * (380 / max_y)
        grid_lines.append(f'  <line x1="60" y1="{y_pos:.1f}" x2="920" y2="{y_pos:.1f}" stroke="#262b38" stroke-dasharray="3,3" />')
        grid_lines.append(f'  <text x="50" y="{y_pos+4:.1f}" fill="#8e99ac" font-size="12" text-anchor="end" font-family="sans-serif">{val}</text>')
        
    # Year labels (vertical)
    timeline_len = len(timeline)
    denom = (timeline_len - 1) if timeline_len > 1 else 1

    year_markers = []
    seen_years = set()
    for i, entry in enumerate(timeline):
        y = entry["year"]
        if y % 2 == 0 and y not in seen_years:
            seen_years.add(y)
            x_pos = 60 + i * (860 / denom)
            year_markers.append(f'  <line x1="{x_pos:.1f}" y1="40" x2="{x_pos:.1f}" y2="420" stroke="#222736" />')
            year_markers.append(f'  <text x="{x_pos:.1f}" y="440" fill="#8e99ac" font-size="11" text-anchor="middle" font-family="sans-serif">{y}</text>')

    # Path points
    points = []
    for i, entry in enumerate(timeline):
        x = 60 + i * (860 / denom)
        y = 420 - entry["cumulative"] * (380 / max_y)
        points.append(f"{x:.1f} {y:.1f}")
        
    path_d = "M " + " L ".join(points)
    area_d = f"{path_d} L 920.0 420 L 60.0 420 Z"
    
    # Milestones
    milestone_dots = []
    month_to_idx = {entry["month"]: idx for idx, entry in enumerate(timeline)}
    highlight_milestones = list(range(100, max_species + 1, 100))
    for m in summary["milestones"]:
        if m["milestone"] in highlight_milestones:
            idx = month_to_idx.get(m["month"])
            if idx is not None:
                x = 60 + idx * (860 / denom)
                y = 420 - m["milestone"] * (380 / max_y)
                milestone_dots.append(f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="4.5" fill="#ff9f43" stroke="#0f1117" stroke-width="1.5" />')
                milestone_dots.append(f'  <text x="{x-8:.1f}" y="{y-10:.1f}" fill="#feca57" font-size="10" font-weight="bold" font-family="sans-serif" text-anchor="end">{m["milestone"]}</text>')

    grid_lines_str = "\n".join(grid_lines)
    year_markers_str = "\n".join(year_markers)
    milestone_dots_str = "\n".join(milestone_dots)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 480" width="100%" height="100%" style="background-color: #0f1117; border-radius: 12px;">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#ff9f43" stop-opacity="0.4" />
      <stop offset="100%" stop-color="#ff9f43" stop-opacity="0.0" />
    </linearGradient>
  </defs>
  
  <!-- Title -->
  <text x="60" y="25" fill="#ffffff" font-size="16" font-weight="bold" font-family="sans-serif">Photographic Species Life List Growth ({timeline[0]["year"]} - {timeline[-1]["year"]})</text>
  <text x="920" y="25" fill="#ff9f43" font-size="14" font-weight="bold" text-anchor="end" font-family="sans-serif">Total: {max_species} Species</text>

  <!-- Grids -->
{grid_lines_str}
{year_markers_str}

  <!-- Area & Line -->
  <path d="{area_d}" fill="url(#grad)" />
  <path d="{path_d}" fill="none" stroke="#ff9f43" stroke-width="3" stroke-linecap="round" />

  <!-- Milestone dots -->
{milestone_dots_str}
</svg>
"""
    return svg
