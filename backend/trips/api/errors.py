"""API error envelope."""

from __future__ import annotations

import uuid

from rest_framework.response import Response
from rest_framework.views import exception_handler

from trips.services.planning import PlanError


def error_body(
    *,
    code: str,
    message: str,
    field_errors: dict | None = None,
    retryable: bool = False,
    request_id: str | None = None,
) -> dict:
    return {
        "code": code,
        "message": message,
        "field_errors": field_errors or {},
        "retryable": retryable,
        "request_id": request_id or str(uuid.uuid4()),
    }


def custom_exception_handler(exc, context):
    if isinstance(exc, PlanError):
        return Response(
            error_body(
                code=exc.code,
                message=exc.message,
                field_errors=exc.field_errors,
                retryable=exc.retryable,
            ),
            status=exc.status,
        )
    response = exception_handler(exc, context)
    if response is not None:
        request_id = str(uuid.uuid4())
        if isinstance(response.data, dict):
            response.data = error_body(
                code="REQUEST_ERROR",
                message=str(response.data.get("detail") or response.data),
                field_errors={
                    k: v for k, v in response.data.items() if k != "detail"
                }
                if not response.data.get("detail")
                else {},
                retryable=response.status_code >= 500,
                request_id=request_id,
            )
        else:
            response.data = error_body(
                code="REQUEST_ERROR",
                message=str(response.data),
                request_id=request_id,
            )
    return response
