from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    ROLE_CHOICES = [
        ('TT_Coordinator', 'TT Coordinator'),
        ('Department_Coordinator', 'Department Coordinator'),
        ('faculty', 'Faculty'),
        ('student', 'Student'),
    ]
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='TT_Coordinator')
      
class Student(models.Model):
    stud_id = models.CharField(primary_key=True,max_length=20, default=1)
    name = models.CharField(max_length=100)
    department = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.name} ({self.department})"

class Faculty(models.Model):
    faculty_id = models.CharField(primary_key=True,max_length=20, default=1)
    faculty_name = models.CharField(max_length=100)
    department = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.faculty_name} ({self.department})"

class Course(models.Model):
    course_id = models.CharField(primary_key=True,max_length=20, default=1)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, default="", blank=True, null=True)
    course_type = models.CharField(
        default="",blank=True, null=True,
        max_length=10,
        choices=[('tt', 'TT Course'), ('dept', 'Department Course'), ('none', 'None')]
    )
    hours_per_week = models.IntegerField(default=0)
    offered_to = models.CharField(max_length=30, default="", blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

class Class(models.Model):
    main_id = models.AutoField(primary_key=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    section_id = models.CharField(max_length=50, blank=True, null=True)
    faculty = models.ManyToManyField(Faculty, related_name='classes')  # Multiple faculty
    academic_year = models.CharField(max_length=10)
    semester = models.CharField(max_length=10, choices=[('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5'), ('6', '6'), ('7', '7'), ('8', '8')])
    dept = models.CharField(max_length=10, blank=True, null=True)
    venue = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        unique_together = ('course', 'section_id', 'academic_year', 'semester', 'dept')

    def __str__(self):
        faculty_names = ', '.join(f.faculty_name for f in self.faculty.all())
        return f"{self.course.name} - {self.section_id} ({faculty_names})"

class Registration(models.Model):
    stud_id = models.ForeignKey(Student, on_delete=models.CASCADE)
    main_id = models.ForeignKey(Class, on_delete=models.CASCADE)

class Timetable(models.Model):
    main_id = models.ForeignKey(Class, on_delete=models.CASCADE)
    day = models.IntegerField(choices=[(i, day) for i, day in enumerate(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"], start=1)])
    slot = models.IntegerField(choices=[(i, slot) for i, slot in enumerate(["9:00 AM - 9:50 AM", "9:50 AM - 10:40 AM", "11:00 AM - 11:50 AM", "11:50 PM - 12:40 PM", "1:30 PM - 2:15 PM", "2:15 PM - 3:00 PM", "3:15 PM - 4:00 PM", "4:00 PM - 4:45 PM"], start=1)])

    class Meta:
        unique_together = ('main_id', 'day', 'slot')

    def __str__(self):
        return f"{self.main_id.course.name} on Day {self.day}, Slot {self.slot}"
    
class TimetableStatus(models.Model):
    STATUS_CHOICES = [
        ('tt_coordinator', 'TT Coordinator Assigning'),
        ('dept_coordinator', 'Department Coordinator Assigning'),
        ('ga_running', 'Genetic Algorithm Running'),
        ('completed', 'Finalized'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='tt_coordinator')
    academic_year = models.CharField(max_length=10, default='none')
    semester = models.CharField(max_length=10, default='none', choices=[('1', '1'), ('2', '2'),('3', '3'), ('4', '4'),('5', '5'), ('6', '6'),('7', '7'), ('8', '8')])
    section = models.CharField(max_length=2, default='none')
    dept = models.CharField(max_length=10, default="")    
    
    class Meta:
        unique_together = ('academic_year', 'semester', 'section', 'dept')
    
    def __str__(self):
        return self.status