import csv
import itertools
from collections import defaultdict
import yaml
import random

class ScheduleData:
    @classmethod
    def from_config(cls, config_path):
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return cls(
            semesters_csv_path=config['semesters_csv_path'],
            professors_csv_path=config['professors_csv_path'],
            students_csv_path=config['students_data_csv_path'],
            student_restrictions_csv_path=config['student_restrictions_csv_path'],
            professor_constraints_csv_path=config['professor_constraints_csv_path'],
            course_properties_csv_path=config['course_properties_csv_path'],
            swappable_courses_csv_path=config['swappable_courses_csv_path']
        )

    def __init__(self, semesters_csv_path, professors_csv_path, students_csv_path,
                 student_restrictions_csv_path, professor_constraints_csv_path,
                 course_properties_csv_path, swappable_courses_csv_path):
        self.laboratory_classes = []
        self.current_schedule = {}
        self.semesters = self._load_semesters(semesters_csv_path)
        self.professors = self._load_professors(professors_csv_path)
        self.swappable_courses = self._load_swappable_courses(swappable_courses_csv_path)
        self.students = self._load_students(students_csv_path, self.swappable_courses)
        self.student_restrictions = self._load_student_restrictions(student_restrictions_csv_path)
        self.professor_constraints = self._load_professor_constraints(professor_constraints_csv_path)
        self.course_properties = self._load_course_properties(course_properties_csv_path)
        self.all_courses = self._get_all_courses()
        self.course_to_index = {course: i for i, course in enumerate(self.all_courses)}


    def _get_all_courses(self):
        all_courses = set()
        for courses in self.semesters.values():
            all_courses.update(courses)
        return sorted(list(all_courses))

    def from_individual(self, individual):
        self.current_schedule = {}
        idx = 0
        for course_name in self.all_courses:
            properties = self.course_properties.get(course_name, {})
            duration = 2 if properties.get('duration_rule') in ['double',"double_tog","double_sep"] else 1

            if properties.get('fixed_slots'):
                self.current_schedule[course_name] = tuple(properties['fixed_slots'])
                continue

            if idx + duration > len(individual):
                # Avoid index out of bounds if individual is not perfectly sized
                continue

            if duration == 1:
                self.current_schedule[course_name] = 1 << individual[idx]
                idx += 1
            else: # duration == 2
                if individual[idx] ==  individual[idx+1]:
                        
                    self.current_schedule[course_name] =  1048575
                else:
                    self.current_schedule[course_name] = 1 << individual[idx] | 1 << individual[idx+1]
                idx += 2
        return self.current_schedule

    def _load_semesters(self, file_path):
        semesters = defaultdict(list)
        try:
            with open(file_path, mode='r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    semesters[int(row['semester_id'])].append(row['course_name'])
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Semesters data will be empty.")
        return dict(semesters)

    def _load_professors(self, file_path):
        professors = defaultdict(list)
        try:
            with open(file_path, mode='r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    professors[int(row['professor_id'])].append(row['course_name'])
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Professors data will be empty.")
        return dict(professors)

    def _load_swappable_courses(self, file_path):
        swappable = defaultdict(list)
        try:
            with open(file_path, mode='r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    swappable[row['substitution_tag']].append(row['course_name'])
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Swappable courses data will be empty.")
        return dict(swappable)

    def _load_students(self, file_path, swappable_courses):
        base_schedules = defaultdict(list)
        try:
            with open(file_path, mode='r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    base_schedules[int(row['student_id'])].append(row['course_name'])
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Students data will be empty.")
            return {}

        final_schedules = {}
        for student_id, base_schedule in base_schedules.items():
            core_courses = [course for course in base_schedule if not course.startswith('SUB_')]

            swap_tags = [course for course in base_schedule if course.startswith('SUB_')]

            swap_options = []
            for tag in swap_tags:
                if tag in swappable_courses:
                    swap_options.append(swappable_courses[tag])

            if not swap_options:
                final_schedules[student_id] = [core_courses]
                continue

            combinations = list(itertools.product(*swap_options))

            student_possibilities = []
            for combo in combinations:
                new_schedule = core_courses + list(combo)
                if len(new_schedule) == len(set(new_schedule)): # Check for duplicates
                    student_possibilities.append(new_schedule)

            final_schedules[student_id] = student_possibilities

        return final_schedules

    def _load_student_restrictions(self, file_path):
        restrictions = defaultdict(list)
        try:
            with open(file_path, mode='r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    excluded_slots = 0
                    for x in row['excluded_slots'].split(','):
                        excluded_slots |= 1 << int(x.strip())
                    restrictions[int(row['student_id'])].append(excluded_slots)
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Student restrictions will be empty.")
        return dict(restrictions)

    def _load_professor_constraints(self, file_path):
        constraints = {}
        try:
            with open(file_path, mode='r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    # Convert restricted_slots to a bitmask
                    restricted_slots_mask = 0
                    for x in row['restricted_slots'].split(','):
                        restricted_slots_mask |= (1 << int(x.strip()))
                    constraints[int(row['professor_id'])] = [restricted_slots_mask]
                    
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Professor constraints will be empty.")
        return constraints

    def _load_course_properties(self, file_path):
        properties = {}
        try:
            with open(file_path, mode='r', encoding='utf-8') as infile:
                reader = csv.DictReader(infile)
                for row in reader:
                    fixed_slots = []
                    if row.get('fixed_slots'):
                        fixed_slots = [int(x.strip()) for x in row['fixed_slots'].split(',')]
                    properties[row['course_name']] = {
                        'duration_rule': row['duration_rule'],
                        'fixed_slots': fixed_slots
                    }
                    if int(row.get("use_laboratory")):
                        self.laboratory_classes.append(row['course_name'])
        except FileNotFoundError:
            print(f"Warning: {file_path} not found. Course properties will be empty.")
        return properties

    def get_len_semester(self):
        return len(self.semesters.keys())
    
    def get_len_professor(self):
        return len(self.professors.keys())
    
    def get_len_student(self):
        return len(self.students.keys())
    
    def get_len_course(self):
        return len(self.all_courses)
    def get_laboratory_classes(self):
        return self.laboratory_classes


    def get_courses_for_semester(self, semester_id):
        return self.semesters.get(semester_id, [])

    def get_courses_for_professor(self, professor_id):
        return self.professors.get(professor_id, [])

    def get_student_schedules(self, student_id):
        return self.students.get(student_id, [])

    def get_professor_constraints(self, professor_id):
        return self.professor_constraints.get(professor_id, [])

    def get_course_properties(self):
        return self.course_properties

    def get_course_schedule(self, course_name):
        return self.current_schedule.get(course_name)

    def get_schedule_for_class_index(self, index):
        if 0 <= index < len(self.all_courses):
            course_name = self.all_courses[index]
            return self.get_course_schedule(course_name)
        return None

    def get_filtered_student_schedules(self, student_id):
        initial_schedules_courses = self.get_student_schedules(student_id)
        student_restrictions = self.student_restrictions.get(student_id, [])

        final_schedules = []

        if not student_restrictions:
            for schedule_courses in initial_schedules_courses:
                schedule_tuples = [self.get_course_schedule(course) for course in schedule_courses]
                final_schedules.append([t for t in schedule_tuples if t is not None])
            return final_schedules


        for i, schedule_courses in enumerate(initial_schedules_courses):
            possibility_id = i + 1

            schedule_tuples = [self.get_course_schedule(course) for course in schedule_courses]
            schedule_tuples = [t for t in schedule_tuples if t is not None]

            for restriction in student_restrictions:
                # Assuming the structure of restriction is a list of dicts
                # and each dict has 'excluded_slots'
                excluded_slots = restriction
                filtered_list = []
                for lecture in schedule_tuples:
                    if lecture and not  (lecture & excluded_slots):
                        filtered_list.append(lecture)
                final_schedules.append(filtered_list)

        return final_schedules
