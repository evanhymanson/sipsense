#!/usr/bin/env python3
"""Check Socrata API endpoints for liquor product datasets."""
import json
import sys
import urllib.request
import urllib.error

def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": str(e)}

def check_views_api(url, state_name):
    print(f"\n{'='*60}")
    print(f"STATE: {state_name}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    data = fetch_json(url)
    if isinstance(data, dict) and "error" in data:
        print(f"  ERROR: {data['error']}")
        return
    if not isinstance(data, list):
        print(f"  Unexpected response type: {type(data)}")
        print(f"  Content preview: {str(data)[:500]}")
        return
    if len(data) == 0:
        print("  No datasets found.")
        return
    print(f"  Found {len(data)} dataset(s):")
    for d in data:
        did = d.get('id', 'N/A')
        name = d.get('name', 'N/A')
        rows = d.get('rowCount', 'N/A')
        desc = str(d.get('description', ''))[:200]
        dtype = d.get('displayType', d.get('viewType', 'N/A'))
        cols = d.get('columns', [])
        col_names = [c.get('name', '') for c in cols if c.get('name')]
        print(f"\n  Dataset ID: {did}")
        print(f"  Name: {name}")
        print(f"  Type: {dtype}")
        print(f"  Rows: {rows}")
        print(f"  Description: {desc}")
        print(f"  Columns ({len(col_names)}): {col_names[:25]}")

def check_catalog_api(url, label):
    print(f"\n{'='*60}")
    print(f"CATALOG: {label}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    data = fetch_json(url)
    if isinstance(data, dict) and "error" in data:
        print(f"  ERROR: {data['error']}")
        return
    results = data.get('results', [])
    print(f"  Found {len(results)} result(s), total: {data.get('resultSetSize', 'N/A')}")
    for r in results:
        res = r.get('resource', {})
        meta = r.get('metadata', {})
        domain = meta.get('domain', 'N/A')
        rid = res.get('id', 'N/A')
        name = res.get('name', 'N/A')
        rtype = res.get('type', 'N/A')
        desc = str(res.get('description', ''))[:150]
        cols = res.get('columns_name', [])
        link = r.get('link', 'N/A')
        print(f"\n  Domain: {domain}, ID: {rid}")
        print(f"  Name: {name}")
        print(f"  Type: {rtype}")
        print(f"  Description: {desc}")
        print(f"  Columns: {cols[:15]}")
        print(f"  Link: {link}")

if __name__ == '__main__':
    # State-specific searches
    states = [
        ("https://data.nh.gov/api/views.json?q=liquor+products", "New Hampshire"),
        ("https://data.vermont.gov/api/views.json?q=liquor", "Vermont"),
        ("https://data.pa.gov/api/views.json?q=liquor", "Pennsylvania"),
        ("https://data.nc.gov/api/views.json?q=liquor", "North Carolina"),
        ("https://data.ohio.gov/api/views.json?q=liquor", "Ohio"),
        ("https://opendata.utah.gov/api/views.json?q=liquor", "Utah"),
        ("https://data.mn.gov/api/views.json?q=liquor", "Minnesota"),
        ("https://data.mass.gov/api/views.json?q=liquor", "Massachusetts"),
        ("https://data.maine.gov/api/views.json?q=liquor", "Maine"),
        ("https://data.idaho.gov/api/views.json?q=liquor", "Idaho"),
    ]

    for url, name in states:
        check_views_api(url, name)

    # Catalog searches
    catalogs = [
        ("https://api.us.socrata.com/api/catalog/v1?q=liquor%20products&limit=20", "liquor products"),
        ("https://api.us.socrata.com/api/catalog/v1?q=spirits%20price%20list&limit=20", "spirits price list"),
    ]

    for url, label in catalogs:
        check_catalog_api(url, label)
