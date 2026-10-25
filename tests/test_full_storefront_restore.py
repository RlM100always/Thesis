"""Safeguard full storefront route wiring after recovering the user's source ZIP."""
from api.main import app


def test_local_storefront_routes_are_mounted():
    registered = {
        (method, route.path)
        for route in app.routes
        if hasattr(route, "methods")
        for method in route.methods
    }
    expected = {
        ("GET", "/api/public/store/"),
        ("GET", "/api/public/store/slug/{slug}"),
        ("GET", "/api/public/store/{organization_id}"),
        ("POST", "/api/public/orders/{organization_id}"),
        ("GET", "/api/public/orders/{organization_id}/status/{access_token}"),
        ("POST", "/api/sc/register"),
        ("POST", "/api/sc/login"),
        ("GET", "/api/sc/me"),
        ("GET", "/api/app/store/orders"),
        ("GET", "/api/app/store/coupons"),
        ("POST", "/api/public/store/{org_id}/coupon/validate"),
        ("GET", "/api/public/reviews/{org_id}/{product_id}"),
        ("POST", "/api/public/payment/initiate/{org_id}"),
    }
    assert expected <= registered, f"Missing routes: {expected - registered}"


def test_existing_business_apis_and_research_reset_remain_mounted():
    paths = {route.path for route in app.routes}
    assert "/api/app/organizations" in paths
    assert "/api/research/portal/shops" in paths
    assert "/api/app/bsmart/run" in paths
    assert "/health" in paths
