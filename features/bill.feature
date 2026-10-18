Feature: The bill
  A bill or letter with a due date read from the webcam becomes a filled
  payment page in a visible browser, paused before paying. When no payment
  page can be reached, the card shows the phone number printed on the bill
  instead. Serves N1 and N2.

  Background:
    Given the Handled web app is open on the laptop with the webcam live
    And the user has held up an LADWP bill for $148.22 due 2026-11-05 on account 1234567890 with the phone number 1-800-342-5397 printed on it

  @D14
  Scenario: The payment page is filled and paused before paying
    When the bill chore begins
    Then the user sees the browser on the LADWP payment page with account 1234567890 and the amount $148.22 filled in
    And the user sees the Confirm control on the card
    And the user sees on the card LADWP, $148.22 and the due date 2026-11-05
    And the biller's records show nothing paid on account 1234567890

  @D15
  Scenario Outline: No reachable payment page means the card shows the number to call
    Given <fault>
    When the bill chore begins
    Then the user sees on the card "call to pay" with 1-800-342-5397
    And the user sees the browser still open on <last page>
    And the biller's records show nothing paid on account 1234567890

    Examples:
      | fault                                            | last page                           |
      | no payment page for LADWP can be found           | the search results it tried         |
      | the LADWP payment page does not answer           | the blank tab it tried to open      |
      | the LADWP payment page demands a login           | the biller's login page             |

  @D7
  Scenario: Confirm pays the bill and the card says so
    Given the browser is paused on the LADWP payment page with the Confirm control showing
    When the user taps Confirm
    Then the biller's records show $148.22 paid on account 1234567890
    And the user sees on the card "Paid LADWP $148.22"
