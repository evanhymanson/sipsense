#!/usr/bin/env python3
"""Check Socrata endpoints via subprocess curl to avoid SSL issues."""
import json
import subprocess
import sys

def curl_json(url, timeout=15):
    """Fetch JSON via curl subprocess."""
    try:
        result = subprocess.run(
            ['curl', '-s', '-w', '\n___HTTP_CODE___%{http_code}', '--max-time', str(timeout), url],
            capture_output=True, text=True, timeout=timeout+5
        )
        output = result.stdout
        # Split off HTTP code
        if '___HTTP_CODE___' in output:
            parts = output.rsplit('___HTTP_CODE___', 1)
            body = parts[0].strip()
            code = parts[1].strip()
        else:
            body = output.strip()
            code = '???'

        if not body:
            return None, f"Empty response (HTTP {code})"
        if code == '403':
            return None, f"403 Forbidden (blocked by WAF/CDN)"
        if code == '000':
            return None, f"Connection failed (DNS/timeout)"
        if not code.startswith('2'):
            return None, f"HTTP {code}: {body[:200]}"

        try:
            data = json.loads(body)
            return data, None
        except json.JSONDecodeError as e:
            return None, f"Invalid JSON (HTTP {code}): {str(e)}: {body[:200]}"
    except subprocess.TimeoutExpired:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)


def check_views(url, state):
    print(f"\n{'='*70}")
    print(f"  {state}")
    print(f"  {url}")
    print(f"{'='*70}")
    data, err = curl_json(url)
    if err:
        print(f"  FAILED: {err}")
        return []

    if isinstance(data, dict):
        # Some return a single object or error
        if 'error' in data:
            print(f"  API Error: {data.get('message', data.get('error'))}")
            return []
        print(f"  Unexpected dict response: {str(data)[:300]}")
        return []

    if not isinstance(data, list):
        print(f"  Unexpected type: {type(data)}")
        return []

    if len(data) == 0:
        print("  No datasets found.")
        return []

    print(f"  Found {len(data)} dataset(s):\n")
    product_datasets = []
    for d in data:
        did = d.get('id', 'N/A')
        name = d.get('name', 'N/A')
        rows = d.get('rowCount', 'N/A')
        desc = str(d.get('description', ''))[:300]
        dtype = d.get('displayType', d.get('viewType', 'N/A'))
        cols = d.get('columns', [])
        col_names = [c.get('name', '') for c in cols if c.get('name')]

        print(f"  [{did}] {name}")
        print(f"    Type: {dtype}, Rows: {rows}")
        print(f"    Desc: {desc}")
        print(f"    Columns ({len(col_names)}): {col_names[:25]}")
        print()

        # Check if it's a product catalog
        name_lower = name.lower()
        desc_lower = desc.lower()
        is_product = any(kw in name_lower or kw in desc_lower for kw in
            ['product', 'price list', 'catalog', 'item', 'spirits', 'beverage', 'brand'])
        if is_product:
            product_datasets.append((did, name, rows, col_names, state))

    return product_datasets


def check_catalog(url, label):
    print(f"\n{'='*70}")
    print(f"  CATALOG SEARCH: {label}")
    print(f"  {url}")
    print(f"{'='*70}")
    data, err = curl_json(url)
    if err:
        print(f"  FAILED: {err}")
        return []

    results = data.get('results', [])
    total = data.get('resultSetSize', 'N/A')
    print(f"  Total matches: {total}, showing {len(results)}\n")

    product_datasets = []
    for r in results:
        res = r.get('resource', {})
        meta = r.get('metadata', {})
        domain = meta.get('domain', 'N/A')
        rid = res.get('id', 'N/A')
        name = res.get('name', 'N/A')
        rtype = res.get('type', 'N/A')
        desc = str(res.get('description', ''))[:200]
        cols = res.get('columns_name', [])
        link = r.get('link', 'N/A')

        print(f"  [{domain}] {rid} - {name}")
        print(f"    Type: {rtype}")
        print(f"    Desc: {desc}")
        print(f"    Columns: {cols[:20]}")
        print(f"    Link: {link}")
        print()

        # Flag product catalog datasets
        name_lower = name.lower()
        desc_lower = desc.lower()
        col_str = ' '.join(cols).lower()
        is_product = any(kw in name_lower or kw in desc_lower or kw in col_str for kw in
            ['product', 'price', 'catalog', 'item', 'brand', 'proof', 'abv', 'spirits', 'bottle'])
        is_license = any(kw in name_lower for kw in ['license', 'violation', 'permit', 'complaint'])
        if is_product and not is_license and rtype == 'dataset':
            product_datasets.append((rid, name, domain, cols, link))

    return product_datasets


if __name__ == '__main__':
    all_product_datasets = []

    # State-specific views API
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
        results = check_views(url, name)
        all_product_datasets.extend(results)

    # Catalog searches
    catalogs = [
        ("https://api.us.socrata.com/api/catalog/v1?q=liquor%20products&limit=20", "liquor products"),
        ("https://api.us.socrata.com/api/catalog/v1?q=spirits%20price%20list&limit=20", "spirits price list"),
        ("https://api.us.socrata.com/api/catalog/v1?q=whiskey%20catalog&limit=20", "whiskey catalog"),
        ("https://api.us.socrata.com/api/catalog/v1?q=liquor%20price%20list&limit=20", "liquor price list"),
        ("https://api.us.socrata.com/api/catalog/v1?q=abc%20products&limit=20", "abc products"),
        ("https://api.us.socrata.com/api/catalog/v1?q=beverage%20alcohol%20products&limit=20", "beverage alcohol products"),
    ]

    catalog_datasets = []
    for url, label in catalogs:
        results = check_catalog(url, label)
        catalog_datasets.extend(results)

    # Summary
    print(f"\n\n{'#'*70}")
    print(f"  SUMMARY: Promising Product Catalog Datasets")
    print(f"{'#'*70}")

    if all_product_datasets:
        print(f"\nFrom state-specific APIs ({len(all_product_datasets)}):")
        for did, name, rows, cols, state in all_product_datasets:
            print(f"  [{state}] {did} - {name} ({rows} rows)")

    if catalog_datasets:
        # Deduplicate by ID
        seen = set()
        unique = []
        for item in catalog_datasets:
            if item[0] not in seen:
                seen.add(item[0])
                unique.append(item)
        print(f"\nFrom catalog searches ({len(unique)} unique):")
        for rid, name, domain, cols, link in unique:
            print(f"  [{domain}] {rid} - {name}")
            print(f"    Columns: {cols[:15]}")
            print(f"    Link: {link}")
