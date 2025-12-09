from functools import lru_cache
import multiprocessing
import random
from deap import creator, base, tools, algorithms
import pandas as pd
from schedule_data_loader import ScheduleData
import functools
import time
import yaml
import argparse
from frozendict import frozendict
import numpy as np
import os

@lru_cache(100000)
def get_hours_from_bitmask(bitmask):
    hours = []
    for i in range(21):
        if bitmask & (1 << i):
            hours.append(i)
    return hours

    


def fitness(individual,config,schedule_data):
    answer = 1000000
    individual = tuple(individual)
    schedule = schedule_data.from_individual(individual)
    course_properties = schedule_data.get_course_properties()
    for course_name, properties in course_properties.items():
        if properties.get('duration_rule') == 'single_and_half':
            lectureb = schedule.get(course_name)
            lecture = get_hours_from_bitmask(lectureb)
            if lecture and (lecture[0] % 4 == 1 or lecture[0] % 4 == 3):
                schedule[course_name] = lectureb | 1 << (lecture[0]+1)
        if properties.get('duration_rule') == 'double_tog':
            lectureb = schedule.get(course_name)
            lecture = get_hours_from_bitmask(lectureb)

            if len(lecture) > 1 and ((lecture[0]-1) % 4 != (lecture[1]-1) % 4 -1) and abs(lecture[0]-lecture[1]) != 1:
                answer -= config["punishment_pref_classes"]
        if properties.get('duration_rule') == 'double_sep':
            lectureb = schedule.get(course_name)
            lecture = get_hours_from_bitmask(lectureb)
            if len(lecture) > 1 and (lecture[0]-1) // 4 == (lecture[1]-1) // 4 and abs(lecture[0]-lecture[1]) == 1:
                answer -= config["punishment_pref_classes"]
    for professor in range(1,schedule_data.get_len_professor()+1):
        lectures_days = [0,0,0,0,0]
        cont_lectures_days = [0,0,0,0,0]
        for lecture in schedule_data.get_courses_for_professor(professor):
            hours = schedule[lecture]
            hours =get_hours_from_bitmask(hours)
 
            if len(hours) > 2 or not hours:
                answer -= 500*10
                continue
            if len(hours) == 2:
                lectures_days[(hours[0] - 1)//4] = 1
                lectures_days[(hours[1] - 1)//4] = 1
                cont_lectures_days[(hours[0] - 1)//4] += 1
                cont_lectures_days[(hours[1] - 1)//4] += 1
            else:
                lectures_days[(hours[0] - 1)//4] = 1
                cont_lectures_days[(hours[0] - 1)//4] += 1
            if sum(lectures_days) > int(config["limit_days_professor"]):
                cont_lectures_days = sorted(cont_lectures_days)
                answer -= int(config["punishment_limit_days_professor"])*sum(cont_lectures_days[:5-int(config["limit_days_professor"])])
    lab_hours = [0 for _ in range(20)]
    for lecture in schedule_data.get_laboratory_classes():
        hours = schedule[lecture]
        hours =get_hours_from_bitmask(hours)
        if len(hours) == 2:
            lab_hours[hours[0] - 1] += 1
            if lab_hours[hours[0] - 1] > 4:
                answer -= 500
            lab_hours[hours[1] - 1] += 1
            if lab_hours[hours[1] - 1] > 4:
                answer -= 500
        else:
            lab_hours[hours[0] - 1] += 1
            if lab_hours[hours[0] - 1] > 4:
                answer -= 500
            



    for prof_id in range(1, schedule_data.get_len_professor()+1):
        restricted_slots = schedule_data.get_professor_constraints(prof_id)
        if not restricted_slots:
            continue

        prof_courses = schedule_data.get_courses_for_professor(prof_id)
        prof_lectures = [schedule.get(course) for course in prof_courses if schedule.get(course)]
        
        for lecture in prof_lectures:
            if any(slot & lecture for slot in restricted_slots):
                answer -= 500

   
    for i in range(config["all_day_start_semester"], schedule_data.get_len_semester()+1):
        semester_courses = schedule_data.get_courses_for_semester(i)
        semester_lectures = [schedule.get(course) for course in semester_courses if schedule.get(course)]
        for lecture in semester_lectures:
            hours_after =1677720
            if lecture & hours_after:
                answer -= 500


    for i in range(len(schedule_data.all_courses)):
        class_ = schedule_data.get_schedule_for_class_index(i)
        class_ = get_hours_from_bitmask(class_)
        if class_ and len(class_) == 2:
            a, b = class_[0], class_[1]
            if b < a: a, b = b, a
            if (a - 1) // 4 == (b - 1) // 4:
                if a + 1 != b:
                    answer -= 500
            else:
                if (a - 1) // 4 + 1 == (b - 1) // 4 or ((a - 1) // 4 == 0 and (b - 1) // 4 == 4):
                    answer -= 500

 
    for semester_id in range(1, schedule_data.get_len_semester()+1):
        semester_courses = schedule_data.get_courses_for_semester(semester_id)
        semester_lectures = [schedule.get(course) for course in semester_courses if schedule.get(course)]
        seen_slots = 0
        for lesson in semester_lectures:

            if lesson & seen_slots:
                answer -= 500
            else:

                seen_slots |= lesson
        for i in range(0,20,4):
            
            hours_dayb = (seen_slots >> (i+1)) & 15
            hours_day = get_hours_from_bitmask(hours_dayb)
            actualtime = -1
            if hours_day:
                actualtime = hours_day[0]
                for i in range(1,len(hours_day)):
                    if hours_day[i] != actualtime + 1:
                        answer -= config["punishment_gap_classes"]
                    actualtime = hours_day[i]

    for prof_id in range(1, schedule_data.get_len_professor()+1):
        prof_courses = schedule_data.get_courses_for_professor(prof_id)
        prof_lectures = [schedule.get(course) for course in prof_courses if schedule.get(course)]
        seen_slots = 0
        for lesson in prof_lectures:
            if lesson & seen_slots:
                answer -= 500
            else:
                seen_slots |= lesson


    
    for i in range(1, schedule_data.get_len_student()+1):
        maximo = 0
        student_schedules = schedule_data.get_filtered_student_schedules(i)
        for possibility in student_schedules:
            maximo = max(maximo, without_repetitions(possibility))
        answer += maximo

    return answer,



@lru_cache(maxsize=200000) 
def _solve_recursive(sets_tuple):


    if not sets_tuple:
            return 0

    current_set_mask = sets_tuple[0]
    tail_sets_tuple = sets_tuple[1:]
    compatible_sets_in_tail = tuple(s_mask for s_mask in tail_sets_tuple if not (s_mask & current_set_mask))
    if len(tail_sets_tuple)-len(compatible_sets_in_tail) <= 1:
        return _solve_recursive(compatible_sets_in_tail) + 1
    res_without = _solve_recursive(tail_sets_tuple)
    res_with = 1 + _solve_recursive(compatible_sets_in_tail)
    
    return max(res_with, res_without)


def without_repetitions(tuples_list):
    """
    Wrapper function to find the size of the maximum subset of mutually
    disjoint sets.
    """

    sets_of_size_1 = set()
    for s_int in tuples_list:

        if (s_int != 0) and ((s_int & (s_int - 1)) == 0):

            sets_of_size_1.add(s_int)
            


    filtered_sets_as_integers = []
    for s_int in tuples_list:
        is_compatible = True
        for single_elem in sets_of_size_1:
            if (s_int & single_elem): 
                is_compatible = False
                break
        if is_compatible:
            filtered_sets_as_integers.append(s_int)

    sets_tuple = tuple(sorted(filtered_sets_as_integers))
    
    return _solve_recursive(sets_tuple)+len(sets_of_size_1)





def fast_roulette_selection(individuals, k):
    """Vectorized roulette wheel selection using NumPy"""

    fitnesses = np.array([ind.fitness.values[0] for ind in individuals])
    fitnesses = fitnesses.astype(np.float64)
    fitnesses = np.maximum(fitnesses, 0.00001)  
    fitnesses = fitnesses - fitnesses.min()  
    fitnesses = fitnesses/fitnesses.sum()  

    if fitnesses.min() < 0:
        fitnesses = fitnesses - fitnesses.min()
    

    total_fitness = fitnesses.sum()
    if total_fitness == 0:

        probs = np.ones(len(individuals)) / len(individuals)
    else:
        probs = fitnesses / total_fitness
    selected_indices = np.random.choice(len(individuals), size=k, p=probs)
    return [individuals[i] for i in selected_indices]

def main():
    schedule_data = ScheduleData.from_config("config.yaml")
    with open("config.yaml", 'r') as f:
            config = yaml.safe_load(f)
            creator.create("FitnessMax", base.Fitness, weights=(1.0,))
            creator.create("Individual", list, fitness=creator.FitnessMax)

            CXPB, MUTPBS, NGEN, N_ELITES, N = config["crossover_prob"], config["mutation_prob"],  config["num_generations"] , config["num_elites"], config["population_size"]
            selection_method = config["selection_method"]
            mutation_method = config["mutation_method"]
            toolbox = base.Toolbox()
            toolbox.register("attr_int", random.randint, 1, 20)
            n_genes = 0
            for course_name in schedule_data.all_courses:
                properties = schedule_data.course_properties.get(course_name, {})
                if properties.get('fixed_slots'):
                    continue
                duration = 2 if properties.get('duration_rule') in ['double',"double_sep","double_tog"] else 1
                n_genes += duration

           

            
            toolbox.register("evaluate", fitness, config=frozendict(config),schedule_data=schedule_data)
            toolbox.register("mate", tools.cxTwoPoint)
            os.makedirs(f"output/{selection_method}_{mutation_method}_{MUTPBS}_{CXPB}", exist_ok=True)
            if mutation_method == "uniform":
                    toolbox.register("mutates", tools.mutUniformInt, low=1, up=20, indpb=0.1)
            else:
                toolbox.register("mutates", tools.mutShuffleIndexes, indpb=0.1)

            if selection_method == "roulette":
                toolbox.register("select", fast_roulette_selection)
            else:
                toolbox.register("select", tools.selTournament, tournsize=config["tournament_size"])
            for a in range(config["num_runs"]):
                df = pd.DataFrame()

                random.seed(a)
                toolbox.register("individual", tools.initRepeat, creator.Individual, toolbox.attr_int, n=n_genes)
                toolbox.register("population", tools.initRepeat, list, toolbox.individual)
                pool = multiprocessing.Pool(processes=max(1, multiprocessing.cpu_count()-2))
                toolbox.register("map", pool.map)


                population = toolbox.population(n=N)
                
                fitnesses = toolbox.map(toolbox.evaluate, population)
                for ind, fit in zip(population, fitnesses):
                    ind.fitness.values = fit
                for gen in range(NGEN):
                    timestart = time.time()
                    elites = tools.selBest(population, k=N_ELITES)
                    elites = [toolbox.clone(ind) for ind in elites]

                    offspring = toolbox.select(population, k=len(population) - N_ELITES)
                    offspring = [toolbox.clone(ind) for ind in offspring]

                    for i in range(1, len(offspring), 2):
                        if random.random() < CXPB:
                            offspring[i - 1], offspring[i] = toolbox.mate(offspring[i - 1],offspring[i])
                            del offspring[i - 1].fitness.values, offspring[i].fitness.values

                    for i in range(len(offspring)):
                        if random.random() < MUTPBS:
                            offspring[i], = toolbox.mutates(offspring[i])
                            del offspring[i].fitness.values

                    invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
                    fits = toolbox.map(toolbox.evaluate, invalid_ind)
                    for fit, ind in zip(fits, invalid_ind):
                        ind.fitness.values = fit
                    
                    population[:] = elites + offspring

                    fits = [ind.fitness.values[0] for ind in population]
                    mean = sum(fits) / len(population)
                    timeend = time.time()
                    row = {}
                    row["gen"] = gen
                    row["min"] = min(fits) - 1000000
                    row["max"] = max(fits) - 1000000
                    row["mean"] = round(mean, 2) - 1000000
                    row["median"] = round(np.median(fits), 2) - 1000000 
                    row["num_invalid"] = len(invalid_ind)
                    row["time"] = timeend - timestart
                    row["best_individual"] = str(tools.selBest(population, k=1)[0])

                    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
                df.to_csv(f"output/{selection_method}_{mutation_method}_{MUTPBS}_{CXPB}/run{a}.csv", index=False)
                pool.close()
                pool.join()

        

                top10 = tools.selBest(population, k=10)
                melhor = top10[0]
                print(f"Best individual in run {a} is {melhor}, {melhor.fitness.values}")
  


if __name__ == "__main__":
    main()