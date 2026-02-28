"""
Wikidata SPARQL scraper for whiskey entries.

Queries the Wikidata knowledge graph for whiskey items across multiple
entity types. Expects ~30–50k entries total.

Wikidata endpoint: https://query.wikidata.org/sparql
Rate limit: ~60 requests/minute — we add delays between queries.
"""

import logging
import time
from typing import Optional

import httpx

log = logging.getLogger(__name__)

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
# Wikidata requires a descriptive User-Agent with contact info; GET is blocked, use POST
USER_AGENT = "SipSense/1.0 (https://github.com/sipsense; sipsense-bot@example.com)"

# Wikidata entity IDs for whiskey types
# Q56884561 = whisky (general); may return 0 results depending on data state
# Querying multiple known subtypes is more reliable
WHISKEY_ENTITY_IDS = [
    ("Q56884561", "whisky"),        # whisky (general class)
    ("Q14353",    "bourbon"),       # bourbon whiskey
    ("Q1247393",  "scotch"),        # Scotch whisky
    ("Q485446",   "irish"),         # Irish whiskey
    ("Q877541",   "japanese"),      # Japanese whisky
    ("Q213048",   "rye"),           # rye whiskey
    ("Q106812",   "canadian"),      # Canadian whisky
]

# SPARQL query template — one query per entity type
QUERY_TEMPLATE = """
SELECT DISTINCT ?item ?itemLabel ?distilleryLabel ?countryLabel ?abv WHERE {{
  {{ ?item wdt:P31 wd:{entity_id} }}
  UNION
  {{ ?item wdt:P31/wdt:P279 wd:{entity_id} }}
  OPTIONAL {{ ?item wdt:P176 ?distillery }}
  OPTIONAL {{ ?item wdt:P495 ?country }}
  OPTIONAL {{ ?item wdt:P2665 ?abv }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
}}
LIMIT {limit}
"""

# Broader fallback: query by label string match using mwapi
LABEL_SEARCH_QUERIES = [
    """
SELECT DISTINCT ?item ?itemLabel ?distilleryLabel ?countryLabel ?abv WHERE {
  SERVICE wikibase:mwapi {
    bd:serviceParam wikibase:endpoint "www.wikidata.org" ;
                    wikibase:api "EntitySearch" ;
                    mwapi:search "whisky" ;
                    mwapi:language "en" ;
                    mwapi:limit "500" .
    ?item wikibase:apiOutputItem mwapi:item .
  }
  ?item wdt:P31 ?type.
  OPTIONAL { ?item wdt:P176 ?distillery }
  OPTIONAL { ?item wdt:P495 ?country }
  OPTIONAL { ?item wdt:P2665 ?abv }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
LIMIT 5000
""",
    """
SELECT DISTINCT ?item ?itemLabel ?distilleryLabel ?countryLabel ?abv WHERE {
  SERVICE wikibase:mwapi {
    bd:serviceParam wikibase:endpoint "www.wikidata.org" ;
                    wikibase:api "EntitySearch" ;
                    mwapi:search "bourbon whiskey" ;
                    mwapi:language "en" ;
                    mwapi:limit "500" .
    ?item wikibase:apiOutputItem mwapi:item .
  }
  ?item wdt:P31 ?type.
  OPTIONAL { ?item wdt:P176 ?distillery }
  OPTIONAL { ?item wdt:P495 ?country }
  OPTIONAL { ?item wdt:P2665 ?abv }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
LIMIT 5000
""",
]


