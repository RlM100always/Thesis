"""End-to-end coverage for account-based multi-store customer commerce."""
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.domain_models import Branch, InventoryBalance, Product, SalesDocument, Store, StoreProduct


def _register(client, email="buyer@example.com", phone="01711111111"):
    response = client.post("/api/sc/register", json={
        "display_name": "Demo Buyer",
        "email": email,
        "phone": phone,
        "password": "StrongPass123",
    })
    assert response.status_code == 200, response.text
    body = response.json()
    return body["token"], {"Authorization": f"Bearer {body['token']}"}


def _seed_store(engine, organization_id, product_id, slug, display_name):
    with Session(engine) as db:
        store = Store(
            organization_id=organization_id, slug=slug, display_name=display_name,
            is_active=True, show_price=True,
        )
        db.add(store)
        db.flush()
        db.add(StoreProduct(
            store_id=store.id, product_id=product_id, is_listed=True,
            online_price_bdt=Decimal("75.00"),
        ))
        db.commit()
        return store.id


def test_customer_can_manage_multiple_saved_addresses(world, client_for):
    client, _ = client_for("owner")
    _, headers = _register(client)

    first = client.post("/api/sc/addresses", headers=headers, json={
        "label": "বাড়ি", "recipient_name": "Demo Buyer", "phone": "01711111111",
        "division": "ঢাকা", "district": "ঢাকা", "thana": "ধানমন্ডি",
        "address_detail": "বাড়ি ১২, রোড ৪", "postal_code": "1209",
    })
    assert first.status_code == 201, first.text
    first_id = first.json()["id"]
    assert first.json()["is_default"] is True

    second = client.post("/api/sc/addresses", headers=headers, json={
        "label": "অফিস", "recipient_name": "Demo Buyer", "phone": "01711111111",
        "division": "ঢাকা", "district": "ঢাকা", "thana": "মিরপুর",
        "address_detail": "অফিস ২০", "is_default": False,
    })
    assert second.status_code == 201, second.text
    assert second.json()["is_default"] is False

    changed = client.patch(f"/api/sc/addresses/{second.json()['id']}", headers=headers, json={"is_default": True})
    assert changed.status_code == 200, changed.text
    listed = client.get("/api/sc/addresses", headers=headers).json()["addresses"]
    assert {a["id"]: a["is_default"] for a in listed} == {first_id: False, second.json()["id"]: True}

    deleted = client.delete(f"/api/sc/addresses/{second.json()['id']}", headers=headers)
    assert deleted.status_code == 200
    remaining = client.get("/api/sc/addresses", headers=headers).json()["addresses"]
    assert len(remaining) == 1
    assert remaining[0]["id"] == first_id and remaining[0]["is_default"] is True


def test_customer_wishlist_and_cart_are_persistent_and_private(engine, world, client_for):
    _seed_store(engine, world["org_a"], world["product_a"], "shop-a", "Shop A")
    client, _ = client_for("owner")
    _, headers = _register(client)

    added = client.post("/api/sc/wishlist", headers=headers, json={
        "store_slug": "shop-a", "product_id": world["product_a"],
    })
    assert added.status_code == 201, added.text
    wishlist = client.get("/api/sc/wishlist", headers=headers).json()
    assert wishlist["total"] == 1
    assert wishlist["items"][0]["store_slug"] == "shop-a"
    assert wishlist["items"][0]["product_id"] == world["product_a"]

    saved = client.put("/api/sc/cart/shop-a", headers=headers, json={
        "items": [{"product_id": world["product_a"], "quantity": 2, "variant_label": "Size: M"}],
    })
    assert saved.status_code == 200, saved.text
    cart = client.get("/api/sc/cart/shop-a", headers=headers).json()
    assert cart["items"][0]["quantity"] == 2
    assert cart["items"][0]["variant_label"] == "Size: M"
    assert cart["items"][0]["price"] == 75.0

    _, other_headers = _register(client, "other@example.com", "01722222222")
    assert client.get("/api/sc/wishlist", headers=other_headers).json()["total"] == 0
    assert client.get("/api/sc/cart/shop-a", headers=other_headers).json()["items"] == []
    assert client.delete(f"/api/sc/wishlist/shop-a/{world['product_a']}", headers=other_headers).status_code == 200
    assert client.get("/api/sc/wishlist", headers=headers).json()["total"] == 1


def test_wishlist_rejects_products_from_another_tenant(engine, world, client_for):
    _seed_store(engine, world["org_a"], world["product_a"], "shop-a", "Shop A")
    with Session(engine) as db:
        foreign_product = Product(
            organization_id=world["org_b"], sku="FOREIGN-1", name="Foreign product",
            selling_price=Decimal("20"), cost_price=Decimal("10"),
        )
        db.add(foreign_product)
        db.commit()
        foreign_product_id = foreign_product.id
    client, _ = client_for("owner")
    _, headers = _register(client)
    response = client.post("/api/sc/wishlist", headers=headers, json={
        "store_slug": "shop-a", "product_id": foreign_product_id,
    })
    assert response.status_code == 404


