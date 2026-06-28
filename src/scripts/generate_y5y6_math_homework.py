#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
生成 100 份 Year 5 和 Year 6 数学作业并添加到 RAG 存储
"""
import sys
import os
import random

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from homework_rag import store_homework


# Year 5 和 Year 6 数学主题（英国小学课程）
MATH_TOPICS = [
    "Multiplication and Division (Large Numbers)",
    "Fractions, Decimals and Percentages",
    "Ratio and Proportion",
    "Algebra and Equations",
    "Measurement and Conversion",
    "Geometry and Coordinates",
    "Area, Perimeter and Volume",
    "Statistics and Data Interpretation",
    "Problem Solving and Reasoning",
    "Place Value and Rounding",
]


def generate_math_homework(topic: str, index: int, year_group: int) -> str:
    """生成一份数学作业内容"""

    if topic == "Multiplication and Division (Large Numbers)":
        questions = []
        for i in range(5):
            a = random.randint(100, 9999)
            b = random.randint(2, 12)
            questions.append(f"{i+1}. Calculate: {a} × {b} = ?")
        for i in range(5):
            b = random.randint(3, 12)
            result = random.randint(100, 999)
            a = b * result
            questions.append(f"{i+6}. Calculate: {a} ÷ {b} = ?")
        return f"Math Homework - Multiplication and Division (Year {year_group}, Set {index})\n\n" + "\n".join(questions)

    elif topic == "Fractions, Decimals and Percentages":
        questions = [
            f"1. Convert {random.choice([25, 50, 75])}% to a fraction in simplest form.",
            f"2. Convert {random.choice([1, 3, 7])}/4 to a decimal.",
            f"3. What is {random.choice([10, 20, 50])}% of {random.choice([80, 100, 200, 250])}?",
            f"4. Order these: 0.5, 1/4, 75%, 0.3 (smallest to largest).",
            f"5. Add: 2/5 + 1/3 = ?",
            f"6. Subtract: 3/4 - 1/6 = ?",
            f"7. What is {random.choice([3, 5, 7])}/8 as a decimal?",
            f"8. Convert 0.{random.choice([125, 25, 5, 625])} to a percentage.",
            f"9. A shirt costs £{random.choice([20, 40, 50])}. It is reduced by {random.choice([10, 20, 25])}%. What is the sale price?",
            f"10. In a class of {random.choice([20, 25, 30])} pupils, {random.choice([40, 50, 60])}% are boys. How many boys are there?",
        ]
        return f"Math Homework - Fractions, Decimals and Percentages (Year {year_group}, Set {index})\n\n" + "\n".join(questions)

    elif topic == "Ratio and Proportion":
        questions = [
            f"1. Simplify the ratio {random.choice([4, 6, 8])}:{random.choice([2, 3, 4])}.",
            f"2. Divide £{random.choice([30, 40, 50, 60])} in the ratio {random.randint(1,3)}:{random.randint(1,3)}.",
            f"3. If 3 apples cost £{random.randint(1, 5)}.{random.choice(['00', '50'])}, how much do {random.choice([6, 9, 12])} apples cost?",
            f"4. A recipe uses flour and sugar in the ratio {random.randint(2,5)}:1. If you use {random.choice([200, 300, 400])}g of flour, how much sugar do you need?",
            f"5. The ratio of boys to girls is {random.randint(2,4)}:{random.randint(1,3)}. There are {random.choice([15, 20, 25])} pupils. How many boys?",
            f"6. If {random.randint(3, 8)} pencils cost £{random.randint(1, 4)}.{random.choice(['00', '50', '20'])}, what is the cost of {random.randint(10, 20)} pencils?",
            f"7. A map scale is 1:{random.choice([100, 1000, 10000])}. A distance of {random.randint(2, 10)} cm on the map equals how many cm in real life?",
            f"8. Share {random.choice([24, 36, 48])} sweets between Tom and Amy in the ratio 2:3.",
            f"9. If 5 kg of potatoes cost £{random.randint(2, 6)}.{random.choice(['00', '50'])}, how much does 1 kg cost?",
            f"10. A juice is made by mixing water and concentrate in ratio {random.randint(3,5)}:1. To make {random.choice([500, 600, 1000])}ml, how much concentrate is needed?",
        ]
        return f"Math Homework - Ratio and Proportion (Year {year_group}, Set {index})\n\n" + "\n".join(questions)

    elif topic == "Algebra and Equations":
        questions = [
            f"1. If x + {random.randint(5, 20)} = {random.randint(20, 50)}, what is x?",
            f"2. If {random.randint(2, 5)} × y = {random.choice([24, 36, 48, 60])}, what is y?",
            f"3. Solve: 2a - {random.randint(3, 10)} = {random.randint(10, 30)}.",
            f"4. If 3n + {random.randint(1, 9)} = {random.choice([22, 31, 40, 49])}, find n.",
            f"5. Complete the sequence: {random.randint(1, 5)}, {random.randint(6, 15)}, {random.randint(16, 25)}, ___, ___.",
            f"6. If a = {random.randint(2, 8)} and b = {random.randint(2, 8)}, what is 3a + 2b?",
            f"7. Find the missing number: {random.randint(10, 50)} ÷ ? = {random.randint(2, 10)}.",
            f"8. If x = {random.randint(1, 10)}, what is x² + {random.randint(1, 20)}?",
            f"9. Solve: 5 × (n - {random.randint(1, 5)}) = {random.choice([20, 25, 30, 35])}.",
            f"10. Write an expression for 'a number multiplied by {random.randint(2, 6)}, then add {random.randint(1, 10)}'.",
        ]
        return f"Math Homework - Algebra and Equations (Year {year_group}, Set {index})\n\n" + "\n".join(questions)

    elif topic == "Measurement and Conversion":
        questions = [
            f"1. Convert {random.randint(1, 15)} km to metres.",
            f"2. Convert {random.choice([500, 1500, 2500, 3500])} m to km.",
            f"3. Convert {random.randint(1, 10)} kg to grams.",
            f"4. Convert {random.choice([1000, 2500, 5000, 7500])} g to kg.",
            f"5. A bottle holds {random.randint(1, 3)} litres {random.randint(0, 9) * 100} ml. How many ml?",
            f"6. Convert {random.randint(1, 10)} hours to minutes.",
            f"7. How many seconds in {random.randint(1, 10)} minutes?",
            f"8. A rope is {random.randint(2, 10)} m {random.randint(0, 9) * 10} cm long. Write in cm only.",
            f"9. Which is heavier: {random.randint(1, 5)} kg {random.randint(100, 900)} g or {random.randint(1, 6)} kg?",
            f"10. Order these: {random.randint(1, 5)} km, {random.randint(1000, 5000)} m, {random.randint(100000, 500000)} cm",
        ]
        return f"Math Homework - Measurement and Conversion (Year {year_group}, Set {index})\n\n" + "\n".join(questions)

    elif topic == "Geometry and Coordinates":
        questions = [
            f"1. Plot the point ({random.randint(-5, 5)}, {random.randint(-5, 5)}) on a coordinate grid.",
            f"2. What are the coordinates of a point {random.randint(2, 5)} units right and {random.randint(1, 4)} units up from the origin?",
            "3. What is the sum of angles in a triangle?",
            "4. What is the sum of angles in a quadrilateral?",
            f"5. A triangle has angles of {random.randint(30, 80)}° and {random.randint(30, 80)}°. What is the third angle?",
            f"6. Is a {random.choice([95, 100, 120, 150])}° angle acute or obtuse?",
            "7. Name a shape with exactly one pair of parallel sides.",
            f"8. How many degrees in {random.randint(1, 3)} right angles?",
            "9. Reflect the point (3, 4) in the x-axis. What are the new coordinates?",
            f"10. Translate the point ({random.randint(1, 5)}, {random.randint(1, 5)}) by moving {random.randint(1, 5)} units right and {random.randint(1, 3)} units up.",
        ]
        return f"Math Homework - Geometry and Coordinates (Year {year_group}, Set {index})\n\n" + "\n".join(questions)

    elif topic == "Area, Perimeter and Volume":
        questions = [
            f"1. Calculate the area of a rectangle with length {random.randint(5, 15)} cm and width {random.randint(3, 10)} cm.",
            f"2. Calculate the perimeter of a rectangle with length {random.randint(6, 12)} cm and width {random.randint(4, 8)} cm.",
            f"3. A square has side {random.randint(4, 9)} cm. What is its area?",
            f"4. A square has perimeter {random.choice([20, 24, 28, 32, 36])} cm. What is the length of one side?",
            f"5. Calculate the volume of a cuboid with dimensions {random.randint(2, 8)} cm × {random.randint(2, 6)} cm × {random.randint(2, 5)} cm.",
            f"6. A rectangle has area {random.choice([24, 36, 48, 60])} cm² and length {random.choice([4, 6, 8])} cm. What is the width?",
            f"7. A garden is {random.randint(5, 15)} m by {random.randint(3, 10)} m. How much fencing is needed?",
            f"8. A box has volume {random.choice([48, 60, 72, 80])} cm³. If length = {random.choice([3, 4, 5])} cm and width = {random.choice([2, 3, 4])} cm, what is the height?",
            f"9. Which has a larger area: a square of side {random.randint(4, 8)} cm or a rectangle of {random.randint(3, 6)} cm × {random.randint(6, 12)} cm?",
            f"10. A room is {random.randint(3, 8)} m long and {random.randint(2, 6)} m wide. How many tiles of 1 m² are needed to cover the floor?",
        ]
        return f"Math Homework - Area, Perimeter and Volume (Year {year_group}, Set {index})\n\n" + "\n".join(questions)

    elif topic == "Statistics and Data Interpretation":
        questions = [
            f"1. Find the mean of: {random.randint(5, 15)}, {random.randint(5, 15)}, {random.randint(5, 15)}, {random.randint(5, 15)}, {random.randint(5, 15)}.",
            f"2. Find the median of: {random.randint(10, 30)}, {random.randint(10, 30)}, {random.randint(10, 30)}, {random.randint(10, 30)}, {random.randint(10, 30)}.",
            f"3. Find the mode of: {random.choice([3, 5, 7])}, {random.choice([3, 5, 7])}, {random.choice([3, 5, 7])}, {random.choice([3, 5, 7])}, {random.choice([3, 5, 7])}.",
            f"4. Find the range of: {random.randint(1, 10)}, {random.randint(15, 30)}, {random.randint(5, 20)}, {random.randint(25, 50)}, {random.randint(10, 40)}.",
            f"5. The average of 4 numbers is {random.randint(10, 20)}. What is their total?",
            f"6. Five pupils scored {random.randint(60, 80)}, {random.randint(60, 80)}, {random.randint(60, 80)}, {random.randint(60, 80)}, {random.randint(60, 80)} in a test. What is the average?",
            f"7. A bar chart shows {random.randint(5, 15)} prefer apples, {random.randint(5, 15)} prefer bananas, {random.randint(5, 15)} prefer oranges. How many pupils in total?",
            f"8. The temperature on Monday was {random.randint(5, 15)}°C, Tuesday {random.randint(8, 20)}°C, Wednesday {random.randint(5, 18)}°C. What was the average temperature?",
            f"9. A survey shows {random.choice([40, 50, 60])}% like football, {random.choice([20, 30])}% like tennis, rest like swimming. What percentage like swimming?",
            f"10. The highest score is {random.randint(80, 100)}, the lowest is {random.randint(20, 50)}. What is the range?",
        ]
        return f"Math Homework - Statistics and Data Interpretation (Year {year_group}, Set {index})\n\n" + "\n".join(questions)

    elif topic == "Problem Solving and Reasoning":
        questions = [
            f"1. A shop sells {random.randint(50, 100)} items. {random.randint(10, 30)}% are on sale. How many items are on sale?",
            f"2. A train travels at {random.randint(40, 80)} mph for {random.randint(1, 4)} hours. How far does it go?",
            f"3. Tom has £{random.randint(20, 50)}. He spends {random.randint(1, 3)} items costing £{random.randint(3, 8)} each. How much change?",
            f"4. A rectangle has perimeter {random.choice([30, 36, 40, 44, 48])} cm. If the length is {random.randint(6, 12)} cm, what is the width?",
            f"5. {random.randint(100, 500)} pupils. {random.randint(1, 5)}/6 are in Year 5/6. How many?",
            f"6. A film starts at {random.randint(1, 10)}:{random.choice(['00', '15', '30'])} and ends at {random.randint(2, 12)}:{random.choice(['00', '15', '30', '45'])}. How long is it?",
            f"7. Three consecutive numbers add up to {random.choice([60, 75, 90, 105])}. What are they?",
            f"8. A box holds {random.randint(6, 12)} eggs. How many boxes for {random.randint(100, 200)} eggs?",
            f"9. You save £{random.randint(5, 15)} per week. How many weeks to save £{random.choice([100, 150, 200, 250])}?",
            f"10. A number is doubled, then {random.randint(5, 15)} is added. The result is {random.choice([35, 45, 55, 65])}. What was the original number?",
        ]
        return f"Math Homework - Problem Solving and Reasoning (Year {year_group}, Set {index})\n\n" + "\n".join(questions)

    else:  # Place Value and Rounding
        questions = [
            f"1. What is the value of digit {random.randint(1, 9)} in {random.randint(10000, 999999)}?",
            f"2. Round {random.randint(1000, 9999)} to the nearest 100.",
            f"3. Round {random.randint(10000, 99999)} to the nearest 1000.",
            f"4. Write {random.randint(100000, 999999)} in words.",
            f"5. What number is {random.randint(1000, 10000)} more than {random.randint(50000, 90000)}?",
            f"6. What number is {random.randint(1000, 10000)} less than {random.randint(100000, 500000)}?",
            f"7. Order these: {random.randint(10000, 50000)}, {random.randint(50000, 99999)}, {random.randint(10000, 99999)}",
            f"8. What is the largest {random.choice([5, 6])}-digit number using digits {random.randint(1,9)}, {random.randint(1,9)}, {random.randint(1,9)}, {random.randint(1,9)}, {random.randint(1,9)}?",
            f"9. Partition {random.randint(100000, 999999)} into hundred thousands, ten thousands, thousands, hundreds, tens, and ones.",
            f"10. Fill in: {random.randint(10000, 50000)} < ___ < {random.randint(50001, 99999)}",
        ]
        return f"Math Homework - Place Value and Rounding (Year {year_group}, Set {index})\n\n" + "\n".join(questions)


def main():
    """主函数：生成 100 份 Year 5 和 100 份 Year 6 数学作业并添加到 RAG"""
    print("开始生成 100 份 Year 5 数学作业...")

    homework_minutes_options = ["25-30", "30-35", "30"]

    batch_data_y5 = []

    for i in range(1, 101):
        topic = MATH_TOPICS[(i - 1) % len(MATH_TOPICS)]
        content = generate_math_homework(topic, i, 5)

        doc_id = f"hw_math_y5_{i:03d}"
        metadata = {
            "year_group": 5,
            "subject": "Math",
            "homework_minutes": random.choice(homework_minutes_options),
            "key_stage": "KS2",
            "topic": topic,
            "student_id": None,
        }

        batch_data_y5.append({
            "content": content,
            "metadata": metadata,
            "doc_id": doc_id,
        })

        if i % 10 == 0:
            print(f"Year 5: 已生成 {i}/100 份作业")

    print("\n开始生成 100 份 Year 6 数学作业...")

    batch_data_y6 = []

    for i in range(1, 101):
        topic = MATH_TOPICS[(i - 1) % len(MATH_TOPICS)]
        content = generate_math_homework(topic, i, 6)

        doc_id = f"hw_math_y6_{i:03d}"
        metadata = {
            "year_group": 6,
            "subject": "Math",
            "homework_minutes": random.choice(homework_minutes_options),
            "key_stage": "KS2",
            "topic": topic,
            "student_id": None,
        }

        batch_data_y6.append({
            "content": content,
            "metadata": metadata,
            "doc_id": doc_id,
        })

        if i % 10 == 0:
            print(f"Year 6: 已生成 {i}/100 份作业")

    # 批量添加到 RAG
    from homework_rag import get_homework_rag_store

    store = get_homework_rag_store()

    print("\n添加 Year 5 作业到 RAG...")
    store.add_batch_homework(batch_data_y5)
    print(f"成功添加 {len(batch_data_y5)} 份 Year 5 数学作业到 RAG 存储")

    print("\n添加 Year 6 作业到 RAG...")
    store.add_batch_homework(batch_data_y6)
    print(f"成功添加 {len(batch_data_y6)} 份 Year 6 数学作业到 RAG 存储")

    # 显示统计信息
    stats = store.get_stats()
    print(f"\nRAG 存储统计:")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  按主题分布: {stats['by_subject']}")
    print(f"  按年级分布: {stats['by_year_group']}")


if __name__ == "__main__":
    main()
