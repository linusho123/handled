Feature: Identifying the thing
  The user holds a parking ticket, a bill or a product up to the laptop's
  webcam. Within five seconds the card names it and reads its fields, and the
  chore for that kind begins in a visible browser; anything else gets "Hold
  it closer" and nothing happens. Serves N1.

  Background:
    Given the Handled web app is open on the laptop with the webcam live and nothing in front of it

  @D4
  Scenario Outline: Each kind is named within five seconds
    When the user holds <thing> up to the webcam
    Then within 5 seconds the user sees a card naming it <kind> with <fields>
    And the user sees a browser window open on <page>

    Examples:
      | thing                                                              | kind             | fields                                                                      | page                                   |
      | a Los Angeles parking ticket for citation 4512087733 on plate 8ABC123 | a parking ticket | citation 4512087733, plate 8ABC123, Los Angeles, due 2026-11-02            | the Los Angeles pay-or-contest page    |
      | an LADWP bill for $148.22 due 2026-11-05 on account 1234567890          | a bill           | LADWP, $148.22, due 2026-11-05, account 1234567890                          | the LADWP payment page                 |
      | a 32 oz bottle of Cholula Original hot sauce                          | a product        | Cholula Original hot sauce, 32 oz                                           | the first store's search results       |

  @D5
  Scenario Outline: What cannot be read gets "Hold it closer" and no chore
    When the user holds <thing> up to the webcam
    Then after 5 seconds the user sees "Hold it closer" on the card
    And the user sees no browser window open

    Examples:
      | thing                                                   |
      | a parking ticket at arm's length so the digits blur     |
      | a parking ticket moving so fast the frame is smeared    |
      | a blank sheet of paper                                  |
      | a coffee mug with no label                              |

  @D4 @D5
  Scenario Outline: The five-second clock decides between the card and Hold it closer
    Given the eye needs <delay> to make out a Los Angeles parking ticket for citation 4512087733 on plate 8ABC123
    When the user holds that ticket up to the webcam
    Then after 5 seconds the user sees <outcome> on the card
    And the user sees <browser>

    Examples:
      | delay       | outcome                                        | browser                                      |
      | 1 second    | a card naming it a parking ticket               | a browser window open on the Los Angeles pay-or-contest page |
      | 4.9 seconds | a card naming it a parking ticket               | a browser window open on the Los Angeles pay-or-contest page |
      | 5.1 seconds | "Hold it closer"                                | no browser window open                       |
      | 20 seconds  | "Hold it closer"                                | no browser window open                       |

  @D8
  Scenario: A product with more than one size is asked about first
    When the user holds a bottle of Cholula Original hot sauce up to the webcam with its size hidden by their hand
    Then the user sees the question "Is this the 32 oz?" on the card
    And the user sees no store searched until they answer

  @D8
  Scenario: Correcting the size answers the question
    Given the card is asking "Is this the 32 oz?"
    When the user says "no, the 12"
    Then the user sees the card name the product as "Cholula Original hot sauce, 12 oz"
    And the user sees the first store searched for the 12 oz bottle
