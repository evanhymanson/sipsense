"""Tests for blog/content hub endpoints."""

import pytest


class TestBlogArticles:
    def test_list_articles(self, client):
        """GET /blog/articles returns list of all articles."""
        resp = client.get("/blog/articles")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0
        # Each article has required fields
        for article in data:
            assert "slug" in article
            assert "title" in article
            assert "meta_description" in article

    def test_get_article(self, client):
        """GET /blog/articles/{slug} returns article with whiskeys."""
        resp = client.get("/blog/articles/most-popular-whiskeys")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "most-popular-whiskeys"
        assert "title" in data
        assert "intro" in data
        assert isinstance(data["intro"], list)
        assert "whiskeys" in data
        assert isinstance(data["whiskeys"], list)
        assert "generated_at" in data

    def test_get_article_not_found(self, client):
        """Unknown slug returns 404."""
        resp = client.get("/blog/articles/nonexistent-article")
        assert resp.status_code == 404

    def test_article_whiskey_fields(self, client, db_session):
        """Whiskeys in article response have expected fields."""
        # Seed a whiskey so we get results
        from app import models
        w = db_session.query(models.Whiskey).first()
        if not w:
            w = models.Whiskey(
                name="Test Bourbon",
                distillery="Test Distillery",
                category="bourbon",
                abv=45.0,
                price_usd=35.0,
                rating_avg=4.2,
                rating_count=10,
                image_url="/images/test.jpg",
                flavor_profile="sweet,vanilla,caramel",
            )
            db_session.add(w)
            db_session.commit()

        resp = client.get("/blog/articles/best-bourbons-under-50")
        assert resp.status_code == 200
        data = resp.json()
        if len(data["whiskeys"]) > 0:
            w_data = data["whiskeys"][0]
            assert "id" in w_data
            assert "name" in w_data
            assert "distillery" in w_data
            assert "category" in w_data
            assert "price_usd" in w_data
            assert "rating_avg" in w_data
            assert "image_url" in w_data

    def test_all_slugs_valid(self, client):
        """Every article slug from the index is fetchable."""
        index = client.get("/blog/articles").json()
        for article in index:
            resp = client.get(f"/blog/articles/{article['slug']}")
            assert resp.status_code == 200, f"Failed for slug: {article['slug']}"