class WikidataScraper:
    """
    Fetches whiskey entries from Wikidata via SPARQL.

    Runs multiple queries (one per whiskey entity type) and deduplicates
    by Wikidata item ID.
    """

    def __init__(self):
        self._client = httpx.Client(
            timeout=90.0,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/sparql-results+json",
            },
        )
        self._seen_ids: set[str] = set()

    def fetch_whiskeys(self, per_type_limit: int = 10_000) -> list[dict]:
        results = []
        total_queries = len(WHISKEY_ENTITY_IDS) + len(LABEL_SEARCH_QUERIES)

        # Phase 1: entity-type queries
        for i, (entity_id, label) in enumerate(WHISKEY_ENTITY_IDS, 1):
            log.info(
                "Wikidata query %d/%d: %s (%s)…",
                i, total_queries, label, entity_id,
            )
            query = QUERY_TEMPLATE.format(
                entity_id=entity_id, limit=per_type_limit
            )
            try:
                rows = self._run_query(query)
                log.info("  → %d new results", len(rows))
                results.extend(rows)
            except Exception as exc:
                log.warning("  Query failed: %s", exc)
            time.sleep(3)  # respect Wikidata rate limits

        # Phase 2: label search fallback (catches items not typed as whiskey)
        for i, query in enumerate(LABEL_SEARCH_QUERIES, 1):
            log.info(
                "Wikidata label-search query %d/%d…",
                len(WHISKEY_ENTITY_IDS) + i, total_queries,
            )
            try:
                rows = self._run_query(query)
                log.info("  → %d new results", len(rows))
                results.extend(rows)
            except Exception as exc:
                log.warning("  Query failed: %s", exc)
            time.sleep(5)  # label search is heavier

        log.info("Wikidata total: %d unique entries", len(results))
        return results

    # ── internals ─────────────────────────────────────────────────────────

    def _run_query(self, query: str) -> list[dict]:
        # Wikidata requires POST for SPARQL; GET returns 403
        resp = self._client.post(
            SPARQL_ENDPOINT,
            data={"query": query},
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/sparql-results+json",
            },
        )
        resp.raise_for_status()

        bindings = resp.json().get("results", {}).get("bindings", [])
        results = []

        for binding in bindings:
            # Deduplicate by Wikidata item ID
            item_uri = binding.get("item", {}).get("value", "")
            item_id = item_uri.split("/")[-1]
            if item_id in self._seen_ids:
                continue
            self._seen_ids.add(item_id)

            raw = self._binding_to_raw(binding)
            if raw:
                results.append(raw)

        return results

    def _binding_to_raw(self, binding: dict) -> Optional[dict]:
        name = binding.get("itemLabel", {}).get("value", "").strip()
        # Items without an English label get their Q-ID as the label — skip those
        if not name or re.match(r"^Q\d+$", name):
            return None

        distillery = binding.get("distilleryLabel", {}).get("value", "").strip()
        if re.match(r"^Q\d+$", distillery):
            distillery = None

        country = binding.get("countryLabel", {}).get("value", "").strip()
        if re.match(r"^Q\d+$", country):
            country = None

        abv_raw = binding.get("abv", {}).get("value", "")

        return {
            "name":         name,
            "distillery":   distillery or "Unknown",
            "category":     _infer_category(name, country),
            "country":      _normalize_country(country or ""),
            "region":       None,
            "age_str":      None,
            "abv_str":      abv_raw or "40.0",
            "rating_str":   None,
            "price_str":    None,
            "description":  None,
            "flavor_profile": None,
            "upc":          None,
            "source":       "wikidata",
        }

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# ── helpers ───────────────────────────────────────────────────────────────

import re  # noqa: E402 (imported here to keep binding_to_raw clean above)


def _infer_category(name: str, country: Optional[str]) -> str:
    n = name.lower()
    if "bourbon" in n:      return "bourbon"
    if "rye" in n:          return "rye"
    if "scotch" in n:       return "scotch"
    if "single malt" in n:  return "single malt"
    if "blended malt" in n: return "scotch"
    if "irish" in n:        return "irish"
    if "japanese" in n:     return "japanese"
    if "canadian" in n:     return "canadian"
    if "tennessee" in n:    return "bourbon"

    c = (country or "").lower()
    if "scotland" in c:     return "scotch"
    if "united states" in c or "usa" in c: return "bourbon"
    if "ireland" in c:      return "irish"
    if "japan" in c:        return "japanese"
    if "canada" in c:       return "canadian"

    return "whisky"


def _normalize_country(country: str) -> str:
    c = country.lower().strip()
    if "united states" in c:   return "usa"
    if "scotland" in c:        return "scotland"
    if "united kingdom" in c:  return "scotland"
    if "ireland" in c:         return "ireland"
    if "japan" in c:           return "japan"
    if "canada" in c:          return "canada"
    return c
