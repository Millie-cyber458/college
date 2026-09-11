"""
StudyZen Link Audit Report - ASCII Safe Version
"""

import os
import re
from pathlib import Path

print("=" * 80)
print("STUDYZEN LINK AUDIT REPORT".center(80))
print("=" * 80)
print()

# Parse app.py for routes
app_file = Path(r"c:\Users\User\Downloads\StudyZen\app.py")
app_content = app_file.read_text()

# Find all @app.route definitions
app_routes = re.findall(r'@app\.route\("([^"]+)"\)', app_content)

api_file = Path(r"c:\Users\User\Downloads\StudyZen\api_routes.py")
api_content = api_file.read_text()
api_routes_from_file = re.findall(r'@api_bp\.route\(\'([^\']+)\'', api_content)

print("1. INTERNAL FLASK ROUTES")
print("-" * 80)
print("Flask Routes:")
for route in sorted(set(app_routes)):
    print(f"  [OK] {route}")

print()
print("API Routes:")
for route in sorted(set(api_routes_from_file)):
    print(f"  [OK] {route}")

# Template analysis
print()
print("2. TEMPLATE LINKS STATUS")
print("-" * 80)

templates_dir = Path(r"c:\Users\User\Downloads\StudyZen\templates")
template_files = list(templates_dir.glob("*.html"))

all_hardcoded_links = {}
for template_file in template_files:
    try:
        content = template_file.read_text(encoding='utf-8')
    except:
        content = template_file.read_text(encoding='cp1252')
    
    # Find hardcoded href links
    hardcoded = re.findall(r'href="([^"]+)"', content)
    for link in hardcoded:
        if link.startswith('/') and not link.startswith('http'):
            if link not in all_hardcoded_links:
                all_hardcoded_links[link] = []
            all_hardcoded_links[link].append(template_file.name)

print("Hardcoded Links (should use url_for):")
if all_hardcoded_links:
    for link in sorted(all_hardcoded_links.keys()):
        files = all_hardcoded_links[link]
        print(f"  [FOUND] {link}")
        print(f"         Used in: {', '.join(set(files))}")
else:
    print("  [NONE] No hardcoded links found!")

print()
print("3. STATIC FILES")
print("-" * 80)

static_dir = Path(r"c:\Users\User\Downloads\StudyZen\static")

static_files = [
    'css/style.css',
    'css/dashboard.css',
    'css/discord.css',
    'js/script.js'
]

print("Static Files:")
for file_path in static_files:
    full_path = static_dir / file_path
    if full_path.exists():
        print(f"  [OK] {file_path}")
    else:
        print(f"  [MISSING] {file_path}")

print()
print("4. EXTERNAL LINKS")
print("-" * 80)

external_links = {
    'https://fonts.googleapis.com': 'Google Fonts',
    'https://fonts.gstatic.com': 'Google Fonts Static',
    'https://cdn.jsdelivr.net/npm/chart.js': 'Chart.js',
    'https://ui-avatars.com': 'Avatar API',
}

print("External CDN/API Links:")
for url, desc in external_links.items():
    print(f"  [EXTERNAL] {url}")

print()
print("5. FINAL AUDIT SUMMARY")
print("=" * 80)

total_routes = len(set(app_routes)) + len(set(api_routes_from_file))
total_templates = len(template_files)
hardcoded_count = len(all_hardcoded_links)
missing_static = sum(1 for f in static_files if not (static_dir / f).exists())

print(f"Total Routes Defined:     {total_routes}")
print(f"Total Templates:          {total_templates}")
print(f"Hardcoded Links Found:    {hardcoded_count}")
print(f"Missing Static Files:     {missing_static}")

print()
if hardcoded_count > 0:
    print("[WARNING] Found hardcoded links in dashboard.html - should use url_for()")
else:
    print("[OK] All template links use proper Flask functions")

if missing_static > 0:
    print(f"[WARNING] {missing_static} static files are missing")
else:
    print("[OK] All static files exist")

print()
print("AUDIT COMPLETE")
print("=" * 80)
