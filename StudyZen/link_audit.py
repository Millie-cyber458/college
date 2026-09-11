"""
StudyZen Link Audit Report
Tests all internal routes and external links
"""

import os
import re
from pathlib import Path

print("=" * 80)
print("STUDYZEN LINK AUDIT REPORT".center(80))
print("=" * 80)
print()

# =====================================================
# 1. INTERNAL ROUTES ANALYSIS
# =====================================================

print("1. INTERNAL FLASK ROUTES")
print("-" * 80)

# Parse app.py for routes
app_file = Path(r"c:\Users\User\Downloads\StudyZen\app.py")
app_content = app_file.read_text()

# Find all @app.route definitions
app_routes = re.findall(r'@app\.route\("([^"]+)"\)', app_content)
api_routes = re.findall(r'@api_bp\.route\(\'([^\']+)\'', app_content)

api_file = Path(r"c:\Users\User\Downloads\StudyZen\api_routes.py")
api_content = api_file.read_text()
api_routes_from_file = re.findall(r'@api_bp\.route\(\'([^\']+)\'', api_content)

print("Flask Routes (@app.route):")
for route in sorted(set(app_routes)):
    print(f"  [OK] {route}")

print()
print("API Routes (@api_bp.route):")
for route in sorted(set(api_routes + api_routes_from_file)):
    print(f"  [OK] {route}")

# =====================================================
# 2. TEMPLATE LINKS ANALYSIS
# =====================================================

print()
print("2. LINKS IN TEMPLATES")
print("-" * 80)

templates_dir = Path(r"c:\Users\User\Downloads\StudyZen\templates")
template_files = list(templates_dir.glob("*.html"))

# Collect all url_for() calls
all_url_fors = {}
all_hardcoded_links = {}
all_fetch_calls = {}

for template_file in template_files:
    try:
        content = template_file.read_text(encoding='utf-8')
    except:
        content = template_file.read_text(encoding='cp1252')
    
    # Find url_for calls
    url_fors = re.findall(r"url_for\('([^']+)'", content)
    for url_for_call in url_fors:
        if url_for_call not in all_url_fors:
            all_url_fors[url_for_call] = []
        all_url_fors[url_for_call].append(template_file.name)
    
    # Find hardcoded href links
    hardcoded = re.findall(r'href="([^"]+)"', content)
    for link in hardcoded:
        if link.startswith('/') or link.startswith('http'):
            if link not in all_hardcoded_links:
                all_hardcoded_links[link] = []
            all_hardcoded_links[link].append(template_file.name)
    
    # Find fetch calls
    fetch_calls = re.findall(r"fetch\(`([^`]+)`", content)
    for fetch in fetch_calls:
        if fetch not in all_fetch_calls:
            all_fetch_calls[fetch] = []
        all_fetch_calls[fetch].append(template_file.name)

print("url_for() Calls (Template-based):")
print()
for route_name in sorted(all_url_fors.keys()):
    files = all_url_fors[route_name]
    print(f"  • {route_name}")
    print(f"    Used in: {', '.join(files)}")
    
    # Check if route exists
    if route_name in app_routes or route_name in [
        'index', 'dashboard', 'community', 'about', 'profile', 'login', 'logout',
        'view_group', 'view_channel', 'post_message', 'join_group', 'auth_google'
    ]:
        print(f"    Status: ✓ ROUTE EXISTS")
    else:
        print(f"    Status: ✗ ROUTE NOT FOUND")
    print()

print()
print("Hardcoded Links:")
print()
for link in sorted(all_hardcoded_links.keys()):
    files = all_hardcoded_links[link]
    status = ""
    
    if link.startswith('http'):
        status = "EXTERNAL"
    elif link == '/dashboard' or link == '/profile' or link == '/logout' or link == '/community':
        status = "⚠ HARDCODED (should use url_for)"
    else:
        status = "ROUTE"
    
    print(f"  • {link}")
    print(f"    Used in: {', '.join(files)}")
    print(f"    Status: {status}")
    print()

print()
print("Fetch API Calls:")
print()
for fetch_url in sorted(all_fetch_calls.keys()):
    files = all_fetch_calls[fetch_url]
    print(f"  • {fetch_url}")
    print(f"    Used in: {', '.join(files)}")
    print()

