@pending_matching_source @not_executed @simulated_data
Feature: Approved Demo 6 design with actual scientific data
  The HTML reference defines the visual and interaction behavior.
  These are acceptance specifications, not passing test results.
  Mock and HTTP modes must share the approved components.

  Background:
    Given the authorized worktree is OrbitVitals-Codex
    And the branch is feature/frontend-bridge
    And Silvio has supplied the exact source matching OrbitVitals_Demo (6).html
    And the original HTML and application use the same browser, OS, fonts, zoom and theme
    And any test API is owned by the test and does not use port 8000

  Scenario Outline: Preserve the approved Today layout at matching viewports
    Given the viewport is <width> by <height> CSS pixels with device scale factor 1
    When I open Today in <mode> mode
    Then the Mission Day area retains its approved position and geometry
    And all six physiological card slots and their sparkline areas remain present
    And the main resting-heart-rate chart retains its approved position
    And the Recovery, Worth a Look and Daily Review areas retain their visual hierarchy
    And layout, spacing, typography, colors, icons and responsive behavior match the reference
    And no alternate technical dashboard replaces Today

    Examples:
      | width | height | mode |
      | 1440  | 900    | mock |
      | 1440  | 900    | http |
      | 1366  | 768    | mock |
      | 1366  | 768    | http |
      | 1024  | 768    | http |
      | 768   | 1024   | http |
      | 390   | 844    | mock |
      | 390   | 844    | http |

  Scenario: Use one component structure for both data sources
    When I switch between mock and HTTP configurations
    Then the approved Today and Medical component structure remains the same
    And only the data provider, content and capability states change
    And missing HTTP data does not select a replacement dashboard

  Scenario Outline: Use the intended crew display mapping without changing IDs
    When I select <display_name>
    Then HTTP requests use crew ID <backend_id>
    And the UI identifies the records as simulated
    And stored backend names and identifiers remain unchanged

    Examples:
      | display_name | backend_id       |
      | Crew A       | sim-mission-v1-01 |
      | Crew B       | sim-mission-v1-02 |
      | Crew C       | sim-mission-v1-03 |

  Scenario: Reject an unknown crew identity without showing another astronaut
    When an unknown crew ID is selected
    Then no request or display silently substitutes Vega
    And an honest unavailable state appears in the approved structure

  Scenario: Keep missing HRV and blood-pressure cards
    Given the seeded API has no HRV or blood-pressure observations
    When I open Today in HTTP mode
    Then the original card and sparkline spaces remain
    And no mock HRV or default blood-pressure value fills those cards
    And the missing values are not interpreted as nominal health

  Scenario: Do not infer resting acquisition context
    Given a canonical heart_rate observation has no resting or waking context
    When it is considered for a resting-specific card or chart
    Then the context is explicitly qualified or the resting-specific value is unavailable
    And the timestamp is not used to invent a resting condition

  Scenario: Convert sleep display units without changing the scientific payload
    Given a stored sleep-duration observation is 370 min
    When the approved card displays hours to one decimal place
    Then the display is 6.2 h
    And details retain the exact value 370 min
    And the stored payload and canonical unit remain unchanged

  Scenario: Keep the last-night value separate from the window aggregate
    Given Noor's nine-night result has observed_value 430 min
    And the latest included sleep record is 370 min
    When I view the last-night card and the evaluation details
    Then the last-night card uses the record value
    And the evaluation details identify 430 min as the window median
    And the 480 min selected personal median is not labelled a sleep target

  Scenario Outline: Replay actual stored Noor results without future leakage
    Given the API is seeded with the recorded demonstration policy
    When I select the <nights>-night sleep checkpoint
    Then the displayed result status is <status>
    And the chart contains <included> usable nights out of <expected>
    And records and intervals after that checkpoint remain hidden
    And the exact evaluation ID and explanation match the stored response

    Examples:
      | nights | status            | included | expected |
      | 2      | insufficient_data | 2        | 2        |
      | 5      | attention         | 4        | 5        |
      | 9      | attention         | 7        | 9        |

  Scenario: Retain the sleep replay horizon when changing metrics
    Given the five-night Noor checkpoint is selected
    When I switch between sleep duration and sleep efficiency
    Then both views use the same stored horizon
    And a missing metric finding stays unavailable rather than borrowing another result

  Scenario: Show a missing checkpoint honestly
    Given a requested Noor checkpoint is absent from the API
    When I select that checkpoint
    Then its existing panel shows an unavailable result and no invented plot
    And no later evaluation is substituted

  Scenario: Separate quality completeness from sleep coverage
    Given the captured server has no expected sleep sampling interval
    And Noor's nine-night finding reports acceptable quality and null completeness
    When the sleep explanation reports seven of nine nights
    Then those counts remain night coverage
    And no 78 percent quality, confidence or sensor-accuracy score is invented

  Scenario: Preserve missing and unusable observations
    Given October 14 and October 18 night buckets are missing
    And another scenario contains unusable records such as -30 min or 125 percent
    When I inspect the chart and record evidence
    Then missing or excluded values are not plotted as zero or valid physiological points
    And lines do not bridge missing sleep nights
    And raw excluded records remain inspectable with their actual quality notes

  Scenario: Quality failure is not a physiological emergency
    Given Chen's early sleep result is nominal with degraded quality
    When I open its evidence in the approved Medical pane
    Then the physiological and quality states remain distinct
    And the UI does not create an alert, urgency level or diagnosis from the quality state

  Scenario: Use only the reference selected by the finding
    Given the finding references a specific baseline ID
    When that baseline is missing, foreign, in another phase or otherwise ineligible
    Then the UI reports the reference issue
    And it does not silently use the newest available baseline
    And no clinical normal band is manufactured from unrelated statistics

  Scenario: Do not apply mock physiological classifiers in HTTP mode
    Given the backend returns a trend-based attention finding
    And its absolute baseline-deviation criterion was not met
    When the Worth a Look panel renders the finding
    Then the actual trend explanation is retained
    And mock range or streak rules do not reclassify it as outside a personal range

  Scenario: Preserve the Medical dashboard and interactions
    When I open Medical and navigate crew, review items, charts and evidence
    Then the approved sidebar, panes, navigation and responsive interactions remain
    And actual evaluations are rendered inside that structure
    And a generic evaluation-list dashboard is not substituted
    And acknowledgement, annotation and messaging controls do not fake HTTP success

  Scenario: Preserve chart and navigation interactions
    When I use chart hover, keyboard navigation, tooltips and the data table
    And I use crew navigation, theme controls, sheets and mobile back navigation
    Then behavior and transitions match the approved reference
    And values, units, references, gaps and quality descriptions remain accurate

  Scenario: Keep mock workflows functional
    Given mock mode is selected
    When I complete a check-in, simulated measurement, share or sleep-aid workflow
    Then its original local demonstration behavior remains functional
    And it is not represented as a backend or medical action

  Scenario: Keep unsupported HTTP actions visible and honest
    Given HTTP mode is selected
    When I inspect Daily Review and other workflow areas
    Then the approved rows and panels retain their geometry
    And unavailable actions state that no endpoint exists
    And no sent message, queued report, saved annotation or successful check-in is claimed

  Scenario: Do not invent mission time or recovery
    Given the API supplies neither a mission epoch nor a recovery score
    When Mission Day and Recovery render
    Then they use agreed labelled simulation metadata or unavailable content
    And seeded October timestamps are not shifted to the HTML's November mock clock
    And no recovery, fatigue or readiness score is inferred from unrelated values

  Scenario: Loading and failures retain the approved design
    Given the server is unreachable, returns an HTTP error or returns no stored data
    When the app loads or refreshes
    Then loading, error or empty content remains inside the approved design
    And the interface does not invent a nominal result or switch to mock mode
    And a failed refresh labels retained data as stale

  Scenario: Isolate crew state during asynchronous navigation
    Given a request for Crew A is pending
    When I select Crew B and its response arrives first
    Then Crew A's later response cannot replace Crew B's data
    And a failed Crew B request does not expose Crew A's stale data as Crew B

  Scenario: Preserve contracts and explanations
    When a response has an unknown field, wrong canonical unit or unsuitable identity
    Then the existing bridge rejects the mismatch
    And the UI shows an error without a fallback scientific result
    And valid summaries, explanations, quality notes and provenance remain escaped text

  Scenario: Final visual acceptance is an explicit release gate
    Given all functional checks pass
    When matching reference and application captures are compared
    Then Today, Medical, charts, sheets, navigation, themes and responsive states are reviewed
    And text/value masks do not hide spacing, geometry, missing markers or badge regressions
    And Silvio's visual acceptance and the scientific review are recorded
    And passing automated tests alone does not imply visual or clinical acceptance
