"""Trip plan persistence."""

from __future__ import annotations

import hashlib
import secrets
import uuid

from django.db import models


class TripPlan(models.Model):
    """Immutable snapshot of a planned trip."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    access_token_hash = models.CharField(max_length=64, db_index=True)
    schema_version = models.CharField(max_length=32, default="trip-plan-v1")
    rule_version = models.CharField(max_length=64, default="hos-property-carrying-70-8-v1")
    input_json = models.JSONField()
    route_json = models.JSONField()
    timeline_json = models.JSONField()
    logs_json = models.JSONField()
    diagnostics_json = models.JSONField(default=dict)
    validation_json = models.JSONField(default=dict)
    provider_meta = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]

    @staticmethod
    def hash_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def mint_token(cls) -> str:
        return secrets.token_urlsafe(32)

    def __str__(self) -> str:
        return f"TripPlan {self.id}"
