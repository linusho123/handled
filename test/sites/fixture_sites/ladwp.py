"""ladwp: the Los Angeles Department of Water and Power's bill payment, as a fixture.

  GET  /        the home page, with a link to pay
  GET  /pay     the payment page: account, amount, card fields
  POST /pay     pays: the ledger records {"kind": "payment", …}
  GET/POST /login the login wall (fault `login`)

Faults: `down` (every page answers nothing), `nopage` (there is no payment
page: /pay is not found and home offers no link), `login` (every page goes
to the login wall).
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import Response

from fixture_sites.base import Site, esc, last4, page

TITLE = "LADWP - Los Angeles Department of Water and Power"


class BillerSite(Site):
    name = "ladwp"
    title = TITLE
    faults = frozenset({"down", "nopage", "login"})

    def router(self) -> APIRouter:
        r = APIRouter()

        @r.get("/")
        def home(request: Request) -> Response:
            if blocked := self.fault_response(request):
                return blocked
            link = "" if self.fault == "nopage" else "<a id='pay' href='/sites/ladwp/pay'>Pay my bill</a>"
            return page(TITLE, f"<p>Water and power for Los Angeles.</p>{link}")

        @r.get("/pay")
        def pay_form(request: Request) -> Response:
            if blocked := self.fault_response(request):
                return blocked
            if self.fault == "nopage":
                return page(f"{TITLE} - Page not found", "<p>Page not found.</p>", 404)
            return page(
                f"{TITLE} - Pay my bill",
                "<form method='post' action='/sites/ladwp/pay'>"
                "<label>Account number <input name='account' id='account'></label>"
                "<label>Amount <input name='amount' id='amount'></label>"
                "<label>Name on card <input name='card_name' id='card_name'></label>"
                "<label>Card number <input name='card_number' id='card_number'></label>"
                "<label>Expiry <input name='card_expiry' id='card_expiry'></label>"
                "<label>CVC <input name='card_cvc' id='card_cvc'></label>"
                "<button type='submit' id='submit'>Pay now</button></form>",
            )

        @r.post("/pay")
        def pay(
            request: Request,
            account: str = Form(...),
            amount: str = Form(...),
            card_number: str = Form(...),
            card_expiry: str = Form(...),
            card_cvc: str = Form(...),
            card_name: str = Form(""),
        ) -> Response:
            if blocked := self.fault_response(request):
                return blocked
            if self.fault == "nopage":
                return page(f"{TITLE} - Page not found", "<p>Page not found.</p>", 404)
            if not (account.strip() and amount.strip() and last4(card_number) and card_expiry.strip() and card_cvc.strip()):
                return page(f"{TITLE} - Payment incomplete", "<p role='alert'>Every field is required.</p>", 400)
            paid = amount.strip().lstrip("$")
            self.record({"kind": "payment", "account": account.strip(), "amount": paid, "card_last4": last4(card_number), "card_name": card_name.strip()})
            return page(f"{TITLE} - Payment received", f"<p id='receipt'>Paid ${esc(paid)} on account {esc(account.strip())}.</p>")

        @r.get("/login")
        def login(request: Request) -> Response:
            return self.fault_response(request) or self.login_page()

        @r.post("/login")
        def login_post(request: Request) -> Response:
            return self.fault_response(request) or self.login_page()

        return r
