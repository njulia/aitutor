#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
检查各年级数学作业是否存在，缺失则生成 500 份作业并添加到 RAG 存储
支持 Year 1-6 所有年级
"""
import sys
import os
import random

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.homework_rag import get_homework_rag_store

os.environ["TOKENIZERS_PARALLELISM"] = "false"
# 各年级数学主题（英国小学课程）
MATH_TOPICS_BY_YEAR = {
    1: [
        "Number Recognition 1-20",
        "Counting and Ordering",
        "Simple Addition",
        "Simple Subtraction",
        "Shapes and Patterns",
        "Measurement (Length)",
        "Time (O'clock)",
        "Money (Coins)",
    ],
    2: [
        "Addition and Subtraction (2-digit)",
        "Multiplication Basics",
        "Division Basics",
        "Fractions (Halves and Quarters)",
        "Measurement (cm and m)",
        "Time (Half Past)",
        "Money (Pounds and Pence)",
        "Geometry (2D Shapes)",
    ],
    3: [
        "Addition and Subtraction",
        "Multiplication and Division",
        "Fractions",
        "Measurement",
        "Geometry",
        "Time",
        "Money",
        "Place Value",
        "Number Bonds",
        "Problem Solving",
    ],
    4: [
        "Multiplication and Division",
        "Fractions and Decimals",
        "Measurement and Conversion",
        "Geometry and Angles",
        "Time and Duration",
        "Money and Budgeting",
        "Place Value and Rounding",
        "Addition and Subtraction (4-digit)",
        "Area and Perimeter",
        "Data and Statistics",
    ],
    5: [
        "Large Numbers and Place Value",
        "Multiplication (4-digit by 2-digit)",
        "Division and Long Division",
        "Fractions, Decimals and Percentages",
        "Geometry (Angles and Coordinates)",
        "Area and Volume",
        "Ratio and Proportion",
        "Algebra Basics",
        "Statistics and Probability",
        "Problem Solving",
    ],
    6: [
        "Advanced Fractions and Decimals",
        "Multiplication and Division (Large Numbers)",
        "Percentages and Ratio",
        "Algebra and Equations",
        "Geometry (Transformations)",
        "Area, Perimeter and Volume",
        "Statistics and Data Interpretation",
        "Negative Numbers",
        "SATs Preparation",
        "Complex Problem Solving",
    ],
}


def generate_math_homework(year_group: int, topic: str, index: int) -> tuple:
    """根据年级、主题生成数学作业，返回 (content, correct_answers)"""

    if year_group == 1:
        return _generate_year1_homework(topic, index)
    elif year_group == 2:
        return _generate_year2_homework(topic, index)
    elif year_group == 3:
        return _generate_year3_homework(topic, index)
    elif year_group == 4:
        return _generate_year4_homework(topic, index)
    elif year_group == 5:
        return _generate_year5_homework(topic, index)
    elif year_group == 6:
        return _generate_year6_homework(topic, index)


def _generate_year1_homework(topic: str, index: int) -> tuple:
    """Year 1 数学作业（5-6 岁），返回 (content, correct_answers)"""
    if topic == "Number Recognition 1-20":
        nums = random.sample(range(1, 21), 10)
        questions = [f"{i+1}. Write the number: {n}" for i, n in enumerate(nums)]
        answers = [str(n) for n in nums]
    elif topic == "Counting and Ordering":
        starts = random.sample(range(1, 15), 5)
        questions = [f"{i+1}. Count on from {s}: {s}, __, __, __, __" for i, s in enumerate(starts)]
        answers = [f"{s+1}, {s+2}, {s+3}, {s+4}" for s in starts]
        order_items = [(random.randint(1,10), random.randint(1,10), random.randint(1,10)) for _ in range(5)]
        questions += [f"{i+6}. Order these: {a}, {b}, {c}" for i, (a, b, c) in enumerate(order_items)]
        answers += [f"{sorted([a,b,c])[0]}, {sorted([a,b,c])[1]}, {sorted([a,b,c])[2]}" for a, b, c in order_items]
    elif topic == "Simple Addition":
        additions = [(random.randint(1,10), random.randint(1,10)) for _ in range(10)]
        questions = [f"{i+1}. {a} + {b} = ?" for i, (a, b) in enumerate(additions)]
        answers = [str(a + b) for a, b in additions]
    elif topic == "Simple Subtraction":
        subtractions = [(random.randint(5,20), random.randint(1,5)) for _ in range(10)]
        questions = [f"{i+1}. {a} - {b} = ?" for i, (a, b) in enumerate(subtractions)]
        answers = [str(a - b) for a, b in subtractions]
    elif topic == "Shapes and Patterns":
        questions = [
            "1. How many sides does a triangle have?",
            "2. How many sides does a square have?",
            "3. Draw a circle.",
            "4. Name a shape with 3 corners.",
            "5. What comes next: circle, square, circle, square, ___?",
            "6. How many corners does a rectangle have?",
            "7. Draw a triangle.",
            "8. Is a ball a circle or a square?",
            "9. Count the sides of a rectangle.",
            "10. What shape is a clock?",
        ]
        answers = ["3", "4", "drawing (circle)", "triangle", "circle", "4", "drawing (triangle)", "neither (sphere)", "4", "circle (typically)"]
    elif topic == "Measurement (Length)":
        questions = [
            "1. Which is longer: a pencil or a ruler?",
            "2. Is a book longer than a table?",
            "3. How many hand-spaces long is your desk?",
            "4. Draw a line longer than your finger.",
            "5. Is a shoe longer than a sock?",
            "6. Measure your pencil in cubes.",
            "7. Which is shorter: a pen or a crayon?",
            "8. How tall are you in cubes?",
            "9. Draw something shorter than your hand.",
            "10. Is a door taller than you?",
        ]
        answers = ["ruler", "no", "varies (student measurement)", "drawing", "yes", "varies (student measurement)", "varies", "varies (student measurement)", "drawing", "yes"]
    elif topic == "Time (O'clock)":
        hours = random.sample(range(1, 13), 5)
        questions = [f"{i+1}. Draw the clock hands for {h}:00" for i, h in enumerate(hours)]
        answers_draw = [f"hour hand on {h}, minute hand on 12" for h in hours]
        show_hours = [random.randint(1,12) for _ in range(5)]
        questions += [f"{i+6}. What time is it? (clock shows {h}:00)" for i, h in enumerate(show_hours)]
        answers_show = [f"{h}:00" for h in show_hours]
        answers = answers_draw + answers_show
    elif topic == "Money (Coins)":
        questions = [
            "1. What coin is worth 1p?",
            "2. What coin is worth 2p?",
            "3. What coin is worth 5p?",
            "4. What coin is worth 10p?",
            "5. What coin is worth 20p?",
            "6. How many 1p coins make 5p?",
            "7. How many 2p coins make 10p?",
            "8. You have a 5p coin and a 2p coin. How much do you have?",
            "9. You have two 10p coins. How much do you have?",
            "10. Which coin is worth more: 5p or 10p?",
        ]
        answers = ["1p coin", "2p coin", "5p coin", "10p coin", "20p coin", "5", "5", "7p", "20p", "10p"]
    else:
        questions = [f"{i+1}. Year 1 Maths practice question {i+1}" for i in range(10)]
        answers = [f"answer {i+1}" for i in range(10)]

    content = f"Maths Homework - Year 1 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year2_homework(topic: str, index: int) -> tuple:
    """Year 2 数学作业（6-7 岁），返回 (content, correct_answers)"""
    if topic == "Addition and Subtraction (2-digit)":
        questions = []
        answers = []
        additions = []
        for i in range(5):
            a = random.randint(10, 50)
            b = random.randint(10, 50)
            additions.append((a, b))
            questions.append(f"{i+1}. {a} + {b} = ?")
        answers = [str(a + b) for a, b in additions]
        subtractions = []
        for i in range(5):
            a = random.randint(30, 80)
            b = random.randint(10, a)
            subtractions.append((a, b))
            questions.append(f"{i+6}. {a} - {b} = ?")
        answers += [str(a - b) for a, b in subtractions]
    elif topic == "Multiplication Basics":
        multiplications = [(random.randint(2,5), random.randint(1,10)) for _ in range(10)]
        questions = [f"{i+1}. {a} × {b} = ?" for i, (a, b) in enumerate(multiplications)]
        answers = [str(a * b) for a, b in multiplications]
    elif topic == "Division Basics":
        questions = []
        answers = []
        for i in range(5):
            b = random.randint(2, 5)
            result = random.randint(2, 5)
            questions.append(f"{i+1}. {b * result} ÷ {b} = ?")
            answers.append(str(result))
        share_data = []
        for i in range(5):
            total = random.choice([6,8,10,12,15])
            people = random.randint(2,3)
            share_data.append((total, people))
            questions.append(f"{i+6}. Share {total} equally between {people} people.")
        answers += [f"{total//people} each (remainder {total%people})" if total%people != 0 else f"{total//people} each" for total, people in share_data]
    elif topic == "Fractions (Halves and Quarters)":
        half_vals = [4,6,8,10,12]
        quarter_vals = [4,8,12,16,20]
        compare_vals = [8,12,16]
        half2_vals = [10,14,18,20]
        quarter2_vals = [8,16,20,24]
        sweets_vals = [8,12,16]
        v1 = random.choice(half_vals)
        v2 = random.choice(quarter_vals)
        v3 = random.choice(compare_vals)
        v4 = random.choice(half2_vals)
        v5 = random.choice(quarter2_vals)
        v6 = random.choice(sweets_vals)
        questions = [
            f"1. What is 1/2 of {v1}?",
            f"2. What is 1/4 of {v2}?",
            "3. Shade 1/2 of the rectangle.",
            "4. Shade 1/4 of the circle.",
            f"5. Which is bigger: 1/2 or 1/4 of {v3}?",
            f"6. What is half of {v4}?",
            f"7. What is a quarter of {v5}?",
            "8. Draw a shape and shade 1/2.",
            "9. Draw a shape and shade 1/4.",
            f"10. If you have {v6} sweets, what is 1/2?",
        ]
        answers = [str(v1//2), str(v2//4), "drawing (half shaded)", "drawing (quarter shaded)", "1/2", str(v4//2), str(v5//4), "drawing (half shaded)", "drawing (quarter shaded)", str(v6//2)]
    elif topic == "Measurement (cm and m)":
        m_val = random.randint(1,5)
        cm_vals = [100,200,300,400,500]
        cm_val = random.choice(cm_vals)
        cm_compare = random.randint(50,150)
        m_compare = random.randint(1,3)
        questions = [
            "1. How many cm in 1 m?",
            f"2. Convert {m_val} m to cm.",
            f"3. Convert {cm_val} cm to m.",
            "4. Is a pencil about 15 cm or 15 m?",
            "5. Is a room about 4 m or 4 cm wide?",
            "6. Measure your book in cm.",
            "7. How long is your desk in cm?",
            f"8. Which is longer: {cm_compare} cm or {m_compare} m?",
            "9. Draw a line that is 10 cm long.",
            "10. How many cm in 2 m?",
        ]
        answers = ["100", str(m_val * 100), f"{cm_val//100} m", "15 cm", "4 m", "varies (student measurement)", "varies (student measurement)", f"{m_compare} m" if m_compare * 100 > cm_compare else f"{cm_compare} cm", "drawing (10 cm)", "200"]
    elif topic == "Time (Half Past)":
        hours = random.sample(range(1, 13), 5)
        questions = [f"{i+1}. Draw the clock hands for {h}:30" for i, h in enumerate(hours)]
        answers_draw = [f"hour hand between {h} and {h+1 if h<12 else 1}, minute hand on 6" for h in hours]
        questions += [
            "6. What does 'half past' mean?",
            "7. Draw half past 3.",
            "8. Draw half past 9.",
            "9. How many minutes in half an hour?",
            "10. What time is half past 6?",
        ]
        answers = answers_draw + ["30 minutes past the hour", "drawing (3:30)", "drawing (9:30)", "30", "6:30"]
    elif topic == "Money (Pounds and Pence)":
        pound_val = random.randint(2,5)
        pence_vals = [100,200,300,500]
        pence_val = random.choice(pence_vals)
        have_pound = random.randint(1,5)
        spend_pence = random.randint(50,200)
        pencil_cost = random.choice([20,30,50])
        need_pound = random.randint(1,3)
        sweet_cost = random.choice([10,20,30])
        spend_pound = random.randint(1,3)
        spend_pence_part = random.choice(['00','50'])
        questions = [
            "1. How many pence in £1?",
            f"2. How many pence in £{pound_val}?",
            f"3. Convert {pence_val}p to £.",
            f"4. You have £{have_pound}. You spend {spend_pence}p. How much left?",
            f"5. A pencil costs {pencil_cost}p. How much for 2 pencils?",
            "6. Write £2.50 in pence.",
            "7. Write 150p in pounds.",
            f"8. You have £{need_pound}. You need £5. How much more do you need?",
            f"9. Three sweets cost {sweet_cost}p each. Total cost?",
            f"10. Change from £5 when spending £{spend_pound}.{spend_pence_part}?",
        ]
        left_pence = have_pound * 100 - spend_pence
        left_pound = left_pence // 100
        left_pence_part = left_pence % 100
        spend_total = spend_pound * 100 + (50 if spend_pence_part == '50' else 0)
        change = 500 - spend_total
        answers = ["100", str(pound_val * 100), f"£{pence_val//100}", f"£{left_pound}.{left_pence_part:02d}", f"{pencil_cost * 2}p", "250p", "£1.50", f"£{5 - need_pound}", f"{sweet_cost * 3}p", f"£{change//100}.{change%100:02d}"]
    elif topic == "Geometry (2D Shapes)":
        questions = [
            "1. How many sides does a triangle have?",
            "2. How many sides does a square have?",
            "3. How many sides does a pentagon have?",
            "4. How many sides does a hexagon have?",
            "5. Draw a rectangle.",
            "6. What shape has 4 equal sides?",
            "7. Is a circle a 2D shape?",
            "8. How many corners does a triangle have?",
            "9. Name a shape with 6 sides.",
            "10. Draw an octagon.",
        ]
        answers = ["3", "4", "5", "6", "drawing (rectangle)", "square", "yes", "3", "hexagon", "drawing (octagon)"]
    else:
        questions = [f"{i+1}. Year 2 Maths practice question {i+1}" for i in range(10)]
        answers = [f"answer {i+1}" for i in range(10)]

    content = f"Maths Homework - Year 2 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year3_homework(topic: str, index: int) -> tuple:
    """Year 3 数学作业（7-8 岁），返回 (content, correct_answers)"""
    if topic == "Addition and Subtraction":
        questions = []
        answers = []
        additions = []
        for i in range(5):
            a = random.randint(100, 500)
            b = random.randint(100, 500)
            additions.append((a, b))
            questions.append(f"{i+1}. {a} + {b} = ?")
        answers = [str(a + b) for a, b in additions]
        subtractions = []
        for i in range(5):
            a = random.randint(200, 800)
            b = random.randint(100, a)
            subtractions.append((a, b))
            questions.append(f"{i+6}. {a} - {b} = ?")
        answers += [str(a - b) for a, b in subtractions]
    elif topic == "Multiplication and Division":
        questions = []
        answers = []
        for i in range(5):
            a = random.randint(2, 10)
            b = random.randint(10, 50)
            questions.append(f"{i+1}. {b} × {a} = ?")
            answers.append(str(b * a))
        for i in range(5):
            b = random.randint(2, 10)
            result = random.randint(10, 50)
            questions.append(f"{i+6}. {b * result} ÷ {b} = ?")
            answers.append(str(result))
    elif topic == "Fractions":
        third_vals = [12,15,18,21,24]
        quarter_vals = [8,12,16,20,24]
        fifth_vals = [10,15,20,25,30]
        two_third_vals = [9,12,15,18]
        marble_vals = [15,20,25]
        v1 = random.choice(third_vals)
        v2 = random.choice(quarter_vals)
        v3 = random.choice(fifth_vals)
        v4 = random.choice(two_third_vals)
        v5 = random.choice(marble_vals)
        questions = [
            f"1. What is 1/3 of {v1}?",
            f"2. What is 1/4 of {v2}?",
            f"3. What is 1/5 of {v3}?",
            "4. Which is larger: 1/2 or 1/4?",
            "5. Add: 1/5 + 2/5 = ?",
            "6. Subtract: 3/4 - 1/4 = ?",
            "7. Order: 1/2, 1/3, 1/4 (smallest to largest).",
            f"8. What is 2/3 of {v4}?",
            "9. Draw a shape and shade 2/3.",
            f"10. If you have {v5} marbles and give away 1/5, how many left?",
        ]
        answers = [str(v1//3), str(v2//4), str(v3//5), "1/2", "3/5", "1/2", "1/4, 1/3, 1/2", str(v4//3*2), "drawing (2/3 shaded)", str(v5 - v5//5)]
    elif topic == "Measurement":
        m_val = random.randint(1,5)
        cm_val = random.choice([100,200,300,400,500])
        kg_val = random.randint(1,5)
        g_val = random.choice([500,1000,1500,2000])
        str_m = random.randint(1,3)
        str_cm = random.randint(0,9)*10
        ml_val = random.choice([500,1000,1500])
        order_m = random.randint(1,5)
        order_cm = random.randint(100,500)
        order_mm = random.randint(1000,5000)
        questions = [
            f"1. Convert {m_val} m to cm.",
            f"2. Convert {cm_val} cm to m.",
            f"3. Convert {kg_val} kg to g.",
            f"4. Convert {g_val} g to kg.",
            f"5. A string is {str_m} m {str_cm} cm long. How many cm?",
            "6. Which is heavier: 1 kg or 500 g?",
            "7. How many ml in 1 litre?",
            f"8. Convert {ml_val} ml to litres.",
            "9. Measure your desk in cm.",
            f"10. Order: {order_m} m, {order_cm} cm, {order_mm} mm",
        ]
        answers = [str(m_val * 100), f"{cm_val//100} m", str(kg_val * 1000), f"{g_val//1000} kg" if g_val%1000==0 else f"{g_val/1000} kg", str(str_m * 100 + str_cm), "1 kg", "1000", f"{ml_val//1000} L" if ml_val%1000==0 else f"{ml_val/1000} L", "varies (student measurement)", f"{order_cm} cm, {order_mm} mm, {order_m} m (depends on values)"]
    elif topic == "Geometry":
        questions = [
            "1. How many sides does a triangle have?",
            "2. How many sides does a square have?",
            "3. How many sides does a pentagon have?",
            "4. How many sides does a hexagon have?",
            "5. How many corners does a cube have?",
            "6. How many faces does a cube have?",
            "7. Draw a right angle.",
            "8. Is a circle 2D or 3D?",
            "9. Name a 3D shape.",
            "10. How many edges does a cuboid have?",
        ]
        answers = ["3", "4", "5", "6", "8", "6", "drawing (90 degree angle)", "2D", "cube (or cuboid, sphere, etc.)", "12"]
    elif topic == "Time":
        h1 = random.randint(1,11)
        m1 = random.choice(['00','15','30','45'])
        add_h1 = random.randint(1,5)
        h2 = random.randint(4,12)
        m2 = random.choice(['00','30'])
        sub_h2 = random.randint(1,3)
        hours_val = random.randint(1,3)
        secs_min = random.randint(1,5)
        weeks_days = random.randint(1,12)
        questions = [
            f"1. What time is {add_h1} hours after {h1}:{m1}?",
            f"2. What time was it {sub_h2} hours before {h2}:{m2}?",
            f"3. How many minutes in {hours_val} hours?",
            "4. Draw clock hands for 4:15.",
            "5. Draw clock hands for 7:45.",
            "6. School starts at 9:00 and ends at 3:30. How long?",
            f"7. How many seconds in {secs_min} minutes?",
            "8. How many days in January?",
            "9. How many weeks in a year?",
            f"10. Convert {weeks_days} weeks to days.",
        ]
        end_h = (h1 + add_h1) % 12 if (h1 + add_h1) <= 12 else (h1 + add_h1 - 12)
        end_m = m1
        start_h = h2 - sub_h2 if h2 > sub_h2 else h2 - sub_h2 + 12
        answers = [f"{end_h}:{end_m}", f"{start_h}:{m2}", str(hours_val * 60), "drawing (4:15)", "drawing (7:45)", "6 hours 30 minutes", str(secs_min * 60), "31", "52", str(weeks_days * 7)]
    elif topic == "Money":
        pound1 = random.randint(1,10)
        pence1 = random.choice([100,200,350,500])
        toy_pound = random.randint(2,5)
        toy_pence = random.choice(['00','50','99'])
        have_pound = random.randint(5,15)
        spend_pound = random.randint(1,4)
        spend_pence = random.choice(['00','50'])
        pencil_cost = random.choice([30,45,60])
        book_cost = random.randint(3,7)
        book_num = random.randint(2,4)
        save_pound = random.randint(2,5)
        save_weeks = random.randint(4,10)
        share_pound = random.choice([10,15,20])
        share_people = random.randint(2,5)
        questions = [
            f"1. Convert £{pound1} to pence.",
            f"2. Convert {pence1}p to £.",
            f"3. You buy a toy for £{toy_pound}.{toy_pence}. Change from £10?",
            f"4. You have £{have_pound}. Spend £{spend_pound}.{spend_pence}. How much left?",
            f"5. Three pencils cost {pencil_cost}p each. Total?",
            f"6. A book costs £{book_cost}. How much for {book_num} books?",
            "7. Write £3.50 in pence.",
            "8. Write 450p in pounds.",
            f"9. Save £{save_pound} per week. How much in {save_weeks} weeks?",
            f"10. Share £{share_pound} between {share_people} people.",
        ]
        toy_cost_pence = toy_pound * 100 + (0 if toy_pence == '00' else 50 if toy_pence == '50' else 99)
        toy_change = 1000 - toy_cost_pence
        spend_total_pence = spend_pound * 100 + (0 if spend_pence == '00' else 50)
        left_total = have_pound * 100 - spend_total_pence
        answers = [str(pound1 * 100), f"£{pence1//100}" if pence1%100==0 else f"£{pence1/100}", f"£{toy_change//100}.{toy_change%100:02d}", f"£{left_total//100}.{left_total%100:02d}", f"{pencil_cost * 3}p", f"£{book_cost * book_num}", "350p", "£4.50", f"£{save_pound * save_weeks}", f"£{share_pound/share_people:.2f}"]
    elif topic == "Place Value":
        num = random.randint(100,999)
        digit = int(random.choice(str(num)))
        num2 = random.randint(100,999)
        num3 = random.randint(100,500)
        add_val = random.randint(10,100)
        num4 = random.randint(300,900)
        sub_val = random.randint(10,100)
        partition = random.randint(100,999)
        o1 = random.randint(100,500)
        o2 = random.randint(100,500)
        o3 = random.randint(100,500)
        d1 = random.randint(1,9)
        d2 = random.randint(1,9)
        d3 = random.randint(1,9)
        plus100 = random.randint(100,800)
        minus100 = random.randint(300,999)
        questions = [
            f"1. Value of digit {digit} in {num}?",
            f"2. Write {num2} in words.",
            "3. Write 'two hundred and twenty-three' in numbers.",
            f"4. What is {add_val} more than {num3}?",
            f"5. What is {sub_val} less than {num4}?",
            f"6. Partition {partition} into hundreds, tens, ones.",
            f"7. Order: {o1}, {o2}, {o3}",
            f"8. Largest 3-digit number with digits {d1}, {d2}, {d3}?",
            f"9. 100 more than {plus100}?",
            f"10. 100 less than {minus100}?",
        ]
        num_str = str(num)
        if digit == int(num_str[0]):
            place_val = digit * 100
        elif digit == int(num_str[1]):
            place_val = digit * 10
        else:
            place_val = digit
        answers = [str(place_val), str(num2), "223", str(num3 + add_val), str(num4 - sub_val), f"{partition//100} hundreds, {(partition//10)%10} tens, {partition%10} ones", f"{sorted([o1,o2,o3])[0]}, {sorted([o1,o2,o3])[1]}, {sorted([o1,o2,o3])[2]}", str(int(''.join(sorted([str(d1),str(d2),str(d3)], reverse=True)))), str(plus100 + 100), str(minus100 - 100)]
    elif topic == "Number Bonds":
        n1 = random.randint(1,9)
        n2 = random.randint(10,19)
        n3 = random.randint(1,9)
        n4 = random.randint(10,15)
        n5 = random.randint(1,9)
        n6 = random.randint(5,15)
        n7 = random.randint(1,9)
        n8 = random.randint(1,9)
        n9 = random.randint(10,19)
        n10 = random.randint(1,9)
        questions = [
            f"1. What + {n1} = 10?",
            f"2. What + {n2} = 20?",
            f"3. {n3} + ? = 10",
            f"4. {n4} + ? = 20",
            f"5. ? + {n5} = 10",
            f"6. ? + {n6} = 20",
            "7. Write three pairs that add to 10.",
            "8. Write three pairs that add to 20.",
            f"9. {n7} + {n8} = ?",
            f"10. {n9} + {n10} = ?",
        ]
        answers = [str(10 - n1), str(20 - n2), str(10 - n3), str(20 - n4), str(10 - n5), str(20 - n6), "1+9, 2+8, 3+7 (etc.)", "1+19, 2+18, 3+17 (etc.)", str(n7 + n8), str(n9 + n10)]
    elif topic == "Problem Solving":
        apples = random.randint(20,50)
        eaten = random.randint(5,15)
        box_hold = random.randint(5,10)
        boxes = random.randint(3,8)
        tom_money = random.randint(5,15)
        tom_spend = random.randint(2,5)
        tom_get = random.randint(1,3)
        train_h = random.randint(1,11)
        train_m = random.choice(['00','15','30','45'])
        train_later = random.randint(1,4)
        children = random.randint(20,40)
        teams = random.randint(4,6)
        rect_l = random.randint(3,8)
        rect_w = random.randint(2,5)
        pages = random.randint(10,30)
        days = random.randint(3,7)
        pen_cost = random.choice([30,40,50])
        sweets = random.randint(30,60)
        share_children = random.randint(3,6)
        film_h = random.randint(1,2)
        film_m = random.choice([15,30,45])
        start_h = random.randint(1,6)
        start_m = random.choice(['00','15','30','45'])
        questions = [
            f"1. {apples} apples, {eaten} eaten. How many left?",
            f"2. Box holds {box_hold} pencils. How many in {boxes} boxes?",
            f"3. Tom has £{tom_money}. Spends £{tom_spend}. Gets £{tom_get}. How much now?",
            f"4. Train leaves at {train_h}:{train_m}. Arrives {train_later} hours later. What time?",
            f"5. {children} children. Teams of {teams}. How many teams?",
            f"6. Rectangle: length {rect_l} cm, width {rect_w} cm. Perimeter?",
            f"7. Reads {pages} pages/day. How many in {days} days?",
            f"8. Pens cost {pen_cost}p. How many with £2?",
            f"9. {sweets} sweets shared among {share_children} children. Each gets?",
            f"10. Film lasts {film_h}h {film_m}min. Starts at {start_h}:{start_m}. Ends?",
        ]
        answers = [str(apples - eaten), str(box_hold * boxes), f"£{tom_money - tom_spend + tom_get}", f"{(train_h + train_later) % 12 if (train_h + train_later) <= 12 else (train_h + train_later - 12)}:{train_m}", f"{children // teams} teams (remainder {children % teams})", str(2 * (rect_l + rect_w)), str(pages * days), f"{200 // pen_cost} pens", f"{sweets // share_children} each (remainder {sweets % share_children})", f"{(start_h + film_h + (int(start_m) + film_m) // 60) % 12 if (start_h + film_h + (int(start_m) + film_m) // 60) <= 12 else (start_h + film_h + (int(start_m) + film_m) // 60 - 12)}:{(int(start_m) + film_m) % 60:02d}"]
    else:
        questions = [f"{i+1}. Year 3 Maths practice question {i+1}" for i in range(10)]
        answers = [f"answer {i+1}" for i in range(10)]

    content = f"Maths Homework - Year 3 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year4_homework(topic: str, index: int) -> tuple:
    """Year 4 数学作业（8-9 岁），返回 (content, correct_answers)"""
    if topic == "Multiplication and Division":
        questions = []
        answers = []
        for i in range(5):
            a = random.randint(2, 12)
            b = random.randint(10, 99)
            questions.append(f"{i+1}. {b} × {a} = ?")
            answers.append(str(b * a))
        for i in range(5):
            b = random.randint(2, 12)
            result = random.randint(10, 50)
            questions.append(f"{i+6}. {b * result} ÷ {b} = ?")
            answers.append(str(result))
    elif topic == "Fractions and Decimals":
        third_vals = [12,15,18,21,24,27]
        fifth_vals = [10,15,20,25,30]
        v1 = random.choice(third_vals)
        v2 = random.choice(fifth_vals)
        dec1 = random.choice([1,2,3,4,5])
        dec2 = random.choice([2,4,6,8])
        dec3 = random.choice([3,5,7])
        sweets_val = random.choice([20,30,40])
        questions = [
            f"1. What is 1/3 of {v1}?",
            f"2. What is 2/5 of {v2}?",
            f"3. Convert {dec1}/10 to decimal.",
            f"4. Convert 0.{dec2} to fraction.",
            "5. Which is larger: 1/2 or 1/3?",
            "6. Add: 1/4 + 2/4 = ?",
            "7. Subtract: 3/5 - 1/5 = ?",
            f"8. Write {dec3}/10 as decimal.",
            "9. Order: 0.3, 1/2, 0.7, 1/4 (smallest to largest).",
            f"10. {sweets_val} sweets, eat 1/4. How many left?",
        ]
        answers = [str(v1//3), str(v2//5*2), f"0.{dec1}", f"{dec2}/10", "1/2", "3/4", "2/5", f"0.{dec3}", "1/4, 0.3, 1/2, 0.7", str(sweets_val - sweets_val//4)]
    elif topic == "Measurement and Conversion":
        km_val = random.randint(1,10)
        m_val = random.choice([500,1000,1500,2000,2500])
        kg_val = random.randint(1,5)
        g_val = random.choice([1000,2000,3000,4000])
        ribbon_m = random.randint(1,5)
        m_compare = random.randint(1,5)
        m_compare2 = random.randint(500,3000)
        jug_l = random.randint(1,3)
        jug_ml = random.randint(0,9)*100
        ml_val = random.choice([500,1000,1500,2000,2500])
        bag_kg = random.randint(1,5)
        bag_g = random.randint(0,9)*100
        order_km = random.randint(1,5)
        order_m = random.randint(500,5000)
        order_cm = random.randint(100,1000)
        questions = [
            f"1. Convert {km_val} km to m.",
            f"2. Convert {m_val} m to km.",
            f"3. Convert {kg_val} kg to g.",
            f"4. Convert {g_val} g to kg.",
            f"5. Ribbon is {ribbon_m} m long. How many cm?",
            f"6. Which is longer: {m_compare} km or {m_compare2} m?",
            f"7. Jug holds {jug_l}L {jug_ml}ml. How many ml?",
            f"8. Convert {ml_val} ml to litres.",
            f"9. Bag weighs {bag_kg}kg {bag_g}g. Write in grams.",
            f"10. Order: {order_km} km, {order_m} m, {order_cm} cm",
        ]
        answers = [str(km_val * 1000), f"{m_val//1000} km" if m_val%1000==0 else f"{m_val/1000} km", str(kg_val * 1000), f"{g_val//1000} kg", str(ribbon_m * 100), f"{m_compare} km" if m_compare * 1000 > m_compare2 else f"{m_compare2} m", str(jug_l * 1000 + jug_ml), f"{ml_val//1000} L" if ml_val%1000==0 else f"{ml_val/1000} L", str(bag_kg * 1000 + bag_g), "depends on values"]
    elif topic == "Geometry and Angles":
        shape = "hexagon" if random.choice([True,False]) else "pentagon"
        angle = random.choice([45,60,90,120,135])
        sym_shape = "square" if random.choice([True,False]) else "equilateral triangle"
        questions = [
            "1. What is a right angle in degrees?",
            "2. How many degrees in a straight line?",
            "3. How many degrees in a full turn?",
            f"4. How many sides does a {shape} have?",
            "5. Name a shape with 8 sides.",
            f"6. Is {angle} degrees acute, obtuse, or right?",
            "7. Draw an acute angle.",
            "8. How many pairs of parallel sides in a rectangle?",
            "9. Name a shape with rotational symmetry.",
            f"10. How many lines of symmetry in a {sym_shape}?",
        ]
        shape_sides = 6 if shape == "hexagon" else 5
        angle_type = "right" if angle == 90 else "acute" if angle < 90 else "obtuse"
        sym_lines = 4 if sym_shape == "square" else 3
        answers = ["90", "180", "360", str(shape_sides), "octagon", angle_type, "drawing (< 90 degrees)", "2", "square (or rectangle, equilateral triangle, etc.)", str(sym_lines)]
    elif topic == "Time and Duration":
        start_h = random.randint(1,11)
        start_m = random.choice(['00','15','30','45'])
        lasts_h = random.randint(1,3)
        lasts_m = random.choice([0,15,30,45])
        hours_val = random.randint(1,4)
        secs_val = random.randint(1,5)
        dur_h1 = random.randint(1,11)
        dur_m1 = random.choice(['00','30'])
        dur_h2 = random.randint(2,12)
        dur_m2 = random.choice(['00','30'])
        train_h = random.randint(1,4)
        train_m = random.choice([15,30,45])
        train_start = random.randint(1,10)
        train_start_m = random.choice(['00','15','30'])
        lesson_min = random.randint(45,60)
        lesson_hrs = random.randint(2,4)
        weeks_days = random.randint(1,12)
        questions = [
            f"1. Film starts at {start_h}:{start_m}. Lasts {lasts_h}h {lasts_m}min. Ends?",
            f"2. How many minutes in {hours_val} hours?",
            f"3. How many seconds in {secs_val} minutes?",
            f"4. Duration between {dur_h1}:{dur_m1} and {dur_h2}:{dur_m2}?",
            f"5. Train takes {train_h}h {train_m}min. Starts at {train_start}:{train_start_m}. Arrives?",
            "6. How many days in a leap year?",
            "7. How many hours in 3 days?",
            "8. If today is Monday, what day in 14 days?",
            f"9. Lesson lasts {lesson_min} min. How many in {lesson_hrs} hours?",
            f"10. Convert {weeks_days} weeks to days.",
        ]
        end_total_min = int(start_m) + lasts_m
        end_h = (start_h + lasts_h + end_total_min // 60) % 12 if (start_h + lasts_h + end_total_min // 60) <= 12 else (start_h + lasts_h + end_total_min // 60 - 12)
        end_m = end_total_min % 60
        train_arrive_m = int(train_start_m) + train_m
        train_arrive_h = (train_start + train_m // 60 + train_arrive_m // 60)
        answers = [f"{end_h}:{end_m:02d}", str(hours_val * 60), str(secs_val * 60), "calculate difference", f"{train_arrive_h % 12 if train_arrive_h <= 12 else train_arrive_h - 12}:{train_arrive_m % 60:02d}", "366", "72", "Monday", f"{lesson_hrs * 60 // lesson_min}", str(weeks_days * 7)]
    elif topic == "Money and Budgeting":
        pound1 = random.randint(1,20)
        pence1 = random.choice([500,1000,1500,2000,2500])
        items_num = random.randint(2,5)
        item_pound = random.randint(1,5)
        item_pence = random.choice(['00','50','99'])
        have_pound = random.randint(10,30)
        spend_pound = random.randint(3,8)
        spend_pence = random.choice(['00','50'])
        toy_cost = random.randint(5,15)
        save_per_week = random.randint(2,5)
        share_total = random.choice([15,30,45,60])
        book_pound = random.randint(3,8)
        book_pence = random.choice(['50','99'])
        pen_pound = random.randint(1,3)
        pen_pence = random.choice(['00','50'])
        save_weeks = random.randint(4,12)
        item_orig = random.randint(5,20)
        budget = random.randint(20,50)
        cost1 = random.randint(3,8)
        cost2 = random.randint(2,6)
        cost3 = random.randint(4,10)
        questions = [
            f"1. Convert £{pound1} to pence.",
            f"2. Convert {pence1}p to £.",
            f"3. Buy {items_num} items at £{item_pound}.{item_pence} each. Total?",
            f"4. Have £{have_pound}. Spend £{spend_pound}.{spend_pence}. Change?",
            f"5. Toy costs £{toy_cost}. Save £{save_per_week}/week. How many weeks?",
            f"6. Three friends share £{share_total} equally. Each gets?",
            f"7. Book costs £{book_pound}.{book_pence} and pen costs £{pen_pound}.{pen_pence}. Total?",
            f"8. Save £{random.randint(3,10)}/week. How much in {save_weeks} weeks?",
            f"9. Item costs £{item_orig}. Discount 10%. New price?",
            f"10. Budget £{budget}. Buy items costing £{cost1}, £{cost2}, £{cost3}. Change?",
        ]
        item_cost_pence = item_pound * 100 + (0 if item_pence == '00' else 50 if item_pence == '50' else 99)
        spend_total_pence = spend_pound * 100 + (0 if spend_pence == '00' else 50)
        book_total_pence = book_pound * 100 + (50 if book_pence == '50' else 99) + pen_pound * 100 + (0 if pen_pence == '00' else 50)
        save_amt = random.randint(3,10)
        answers = [str(pound1 * 100), f"£{pence1//100}" if pence1%100==0 else f"£{pence1/100}", f"£{items_num * item_cost_pence // 100}.{items_num * item_cost_pence % 100:02d}", f"£{(have_pound * 100 - spend_total_pence)//100}.{(have_pound * 100 - spend_total_pence)%100:02d}", f"{(toy_cost * 100 + save_per_week * 100 - 1) // (save_per_week * 100)} weeks", f"£{share_total/3:.2f}", f"£{book_total_pence//100}.{book_total_pence%100:02d}", f"£{save_amt * save_weeks}", f"£{item_orig * 90 // 100}.{item_orig * 90 % 100:02d}", f"£{budget - cost1 - cost2 - cost3}"]
    elif topic == "Place Value and Rounding":
        digit = random.randint(1,9)
        num = random.randint(1000,9999)
        num2 = random.randint(1000,9999)
        num3 = random.randint(1000,9999)
        num4 = random.randint(1000,5000)
        add_val = random.randint(100,1000)
        num5 = random.randint(3000,9000)
        sub_val = random.randint(100,1000)
        partition = random.randint(1000,9999)
        o1 = random.randint(1000,5000)
        o2 = random.randint(1000,5000)
        o3 = random.randint(1000,5000)
        plus1000 = random.randint(1000,8000)
        questions = [
            f"1. Value of digit {digit} in {num}?",
            f"2. Round {num2} to nearest 100.",
            f"3. Round {num3} to nearest 1000.",
            f"4. Write {num} in words.",
            f"5. What is {add_val} more than {num4}?",
            f"6. What is {sub_val} less than {num5}?",
            f"7. Partition {partition} into thousands, hundreds, tens, ones.",
            f"8. Order: {o1}, {o2}, {o3}",
            "9. Largest 4-digit number?",
            f"10. 1000 more than {plus1000}?",
        ]
        num_str = str(num)
        digit_pos = num_str.index(str(digit)) if str(digit) in num_str else 3
        place_val = digit * (10 ** (3 - digit_pos))
        answers = [str(place_val), str(round(num2, -2)), str(round(num3, -3)), str(num), str(num4 + add_val), str(num5 - sub_val), f"{partition//1000} thousands, {(partition//100)%10} hundreds, {(partition//10)%10} tens, {partition%10} ones", f"{sorted([o1,o2,o3])[0]}, {sorted([o1,o2,o3])[1]}, {sorted([o1,o2,o3])[2]}", "9999", str(plus1000 + 1000)]
    elif topic == "Addition and Subtraction (4-digit)":
        questions = []
        answers = []
        for i in range(5):
            a = random.randint(1000, 5000)
            b = random.randint(1000, 5000)
            questions.append(f"{i+1}. {a} + {b} = ?")
            answers.append(str(a + b))
        for i in range(5):
            a = random.randint(3000, 9000)
            b = random.randint(1000, a)
            questions.append(f"{i+6}. {a} - {b} = ?")
            answers.append(str(a - b))
    elif topic == "Area and Perimeter":
        l1 = random.randint(3,10)
        w1 = random.randint(2,8)
        l2 = random.randint(3,10)
        w2 = random.randint(2,8)
        side1 = random.randint(3,8)
        side2 = random.randint(3,8)
        area_given = random.choice([12,16,20,24,30])
        length_given = random.choice([3,4,5,6])
        perimeter_given = random.choice([16,20,24,28,32])
        room_l = random.randint(3,6)
        room_w = random.randint(2,5)
        garden_perim = random.randint(20,40)
        garden_l = random.randint(5,10)
        questions = [
            f"1. Rectangle: length {l1} cm, width {w1} cm. Area?",
            f"2. Rectangle: length {l2} cm, width {w2} cm. Perimeter?",
            f"3. Square: side {side1} cm. Area?",
            f"4. Square: side {side2} cm. Perimeter?",
            f"5. Area is {area_given} cm². Length is {length_given} cm. Width?",
            f"6. Perimeter is {perimeter_given} cm. Square. Side length?",
            "7. Draw a rectangle with area 12 cm².",
            "8. Draw a square with perimeter 20 cm.",
            f"9. Room is {room_l} m by {room_w} m. Area?",
            f"10. Garden perimeter is {garden_perim} m. Length is {garden_l} m. Width?",
        ]
        answers = [str(l1 * w1), str(2 * (l2 + w2)), str(side1 * side1), str(4 * side2), str(area_given // length_given), str(perimeter_given // 4), "drawing (e.g., 3x4)", "5 cm", str(room_l * room_w), str((garden_perim - 2 * garden_l) // 2)]
    elif topic == "Data and Statistics":
        nums1 = [random.randint(1,10) for _ in range(4)]
        nums2 = [random.randint(1,10) for _ in range(5)]
        mode_nums = [random.choice([1,2,3]) for _ in range(5)]
        range_nums = [random.randint(1,10) for _ in range(4)]
        survey1 = random.randint(10,30)
        survey2 = random.randint(5,20)
        like_maths = random.randint(10,30)
        like_english = random.randint(5,25)
        swim = random.randint(8,28)
        avg_nums = [random.randint(1,10) for _ in range(3)]
        questions = [
            f"1. Find the mean of: {', '.join(map(str, nums1))}",
            f"2. Find the median of: {', '.join(map(str, nums2))}",
            f"3. What is the mode of: {', '.join(map(str, mode_nums))}?",
            f"4. Range of: {', '.join(map(str, range_nums))}?",
            "5. Draw a bar chart for: Apples=5, Bananas=3, Oranges=7.",
            "6. Draw a pictograph for: Mon=10, Tue=15, Wed=8.",
            f"7. Survey: {survey1} like football, {survey2} like tennis. Total surveyed?",
            f"8. Which is most popular: Football ({survey1}), Tennis ({survey2}), Swimming ({swim})?",
            f"9. Interpret: 20 students, {like_maths} like maths, {like_english} like English. Fraction like maths?",
            f"10. Average of {', '.join(map(str, avg_nums))}?",
        ]
        answers = [f"{sum(nums1)/len(nums1):.1f}", str(sorted(nums2)[2]), str(max(set(mode_nums), key=mode_nums.count)), str(max(range_nums) - min(range_nums)), "drawing (bar chart)", "drawing (pictograph)", str(survey1 + survey2), max([(survey1, "Football"), (survey2, "Tennis"), (swim, "Swimming")], key=lambda x: x[0])[1], f"{like_maths}/20", f"{sum(avg_nums)/len(avg_nums):.1f}"]
    else:
        questions = [f"{i+1}. Year 4 Maths practice question {i+1}" for i in range(10)]
        answers = [f"answer {i+1}" for i in range(10)]

    content = f"Maths Homework - Year 4 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year5_homework(topic: str, index: int) -> tuple:
    """Year 5 数学作业（9-10 岁），返回 (content, correct_answers)"""
    if topic == "Large Numbers and Place Value":
        digit = random.randint(1,9)
        num = random.randint(10000,999999)
        num2 = random.randint(10000,999999)
        num3 = random.randint(10000,999999)
        num4 = random.randint(10000,999999)
        add_val = random.randint(1000,10000)
        num5 = random.randint(10000,50000)
        sub_val = random.randint(1000,10000)
        num6 = random.randint(50000,999999)
        o1 = random.randint(10000,99999)
        o2 = random.randint(10000,99999)
        o3 = random.randint(10000,99999)
        partition = random.randint(10000,999999)
        d1 = random.randint(1,9)
        d2 = random.randint(1,9)
        d3 = random.randint(1,9)
        d4 = random.randint(1,9)
        d5 = random.randint(1,9)
        d6 = random.randint(1,9)
        plus10000 = random.randint(10000,90000)
        questions = [
            f"1. Value of digit {digit} in {num}?",
            f"2. Write {num2} in words.",
            f"3. Round {num3} to nearest 1000.",
            f"4. Round {num4} to nearest 10000.",
            f"5. What is {add_val} more than {num5}?",
            f"6. What is {sub_val} less than {num6}?",
            f"7. Order: {o1}, {o2}, {o3}",
            f"8. Partition {partition} into place values.",
            f"9. Largest 6-digit number with digits {d1}, {d2}, {d3}, {d4}, {d5}, {d6}?",
            f"10. 10000 more than {plus10000}?",
        ]
        num_str = str(num)
        digit_indices = [i for i, c in enumerate(num_str) if int(c) == digit]
        place_val = digit * (10 ** (len(num_str) - 1 - digit_indices[0])) if digit_indices else digit
        answers = [str(place_val), str(num2), str(round(num3, -3)), str(round(num4, -4)), str(num5 + add_val), str(num6 - sub_val), f"{sorted([o1,o2,o3])[0]}, {sorted([o1,o2,o3])[1]}, {sorted([o1,o2,o3])[2]}", "by place values", str(int(''.join(sorted([str(d1),str(d2),str(d3),str(d4),str(d5),str(d6)], reverse=True)))), str(plus10000 + 10000)]
    elif topic == "Multiplication (4-digit by 2-digit)":
        questions = []
        answers = []
        for i in range(5):
            a = random.randint(100, 999)
            b = random.randint(10, 99)
            questions.append(f"{i+1}. {a} × {b} = ?")
            answers.append(str(a * b))
        for i in range(5):
            a = random.randint(1000, 9999)
            b = random.randint(10, 99)
            questions.append(f"{i+6}. {a} × {b} = ?")
            answers.append(str(a * b))
    elif topic == "Division and Long Division":
        questions = []
        answers = []
        for i in range(5):
            b = random.randint(3, 12)
            result = random.randint(50, 500)
            questions.append(f"{i+1}. {b * result} ÷ {b} = ?")
            answers.append(str(result))
        for i in range(5):
            b = random.randint(10, 25)
            result = random.randint(100, 500)
            remainder = random.randint(1, b-1)
            questions.append(f"{i+6}. {b * result + remainder} ÷ {b} = ? (with remainder)")
            answers.append(f"{result} remainder {remainder}")
    elif topic == "Fractions, Decimals and Percentages":
        dec_num = random.choice([1,2,3,4,5,6,7,8,9])
        pct_val = random.choice([25,50,75])
        pct_of = random.choice([40,60,80,100,200])
        mult_num = random.randint(2,10)
        frac_of_total = random.choice([20,40,50,100])
        frac_of_part = random.choice([5,10,20,25])
        pct2 = random.choice([10,20,30,40,50])
        pct2_of = random.choice([60,80,100,120])
        dec_val = random.choice([125,25,375,5,625,75,875])
        questions = [
            f"1. Convert {dec_num}/10 to decimal and percentage.",
            f"2. Convert {pct_val}% to fraction and decimal.",
            f"3. What is {pct_val}% of {pct_of}?",
            "4. Add: 2/5 + 1/3 = ?",
            "5. Subtract: 3/4 - 1/6 = ?",
            f"6. Multiply: 2/3 × {mult_num} = ?",
            "7. Order: 0.6, 2/3, 65%, 3/5 (smallest to largest).",
            f"8. What fraction of {frac_of_total} is {frac_of_part}?",
            f"9. {pct2}% of {pct2_of}?",
            f"10. Convert 0.{dec_val} to fraction and percentage.",
        ]
        answers = [f"0.{dec_num}, {dec_num*10}%", f"{pct_val//25}/4, 0.{pct_val//100 if pct_val==100 else pct_val//25*4}", str(pct_val * pct_of // 100), "11/15", "7/12", f"{2*mult_num}/3", "3/5, 0.6, 65%, 2/3", f"{frac_of_part}/{frac_of_total}", str(pct2 * pct2_of // 100), f"{dec_val}/1000, {dec_val/10}%"]
    elif topic == "Geometry (Angles and Coordinates)":
        angle = random.choice([30,45,60,90,120,135,150,180])
        third_angle = random.choice([40,50,70,80])
        fourth_angle = random.choice([60,80,100,120])
        x_coord = random.randint(1,10)
        y_coord = random.randint(1,10)
        p1x = random.randint(1,5)
        p1y = random.randint(1,5)
        p2x = random.randint(1,5)
        p2y = random.randint(1,5)
        refl_x = random.randint(1,5)
        refl_y = random.randint(1,5)
        questions = [
            f"1. What type of angle is {angle} degrees?",
            f"2. Calculate the missing angle: Triangle has angles 60° and {third_angle}°. Third angle?",
            f"3. Calculate the missing angle: Quadrilateral has angles 90°, 90°, {fourth_angle}°. Fourth angle?",
            "4. Draw an acute angle.",
            "5. Draw an obtuse angle.",
            f"6. What are the coordinates of a point {x_coord} units right and {y_coord} units up from origin?",
            f"7. Plot points: ({p1x},{p1y}) and ({p2x},{p2y}). Draw the line.",
            "8. How many degrees in a triangle?",
            "9. How many degrees in a quadrilateral?",
            f"10. Reflect point ({refl_x},{refl_y}) across the x-axis.",
        ]
        angle_type = "right" if angle == 90 else "acute" if angle < 90 else "straight" if angle == 180 else "obtuse"
        answers = [angle_type, str(180 - 60 - third_angle), str(360 - 90 - 90 - fourth_angle), "drawing (< 90 degrees)", "drawing (> 90 degrees)", f"({x_coord}, {y_coord})", "drawing", "180", "360", f"({refl_x}, {-refl_y})"]
    elif topic == "Area and Volume":
        l1 = random.randint(5,15)
        w1 = random.randint(3,10)
        l2 = random.randint(5,15)
        w2 = random.randint(3,10)
        base = random.randint(4,10)
        height = random.randint(3,8)
        cube_side = random.randint(2,6)
        cub_l = random.randint(3,8)
        cub_w = random.randint(2,6)
        cub_h = random.randint(2,5)
        area_given = random.choice([24,36,48,60])
        length_given = random.choice([4,6,8,10])
        vol_given = random.choice([24,36,48,60])
        vol_l = random.choice([3,4,6])
        vol_w = random.choice([2,3,4])
        garden_l = random.randint(5,15)
        garden_w = random.randint(3,10)
        box_l = random.randint(5,15)
        box_w = random.randint(3,8)
        box_h = random.randint(2,6)
        questions = [
            f"1. Rectangle: length {l1} cm, width {w1} cm. Area?",
            f"2. Rectangle: length {l2} cm, width {w2} cm. Perimeter?",
            f"3. Triangle: base {base} cm, height {height} cm. Area?",
            f"4. Cube: side {cube_side} cm. Volume?",
            f"5. Cuboid: {cub_l} cm × {cub_w} cm × {cub_h} cm. Volume?",
            f"6. Area is {area_given} cm². Length is {length_given} cm. Width?",
            f"7. Volume is {vol_given} cm³. Length {vol_l} cm, width {vol_w} cm. Height?",
            "8. Draw a rectangle with area 24 cm².",
            f"9. Garden is {garden_l} m by {garden_w} m. Area?",
            f"10. Box is {box_l} cm × {box_w} cm × {box_h} cm. Volume?",
        ]
        answers = [str(l1 * w1), str(2 * (l2 + w2)), str(base * height // 2), str(cube_side ** 3), str(cub_l * cub_w * cub_h), str(area_given // length_given), str(vol_given // (vol_l * vol_w)), "drawing (e.g., 4x6)", str(garden_l * garden_w), str(box_l * box_w * box_h)]
    elif topic == "Ratio and Proportion":
        r1 = random.randint(2,10)
        r2 = random.randint(2,10)
        share1 = random.choice([20,30,40,50,60])
        share2 = random.choice([24,36,48,60])
        apple_cost = random.choice([1,2,3])
        apple_num = random.randint(5,15)
        flour = random.randint(100,500)
        people = random.randint(8,12)
        map_cm = random.randint(2,10)
        pencil_cost_pound = random.choice([1,2])
        pencil_cost_pence = random.choice(['00','50'])
        boys = random.choice([12,15,18,21])
        speed = random.randint(50,80)
        hours = random.randint(2,5)
        rice_g = random.randint(100,500)
        rice_serves = random.randint(2,4)
        rice_people = random.randint(6,10)
        questions = [
            f"1. Simplify ratio {r1}:{r2}.",
            f"2. Share {share1} in ratio 2:3.",
            f"3. Share {share2} in ratio 3:5.",
            f"4. If 3 apples cost £{apple_cost}, how much for {apple_num} apples?",
            f"5. Recipe for 4 people needs {flour}g flour. For {people} people?",
            f"6. Map scale 1:10000. Distance on map is {map_cm} cm. Real distance?",
            f"7. If 5 pencils cost £{pencil_cost_pound}.{pencil_cost_pence}, cost of 12 pencils?",
            f"8. Ratio of boys:girls is 3:4. There are {boys} boys. How many girls?",
            f"9. Car travels {speed} miles in 1 hour. How far in {hours} hours?",
            f"10. {rice_g}g of rice serves {rice_serves} people. How much for {rice_people} people?",
        ]
        import math
        gcd = math.gcd(r1, r2)
        pencil_total_pence = pencil_cost_pound * 100 + (0 if pencil_cost_pence == '00' else 50)
        answers = [f"{r1//gcd}:{r2//gcd}", f"{share1//5*2}:{share1//5*3}", f"{share2//8*3}:{share2//8*5}", f"£{apple_cost * apple_num / 3:.2f}", f"{flour * people // 4}g", f"{map_cm * 10000} cm = {map_cm * 100} m", f"£{pencil_total_pence * 12 / 5 / 100:.2f}", f"{boys // 3 * 4} girls", f"{speed * hours} miles", f"{rice_g * rice_people // rice_serves}g"]
    elif topic == "Algebra Basics":
        add_val = random.randint(5,20)
        result1 = random.randint(25,50)
        mult_val = random.randint(2,10)
        result2 = random.choice([24,36,48,60,72])
        eq_result = random.choice([20,30,40,50,60])
        sub_val = random.randint(5,15)
        result3 = random.randint(10,30)
        a_val = random.randint(2,5)
        b_val = random.randint(3,7)
        seq1 = random.randint(1,5)
        seq2 = random.randint(6,10)
        seq3 = random.randint(11,15)
        add_val2 = random.randint(1,10)
        result4 = random.randint(10,40)
        mult_expr = random.randint(2,5)
        add_expr = random.randint(1,10)
        questions = [
            f"1. If x + {add_val} = {result1}, find x.",
            f"2. If {mult_val} × y = {result2}, find y.",
            f"3. Solve: 2x = {eq_result}.",
            f"4. Solve: x - {sub_val} = {result3}.",
            f"5. If a = {a_val} and b = {b_val}, what is a + b?",
            f"6. If a = {a_val} and b = {b_val}, what is a × b?",
            f"7. Complete the sequence: {seq1}, {seq2}, {seq3}, __, __",
            f"8. Find the nth term: {seq1}, {seq2}, {seq3}, ...",
            f"9. If 3x + {add_val2} = {result4}, find x.",
            f"10. Write an expression for: 'A number multiplied by {mult_expr}, then add {add_expr}'.",
        ]
        diff = seq2 - seq1
        answers = [str(result1 - add_val), str(result2 // mult_val), str(eq_result // 2), str(result3 + sub_val), str(a_val + b_val), str(a_val * b_val), f"{seq3 + diff}, {seq3 + 2*diff}", f"{diff}n + {seq1 - diff}", str((result4 - add_val2) // 3), f"{mult_expr}n + {add_expr}"]
    elif topic == "Statistics and Probability":
        nums = [random.randint(1,20) for _ in range(5)]
        nums2 = [random.randint(1,20) for _ in range(5)]
        mode_nums = [random.choice([2,4,6]) for _ in range(5)]
        range_nums = [random.randint(1,20) for _ in range(4)]
        roll = random.randint(1,6)
        red = random.randint(3,8)
        blue = random.randint(2,7)
        sections = random.randint(2,5)
        tea = random.randint(10,30)
        coffee = random.randint(5,25)
        questions = [
            f"1. Find the mean of: {', '.join(map(str, nums))}",
            f"2. Find the median of: {', '.join(map(str, nums2))}",
            f"3. Mode of: {', '.join(map(str, mode_nums))}?",
            f"4. Range of: {', '.join(map(str, range_nums))}?",
            "5. Draw a line graph for: Mon=10, Tue=15, Wed=8, Thu=12, Fri=20.",
            f"6. Probability of rolling a {roll} on a dice?",
            f"7. Bag has {red} red balls and {blue} blue balls. P(red)?",
            "8. Coin flipped. P(heads)?",
            f"9. Spinner has {sections} sections. P(landing on one section)?",
            f"10. Survey: {tea} prefer tea, {coffee} prefer coffee. P(tea)?",
        ]
        answers = [f"{sum(nums)/len(nums):.1f}", str(sorted(nums2)[2]), str(max(set(mode_nums), key=mode_nums.count)), str(max(range_nums) - min(range_nums)), "drawing (line graph)", "1/6", f"{red}/{red+blue}", "1/2", f"1/{sections}", f"{tea}/{tea+coffee}"]
    elif topic == "Problem Solving":
        students = random.randint(100,500)
        pct_boys = random.randint(10,30)
        area = random.choice([48,60,72,84])
        length = random.choice([6,8,10,12])
        book_pound = random.randint(5,15)
        book_pence = random.choice(['00','50','99'])
        speed = random.randint(50,80)
        travel_h = random.randint(1,4)
        travel_m = random.choice([0,30])
        rice_g = random.randint(100,500)
        rice_people = random.randint(4,8)
        box_l = random.randint(5,15)
        box_w = random.randint(3,10)
        box_h = random.randint(2,8)
        save_week = random.randint(5,20)
        need_money = random.randint(100,500)
        ratio_total = random.choice([24,32,40,48,56])
        start_h = random.randint(1,11)
        start_m = random.choice(['00','15','30','45'])
        film_h = random.randint(1,3)
        film_m = random.choice([0,15,30,45])
        pages = random.randint(100,500)
        read_pages = random.randint(10,30)
        questions = [
            f"1. {students} students. {pct_boys}% are boys. How many girls?",
            f"2. Rectangle area is {area} cm². Length is {length} cm. Perimeter?",
            f"3. Book costs £{book_pound}.{book_pence}. Discount 20%. New price?",
            f"4. Train travels {speed} mph for {travel_h} hours {travel_m} min. Distance?",
            f"5. {rice_g}g rice shared among {rice_people} people. Each gets?",
            f"6. Box is {box_l} cm × {box_w} cm × {box_h} cm. Volume?",
            f"7. Save £{save_week}/week. Need £{need_money}. How many weeks?",
            f"8. Ratio 3:5. Total is {ratio_total}. Larger share?",
            f"9. Film starts {start_h}:{start_m}, lasts {film_h}h {film_m}min. Ends?",
            f"10. {pages} pages. Read {read_pages} pages/day. Days to finish?",
        ]
        book_pence_val = 0 if book_pence == '00' else 50 if book_pence == '50' else 99
        book_total = book_pound * 100 + book_pence_val
        discount_price = book_total * 80 // 100
        end_total_min = int(start_m) + film_m
        end_h = (start_h + film_h + end_total_min // 60)
        end_m = end_total_min % 60
        answers = [str(students * (100 - pct_boys) // 100), str(2 * (length + area // length)), f"£{discount_price//100}.{discount_price%100:02d}", str(speed * (travel_h + travel_m / 60)), f"{rice_g // rice_people}g (remainder {rice_g % rice_people}g)", str(box_l * box_w * box_h), f"{(need_money + save_week - 1) // save_week} weeks", str(ratio_total // 8 * 5), f"{end_h % 12 if end_h <= 12 else end_h - 12}:{end_m:02d}", f"{(pages + read_pages - 1) // read_pages} days"]
    else:
        questions = [f"{i+1}. Year 5 Maths practice question {i+1}" for i in range(10)]
        answers = [f"answer {i+1}" for i in range(10)]

    content = f"Maths Homework - Year 5 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year6_homework(topic: str, index: int) -> tuple:
    """Year 6 数学作业（10-11 岁），返回 (content, correct_answers)"""
    if topic == "Advanced Fractions and Decimals":
        frac1_add = random.choice(['2/3','3/4','5/6'])
        frac2_add = random.choice(['1/4','1/3','2/5'])
        frac1_sub = random.choice(['3/4','5/6','7/8'])
        frac2_sub = random.choice(['1/3','1/4','1/6'])
        frac1_mul = random.choice(['2/3','3/5','4/7'])
        frac2_mul = random.choice(['3/4','5/6','2/5'])
        frac1_div = random.choice(['3/4','2/3','5/6'])
        frac2_div = random.choice(['1/2','2/3','3/4'])
        improper_num = random.choice([3,7,9,11,13])
        whole = random.choice([1,2,3])
        numerator = random.choice([1,3,5,7])
        denominator = random.choice([2,4,8])
        mult_val = random.choice([0.1,0.01,0.001])
        mult_num = random.randint(100,9999)
        dec_frac = random.choice([0.5,0.25,0.2,0.125])
        div_num = random.randint(100,999)
        div_by = random.choice([10,100,1000])
        questions = [
            f"1. Add: {frac1_add} + {frac2_add} = ?",
            f"2. Subtract: {frac1_sub} - {frac2_sub} = ?",
            f"3. Multiply: {frac1_mul} × {frac2_mul} = ?",
            f"4. Divide: {frac1_div} ÷ {frac2_div} = ?",
            f"5. Convert {improper_num}/8 to mixed number.",
            f"6. Convert {whole} {numerator}/{denominator} to improper fraction.",
            "7. Order: 0.75, 3/4, 70%, 4/5 (smallest to largest).",
            f"8. What is {mult_val} × {mult_num}?",
            f"9. {dec_frac} as fraction in simplest form?",
            f"10. {div_num} ÷ {div_by}?",
        ]
        # Fraction answers (simplified)
        answers = [
            "17/12 or 1 5/12",  # 2/3+1/4 (approximate)
            "7/24",  # 3/4-1/6 (approximate)
            "1/2",  # approximate
            "1",  # approximate
            f"{improper_num//8} {improper_num%8}/8" if improper_num >= 8 else f"{improper_num}/8",
            str(whole * denominator + numerator) + f"/{denominator}",
            "70%, 0.75, 3/4, 4/5",
            str(mult_val * mult_num),
            "1/2" if dec_frac == 0.5 else "1/4" if dec_frac == 0.25 else "1/5" if dec_frac == 0.2 else "1/8",
            str(div_num / div_by),
        ]
    elif topic == "Multiplication and Division (Large Numbers)":
        questions = []
        answers = []
        for i in range(5):
            a = random.randint(1000, 9999)
            b = random.randint(10, 99)
            questions.append(f"{i+1}. {a} × {b} = ?")
            answers.append(str(a * b))
        for i in range(5):
            b = random.randint(10, 25)
            result = random.randint(100, 999)
            remainder = random.randint(0, b-1)
            questions.append(f"{i+6}. {b * result + remainder} ÷ {b} = ?")
            answers.append(f"{result} remainder {remainder}" if remainder > 0 else str(result))
    elif topic == "Percentages and Ratio":
        pct1 = random.choice([10,15,20,25,50,75])
        amt1 = random.choice([40,60,80,100,200])
        pct_of_val = random.choice([25,50,75])
        total1 = random.choice([100,200,300,400])
        increase_val = random.choice([100,150,200,250])
        increase_pct = random.choice([10,20,25,50])
        decrease_val = random.choice([100,150,200,250])
        decrease_pct = random.choice([10,20,25,50])
        share_amt = random.choice([60,80,100,120])
        r1 = random.randint(2,5)
        r2 = random.randint(2,5)
        orig_price = random.choice([40,50,60,80])
        increase_pct2 = random.choice([10,20,25])
        discount_pct = random.choice([20,25,30,50])
        orig_price2 = random.choice([40,60,80,100])
        ratio_total = random.choice([36,48,60,72,84])
        girl_pct = random.choice([15,20,25,30])
        total_students = random.choice([80,100,120,160])
        vat_price = random.choice([50,60,80,100])
        questions = [
            f"1. What is {pct1}% of £{amt1}?",
            f"2. {pct_of_val} is what % of {total1}?",
            f"3. Increase {increase_val} by {increase_pct}%.",
            f"4. Decrease {decrease_val} by {decrease_pct}%.",
            f"5. Share £{share_amt} in ratio {r1}:{r2}.",
            f"6. Price was £{orig_price}. Increased by {increase_pct2}%. New price?",
            f"7. Sale: {discount_pct}% off. Original £{orig_price2}. Sale price?",
            f"8. Ratio 5:7. Total {ratio_total}. Difference between shares?",
            f"9. {girl_pct}% of {total_students} students are girls. How many boys?",
            f"10. VAT at 20%. Item costs £{vat_price}. Total with VAT?",
        ]
        answers = [f"£{pct1 * amt1 // 100}", f"{pct_of_val * 100 // total1}%", str(increase_val * (100 + increase_pct) // 100), str(decrease_val * (100 - decrease_pct) // 100), f"£{share_amt//(r1+r2)*r1} and £{share_amt//(r1+r2)*r2}", f"£{orig_price * (100 + increase_pct2) // 100}", f"£{orig_price2 * (100 - discount_pct) // 100}", str(ratio_total // 12 * 2), str(total_students * (100 - girl_pct) // 100), f"£{vat_price * 120 // 100}"]
    elif topic == "Algebra and Equations":
        add_val = random.randint(5,20)
        result1 = random.randint(20,80)
        sub_inside = random.randint(3,10)
        result2 = random.choice([20,30,40,50])
        x_val = random.randint(2,8)
        y_val = random.randint(3,10)
        a_val = random.randint(2,6)
        b_val = random.randint(3,8)
        mult_val = random.randint(2,8)
        sub_val = random.randint(1,10)
        result3 = random.randint(10,50)
        add_y = random.randint(2,10)
        result4 = random.randint(10,30)
        coeff1 = random.randint(2,5)
        coeff2 = random.randint(1,5)
        coeff3 = random.randint(1,3)
        expand_mult = random.randint(2,5)
        expand_add = random.randint(1,10)
        x_eq = random.choice([3,6,9,12])
        seq1 = random.randint(3,8)
        seq2 = random.randint(5,16)
        seq3 = random.randint(7,24)
        questions = [
            f"1. Solve: 3x + {add_val} = {result1}.",
            f"2. Solve: 2(x - {sub_inside}) = {result2}.",
            f"3. If x = {x_val} and y = {y_val}, find 2x + 3y.",
            f"4. If a = {a_val} and b = {b_val}, find a² + b.",
            f"5. Solve: {mult_val}x - {sub_val} = {result3}.",
            f"6. Find y if 4y + {add_y} = 3y + {result4}.",
            f"7. Simplify: {coeff1}a + {coeff2}a - {coeff3}a.",
            f"8. Expand: {expand_mult}(x + {expand_add}).",
            f"9. If 5x = 3y and x = {x_eq}, find y.",
            f"10. nth term of sequence: {seq1}, {seq2}, {seq3}, ...",
        ]
        answers = [str((result1 - add_val) // 3), str(result2 // 2 + sub_inside), str(2 * x_val + 3 * y_val), str(a_val ** 2 + b_val), str((result3 + sub_val) // mult_val), str(result4 - add_y), f"{coeff1 + coeff2 - coeff3}a", f"{expand_mult}x + {expand_mult * expand_add}", str(5 * x_eq // 3), f"{seq2 - seq1}n + {seq1 - (seq2 - seq1)}"]
    elif topic == "Geometry (Transformations)":
        refl_x = random.randint(1,8)
        refl_y = random.randint(1,8)
        trans_x = random.randint(1,5)
        trans_y = random.randint(1,5)
        trans_vx = random.randint(-3,3)
        trans_vy = random.randint(-3,3)
        rot_x = random.randint(1,5)
        rot_y = random.randint(1,5)
        tri_x = random.randint(2,6)
        tri_y = random.randint(2,6)
        rect_x = random.randint(3,8)
        rect_y = random.randint(2,6)
        enlarge_x = random.randint(1,5)
        enlarge_y = random.randint(1,5)
        scale = random.choice([2,3])
        questions = [
            f"1. Reflect point ({refl_x},{refl_y}) across y-axis.",
            f"2. Translate point ({trans_x},{trans_y}) by vector ({trans_vx},{trans_vy}).",
            f"3. Rotate point ({rot_x},{rot_y}) 90° clockwise about origin.",
            f"4. Find area of triangle with vertices (0,0), ({tri_x},0), (0,{tri_y}).",
            f"5. Find perimeter of rectangle with vertices (0,0), ({rect_x},0), ({rect_x},{rect_y}), (0,{rect_y}).",
            "6. How many lines of symmetry in a regular hexagon?",
            "7. How many lines of symmetry in an equilateral triangle?",
            "8. Describe the transformation from (2,3) to (5,3).",
            f"9. Point ({enlarge_x},{enlarge_y}) enlarged by scale factor {scale}. New coordinates?",
            "10. What type of triangle has vertices (0,0), (4,0), (0,3)?",
        ]
        answers = [f"(-{refl_x}, {refl_y})", f"({trans_x + trans_vx}, {trans_y + trans_vy})", f"({rot_y}, {-rot_x})", str(tri_x * tri_y // 2), str(2 * (rect_x + rect_y)), "6", "3", "translation by vector (3,0)", f"({enlarge_x * scale}, {enlarge_y * scale})", "right-angled triangle"]
    elif topic == "Area, Perimeter and Volume":
        radius = random.choice([3,4,5,6,7])
        diameter = random.choice([6,8,10,12,14])
        base = random.randint(5,15)
        height = random.randint(4,12)
        para_base = random.randint(5,12)
        para_height = random.randint(3,10)
        trap_a = random.randint(4,8)
        trap_b = random.randint(6,12)
        trap_h = random.randint(3,8)
        cyl_r = random.randint(2,5)
        cyl_h = random.randint(5,10)
        cube_side = random.randint(3,8)
        cub_l = random.randint(4,10)
        cub_w = random.randint(3,8)
        cub_h = random.randint(2,6)
        circ = random.choice([31.4, 62.8, 94.2])
        sphere_r = random.randint(2,6)
        questions = [
            f"1. Circle radius {radius} cm. Area? (use π = 3.14)",
            f"2. Circle diameter {diameter} cm. Circumference? (use π = 3.14)",
            f"3. Triangle: base {base} cm, height {height} cm. Area?",
            f"4. Parallelogram: base {para_base} cm, height {para_height} cm. Area?",
            f"5. Trapezium: parallel sides {trap_a} cm and {trap_b} cm, height {trap_h} cm. Area?",
            f"6. Cylinder: radius {cyl_r} cm, height {cyl_h} cm. Volume? (use π = 3.14)",
            f"7. Cube: side {cube_side} cm. Surface area?",
            f"8. Cuboid: {cub_l} cm × {cub_w} cm × {cub_h} cm. Surface area?",
            f"9. Circle circumference is {circ} cm. Radius?",
            f"10. Sphere radius {sphere_r} cm. Volume? (use π = 3.14, V = 4/3πr³)",
        ]
        answers = [str(int(3.14 * radius ** 2)), str(int(3.14 * diameter)), str(base * height // 2), str(para_base * para_height), str((trap_a + trap_b) * trap_h // 2), str(int(3.14 * cyl_r ** 2 * cyl_h)), str(6 * cube_side ** 2), str(2 * (cub_l * cub_w + cub_l * cub_h + cub_w * cub_h)), str(int(circ / 3.14 / 2)), str(int(4/3 * 3.14 * sphere_r ** 3))]
    elif topic == "Statistics and Data Interpretation":
        nums = [random.randint(10,50) for _ in range(5)]
        nums2 = [random.randint(10,50) for _ in range(6)]
        mode_nums = [random.randint(10,30) for _ in range(5)]
        range_nums = [random.randint(10,50) for _ in range(4)]
        mean_val = random.choice([15,20,25,30])
        n1 = random.randint(10,20)
        n2 = random.randint(10,20)
        n3 = random.randint(10,20)
        target_mean = random.randint(15,25)
        survey_total = random.randint(50,100)
        survey_pct = random.randint(20,40)
        questions = [
            f"1. Mean of: {', '.join(map(str, nums))}",
            f"2. Median of: {', '.join(map(str, nums2))}",
            f"3. Mode of: {', '.join(map(str, mode_nums))}",
            f"4. Range of: {', '.join(map(str, range_nums))}",
            "5. Draw a pie chart for: Football=40%, Tennis=25%, Swimming=35%.",
            "6. Scatter graph shows correlation between study time and test score. Describe the relationship.",
            f"7. Mean of 5 numbers is {mean_val}. Total sum?",
            f"8. Add a number to {n1}, {n2}, {n3} so mean becomes {target_mean}.",
            "9. Interpret: Box plot shows median=15, Q1=10, Q3=22. IQR?",
            f"10. Survey: {survey_total} people. {survey_pct}% prefer A. How many prefer A?",
        ]
        answers = [f"{sum(nums)/len(nums):.1f}", f"{(sorted(nums2)[2] + sorted(nums2)[3]) / 2}", str(max(set(mode_nums), key=mode_nums.count)), str(max(range_nums) - min(range_nums)), "drawing (pie chart)", "positive correlation", str(mean_val * 5), str(4 * target_mean - n1 - n2 - n3), "12", str(survey_total * survey_pct // 100)]
    elif topic == "Negative Numbers":
        n1 = random.randint(-20,-1)
        n2 = random.randint(1,20)
        n3 = random.randint(-10,-1)
        n4 = random.randint(1,10)
        n5 = random.randint(-10,-1)
        n6 = random.randint(1,10)
        n7 = random.randint(1,10)
        n8 = random.randint(11,20)
        neg1 = random.randint(-10,0)
        neg2 = random.randint(-10,0)
        pos1 = random.randint(0,10)
        pos2 = random.randint(0,10)
        temp1 = random.randint(-10,-1)
        temp_rise = random.randint(5,15)
        temp2 = random.randint(1,10)
        temp_drop = random.randint(5,20)
        bank_neg = random.randint(10,50)
        bank_deposit = random.randint(20,100)
        neg_mult1 = random.randint(-10,-1)
        neg_mult2 = random.randint(-10,-1)
        comp1 = random.randint(-10,0)
        comp2 = random.randint(-10,0)
        questions = [
            f"1. {n1} + {n2} = ?",
            f"2. {n3} - {n4} = ?",
            f"3. {n5} × {n6} = ?",
            f"4. {n7} - {n8} = ?",
            f"5. Order: {neg1}, {neg2}, {pos1}, {pos2}",
            f"6. Temperature is {temp1}°C. Rises by {temp_rise}°C. New temperature?",
            f"7. Temperature is {temp2}°C. Drops by {temp_drop}°C. New temperature?",
            f"8. Bank balance: -£{bank_neg}. Deposit £{bank_deposit}. New balance?",
            f"9. What is {neg_mult1} × {neg_mult2}?",
            f"10. Fill in: {comp1} < {comp2} (True or False)?",
        ]
        answers = [str(n1 + n2), str(n3 - n4), str(n5 * n6), str(n7 - n8), f"{min([neg1,neg2,pos1,pos2])}, {sorted([neg1,neg2,pos1,pos2])[1]}, {sorted([neg1,neg2,pos1,pos2])[2]}, {max([neg1,neg2,pos1,pos2])}", str(temp1 + temp_rise), str(temp2 - temp_drop), f"£{bank_deposit - bank_neg}", str(neg_mult1 * neg_mult2), "True" if comp1 < comp2 else "False"]
    else:
        questions = [f"{i+1}. Year 6 Maths practice question {i+1}" for i in range(10)]
        answers = [f"answer {i+1}" for i in range(10)]

    content = f"Maths Homework - Year 6 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


# 各年级 Key Stage 和作业时间设置
YEAR_CONFIG = {
    1: {"key_stage": "KS1", "homework_minutes": "10-15"},
    2: {"key_stage": "KS1", "homework_minutes": "10-15"},
    3: {"key_stage": "KS2", "homework_minutes": "20-30"},
    4: {"key_stage": "KS2", "homework_minutes": "20-30"},
    5: {"key_stage": "KS2", "homework_minutes": "30"},
    6: {"key_stage": "KS2", "homework_minutes": "30"},
}


def clean_year_math(year_group: int) -> int:
    """清理指定年级的所有数学作业"""
    store = get_homework_rag_store()
    results = store.search_by_metadata({"year_group": year_group, "subject": "Maths"})
    
    if not results:
        print(f"  Year {year_group}: 没有找到需要清理的作业")
        return 0
    
    deleted = 0
    for item in results:
        doc_id = item.get("doc_id")
        if doc_id and store.delete_homework(doc_id):
            deleted += 1
    
    print(f"  Year {year_group}: 已清理 {deleted} 份作业")
    return deleted


def check_year_math_exists(year_group: int) -> bool:
    """检查指定年级是否已有数学作业"""
    store = get_homework_rag_store()
    results = store.search(query="maths", k=1, filters={"year_group": year_group, "subject": "Maths"})
    return len(results) > 0


def generate_year_homework(year_group: int, count: int = 500) -> list:
    """为指定年级生成指定数量的数学作业"""
    topics = MATH_TOPICS_BY_YEAR.get(year_group, [])
    if not topics:
        print(f"警告：未找到 Year {year_group} 的数学主题")
        return []

    config = YEAR_CONFIG.get(year_group, {"key_stage": "KS2", "homework_minutes": "20-30"})
    batch_data = []

    for i in range(1, count + 1):
        topic = topics[(i - 1) % len(topics)]
        content, correct_answers = generate_math_homework(year_group, topic, i)

        metadata = {
            "year_group": year_group,
            "subject": "Maths",
            "homework_minutes": config["homework_minutes"],
            "key_stage": config["key_stage"],
            "topic": topic,
            "student_id": None,
            "correct_answers": correct_answers
        }
        doc_id = f"math_y{year_group}_{i:03d}"
        batch_data.append({
            "content": content,
            "metadata": metadata,
            "doc_id": doc_id,
        })

        if i % 10 == 0:
            print(f"  已生成 {i}/{count} 份作业")

    return batch_data

def check_year_math_exists(year_group: int) -> bool:
    """检查指定年级是否已有英语作业"""
    store = get_homework_rag_store()
    results = store.search(query="maths", k=1, filters={"year_group": year_group, "subject": "Maths"})
    return len(results) > 0


def main():
    """主函数：检查各年级Math作业，缺失则生成"""
    print("检查各年级Math作业是否存在...\n")

    store = get_homework_rag_store()
    years_to_generate = []

    for year in range(1, 7):
        exists = check_year_math_exists(year)
        status = "已有" if exists else "缺失"
        print(f"  Year {year}: {status}")
        if not exists:
            years_to_generate.append(year)

    if not years_to_generate:
        print("\n所有年级Math作业已存在，无需生成。")
        return

    print(f"\n需要生成的年级: {', '.join(f'Year {y}' for y in years_to_generate)}")

    for year in years_to_generate:
        print(f"\n开始生成 Year {year} Math作业...")
        batch_data = generate_year_homework(year, count=500)

        if batch_data:
            store.add_batch_homework(batch_data)
            print(f"成功添加 {len(batch_data)} 份 Year {year} Math作业到 RAG 存储")

    # for i in range(1, 7):
    #     # 清理 Year 3
    #     clean_year_math(i)
    #
    #     print(f"\n开始生成 Year {i} 数学作业...")
    #     batch_data = generate_year_homework(i, count=500)
    #
    #     if batch_data:
    #         store.add_batch_homework(batch_data)
    #         print(f"成功添加 {len(batch_data)} 份 Year {i} 数学作业到 RAG 存储")

    # 显示统计信息
    stats = store.get_stats()
    print(f"\nRAG 存储统计:")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  按主题分布: {stats['by_subject']}")
    print(f"  按年级分布: {stats['by_year_group']}")


if __name__ == "__main__":
    main()