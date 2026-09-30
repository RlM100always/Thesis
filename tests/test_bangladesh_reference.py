def test_bangladesh_reference_contains_official_complete_location_and_mfs_lists(client_for):
    client, _ = client_for("owner")
    response = client.get("/api/reference/bangladesh")
    assert response.status_code == 200
    data = response.json()
    assert len(data["divisions"]) == 8
    assert len(data["districts"]) == 64
    assert len(data["mfs_providers"]) == 14
    dhaka = next(row for row in data["districts"] if row["code"] == "BD3026")
    assert dhaka["label_bn"] == "ঢাকা" and dhaka["parent_code"] == "dhaka"
    assert all(row["source_url"].startswith("https://") and row["verified_on"] for row in data["districts"])
    assert {row["code"] for row in data["mfs_providers"]} >= {"bkash", "nagad", "rocket", "upay"}
