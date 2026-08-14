#!/usr/bin/env python3
"""
Generates an interactive HTML line chart and growth dashboard showing the month-by-month
growth of Bill's photographic species life list since the first photo in November 2003.
"""

import os
import sys
import json
import importlib.util
from datetime import datetime
from collections import defaultdict

from lrcat_utils import open_catalog, make_relative_url

OUTPUT_HTML = "html/photo_lifelist_growth.html"

def fetch_data():
    spec = importlib.util.spec_from_file_location("clcp", "chronological-lifelist-custom-page.py")
    clcp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(clcp)

    print("Querying Lightroom for earliest published SmugMug photos...")
    with open_catalog() as cursor:
        photos = clcp.fetch_earliest_published_photos(cursor)

    species_list = []
    for k, v in photos.items():
        d = v.get("date")
        if d and d != "Unknown Date":
            species_list.append({
                "name": v["name"],
                "date": d,
                "location": v.get("location", "Unknown Location"),
                "url": v.get("url", ""),
                "photo_count": v.get("photo_count", 1)
            })

    species_list.sort(key=lambda x: (x["date"], x["name"]))
    return species_list

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
            --card-bg: #181b24;
            --card-border: #262b38;
            --text-main: #f0f3f8;
            --text-muted: #8e99ac;
            --accent-orange: #ff9f43;
            --accent-amber: #feca57;
            --accent-blue: #48dbfb;
            --accent-green: #1dd1a1;
            --accent-purple: #9b59b6;
            --chart-grid: #222736;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.6;
            padding: 40px 24px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            margin-bottom: 35px;
            border-bottom: 1px solid var(--card-border);
            padding-bottom: 25px;
        }}

        h1 {{
            font-size: 2.2rem;
            font-weight: 700;
            color: #fff;
            margin-bottom: 8px;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}

        .subtitle {{
            color: var(--text-muted);
            font-size: 1.05rem;
        }}

        /* Stat Cards */
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 18px;
            margin-bottom: 30px;
        }}

        .stat-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 20px;
            position: relative;
            overflow: hidden;
            box-shadow: 0 4px 12px rgba(0,0,0,0.25);
        }}

        .stat-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: var(--accent-orange);
        }}

        .stat-card.blue::before {{ background: var(--accent-blue); }}
        .stat-card.green::before {{ background: var(--accent-green); }}
        .stat-card.purple::before {{ background: var(--accent-purple); }}

        .stat-label {{
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            color: var(--text-muted);
            margin-bottom: 6px;
        }}

        .stat-value {{
            font-size: 2rem;
            font-weight: 700;
            color: #fff;
            line-height: 1.2;
        }}

        .stat-desc {{
            font-size: 0.85rem;
            color: var(--text-muted);
            margin-top: 6px;
        }}

        /* Chart Section */
        .chart-section {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 24px;
            margin-bottom: 35px;
            box-shadow: 0 6px 18px rgba(0,0,0,0.3);
        }}

        .chart-header {{
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            gap: 15px;
        }}

        .chart-title {{
            font-size: 1.3rem;
            font-weight: 600;
            color: #fff;
        }}

        .chart-controls {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}

        .btn {{
            background: #252a38;
            color: var(--text-muted);
            border: 1px solid var(--card-border);
            padding: 7px 14px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .btn:hover {{
            background: #2d3345;
            color: #fff;
        }}

        .btn.active {{
            background: var(--accent-orange);
            color: #0f1117;
            border-color: var(--accent-orange);
            font-weight: 600;
        }}

        .chart-wrapper {{
            position: relative;
            height: 480px;
            width: 100%;
        }}

        /* Top Surge Months & Milestones Grid */
        .details-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
            gap: 25px;
            margin-bottom: 35px;
        }}

        .section-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 22px;
        }}

        .section-title {{
            font-size: 1.15rem;
            font-weight: 600;
            color: #fff;
            margin-bottom: 16px;
            border-bottom: 1px solid var(--card-border);
            padding-bottom: 10px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        /* Table & Lists */
        .surge-list, .milestone-list {{
            list-style: none;
        }}

        .surge-item, .milestone-item {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 11px 0;
            border-bottom: 1px solid #202430;
            font-size: 0.95rem;
        }}

        .surge-item:last-child, .milestone-item:last-child {{
            border-bottom: none;
        }}

        .badge {{
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
        }}

        .badge-orange {{ background: rgba(255, 159, 67, 0.15); color: var(--accent-orange); border: 1px solid rgba(255, 159, 67, 0.3); }}
        .badge-blue {{ background: rgba(72, 219, 251, 0.15); color: var(--accent-blue); border: 1px solid rgba(72, 219, 251, 0.3); }}
        .badge-green {{ background: rgba(29, 209, 161, 0.15); color: var(--accent-green); border: 1px solid rgba(29, 209, 161, 0.3); }}
        
        .item-main {{
            display: flex;
            flex-direction: column;
            gap: 2px;
        }}

        .item-title {{
            font-weight: 500;
            color: #fff;
        }}

        .item-sub {{
            font-size: 0.8rem;
            color: var(--text-muted);
        }}

        .item-right {{
            text-align: right;
        }}

        footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 0.85rem;
            margin-top: 50px;
            border-top: 1px solid var(--card-border);
            padding-top: 20px;
        }}

        a {{
            color: var(--accent-orange);
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📈 Photographic Species Life List Growth</h1>
            <p class="subtitle">Monthly cumulative progress of Bill Walker's bird photography life list (November 2003 – Present)</p>
        </header>

        <!-- Stats Overview -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Photo Life List</div>
                <div class="stat-value">{summary['total_species']}</div>
                <div class="stat-desc">Published species photographed</div>
            </div>

            <div class="stat-card blue">
                <div class="stat-label">First Photo Date</div>
                <div class="stat-value" style="font-size: 1.35rem; margin-top: 4px;">{summary['first_photo']['date']}</div>
                <div class="stat-desc">{summary['first_photo']['name']} ({summary['first_photo']['location']})</div>
            </div>

            <div class="stat-card green">
                <div class="stat-label">Latest Photo Date</div>
                <div class="stat-value" style="font-size: 1.35rem; margin-top: 4px;">{summary['latest_photo']['date']}</div>
                <div class="stat-desc">{summary['latest_photo']['name']}</div>
            </div>

            <div class="stat-card purple">
                <div class="stat-label">Active Timeline</div>
                <div class="stat-value" style="font-size: 1.5rem; margin-top: 3px;">{round(summary['total_months'] / 12, 1)} yrs</div>
                <div class="stat-desc">{summary['total_months']} total months (~{round(summary['total_species'] / (summary['total_months'] / 12), 1)} species/yr)</div>
            </div>
        </div>

        <!-- Main Chart -->
        <div class="chart-section">
            <div class="chart-header">
                <div class="chart-title">Month-by-Month Cumulative Growth & Additions</div>
                <div class="chart-controls">
                    <button class="btn active" id="btn-cumulative" onclick="setChartMode('both')">Cumulative & Monthly</button>
                    <button class="btn" id="btn-cum-only" onclick="setChartMode('cumulative')">Cumulative Only</button>
                    <button class="btn" id="btn-monthly-only" onclick="setChartMode('monthly')">Monthly Additions Only</button>
                    <span style="border-left: 1px solid var(--card-border); margin: 0 4px;"></span>
                    <button class="btn active" id="btn-all" onclick="setTimeRange('all')">All Time</button>
                    <button class="btn" id="btn-10y" onclick="setTimeRange(10)">Last 10Y</button>
                    <button class="btn" id="btn-5y" onclick="setTimeRange(5)">Last 5Y</button>
                </div>
            </div>
            <div class="chart-wrapper">
                <canvas id="growthChart"></canvas>
            </div>
        </div>

        <!-- Details Grid -->
        <div class="details-grid">
            <!-- Top Surge Months -->
            <div class="section-card">
                <div class="section-title">
                    <span>🚀 Top Birding Surge Months</span>
                    <span class="badge badge-orange">Highest Additions</span>
                </div>
                <ul class="surge-list" id="surge-list-container">
                    <!-- Populated by JS -->
                </ul>
            </div>

            <!-- Key Milestones -->
            <div class="section-card">
                <div class="section-title">
                    <span>🏆 Milestone Species</span>
                    <span class="badge badge-green">Timeline</span>
                </div>
                <ul class="milestone-list" id="milestone-list-container">
                    <!-- Populated by JS -->
                </ul>
            </div>
        </div>

        <footer>
            <p>Data dynamically extracted from <a href="file://{os.path.abspath('lrcat_utils.py')}">Lightroom Catalog</a>. View full indexes in <a href="chronological_life_list.html">Chronological Life List</a> or <a href="taxonomic_life_list.html">Taxonomic Life List</a>.</p>
        </footer>
    </div>

    <script>
        const rawTimeline = {timeline_json};
        const summaryData = {summary_json};

        let currentRange = 'all';
        let currentMode = 'both';
        let chartInstance = null;

        function getFilteredData() {{
            if (currentRange === 'all') return rawTimeline;
            const monthsCount = currentRange * 12;
            return rawTimeline.slice(-monthsCount);
        }}

        function initChart() {{
            const ctx = document.getElementById('growthChart').getContext('2d');
            const data = getFilteredData();

            const labels = data.map(d => d.label);
            const cumulativeData = data.map(d => d.cumulative);
            const monthlyData = data.map(d => d.new_count);

            const gradient = ctx.createLinearGradient(0, 0, 0, 450);
            gradient.addColorStop(0, 'rgba(255, 159, 67, 0.45)');
            gradient.addColorStop(1, 'rgba(255, 159, 67, 0.0)');

            const datasets = [];

            if (currentMode === 'both' || currentMode === 'cumulative') {{
                datasets.push({{
                    type: 'line',
                    label: 'Cumulative Species',
                    data: cumulativeData,
                    borderColor: '#ff9f43',
                    backgroundColor: gradient,
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.25,
                    pointRadius: data.length > 120 ? 0 : 2,
                    pointHoverRadius: 6,
                    pointBackgroundColor: '#ff9f43',
                    yAxisID: 'y'
                }});
            }}

            if (currentMode === 'both' || currentMode === 'monthly') {{
                datasets.push({{
                    type: 'bar',
                    label: 'New Species Added',
                    data: monthlyData,
                    backgroundColor: 'rgba(72, 219, 251, 0.65)',
                    hoverBackgroundColor: '#48dbfb',
                    borderRadius: 3,
                    yAxisID: currentMode === 'both' ? 'y1' : 'y'
                }});
            }}

            const scales = {{
                x: {{
                    grid: {{ color: '#222736' }},
                    ticks: {{ 
                        color: '#8e99ac',
                        maxRotation: 45,
                        autoSkip: true,
                        maxTicksLimit: 20
                    }}
                }},
                y: {{
                    position: 'left',
                    grid: {{ color: '#222736' }},
                    ticks: {{ color: '#8e99ac' }},
                    title: {{
                        display: true,
                        text: 'Cumulative Species Total',
                        color: '#8e99ac'
                    }}
                }}
            }};

            if (currentMode === 'both') {{
                scales.y1 = {{
                    position: 'right',
                    grid: {{ drawOnChartArea: false }},
                    ticks: {{ color: '#48dbfb' }},
                    title: {{
                        display: true,
                        text: 'New Species / Month',
                        color: '#48dbfb'
                    }}
                }};
            }}

            chartInstance = new Chart(ctx, {{
                data: {{ labels, datasets }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {{
                        mode: 'index',
                        intersect: false
                    }},
                    plugins: {{
                        legend: {{
                            labels: {{ color: '#f0f3f8', font: {{ size: 12 }} }}
                        }},
                        tooltip: {{
                            backgroundColor: 'rgba(24, 27, 36, 0.95)',
                            titleColor: '#fff',
                            bodyColor: '#f0f3f8',
                            borderColor: '#384152',
                            borderWidth: 1,
                            padding: 12,
                            boxPadding: 6,
                            callbacks: {{
                                afterBody: function(context) {{
                                    const idx = context[0].dataIndex;
                                    const item = getFilteredData()[idx];
                                    if (item.new_count > 0) {{
                                        const names = item.species_names;
                                        const preview = names.slice(0, 5).join(', ');
                                        const extra = names.length > 5 ? ` +${{names.length - 5}} more` : '';
                                        return `\\nAdded in this month:\\n• ${{preview}}${{extra}}`;
                                    }}
                                    return '';
                                }}
                            }}
                        }}
                    }},
                    scales: scales
                }}
            }});
        }}

        function setTimeRange(range) {{
            currentRange = range;
            document.querySelectorAll('.chart-controls button[id^="btn-"]').forEach(btn => {{
                if (['btn-all', 'btn-10y', 'btn-5y'].includes(btn.id)) {{
                    btn.classList.remove('active');
                }}
            }});
            if (range === 'all') document.getElementById('btn-all').classList.add('active');
            if (range === 10) document.getElementById('btn-10y').classList.add('active');
            if (range === 5) document.getElementById('btn-5y').classList.add('active');

            if (chartInstance) chartInstance.destroy();
            initChart();
        }}

        function setChartMode(mode) {{
            currentMode = mode;
            document.querySelectorAll('.chart-controls button[id^="btn-"]').forEach(btn => {{
                if (['btn-cumulative', 'btn-cum-only', 'btn-monthly-only'].includes(btn.id)) {{
                    btn.classList.remove('active');
                }}
            }});
            if (mode === 'both') document.getElementById('btn-cumulative').classList.add('active');
            if (mode === 'cumulative') document.getElementById('btn-cum-only').classList.add('active');
            if (mode === 'monthly') document.getElementById('btn-monthly-only').classList.add('active');

            if (chartInstance) chartInstance.destroy();
            initChart();
        }}

        function populateDetails() {{
            // Top Surges
            const topSurges = [...rawTimeline].sort((a, b) => b.new_count - a.new_count).slice(0, 10);
            const sortedSurges = topSurges.sort((a, b) => b.month.localeCompare(a.month));
            const surgeContainer = document.getElementById('surge-list-container');
            surgeContainer.innerHTML = sortedSurges.map((s, idx) => {{
                let tripHtml = '';
                if (s.trips && s.trips.length > 0) {{
                    tripHtml = `<span class="item-sub" style="color: var(--accent-blue); font-weight: 500; margin-top: 3.5px;">✈️ ${{s.trips.join(', ')}}</span>`;
                }} else if (s.locations && s.locations.length > 0) {{
                    tripHtml = `<span class="item-sub" style="color: var(--accent-green); margin-top: 3.5px;">📍 ${{s.locations.slice(0, 1).join(', ')}}</span>`;
                }}
                return `
                    <li class="surge-item">
                        <div class="item-main">
                            <span class="item-title">${{s.label}}</span>
                            <span class="item-sub">${{s.species_names.slice(0, 3).join(', ')}}${{s.species_names.length > 3 ? '...' : ''}}</span>
                            ${{tripHtml}}
                        </div>
                        <div class="item-right">
                            <span class="badge badge-orange">+${{s.new_count}} species</span>
                            <div class="item-sub" style="margin-top: 2px;">Total: ${{s.cumulative}}</div>
                        </div>
                    </li>
                `;
            }}).join('');

            // Milestones
            const milestoneContainer = document.getElementById('milestone-list-container');
            const keyMilestones = summaryData.milestones.filter(m => m.milestone % 100 === 0);
            milestoneContainer.innerHTML = keyMilestones.map(m => `
                <li class="milestone-item">
                    <div class="item-main">
                        <span class="item-title">${{m.species}}</span>
                        <span class="item-sub">${{m.location}} (${{m.date}})</span>
                    </div>
                    <div class="item-right">
                        <span class="badge badge-green">#${{m.milestone}}</span>
                    </div>
                </li>
            `).join('');
        }}

        document.addEventListener('DOMContentLoaded', () => {{
            initChart();
            populateDetails();
        }});
    </script>
</body>
</html>
"""
    return html

def main():
    os.makedirs(os.path.dirname(OUTPUT_HTML), exist_ok=True)
    species_list = fetch_data()
    summary, timeline = process_timeline(species_list)
    html_content = build_html(summary, timeline)

    with open(OUTPUT_HTML, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n✅ Interactive growth chart HTML generated successfully at:")
    print(f"   [html/photo_lifelist_growth.html](file://{os.path.abspath(OUTPUT_HTML)})")

if __name__ == "__main__":
    main()