def test_account_order_history_combines_orders_across_stores(engine, world, client_for):
    _seed_store(engine, world["org_a"], world["product_a"], "shop-a", "Shop A")
    with Session(engine) as db:
        branch_b = Branch(organization_id=world["org_b"], code="MAIN", name="Main")
        product_b = Product(
            organization_id=world["org_b"], sku="TEA-1", name="Tea",
            selling_price=Decimal("35"), cost_price=Decimal("20"),
        )
        db.add_all([branch_b, product_b])
        db.flush()
        db.add(InventoryBalance(
            organization_id=world["org_b"], branch_id=branch_b.id,
            product_id=product_b.id, quantity=Decimal("8"),
        ))
        db.commit()
        product_b_id = product_b.id
    _seed_store(engine, world["org_b"], product_b_id, "shop-b", "Shop B")

    client, _ = client_for("owner")
    token, headers = _register(client)
    for org_id, product_id in [(world["org_a"], world["product_a"]), (world["org_b"], product_b_id)]:
        placed = client.post(f"/api/public/orders/{org_id}", json={
            "shipping_name": "Demo Buyer", "shipping_phone": "01711111111",
            "shipping_address": "Sample address only",
            "items": [{"product_id": product_id, "quantity": 1}],
            "store_customer_token": token,
        })
        assert placed.status_code == 200, placed.text

    response = client.get("/api/sc/orders", headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert {order["store_slug"] for order in body["orders"]} == {"shop-a", "shop-b"}
    assert all(order["document_number"].startswith("WEB-") for order in body["orders"])


def test_password_change_revokes_old_sessions_and_logout_revokes_current_session(world, client_for):
    client, _ = client_for("owner")
    old_token, old_headers = _register(client)
    changed = client.post("/api/sc/password", headers=old_headers, json={
        "current_password": "StrongPass123", "new_password": "NewStrongPass456",
    })
    assert changed.status_code == 200, changed.text
    new_token = changed.json()["token"]
    assert new_token != old_token
    assert client.get("/api/sc/me", headers=old_headers).status_code == 401
    new_headers = {"Authorization": f"Bearer {new_token}"}
    assert client.get("/api/sc/me", headers=new_headers).status_code == 200
    assert client.post("/api/sc/logout", headers=new_headers).status_code == 200
    assert client.get("/api/sc/me", headers=new_headers).status_code == 401



def test_reviews_require_owned_delivered_order_and_a_product_from_that_order(engine, world, client_for):
    _seed_store(engine, world["org_a"], world["product_a"], "shop-a", "Shop A")
    client, _ = client_for("owner")
    token, headers = _register(client)
    placed = client.post(f"/api/public/orders/{world['org_a']}", json={
        "shipping_name": "Demo Buyer", "shipping_phone": "01711111111",
        "shipping_address": "Sample address only",
        "items": [{"product_id": world["product_a"], "quantity": 1}],
        "store_customer_token": token,
    })
    assert placed.status_code == 200, placed.text
    order_id = placed.json()["id"]
    review_body = {
        "product_id": world["product_a"], "order_id": order_id,
        "rating": 5, "comment": "Sample review",
    }
    assert client.post(f"/api/public/reviews/{world['org_a']}", headers=headers, json=review_body).status_code == 409

    with Session(engine) as db:
        order = db.get(SalesDocument, order_id)
        order.status = "delivered"
        foreign_product = Product(
            organization_id=world["org_a"], sku="NOT-ORDERED", name="Not ordered",
            selling_price=Decimal("10"), cost_price=Decimal("5"),
        )
        db.add(foreign_product)
        db.commit()
        foreign_product_id = foreign_product.id

    not_purchased = {**review_body, "product_id": foreign_product_id}
    assert client.post(f"/api/public/reviews/{world['org_a']}", headers=headers, json=not_purchased).status_code == 403
    accepted = client.post(f"/api/public/reviews/{world['org_a']}", headers=headers, json=review_body)
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["rating"] == 5


def test_account_cannot_read_or_edit_another_customers_address(world, client_for):
    client, _ = client_for("owner")
    _, owner_headers = _register(client)
    _, other_headers = _register(client, "other@example.com", "01722222222")
    created = client.post("/api/sc/addresses", headers=owner_headers, json={
        "label": "বাড়ি", "recipient_name": "Demo Buyer", "phone": "01711111111",
        "division": "ঢাকা", "district": "ঢাকা", "address_detail": "Sample address",
    }).json()
    assert client.patch(f"/api/sc/addresses/{created['id']}", headers=other_headers, json={"label": "চুরি"}).status_code == 404
    assert client.delete(f"/api/sc/addresses/{created['id']}", headers=other_headers).status_code == 404
