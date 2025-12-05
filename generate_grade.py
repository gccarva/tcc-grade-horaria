from frozendict import frozendict
import pandas as pd
import yaml
from main import evalOneMax,get_hours_from_bitmask
from schedule_data_loader import ScheduleData

TIME_SLOT_MAP = {
    1: ("08:00", "Segunda"), 2: ("10:00", "Segunda"), 3: ("13:30", "Segunda"), 4: ("15:30", "Segunda"),
    5: ("08:00", "Terça"), 6: ("10:00", "Terça"), 7: ("13:30", "Terça"), 8: ("15:30", "Terça"),
    9: ("08:00", "Quarta"), 10: ("10:00", "Quarta"), 11: ("13:30", "Quarta"), 12: ("15:30", "Quarta"),
    13: ("08:00", "Quinta"), 14: ("10:00", "Quinta"), 15: ("13:30", "Quinta"), 16: ("15:30", "Quinta"),
    17: ("08:00", "Sexta"), 18: ("10:00", "Sexta"), 19: ("13:30", "Sexta"), 20: ("15:30", "Sexta")
}

TIME_SLOTS = [
    "08:00","08:50","10:00","10:50","11:40","13:30","14:20","15:30","16:20","17:10",
]
DAYS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]
EMPTY_CELL = "------"

def generate_schedule_csv(entity_type, entity_range, schedule_data, grade, time_slots, days):
    for entity_id in entity_range:
        schedule_matrix = pd.DataFrame(index=time_slots, columns=days)
        schedule_matrix = schedule_matrix.fillna(EMPTY_CELL)

        if entity_type == 'semester':
            courses = schedule_data.get_courses_for_semester(entity_id)
        elif entity_type == 'professor':
            courses = schedule_data.get_courses_for_professor(entity_id)
        else:
            continue

        for lecture in courses:
            hours = []
            name = lecture
            for hour in get_hours_from_bitmask(grade[lecture]):
                start_time, day = TIME_SLOT_MAP[hour]
                hours.append((start_time, day))
                hours.append((time_slots[time_slots.index(start_time) + 1], day))

            if schedule_data.get_course_properties()[name].get("duration_rule") == "single_and_half":
                hours.append((time_slots[time_slots.index(hours[0][0])+2], hours[0][1]))

            if len(name) < 6:
                name =" " * ((6 - len(name)+1)//2) + name + " " *( (6 - len(name))//2)

            for hour, day in hours:
                if schedule_matrix.loc[hour, day] == EMPTY_CELL:
                    schedule_matrix.loc[hour, day] = name
                else:
                    schedule_matrix.loc[hour, day] += f"/{name}"

        schedule_matrix.to_csv(f"output/grade_horaria_{entity_type}_{entity_id}.csv")

if __name__ == "__main__":
    melhor =[18, 17, 15, 4, 10, 1, 3, 4, 18, 17, 2, 9, 5, 18, 14, 11, 12, 4, 6, 13, 6, 10, 9, 14, 3, 2, 5, 13, 18, 17, 7, 15, 8, 16, 7, 15, 6, 5, 13, 1, 17, 18, 14, 13, 5, 14, 1, 2, 20, 19, 16, 8, 1, 2]
    
    
    schedule_data = ScheduleData.from_config(
            "config.yaml"
        )
    grade = schedule_data.from_individual(melhor)
    with open("config.yaml", 'r') as f:
        config = yaml.safe_load(f)  
    
    print(schedule_data.get_laboratory_classes(),evalOneMax(melhor,frozendict(config),schedule_data))
    generate_schedule_csv('semester', range(1, 10), schedule_data, grade, TIME_SLOTS, DAYS)
    generate_schedule_csv('professor', range(1, 16), schedule_data, grade, TIME_SLOTS, DAYS)
