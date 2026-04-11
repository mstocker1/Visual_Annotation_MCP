# Flow v2 Contract

Sprint 0 contract for multi-step flow execution.

## Input

- Tool: run_flow_v2
- Parameter: flow_json
- Type: JSON string representing a non-empty array of step objects.

## Step Schema

Each step must include:

- action: string

Action-specific required fields:

- navigate: url
- inspect_elements: none
- click_element: element_id
- click_by_selector: selector
- click_by_role: role
- fill_element: element_id, text
- fill_by_label: label, text
- click_by_text: text
- fill_by_selector: selector, text
- dismiss_common_popups: none
- detect_blockers: none
- dismiss_overlay: none
- close_cookie_banner: none
- wait_for_selector: selector
- wait_for_text: text
- select_option: selector or element_id, and one of value/label/index
- check_uncheck: selector or element_id
- submit_form: selector or element_id
- upload_file: file_path and selector or element_id
- press_key: key
- wait_for_url: url_contains
- screenshot_viewport: none
- screenshot_element: element_id
- highlight_element: element_id

## Validation Rules

- flow_json must be valid JSON.
- Decoded value must be a non-empty list.
- Each list item must be an object.
- action is required and must be supported.
- Required action fields must be present and non-empty when string typed.

Optional step-level flow controls (Sprint 3):

- store_as: non-empty string key to store step result in context.
- if_var: non-empty context key for conditional execution.
  - equals: optional comparison value when if_var is present.
- retry: object
  - max_attempts: integer >= 1
  - backoff_ms: integer >= 0
- on_error: one of fail, skip, fallback_action
  - fallback_action: required action object when on_error is fallback_action

## Output Envelope

Success:

- ok: true
- steps_executed: integer
- final_url: string
- results: array

Failure:

- ok: false
- action: run_flow_v2
- error:
  - error_code: one of
    - invalid_json
    - invalid_flow
    - invalid_step
    - unsupported_action
    - execution_error
  - message: string
  - details: optional object

## Compatibility

- run_flow is kept as a legacy alias and routes internally to run_flow_v2.
