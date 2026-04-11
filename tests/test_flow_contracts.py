"""Tests for flow schema parsing and validation contracts."""

from __future__ import annotations

import unittest

from visual_annotation_mcp.errors import ErrorCode, MCPToolError
from visual_annotation_mcp.flow_contracts import parse_flow_json


class FlowContractsTests(unittest.TestCase):
    def test_parse_flow_json_accepts_valid_flow(self) -> None:
        flow = '[{"action":"navigate","url":"https://example.com"},{"action":"inspect_elements"}]'
        out = parse_flow_json(flow)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["action"], "navigate")


    def test_parse_flow_json_rejects_invalid_json(self) -> None:
        with self.assertRaises(MCPToolError) as ctx:
            parse_flow_json("{not json")
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_JSON)


    def test_parse_flow_json_rejects_non_list(self) -> None:
        with self.assertRaises(MCPToolError) as ctx:
            parse_flow_json('{"action":"navigate"}')
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_FLOW)


    def test_parse_flow_json_rejects_empty_list(self) -> None:
        with self.assertRaises(MCPToolError) as ctx:
            parse_flow_json("[]")
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_FLOW)


    def test_parse_flow_json_rejects_missing_action(self) -> None:
        with self.assertRaises(MCPToolError) as ctx:
            parse_flow_json('[{"url":"https://example.com"}]')
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_STEP)


    def test_parse_flow_json_rejects_unsupported_action(self) -> None:
        with self.assertRaises(MCPToolError) as ctx:
            parse_flow_json('[{"action":"do_magic"}]')
        self.assertEqual(ctx.exception.code, ErrorCode.UNSUPPORTED_ACTION)


    def test_parse_flow_json_rejects_missing_required_fields(self) -> None:
        with self.assertRaises(MCPToolError) as ctx:
            parse_flow_json('[{"action":"fill_by_selector","selector":"#email"}]')
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_STEP)
        self.assertIn("text", ctx.exception.message)

    def test_parse_flow_json_accepts_sprint1_actions(self) -> None:
        flow = (
            '[{"action":"wait_for_selector","selector":"#email"},'
            '{"action":"fill_by_label","label":"Email","text":"a@b.com"},'
            '{"action":"click_by_role","role":"button","name":"Continue"},'
            '{"action":"wait_for_text","text":"Finish"}]'
        )
        out = parse_flow_json(flow)
        self.assertEqual(len(out), 4)

    def test_parse_flow_json_accepts_sprint2_actions(self) -> None:
        flow = (
            '[{"action":"detect_blockers"},'
            '{"action":"dismiss_overlay"},'
            '{"action":"close_cookie_banner"},'
            '{"action":"select_option","selector":"#country","value":"ca"},'
            '{"action":"check_uncheck","selector":"#terms","checked":true},'
            '{"action":"submit_form","selector":"#profile-form"},'
            '{"action":"upload_file","selector":"#resume","file_path":"C:/tmp/a.txt"}]'
        )
        out = parse_flow_json(flow)
        self.assertEqual(len(out), 7)

    def test_parse_flow_json_rejects_select_option_without_locator(self) -> None:
        with self.assertRaises(MCPToolError) as ctx:
            parse_flow_json('[{"action":"select_option","value":"ca"}]')
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_STEP)

    def test_parse_flow_json_rejects_select_option_without_choice(self) -> None:
        with self.assertRaises(MCPToolError) as ctx:
            parse_flow_json('[{"action":"select_option","selector":"#country"}]')
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_STEP)

    def test_parse_flow_json_rejects_upload_without_locator(self) -> None:
        with self.assertRaises(MCPToolError) as ctx:
            parse_flow_json('[{"action":"upload_file","file_path":"C:/tmp/a.txt"}]')
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_STEP)

    def test_parse_flow_json_rejects_invalid_retry(self) -> None:
        with self.assertRaises(MCPToolError) as ctx:
            parse_flow_json('[{"action":"wait_for_text","text":"ok","retry":{"max_attempts":0}}]')
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_STEP)

    def test_parse_flow_json_rejects_invalid_on_error(self) -> None:
        with self.assertRaises(MCPToolError) as ctx:
            parse_flow_json('[{"action":"wait_for_text","text":"ok","on_error":"later"}]')
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_STEP)

    def test_parse_flow_json_rejects_missing_fallback_action(self) -> None:
        with self.assertRaises(MCPToolError) as ctx:
            parse_flow_json('[{"action":"wait_for_text","text":"ok","on_error":"fallback_action"}]')
        self.assertEqual(ctx.exception.code, ErrorCode.INVALID_STEP)


if __name__ == "__main__":
    unittest.main()
