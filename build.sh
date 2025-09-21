#!/usr/bin/env bash
# Install dependencies
pip install -r requirements.txt

# Run migrations and collect static files
python manage.py migrate
python manage.py collectstatic --noinput
#!/usr/bin/env bash

echo "📦 Installing requirements..."
pip install -r requirements.txt

echo "⚙️ Running migrations..."
python manage.py migrate

echo "🧪 Seeding groups and users..."
python manage.py seed_groups
python manage.py seed_users  # <-- this runs the user creation
