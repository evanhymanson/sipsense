import logging
import math
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stores", tags=["stores"])

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
CACHE_EXPIRY_DAYS = 7
DEFAULT_RADIUS_M = 5000
MAX_RADIUS_M = 25000


# ── Utilities ──────────────────────────────────────────────────────────────


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance in meters between two lat/lng points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _build_overpass_query(lat: float, lng: float, radius: int) -> str:
    return (
        f'[out:json][timeout:10];'
        f'('
        f'node["shop"="alcohol"](around:{radius},{lat},{lng});'
        f'node["shop"="wine"](around:{radius},{lat},{lng});'
        f'node["shop"="beverages"]["drink:alcohol"="yes"](around:{radius},{lat},{lng});'
        f');'
        f'out body;'
    )


def _parse_osm_node(element: dict) -> dict:
    tags = element.get("tags", {})
    addr_parts = []
    if tags.get("addr:housenumber"):
        addr_parts.append(tags["addr:housenumber"])
    if tags.get("addr:street"):
        addr_parts.append(tags["addr:street"])
    if tags.get("addr:city"):
        addr_parts.append(tags["addr:city"])
    if tags.get("addr:state"):
        addr_parts.append(tags["addr:state"])

    return {
        "osm_id": element["id"],
        "name": tags.get("name", "Liquor Store"),
        "lat": element["lat"],
        "lng": element["lon"],
        "address": ", ".join(addr_parts) if addr_parts else None,
        "phone": tags.get("phone") or tags.get("contact:phone"),
        "website": tags.get("website") or tags.get("contact:website"),
        "opening_hours": tags.get("opening_hours"),
        "shop_type": tags.get("shop", "alcohol"),
    }


def _upsert_stores(db: Session, parsed_stores: list[dict]) -> list[models.LiquorStore]:
    result = []
    for data in parsed_stores:
        existing = db.query(models.LiquorStore).filter(
            models.LiquorStore.osm_id == data["osm_id"]
        ).first()
        if existing:
            for key, val in data.items():
                setattr(existing, key, val)
            existing.last_fetched = datetime.now(timezone.utc)
            result.append(existing)
        else:
            store = models.LiquorStore(**data)
            db.add(store)
            result.append(store)
    db.commit()
    for s in result:
        db.refresh(s)
    return result


def _fetch_nearby(lat: float, lng: float, radius: int, db: Session) -> list[dict]:
    """Find nearby stores (cache-first, Overpass fallback). Returns dicts with distance_m."""
    delta_lat = radius / 111_000
    delta_lng = radius / (111_000 * max(math.cos(math.radians(lat)), 0.01))

    cached = db.query(models.LiquorStore).filter(
        and_(
            models.LiquorStore.lat.between(lat - delta_lat, lat + delta_lat),
            models.LiquorStore.lng.between(lng - delta_lng, lng + delta_lng),
            models.LiquorStore.last_fetched >= datetime.now(timezone.utc) - timedelta(days=CACHE_EXPIRY_DAYS),
        )
    ).all()

    cached_nearby = []
    for store in cached:
        dist = _haversine(lat, lng, store.lat, store.lng)
        if dist <= radius:
            cached_nearby.append((store, dist))

    if cached_nearby:
        cached_nearby.sort(key=lambda x: x[1])
        results = []
        for store, dist in cached_nearby:
            d = schemas.LiquorStoreRead.model_validate(store).model_dump()
            d["distance_m"] = round(dist, 1)
            results.append(d)
        return results

    # Fallback: query Overpass API
    query = _build_overpass_query(lat, lng, radius)
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(OVERPASS_URL, data={"data": query})
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Store location service timed out. Try again or reduce radius.")
    except httpx.HTTPError as e:
        logger.error("Overpass API error: %s", e)
        raise HTTPException(status_code=502, detail="Failed to reach store location service.")

    elements = data.get("elements", [])
    if not elements:
        return []

    parsed = [_parse_osm_node(el) for el in elements]
    stores = _upsert_stores(db, parsed)

    results = []
    for store in stores:
        dist = _haversine(lat, lng, store.lat, store.lng)
        d = schemas.LiquorStoreRead.model_validate(store).model_dump()
        d["distance_m"] = round(dist, 1)
        results.append(d)

    results.sort(key=lambda s: s["distance_m"])
    return results


# ── Endpoints ──────────────────────────────────────────────────────────────


@router.get("/nearby", response_model=list[schemas.LiquorStoreRead])
def get_nearby_stores(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius: int = Query(DEFAULT_RADIUS_M, ge=500, le=MAX_RADIUS_M),
    db: Session = Depends(get_db),
):
    """Find nearby liquor stores via OpenStreetMap. Results are cached for 7 days."""
    store_dicts = _fetch_nearby(lat, lng, radius, db)
    return [schemas.LiquorStoreRead(**d) for d in store_dicts]


@router.get("/whiskey/{whiskey_id}", response_model=list[schemas.StoreWithAvailability])
def get_stores_for_whiskey(
    whiskey_id: int,
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius: int = Query(DEFAULT_RADIUS_M, ge=500, le=MAX_RADIUS_M),
    db: Session = Depends(get_db),
):
    """Find nearby stores enriched with community-reported availability for a whiskey."""
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    store_dicts = _fetch_nearby(lat, lng, radius, db)

    results = []
    for sd in store_dicts:
        reports = db.query(models.StoreAvailability).filter(
            and_(
                models.StoreAvailability.store_id == sd["id"],
                models.StoreAvailability.whiskey_id == whiskey_id,
            )
        ).order_by(models.StoreAvailability.reported_at.desc()).limit(10).all()

        latest_status = reports[0].status if reports else None
        result = schemas.StoreWithAvailability(
            **sd,
            availability=[schemas.StoreAvailabilityRead.model_validate(r) for r in reports],
            latest_status=latest_status,
            report_count=len(reports),
        )
        results.append(result)

    # Stores with reports first, then by distance
    results.sort(key=lambda s: (s.report_count == 0, s.distance_m or 99999))
    return results


@router.post("/{store_osm_id}/report", response_model=schemas.StoreAvailabilityRead, status_code=201)
def report_availability(
    store_osm_id: int,
    report: schemas.StoreAvailabilityCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit a community availability report for a whiskey at a store."""
    store = db.query(models.LiquorStore).filter(
        models.LiquorStore.osm_id == store_osm_id
    ).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found. Search for nearby stores first.")

    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == report.whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    db_report = models.StoreAvailability(
        user_id=current_user.username,
        store_id=store.id,
        whiskey_id=report.whiskey_id,
        status=report.status,
    )
    db.add(db_report)
    db.commit()
    db.refresh(db_report)
    return db_report


@router.get("/{store_osm_id}/availability", response_model=list[schemas.StoreAvailabilityRead])
def get_store_availability(
    store_osm_id: int,
    whiskey_id: int = Query(None),
    db: Session = Depends(get_db),
):
    """Get availability reports for a store, optionally filtered by whiskey."""
    store = db.query(models.LiquorStore).filter(
        models.LiquorStore.osm_id == store_osm_id
    ).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")

    query = db.query(models.StoreAvailability).filter(
        models.StoreAvailability.store_id == store.id
    )
    if whiskey_id is not None:
        query = query.filter(models.StoreAvailability.whiskey_id == whiskey_id)

    return query.order_by(models.StoreAvailability.reported_at.desc()).limit(50).all()
