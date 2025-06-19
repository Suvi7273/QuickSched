from django.core.exceptions import ValidationError
from .models import Timetable, Class
from django.db.models import Q

#MAIN_COURSES = ['DL', 'FS', 'SE', 'CE', 'ASSO']  
        
def validate_timetable_constraints(main_id, day, slot, current_year, current_semester, section, dept, timetable_cache=None, temp_timetable=None):
    # Standardize day as a list
    if isinstance(day, list):
        # Validate that all elements are integers
        if not all(isinstance(d, int) for d in day):
            raise ValueError(f"All day values must be integers, got: {day}")
        days = day  # Use the list as-is
    else:
        days = [day]  # Wrap single day in a list

    classes = Class.objects.filter(academic_year=current_year, semester=current_semester)
    relevant_courses = set(cls.course for cls in classes)    
    MAIN_COURSES = [course.name for course in relevant_courses if course.course_type == 'none']
     
    #class_obj = Class.objects.get(main_id=main_id)
    class_obj = Class.objects.prefetch_related('faculty').get(main_id=main_id)
    course_name = class_obj.course.name
    course_type = class_obj.course.course_type
    
    # 1. Slot Uniqueness 
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
            # Rule 1: Block if new course is 'none' and slot is occupied
            if course_type == 'none':
                raise ValidationError(f"Slot on {d} is already assigned, and courses with type 'none' cannot share slots.")
            # Rule 2: Block if slot has a 'none' course and anything else tries to join
            if any(t.main_id.course.course_type == 'none' for t in existing_assignments):
                raise ValidationError(f"Slot on {d} contains a course with type 'none', so no additional courses can be assigned.")
    
    # 7. Check if the same venue is already booked for this slot
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

    # 2. Faculty Double Booking Check
    for faculty in class_obj.faculty.all():  # Check all faculty
        if faculty.faculty_name not in ["Some faculty (-)", "Some faculty"] and course_name not in ['PET','LIB'] and course_name not in ['PROJ WORK']:
            for d in days:
                if Timetable.objects.filter(
                    day=d,
                    slot=slot,
                    main_id__faculty=faculty,  # Use __faculty to filter ManyToManyField
                    main_id__academic_year=current_year
                ).exists():
                    raise ValidationError(f"Faculty {faculty.faculty_name} is already assigned another course on {d} during this slot.")
                
    # 3. Continuous Assignment Prevention (Only for Main Courses)
    if course_name in MAIN_COURSES:
        previous_slot = Timetable.objects.filter(day=day, slot=slot - 1,main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id=section, main_id__dept=dept).first()
        next_slot = Timetable.objects.filter(day=day, slot=slot + 1,main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id=section, main_id__dept=dept).first()

        if previous_slot and previous_slot.main_id.course.name == course_name:
            raise ValidationError("Cannot assign the same main course consecutively.")

        if next_slot and next_slot.main_id.course.name == course_name:
            raise ValidationError("Cannot assign the same main course consecutively.")

    # 4. Assignment Across Multiple Days (If applicable)
    if len(days) > 1:
        for d in days:
            if Timetable.objects.filter(
                Q(day=d, slot=slot,main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id=section, main_id__dept=dept) | 
                Q(day=d, slot=slot,main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id__isnull=True, main_id__dept__isnull=True, main_id__course__offered_to='all')).exists():
                raise ValidationError(f"Slot on {d} is already assigned. Please select another slot.")
            # Ensure same course is being assigned
            existing = Timetable.objects.filter(
                Q(day=d, slot=slot, main_id__course__name=course_name,main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id=section, main_id__dept=dept) |
                Q(day=d, slot=slot, main_id__course__name=course_name,main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id__isnull=True, main_id__dept__isnull=True, main_id__course__offered_to='all'))
            if existing.exists() is False:
                raise ValidationError(f"The same course must be assigned to all selected days.")

    # 5. Ensure Faculty Doesn’t Handle More Than 2 Main Courses Continuously
    if course_name in MAIN_COURSES:
        for faculty in class_obj.faculty.all():  # Check all faculty
            if faculty.faculty_name not in ["Some faculty (-)", "Some faculty"] and course_name not in ['PET','LIB'] and course_name not in ['PROJ WORK']:
                for d in days:
                    prev1 = Timetable.objects.filter(day=d, slot=slot - 1, main_id__faculty=faculty, main_id__academic_year=current_year).first()
                    prev2 = Timetable.objects.filter(day=d, slot=slot - 2, main_id__faculty=faculty, main_id__academic_year=current_year).first()
                    next1 = Timetable.objects.filter(day=d, slot=slot + 1, main_id__faculty=faculty, main_id__academic_year=current_year).first()
                    next2 = Timetable.objects.filter(day=d, slot=slot + 2, main_id__faculty=faculty, main_id__academic_year=current_year).first()

                    if prev1 and prev2 and prev1.main_id.course.name in MAIN_COURSES and prev2.main_id.course.name in MAIN_COURSES:
                        raise ValidationError(f"Faculty {faculty.faculty_name} cannot handle more than 2 courses continuously.")
                    if next1 and next2 and next1.main_id.course.name in MAIN_COURSES and next2.main_id.course.name in MAIN_COURSES:
                        raise ValidationError(f"Faculty {faculty.faculty_name} cannot handle more than 2 courses continuously.")
                                  
    # 6. NOT MORE THAN 2 SLOTS FOR A MAIN SUBJECT IN A DAY
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