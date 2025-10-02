#!/bin/bash

# Step 1: Create a new branch
git checkout -b fix/whitenoise-support

# Step 2: Ensure whitenoise is in requirements.txt
grep -qxF "whitenoise==6.6.0" requirements.txt || echo "whitenoise==6.6.0" >> requirements.txt

# Step 3: Inject Whitenoise middleware into settings.py
SETTINGS="backend/settings/base.py"

# Add middleware if not present
grep -q "whitenoise.middleware.WhiteNoiseMiddleware" $SETTINGS || \
sed -i "/'django.middleware.security.SecurityMiddleware'/a\    'whitenoise.middleware.WhiteNoiseMiddleware'," $SETTINGS

# Add STATIC_ROOT and update STATICFILES_DIRS to avoid warning
grep -q "STATIC_ROOT" $SETTINGS || echo -e "\nSTATIC_ROOT = BASE_DIR / 'staticfiles'" >> $SETTINGS
sed -i "s|STATICFILES_DIRS = \[.*\]|STATICFILES_DIRS = [BASE_DIR / 'static'] if DEBUG else []|" $SETTINGS

# Step 4: Commit the change
git add $SETTINGS requirements.txt
git commit -m "fix: add whitenoise support and static config for production"

# Step 5: Push branch
git push origin fix/whitenoise-support

# Step 6: Suggest PR if gh CLI installed
if command -v gh &> /dev/null; then
    gh pr create --title "Fix: Add Whitenoise and static settings" \
                 --body "Add Whitenoise middleware, configure static files for CI and production" \
                 --base main \
                 --head fix/whitenoise-support
else
    echo "✅ Branch pushed! Now visit GitHub to open a PR:"
    echo "👉 https://github.com/KopanoKaasNielsen/Consultants-Application-Management-System/compare/fix/whitenoise-support?expand=1"
fi
