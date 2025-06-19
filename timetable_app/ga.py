import random
from collections import defaultdict
from .models import Timetable, Class, TimetableStatus, Course
from .validators import validate_timetable_constraints
from django.core.exceptions import ValidationError
from django.db.models import Q

import logging
logger = logging.getLogger(__name__)

# Define course slot requirements
COURSE_SLOT_REQUIREMENTS = {}
# Time slots and days
TIME_SLOTS = [1, 2, 3, 4, 5, 6, 7, 8]
DAYS = [1, 2, 3, 4, 5, 6]

# Dictionary to hold pre-assigned (locked) timetable slots
locked_slots = set()  # Format: (day, slot)
locked_assignments = defaultdict(list)  # Format: (day, slot): [(main_id, course_name), ...]

def fitness(individual, current_year, current_semester, section, dept, timetable_cache=None):
    score = 0
    course_distribution = defaultdict(int)
    temp_timetable = defaultdict(list)
    for day, slot, main_id, _ in individual:
        if main_id not in all_classes:
            logger.error(f"Invalid main_id {main_id} in fitness")
            score -= 50
            continue
        temp_timetable[(day, slot)].append(all_classes[main_id])

    for day, slot, main_id, course_name in individual:
        if main_id not in all_classes:
            logger.error(f"Invalid main_id {main_id} in fitness validation")
            score -= 50
            continue
        try:
            validate_timetable_constraints(main_id, day, slot, current_year, current_semester, section, dept, timetable_cache, temp_timetable)
            score += 5
            course_distribution[course_name] += 1
        except ValidationError as e:
            score -= 50
            logger.debug(f"Fitness penalty for main_id {main_id}, day {day}, slot {slot}: {e}")
    for course, required_slots in COURSE_SLOT_REQUIREMENTS.items():
        diff = abs(course_distribution[course] - required_slots)
        score -= diff * 50
    return score

def generate_population(current_year, current_semester, section, dept, size=20, timetable_cache=None):
    print("entered population")
    population = []
    for _ in range(size):
        individual = [(day, slot, main_id, course_name) 
                      for (day, slot), assignments in locked_assignments.items() 
                      for main_id, course_name in assignments if main_id in all_classes]

        course_slots_remaining = COURSE_SLOT_REQUIREMENTS.copy()
        for _, _, _, course in individual:
            if course in course_slots_remaining:
                course_slots_remaining[course] -= 1
        available_slots = [(day, slot) for day in DAYS for slot in TIME_SLOTS if (day, slot) not in locked_slots]
        main_courses = {cls.course.name for cls in all_classes.values() if cls.course.course_type == 'none'}
        temp_timetable = defaultdict(list)
        for day, slot, main_id, _ in individual:
            if main_id not in all_classes:
                print(f"Invalid main_id {main_id} in locked assignments")
                continue
            temp_timetable[(day, slot)].append(all_classes[main_id])
            assert isinstance(all_classes[main_id], Class), f"temp_timetable contains non-Class object for main_id {main_id}"

        while available_slots and any(count > 0 for count in course_slots_remaining.values()):
            random.shuffle(available_slots)
            assigned_in_iteration = False
            for day, slot in available_slots[:]:
                available_courses = [c for c, count in course_slots_remaining.items() if count > 0]
                if not available_courses:
                    break
                assigned_courses_on_day = defaultdict(int)
                for d, _, _, c in individual:
                    if d == day:
                        assigned_courses_on_day[c] += 1
                available_courses = [c for c in available_courses if c not in main_courses or assigned_courses_on_day[c] < 2]
                if not available_courses:
                    available_slots.remove((day, slot))
                    continue
                course_name = random.choice(available_courses)
                valid_classes = [main_id for main_id in course_class_map[course_name] if main_id in all_classes]
                if valid_classes:
                    random.shuffle(valid_classes)
                    assigned = False
                    for main_id in valid_classes:
                        try:
                            validate_timetable_constraints(main_id, day, slot, current_year, current_semester, section, dept, timetable_cache, temp_timetable)
                            cls = all_classes[main_id]
                            if course_name in main_courses:
                                # Rebuild temp_timetable for check
                                temp_timetable_check = defaultdict(list)
                                for d, s, mid, _ in individual:
                                    if mid not in all_classes:
                                        continue
                                    temp_timetable_check[(d, s)].append(all_classes[mid])
                                prev_slot = temp_timetable_check.get((day, slot - 1), [])
                                next_slot = temp_timetable_check.get((day, slot + 1), [])
                                for c in prev_slot + next_slot:
                                    if not isinstance(c, Class):
                                        print(f"Non-Class object in temp_timetable_check: {c}, main_id={main_id}, day={day}, slot={slot}")
                                        continue
                                    if c.course.name == course_name:
                                        raise ValidationError(f"Cannot assign {course_name} consecutively in slot {slot} on day {day}")
                            individual.append((day, slot, main_id, course_name))
                            temp_timetable[(day, slot)].append(cls)
                            assert isinstance(cls, Class), f"temp_timetable appended non-Class object for main_id {main_id}"
                            course_slots_remaining[course_name] -= 1
                            assigned = True
                            assigned_in_iteration = True
                            available_slots.remove((day, slot))
                            #print(f"Assigned {course_name} to day {day}, slot {slot}, main_id {main_id}")
                            break
                        except ValidationError as e:
                            print(f"Validation failed for {course_name} on day {day}, slot {slot}: {e}")
                            continue
                    if not assigned:
                        available_slots.remove((day, slot))
                else:
                    available_slots.remove((day, slot))
            if not assigned_in_iteration:
                break
        population.append(individual)
    print("exiting population")
    return population

