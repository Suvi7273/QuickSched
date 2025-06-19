from django import forms
from .models import Timetable, Class

class FacultyUploadForm(forms.Form):
    file = forms.FileField()
    
class StudentUploadForm(forms.Form):
    file = forms.FileField()
    
class CourseUploadForm(forms.Form):
    file = forms.FileField()
    
class RegistrationUploadForm(forms.Form):
    file = forms.FileField()
    
class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['course', 'section_id', 'faculty', 'academic_year', 'semester', 'dept', 'venue']
        widgets = {
            'academic_year': forms.TextInput(attrs={'placeholder': 'e.g., 2025_odd or 2025_even'}),
            'faculty': forms.SelectMultiple(attrs={'size': '5'}),  # Allow multiple selections
        }

class YearSemesterForm(forms.Form):
    academic_year = forms.CharField(
        label='Academic Year',
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 2025_odd or 2025_even'})
    )
    semester = forms.ChoiceField(
        label='Semester',
        choices=[(str(i), str(i)) for i in range(1, 9)]
    )
    section = forms.CharField(
        label='Section',
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 1 or 2 or 3'})
    )
    dept = forms.CharField(
        label='dept',
        widget=forms.TextInput()
    )
    
class TimetableForm(forms.ModelForm):
    DAYS = [
        (1, 'Monday'),
        (2, 'Tuesday'),
        (3, 'Wednesday'),
        (4, 'Thursday'),
        (5, 'Friday'),
        (6, 'Saturday'),
    ]

    SLOTS = [
        (1, "9:00 AM - 9:50 AM"),
        (2, "9:50 AM - 10:40 AM"),
        (3, "11:00 AM - 11:50 AM"),
        (4, "11:50 PM - 12:40 PM"),
        (5, "1:30 PM - 2:15 PM"),
        (6, "2:15 PM - 3:00 PM"),
        (7, "3:15 PM - 4:00 PM"),
        (8, "4:00 PM - 4:45 PM"),
    ]

    days = forms.MultipleChoiceField(
        choices=DAYS,
        widget=forms.CheckboxSelectMultiple
    )

    slots = forms.MultipleChoiceField(
        choices=SLOTS,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Timetable
        fields = ['main_id', 'days', 'slots']