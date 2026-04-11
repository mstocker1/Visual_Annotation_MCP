# Sprint Backlog

Ticket-sized backlog (1-2 days each).

## Sprint 0

- S0-01: Define tool naming conventions and parameter defaults.
- S0-02: Define error model and response envelope.
- S0-03: Define flow schema v2 and compatibility notes.
- S0-04: Add schema validation and examples.

## Sprint 1

- S1-01: Implement click_by_role(role, name, exact).
- S1-02: Implement click_by_selector(selector).
- S1-03: Implement fill_by_label(label, text).
- S1-04: Implement wait_for_selector(selector, state).
- S1-05: Implement wait_for_text(text, optional scope).
- S1-06: Implement wait_for_navigation(url pattern).
- S1-07: Add stale handle recovery + re-inspect fallback.
- S1-08: Add regression tests for delayed/covered/hidden states.

## Sprint 2

- S2-01: Implement detect_blockers with z-index and bounds metadata.
- S2-02: Implement dismiss_overlay(selector optional, strategy auto/esc/close).
- S2-03: Implement close_cookie_banner convenience action.
- S2-04: Implement select_option by selector/id with value/label/index.
- S2-05: Implement check_uncheck and radio/select guards.
- S2-06: Implement submit_form with post-submit wait policy.
- S2-07: Implement upload_file with safe path handling.
- S2-08: Add flow examples for modal-first signup and email capture.

## Sprint 3

- S3-01: Create FlowExecutor state machine class.
- S3-02: Add ExecutionContext and store_as variable behavior.
- S3-03: Add retry policy (max attempts and backoff).
- S3-04: Add on_error behavior (fail, skip, fallback_action).
- S3-05: Add conditional branching step support.
- S3-06: Add run_flow_v2 schema validation and normalized errors.
- S3-07: Add step-level timing and attempt metadata.
- S3-08: Add compatibility adapter for existing run_flow input.

## Sprint 4

- S4-01: Implement assert_element_exists.
- S4-02: Implement assert_element_visible.
- S4-03: Implement assert_text_contains.
- S4-04: Implement assert_url_matches.
- S4-05: Implement extract_element (attrs/text).
- S4-06: Implement extract_form_data.
- S4-07: Implement extract_table.
- S4-08: Implement extract_page_model.
- S4-09: Implement run_story templates with setup/teardown.
- S4-10: Add parameterized stories and tag filtering.

## Sprint 5

- S5-01: Add request correlation id and structured logs.
- S5-02: Add per-tool latency and failure metrics.
- S5-03: Add optional telemetry (opt-in env flag).
- S5-04: Add URL and path hardening tests.
- S5-05: Add secret redaction in logs.
- S5-06: Add timeout audit across browser actions.
- S5-07: Add concurrency stress tests.
- S5-08: Add operational troubleshooting docs.

## Sprint 6

- S6-01: Raise type-check strictness and resolve warnings.
- S6-02: Enforce lint + docstring quality gates.
- S6-03: Raise coverage floor and close gaps.
- S6-04: Add CI matrix for OS and Python versions.
- S6-05: Add security scan stage and dependency audit.
- S6-06: Prepare release notes and migration guidance.
- S6-07: Run RC, triage feedback, cut GA release.
