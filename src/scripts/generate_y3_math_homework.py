#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
生成 100 份 Year 3 数学作业并添加到 RAG 存储
"""
import sys
import os
import random

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from homework_rag import store_homework


# Year 3 数学主题（英国小学课程）
MATH_TOPICS = [
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
]


def generate_math_homework(topic: str, index: int) -> str:
    """生成一份数学作业内容"""
    
    if topic == "Addition and Subtraction":
        questions = []
        for i in range(5):
            a = random.randint(10, 100)
            b = random.randint(10, 100)
            questions.append(f"{i+1}. Calculate: {a} + {b} = ?")
        for i in range(5):
            a = random.randint(50, 150)
            b = random.randint(10, a)
            questions.append(f"{i+6}. Calculate: {a} - {b} = ?")
        return f"Math Homework - Addition and Subtraction (Set {index})\n\n" + "\n".join(questions)
    
    elif topic == "Multiplication and Division":
        questions = []
        for i in range(5):
            a = random.randint(2, 10)
            b = random.randint(2, 10)
            questions.append(f"{i+1}. Calculate: {a} × {b} = ?")
        for i in range(5):
            b = random.randint(2, 10)
            result = random.randint(2, 10)
            a = b * result
            questions.append(f"{i+6}. Calculate: {a} ÷ {b} = ?")
        return f"Math Homework - Multiplication and Division (Set {index})\n\n" + "\n".join(questions)
    
    elif topic == "Fractions":
        questions = [
            f"1. What is 1/2 of {random.choice([10, 12, 14, 16, 18, 20])}?",
            f"2. What is 1/4 of {random.choice([8, 12, 16, 20, 24])}?",
            f"3. What is 1/3 of {random.choice([9, 12, 15, 18, 21])}?",
            f"4. Compare: Which is larger, 1/2 or 1/4?",
            f"5. Draw a rectangle and shade {random.choice(['1/2', '1/4', '1/3'])} of it.",
            f"6. What fraction of 20 is {random.choice([5, 10, 4])}?",
            f"7. Fill in the blank: 1/2 = ?/4",
            f"8. Fill in the blank: 1/3 = ?/6",
            f"9. Order these fractions from smallest to largest: 1/4, 1/2, 1/3",
            f"10. If you have {random.choice([8, 12, 16])} apples and give away 1/4, how many do you give away?",
        ]
        return f"Math Homework - Fractions (Set {index})\n\n" + "\n".join(questions)
    
    elif topic == "Measurement":
        questions = [
            f"1. Convert {random.choice([1, 2, 3, 4, 5])} metres to centimetres.",
            f"2. Convert {random.choice([100, 200, 300, 400, 500])} centimetres to metres.",
            f"3. Convert {random.choice([1, 2, 3, 4, 5])} kilograms to grams.",
            f"4. Convert {random.choice([500, 1000, 1500, 2000])} grams to kilograms.",
            f"5. A pencil is {random.randint(10, 20)} cm long. How many mm is this?",
            f"6. Which is heavier: {random.randint(1, 5)} kg or {random.randint(500, 2000)} g?",
            f"7. Measure the length of your desk in cm.",
            f"8. How many litres is {random.choice([500, 1000, 1500, 2000])} ml?",
            f"9. A bottle holds {random.randint(1, 3)} litres. How many ml is this?",
            f"10. Order these lengths: {random.randint(10, 50)} cm, {random.randint(1, 5)} m, {random.randint(100, 500)} mm",
        ]
        return f"Math Homework - Measurement (Set {index})\n\n" + "\n".join(questions)
    
    elif topic == "Geometry":
        questions = [
            "1. How many sides does a triangle have?",
            "2. How many sides does a square have?",
            "3. How many sides does a rectangle have?",
            f"4. Name a shape with {random.choice([5, 6, 8])} sides.",
            "5. How many corners does a cube have?",
            "6. How many faces does a cube have?",
            "7. Draw a right angle.",
            "8. Is a circle a 2D or 3D shape?",
            "9. Name one 3D shape you can see at home.",
            f"10. How many edges does a {'cuboid' if random.choice([True, False]) else 'pyramid'} have?",
        ]
        return f"Math Homework - Geometry (Set {index})\n\n" + "\n".join(questions)
    
    elif topic == "Time":
        questions = [
            f"1. What time will it be {random.randint(1, 5)} hours after {random.randint(1, 11)}:{random.choice(['00', '15', '30', '45'])}?",
            f"2. What time was it {random.randint(1, 3)} hours before {random.randint(4, 12)}:{random.choice(['00', '15', '30', '45'])}?",
            f"3. How many minutes are in {random.randint(1, 3)} hours?",
            f"4. How many hours are in {random.randint(1, 3)} days?",
            "5. Draw the hands on a clock to show 3:30.",
            "6. Draw the hands on a clock to show 9:15.",
            f"7. If school starts at 9:00 and ends at 3:30, how long is the school day?",
            f"8. What is {random.randint(1, 59)} minutes past {random.randint(1, 11)} o'clock?",
            "9. How many days are in January?",
            "10. How many weeks are in a year?",
        ]
        return f"Math Homework - Time (Set {index})\n\n" + "\n".join(questions)
    
    elif topic == "Money":
        questions = [
            f"1. How many pence is £{random.randint(1, 10)}?",
            f"2. Convert {random.choice([100, 200, 350, 500, 750])}p to pounds.",
            f"3. You buy a toy for £{random.randint(2, 8)}.{random.choice(['00', '50', '99'])}. You pay with £10. How much change do you get?",
            f"4. You have £{random.randint(5, 20)}. You spend £{random.randint(1, 4)}.{random.choice(['00', '50'])}. How much do you have left?",
            f"5. Three pencils cost {random.choice([30, 45, 60])}p each. How much do they cost in total?",
            f"6. A book costs £{random.randint(3, 7)}. How much would {random.randint(2, 4)} books cost?",
            "7. Write £2.50 in pence.",
            "8. Write 350p in pounds.",
            f"9. You save £{random.randint(2, 5)} each week. How much will you have saved in {random.randint(4, 10)} weeks?",
            f"10. Share £{random.choice([10, 12, 15, 20])} equally between {random.randint(2, 5)} people. How much does each person get?",
        ]
        return f"Math Homework - Money (Set {index})\n\n" + "\n".join(questions)
    
    elif topic == "Place Value":
        questions = [
            f"1. What is the value of the digit {random.randint(1, 9)} in the number {random.randint(100, 999)}?",
            f"2. Write {random.randint(100, 999)} in words.",
            f"3. Write '{random.choice(['one hundred and twenty-three', 'two hundred and fifty', 'three hundred and four'])}' in numbers.",
            f"4. What number is {random.randint(10, 100)} more than {random.randint(100, 500)}?",
            f"5. What number is {random.randint(10, 100)} less than {random.randint(300, 900)}?",
            f"6. Partition {random.randint(100, 999)} into hundreds, tens and ones.",
            f"7. Order these numbers: {random.randint(100, 500)}, {random.randint(100, 500)}, {random.randint(100, 500)}",
            f"8. What is the largest 3-digit number you can make with digits {random.randint(1,9)}, {random.randint(1,9)}, {random.randint(1,9)}?",
            f"9. What is 100 more than {random.randint(100, 800)}?",
            f"10. What is 100 less than {random.randint(300, 999)}?",
        ]
        return f"Math Homework - Place Value (Set {index})\n\n" + "\n".join(questions)
    
    elif topic == "Number Bonds":
        questions = [
            f"1. What number added to {random.randint(1, 9)} makes 10?",
            f"2. What number added to {random.randint(10, 19)} makes 20?",
            f"3. Complete: {random.randint(1, 9)} + ? = 10",
            f"4. Complete: {random.randint(10, 15)} + ? = 20",
            f"5. Find the missing number: ? + {random.randint(1, 9)} = 10",
            f"6. Find the missing number: ? + {random.randint(5, 15)} = 20",
            f"7. Write three pairs of numbers that add up to 10.",
            f"8. Write three pairs of numbers that add up to 20.",
            f"9. If {random.randint(1, 9)} + {random.randint(1, 9)} = ?, what is the answer?",
            f"10. Use number bonds to solve: {random.randint(10, 19)} + {random.randint(1, 9)} = ?",
        ]
        return f"Math Homework - Number Bonds (Set {index})\n\n" + "\n".join(questions)
    
    else:  # Problem Solving
        questions = [
            f"1. There are {random.randint(20, 50)} apples. {random.randint(5, 15)} are eaten. How many are left?",
            f"2. A box holds {random.randint(5, 10)} pencils. How many pencils in {random.randint(3, 8)} boxes?",
            f"3. Tom has £{random.randint(5, 15)}. He spends £{random.randint(2, 5)}. His friend gives him £{random.randint(1, 3)}. How much does he have now?",
            f"4. A train leaves at {random.randint(1, 11)}:{random.choice(['00', '15', '30', '45'])} and arrives {random.randint(1, 4)} hours later. What time does it arrive?",
            f"5. There are {random.randint(20, 40)} children. Each team needs {random.randint(4, 6)} children. How many teams can be made?",
            f"6. A rectangle has length {random.randint(3, 8)} cm and width {random.randint(2, 5)} cm. What is the perimeter?",
            f"7. Sarah reads {random.randint(10, 30)} pages each day. How many pages in {random.randint(3, 7)} days?",
            f"8. A shop sells pens for {random.choice([30, 40, 50])}p each. How many can you buy with £2?",
            f"9. There are {random.randint(30, 60)} sweets. They are shared equally among {random.randint(3, 6)} children. How many does each child get?",
            f"10. A film lasts {random.randint(1, 2)} hours {random.choice([15, 30, 45])} minutes. It starts at {random.randint(1, 6)}:{random.choice(['00', '15', '30', '45'])}. What time does it end?",
        ]
        return f"Math Homework - Problem Solving (Set {index})\n\n" + "\n".join(questions)


def main():
    """主函数：生成 100 份作业并添加到 RAG"""
    print("开始生成 100 份 Year 3 数学作业...")
    
    homework_minutes_options = ["15-20", "20-25", "25-30"]
    
    batch_data = []
    
    for i in range(1, 101):
        topic = MATH_TOPICS[(i - 1) % len(MATH_TOPICS)]
        content = generate_math_homework(topic, i)
        
        doc_id = f"hw_math_y3_{i:03d}"
        metadata = {
            "year_group": 3,
            "subject": "Math",
            "homework_minutes": random.choice(homework_minutes_options),
            "key_stage": "KS2",
            "topic": topic,
            "student_id": None,
        }
        
        batch_data.append({
            "content": content,
            "metadata": metadata,
            "doc_id": doc_id,
        })
        
        if i % 10 == 0:
            print(f"已生成 {i}/100 份作业")
    
    # 批量添加到 RAG
    from homework_rag import get_homework_rag_store
    
    store = get_homework_rag_store()
    store.add_batch_homework(batch_data)
    
    print(f"成功添加 {len(batch_data)} 份数学作业到 RAG 存储")
    
    # 显示统计信息
    stats = store.get_stats()
    print(f"\nRAG 存储统计:")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  按主题分布: {stats['by_subject']}")
    print(f"  按年级分布: {stats['by_year_group']}")


if __name__ == "__main__":
    main()
