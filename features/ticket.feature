Feature: The parking ticket
  A parking ticket read from the webcam becomes a filled pay-or-contest page
  in a visible browser with Pay or Contest on the card. Pay fills the card on
  file and pauses before submit; Contest turns the spoken reason into a
  one-paragraph letter and pauses before submit. Nothing is submitted until
  the user taps Confirm, and walking away leaves it paused forever. Serves
  N1 and N2.

  Background:
    Given the Handled web app is open on the laptop with the webcam live
    And the user has held up a Los Angeles parking ticket for citation 4512087733 on plate 8ABC123 issued 2026-10-12 and due 2026-11-02

  @D9
  Scenario: The city's page is filled and the card offers Pay or Contest
    When the ticket chore begins
    Then the user sees the browser on the Los Angeles pay-or-contest page with citation 4512087733 and plate 8ABC123 filled in
    And the user sees the card offer "Pay" and "Contest" with the deadline 2026-11-02

  @D10
  Scenario Outline: A step that fails submits nothing and leaves the page open
    Given <fault>
    When the ticket chore begins
    Then the user sees on the card "<failed step>"
    And the user sees the browser still open on <last page>
    And the city's records show nothing submitted for citation 4512087733

    Examples:
      | fault                                                    | failed step                                      | last page                              |
      | the city's page does not answer                          | Could not reach the Los Angeles citation page    | the blank tab it tried to open         |
      | the city's page finds no citation 4512087733             | Citation 4512087733 was not found                | the city's lookup page                 |
      | the city's page demands a login before showing the citation | The city's page asks for a login                  | the city's login page                  |

  @D11
  Scenario: Pay fills the card on file and pauses before submit
    Given the pay-or-contest page is filled
    When the user taps "Pay"
    Then the user sees the browser on the city's payment page with the card on file filled in and the amount $73.00
    And the user sees the Confirm control on the card
    And the city's records show nothing paid for citation 4512087733

  @D12
  Scenario: Contest writes a letter from the spoken reason and pauses before submit
    Given the pay-or-contest page is filled
    When the user taps "Contest" and says "the meter was broken, I put in two dollars and it never started"
    Then the user sees on the card a one-paragraph letter that mentions the broken meter and the two dollars
    And the user sees the browser on the city's contest form with that letter pasted in
    And the user sees the Confirm control on the card
    And the city's records show no contest filed for citation 4512087733

  @D7
  Scenario: Confirm completes the step and the card says so
    Given the browser is paused on the city's payment page with the Confirm control showing
    When the user taps Confirm
    Then the city's records show citation 4512087733 paid
    And the user sees on the card "Paid citation 4512087733"

  @D7
  Scenario: Saying yes counts as Confirm
    Given the browser is paused on the city's contest form with the Confirm control showing
    When the user says "yes"
    Then the city's records show a contest filed for citation 4512087733
    And the user sees on the card "Contest filed for citation 4512087733"

  @D6
  Scenario Outline: Walking away leaves the page paused forever
    Given the browser is paused on the city's payment page with the Confirm control showing
    When <time> passes with no tap and no word from the user
    Then the user sees the browser still paused on the city's payment page with the Confirm control showing
    And the city's records show nothing paid for citation 4512087733

    Examples:
      | time       |
      | 1 minute   |
      | 1 hour     |
      | 3 days     |

  @D13
  Scenario Outline: A ticket with no printed due date is due twenty-one days after issue
    Given the user has held up a Los Angeles parking ticket for citation 4512087734 issued <issued> with no due date printed
    When the ticket chore begins
    Then the user sees the card offer "Pay" and "Contest" with the deadline <deadline>
    And the user sees on the card "counted 21 days from the issue date"

    Examples:
      | issued     | deadline   |
      | 2026-10-12 | 2026-11-02 |
      | 2026-10-31 | 2026-11-21 |
      | 2026-12-20 | 2027-01-10 |
      | 2028-02-10 | 2028-03-02 |
