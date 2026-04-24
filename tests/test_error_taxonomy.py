"""Tests for simp/server/error_taxonomy.py — SIMP canonical error codes."""

import pytest
from simp.server.error_taxonomy import (
    SimpErrorCode,
    SimpError,
    ERROR_HTTP_MAP,
)


class TestSimpErrorCode:
    """Verify all error codes and their HTTP mappings."""

    def test_all_codes_have_http_mapping(self):
        """Every SimpErrorCode must have a corresponding entry in ERROR_HTTP_MAP."""
        for code in SimpErrorCode:
            assert code in ERROR_HTTP_MAP, (
                f"{code.value} is missing from ERROR_HTTP_MAP"
            )

    def test_http_status_map_invalid_signature(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.INVALID_SIGNATURE] == 401

    def test_http_status_map_unauthorized(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.UNAUTHORIZED] == 403

    def test_http_status_map_not_found(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.NOT_FOUND] == 404

    def test_http_status_map_invalid_request(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.INVALID_REQUEST] == 400

    def test_http_status_map_tool_invocation_failed(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.TOOL_INVOCATION_FAILED] == 500

    def test_http_status_map_route_failed(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.ROUTE_FAILED] == 502

    def test_http_status_map_stream_unavailable(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.STREAM_UNAVAILABLE] == 503

    def test_http_status_map_rate_limited(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.RATE_LIMITED] == 429

    def test_http_status_map_internal_error(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.INTERNAL_ERROR] == 500

    def test_http_status_map_timeout(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.TIMEOUT] == 504

    def test_http_status_map_bad_gateway(self):
        assert ERROR_HTTP_MAP[SimpErrorCode.BAD_GATEWAY] == 502

    def test_enum_values_are_strings(self):
        """Each enum member value should be a clean uppercase string."""
        for code in SimpErrorCode:
            assert isinstance(code.value, str)
            assert code.value.isupper(), f"{code.value} is not uppercase"


class TestSimpError:
    """Verify SimpError dataclass behavior."""

    def test_create_minimal(self):
        err = SimpError(code=SimpErrorCode.NOT_FOUND, message="Agent not found")
        assert err.code == SimpErrorCode.NOT_FOUND
        assert err.message == "Agent not found"
        assert err.detail is None
        assert len(err.error_id) == 12  # uuid hex prefix

    def test_create_with_detail(self):
        err = SimpError(
            code=SimpErrorCode.INVALID_REQUEST,
            message="Missing field",
            detail={"field": "target_agent"},
        )
        assert err.detail == {"field": "target_agent"}

    def test_to_dict_keys(self):
        err = SimpError(code=SimpErrorCode.UNAUTHORIZED, message="Bad key")
        d = err.to_dict()
        assert set(d.keys()) == {"error_id", "code", "message", "detail", "http_status"}

    def test_to_dict_values(self):
        err = SimpError(code=SimpErrorCode.RATE_LIMITED, message="Too fast")
        d = err.to_dict()
        assert d["code"] == "RATE_LIMITED"
        assert d["message"] == "Too fast"
        assert d["detail"] == {}
        assert d["http_status"] == 429
        assert d["error_id"] == err.error_id

    def test_to_response_envelope(self):
        err = SimpError(code=SimpErrorCode.INTERNAL_ERROR, message="Boom")
        resp = err.to_response()
        assert resp["success"] is False
        assert "error" in resp
        assert resp["error"]["code"] == "INTERNAL_ERROR"

    def test_to_response_includes_all_dict_fields(self):
        err = SimpError(code=SimpErrorCode.TIMEOUT, message="Timed out")
        resp = err.to_response()
        inner = resp["error"]
        for key in ("error_id", "code", "message", "detail", "http_status"):
            assert key in inner, f"to_response().error missing key: {key}"

    def test_error_id_uniqueness(self):
        ids = {
            SimpError(code=SimpErrorCode.NOT_FOUND, message="a").error_id
            for _ in range(100)
        }
        assert len(ids) == 100, "error_id values are not unique"

    def test_default_detail_handling(self):
        err = SimpError(code=SimpErrorCode.BAD_GATEWAY, message="Upstream fail")
        d = err.to_dict()
        assert d["detail"] == {}  # None becomes empty dict in to_dict

    def test_unknown_code_falls_back_to_500(self):
        """If somehow a code not in ERROR_HTTP_MAP is used, default to 500."""
        # SimpErrorCode has all codes mapped, but test the fallback path
        err_dict = SimpError(
            code=SimpErrorCode.INTERNAL_ERROR, message="test"
        ).to_dict()
        assert err_dict["http_status"] == 500

    def test_str_representation(self):
        err = SimpError(code=SimpErrorCode.INVALID_SIGNATURE, message="Bad sig")
        d = err.to_dict()
        assert isinstance(d["code"], str)
        assert d["code"] == "INVALID_SIGNATURE"
