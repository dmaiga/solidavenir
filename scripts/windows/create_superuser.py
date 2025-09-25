from django.contrib.auth import get_user_model

User = get_user_model()
username = "admin"
email = "admin@solidavenir.com"
password = "changeMe123!"
user_type = "admin"

if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(username=username, email=email, password=password, user_type=user_type)
    print("✅ Superuser créé !")
else:
    print("ℹ️ Superuser existe déjà")
