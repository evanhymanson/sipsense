"""
Tests for Vivino-style community reviews:
- Flavor tags on check-in
- Review summary endpoint (distribution, community tags, serving styles)
- Review sorting
- Flavor tags list endpoint
"""


def test_flavor_tags_endpoint(client):
    """GET /whiskeys/flavor-tags returns the predefined list."""
    resp = client.get("/whiskeys/flavor-tags")
    assert resp.status_code == 200
    tags = resp.json()
    assert isinstance(tags, list)
    assert "vanilla" in tags
    assert "smoke" in tags
    assert len(tags) > 10


def test_rate_with_flavor_tags(client, auth_headers, sample_whiskeys):
    """Flavor tags are saved with a check-in."""
    w = sample_whiskeys[0]
    resp = client.post(
        f"/whiskeys/{w.id}/rate",
        json={"score": 4.0, "notes": "Rich and sweet", "flavor_tags": ["vanilla", "caramel", "oak"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data["rating"]["flavor_tags"]) == {"vanilla", "caramel", "oak"}


def test_rate_invalid_flavor_tag(client, auth_headers, sample_whiskeys):
    """Invalid flavor tags are rejected with 422."""
    w = sample_whiskeys[0]
    resp = client.post(
        f"/whiskeys/{w.id}/rate",
        json={"score": 4.0, "flavor_tags": ["nonexistent_tag"]},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_rate_too_many_flavor_tags(client, auth_headers, sample_whiskeys):
    """More than 10 flavor tags are rejected."""
    w = sample_whiskeys[0]
    tags = ["vanilla", "caramel", "oak", "smoke", "honey", "spice",
            "cherry", "apple", "citrus", "chocolate", "leather"]
    assert len(tags) == 11
    resp = client.post(
        f"/whiskeys/{w.id}/rate",
        json={"score": 4.0, "flavor_tags": tags},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_rerate_replaces_tags(client, auth_headers, sample_whiskeys):
    """Re-rating a whiskey replaces the previous flavor tags."""
    w = sample_whiskeys[0]
    # First rating
    client.post(
        f"/whiskeys/{w.id}/rate",
        json={"score": 4.0, "flavor_tags": ["vanilla", "oak"]},
        headers=auth_headers,
    )
    # Re-rate with different tags
    resp = client.post(
        f"/whiskeys/{w.id}/rate",
        json={"score": 4.5, "flavor_tags": ["smoke", "peat"]},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert set(resp.json()["rating"]["flavor_tags"]) == {"smoke", "peat"}

    # Verify via ratings list
    ratings = client.get(f"/whiskeys/{w.id}/ratings").json()
    assert len(ratings) == 1  # still one rating (upsert)
    assert set(ratings[0]["flavor_tags"]) == {"smoke", "peat"}


def test_review_summary_distribution(client, auth_headers, second_auth_headers, sample_whiskeys):
    """Review summary returns correct rating distribution."""
    w = sample_whiskeys[0]
    # Two ratings: 5.0 and 3.0
    client.post(f"/whiskeys/{w.id}/rate", json={"score": 5.0}, headers=auth_headers)
    client.post(f"/whiskeys/{w.id}/rate", json={"score": 3.0}, headers=second_auth_headers)

    resp = client.get(f"/whiskeys/{w.id}/review-summary")
    assert resp.status_code == 200
    data = resp.json()
    dist = data["distribution"]
    assert dist["total"] == 2
    assert dist["star_5"] == 1
    assert dist["star_3"] == 1
    assert dist["star_1"] == 0
    assert dist["average"] == 4.0


def test_review_summary_community_tags(client, auth_headers, second_auth_headers, sample_whiskeys):
    """Community tags aggregate across multiple reviewers."""
    w = sample_whiskeys[0]
    client.post(
        f"/whiskeys/{w.id}/rate",
        json={"score": 4.0, "flavor_tags": ["vanilla", "caramel"]},
        headers=auth_headers,
    )
    client.post(
        f"/whiskeys/{w.id}/rate",
        json={"score": 3.5, "flavor_tags": ["vanilla", "oak"]},
        headers=second_auth_headers,
    )

    resp = client.get(f"/whiskeys/{w.id}/review-summary")
    data = resp.json()
    tags = {t["tag"]: t["count"] for t in data["community_tags"]}
    assert tags["vanilla"] == 2  # both users tagged vanilla
    assert tags.get("caramel", 0) == 1
    assert tags.get("oak", 0) == 1


def test_review_summary_serving_styles(client, auth_headers, second_auth_headers, sample_whiskeys):
    """Serving style breakdown is returned correctly."""
    w = sample_whiskeys[0]
    client.post(
        f"/whiskeys/{w.id}/rate",
        json={"score": 4.0, "serving_style": "neat"},
        headers=auth_headers,
    )
    client.post(
        f"/whiskeys/{w.id}/rate",
        json={"score": 3.5, "serving_style": "neat"},
        headers=second_auth_headers,
    )

    resp = client.get(f"/whiskeys/{w.id}/review-summary")
    data = resp.json()
    assert data["serving_style_counts"]["neat"] == 2


def test_review_summary_empty(client, sample_whiskeys):
    """Review summary for whiskey with no ratings returns zeros."""
    w = sample_whiskeys[0]
    resp = client.get(f"/whiskeys/{w.id}/review-summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["distribution"]["total"] == 0
    assert data["distribution"]["average"] == 0.0
    assert data["community_tags"] == []


def test_ratings_sort_by_highest(client, auth_headers, second_auth_headers, sample_whiskeys):
    """Sort by highest returns reviews in descending score order."""
    w = sample_whiskeys[0]
    client.post(f"/whiskeys/{w.id}/rate", json={"score": 2.0}, headers=auth_headers)
    client.post(f"/whiskeys/{w.id}/rate", json={"score": 5.0}, headers=second_auth_headers)

    resp = client.get(f"/whiskeys/{w.id}/ratings?sort_by=highest")
    ratings = resp.json()
    assert ratings[0]["score"] == 5.0
    assert ratings[1]["score"] == 2.0


def test_ratings_sort_by_lowest(client, auth_headers, second_auth_headers, sample_whiskeys):
    """Sort by lowest returns reviews in ascending score order."""
    w = sample_whiskeys[0]
    client.post(f"/whiskeys/{w.id}/rate", json={"score": 2.0}, headers=auth_headers)
    client.post(f"/whiskeys/{w.id}/rate", json={"score": 5.0}, headers=second_auth_headers)

    resp = client.get(f"/whiskeys/{w.id}/ratings?sort_by=lowest")
    ratings = resp.json()
    assert ratings[0]["score"] == 2.0
    assert ratings[1]["score"] == 5.0


def test_ratings_sort_by_helpful(client, auth_headers, second_auth_headers, sample_whiskeys):
    """Sort by helpful orders by helpful vote count descending."""
    w = sample_whiskeys[0]
    # User 1 rates
    r1 = client.post(
        f"/whiskeys/{w.id}/rate", json={"score": 3.0}, headers=auth_headers
    ).json()["rating"]["id"]
    # User 2 rates
    client.post(f"/whiskeys/{w.id}/rate", json={"score": 4.0}, headers=second_auth_headers)
    # User 2 marks user 1's rating as helpful
    client.post(f"/ratings/{r1}/helpful", headers=second_auth_headers)

    resp = client.get(f"/whiskeys/{w.id}/ratings?sort_by=helpful")
    ratings = resp.json()
    # User 1's rating (1 helpful vote) should come first
    assert ratings[0]["user_id"] == "testuser"
    assert ratings[0]["helpful_count"] == 1


def test_ratings_include_username_and_tags(client, auth_headers, sample_whiskeys):
    """Ratings list includes username and flavor_tags fields."""
    w = sample_whiskeys[0]
    client.post(
        f"/whiskeys/{w.id}/rate",
        json={"score": 4.0, "flavor_tags": ["honey", "spice"]},
        headers=auth_headers,
    )

    resp = client.get(f"/whiskeys/{w.id}/ratings")
    ratings = resp.json()
    assert ratings[0]["username"] == "testuser"
    assert set(ratings[0]["flavor_tags"]) == {"honey", "spice"}
