Feature: The report
  At the end of a chore, whether completed, paused at Confirm or stopped at
  a failed step, the card says what was identified, what was done, the
  deadline and a link to the page, and the phone gets one text with the
  same. A chore with a deadline gets a second text the day before it; a
  product gets none. Serves N1.

  Background:
    Given the Handled web app is open on the laptop with the webcam live

  @D19
  Scenario Outline: Every ending is reported on the card and in one text
    Given the user has held up <thing>
    And the chore has <ended>
    When the chore ends
    Then the user sees a card with <identified>, "<done>", <deadline> and a link to the page the browser is on
    And the user's phone receives one text saying "<done>" with <deadline>

    Examples:
      | thing                                                                  | ended                                          | identified                        | done                                              | deadline        |
      | a Los Angeles parking ticket for citation 4512087733 due 2026-11-02   | been confirmed as paid                          | citation 4512087733               | Paid citation 4512087733                           | 2026-11-02      |
      | a Los Angeles parking ticket for citation 4512087733 due 2026-11-02   | paused at Confirm on the payment page           | citation 4512087733               | Ready to pay citation 4512087733, waiting for you  | 2026-11-02      |
      | a Los Angeles parking ticket for citation 4512087733 due 2026-11-02   | stopped because the city's page did not answer  | citation 4512087733               | Could not reach the Los Angeles citation page      | 2026-11-02      |
      | an LADWP bill for $148.22 due 2026-11-05 on account 1234567890          | paused at Confirm on the payment page           | LADWP $148.22                     | Ready to pay LADWP $148.22, waiting for you        | 2026-11-05      |
      | a 32 oz bottle of Cholula Original hot sauce                          | been confirmed as ordered from Walmart at $8.98 | Cholula Original hot sauce, 32 oz | Ordered from Walmart, $8.98                        | no deadline     |

  @D20
  Scenario Outline: The day before a deadline brings a second text
    Given the user has held up <thing> and the chore was reported with the deadline <deadline>
    When the clock reaches 9:00 in the morning on <day before>
    Then the user's phone receives a second text naming <chore> and saying the deadline is tomorrow

    Examples:
      | thing                                                                 | deadline   | day before | chore                |
      | a Los Angeles parking ticket for citation 4512087733 due 2026-11-02  | 2026-11-02 | 2026-11-01 | citation 4512087733  |
      | an LADWP bill for $148.22 due 2026-11-05 on account 1234567890         | 2026-11-05 | 2026-11-04 | the LADWP bill       |
      | a Los Angeles parking ticket for citation 4512087735 due 2026-10-19  | 2026-10-19 | 2026-10-18 | citation 4512087735  |

  @D21
  Scenario: A product gets no second text
    Given the user has held up a 32 oz bottle of Cholula Original hot sauce and the chore was reported with no deadline
    When 30 days pass
    Then the user's phone receives no second text
