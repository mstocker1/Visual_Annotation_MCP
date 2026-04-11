# Operations Runbook

This guide covers runtime observability for Visual Annotation MCP.

## Structured Log Format

Logs are emitted as JSON lines from `visual_annotation_mcp.observability`.

Primary fields:
- `event`: `request_start`, `tool_start`, `tool_success`, `tool_error`, `request_end`, `telemetry_metric`
- `request_id`: correlation id for one tool request
- `tool`: top-level tool or flow sub-action key
- `metadata`: redacted structured details
- `ts_ms`: epoch milliseconds

Sensitive values are automatically redacted for common secret keys (`password`, `token`, `authorization`, etc.) and bearer tokens.

## Environment Controls

- `VISUAL_ANNOTATION_TELEMETRY=1`
  - Enables extra telemetry metric events.
- `VISUAL_ANNOTATION_ALLOWED_HOSTS=host1,host2`
  - Allows navigation only to approved hosts.
- `VISUAL_ANNOTATION_ALLOWED_PATHS=pathA,pathB`
  - Allows `upload_file` only under approved roots.
- `VISUAL_ANNOTATION_ALLOW_UNRESTRICTED=1`
  - Development-only override that disables default-deny restrictions.

## Observability Tool

Use `observability_snapshot` to fetch in-memory aggregated metrics:
- `calls`
- `failures`
- `avg_ms`
- `max_ms`

This is useful when collecting health status from long-running sessions.

## Query Examples

### PowerShell: recent tool errors

```powershell
Get-Content mcp.log | Select-String '"event":"tool_error"'
```

### PowerShell: latency events for flow actions

```powershell
Get-Content mcp.log | Select-String '"tool":"flow\.' | Select-String '"event":"tool_success"'
```

### PowerShell: find all events by request id

```powershell
Get-Content mcp.log | Select-String '"request_id":"<replace-me>"'
```

### Python: summarize failures by tool

```python
import json
from collections import Counter

failures = Counter()
with open("mcp.log", "r", encoding="utf-8") as f:
    for line in f:
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("event") == "tool_error":
            failures[row.get("tool", "unknown")] += 1

print(dict(failures))
```

## Troubleshooting

1. Symptom: repeated `tool_error` for `flow.wait_for_text`.
- Check whether the selector/text is deterministic.
- Increase the step timeout (`timeout_ms`) and confirm blockers are dismissed.
- Use `detect_blockers` + `dismiss_overlay` before the failing step.

2. Symptom: `upload_file` is denied.
- Confirm `VISUAL_ANNOTATION_ALLOWED_PATHS` includes the file root.
- Use absolute paths to avoid ambiguity.
- Verify file exists and is readable in the host environment.

3. Symptom: navigation denied.
- Confirm target host is listed in `VISUAL_ANNOTATION_ALLOWED_HOSTS`.
- For local debugging only, set `VISUAL_ANNOTATION_ALLOW_UNRESTRICTED=1`.

4. Symptom: high average latency for screenshot/highlight tools.
- Reduce screenshot scope (`full_page=False`, lower context needs).
- Avoid unnecessary repeated `inspect_elements` calls in short loops.
- Measure with `observability_snapshot` before/after changes.

## Escalation Checklist

1. Capture `observability_snapshot` output.
2. Capture last 200 structured log lines.
3. Include flow JSON or exact MCP tool inputs that reproduced the issue.
4. Include environment controls used (`VISUAL_ANNOTATION_*`).