def crossover(parent1, parent2, current_year, current_semester, section, dept, timetable_cache=None):
    logger.debug("entered crossover")
    locked_set = set(locked_assignments.keys())
    child = []
    main_courses = {cls.course.name for cls in all_classes.values() if cls.course.course_type == 'none'}
    parent1_dict = {(day, slot): (main_id, course_name) for day, slot, main_id, course_name in parent1}
    parent2_dict = {(day, slot): (main_id, course_name) for day, slot, main_id, course_name in parent2}
    temp_timetable = defaultdict(list)

    for day in DAYS:
        for slot in TIME_SLOTS:
            key = (day, slot)
            if key in locked_set:
                for main_id, course_name in locked_assignments[key]:
                    if main_id not in all_classes:
                        logger.error(f"Invalid main_id {main_id} in locked assignments")
                        continue
                    child.append((day, slot, main_id, course_name))
                    temp_timetable[key].append(all_classes[main_id])
                    assert isinstance(all_classes[main_id], Class), f"temp_timetable contains non-Class object for main_id {main_id}"
            else:
                if key in parent2_dict:
                    main_id, course_name = parent2_dict[key]
                elif key in parent1_dict:
                    main_id, course_name = parent1_dict[key]
                else:
                    continue
                if main_id not in all_classes:
                    logger.error(f"Invalid main_id {main_id} in parent")
                    continue
                try:
                    validate_timetable_constraints(main_id, day, slot, current_year, current_semester, section, dept, timetable_cache, temp_timetable)
                    if course_name in main_courses:
                        prev_slot = temp_timetable.get((day, slot - 1), [])
                        next_slot = temp_timetable.get((day, slot + 1), [])
                        for c in prev_slot + next_slot:
                            if not isinstance(c, Class):
                                logger.error(f"Non-Class object in temp_timetable: {c}, main_id={main_id}, day={day}, slot={slot}")
                                continue
                            if c.course.name == course_name:
                                raise ValidationError(f"Cannot assign {course_name} consecutively in slot {slot} on day {day}")
                    child.append((day, slot, main_id, course_name))
                    temp_timetable[key].append(all_classes[main_id])
                    assert isinstance(all_classes[main_id], Class), f"temp_timetable contains non-Class object for main_id {main_id}"
                    logger.debug(f"Crossover: Assigned {course_name} to day {day}, slot {slot}, main_id {main_id}")
                except ValidationError as e:
                    logger.debug(f"Crossover validation failed for {course_name} on day {day}, slot {slot}: {e}")
                    if key in parent1_dict:
                        main_id, course_name = parent1_dict[key]
                        if main_id not in all_classes:
                            logger.error(f"Invalid main_id {main_id} in parent1 fallback")
                            continue
                        try:
                            validate_timetable_constraints(main_id, day, slot, current_year, current_semester, section, dept, timetable_cache, temp_timetable)
                            if course_name in main_courses:
                                prev_slot = temp_timetable.get((day, slot - 1), [])
                                next_slot = temp_timetable.get((day, slot + 1), [])
                                for c in prev_slot + next_slot:
                                    if not isinstance(c, Class):
                                        logger.error(f"Non-Class object in temp_timetable: {c}, main_id={main_id}, day={day}, slot={slot}")
                                        continue
                                    if c.course.name == course_name:
                                        raise ValidationError(f"Cannot assign {course_name} consecutively in slot {slot} on day {day}")
                            child.append((day, slot, main_id, course_name))
                            temp_timetable[key].append(all_classes[main_id])
                            assert isinstance(all_classes[main_id], Class), f"temp_timetable contains non-Class object for main_id {main_id}"
                            logger.debug(f"Crossover: Fallback assigned {course_name} to day {day}, slot {slot}, main_id {main_id}")
                        except ValidationError as e:
                            logger.debug(f"Crossover fallback failed for {course_name} on day {day}, slot {slot}: {e}")
                            continue
    logger.debug("exiting crossover")
    return child

