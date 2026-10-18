Feature: The product
  A product read from the webcam is searched at three stores, each in its
  own tab, and the card ranks the prices cheapest first with Buy on the
  cheapest. Buy goes to that store's checkout with the Visa on file and
  pauses before placing the order. Serves N1 and N2.

  Background:
    Given the Handled web app is open on the laptop with the webcam live
    And the user has held up a 32 oz bottle of Cholula Original hot sauce

  @D16
  Scenario Outline: Prices from three stores are ranked cheapest first
    Given Target lists the 32 oz Cholula Original at <target>
    And Walmart lists it at <walmart>
    And Amazon lists it at <amazon>
    When the product chore begins
    Then the user sees three browser tabs, one per store, each on the product's page
    And the user sees the card rank the stores <ranking>
    And the user sees the Buy control on <cheapest>

    Examples:
      | target | walmart | amazon | ranking                 | cheapest |
      | $9.49  | $8.98   | $10.99 | Walmart, Target, Amazon | Walmart  |
      | $8.98  | $8.98   | $10.99 | Target, Walmart, Amazon | Target   |
      | $0.01  | $8.98   | $10.99 | Target, Walmart, Amazon | Target   |
      | $999.00 | $8.98  | $10.99 | Walmart, Amazon, Target | Walmart  |

  @D17
  Scenario: A store without the product is listed as not found
    Given Target lists the 32 oz Cholula Original at $9.49
    And Walmart does not list it
    And Amazon lists it at $10.99
    When the product chore begins
    Then the user sees the card rank Target then Amazon with Walmart marked "not found"
    And the user sees the Buy control on Target

  @D17
  Scenario: No store with the product means no Buy control
    Given none of Target, Walmart and Amazon lists the 32 oz Cholula Original
    When the product chore begins
    Then the user sees on the card "Not found at Target, Walmart or Amazon"
    And the user sees no Buy control

  @D18
  Scenario: Buy goes to checkout with the Visa on file and pauses
    Given the card ranks Walmart cheapest at $8.98 with the Buy control on it
    When the user taps Buy
    Then the user sees the browser on Walmart's checkout with the 32 oz Cholula Original in the cart, the shipping address filled and the Visa on file filled
    And the user sees the Confirm control on the card
    And Walmart's records show no order placed

  @D7
  Scenario: Confirm places the order and the card says so
    Given the browser is paused on Walmart's checkout with the Confirm control showing
    When the user taps Confirm
    Then Walmart's records show one order for the 32 oz Cholula Original
    And the user sees on the card "Ordered from Walmart, $8.98"
