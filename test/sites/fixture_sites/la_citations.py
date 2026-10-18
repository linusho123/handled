"""la-citations: the city of Los Angeles's citation portal, as a fixture.

  GET  /                 the lookup form (citation, plate)
  GET  /lookup           the citation's page (the pay-or-contest page): the lookup form keeping the
                         citation and plate the browser submitted, the citation, Pay and Contest;
                         or "not found" on the lookup page
  GET  /pay?citation=    the payment form: the amount set by the city, the card fields
  POST /pay              pays: the ledger records {"kind": "payment", …}
  GET  /contest?citation= the contest form with a letter box
  POST /contest          files: the ledger records {"kind": "contest", …}
  GET/POST /login        the login wall (fault `login`); posting it signs no one in

Faults: `down` (every page answers nothing), `notfound` (no citation is ever
found), `login` (every page goes to the login wall).
"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

from fixture_sites.base import Site, esc, last4, page

# The city's own records of the citations the scenarios name. The city sets the amount.
CITATIONS: dict[str, dict[str, str]] = {
    "4512087733": {"plate": "8ABC123", "amount": "73.00"},
    "4512087734": {"plate": "8ABC123", "amount": "73.00"},
    "4512087735": {"plate": "8ABC123", "amount": "73.00"},
}

TITLE = "City of Los Angeles - Parking Citations"
# The demo's browser reads like the real Parking Violations Bureau page (styled after it, 2026-10-18).
BRAND = "Parking Violations Bureau <small>City of Los Angeles &middot; Moving Los Angeles Forward</small>"
BRAND_COLOR = "#0b3d91"


def city_page(title: str, body: str, status: int = 200) -> HTMLResponse:
    return page(title, body, status, brand=BRAND, color=BRAND_COLOR)


class CitySite(Site):
    name = "la-citations"
    title = TITLE
    faults = frozenset({"down", "notfound", "login"})

    def _find(self, citation: str, plate: str | None = None) -> dict[str, str] | None:
        if self.fault == "notfound":
            return None
        record = CITATIONS.get(citation.strip())
        if record is None or (plate is not None and plate.strip().upper() != record["plate"]):
            return None
        return record

    @staticmethod
    def _form(citation: str = "", plate: str = "") -> str:
        # Like any search box, the form keeps what was submitted to it.
        return (
            "<form method='get' action='/sites/la-citations/lookup'>"
            f"<label>Citation number <input name='citation' id='citation' value='{esc(citation)}'></label>"
            f"<label>License plate <input name='plate' id='plate' value='{esc(plate)}'></label>"
            "<button type='submit' id='lookup'>Look up</button></form>"
        )

    def _lookup_form(self, message: str = "", status: int = 200, citation: str = "", plate: str = "") -> HTMLResponse:
        note = f"<p class='error' role='alert'>{esc(message)}</p>" if message else ""
        return city_page(f"{TITLE} - Look up a citation", note + self._form(citation, plate), status)

    def router(self) -> APIRouter:
        r = APIRouter()

        @r.get("/")
        def home(request: Request) -> Response:
            return self.fault_response(request) or self._lookup_form()

        @r.get("/lookup")
        def lookup(request: Request, citation: str = "", plate: str = "") -> Response:
            if blocked := self.fault_response(request):
                return blocked
            record = self._find(citation, plate)
            if record is None:
                return self._lookup_form(f"Citation {citation} was not found", status=404, citation=citation, plate=plate)
            c = esc(citation.strip())
            return city_page(
                f"{TITLE} - Citation {citation.strip()}",
                self._form(citation, plate) + f"<dl><dt>Citation</dt><dd id='citation-number'>{c}</dd>"
                f"<dt>Plate</dt><dd id='plate-number'>{esc(record['plate'])}</dd>"
                f"<dt>Amount due</dt><dd id='amount'>${esc(record['amount'])}</dd></dl>"
                f"<a class='button' id='pay' href='/sites/la-citations/pay?citation={c}'>Pay</a> "
                f"<a class='button' id='contest' href='/sites/la-citations/contest?citation={c}'>Contest</a>",
            )

        @r.get("/pay")
        def pay_form(request: Request, citation: str = "") -> Response:
            if blocked := self.fault_response(request):
                return blocked
            record = self._find(citation)
            if record is None:
                return self._lookup_form(f"Citation {citation} was not found", status=404)
            c = esc(citation.strip())
            return city_page(
                f"{TITLE} - Pay citation {citation.strip()}",
                "<form method='post' action='/sites/la-citations/pay'>"
                f"<input type='hidden' name='citation' value='{c}'>"
                f"<label>Amount <input name='amount' id='amount' value='${esc(record['amount'])}' readonly></label>"
                "<label>Name on card <input name='card_name' id='card_name'></label>"
                "<label>Card number <input name='card_number' id='card_number'></label>"
                "<label>Expiry <input name='card_expiry' id='card_expiry'></label>"
                "<label>CVC <input name='card_cvc' id='card_cvc'></label>"
                "<button type='submit' id='submit'>Pay now</button></form>",
            )

        @r.post("/pay")
        def pay(
            request: Request,
            citation: str = Form(...),
            card_number: str = Form(...),
            card_expiry: str = Form(...),
            card_cvc: str = Form(...),
            card_name: str = Form(""),
        ) -> Response:
            if blocked := self.fault_response(request):
                return blocked
            record = self._find(citation)
            if record is None:
                return self._lookup_form(f"Citation {citation} was not found", status=404)
            if not (last4(card_number) and card_expiry.strip() and card_cvc.strip()):
                return city_page(f"{TITLE} - Payment declined", "<p role='alert'>Card details are incomplete.</p>", 400)
            self.record({"kind": "payment", "citation": citation.strip(), "amount": record["amount"], "card_last4": last4(card_number), "card_name": card_name.strip()})
            return city_page(f"{TITLE} - Payment received", f"<p id='receipt'>Citation {esc(citation.strip())} paid, ${esc(record['amount'])}.</p>")

        @r.get("/contest")
        def contest_form(request: Request, citation: str = "") -> Response:
            if blocked := self.fault_response(request):
                return blocked
            if self._find(citation) is None:
                return self._lookup_form(f"Citation {citation} was not found", status=404)
            c = esc(citation.strip())
            return city_page(
                f"{TITLE} - Contest citation {citation.strip()}",
                "<form method='post' action='/sites/la-citations/contest'>"
                f"<input type='hidden' name='citation' value='{c}'>"
                "<label>Your statement <textarea name='letter' id='letter' rows='8' cols='80'></textarea></label>"
                "<button type='submit' id='submit'>Submit contest</button></form>",
            )

        @r.post("/contest")
        def contest(request: Request, citation: str = Form(...), letter: str = Form(...)) -> Response:
            if blocked := self.fault_response(request):
                return blocked
            if self._find(citation) is None:
                return self._lookup_form(f"Citation {citation} was not found", status=404)
            if not letter.strip():
                return city_page(f"{TITLE} - Contest incomplete", "<p role='alert'>A statement is required.</p>", 400)
            self.record({"kind": "contest", "citation": citation.strip(), "letter": letter.strip()})
            return city_page(f"{TITLE} - Contest received", f"<p id='receipt'>Contest filed for citation {esc(citation.strip())}.</p>")

        @r.get("/login")
        def login(request: Request) -> Response:
            return self.fault_response(request) or self.login_page()

        @r.post("/login")
        def login_post(request: Request) -> Response:
            return self.fault_response(request) or self.login_page()

        return r
