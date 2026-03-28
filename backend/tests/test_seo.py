"""Tests for the seo router — sitemap.xml, OG tags for social sharing."""


class TestSitemap:
    def test_returns_xml(self, client):
        resp = client.get("/seo/sitemap.xml")
        assert resp.status_code == 200
        assert "application/xml" in resp.headers["content-type"]

    def test_contains_root(self, client):
        body = client.get("/seo/sitemap.xml").text
        assert "https://sipsense.ai/" in body

    def test_contains_learn(self, client):
        body = client.get("/seo/sitemap.xml").text
        assert "https://sipsense.ai/learn" in body

    def test_contains_categories(self, client):
        body = client.get("/seo/sitemap.xml").text
        assert "learn/categories/bourbon" in body
        assert "learn/categories/scotch" in body

    def test_contains_distilleries(self, client):
        body = client.get("/seo/sitemap.xml").text
        assert "learn/distilleries/makers-mark" in body

    def test_contains_whiskeys(self, client, sample_whiskeys):
        body = client.get("/seo/sitemap.xml").text
        # Sample whiskeys have image_url so they should appear
        assert f"/whiskey/{sample_whiskeys[0].id}" in body

    def test_cache_header(self, client):
        resp = client.get("/seo/sitemap.xml")
        assert "max-age=3600" in resp.headers.get("cache-control", "")


class TestWhiskeyOG:
    def test_returns_html(self, client, sample_whiskeys):
        resp = client.get(f"/seo/og/whiskey/{sample_whiskeys[0].id}")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_contains_og_tags(self, client, sample_whiskeys):
        body = client.get(f"/seo/og/whiskey/{sample_whiskeys[0].id}").text
        assert 'og:title' in body
        assert 'og:description' in body
        assert 'og:image' in body
        assert 'og:url' in body

    def test_contains_twitter_tags(self, client, sample_whiskeys):
        body = client.get(f"/seo/og/whiskey/{sample_whiskeys[0].id}").text
        assert 'twitter:card' in body
        assert 'twitter:title' in body

    def test_meta_refresh(self, client, sample_whiskeys):
        body = client.get(f"/seo/og/whiskey/{sample_whiskeys[0].id}").text
        assert 'http-equiv="refresh"' in body

    def test_not_found(self, client):
        resp = client.get("/seo/og/whiskey/99999")
        assert resp.status_code == 404