def mutate(individual, generation, max_generations, current_year, current_semester, section, dept, timetable_cache=None):
    logger.debug("entered mutate")
    if not individual:
        return individual

    mutation_rate = max(0.5 - (0.4 * generation / max_generations), 0.1)
    course_slots = {course: sum(1 for _, _, _, c in individual if c == course) for course in COURSE_SLOT_REQUIREMENTS}
    main_courses = {cls.course.name for cls in all_classes.values() if cls.course.course_type == 'none'}
    temp_timetable = defaultdict(list)
    for day, slot, main_id, _ in individual:
        if main_id not in all_classes:
            logger.error(f"Invalid main_id {main_id} in individual")
            continue
        temp_timetable[(day, slot)].append(all_classes[main_id])
        assert isinstance(all_classes[main_id], Class), f"temp_timetable contains non-Class object for main_id {main_id}"

    available_slots = [(day, slot) for day in DAYS for slot in TIME_SLOTS if (day, slot) not in [(d, s) for d, s, _, _ in individual]]
    random.shuffle(available_slots)

    for day, slot in available_slots:
        under_assigned_courses = [c for c, count in course_slots.items() if count < COURSE_SLOT_REQUIREMENTS[c]]
        if not under_assigned_courses:
            break
        course_name = random.choice(under_assigned_courses)
        valid_classes = [main_id for main_id in course_class_map[course_name] if main_id in all_classes]
        if valid_classes:
            main_id = random.choice(valid_classes)
            try:
                validate_timetable_constraints(main_id, day, slot, current_year, current_semester, section, dept, timetable_cache, temp_timetable)
                if course_name in main_courses:
                    prev_slot = temp_timetable.get((day, slot - 1), [])
                    next_slot = temp_timetable.get((day, slot + 1), [])
                    for c in prev_slot + next_slot:
                        if not isinstance(c, Class):
                            logger.error(f"Non-Class object in temp_timetable: {c}, main_id={main_id}, day={day}, slot={slot}")
                            continue
                        if c.course.name == course_name:
                            raise ValidationError(f"Cannot assign {course_name} consecutively in slot {slot} on day {day}")
                individual.append((day, slot, main_id, course_name))
                temp_timetable[(day, slot)].append(all_classes[main_id])
                assert isinstance(all_classes[main_id], Class), f"temp_timetable appended non-Class object for main_id {main_id}"
                course_slots[course_name] += 1
                logger.debug(f"Mutated: Added {course_name} to day {day}, slot {slot}")
            except ValidationError as e:
                logger.debug(f"Mutation failed for {course_name} on day {day}, slot {slot}: {e}")

    for i in range(len(individual)):
        day, slot, main_id, old_course = individual[i]
        if (day, slot) in locked_slots:
            continue
        if main_id not in all_classes:
            logger.error(f"Invalid main_id {main_id} in individual for mutation")
            continue
        if random.random() < mutation_rate:
            available_courses = [c for c, count in course_slots.items()
                                if count < COURSE_SLOT_REQUIREMENTS[c] and c != old_course]
            if available_courses:
                new_course = random.choice(available_courses)
                valid_classes = [main_id for main_id in course_class_map[new_course] if main_id in all_classes]
                if valid_classes:
                    main_id = random.choice(valid_classes)
                    try:
                        validate_timetable_constraints(main_id, day, slot, current_year, current_semester, section, dept, timetable_cache, temp_timetable)
                        if new_course in main_courses:
                            prev_slot = temp_timetable.get((day, slot - 1), [])
                            next_slot = temp_timetable.get((day, slot + 1), [])
                            for c in prev_slot + next_slot:
                                if not isinstance(c, Class):
                                    logger.error(f"Non-Class object in temp_timetable: {c}, main_id={main_id}, day={day}, slot={slot}")
                                    continue
                                if c.course.name == new_course:
                                    raise ValidationError(f"Cannot assign {new_course} consecutively in slot {slot} on day {day}")
                        temp_timetable[(day, slot)] = [all_classes[main_id]]
                        assert isinstance(all_classes[main_id], Class), f"temp_timetable updated with non-Class object for main_id {main_id}"
                        individual[i] = (day, slot, main_id, new_course)
                        course_slots[old_course] -= 1
                        course_slots[new_course] += 1
                        logger.debug(f"Mutated: Changed {old_course} to {new_course} on day {day}, slot {slot}")
                    except ValidationError as e:
                        logger.debug(f"Mutation failed for {new_course} on day {day}, slot {slot}: {e}")
    logger.debug("exiting mutate")
    return individual