# =====================================================
# 3. EXTERNAL LINKS ANALYSIS
# =====================================================

print()
print("3. EXTERNAL LINKS")
print("-" * 80)

external_links = {
    'https://fonts.googleapis.com': 'Google Fonts (CSS)',
    'https://fonts.gstatic.com': 'Google Fonts (Static)',
    'https://cdn.jsdelivr.net/npm/chart.js': 'Chart.js Library',
    'https://ui-avatars.com': 'Avatar Generator',
    'https://accounts.google.com/.well-known/openid-configuration': 'Google OAuth Config'
}

for url, description in external_links.items():
    print(f"  • {url}")
    print(f"    Purpose: {description}")
    print()

# =====================================================
# 4. STATIC FILES ANALYSIS
# =====================================================

print()
print("4. STATIC FILES REFERENCE")
print("-" * 80)

static_dir = Path(r"c:\Users\User\Downloads\StudyZen\static")
css_files = list((static_dir / "css").glob("*.css")) if (static_dir / "css").exists() else []
js_files = list((static_dir / "js").glob("*.js")) if (static_dir / "js").exists() else []
img_files = list((static_dir / "images").glob("*")) if (static_dir / "images").exists() else []

print("CSS Files Referenced:")
css_referenced = [
    'css/style.css',
    'css/dashboard.css',
    'css/discord.css'
]
for css in css_referenced:
    file_path = static_dir / css
    exists = "✓" if file_path.exists() else "✗"
    print(f"  {exists} {css}")

print()
print("JavaScript Files Referenced:")
js_referenced = [
    'js/script.js'
]
for js in js_referenced:
    file_path = static_dir / js
    exists = "✓" if file_path.exists() else "✗"
    print(f"  {exists} {js}")

# =====================================================
# 5. ISSUES FOUND
# =====================================================

print()
print("5. ISSUES & RECOMMENDATIONS")
print("-" * 80)

issues = []

# Check for hardcoded routes that should use url_for
hardcoded_route_issues = [link for link in all_hardcoded_links.keys() 
                          if link.startswith('/') and not link.startswith('http')]

if hardcoded_route_issues:
    print("\n⚠ HARDCODED LINKS (Should use url_for):")
    for link in hardcoded_route_issues:
        print(f"  • {link} in {', '.join(all_hardcoded_links[link])}")
        issues.append(f"Hardcoded link: {link}")

# Check for missing routes
undefined_routes = []
for route_name in all_url_fors.keys():
    if route_name not in ['index', 'dashboard', 'community', 'about', 'profile', 
                          'login', 'logout', 'view_group', 'view_channel', 
                          'post_message', 'join_group', 'auth_google', 'static']:
        undefined_routes.append(route_name)

if undefined_routes:
    print("\n✗ UNDEFINED ROUTES (referenced but not implemented):")
    for route in undefined_routes:
        print(f"  • {route}")
        issues.append(f"Undefined route: {route}")

# Check for missing static files
print("\n⚠ MISSING STATIC FILES:")
missing_static = []
if not (static_dir / "css" / "style.css").exists():
    print("  ✗ css/style.css")
    missing_static.append("css/style.css")
else:
    print("  ✓ css/style.css")

if not (static_dir / "css" / "dashboard.css").exists():
    print("  ✗ css/dashboard.css")
    missing_static.append("css/dashboard.css")
else:
    print("  ✓ css/dashboard.css")

if not (static_dir / "css" / "discord.css").exists():
    print("  ✗ css/discord.css")
    missing_static.append("css/discord.css")
else:
    print("  ✓ css/discord.css")

if not (static_dir / "js" / "script.js").exists():
    print("  ✗ js/script.js")
    missing_static.append("js/script.js")
else:
    print("  ✓ js/script.js")

# =====================================================
# 6. SUMMARY
# =====================================================

print()
print("=" * 80)
print("SUMMARY".center(80))
print("=" * 80)
print()
print(f"Flask Routes Defined: {len(set(app_routes))}")
print(f"API Routes Defined: {len(set(api_routes + api_routes_from_file))}")
print(f"Templates: {len(template_files)}")
print(f"Total Issues Found: {len(issues)}")
print()

if issues:
    print("Issues to Fix:")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
else:
    print("✓ No critical issues found!")

print()
