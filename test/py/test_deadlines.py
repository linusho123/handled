"""D9, D13: the printed due date, else the printed issue date plus 21 days, never today."""

import pytest

from app.desk.deadlines import COUNTED_FROM_ISSUE, TICKET_DAYS_FROM_ISSUE, ticket_deadline


def test_the_printed_due_date_is_the_deadline():
    assert ticket_deadline({"issued": "2026-10-12", "due": "2026-11-02"}) == ("2026-11-02", None)


@pytest.mark.parametrize(
    "issued, deadline",
    [("2026-10-12", "2026-11-02"), ("2026-10-31", "2026-11-21"), ("2026-12-20", "2027-01-10"), ("2028-02-10", "2028-03-02")],
)
def test_no_printed_due_date_counts_21_days_from_the_issue_date(issued, deadline):
    assert TICKET_DAYS_FROM_ISSUE == 21
    assert ticket_deadline({"issued": issued, "due": None}) == (deadline, COUNTED_FROM_ISSUE)
    assert COUNTED_FROM_ISSUE == "counted 21 days from the issue date"