def evaluate_population(population, current_year, current_semester, section, dept, timetable_cache=None):
    return [fitness(ind, current_year, current_semester, section, dept, timetable_cache) for ind in population]

def load_locked_slots(current_year, current_semester, section, dept, all_classes):
    print("entered lock")
    global locked_slots, locked_assignments
    locked_slots.clear()
    locked_assignments.clear()

    qs = Timetable.objects.select_related('main_id__course').filter(
        Q(main_id__academic_year=current_year,
          main_id__semester=current_semester,
          main_id__section_id=section,
          main_id__dept=dept) |
        Q(main_id__academic_year=current_year,
          main_id__semester=current_semester,
          main_id__section_id__isnull=True,
          main_id__dept__isnull=True,
          main_id__course__offered_to='all')
    ).values_list('day', 'slot', 'main_id__main_id', 'main_id__course__name')

    for day, slot, main_id, course_name in qs:
        if main_id not in all_classes:
            logger.warning(f"Skipping locked assignment for invalid main_id {main_id}")
            continue
        key = (day, slot)
        locked_slots.add(key)
        locked_assignments[key].append((main_id, course_name))
        logger.debug(f"Locked: day={day}, slot={slot}, main_id={main_id}, course={course_name}")
    print("exiting lock")

def run_ga_logic(current_year, current_semester, section, dept, count=0):
    print("Running Optimized Genetic Algorithm...")
        
    global all_classes, course_class_map
    all_classes = {}
    course_class_map = defaultdict(list)
    
    if count == 0:
        COURSE_SLOT_REQUIREMENTS.clear()
        all_classes.clear()
        course_class_map.clear()
    
    timetable_cache = {
        (day, slot): list(Timetable.objects.select_related('main_id__course').prefetch_related('main_id__faculty').filter(
            Q(day=day, slot=slot,
              main_id__academic_year=current_year,
              main_id__semester=current_semester,
              main_id__section_id=section,
              main_id__dept=dept) |
            Q(day=day, slot=slot,
              main_id__academic_year=current_year,
              main_id__semester=current_semester,
              main_id__section_id__isnull=True,
              main_id__dept__isnull=True,
              main_id__course__offered_to='all')
        )) for day in DAYS for slot in TIME_SLOTS
    }
    
    # Fetch all Class instances and store in a dictionary
    # Validate all_classes
    all_classes = { 
        cls.main_id: cls
        for cls in Class.objects.select_related('course').prefetch_related('faculty').filter(
            Q(academic_year=current_year,
            semester=current_semester,
            section_id=section,
            dept=dept) |
            Q(academic_year=current_year,
            semester=current_semester,
            section_id__isnull=True, 
            dept__isnull=True,
            course__offered_to='all')
        )
        if isinstance(cls, Class)
    }
    #print(f"all_classes keys: {list(all_classes.keys())}")

    # Validate course_class_map
    for cls in all_classes.values():
        if cls.course and cls.course.name:
            course_class_map[cls.course.name].append(cls.main_id)
    for course_name, main_ids in course_class_map.items():
        invalid_ids = [mid for mid in main_ids if mid not in all_classes]
        if invalid_ids:
            print(f"Invalid main_ids in course_class_map for {course_name}: {invalid_ids}")
            course_class_map[course_name] = [mid for mid in main_ids if mid in all_classes]

    # Validate locked_assignments
    invalid_locked = []
    for (day, slot), assignments in locked_assignments.items():
        valid_assignments = [(mid, cname) for mid, cname in assignments if mid in all_classes]
        if len(valid_assignments) != len(assignments):
            invalid_locked.append((day, slot, [mid for mid, _ in assignments if mid not in all_classes]))
        locked_assignments[(day, slot)] = valid_assignments
    if invalid_locked:
        print(f"Invalid main_ids in locked_assignments: {invalid_locked}")

    classes = Class.objects.filter(
        Q(academic_year=current_year,
          semester=current_semester,
          section_id=section,
          dept=dept) |
        Q(academic_year=current_year,
          semester=current_semester,
          section_id__isnull=True, 
          dept__isnull=True,
          course__offered_to='all')
    )

    relevant_courses = set(cls.course for cls in classes)    
    for course in relevant_courses:
        if course.course_type == 'none':
            COURSE_SLOT_REQUIREMENTS[course.name] = course.hours_per_week

    load_locked_slots(current_year, current_semester, section, dept, all_classes)

    population = generate_population(current_year, current_semester, section, dept, size=20, timetable_cache=timetable_cache)

    generations = 20
    best_fitness = -float('inf')
    stagnation_count = 0
    best_solution = None

    for gen in range(generations):
        fitness_scores = evaluate_population(population, current_year, current_semester, section, dept, timetable_cache)
        sorted_pop = [(score, individual) for score, individual in zip(fitness_scores, population)]
        sorted_pop.sort(reverse=True)

        current_best_fitness = sorted_pop[0][0]
        if current_best_fitness > best_fitness:
            best_fitness = current_best_fitness
            best_solution = sorted_pop[0][1]
            stagnation_count = 0
            print(f"Generation {gen}: New best fitness: {best_fitness}")
        else:
            stagnation_count += 1

        if stagnation_count >= 20:
            print(f"Early stopping at generation {gen} - No improvement for {stagnation_count} generations")
            break

        population_size = max(10, len(population)//2) if stagnation_count > 5 else 20

        population = [individual for _, individual in sorted_pop]
        elite_count = max(3, population_size // 10)
        parents = population[:population_size // 2]
        next_generation = population[:elite_count]

        for _ in range(population_size - elite_count):
            parent1, parent2 = random.sample(parents, 2)
            child = crossover(parent1, parent2, current_year, current_semester, section, dept, timetable_cache)
            child = mutate(child, gen, generations, current_year, current_semester, section, dept, timetable_cache)
            next_generation.append(child)

        population = next_generation

    if best_solution is None:
        best_solution = max(population, key=lambda ind: fitness(ind, current_year, current_semester, section, dept, timetable_cache))

    print(f"Best fitness achieved: {best_fitness}")
    logger.debug(f"best_solution: {[(day, slot, main_id, course_name) for day, slot, main_id, course_name in best_solution]}")

    valid_solution = True
    constraint_violations = 0
    temp_timetable = defaultdict(list)
    for day, slot, main_id, _ in best_solution:
        if main_id not in all_classes:
            logger.error(f"Invalid main_id {main_id} in best_solution, not in all_classes")
            constraint_violations += 1
            valid_solution = False
            continue
        temp_timetable[(day, slot)].append(all_classes[main_id])
        assert isinstance(all_classes[main_id], Class), f"temp_timetable contains non-Class object for main_id {main_id}"

    # Log temp_timetable contents
    logger.debug(f"temp_timetable: {[(k, [type(c) for c in v]) for k, v in temp_timetable.items()]}")

    for day, slot, main_id, course_name in best_solution:
        if (day, slot) in locked_slots:
            continue
        if main_id not in all_classes:
            logger.error(f"Skipping validation for invalid main_id {main_id}")
            constraint_violations += 1
            valid_solution = False
            continue
        try:
            validate_timetable_constraints(main_id, day, slot, current_year, current_semester, section, dept, timetable_cache, temp_timetable)
            cls = all_classes[main_id]
            if cls.course.course_type == 'none':
                prev_slot = temp_timetable.get((day, slot - 1), [])
                next_slot = temp_timetable.get((day, slot + 1), [])
                for c in prev_slot + next_slot:
                    if not isinstance(c, Class):
                        logger.error(f"Non-Class object in temp_timetable: {c}, main_id={main_id}, day={day}, slot={slot}")
                        continue
                    if c.course.name == course_name:
                        raise ValidationError(f"Consecutive main course {course_name} in slot {slot} on day {day}")
        except ValidationError as e:
            constraint_violations += 1
            valid_solution = False
            logger.error(f"Invalid assignment in best solution: main_id={main_id}, day={day}, slot={slot}: {e}")

    # Check COURSE_SLOT_REQUIREMENTS
    scheduled_slots = defaultdict(int)
    for day, slot, main_id, course_name in best_solution:
        if (day, slot) in locked_slots:
            scheduled_slots[course_name] += 1
            continue
        if main_id not in all_classes:
            logger.error(f"Skipping slot count for invalid main_id {main_id}")
            continue
        try:
            validate_timetable_constraints(main_id, day, slot, current_year, current_semester, section, dept, timetable_cache, temp_timetable)
            cls = all_classes[main_id]
            if cls.course.course_type == 'none':
                prev_slot = temp_timetable.get((day, slot - 1), [])
                next_slot = temp_timetable.get((day, slot + 1), [])
                for c in prev_slot + next_slot:
                    if not isinstance(c, Class):
                        logger.error(f"Non-Class object in temp_timetable: {c}, main_id={main_id}, day={day}, slot={slot}")
                        continue
                    if c.course.name == course_name:
                        raise ValidationError(f"Consecutive main course {course_name} in slot {slot} on day {day}")
            scheduled_slots[course_name] += 1
        except ValidationError as e:
            logger.error(f"Skipping slot count for main_id={main_id}, day={day}, slot={slot}: {e}")

    print(COURSE_SLOT_REQUIREMENTS)
    print(scheduled_slots)

    requirements_met = True
    for course, required in COURSE_SLOT_REQUIREMENTS.items():
        if course not in scheduled_slots or scheduled_slots[course] != required:
            requirements_met = False
            print(f"Requirement not met for {course}: scheduled {scheduled_slots.get(course, 0)} vs required {required}")

    # Retry if solution is invalid or requirements not met
    if (not valid_solution or not requirements_met) and count < 5:
        print(f"Retry {count + 1}: {constraint_violations} constraint violations, Requirements Met={requirements_met}")
        return run_ga_logic(current_year, current_semester, section, dept, count + 1)

    # Build a Q object to match all locked (day, slot) pairs
    locked_conditions = Q()
    for day, slot in locked_slots:
        locked_conditions |= Q(day=day, slot=slot)

    # Delete only entries that are NOT in locked slots
    if locked_conditions:
        Timetable.objects.filter(
            Q(main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id=section, main_id__dept=dept) | 
            Q(main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id__isnull=True, main_id__dept__isnull=True, main_id__course__offered_to='all')
        ).exclude(locked_conditions).delete()
    else:
        Timetable.objects.filter(
            Q(main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id=section, main_id__dept=dept) |
            Q(main_id__academic_year=current_year, main_id__semester=current_semester, main_id__section_id__isnull=True, main_id__dept__isnull=True, main_id__course__offered_to='all')
        ).delete()

    # Save timetable entries
    successful_assignments = 0
    for day, slot, main_id, course_name in best_solution:
        if (day, slot) in locked_slots:
            continue
        if main_id not in all_classes:
            logger.error(f"Skipping save for invalid main_id {main_id}")
            continue
        try:
            # Revalidate before saving
            validate_timetable_constraints(main_id, day, slot, current_year, current_semester, section, dept, timetable_cache, temp_timetable)
            Timetable.objects.create(
                main_id=all_classes[main_id],
                day=day,
                slot=slot
            )
            successful_assignments += 1
            logger.info(f"Created timetable entry for main_id {main_id}, day {day}, slot {slot}")
        except ValidationError as e:
            logger.error(f"Failed to create timetable entry for main_id {main_id}, day {day}, slot {slot}: {e}")
        except Exception as e:
            logger.error(f"Error creating timetable entry: {e}")

    print(f"Created {successful_assignments} timetable entries")

    timetable_status, _ = TimetableStatus.objects.get_or_create(
        academic_year=current_year,
        semester=current_semester,
        section=section,
        dept=dept,
        defaults={'id': 1})
    if requirements_met:
        timetable_status.status = 'completed' 
        timetable_status.save()
        print("Optimized Genetic Algorithm completed successfully.")
    else:
        print("Optimized Genetic Algorithm completed with partial solution.")