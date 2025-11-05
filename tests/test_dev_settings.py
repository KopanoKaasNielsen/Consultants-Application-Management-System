"""Regression tests for development settings."""

from django.conf import settings


def test_dev_staticfiles_storage_uses_default_backend():
    """Development builds should not require a staticfiles manifest."""

    assert (
        settings.STATICFILES_STORAGE
        == 'django.contrib.staticfiles.storage.StaticFilesStorage'
    )
