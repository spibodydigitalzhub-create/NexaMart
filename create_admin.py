import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace_app.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@nexamart.com', 'NexaMart2024!')
    print("✅ Superuser 'admin' created successfully!")
else:
    print("ℹ️ Superuser 'admin' already exists.")
