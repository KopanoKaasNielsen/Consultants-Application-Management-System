"""Serializers for API payloads surfaced through DRF."""

from __future__ import annotations

from rest_framework import serializers


class PaginationSerializer(serializers.Serializer):
    page = serializers.IntegerField(min_value=1)
    page_size = serializers.IntegerField(min_value=1)
    total_pages = serializers.IntegerField(min_value=0)
    total_results = serializers.IntegerField(min_value=0)
    has_next = serializers.BooleanField()
    has_previous = serializers.BooleanField()


class ConsultantDocumentsSerializer(serializers.Serializer):
    is_complete = serializers.BooleanField()
    missing = serializers.ListField(child=serializers.CharField())


class ConsultantDashboardEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    status = serializers.CharField()
    status_display = serializers.CharField()
    submitted_at = serializers.CharField(allow_null=True)
    updated_at = serializers.CharField(allow_null=True)
    certificate_expires_at = serializers.CharField(allow_null=True)
    certificate_status = serializers.CharField(allow_null=True)
    certificate_status_reason = serializers.CharField(allow_null=True)
    documents = ConsultantDocumentsSerializer()


class ConsultantFiltersSerializer(serializers.Serializer):
    status = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    date_from = serializers.CharField(allow_null=True)
    date_to = serializers.CharField(allow_null=True)
    category = serializers.CharField(allow_null=True)
    search = serializers.CharField(allow_null=True)
    sort = serializers.CharField()


class ConsultantDashboardListSerializer(serializers.Serializer):
    results = ConsultantDashboardEntrySerializer(many=True)
    pagination = PaginationSerializer()
    applied_filters = ConsultantFiltersSerializer()


class LogEntryUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField(allow_null=True)
    email = serializers.EmailField(allow_null=True)


class LogEntrySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    timestamp = serializers.CharField()
    logger = serializers.CharField()
    level = serializers.CharField()
    message = serializers.CharField()
    user = LogEntryUserSerializer(allow_null=True)
    context = serializers.DictField(
        child=serializers.JSONField(), allow_empty=True
    )


class LogEntryFiltersSerializer(serializers.Serializer):
    level = serializers.CharField(allow_null=True)
    logger = serializers.CharField(allow_null=True)
    user_id = serializers.IntegerField(allow_null=True)
    action = serializers.CharField(allow_null=True)
    search = serializers.CharField(allow_null=True)


class LogEntryListSerializer(serializers.Serializer):
    results = LogEntrySerializer(many=True)
    pagination = PaginationSerializer()
    applied_filters = LogEntryFiltersSerializer()


class ConsultantValidationSuccessSerializer(serializers.Serializer):
    valid = serializers.BooleanField(default=True)


class ConsultantValidationErrorSerializer(serializers.Serializer):
    errors = serializers.DictField(child=serializers.CharField())
