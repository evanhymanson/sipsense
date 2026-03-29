"""Tests for the seo router -- sitemap, OG tags, and prerendering for crawlers."""


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
        assert f"/whiskey/{sample_whiskeys[0].id}" in body

    def test_cache_header(self, client):
        resp = client.get("/seo/sitemap.xml")
        assert "max-age=3600" in resp.headers.get("cache-control", "")

    def test_contains_lists(self, client):
        body = client.get("/seo/sitemap.xml").text
        assert "https://sipsense.ai/lists" in body
        assert "lists/top-bourbons" in body


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

    def test_canonical_url(self, client, sample_whiskeys):
        body = client.get(f"/seo/og/whiskey/{sample_whiskeys[0].id}").text
        assert 'rel="canonical"' in body

    def test_not_found(self, client):
        resp = client.get("/seo/og/whiskey/99999")
        assert resp.status_code == 404


class TestPrerenderHome:
    def test_returns_html(self, client):
        resp = client.get("/seo/prerender/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_contains_title_and_meta(self, client):
        body = client.get("/seo/prerender/").text
        assert "SipSense" in body
        assert "<h1>" in body
        assert 'name="description"' in body
        assert 'rel="canonical"' in body


class TestPrerenderLearn:
    def test_returns_html(self, client):
        resp = client.get("/seo/prerender/learn")
        assert resp.status_code == 200

    def test_contains_content(self, client):
        body = client.get("/seo/prerender/learn").text
        assert "Bourbon" in body
        assert "Scotch" in body
        assert "Maker" in body


class TestPrerenderGlossary:
    def test_returns_html(self, client):
        resp = client.get("/seo/prerender/learn/glossary")
        assert resp.status_code == 200

    def test_contains_terms(self, client):
        body = client.get("/seo/prerender/learn/glossary").text
        assert "Single Malt" in body
        assert "ABV" in body


class TestPrerenderCategory:
    def test_bourbon(self, client):
        resp = client.get("/seo/prerender/learn/categories/bourbon")
        assert resp.status_code == 200
        assert "Bourbon" in resp.text

    def test_not_found(self, client):
        resp = client.get("/seo/prerender/learn/categories/invalid")
        assert resp.status_code == 404


class TestPrerenderDistillery:
    def test_buffalo_trace(self, client):
        resp = client.get("/seo/prerender/learn/distilleries/buffalo-trace")
        assert resp.status_code == 200
        assert "Buffalo Trace" in resp.text

    def test_not_found(self, client):
        resp = client.get("/seo/prerender/learn/distilleries/invalid")
        assert resp.status_code == 404


class TestPrerenderLists:
    def test_index(self, client):
        resp = client.get("/seo/prerender/lists")
        assert resp.status_code == 200
        assert "Top Bourbons" in resp.text

    def test_detail(self, client):
        resp = client.get("/seo/prerender/lists/top-bourbons")
        assert resp.status_code == 200

    def test_not_found(self, client):
        resp = client.get("/seo/prerender/lists/invalid")
        assert resp.status_code == 404
