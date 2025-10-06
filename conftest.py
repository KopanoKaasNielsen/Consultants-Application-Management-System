import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings.dev")

import django  # noqa: E402

django.setup()
