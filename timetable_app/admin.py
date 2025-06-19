from django.contrib import admin
from .models import Faculty, Course, Timetable, TimetableStatus

admin.site.register(Faculty)
admin.site.register(Course)
admin.site.register(Timetable)
admin.site.register(TimetableStatus)
