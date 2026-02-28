"""Tests for whiskey CRUD, search, filtering, sorting, ratings, and value picks."""

import pytest


class TestListWhiskeys:
    def test_list_all(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 6

    def test_search_by_name(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/", params={"q": "Buffalo"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "Buffalo Trace"

    def test_search_by_distillery(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/", params={"q": "Suntory"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_category(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/", params={"category": "bourbon"})
        assert resp.status_code == 200
        data = resp.json()
        assert all("bourbon" in w["category"].lower() for w in data)

    def test_filter_by_region(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/", params={"region": "Islay"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_flavor(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/", params={"flavor": "smoky"})
        assert resp.status_code == 200
        data = resp.json()
        assert all("smoky" in (w.get("flavor_profile") or "").lower() for w in data)

    def test_filter_by_price_range(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/", params={"min_price": 30, "max_price": 60})
        assert resp.status_code == 200
        data = resp.json()
        assert all(30 <= w["price_usd"] <= 60 for w in data)

    def test_filter_by_min_abv(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/", params={"min_abv": 45})
        assert resp.status_code == 200
        data = resp.json()
        assert all(w["abv"] >= 45 for w in data)

    def test_sort_by_price_asc(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/", params={"sort_by": "price_asc"})
        data = resp.json()
        prices = [w["price_usd"] for w in data if w["price_usd"] is not None]
        assert prices == sorted(prices)

    def test_sort_by_price_desc(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/", params={"sort_by": "price_desc"})
        data = resp.json()
        prices = [w["price_usd"] for w in data if w["price_usd"] is not None]
        assert prices == sorted(prices, reverse=True)

    def test_sort_by_name(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/", params={"sort_by": "name"})
        data = resp.json()
        names = [w["name"] for w in data]
        assert names == sorted(names)

    def test_pagination(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/", params={"skip": 0, "limit": 2})
        assert len(resp.json()) == 2
        resp2 = client.get("/whiskeys/", params={"skip": 2, "limit": 2})
        assert len(resp2.json()) == 2
        # No overlap
        ids1 = {w["id"] for w in resp.json()}
        ids2 = {w["id"] for w in resp2.json()}
        assert ids1.isdisjoint(ids2)


class TestGetWhiskey:
    def test_get_by_id(self, client, sample_whiskeys):
        wid = sample_whiskeys[0].id
        resp = client.get(f"/whiskeys/{wid}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Buffalo Trace"

    def test_get_not_found(self, client):
        resp = client.get("/whiskeys/99999")
        assert resp.status_code == 404


class TestCreateWhiskey:
    def test_create(self, client):
        resp = client.post("/whiskeys/", json={
            "name": "Test Whiskey",
            "distillery": "Test Distillery",
            "category": "bourbon",
            "abv": 46.0,
            "price_usd": 40.0,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Whiskey"
        assert data["id"] is not None


class TestRateWhiskey:
    def test_rate_success(self, client, auth_headers, sample_whiskeys):
        wid = sample_whiskeys[0].id
        resp = client.post(
            f"/whiskeys/{wid}/rate",
            json={"score": 4.5, "notes": "Great bourbon"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Response is CheckInResponse: {rating: {...}, new_badges: [...]}
        assert data["rating"]["score"] == 4.5
        assert data["rating"]["notes"] == "Great bourbon"
        assert "new_badges" in data

    def test_rate_updates_average(self, client, auth_headers, sample_whiskeys):
        wid = sample_whiskeys[0].id
        client.post(f"/whiskeys/{wid}/rate", json={"score": 5.0}, headers=auth_headers)
        whiskey = client.get(f"/whiskeys/{wid}").json()
        assert whiskey["rating_avg"] > 0
        assert whiskey["rating_count"] >= 1

    def test_rate_invalid_score(self, client, auth_headers, sample_whiskeys):
        wid = sample_whiskeys[0].id
        resp = client.post(
            f"/whiskeys/{wid}/rate",
            json={"score": 6.0},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_rate_unauthenticated(self, client, sample_whiskeys):
        wid = sample_whiskeys[0].id
        resp = client.post(f"/whiskeys/{wid}/rate", json={"score": 4.0})
        assert resp.status_code == 401

    def test_rate_not_found(self, client, auth_headers):
        resp = client.post(
            "/whiskeys/99999/rate",
            json={"score": 4.0},
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestGetRatings:
    def test_get_ratings(self, client, auth_headers, sample_whiskeys):
        wid = sample_whiskeys[0].id
        client.post(f"/whiskeys/{wid}/rate", json={"score": 4.0}, headers=auth_headers)
        resp = client.get(f"/whiskeys/{wid}/ratings")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_ratings_not_found(self, client):
        resp = client.get("/whiskeys/99999/ratings")
        assert resp.status_code == 404


class TestValuePicks:
    def test_value_picks(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/value-picks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0

    def test_value_picks_with_category(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/value-picks", params={"category": "bourbon"})
        data = resp.json()
        assert all("bourbon" in w["category"].lower() for w in data)

    def test_value_picks_max_price(self, client, sample_whiskeys):
        resp = client.get("/whiskeys/value-picks", params={"max_price": 30})
        data = resp.json()
        assert all(w["price_usd"] <= 30 for w in data)
