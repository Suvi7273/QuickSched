import django
import os
import sys

sys.path.append("D:/Documents/sem6-docs/SEP/proj4/timetable_project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "timetable_project.settings")
django.setup()

from timetable_app.models import CustomUser

def create_users():
    users = [
        {"username": "ctc", "password": "admin123", "role": "TT_Coordinator"},
        {"username": "dtc_ai_ds", "password": "password1", "role": "Department_Coordinator"},
        {"username": "dtc_ece", "password": "password2", "role": "Department_Coordinator"},
        {"username": "faculty1", "password": "faculty123", "role": "faculty"},  
        {"username": "student1", "password": "student123", "role": "student"},  
    ]

    for user_data in users:
        user, created = CustomUser.objects.get_or_create(username=user_data["username"])
        if created:
            user.set_password(user_data["password"])
            user.role = user_data["role"]
            user.is_active = True
            user.is_staff = True if user_data["role"] not in ["faculty", "student"] else False  # Staff for non-faculty/student
            user.save()
            print(f"User {user_data['username']} created successfully!")
        else:
            print(f"User {user_data['username']} already exists.")

if __name__ == "__main__":
    create_users()