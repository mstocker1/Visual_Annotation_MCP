# Acceptance Matrix

This matrix defines completion checks across all sprints.

## Core Interaction and Visuals

- AT-01: navigate + inspect returns stable id list.
- AT-02: click action transitions page state.
- AT-03: fill action updates field value.
- AT-04: screenshot_element returns valid PNG bytes.
- AT-05: highlight circle encloses target region.
- AT-06: color auto fallback avoids low-contrast choice.
- AT-07: blur_background blurs outside target while preserving target clarity.
- AT-08: annotate_last_image stacking preserves prior layers.

## Dynamic Content and Blockers

- AT-09: delayed element appears and becomes actionable within timeout.
- AT-10: temporarily covered element is retried until actionable.
- AT-11: dismiss_common_popups returns click count and advances page state.
- AT-12: detect_blockers returns plausible overlay candidates.

## Locator and Wait Reliability

- AT-13: click_by_role resolves exact and partial names.
- AT-14: click_by_selector handles first-match behavior deterministically.
- AT-15: fill_by_label resolves matching input fields.
- AT-16: wait_for_selector supports visible/hidden/attached/detached.
- AT-17: wait_for_text supports page-level and scoped matching.

## Flow Runner v2

- AT-18: variable storage and interpolation work across steps.
- AT-19: retry policy retries failed step and records attempts.
- AT-20: on_error skip continues flow and records skipped status.
- AT-21: on_error fallback_action executes alternate step.
- AT-22: branching executes expected path based on condition outcome.

## Assertions and Extraction

- AT-23: assert_element_exists pass and fail behavior validated.
- AT-24: assert_element_visible pass and fail behavior validated.
- AT-25: assert_text_contains pass and fail behavior validated.
- AT-26: assert_url_matches pass and fail behavior validated.
- AT-27: extract_element returns requested text and attrs.
- AT-28: extract_form_data returns key/value map for visible fields.
- AT-29: extract_table returns row/column records.
- AT-30: extract_page_model returns consistent structural schema.

## Story Mapping

- AT-31: run_story executes setup, steps, teardown in order.
- AT-32: parameterized story runs multiple parameter sets.
- AT-33: tag filtering executes only matching stories.

## Security, Observability, Release

- AT-34: URL allowlist blocks unauthorized hosts.
- AT-35: path traversal attempts are rejected.
- AT-36: sensitive values are redacted in logs.
- AT-37: structured logs include request id and tool metadata.
- AT-38: metrics capture latency and failure counts by tool.
- AT-39: CI matrix passes on supported OS/Python combinations.
- AT-40: release checklist completed with changelog and migration notes.

## Pass Rule

Program completion requires:

- All AT checks green.
- No critical severity unresolved defects.
- CI and release gates green.
