"""Harness honesty for the fixture sites: each ledger is written only by that site's own
submit, pay or order route on a real form post; visiting pages writes nothing."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fixture_sites import Sites, SiteError

CARD = {"card_number": "4242 4242 4242 4242", "card_expiry": "12/30", "card_cvc": "123"}
SHIP = {"ship_name": "Pat User", "ship_street": "1 Main St", "ship_city": "Los Angeles", "ship_state": "CA", "ship_zip": "90001"}


@pytest.fixture
def sites():
    return Sites()


@pytest.fixture
def client(sites):
    api = FastAPI()
    api.include_router(sites.router())
    return TestClient(api, follow_redirects=False)


def ledgers(sites):
    return {name: site.ledger for name, site in sites.by_name.items()}


EMPTY = {"la-citations": [], "ladwp": [], "target": [], "walmart": [], "amazon": []}


def test_every_ledger_starts_empty(sites):
    assert ledgers(sites) == EMPTY


def test_visiting_every_page_writes_no_ledger(sites, client):
    for store in ("target", "walmart", "amazon"):
        sites[store].set_prices({"cholula-original-32oz": "9.49", "cholula-original-12oz": "4.99"})
    paths = [
        "/sites/la-citations/",
        "/sites/la-citations/lookup?citation=4512087733&plate=8ABC123",
        "/sites/la-citations/pay?citation=4512087733",
        "/sites/la-citations/contest?citation=4512087733",
        "/sites/la-citations/login",
        "/sites/ladwp/",
        "/sites/ladwp/pay",
        "/sites/ladwp/login",
    ]
    for store in ("target", "walmart", "amazon"):
        paths += [f"/sites/{store}/", f"/sites/{store}/search?q=cholula", f"/sites/{store}/product/cholula-original-32oz", f"/sites/{store}/cart", f"/sites/{store}/checkout"]
    for path in paths:
        assert client.get(path).status_code == 200, path
    assert ledgers(sites) == EMPTY


def test_city_pay_route_records_the_payment_and_nothing_else(sites, client):
    r = client.post("/sites/la-citations/pay", data={"citation": "4512087733", **CARD})
    assert r.status_code == 200
    assert sites["la-citations"].ledger == [{"kind": "payment", "citation": "4512087733", "amount": "73.00", "card_last4": "4242", "card_name": ""}]
    assert {k: v for k, v in ledgers(sites).items() if k != "la-citations"} == {k: [] for k in EMPTY if k != "la-citations"}


def test_city_contest_route_records_the_letter(sites, client):
    r = client.post("/sites/la-citations/contest", data={"citation": "4512087733", "letter": "The meter was broken."})
    assert r.status_code == 200
    assert sites["la-citations"].ledger == [{"kind": "contest", "citation": "4512087733", "letter": "The meter was broken."}]


def test_biller_pay_route_records_the_payment(sites, client):
    r = client.post("/sites/ladwp/pay", data={"account": "1234567890", "amount": "$148.22", **CARD})
    assert r.status_code == 200
    assert sites["ladwp"].ledger == [{"kind": "payment", "account": "1234567890", "amount": "148.22", "card_last4": "4242", "card_name": ""}]


def test_store_cart_records_nothing_and_order_records_the_order(sites, client):
    sites["walmart"].set_prices({"cholula-original-32oz": "$8.98"})
    assert client.post("/sites/walmart/cart", data={"slug": "cholula-original-32oz"}).status_code == 303
    assert sites["walmart"].ledger == []
    assert client.post("/sites/walmart/order", data={**SHIP, **CARD}).status_code == 200
    (entry,) = sites["walmart"].ledger
    assert entry["kind"] == "order"
    assert entry["items"] == [{"slug": "cholula-original-32oz", "name": "Cholula Original Hot Sauce, 32 oz", "price": "8.98"}]
    assert entry["total"] == "8.98"
    assert sites["target"].ledger == [] and sites["amazon"].ledger == []


def test_an_order_with_an_empty_cart_records_nothing(sites, client):
    sites["target"].set_prices({"cholula-original-32oz": "9.49"})
    assert client.post("/sites/target/order", data={**SHIP, **CARD}).status_code == 400
    assert sites["target"].ledger == []


@pytest.mark.parametrize("path,data", [
    ("/sites/la-citations/pay", {"citation": "4512087733", "card_number": "x", "card_expiry": "12/30", "card_cvc": "1"}),
    ("/sites/la-citations/pay", {"citation": "9999999999", **CARD}),
    ("/sites/la-citations/contest", {"citation": "4512087733", "letter": "   "}),
    ("/sites/ladwp/pay", {"account": " ", "amount": "1", **CARD}),
])
def test_an_incomplete_or_unknown_form_records_nothing(sites, client, path, data):
    assert client.post(path, data=data).status_code in (400, 404)
    assert ledgers(sites) == EMPTY


def test_a_json_post_is_not_a_form_post(sites, client):
    assert client.post("/sites/la-citations/pay", json={"citation": "4512087733", **CARD}).status_code == 422
    assert ledgers(sites) == EMPTY


@pytest.mark.parametrize("fault", ["down", "login"])
def test_a_faulted_city_records_no_payment(sites, client, fault):
    sites["la-citations"].set_fault(fault)
    assert client.post("/sites/la-citations/pay", data={"citation": "4512087733", **CARD}).status_code in (303, 503)
    assert client.post("/sites/la-citations/contest", data={"citation": "4512087733", "letter": "x"}).status_code in (303, 503)
    assert ledgers(sites) == EMPTY


@pytest.mark.parametrize("fault", ["down", "login", "nopage"])
def test_a_faulted_biller_records_no_payment(sites, client, fault):
    sites["ladwp"].set_fault(fault)
    assert client.post("/sites/ladwp/pay", data={"account": "1234567890", "amount": "148.22", **CARD}).status_code in (303, 404, 503)
    assert ledgers(sites) == EMPTY


def test_city_faults(sites, client):
    lookup = "/sites/la-citations/lookup?citation=4512087733&plate=8ABC123"
    assert client.get(lookup).status_code == 200
    assert client.get("/sites/la-citations/lookup?citation=4512087733&plate=WRONG1").status_code == 404
    sites["la-citations"].set_fault("down")
    r = client.get(lookup)
    assert (r.status_code, r.content) == (503, b"")
    sites["la-citations"].set_fault("notfound")
    r = client.get(lookup)
    assert r.status_code == 404 and "Citation 4512087733 was not found" in r.text
    sites["la-citations"].set_fault("login")
    r = client.get(lookup)
    assert (r.status_code, r.headers["location"]) == (303, "/sites/la-citations/login")
    assert client.get("/sites/la-citations/login").status_code == 200


def test_biller_faults(sites, client):
    sites["ladwp"].set_fault("nopage")
    assert client.get("/sites/ladwp/pay").status_code == 404
    assert "Pay my bill" not in client.get("/sites/ladwp/").text
    sites["ladwp"].set_fault("down")
    assert (client.get("/sites/ladwp/").status_code, client.get("/sites/ladwp/").content) == (503, b"")


@pytest.mark.parametrize("store", ["target", "walmart", "amazon"])
def test_head_1_a_down_store_answers_nothing(sites, client, store):
    # head-1: a store page that does not answer is how a product chore ends at a failed
    # step before P3 (D19, D21): `down` answers every store page with an empty 503.
    sites[store].set_prices({"cholula-original-32oz": "8.98"})
    sites[store].set_fault("down")
    for path in ["/", "/search?q=cholula", "/product/cholula-original-32oz", "/cart", "/checkout"]:
        r = client.get(f"/sites/{store}{path}")
        assert (r.status_code, r.content) == (503, b""), path
    r = client.post(f"/sites/{store}/cart", data={"slug": "cholula-original-32oz"})
    assert (r.status_code, r.content) == (503, b"")
    assert ledgers(sites) == EMPTY


def test_a_store_lists_only_at_a_set_price(sites, client):
    assert "No results" in client.get("/sites/amazon/search?q=cholula").text
    assert client.get("/sites/amazon/product/cholula-original-32oz").status_code == 404
    sites["amazon"].set_prices({"cholula-original-32oz": "10.99"})
    r = client.get("/sites/amazon/search?q=cholula original 32 oz")
    assert "Cholula Original Hot Sauce, 32 oz" in r.text and "$10.99" in r.text and "12 oz" not in r.text
    sites["amazon"].set_fault("nolisting")
    assert "No results" in client.get("/sites/amazon/search?q=cholula").text


def test_unknown_faults_sites_and_products_are_refused(sites):
    with pytest.raises(SiteError):
        sites["nowhere"]
    with pytest.raises(SiteError):
        sites["ladwp"].set_fault("notfound")
    with pytest.raises(SiteError):
        sites["target"].set_prices({"sriracha": "3.00"})
    with pytest.raises(SiteError):
        sites["target"].set_prices({"cholula-original-32oz": "-1"})


def test_reset_empties_ledgers_faults_prices_and_carts(sites, client):
    sites["walmart"].set_prices({"cholula-original-32oz": "8.98"})
    client.post("/sites/walmart/cart", data={"slug": "cholula-original-32oz"})
    client.post("/sites/walmart/order", data={**SHIP, **CARD})
    client.post("/sites/la-citations/pay", data={"citation": "4512087733", **CARD})
    # head-2: a cart that is full when the reset comes, in two stores, so the reset
    # (and nothing else) is what empties it.
    for store in ("walmart", "amazon"):
        sites[store].set_prices({"cholula-original-32oz": "8.98"})
        assert client.post(f"/sites/{store}/cart", data={"slug": "cholula-original-32oz"}).status_code == 303
        assert sites[store].cart == ["cholula-original-32oz"]
        assert "cart-item" in client.get(f"/sites/{store}/cart").text
    sites["la-citations"].set_fault("down")
    sites["walmart"].set_fault("nolisting")
    sites.reset()
    assert ledgers(sites) == EMPTY
    assert all(site.fault is None for site in sites.by_name.values())
    for store in ("target", "walmart", "amazon"):
        assert sites[store].prices == {} and sites[store].cart == []
        assert "cart-item" not in client.get(f"/sites/{store}/cart").text
        assert "cart-item" not in client.get(f"/sites/{store}/checkout").text


def test_head_2_a_cart_kept_through_a_reset_places_no_order(sites, client):
    # The next scenario sets the same price; a cart the reset kept would let it order
    # an item the scenario never put in the cart.
    sites["target"].set_prices({"cholula-original-32oz": "9.49"})
    assert client.post("/sites/target/cart", data={"slug": "cholula-original-32oz"}).status_code == 303
    sites.reset()
    sites["target"].set_prices({"cholula-original-32oz": "9.49"})
    assert client.post("/sites/target/order", data={**SHIP, **CARD}).status_code == 400
    assert ledgers(sites) == EMPTY


@pytest.mark.parametrize("change", ["only-another-product-priced", "no-prices", "nolisting"])
def test_contract_1_an_order_for_an_item_the_store_no_longer_lists_records_nothing(sites, client, change):
    sites["walmart"].set_prices({"cholula-original-32oz": "8.98"})
    assert client.post("/sites/walmart/cart", data={"slug": "cholula-original-32oz"}).status_code == 303
    if change == "only-another-product-priced":
        sites["walmart"].set_prices({"cholula-original-12oz": "4.99"})
    elif change == "no-prices":
        sites["walmart"].set_prices({})
    else:
        sites["walmart"].set_fault("nolisting")
    assert client.post("/sites/walmart/order", data={**SHIP, **CARD}).status_code == 400
    assert ledgers(sites) == EMPTY


def test_contract_1_an_order_with_any_item_no_longer_listed_records_nothing(sites, client):
    sites["walmart"].set_prices({"cholula-original-32oz": "8.98", "cholula-original-12oz": "4.99"})
    assert client.post("/sites/walmart/cart", data={"slug": "cholula-original-32oz"}).status_code == 303
    assert client.post("/sites/walmart/cart", data={"slug": "cholula-original-12oz"}).status_code == 303
    sites["walmart"].set_prices({"cholula-original-12oz": "4.99"})
    assert client.post("/sites/walmart/order", data={**SHIP, **CARD}).status_code == 400
    assert ledgers(sites) == EMPTY


@pytest.mark.parametrize("price", ["NaN", "sNaN", "Infinity", "-Infinity", "1e40"])
def test_risk_1_a_price_that_is_not_a_finite_amount_is_refused(sites, price):
    with pytest.raises(SiteError):
        sites["walmart"].set_prices({"cholula-original-32oz": price})
    assert sites["walmart"].prices == {}


@pytest.mark.parametrize("fault", [["x"], {"a": 1}, 3, True])
def test_risk_1_a_fault_that_is_not_a_name_is_refused(sites, fault):
    with pytest.raises(SiteError):
        sites["ladwp"].set_fault(fault)
    assert sites["ladwp"].fault is None
