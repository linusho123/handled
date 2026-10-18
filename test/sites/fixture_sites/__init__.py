"""The fixture sites the test server hosts under /sites/<site>/… (BUILD-PLAN.md, P0).

la-citations (the city's citation portal), ladwp (the biller), and the three
store fronts target, walmart and amazon. Each site keeps a ledger, its far
side: the ledger is appended to only by that site's own submit, pay or order
route, when a form actually posts to it, never by a page visit and never by
the app. Faults (and a store's prices) are set per scenario through
POST /test/sites; a reset empties every ledger, fault, price and cart. Nothing
is pre-seeded: a store with no price set lists nothing.
"""

from __future__ import annotations

from fastapi import APIRouter

from fixture_sites.base import Site, SiteError
from fixture_sites.la_citations import CitySite
from fixture_sites.ladwp import BillerSite
from fixture_sites.stores import StoreSite


class Sites:
    def __init__(self) -> None:
        self.by_name: dict[str, Site] = {
            "la-citations": CitySite(),
            "ladwp": BillerSite(),
            "target": StoreSite("target", "Target"),
            "walmart": StoreSite("walmart", "Walmart"),
            "amazon": StoreSite("amazon", "Amazon"),
        }

    def __getitem__(self, name: str) -> Site:
        if name not in self.by_name:
            raise SiteError(f"no fixture site {name!r}; the sites are {', '.join(self.by_name)}")
        return self.by_name[name]

    def reset(self) -> None:
        for site in self.by_name.values():
            site.reset()

    def router(self) -> APIRouter:
        router = APIRouter()
        for name, site in self.by_name.items():
            router.include_router(site.router(), prefix=f"/sites/{name}")
        return router


__all__ = ["Site", "SiteError", "Sites"]
