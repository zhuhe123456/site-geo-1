from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


client = TestClient(app)


def test_summarize_endpoint_returns_composite_score() -> None:
    payload = {
        "url": "https://example.com",
        "discovery": {
            "url": "https://example.com",
            "normalized_url": "https://example.com/",
            "final_url": "https://example.com/",
            "domain": "example.com",
            "fetch": {
                "final_url": "https://example.com/",
                "status_code": 200,
                "headers": {"content-type": "text/html"},
                "response_time_ms": 120,
            },
            "homepage": {
                "title": "Example",
                "meta_description": "Example description",
                "canonical": "https://example.com/",
                "lang": "en",
                "viewport": "width=device-width, initial-scale=1",
                "h1": "Example heading",
                "headings": [{"level": "h1", "text": "Example heading"}],
                "hreflang": [],
                "internal_links": [],
                "external_links": [],
                "images": [],
                "scripts": [],
                "stylesheets": [],
                "json_ld_blocks": [],
                "open_graph": {},
                "twitter_cards": {},
                "word_count": 400,
                "html_length": 5000,
                "text_excerpt": "Example excerpt",
            },
            "robots": {
                "url": "https://example.com/robots.txt",
                "exists": True,
                "status_code": 200,
                "allows_all": True,
                "has_sitemap_directive": True,
                "sitemaps": ["https://example.com/sitemap.xml"],
                "user_agents": {
                    "GPTBot": {"allowed": True, "matched_user_agent": "*"},
                    "OAI-SearchBot": {"allowed": True, "matched_user_agent": "*"},
                    "ChatGPT-User": {"allowed": True, "matched_user_agent": "*"},
                    "ClaudeBot": {"allowed": True, "matched_user_agent": "*"},
                    "PerplexityBot": {"allowed": True, "matched_user_agent": "*"},
                    "Google-Extended": {"allowed": True, "matched_user_agent": "*"},
                },
                "raw_preview": "",
            },
            "sitemap": {
                "url": "https://example.com/sitemap.xml",
                "exists": True,
                "status_code": 200,
                "discovered_urls": ["https://example.com/about"],
                "total_urls_sampled": 1,
            },
            "llms": {
                "url": "https://example.com/llms.txt",
                "exists": True,
                "status_code": 200,
                "content_preview": "Example llms",
                "content_length": 50,
            },
            "business_type": "agency",
            "key_pages": {
                "about": "https://example.com/about",
                "service": "https://example.com/services",
                "contact": "https://example.com/contact",
                "article": "https://example.com/blog/example",
                "case_study": "https://example.com/case-study/example",
            },
            "schema_summary": {
                "json_ld_present": True,
                "types": ["Organization", "WebSite"],
                "has_organization": True,
                "has_local_business": False,
                "has_article": False,
                "has_faq_page": False,
                "has_service": False,
                "has_website": True,
                "same_as": ["https://linkedin.com/company/example"],
            },
            "site_signals": {
                "company_name_detected": True,
                "address_detected": True,
                "phone_detected": True,
                "email_detected": True,
                "awards_detected": False,
                "certifications_detected": False,
                "same_as_detected": True,
                "detected_company_name": "Example",
            },
        },
        "visibility": {
            "score": 78,
            "status": "good",
            "findings": {},
            "issues": [],
            "strengths": [],
            "recommendations": [],
            "ai_visibility_score": 78,
            "brand_authority_score": 72,
            "checks": {},
        },
        "technical": {
            "score": 74,
            "status": "good",
            "findings": {},
            "issues": [],
            "strengths": [],
            "recommendations": [],
            "technical_score": 74,
            "checks": {},
            "security_headers": {},
            "ssr_signal": {},
            "render_blocking_risk": {},
        },
        "content": {
            "score": 70,
            "status": "good",
            "findings": {},
            "issues": [],
            "strengths": [],
            "recommendations": [],
            "content_score": 70,
            "experience_score": 68,
            "expertise_score": 72,
            "authoritativeness_score": 66,
            "trustworthiness_score": 74,
            "checks": {},
            "page_analyses": {},
        },
        "schema": {
            "score": 55,
            "status": "fair",
            "findings": {},
            "issues": [],
            "strengths": [],
            "recommendations": [],
            "structured_data_score": 55,
            "checks": {},
            "schema_types": ["Organization", "WebSite"],
            "same_as": ["https://linkedin.com/company/example"],
            "missing_schema_recommendations": [],
        },
        "platform": {
            "score": 62,
            "status": "fair",
            "findings": {},
            "issues": [],
            "strengths": [],
            "recommendations": [],
            "platform_optimization_score": 62,
            "checks": {},
            "platform_scores": {},
        },
    }

    original_token = settings.demo_access_token
    object.__setattr__(settings, "demo_access_token", "summarize-test-token")
    try:
        response = client.post(
            "/api/v1/audit/summarize",
            headers={"X-API-Token": "summarize-test-token"},
            json=payload,
        )
    finally:
        object.__setattr__(settings, "demo_access_token", original_token)
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["composite_geo_score"] > 0
    assert body["data"]["status"] in {"critical", "poor", "fair", "good", "strong"}
    assert body["data"]["ai_perception"]["positive_percentage"] >= 0
    assert body["data"]["ai_perception"]["neutral_percentage"] >= 0
    assert body["data"]["ai_perception"]["controversial_percentage"] >= 0
    assert body["data"]["ai_perception"]["positive_percentage"] + body["data"]["ai_perception"]["neutral_percentage"] + body["data"]["ai_perception"]["controversial_percentage"] == 100
    assert len(body["data"]["ai_perception"]["cognition_keywords"]) == 4
