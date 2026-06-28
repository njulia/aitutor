#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
检查各年级数学作业是否存在，缺失则生成 100 份作业并添加到 RAG 存储
支持 Year 1-6 所有年级
"""
import sys
import os
import random

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from homework_rag import get_homework_rag_store


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


def generate_math_homework(year_group: int, topic: str, index: int) -> str:
    """根据年级、主题生成数学作业"""

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


def _generate_year1_homework(topic: str, index: int) -> str:
    """Year 1 数学作业（5-6 岁）"""
    if topic == "Number Recognition 1-20":
        nums = random.sample(range(1, 21), 10)
        questions = [f"{i+1}. Write the number: {n}" for i, n in enumerate(nums)]
    elif topic == "Counting and Ordering":
        starts = random.sample(range(1, 15), 5)
        questions = [f"{i+1}. Count on from {s}: {s}, __, __, __, __" for i, s in enumerate(starts)]
        questions += [f"{i+6}. Order these: {random.randint(1,10)}, {random.randint(1,10)}, {random.randint(1,10)}" for i in range(5)]
    elif topic == "Simple Addition":
        questions = [f"{i+1}. {random.randint(1,10)} + {random.randint(1,10)} = ?" for i in range(10)]
    elif topic == "Simple Subtraction":
        questions = [f"{i+1}. {random.randint(5,20)} - {random.randint(1,5)} = ?" for i in range(10)]
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
    elif topic == "Measurement (Length)":
        questions = [
            f"1. Which is longer: a pencil or a ruler?",
            f"2. Is a book longer than a table?",
            f"3. How many hand-spaces long is your desk?",
            f"4. Draw a line longer than your finger.",
            f"5. Is a shoe longer than a sock?",
            "6. Measure your pencil in cubes.",
            "7. Which is shorter: a pen or a crayon?",
            "8. How tall are you in cubes?",
            "9. Draw something shorter than your hand.",
            "10. Is a door taller than you?",
        ]
    elif topic == "Time (O'clock)":
        hours = random.sample(range(1, 13), 5)
        questions = [f"{i+1}. Draw the clock hands for {h}:00" for i, h in enumerate(hours)]
        questions += [f"{i+6}. What time is it? (clock shows {random.randint(1,12)}:00)" for i in range(5)]
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
    else:
        questions = [f"{i+1}. Year 1 Math practice question {i+1}" for i in range(10)]

    return f"Math Homework - Year 1 - {topic} (Set {index})\n\n" + "\n".join(questions)


def _generate_year2_homework(topic: str, index: int) -> str:
    """Year 2 数学作业（6-7 岁）"""
    if topic == "Addition and Subtraction (2-digit)":
        questions = []
        for i in range(5):
            a = random.randint(10, 50)
            b = random.randint(10, 50)
            questions.append(f"{i+1}. {a} + {b} = ?")
        for i in range(5):
            a = random.randint(30, 80)
            b = random.randint(10, a)
            questions.append(f"{i+6}. {a} - {b} = ?")
    elif topic == "Multiplication Basics":
        questions = [f"{i+1}. {random.randint(2,5)} × {random.randint(1,10)} = ?" for i in range(10)]
    elif topic == "Division Basics":
        questions = []
        for i in range(5):
            b = random.randint(2, 5)
            result = random.randint(2, 5)
            questions.append(f"{i+1}. {b * result} ÷ {b} = ?")
        for i in range(5):
            questions.append(f"{i+6}. Share {random.choice([6,8,10,12,15])} equally between {random.randint(2,3)} people.")
    elif topic == "Fractions (Halves and Quarters)":
        questions = [
            f"1. What is 1/2 of {random.choice([4,6,8,10,12])}?",
            f"2. What is 1/4 of {random.choice([4,8,12,16,20])}?",
            "3. Shade 1/2 of the rectangle.",
            "4. Shade 1/4 of the circle.",
            f"5. Which is bigger: 1/2 or 1/4 of {random.choice([8,12,16])}?",
            f"6. What is half of {random.choice([10,14,18,20])}?",
            f"7. What is a quarter of {random.choice([8,16,20,24])}?",
            "8. Draw a shape and shade 1/2.",
            "9. Draw a shape and shade 1/4.",
            f"10. If you have {random.choice([8,12,16])} sweets, what is 1/2?",
        ]
    elif topic == "Measurement (cm and m)":
        questions = [
            f"1. How many cm in 1 m?",
            f"2. Convert {random.randint(1,5)} m to cm.",
            f"3. Convert {random.choice([100,200,300,400,500])} cm to m.",
            f"4. Is a pencil about 15 cm or 15 m?",
            f"5. Is a room about 4 m or 4 cm wide?",
            "6. Measure your book in cm.",
            "7. How long is your desk in cm?",
            f"8. Which is longer: {random.randint(50,150)} cm or {random.randint(1,3)} m?",
            "9. Draw a line that is 10 cm long.",
            "10. How many cm in 2 m?",
        ]
    elif topic == "Time (Half Past)":
        hours = random.sample(range(1, 13), 5)
        questions = [f"{i+1}. Draw the clock hands for {h}:30" for i, h in enumerate(hours)]
        questions += [
            "6. What does 'half past' mean?",
            "7. Draw half past 3.",
            "8. Draw half past 9.",
            "9. How many minutes in half an hour?",
            "10. What time is half past 6?",
        ]
    elif topic == "Money (Pounds and Pence)":
        questions = [
            f"1. How many pence in £1?",
            f"2. How many pence in £{random.randint(2,5)}?",
            f"3. Convert {random.choice([100,200,300,500])}p to £.",
            f"4. You have £{random.randint(1,5)}. You spend {random.randint(50,200)}p. How much left?",
            f"5. A pencil costs {random.choice([20,30,50])}p. How much for 2 pencils?",
            "6. Write £2.50 in pence.",
            "7. Write 150p in pounds.",
            f"8. You have £{random.randint(1,3)}. You need £5. How much more do you need?",
            f"9. Three sweets cost {random.choice([10,20,30])}p each. Total cost?",
            f"10. Change from £5 when spending £{random.randint(1,3)}.{random.choice(['00','50'])}?",
        ]
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
    else:
        questions = [f"{i+1}. Year 2 Math practice question {i+1}" for i in range(10)]

    return f"Math Homework - Year 2 - {topic} (Set {index})\n\n" + "\n".join(questions)


def _generate_year3_homework(topic: str, index: int) -> str:
    """Year 3 数学作业（7-8 岁）"""
    if topic == "Addition and Subtraction":
        questions = []
        for i in range(5):
            a = random.randint(100, 500)
            b = random.randint(100, 500)
            questions.append(f"{i+1}. {a} + {b} = ?")
        for i in range(5):
            a = random.randint(200, 800)
            b = random.randint(100, a)
            questions.append(f"{i+6}. {a} - {b} = ?")
    elif topic == "Multiplication and Division":
        questions = []
        for i in range(5):
            a = random.randint(2, 10)
            b = random.randint(10, 50)
            questions.append(f"{i+1}. {b} × {a} = ?")
        for i in range(5):
            b = random.randint(2, 10)
            result = random.randint(10, 50)
            questions.append(f"{i+6}. {b * result} ÷ {b} = ?")
    elif topic == "Fractions":
        questions = [
            f"1. What is 1/3 of {random.choice([12,15,18,21,24])}?",
            f"2. What is 1/4 of {random.choice([8,12,16,20,24])}?",
            f"3. What is 1/5 of {random.choice([10,15,20,25,30])}?",
            "4. Which is larger: 1/2 or 1/4?",
            f"5. Add: 1/5 + 2/5 = ?",
            f"6. Subtract: 3/4 - 1/4 = ?",
            f"7. Order: 1/2, 1/3, 1/4 (smallest to largest).",
            f"8. What is 2/3 of {random.choice([9,12,15,18])}?",
            "9. Draw a shape and shade 2/3.",
            f"10. If you have {random.choice([15,20,25])} marbles and give away 1/5, how many left?",
        ]
    elif topic == "Measurement":
        questions = [
            f"1. Convert {random.randint(1,5)} m to cm.",
            f"2. Convert {random.choice([100,200,300,400,500])} cm to m.",
            f"3. Convert {random.randint(1,5)} kg to g.",
            f"4. Convert {random.choice([500,1000,1500,2000])} g to kg.",
            f"5. A string is {random.randint(1,3)} m {random.randint(0,9)*10} cm long. How many cm?",
            "6. Which is heavier: 1 kg or 500 g?",
            "7. How many ml in 1 litre?",
            f"8. Convert {random.choice([500,1000,1500])} ml to litres.",
            "9. Measure your desk in cm.",
            f"10. Order: {random.randint(1,5)} m, {random.randint(100,500)} cm, {random.randint(1000,5000)} mm",
        ]
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
    elif topic == "Time":
        questions = [
            f"1. What time is {random.randint(1,5)} hours after {random.randint(1,11)}:{random.choice(['00','15','30','45'])}?",
            f"2. What time was it {random.randint(1,3)} hours before {random.randint(4,12)}:{random.choice(['00','30'])}?",
            f"3. How many minutes in {random.randint(1,3)} hours?",
            "4. Draw clock hands for 4:15.",
            "5. Draw clock hands for 7:45.",
            f"6. School starts at 9:00 and ends at 3:30. How long?",
            f"7. How many seconds in {random.randint(1,5)} minutes?",
            "8. How many days in January?",
            "9. How many weeks in a year?",
            f"10. Convert {random.randint(1,12)} weeks to days.",
        ]
    elif topic == "Money":
        questions = [
            f"1. Convert £{random.randint(1,10)} to pence.",
            f"2. Convert {random.choice([100,200,350,500])}p to £.",
            f"3. You buy a toy for £{random.randint(2,5)}.{random.choice(['00','50','99'])}. Change from £10?",
            f"4. You have £{random.randint(5,15)}. Spend £{random.randint(1,4)}.{random.choice(['00','50'])}. How much left?",
            f"5. Three pencils cost {random.choice([30,45,60])}p each. Total?",
            f"6. A book costs £{random.randint(3,7)}. How much for {random.randint(2,4)} books?",
            "7. Write £3.50 in pence.",
            "8. Write 450p in pounds.",
            f"9. Save £{random.randint(2,5)} per week. How much in {random.randint(4,10)} weeks?",
            f"10. Share £{random.choice([10,15,20])} between {random.randint(2,5)} people.",
        ]
    elif topic == "Place Value":
        questions = [
            f"1. Value of digit {random.randint(1,9)} in {random.randint(100,999)}?",
            f"2. Write {random.randint(100,999)} in words.",
            f"3. Write 'two hundred and {random.choice(['twenty-three','forty-five','sixty-seven'])}' in numbers.",
            f"4. What is {random.randint(10,100)} more than {random.randint(100,500)}?",
            f"5. What is {random.randint(10,100)} less than {random.randint(300,900)}?",
            f"6. Partition {random.randint(100,999)} into hundreds, tens, ones.",
            f"7. Order: {random.randint(100,500)}, {random.randint(100,500)}, {random.randint(100,500)}",
            f"8. Largest 3-digit number with digits {random.randint(1,9)}, {random.randint(1,9)}, {random.randint(1,9)}?",
            f"9. 100 more than {random.randint(100,800)}?",
            f"10. 100 less than {random.randint(300,999)}?",
        ]
    elif topic == "Number Bonds":
        questions = [
            f"1. What + {random.randint(1,9)} = 10?",
            f"2. What + {random.randint(10,19)} = 20?",
            f"3. {random.randint(1,9)} + ? = 10",
            f"4. {random.randint(10,15)} + ? = 20",
            f"5. ? + {random.randint(1,9)} = 10",
            f"6. ? + {random.randint(5,15)} = 20",
            "7. Write three pairs that add to 10.",
            "8. Write three pairs that add to 20.",
            f"9. {random.randint(1,9)} + {random.randint(1,9)} = ?",
            f"10. {random.randint(10,19)} + {random.randint(1,9)} = ?",
        ]
    elif topic == "Problem Solving":
        questions = [
            f"1. {random.randint(20,50)} apples, {random.randint(5,15)} eaten. How many left?",
            f"2. Box holds {random.randint(5,10)} pencils. How many in {random.randint(3,8)} boxes?",
            f"3. Tom has £{random.randint(5,15)}. Spends £{random.randint(2,5)}. Gets £{random.randint(1,3)}. How much now?",
            f"4. Train leaves at {random.randint(1,11)}:{random.choice(['00','15','30','45'])}. Arrives {random.randint(1,4)} hours later. What time?",
            f"5. {random.randint(20,40)} children. Teams of {random.randint(4,6)}. How many teams?",
            f"6. Rectangle: length {random.randint(3,8)} cm, width {random.randint(2,5)} cm. Perimeter?",
            f"7. Reads {random.randint(10,30)} pages/day. How many in {random.randint(3,7)} days?",
            f"8. Pens cost {random.choice([30,40,50])}p. How many with £2?",
            f"9. {random.randint(30,60)} sweets shared among {random.randint(3,6)} children. Each gets?",
            f"10. Film lasts {random.randint(1,2)}h {random.choice([15,30,45])}min. Starts at {random.randint(1,6)}:{random.choice(['00','15','30','45'])}. Ends?",
        ]
    else:
        questions = [f"{i+1}. Year 3 Math practice question {i+1}" for i in range(10)]

    return f"Math Homework - Year 3 - {topic} (Set {index})\n\n" + "\n".join(questions)


def _generate_year4_homework(topic: str, index: int) -> str:
    """Year 4 数学作业（8-9 岁）"""
    if topic == "Multiplication and Division":
        questions = []
        for i in range(5):
            a = random.randint(2, 12)
            b = random.randint(10, 99)
            questions.append(f"{i+1}. {b} × {a} = ?")
        for i in range(5):
            b = random.randint(2, 12)
            result = random.randint(10, 50)
            questions.append(f"{i+6}. {b * result} ÷ {b} = ?")
    elif topic == "Fractions and Decimals":
        questions = [
            f"1. What is 1/3 of {random.choice([12,15,18,21,24,27])}?",
            f"2. What is 2/5 of {random.choice([10,15,20,25,30])}?",
            f"3. Convert {random.choice([1,2,3,4,5])}/10 to decimal.",
            f"4. Convert 0.{random.choice([2,4,6,8])} to fraction.",
            f"5. Which is larger: {random.choice(['1/2','2/3','3/4'])} or {random.choice(['1/3','1/4','2/5'])}?",
            "6. Add: 1/4 + 2/4 = ?",
            "7. Subtract: 3/5 - 1/5 = ?",
            f"8. Write {random.choice([3,5,7])}/10 as decimal.",
            "9. Order: 0.3, 1/2, 0.7, 1/4 (smallest to largest).",
            f"10. {random.choice([20,30,40])} sweets, eat 1/4. How many left?",
        ]
    elif topic == "Measurement and Conversion":
        questions = [
            f"1. Convert {random.randint(1,10)} km to m.",
            f"2. Convert {random.choice([500,1000,1500,2000,2500])} m to km.",
            f"3. Convert {random.randint(1,5)} kg to g.",
            f"4. Convert {random.choice([1000,2000,3000,4000])} g to kg.",
            f"5. Ribbon is {random.randint(1,5)} m long. How many cm?",
            f"6. Which is longer: {random.randint(1,5)} km or {random.randint(500,3000)} m?",
            f"7. Jug holds {random.randint(1,3)}L {random.randint(0,9)*100}ml. How many ml?",
            f"8. Convert {random.choice([500,1000,1500,2000,2500])} ml to litres.",
            f"9. Bag weighs {random.randint(1,5)}kg {random.randint(0,9)*100}g. Write in grams.",
            f"10. Order: {random.randint(1,5)} km, {random.randint(500,5000)} m, {random.randint(100,1000)} cm",
        ]
    elif topic == "Geometry and Angles":
        questions = [
            "1. What is a right angle in degrees?",
            "2. How many degrees in a straight line?",
            "3. How many degrees in a full turn?",
            f"4. How many sides does a {'hexagon' if random.choice([True,False]) else 'pentagon'} have?",
            "5. Name a shape with 8 sides.",
            f"6. Is {random.choice([45,60,90,120,135])} degrees acute, obtuse, or right?",
            "7. Draw an acute angle.",
            "8. How many pairs of parallel sides in a rectangle?",
            "9. Name a shape with rotational symmetry.",
            f"10. How many lines of symmetry in a {'square' if random.choice([True,False]) else 'equilateral triangle'}?",
        ]
    elif topic == "Time and Duration":
        questions = [
            f"1. Film starts at {random.randint(1,11)}:{random.choice(['00','15','30','45'])}. Lasts {random.randint(1,3)}h {random.choice([0,15,30,45])}min. Ends?",
            f"2. How many minutes in {random.randint(1,4)} hours?",
            f"3. How many seconds in {random.randint(1,5)} minutes?",
            f"4. Duration between {random.randint(1,11)}:{random.choice(['00','30'])} and {random.randint(2,12)}:{random.choice(['00','30'])}?",
            f"5. Train takes {random.randint(1,4)}h {random.choice([15,30,45])}min. Starts at {random.randint(1,10)}:{random.choice(['00','15','30'])}. Arrives?",
            "6. How many days in a leap year?",
            "7. How many hours in 3 days?",
            f"8. If today is Monday, what day in {random.randint(10,20)} days?",
            f"9. Lesson lasts {random.randint(45,60)} min. How many in {random.randint(2,4)} hours?",
            f"10. Convert {random.randint(1,12)} weeks to days.",
        ]
    elif topic == "Money and Budgeting":
        questions = [
            f"1. Convert £{random.randint(1,20)} to pence.",
            f"2. Convert {random.choice([500,1000,1500,2000,2500])}p to £.",
            f"3. Buy {random.randint(2,5)} items at £{random.randint(1,5)}.{random.choice(['00','50','99'])} each. Total?",
            f"4. Have £{random.randint(10,30)}. Spend £{random.randint(3,8)}.{random.choice(['00','50'])}. Change?",
            f"5. Toy costs £{random.randint(5,15)}. Save £{random.randint(2,5)}/week. How many weeks?",
            f"6. Three friends share £{random.choice([15,30,45,60])} equally. Each gets?",
            f"7. Book costs £{random.randint(3,8)}.{random.choice(['50','99'])} and pen costs £{random.randint(1,3)}.{random.choice(['00','50'])}. Total?",
            f"8. Save £{random.randint(3,10)}/week. How much in {random.randint(4,12)} weeks?",
            f"9. Item costs £{random.randint(5,20)}. Discount 10%. New price?",
            f"10. Budget £{random.randint(20,50)}. Buy items costing £{random.randint(3,8)}, £{random.randint(2,6)}, £{random.randint(4,10)}. Change?",
        ]
    elif topic == "Place Value and Rounding":
        questions = [
            f"1. Value of digit {random.randint(1,9)} in {random.randint(1000,9999)}?",
            f"2. Round {random.randint(1000,9999)} to nearest 100.",
            f"3. Round {random.randint(1000,9999)} to nearest 1000.",
            f"4. Write {random.randint(1000,9999)} in words.",
            f"5. What is {random.randint(100,1000)} more than {random.randint(1000,5000)}?",
            f"6. What is {random.randint(100,1000)} less than {random.randint(3000,9000)}?",
            f"7. Partition {random.randint(1000,9999)} into thousands, hundreds, tens, ones.",
            f"8. Order: {random.randint(1000,5000)}, {random.randint(1000,5000)}, {random.randint(1000,5000)}",
            f"9. Largest 4-digit number with digits {random.randint(1,9)}, {random.randint(1,9)}, {random.randint(1,9)}, {random.randint(1,9)}?",
            f"10. 1000 more than {random.randint(1000,8000)}?",
        ]
    elif topic == "Addition and Subtraction (4-digit)":
        questions = []
        for i in range(5):
            a = random.randint(1000, 5000)
            b = random.randint(1000, 5000)
            questions.append(f"{i+1}. {a} + {b} = ?")
        for i in range(5):
            a = random.randint(3000, 9000)
            b = random.randint(1000, a)
            questions.append(f"{i+6}. {a} - {b} = ?")
    elif topic == "Area and Perimeter":
        questions = [
            f"1. Rectangle: length {random.randint(3,10)} cm, width {random.randint(2,8)} cm. Area?",
            f"2. Rectangle: length {random.randint(3,10)} cm, width {random.randint(2,8)} cm. Perimeter?",
            f"3. Square: side {random.randint(3,8)} cm. Area?",
            f"4. Square: side {random.randint(3,8)} cm. Perimeter?",
            f"5. Area is {random.choice([12,16,20,24,30])} cm². Length is {random.choice([3,4,5,6])} cm. Width?",
            f"6. Perimeter is {random.choice([16,20,24,28,32])} cm. Square. Side length?",
            "7. Draw a rectangle with area 12 cm².",
            "8. Draw a square with perimeter 20 cm.",
            f"9. Room is {random.randint(3,6)} m by {random.randint(2,5)} m. Area?",
            f"10. Garden perimeter is {random.randint(20,40)} m. Length is {random.randint(5,10)} m. Width?",
        ]
    elif topic == "Data and Statistics":
        questions = [
            f"1. Find the mean of: {random.randint(1,10)}, {random.randint(1,10)}, {random.randint(1,10)}, {random.randint(1,10)}",
            f"2. Find the median of: {random.randint(1,10)}, {random.randint(1,10)}, {random.randint(1,10)}, {random.randint(1,10)}, {random.randint(1,10)}",
            f"3. What is the mode of: {random.choice([1,2,3])}, {random.choice([1,2,3])}, {random.choice([1,2,3])}, {random.choice([1,2,3])}, {random.choice([1,2,3])}?",
            f"4. Range of: {random.randint(1,10)}, {random.randint(1,10)}, {random.randint(1,10)}, {random.randint(1,10)}?",
            "5. Draw a bar chart for: Apples=5, Bananas=3, Oranges=7.",
            "6. Draw a pictograph for: Mon=10, Tue=15, Wed=8.",
            f"7. Survey: {random.randint(10,30)} like football, {random.randint(5,20)} like tennis. Total surveyed?",
            f"8. Which is most popular: Football ({random.randint(10,30)}), Tennis ({random.randint(5,25)}), Swimming ({random.randint(8,28)})?",
            "9. Interpret: 20 students, 12 like maths, 8 like English. Fraction like maths?",
            f"10. Average of {random.randint(1,10)}, {random.randint(1,10)}, {random.randint(1,10)}?",
        ]
    else:
        questions = [f"{i+1}. Year 4 Math practice question {i+1}" for i in range(10)]

    return f"Math Homework - Year 4 - {topic} (Set {index})\n\n" + "\n".join(questions)


def _generate_year5_homework(topic: str, index: int) -> str:
    """Year 5 数学作业（9-10 岁）"""
    if topic == "Large Numbers and Place Value":
        questions = [
            f"1. Value of digit {random.randint(1,9)} in {random.randint(10000,999999)}?",
            f"2. Write {random.randint(10000,999999)} in words.",
            f"3. Round {random.randint(10000,999999)} to nearest 1000.",
            f"4. Round {random.randint(10000,999999)} to nearest 10000.",
            f"5. What is {random.randint(1000,10000)} more than {random.randint(10000,50000)}?",
            f"6. What is {random.randint(1000,10000)} less than {random.randint(50000,999999)}?",
            f"7. Order: {random.randint(10000,99999)}, {random.randint(10000,99999)}, {random.randint(10000,99999)}",
            f"8. Partition {random.randint(10000,999999)} into place values.",
            f"9. Largest 6-digit number with digits {random.randint(1,9)}, {random.randint(1,9)}, {random.randint(1,9)}, {random.randint(1,9)}, {random.randint(1,9)}, {random.randint(1,9)}?",
            f"10. 10000 more than {random.randint(10000,90000)}?",
        ]
    elif topic == "Multiplication (4-digit by 2-digit)":
        questions = []
        for i in range(5):
            a = random.randint(100, 999)
            b = random.randint(10, 99)
            questions.append(f"{i+1}. {a} × {b} = ?")
        for i in range(5):
            a = random.randint(1000, 9999)
            b = random.randint(10, 99)
            questions.append(f"{i+6}. {a} × {b} = ?")
    elif topic == "Division and Long Division":
        questions = []
        for i in range(5):
            b = random.randint(3, 12)
            result = random.randint(50, 500)
            questions.append(f"{i+1}. {b * result} ÷ {b} = ?")
        for i in range(5):
            b = random.randint(10, 25)
            result = random.randint(100, 500)
            remainder = random.randint(1, b-1)
            questions.append(f"{i+6}. {b * result + remainder} ÷ {b} = ? (with remainder)")
    elif topic == "Fractions, Decimals and Percentages":
        questions = [
            f"1. Convert {random.choice([1,2,3,4,5,6,7,8,9])}/10 to decimal and percentage.",
            f"2. Convert {random.choice([25,50,75])}% to fraction and decimal.",
            f"3. What is {random.choice([25,50,75])}% of {random.choice([40,60,80,100,200])}?",
            f"4. Add: 2/5 + 1/3 = ?",
            f"5. Subtract: 3/4 - 1/6 = ?",
            f"6. Multiply: 2/3 × {random.randint(2,10)} = ?",
            f"7. Order: 0.6, 2/3, 65%, 3/5 (smallest to largest).",
            f"8. What fraction of {random.choice([20,40,50,100])} is {random.choice([5,10,20,25])}?",
            f"9. {random.choice([10,20,30,40,50])}% of {random.choice([60,80,100,120])}?",
            f"10. Convert 0.{random.choice([125,25,375,5,625,75,875])} to fraction and percentage.",
        ]
    elif topic == "Geometry (Angles and Coordinates)":
        questions = [
            f"1. What type of angle is {random.choice([30,45,60,90,120,135,150,180])} degrees?",
            f"2. Calculate the missing angle: Triangle has angles 60° and {random.choice([40,50,70,80])}°. Third angle?",
            f"3. Calculate the missing angle: Quadrilateral has angles 90°, 90°, {random.choice([60,80,100,120])}°. Fourth angle?",
            "4. Draw an acute angle.",
            "5. Draw an obtuse angle.",
            f"6. What are the coordinates of a point {random.randint(1,10)} units right and {random.randint(1,10)} units up from origin?",
            f"7. Plot points: ({random.randint(1,5)},{random.randint(1,5)}) and ({random.randint(1,5)},{random.randint(1,5)}). Draw the line.",
            "8. How many degrees in a triangle?",
            "9. How many degrees in a quadrilateral?",
            f"10. Reflect point ({random.randint(1,5)},{random.randint(1,5)}) across the x-axis.",
        ]
    elif topic == "Area and Volume":
        questions = [
            f"1. Rectangle: length {random.randint(5,15)} cm, width {random.randint(3,10)} cm. Area?",
            f"2. Rectangle: length {random.randint(5,15)} cm, width {random.randint(3,10)} cm. Perimeter?",
            f"3. Triangle: base {random.randint(4,10)} cm, height {random.randint(3,8)} cm. Area?",
            f"4. Cube: side {random.randint(2,6)} cm. Volume?",
            f"5. Cuboid: {random.randint(3,8)} cm × {random.randint(2,6)} cm × {random.randint(2,5)} cm. Volume?",
            f"6. Area is {random.choice([24,36,48,60])} cm². Length is {random.choice([4,6,8,10])} cm. Width?",
            f"7. Volume is {random.choice([24,36,48,60])} cm³. Length {random.choice([3,4,6])} cm, width {random.choice([2,3,4])} cm. Height?",
            "8. Draw a rectangle with area 24 cm².",
            f"9. Garden is {random.randint(5,15)} m by {random.randint(3,10)} m. Area?",
            f"10. Box is {random.randint(5,15)} cm × {random.randint(3,8)} cm × {random.randint(2,6)} cm. Volume?",
        ]
    elif topic == "Ratio and Proportion":
        questions = [
            f"1. Simplify ratio {random.randint(2,10)}:{random.randint(2,10)}.",
            f"2. Share {random.choice([20,30,40,50,60])} in ratio 2:3.",
            f"3. Share {random.choice([24,36,48,60])} in ratio 3:5.",
            f"4. If 3 apples cost £{random.choice([1,2,3])}, how much for {random.randint(5,15)} apples?",
            f"5. Recipe for 4 people needs {random.randint(100,500)}g flour. For {random.randint(8,12)} people?",
            f"6. Map scale 1:10000. Distance on map is {random.randint(2,10)} cm. Real distance?",
            f"7. If 5 pencils cost £{random.choice([1,2])}.{random.choice(['00','50'])}, cost of 12 pencils?",
            f"8. Ratio of boys:girls is 3:4. There are {random.choice([12,15,18,21])} boys. How many girls?",
            f"9. Car travels {random.randint(50,80)} miles in 1 hour. How far in {random.randint(2,5)} hours?",
            f"10. {random.randint(100,500)}g of rice serves {random.randint(2,4)} people. How much for {random.randint(6,10)} people?",
        ]
    elif topic == "Algebra Basics":
        questions = [
            f"1. If x + {random.randint(5,20)} = {random.randint(25,50)}, find x.",
            f"2. If {random.randint(2,10)} × y = {random.choice([24,36,48,60,72])}, find y.",
            f"3. Solve: 2x = {random.choice([20,30,40,50,60])}.",
            f"4. Solve: x - {random.randint(5,15)} = {random.randint(10,30)}.",
            f"5. If a = {random.randint(2,5)} and b = {random.randint(3,7)}, what is a + b?",
            f"6. If a = {random.randint(2,5)} and b = {random.randint(3,7)}, what is a × b?",
            f"7. Complete the sequence: {random.randint(1,5)}, {random.randint(6,10)}, {random.randint(11,15)}, __, __",
            f"8. Find the nth term: {random.randint(2,5)}, {random.randint(4,10)}, {random.randint(6,15)}, ...",
            f"9. If 3x + {random.randint(1,10)} = {random.randint(10,40)}, find x.",
            f"10. Write an expression for: 'A number multiplied by {random.randint(2,5)}, then add {random.randint(1,10)}'.",
        ]
    elif topic == "Statistics and Probability":
        questions = [
            f"1. Find the mean of: {random.randint(1,20)}, {random.randint(1,20)}, {random.randint(1,20)}, {random.randint(1,20)}, {random.randint(1,20)}",
            f"2. Find the median of: {random.randint(1,20)}, {random.randint(1,20)}, {random.randint(1,20)}, {random.randint(1,20)}, {random.randint(1,20)}",
            f"3. Mode of: {random.choice([2,4,6])}, {random.choice([2,4,6])}, {random.choice([2,4,6])}, {random.choice([2,4,6])}, {random.choice([2,4,6])}?",
            f"4. Range of: {random.randint(1,20)}, {random.randint(1,20)}, {random.randint(1,20)}, {random.randint(1,20)}?",
            "5. Draw a line graph for: Mon=10, Tue=15, Wed=8, Thu=12, Fri=20.",
            f"6. Probability of rolling a {random.randint(1,6)} on a dice?",
            f"7. Bag has {random.randint(3,8)} red balls and {random.randint(2,7)} blue balls. P(red)?",
            "8. Coin flipped. P(heads)?",
            f"9. Spinner has {random.randint(2,5)} sections. P(landing on one section)?",
            f"10. Survey: {random.randint(10,30)} prefer tea, {random.randint(5,25)} prefer coffee. P(tea)?",
        ]
    elif topic == "Problem Solving":
        questions = [
            f"1. {random.randint(100,500)} students. {random.randint(10,30)}% are boys. How many girls?",
            f"2. Rectangle area is {random.choice([48,60,72,84])} cm². Length is {random.choice([6,8,10,12])} cm. Perimeter?",
            f"3. Book costs £{random.randint(5,15)}.{random.choice(['00','50','99'])}. Discount 20%. New price?",
            f"4. Train travels {random.randint(50,80)} mph for {random.randint(1,4)} hours {random.choice([0,30])} min. Distance?",
            f"5. {random.randint(100,500)}g rice shared among {random.randint(4,8)} people. Each gets?",
            f"6. Box is {random.randint(5,15)} cm × {random.randint(3,10)} cm × {random.randint(2,8)} cm. Volume?",
            f"7. Save £{random.randint(5,20)}/week. Need £{random.randint(100,500)}. How many weeks?",
            f"8. Ratio 3:5. Total is {random.choice([24,32,40,48,56])}. Larger share?",
            f"9. Film starts {random.randint(1,11)}:{random.choice(['00','15','30','45'])}, lasts {random.randint(1,3)}h {random.choice([0,15,30,45])}min. Ends?",
            f"10. {random.randint(100,500)} pages. Read {random.randint(10,30)} pages/day. Days to finish?",
        ]
    else:
        questions = [f"{i+1}. Year 5 Math practice question {i+1}" for i in range(10)]

    return f"Math Homework - Year 5 - {topic} (Set {index})\n\n" + "\n".join(questions)


def _generate_year6_homework(topic: str, index: int) -> str:
    """Year 6 数学作业（10-11 岁）"""
    if topic == "Advanced Fractions and Decimals":
        questions = [
            f"1. Add: {random.choice(['2/3','3/4','5/6'])} + {random.choice(['1/4','1/3','2/5'])} = ?",
            f"2. Subtract: {random.choice(['3/4','5/6','7/8'])} - {random.choice(['1/3','1/4','1/6'])} = ?",
            f"3. Multiply: {random.choice(['2/3','3/5','4/7'])} × {random.choice(['3/4','5/6','2/5'])} = ?",
            f"4. Divide: {random.choice(['3/4','2/3','5/6'])} ÷ {random.choice(['1/2','2/3','3/4'])} = ?",
            f"5. Convert {random.choice([3,7,9,11,13])}/8 to mixed number.",
            f"6. Convert {random.choice([1,2,3])} {random.choice([1,3,5,7])}/{random.choice([2,4,8])} to improper fraction.",
            f"7. Order: 0.75, 3/4, 70%, 4/5 (smallest to largest).",
            f"8. What is {random.choice([0.1,0.01,0.001])} × {random.randint(100,9999)}?",
            f"9. {random.choice([0.5,0.25,0.2,0.125])} as fraction in simplest form?",
            f"10. {random.randint(100,999)} ÷ {random.choice([10,100,1000])}?",
        ]
    elif topic == "Multiplication and Division (Large Numbers)":
        questions = []
        for i in range(5):
            a = random.randint(1000, 9999)
            b = random.randint(10, 99)
            questions.append(f"{i+1}. {a} × {b} = ?")
        for i in range(5):
            b = random.randint(10, 25)
            result = random.randint(100, 999)
            remainder = random.randint(0, b-1)
            questions.append(f"{i+6}. {b * result + remainder} ÷ {b} = ?")
    elif topic == "Percentages and Ratio":
        questions = [
            f"1. What is {random.choice([10,15,20,25,50,75])}% of £{random.choice([40,60,80,100,200])}?",
            f"2. {random.choice([25,50,75])} is what % of {random.choice([100,200,300,400])}?",
            f"3. Increase {random.choice([100,150,200,250])} by {random.choice([10,20,25,50])}%.",
            f"4. Decrease {random.choice([100,150,200,250])} by {random.choice([10,20,25,50])}%.",
            f"5. Share £{random.choice([60,80,100,120])} in ratio {random.randint(2,5)}:{random.randint(2,5)}.",
            f"6. Price was £{random.choice([40,50,60,80])}. Increased by {random.choice([10,20,25])}%. New price?",
            f"7. Sale: {random.choice([20,25,30,50])}% off. Original £{random.choice([40,60,80,100])}. Sale price?",
            f"8. Ratio 5:7. Total {random.choice([36,48,60,72,84])}. Difference between shares?",
            f"9. {random.choice([15,20,25,30])}% of {random.choice([80,100,120,160])} students are girls. How many boys?",
            f"10. VAT at 20%. Item costs £{random.choice([50,60,80,100])}. Total with VAT?",
        ]
    elif topic == "Algebra and Equations":
        questions = [
            f"1. Solve: 3x + {random.randint(5,20)} = {random.randint(20,80)}.",
            f"2. Solve: 2(x - {random.randint(3,10)}) = {random.choice([20,30,40,50])}.",
            f"3. If x = {random.randint(2,8)} and y = {random.randint(3,10)}, find 2x + 3y.",
            f"4. If a = {random.randint(2,6)} and b = {random.randint(3,8)}, find a² + b.",
            f"5. Solve: {random.randint(2,8)}x - {random.randint(1,10)} = {random.randint(10,50)}.",
            f"6. Find y if 4y + {random.randint(2,10)} = 3y + {random.randint(10,30)}.",
            f"7. Simplify: {random.randint(2,5)}a + {random.randint(1,5)}a - {random.randint(1,3)}a.",
            f"8. Expand: {random.randint(2,5)}(x + {random.randint(1,10)}).",
            f"9. If 5x = 3y and x = {random.choice([3,6,9,12])}, find y.",
            f"10. nth term of sequence: {random.randint(3,8)}, {random.randint(5,16)}, {random.randint(7,24)}, ...",
        ]
    elif topic == "Geometry (Transformations)":
        questions = [
            f"1. Reflect point ({random.randint(1,8)},{random.randint(1,8)}) across y-axis.",
            f"2. Translate point ({random.randint(1,5)},{random.randint(1,5)}) by vector ({random.randint(-3,3)},{random.randint(-3,3)}).",
            f"3. Rotate point ({random.randint(1,5)},{random.randint(1,5)}) 90° clockwise about origin.",
            f"4. Find area of triangle with vertices (0,0), ({random.randint(2,6)},0), (0,{random.randint(2,6)}).",
            f"5. Find perimeter of rectangle with vertices (0,0), ({random.randint(3,8)},0), ({random.randint(3,8)},{random.randint(2,6)}), (0,{random.randint(2,6)}).",
            "6. How many lines of symmetry in a regular hexagon?",
            "7. How many lines of symmetry in an equilateral triangle?",
            "8. Describe the transformation from (2,3) to (5,3).",
            f"9. Point ({random.randint(1,5)},{random.randint(1,5)}) enlarged by scale factor {random.choice([2,3])}. New coordinates?",
            "10. What type of triangle has vertices (0,0), (4,0), (0,3)?",
        ]
    elif topic == "Area, Perimeter and Volume":
        questions = [
            f"1. Circle radius {random.choice([3,4,5,6,7])} cm. Area? (use π = 3.14)",
            f"2. Circle diameter {random.choice([6,8,10,12,14])} cm. Circumference? (use π = 3.14)",
            f"3. Triangle: base {random.randint(5,15)} cm, height {random.randint(4,12)} cm. Area?",
            f"4. Parallelogram: base {random.randint(5,12)} cm, height {random.randint(3,10)} cm. Area?",
            f"5. Trapezium: parallel sides {random.randint(4,8)} cm and {random.randint(6,12)} cm, height {random.randint(3,8)} cm. Area?",
            f"6. Cylinder: radius {random.randint(2,5)} cm, height {random.randint(5,10)} cm. Volume? (use π = 3.14)",
            f"7. Cube: side {random.randint(3,8)} cm. Surface area?",
            f"8. Cuboid: {random.randint(4,10)} cm × {random.randint(3,8)} cm × {random.randint(2,6)} cm. Surface area?",
            f"9. Circle circumference is {random.choice([31.4, 62.8, 94.2])} cm. Radius?",
            f"10. Sphere radius {random.randint(2,6)} cm. Volume? (use π = 3.14, V = 4/3πr³)",
        ]
    elif topic == "Statistics and Data Interpretation":
        questions = [
            f"1. Mean of: {random.randint(10,50)}, {random.randint(10,50)}, {random.randint(10,50)}, {random.randint(10,50)}, {random.randint(10,50)}",
            f"2. Median of: {random.randint(10,50)}, {random.randint(10,50)}, {random.randint(10,50)}, {random.randint(10,50)}, {random.randint(10,50)}, {random.randint(10,50)}",
            f"3. Mode of: {random.randint(10,30)}, {random.randint(10,30)}, {random.randint(10,30)}, {random.randint(10,30)}, {random.randint(10,30)}",
            f"4. Range of: {random.randint(10,50)}, {random.randint(10,50)}, {random.randint(10,50)}, {random.randint(10,50)}",
            "5. Draw a pie chart for: Football=40%, Tennis=25%, Swimming=35%.",
            f"6. Scatter graph shows correlation between study time and test score. Describe the relationship.",
            f"7. Mean of 5 numbers is {random.choice([15,20,25,30])}. Total sum?",
            f"8. Add a number to {random.randint(10,20)}, {random.randint(10,20)}, {random.randint(10,20)} so mean becomes {random.randint(15,25)}.",
            "9. Interpret: Box plot shows median=15, Q1=10, Q3=22. IQR?",
            f"10. Survey: {random.randint(50,100)} people. {random.randint(20,40)}% prefer A. How many prefer A?",
        ]
    elif topic == "Negative Numbers":
        questions = [
            f"1. {random.randint(-20,-1)} + {random.randint(1,20)} = ?",
            f"2. {random.randint(-10,-1)} - {random.randint(1,10)} = ?",
            f"3. {random.randint(-10,-1)} × {random.randint(1,10)} = ?",
            f"4. {random.randint(1,10)} - {random.randint(11,20)} = ?",
            f"5. Order: {random.randint(-10,0)}, {random.randint(-10,0)}, {random.randint(0,10)}, {random.randint(0,10)}",
            f"6. Temperature is {random.randint(-10,-1)}°C. Rises by {random.randint(5,15)}°C. New temperature?",
            f"7. Temperature is {random.randint(1,10)}°C. Drops by {random.randint(5,20)}°C. New temperature?",
            f"8. Bank balance: -£{random.randint(10,50)}. Deposit £{random.randint(20,100)}. New balance?",
            f"9. What is {random.randint(-10,-1)} × {random.randint(-10,-1)}?",
            f"10. Fill in: {random.randint(-10,0)} < {random.randint(-10,0)} (True or False)?",
        ]
    else:
        questions = [f"{i+1}. Year 6 Math practice question {i+1}" for i in range(10)]

    return f"Math Homework - Year 6 - {topic} (Set {index})\n\n" + "\n".join(questions)


# 各年级 Key Stage 和作业时间设置
YEAR_CONFIG = {
    1: {"key_stage": "KS1", "homework_minutes": "10-15"},
    2: {"key_stage": "KS1", "homework_minutes": "10-15"},
    3: {"key_stage": "KS2", "homework_minutes": "20-30"},
    4: {"key_stage": "KS2", "homework_minutes": "20-30"},
    5: {"key_stage": "KS2", "homework_minutes": "30"},
    6: {"key_stage": "KS2", "homework_minutes": "30"},
}


def check_year_math_exists(year_group: int) -> bool:
    """检查指定年级是否已有数学作业"""
    store = get_homework_rag_store()
    results = store.search(query="math", k=1, filters={"year_group": year_group, "subject": "Math"})
    return len(results) > 0


def generate_year_homework(year_group: int, count: int = 100) -> list:
    """为指定年级生成指定数量的数学作业"""
    topics = MATH_TOPICS_BY_YEAR.get(year_group, [])
    if not topics:
        print(f"警告：未找到 Year {year_group} 的数学主题")
        return []

    config = YEAR_CONFIG.get(year_group, {"key_stage": "KS2", "homework_minutes": "20-30"})
    batch_data = []

    for i in range(1, count + 1):
        topic = topics[(i - 1) % len(topics)]
        content = generate_math_homework(year_group, topic, i)

        doc_id = f"hw_math_y{year_group}_{i:03d}"
        metadata = {
            "year_group": year_group,
            "subject": "Math",
            "homework_minutes": config["homework_minutes"],
            "key_stage": config["key_stage"],
            "topic": topic,
            "student_id": None,
        }

        batch_data.append({
            "content": content,
            "metadata": metadata,
            "doc_id": doc_id,
        })

        if i % 10 == 0:
            print(f"  已生成 {i}/{count} 份作业")

    return batch_data


def main():
    """主函数：检查各年级数学作业，缺失则生成"""
    print("检查各年级数学作业是否存在...\n")

    store = get_homework_rag_store()
    years_to_generate = []

    for year in range(1, 7):
        exists = check_year_math_exists(year)
        status = "已有" if exists else "缺失"
        print(f"  Year {year}: {status}")
        if not exists:
            years_to_generate.append(year)

    if not years_to_generate:
        print("\n所有年级数学作业已存在，无需生成。")
        return

    print(f"\n需要生成的年级: {', '.join(f'Year {y}' for y in years_to_generate)}")

    for year in years_to_generate:
        print(f"\n开始生成 Year {year} 数学作业...")
        batch_data = generate_year_homework(year, count=100)

        if batch_data:
            store.add_batch_homework(batch_data)
            print(f"成功添加 {len(batch_data)} 份 Year {year} 数学作业到 RAG 存储")

    # 显示统计信息
    stats = store.get_stats()
    print(f"\nRAG 存储统计:")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  按主题分布: {stats['by_subject']}")
    print(f"  按年级分布: {stats['by_year_group']}")


if __name__ == "__main__":
    main()