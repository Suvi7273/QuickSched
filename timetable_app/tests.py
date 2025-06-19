from django.test import TestCase
import sys
from collections import Counter, defaultdict
from django.db.models import Q
from django.core.exceptions import ValidationError
import django
import os

# Set up Django environment
sys.path.append("D:/Documents/sem6-docs/SEP/proj4/timetable_project")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "timetable_project.settings")
django.setup()

from timetable_app.models import Timetable, Class, Faculty, TimetableStatus, Course
from timetable_app.validators import validate_timetable_constraints

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.models import Q
from timetable_app.models import Timetable, Class
from datetime import datetime

class TimetableConstraintsTests(TestCase):
    def validate_timetable_constraints(self, main_id, day, slot, current_year, current_semester, section, dept, timetable_cache=None, temp_timetable=None):
        # Validation function from your provided code
        class_obj = Class.objects.prefetch_related('faculty').get(main_id=main_id)
        course_name = class_obj.course.name
        course_type = class_obj.course.course_type
        days = [day] if not isinstance(day, list) else day
        classes = Class.objects.filter(academic_year=current_year, semester=current_semester)
        relevant_courses = set(cls.course for cls in classes)
        MAIN_COURSES = [course.name for course in relevant_courses if course.course_type == 'none']

        # Constraint 1: Slot Uniqueness
        for d in days:
            existing_assignments = Timetable.objects.filter(
                Q(main_id__academic_year=current_year,
                  main_id__semester=current_semester,
                  day=d,
                  slot=slot,
                  main_id__section_id=section,
                  main_id__dept=dept) |
                Q(main_id__academic_year=current_year,
                  main_id__semester=current_semester,
                  day=d,
                  slot=slot,
                  main_id__section_id__isnull=True,
                  main_id__dept__isnull=True,
                  main_id__course__offered_to='all')
            ).exclude(main_id=class_obj)
            if existing_assignments.exists():
                if course_type == 'none':
                    raise ValidationError(f"Slot on {d} is already assigned, and courses with type 'none' cannot share slots.")
                if any(t.main_id.course.course_type == 'none' for t in existing_assignments):
                    raise ValidationError(f"Slot on {d} contains a course with type 'none', so no additional courses can be assigned.")

        # Constraint 2: Venue Booking
        for d in days:
            if Timetable.objects.filter(
                day=d,
                slot=slot,
                main_id__venue=class_obj.venue,
                main_id__academic_year=current_year
            ).exclude(main_id=class_obj).exclude(
                Q(main_id__venue='pg') | Q(main_id__venue='') | Q(main_id__venue__isnull=True)
            ).exists():
                raise ValidationError(f"The venue is already booked on {d} during this slot.")

        # Constraint 3: Faculty Double Booking
        for faculty in class_obj.faculty.all():
            if faculty.faculty_name not in ["Some faculty (-)", "Some faculty"] and course_name not in ['PET', 'LIB', 'PROJ WORK']:
                for d in days:
                    if Timetable.objects.filter(
                        day=d,
                        slot=slot,
                        main_id__faculty=faculty,
                        main_id__academic_year=current_year
                    ).exclude(main_id=class_obj).exists():
                        raise ValidationError(f"Faculty {faculty.faculty_name} is already assigned another course on {d} during this slot.")

        # Constraint 4: Continuous Assignment Prevention
        if course_name in MAIN_COURSES:
            previous_slot = Timetable.objects.filter(day=day, slot=slot - 1, main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id=section, main_id__dept=dept).first()
            next_slot = Timetable.objects.filter(day=day, slot=slot + 1, main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id=section, main_id__dept=dept).first()
            if previous_slot and previous_slot.main_id.course.name == course_name:
                raise ValidationError("Cannot assign the same main course consecutively.")
            if next_slot and next_slot.main_id.course.name == course_name:
                raise ValidationError("Cannot assign the same main course consecutively.")

        # Constraint 5: Multiple Days Assignment
        if len(days) > 1:
            for d in days:
                if Timetable.objects.filter(
                    Q(day=d, slot=slot, main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id=section, main_id__dept=dept) |
                    Q(day=d, slot=slot, main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id__isnull=True, main_id__dept__isnull=True, main_id__course__offered_to='all')
                ).exists():
                    raise ValidationError(f"Slot on {d} is already assigned. Please select another slot.")
                existing = Timetable.objects.filter(
                    Q(day=d, slot=slot, main_id__course__name=course_name, main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id=section, main_id__dept=dept) |
                    Q(day=d, slot=slot, main_id__course__name=course_name, main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id__isnull=True, main_id__dept__isnull=True, main_id__course__offered_to='all')
                )
                if not existing.exists():
                    raise ValidationError(f"The same course must be assigned to all selected days.")

        # Constraint 6: Faculty Continuous Courses
        if course_name in MAIN_COURSES:
            for faculty in class_obj.faculty.all():
                if faculty.faculty_name not in ["Some faculty (-)", "Some faculty"] and course_name not in ['PET', 'LIB', 'PROJ WORK']:
                    for d in days:
                        prev1 = Timetable.objects.filter(day=d, slot=slot - 1, main_id__faculty=faculty, main_id__academic_year=current_year).first()
                        prev2 = Timetable.objects.filter(day=d, slot=slot - 2, main_id__faculty=faculty, main_id__academic_year=current_year).first()
                        next1 = Timetable.objects.filter(day=d, slot=slot + 1, main_id__faculty=faculty, main_id__academic_year=current_year).first()
                        next2 = Timetable.objects.filter(day=d, slot=slot + 2, main_id__faculty=faculty, main_id__academic_year=current_year).first()
                        if prev1 and prev2 and prev1.main_id.course.name in MAIN_COURSES and prev2.main_id.course.name in MAIN_COURSES:
                            raise ValidationError(f"Faculty {faculty.faculty_name} cannot handle more than 2 courses continuously.")
                        if next1 and next2 and next1.main_id.course.name in MAIN_COURSES and next2.main_id.course.name in MAIN_COURSES:
                            raise ValidationError(f"Faculty {faculty.faculty_name} cannot handle more than 2 courses continuously.")

        # Constraint 7: Max 2 Slots per Day for Main Course
        if course_name in MAIN_COURSES:
            for d in days:
                existing_slots = Timetable.objects.filter(
                    day=d,
                    main_id__course__name=course_name,
                    main_id__academic_year=current_year,
                    main_id__semester=current_semester,
                    main_id__section_id=section,
                    main_id__dept=dept
                ).exclude(main_id=class_obj).count()
                if existing_slots >= 2:
                    raise ValidationError(f"Cannot assign more than 2 slots for {course_name} on day {d}.")

    def test_validate_all_timetables(self):
        # Fetch current academic year
        current_year = "2025_even"
        # Fetch all timetable entries for the current academic year
        timetables = Timetable.objects.filter(main_id__academic_year=current_year)
        
        if not timetables.exists():
            print("No timetable entries found for the current academic year.")
            return

        violations = []
        for timetable in timetables:
            try:
                self.validate_timetable_constraints(
                    main_id=timetable.main_id.main_id,
                    day=timetable.day,
                    slot=timetable.slot,
                    current_year=current_year,
                    current_semester=timetable.main_id.semester,
                    section=timetable.main_id.section_id,
                    dept=timetable.main_id.dept
                )
            except ValidationError as e:
                violations.append({
                    'timetable_id': timetable.id,
                    'main_id': str(timetable.main_id.main_id),
                    'course': timetable.main_id.course.name,
                    'day': timetable.day,
                    'slot': timetable.slot,
                    'section': timetable.main_id.section_id,
                    'dept': timetable.main_id.dept,
                    'error': str(e)
                })
            except Class.DoesNotExist:
                violations.append({
                    'timetable_id': timetable.id,
                    'main_id': str(timetable.main_id.main_id),
                    'course': 'Unknown',
                    'day': timetable.day,
                    'slot': timetable.slot,
                    'section': timetable.main_id.section_id,
                    'dept': timetable.main_id.dept,
                    'error': 'Class does not exist for this timetable entry.'
                })

        if violations:
            print(f"Found {len(violations)} timetable constraint violations:")
            for violation in violations:
                print(f"Timetable ID: {violation['timetable_id']}, "
                      f"Main ID: {violation['main_id']}, "
                      f"Course: {violation['course']}, "
                      f"Day: {violation['day']}, "
                      f"Slot: {violation['slot']}, "
                      f"Section: {violation['section']}, "
                      f"Dept: {violation['dept']}, "
                      f"Error: {violation['error']}")
        else:
            print("No timetable constraint violations found.")

    def test_empty_database(self):
        # Test if the database has no timetable entries
        current_year = "2025_even"
        timetables = Timetable.objects.filter(main_id__academic_year=current_year)
        self.assertFalse(timetables.exists(), "No timetable entries should exist for this test to pass as empty.")
        