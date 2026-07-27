#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate deterministic England-curriculum Maths homework for Years 1-6.

The storage and review contract is unchanged.  Every worksheet still contains
numbered questions and stores a positional ``correct_answers`` list in
``src.homework_rag``.  Questions are closed-response or multiple-choice so the
existing reviewer can mark them reliably.

Curriculum basis: Department for Education, National curriculum in England:
mathematics programmes of study, key stages 1 and 2.  The current curriculum
remains in force until the revised curriculum starts in September 2028.
"""
from __future__ import annotations

import argparse
import os
import sys
from fractions import Fraction
from pathlib import Path

# Load the project .env before importing the RAG modules. PGVectorStore chooses
# its database backend and SQL column type when it is imported, so loading the
# environment afterwards would leave this command on the SQLite fallback.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass

from src.homework_rag import get_homework_rag_store
from scripts.homework_generator.homework_generator_utils import (
    add_homework_in_batches,
    build_batch_item,
    count_year_homework,
    get_rag_stats,
    make_mcq,
    render_homework,
    stable_random,
)

os.environ["TOKENIZERS_PARALLELISM"] = "false"

HOMEWORK_COUNT = {1: 600, 2: 600, 3: 1000, 4: 1000, 5: 2000, 6: 2000}

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
        "Properties of Shapes and Angles",
        "Position and Direction (Coordinates)",
        "Time and Duration",
        "Money and Budgeting",
        "Place Value and Rounding",
        "Addition and Subtraction (4-digit)",
        "Area and Perimeter",
        "Statistics (Bar Charts and Time Graphs)",
    ],
    5: [
        "Large Numbers and Place Value",
        "Multiplication (4-digit by 2-digit)",
        "Division and Long Division",
        "Prime Numbers, Factors, Squares and Cubes",
        "Fractions, Decimals and Percentages",
        "Properties of Shapes: Angles",
        "Position and Direction (Reflection and Translation)",
        "Measurement and Conversion",
        "Area and Volume",
        "Statistics (Line Graphs and Tables)",
        "Problem Solving",
    ],
    6: [
        "Advanced Fractions and Decimals",
        "Multiplication and Division (Large Numbers)",
        "Percentages and Ratio",
        "Algebra and Equations",
        "Geometry (Transformations)",
        "Properties of Shapes (Circles, Angles and Nets)",
        "Area, Perimeter and Volume",
        "Statistics and Data Interpretation",
        "Negative Numbers",
        "SATs Preparation",
        "Complex Problem Solving",
    ],
}

YEAR_CONFIG = {
    1: {"key_stage": "KS1", "homework_minutes": "10-15"},
    2: {"key_stage": "KS1", "homework_minutes": "10-20"},
    3: {"key_stage": "KS2", "homework_minutes": "15-20"},
    4: {"key_stage": "KS2", "homework_minutes": "20-25"},
    5: {"key_stage": "KS2", "homework_minutes": "20-30"},
    6: {"key_stage": "KS2", "homework_minutes": "25-30"},
}


def _num_mcq(stem: str, answer: int | float | str, rng, *, spread: int = 3):
    if isinstance(answer, int):
        distractors = [answer + spread, answer - spread, answer + 1, answer - 1, answer + 10]
    elif isinstance(answer, float):
        distractors = [round(answer + 0.1, 2), round(answer - 0.1, 2), round(answer + 1, 2), round(answer / 10, 2)]
    else:
        distractors = ["0", "1", "10", "100"]
    return make_mcq(stem, answer, distractors, rng)


def _year1(topic: str, index: int):
    rng = stable_random("Maths", 1, topic, index)
    q = []
    if topic == "Number Recognition 1-20":
        for _ in range(10):
            n = rng.randint(1, 20)
            kind = rng.choice(["next", "before", "word", "compare"])
            if kind == "next":
                q.append(_num_mcq(f"What number is one more than {n}?", n + 1, rng))
            elif kind == "before":
                q.append(_num_mcq(f"What number is one less than {n}?", n - 1, rng))
            elif kind == "word":
                words = {1:"one",2:"two",3:"three",4:"four",5:"five",6:"six",7:"seven",8:"eight",9:"nine",10:"ten",11:"eleven",12:"twelve",13:"thirteen",14:"fourteen",15:"fifteen",16:"sixteen",17:"seventeen",18:"eighteen",19:"nineteen",20:"twenty"}
                q.append(make_mcq(f"Which numeral means {words[n]}?", n, [max(0,n-1), n+1, min(20,n+2), 10], rng))
            else:
                m = rng.randint(1, 20)
                answer = "greater than" if n > m else "less than" if n < m else "equal to"
                q.append(make_mcq(f"How does {n} compare with {m}?", answer, ["greater than","less than","equal to","cannot tell"], rng))
    elif topic == "Counting and Ordering":
        for _ in range(10):
            start = rng.randint(0, 15)
            step = rng.choice([1, 2, 5])
            seq = [start + step * i for i in range(4)]
            missing = rng.randint(1, 3)
            answer = seq[missing]
            shown = ["__" if i == missing else str(v) for i, v in enumerate(seq)]
            q.append(_num_mcq(f"Which number completes the sequence: {', '.join(shown)}?", answer, rng, spread=step))
    elif topic == "Simple Addition":
        for _ in range(10):
            a = rng.randint(0, 10)
            b = rng.randint(0, 20-a)
            q.append(_num_mcq(f"What is {a} + {b}?", a+b, rng))
    elif topic == "Simple Subtraction":
        for _ in range(10):
            a = rng.randint(5, 20)
            b = rng.randint(0, a)
            q.append(_num_mcq(f"What is {a} - {b}?", a-b, rng))
    elif topic == "Shapes and Patterns":
        facts = [
            ("Which shape has 3 straight sides?", "triangle", ["square","circle","rectangle"]),
            ("Which shape has 4 equal sides?", "square", ["triangle","circle","rectangle"]),
            ("Which 3D shape has 6 square faces?", "cube", ["sphere","cone","cylinder"]),
            ("Which 3D shape can roll and has no flat faces?", "sphere", ["cube","cuboid","pyramid"]),
            ("What comes next: red, blue, red, blue, ...?", "red", ["blue","green","yellow"]),
        ]
        for i in range(10):
            stem, ans, wrong = facts[(i + index) % len(facts)]
            q.append(make_mcq(stem, ans, wrong, rng))
    elif topic == "Measurement (Length)":
        for _ in range(10):
            a, b = rng.randint(1, 20), rng.randint(1, 20)
            if a == b:
                b += 1
            if rng.random() < 0.5:
                ans = f"{max(a,b)} cm"
                q.append(make_mcq(f"Which is the longer length: {a} cm or {b} cm?", ans, [f"{min(a,b)} cm", f"{a+b} cm", "They are equal"], rng))
            else:
                q.append(_num_mcq(f"A ribbon is {a} cm long. Another ribbon is {b} cm long. What is their total length in cm?", a+b, rng))
    elif topic == "Time (O'clock)":
        for _ in range(10):
            hour = rng.randint(1, 12)
            if rng.random() < 0.5:
                q.append(make_mcq(f"Which digital time shows {hour} o'clock?", f"{hour}:00", [f"{hour}:30", f"{(hour%12)+1}:00", "12:30"], rng))
            else:
                next_hour = (hour % 12) + 1
                q.append(make_mcq(f"It is {hour} o'clock. What time will it be one hour later?", f"{next_hour} o'clock", [f"{hour} o'clock", f"{hour}:30", f"{((next_hour)%12)+1} o'clock"], rng))
    elif topic == "Money (Coins)":
        coins = [1, 2, 5, 10, 20, 50]
        for _ in range(10):
            a, b = rng.choice(coins), rng.choice(coins)
            q.append(make_mcq(f"What is the value of a {a}p coin and a {b}p coin altogether?", f"{a+b}p", [f"{abs(a-b)}p", f"{max(a,b)}p", f"{a+b+5}p"], rng))
    else:
        raise ValueError(f"Unknown Year 1 Maths topic: {topic}")
    return render_homework("Maths", 1, topic, index, q)


def _year2(topic: str, index: int):
    rng = stable_random("Maths", 2, topic, index)
    q = []
    if topic == "Addition and Subtraction (2-digit)":
        for _ in range(10):
            a, b = rng.randint(10, 80), rng.randint(1, 19)
            if rng.random() < 0.5:
                q.append(_num_mcq(f"What is {a} + {b}?", a+b, rng, spread=10))
            else:
                if b > a: a, b = b, a
                q.append(_num_mcq(f"What is {a} - {b}?", a-b, rng, spread=10))
    elif topic == "Multiplication Basics":
        for _ in range(10):
            table = rng.choice([2, 5, 10])
            n = rng.randint(1, 12)
            q.append(_num_mcq(f"What is {table} × {n}?", table*n, rng, spread=table))
    elif topic == "Division Basics":
        for _ in range(10):
            divisor = rng.choice([2, 5, 10])
            answer = rng.randint(1, 10)
            q.append(_num_mcq(f"What is {divisor*answer} ÷ {divisor}?", answer, rng))
    elif topic == "Fractions (Halves and Quarters)":
        for _ in range(10):
            whole = rng.choice([4, 8, 12, 16, 20])
            denominator = rng.choice([2, 4])
            ans = whole // denominator
            q.append(_num_mcq(f"What is one {('half' if denominator==2 else 'quarter')} of {whole}?", ans, rng))
    elif topic == "Measurement (cm and m)":
        for _ in range(10):
            if rng.random() < 0.5:
                metres = rng.randint(1, 9)
                q.append(make_mcq(f"How many centimetres are in {metres} metre{'s' if metres>1 else ''}?", f"{metres*100} cm", [f"{metres*10} cm", f"{metres} cm", f"{metres*1000} cm"], rng))
            else:
                a, b = rng.randint(10, 80), rng.randint(5, 40)
                q.append(make_mcq(f"A string is {a} cm long. {b} cm is cut off. How long is it now?", f"{a-b} cm", [f"{a+b} cm", f"{b} cm", f"{a} cm"], rng))
    elif topic == "Time (Half Past)":
        for _ in range(10):
            hour = rng.randint(1, 12)
            if rng.random() < 0.5:
                q.append(make_mcq(f"Which digital time means half past {hour}?", f"{hour}:30", [f"{hour}:00", f"{(hour%12)+1}:30", f"{hour}:15"], rng))
            else:
                q.append(make_mcq(f"It is {hour}:00. What time is it 30 minutes later?", f"{hour}:30", [f"{hour}:15", f"{(hour%12)+1}:00", f"{hour}:45"], rng))
    elif topic == "Money (Pounds and Pence)":
        for _ in range(10):
            pounds = rng.randint(1, 5)
            pence = rng.choice([5, 10, 20, 50])
            q.append(make_mcq(f"How many pence is £{pounds}.{pence:02d}?", f"{pounds*100+pence}p", [f"{pounds*10+pence}p", f"{pounds*100}p", f"{pence}p"], rng))
    elif topic == "Geometry (2D Shapes)":
        facts = [
            ("Which shape has 5 sides?", "pentagon", ["triangle","square","hexagon"]),
            ("Which shape has 6 sides?", "hexagon", ["pentagon","octagon","rectangle"]),
            ("How many vertices does a rectangle have?", "4", ["2","3","5"]),
            ("Which shape has no straight sides?", "circle", ["triangle","square","pentagon"]),
            ("How many lines of symmetry does a square have?", "4", ["1","2","3"]),
        ]
        for i in range(10):
            stem, ans, wrong = facts[(i+index)%len(facts)]
            q.append(make_mcq(stem, ans, wrong, rng))
    else:
        raise ValueError(f"Unknown Year 2 Maths topic: {topic}")
    return render_homework("Maths", 2, topic, index, q)


def _year3(topic: str, index: int):
    rng = stable_random("Maths", 3, topic, index)
    q=[]
    if topic == "Addition and Subtraction":
        for _ in range(10):
            a,b=rng.randint(100,700),rng.randint(20,250)
            if rng.random()<0.5: q.append(_num_mcq(f"Calculate {a} + {b}.",a+b,rng,spread=10))
            else:
                if b>a:a,b=b,a
                q.append(_num_mcq(f"Calculate {a} - {b}.",a-b,rng,spread=10))
    elif topic == "Multiplication and Division":
        for _ in range(10):
            t=rng.choice([3,4,8]); n=rng.randint(2,12)
            if rng.random()<0.5:q.append(_num_mcq(f"What is {t} × {n}?",t*n,rng,spread=t))
            else:q.append(_num_mcq(f"What is {t*n} ÷ {t}?",n,rng))
    elif topic == "Fractions":
        for _ in range(10):
            den=rng.choice([2,3,4,5,8,10]); num=rng.randint(1,den-1)
            kind=rng.choice(["part","compare","equiv"])
            if kind=="part":
                whole=den*rng.randint(2,8); ans=whole*num//den
                q.append(_num_mcq(f"What is {num}/{den} of {whole}?",ans,rng))
            elif kind=="equiv":
                q.append(make_mcq(f"Which fraction is equivalent to {num}/{den}?",f"{num*2}/{den*2}",[f"{num+1}/{den+1}",f"{num}/{den*2}",f"{num*2}/{den}"],rng))
            else:
                other=max(1,num-1)
                ans=f"{num}/{den}" if num>other else f"{other}/{den}"
                q.append(make_mcq(f"Which is greater: {num}/{den} or {other}/{den}?",ans,[f"{other}/{den}","They are equal","Cannot tell"],rng))
    elif topic == "Measurement":
        for _ in range(10):
            kind=rng.choice(["length","mass","capacity","perimeter"])
            if kind=="length":
                cm=rng.randint(100,900); q.append(make_mcq(f"How many metres and centimetres are in {cm} cm?",f"{cm//100} m {cm%100} cm",[f"{cm//10} m {cm%10} cm",f"{cm} m",f"{cm//100} m"],rng))
            elif kind=="mass":
                kg=rng.randint(1,5); q.append(make_mcq(f"How many grams are in {kg} kg?",f"{kg*1000} g",[f"{kg*100} g",f"{kg*10} g",f"{kg} g"],rng))
            elif kind=="capacity":
                l=rng.randint(1,5); q.append(make_mcq(f"How many millilitres are in {l} litre{'s' if l>1 else ''}?",f"{l*1000} ml",[f"{l*100} ml",f"{l*10} ml",f"{l} ml"],rng))
            else:
                a,b=rng.randint(2,12),rng.randint(2,12); q.append(_num_mcq(f"A rectangle is {a} cm by {b} cm. What is its perimeter in cm?",2*(a+b),rng,spread=2))
    elif topic == "Geometry":
        facts=[("How many right angles make a full turn?","4",["1","2","3"]),("Which angle is smaller than a right angle?","acute",["obtuse","reflex","straight"]),("Which 3D shape has 2 circular faces?","cylinder",["cone","sphere","cube"]),("How many faces does a cube have?","6",["4","8","12"])]
        for i in range(10):
            stem,ans,wrong=facts[(i+index)%len(facts)]; q.append(make_mcq(stem,ans,wrong,rng))
    elif topic == "Time":
        for _ in range(10):
            hour=rng.randint(1,10); mins=rng.choice([5,10,15,20,25,30,35,40,45,50,55])
            add=rng.choice([5,10,15,20]); total=hour*60+mins+add
            ans=f"{(total//60-1)%12+1}:{total%60:02d}"
            q.append(make_mcq(f"The time is {hour}:{mins:02d}. What time is it {add} minutes later?",ans,[f"{hour}:{(mins-add)%60:02d}",f"{hour}:{mins:02d}",f"{(hour%12)+1}:{mins:02d}"],rng))
    elif topic == "Money":
        for _ in range(10):
            cost=rng.randint(120,850); paid=((cost+99)//100)*100; change=paid-cost
            q.append(make_mcq(f"An item costs £{cost/100:.2f}. You pay £{paid/100:.2f}. How much change do you get?",f"£{change/100:.2f}",[f"£{cost/100:.2f}",f"£{paid/100:.2f}",f"£{(change+100)/100:.2f}"],rng))
    elif topic == "Place Value":
        for _ in range(10):
            n=rng.randint(100,999); place=rng.choice(["hundreds","tens","ones"])
            digit={"hundreds":n//100,"tens":n//10%10,"ones":n%10}[place]
            q.append(make_mcq(f"What is the {place} digit in {n}?",digit,[(digit+1)%10,(digit+2)%10,n],rng))
    elif topic == "Number Bonds":
        for _ in range(10):
            target=rng.choice([20,50,100]); a=rng.randint(0,target); q.append(_num_mcq(f"What number must be added to {a} to make {target}?",target-a,rng,spread=10))
    elif topic == "Problem Solving":
        for _ in range(10):
            boxes=rng.randint(2,8); each=rng.randint(3,12); used=rng.randint(0,boxes*each//2)
            q.append(_num_mcq(f"There are {boxes} boxes with {each} pencils in each. {used} pencils are used. How many pencils are left?",boxes*each-used,rng,spread=boxes))
    else: raise ValueError(f"Unknown Year 3 Maths topic: {topic}")
    return render_homework("Maths",3,topic,index,q)


def _year4(topic: str, index: int):
    rng=stable_random("Maths",4,topic,index); q=[]
    if topic=="Multiplication and Division":
        for _ in range(10):
            a=rng.randint(2,12); b=rng.randint(2,12)
            if rng.random()<0.6:q.append(_num_mcq(f"Calculate {a} × {b}.",a*b,rng,spread=a))
            else:q.append(_num_mcq(f"Calculate {a*b} ÷ {a}.",b,rng))
    elif topic=="Fractions and Decimals":
        for _ in range(10):
            kind=rng.choice(["tenths","hundredths","equiv","add"])
            if kind=="tenths":
                n=rng.randint(1,9);q.append(make_mcq(f"Write {n}/10 as a decimal.",f"0.{n}",[f"{n}.0",f"0.0{n}",str(n)],rng))
            elif kind=="hundredths":
                n=rng.randint(1,99);q.append(make_mcq(f"Write {n}/100 as a decimal.",f"0.{n:02d}",[f"0.{n}",f"{n/10:g}",str(n)],rng))
            elif kind=="equiv":
                n=rng.randint(1,9);q.append(make_mcq(f"Which fraction is equal to {n}/10?",f"{n*10}/100",[f"{n}/100",f"{n+1}/10",f"10/{n}"],rng))
            else:
                a=rng.randint(1,7);b=rng.randint(1,8-a);q.append(make_mcq(f"What is {a}/10 + {b}/10?",f"{a+b}/10",[f"{a+b}/20",f"{abs(a-b)}/10",f"{a*b}/10"],rng))
    elif topic=="Measurement and Conversion":
        conversions=[("km","m",1000),("m","cm",100),("kg","g",1000),("l","ml",1000)]
        for _ in range(10):
            u1,u2,f=rng.choice(conversions); n=rng.randint(1,9); q.append(make_mcq(f"Convert {n} {u1} to {u2}.",f"{n*f} {u2}",[f"{n*10} {u2}",f"{n*100} {u2}",f"{n} {u2}"],rng))
    elif topic=="Properties of Shapes and Angles":
        facts=[("Which angle is greater than 90° but less than 180°?","obtuse",["acute","right","reflex"]),("How many lines of symmetry does a rectangle have?","2",["1","3","4"]),("What is the total angle in a half turn?","180°",["90°","270°","360°"]),("Which quadrilateral has exactly one pair of parallel sides?","trapezium",["square","rhombus","kite"])]
        for i in range(10): stem,ans,wrong=facts[(i+index)%len(facts)];q.append(make_mcq(stem,ans,wrong,rng))
    elif topic=="Position and Direction (Coordinates)":
        for _ in range(10):
            x,y=rng.randint(0,8),rng.randint(0,8); dx,dy=rng.choice([(1,0),(-1,0),(0,1),(0,-1)])
            nx,ny=max(0,x+dx),max(0,y+dy)
            direction="right" if dx==1 else "left" if dx==-1 else "up" if dy==1 else "down"
            q.append(make_mcq(f"A point starts at ({x}, {y}) and moves one square {direction}. What are its new coordinates?",f"({nx}, {ny})",[f"({y}, {x})",f"({x}, {y})",f"({nx+1}, {ny+1})"],rng))
    elif topic=="Time and Duration":
        for _ in range(10):
            h=rng.randint(8,18);m=rng.choice([0,15,30,45]);duration=rng.choice([15,30,45,60,90]); total=h*60+m+duration
            ans=f"{total//60:02d}:{total%60:02d}"
            q.append(make_mcq(f"A lesson starts at {h:02d}:{m:02d} and lasts {duration} minutes. When does it finish?",ans,[f"{h:02d}:{(m+duration)%60:02d}",f"{(total//60+1):02d}:{total%60:02d}",f"{h:02d}:{m:02d}"],rng))
    elif topic=="Money and Budgeting":
        for _ in range(10):
            budget=rng.choice([1000,1500,2000]); a=rng.randint(100,700);b=rng.randint(100,700); left=budget-a-b
            q.append(make_mcq(f"You have £{budget/100:.2f}. You spend £{a/100:.2f} and £{b/100:.2f}. How much is left?",f"£{left/100:.2f}",[f"£{(budget-a)/100:.2f}",f"£{(a+b)/100:.2f}",f"£{budget/100:.2f}"],rng))
    elif topic=="Place Value and Rounding":
        for _ in range(10):
            n=rng.randint(1000,9999); unit=rng.choice([10,100,1000]); ans=round(n/unit)*unit
            q.append(make_mcq(f"Round {n} to the nearest {unit}.",ans,[ans-unit,ans+unit,n],rng))
    elif topic=="Addition and Subtraction (4-digit)":
        for _ in range(10):
            a,b=rng.randint(1000,8000),rng.randint(500,3000)
            if rng.random()<0.5:q.append(_num_mcq(f"Calculate {a} + {b}.",a+b,rng,spread=100))
            else:
                if b>a:a,b=b,a
                q.append(_num_mcq(f"Calculate {a} - {b}.",a-b,rng,spread=100))
    elif topic=="Area and Perimeter":
        for _ in range(10):
            a,b=rng.randint(2,15),rng.randint(2,15)
            if rng.random()<0.5:q.append(_num_mcq(f"What is the area of a rectangle {a} cm by {b} cm?",a*b,rng,spread=a))
            else:q.append(_num_mcq(f"What is the perimeter of a rectangle {a} cm by {b} cm?",2*(a+b),rng,spread=2))
    elif topic=="Statistics (Bar Charts and Time Graphs)":
        for _ in range(10):
            mon,tue,wed=[rng.randint(5,30) for _ in range(3)]
            kind=rng.choice(["total","difference","greatest"])
            if kind=="total":q.append(_num_mcq(f"A chart shows Monday {mon}, Tuesday {tue}, Wednesday {wed}. What is the total?",mon+tue+wed,rng,spread=5))
            elif kind=="difference":q.append(_num_mcq(f"A chart shows Monday {mon} and Tuesday {tue}. What is the difference?",abs(mon-tue),rng,spread=5))
            else:
                values={"Monday":mon,"Tuesday":tue,"Wednesday":wed};ans=max(values,key=values.get);q.append(make_mcq(f"A chart shows Monday {mon}, Tuesday {tue}, Wednesday {wed}. Which day has the greatest value?",ans,[d for d in values if d!=ans]+["They are equal"],rng))
    else: raise ValueError(f"Unknown Year 4 Maths topic: {topic}")
    return render_homework("Maths",4,topic,index,q)


def _year5(topic: str, index: int):
    rng=stable_random("Maths",5,topic,index); q=[]
    if topic=="Large Numbers and Place Value":
        for _ in range(10):
            n=rng.randint(10000,999999); place=rng.choice([10,100,1000,10000]);ans=round(n/place)*place
            q.append(make_mcq(f"Round {n:,} to the nearest {place:,}.",f"{ans:,}",[f"{ans-place:,}",f"{ans+place:,}",f"{n:,}"],rng))
    elif topic=="Multiplication (4-digit by 2-digit)":
        for _ in range(10):
            a=rng.randint(1000,4999);b=rng.randint(11,29);q.append(_num_mcq(f"Calculate {a} × {b}.",a*b,rng,spread=b))
    elif topic=="Division and Long Division":
        for _ in range(10):
            divisor=rng.randint(2,12);answer=rng.randint(100,999);q.append(_num_mcq(f"Calculate {answer*divisor} ÷ {divisor}.",answer,rng,spread=10))
    elif topic=="Prime Numbers, Factors, Squares and Cubes":
        primes=[2,3,5,7,11,13,17,19,23,29]; composites=[4,6,8,9,10,12,14,15,16,18]
        for _ in range(10):
            kind=rng.choice(["prime","factor","square","cube"])
            if kind=="prime":
                ans=rng.choice(primes);q.append(make_mcq("Which number is prime?",ans,rng.sample(composites,3),rng))
            elif kind=="factor":
                n=rng.choice([12,18,24,30,36,40]);ans=rng.choice([d for d in range(2,n+1) if n%d==0]);wrong=[x for x in range(2,n) if n%x!=0][:8];q.append(make_mcq(f"Which number is a factor of {n}?",ans,wrong,rng))
            elif kind=="square":
                n=rng.randint(2,12);q.append(_num_mcq(f"What is {n} squared?",n*n,rng,spread=n))
            else:
                n=rng.randint(2,6);q.append(_num_mcq(f"What is {n} cubed?",n**3,rng,spread=n))
    elif topic=="Fractions, Decimals and Percentages":
        equivalents=[("1/2","0.5","50%"),("1/4","0.25","25%"),("3/4","0.75","75%"),("1/10","0.1","10%"),("1/5","0.2","20%")]
        for _ in range(10):
            frac,dec,pct=rng.choice(equivalents);kind=rng.choice(["decimal","percent","fraction"])
            if kind=="decimal":q.append(make_mcq(f"Write {frac} as a decimal.",dec,["0.05","0.2","1.5"],rng))
            elif kind=="percent":q.append(make_mcq(f"Write {frac} as a percentage.",pct,["5%","20%","100%"],rng))
            else:q.append(make_mcq(f"Which fraction is equal to {dec}?",frac,["1/10","2/3","3/5"],rng))
    elif topic=="Properties of Shapes: Angles":
        for _ in range(10):
            a=rng.randint(20,160);b=180-a;q.append(make_mcq(f"Two angles on a straight line total 180°. One is {a}°. What is the other?",f"{b}°",[f"{180+a}°",f"{90-a if a<90 else a-90}°",f"{a}°"],rng))
    elif topic=="Position and Direction (Reflection and Translation)":
        for _ in range(10):
            x,y=rng.randint(1,8),rng.randint(1,8);kind=rng.choice(["reflect_y","translate"])
            if kind=="reflect_y":q.append(make_mcq(f"Reflect ({x}, {y}) in the y-axis. What is the image?",f"(-{x}, {y})",[f"({x}, -{y})",f"(-{x}, -{y})",f"({y}, {x})"],rng))
            else:
                dx,dy=rng.randint(-3,3),rng.randint(-3,3);q.append(make_mcq(f"Translate ({x}, {y}) by ({dx}, {dy}). What is the image?",f"({x+dx}, {y+dy})",[f"({x-dx}, {y-dy})",f"({x+dy}, {y+dx})",f"({x}, {y})"],rng))
    elif topic=="Measurement and Conversion":
        for _ in range(10):
            kind=rng.choice(["km_m","m_cm","kg_g","l_ml","time"])
            n=rng.randint(1,20)
            if kind=="km_m":q.append(make_mcq(f"Convert {n} km to m.",f"{n*1000} m",[f"{n*100} m",f"{n*10} m",f"{n} m"],rng))
            elif kind=="m_cm":q.append(make_mcq(f"Convert {n} m to cm.",f"{n*100} cm",[f"{n*10} cm",f"{n*1000} cm",f"{n} cm"],rng))
            elif kind=="kg_g":q.append(make_mcq(f"Convert {n} kg to g.",f"{n*1000} g",[f"{n*100} g",f"{n*10} g",f"{n} g"],rng))
            elif kind=="l_ml":q.append(make_mcq(f"Convert {n} litres to ml.",f"{n*1000} ml",[f"{n*100} ml",f"{n*10} ml",f"{n} ml"],rng))
            else:q.append(make_mcq(f"How many minutes are in {n} hours?",f"{n*60} minutes",[f"{n*100} minutes",f"{n*30} minutes",f"{n} minutes"],rng))
    elif topic=="Area and Volume":
        for _ in range(10):
            l,w,h=rng.randint(2,10),rng.randint(2,10),rng.randint(2,8);kind=rng.choice(["area","volume"])
            if kind=="area":q.append(_num_mcq(f"What is the area of a rectangle {l} cm by {w} cm?",l*w,rng,spread=l))
            else:q.append(_num_mcq(f"What is the volume of a cuboid {l} cm × {w} cm × {h} cm?",l*w*h,rng,spread=h))
    elif topic=="Statistics (Line Graphs and Tables)":
        for _ in range(10):
            vals=[rng.randint(10,80) for _ in range(4)];kind=rng.choice(["total","mean","difference"])
            if kind=="total":q.append(_num_mcq(f"A table contains {vals}. What is the total?",sum(vals),rng,spread=10))
            elif kind=="mean":
                # Make the mean whole by adjusting the final value.
                vals[-1]+=(-sum(vals))%4;q.append(_num_mcq(f"A table contains {vals}. What is the mean?",sum(vals)//4,rng,spread=5))
            else:q.append(_num_mcq(f"A line graph rises from {vals[0]} to {vals[1]}. What is the change?",vals[1]-vals[0],rng,spread=5))
    elif topic=="Problem Solving":
        for _ in range(10):
            packs=rng.randint(10,40);each=rng.randint(12,30);shared=rng.randint(2,10);q.append(_num_mcq(f"There are {packs} packs of {each} cards. They are shared equally among {shared} classes. How many cards does each class get?",packs*each//shared if (packs*each)%shared==0 else packs*each,rng,spread=shared))
            # Ensure the generated division is exact; replace non-exact with a multiplication total question.
            if (packs*each)%shared!=0:q[-1]=_num_mcq(f"There are {packs} packs of {each} cards. How many cards are there altogether?",packs*each,rng,spread=each)
    else: raise ValueError(f"Unknown Year 5 Maths topic: {topic}")
    return render_homework("Maths",5,topic,index,q)


def _year6(topic: str, index: int):
    rng=stable_random("Maths",6,topic,index);q=[]
    if topic=="Advanced Fractions and Decimals":
        for _ in range(10):
            den=rng.choice([4,5,8,10,20]);a,b=rng.randint(1,den-1),rng.randint(1,den-1)
            if a+b<den:
                ans=Fraction(a+b,den);q.append(make_mcq(f"Calculate {a}/{den} + {b}/{den}. Give the simplest fraction.",f"{ans.numerator}/{ans.denominator}",[f"{a+b}/{den*2}",f"{abs(a-b)}/{den}",f"{a*b}/{den}"],rng))
            else:
                n=rng.randint(1,999);q.append(make_mcq(f"Round {n/100:.2f} to one decimal place.",f"{round(n/100,1):.1f}",[f"{n/100:.2f}",f"{round(n/100):.1f}",f"{n/10:.1f}"],rng))
    elif topic=="Multiplication and Division (Large Numbers)":
        for _ in range(10):
            if rng.random()<0.5:
                a=rng.randint(1000,9999);b=rng.randint(12,99);q.append(_num_mcq(f"Calculate {a} × {b}.",a*b,rng,spread=b))
            else:
                divisor=rng.randint(2,12);ans=rng.randint(1000,5000);q.append(_num_mcq(f"Calculate {ans*divisor} ÷ {divisor}.",ans,rng,spread=100))
    elif topic=="Percentages and Ratio":
        for _ in range(10):
            kind=rng.choice(["percent","ratio"])
            if kind=="percent":
                pct=rng.choice([10,20,25,50,75]);n=rng.choice([40,80,100,120,200,400]);ans=n*pct//100;q.append(_num_mcq(f"What is {pct}% of {n}?",ans,rng,spread=10))
            else:
                a,b=rng.randint(1,5),rng.randint(1,5);scale=rng.randint(2,10);q.append(make_mcq(f"A ratio is {a}:{b}. If the first part is {a*scale}, what is the second part?",b*scale,[a*scale,(a+b)*scale,scale],rng))
    elif topic=="Algebra and Equations":
        for _ in range(10):
            x=rng.randint(2,30);a=rng.randint(2,12);kind=rng.choice(["add","multiply","sequence"])
            if kind=="add":q.append(_num_mcq(f"Solve x + {a} = {x+a}.",x,rng))
            elif kind=="multiply":q.append(_num_mcq(f"Solve {a}x = {a*x}.",x,rng))
            else:
                start=rng.randint(1,20);step=rng.randint(2,9);q.append(_num_mcq(f"The sequence is {start}, {start+step}, {start+2*step}, __. What is the missing term?",start+3*step,rng,spread=step))
    elif topic=="Geometry (Transformations)":
        for _ in range(10):
            x,y=rng.randint(-8,8),rng.randint(-8,8);kind=rng.choice(["reflect_x","reflect_y","rotate"])
            if kind=="reflect_x":q.append(make_mcq(f"Reflect ({x}, {y}) in the x-axis.",f"({x}, {-y})",[f"({-x}, {y})",f"({-x}, {-y})",f"({y}, {x})"],rng))
            elif kind=="reflect_y":q.append(make_mcq(f"Reflect ({x}, {y}) in the y-axis.",f"({-x}, {y})",[f"({x}, {-y})",f"({-x}, {-y})",f"({y}, {x})"],rng))
            else:q.append(make_mcq(f"Rotate ({x}, {y}) 180° about the origin.",f"({-x}, {-y})",[f"({x}, {-y})",f"({-x}, {y})",f"({y}, {x})"],rng))
    elif topic=="Properties of Shapes (Circles, Angles and Nets)":
        facts=[("What is the diameter of a circle with radius 6 cm?","12 cm",["3 cm","6 cm","36 cm"]),("What is the radius of a circle with diameter 18 cm?","9 cm",["6 cm","18 cm","36 cm"]),("What is the sum of angles in a triangle?","180°",["90°","270°","360°"]),("How many square faces are in a cube net?","6",["4","8","12"])]
        for i in range(10):stem,ans,wrong=facts[(i+index)%len(facts)];q.append(make_mcq(stem,ans,wrong,rng))
    elif topic=="Area, Perimeter and Volume":
        for _ in range(10):
            l,w,h=rng.randint(2,15),rng.randint(2,12),rng.randint(2,10);kind=rng.choice(["area","perimeter","volume","triangle"])
            if kind=="area":q.append(_num_mcq(f"Find the area of a rectangle {l} cm by {w} cm.",l*w,rng,spread=l))
            elif kind=="perimeter":q.append(_num_mcq(f"Find the perimeter of a rectangle {l} cm by {w} cm.",2*(l+w),rng,spread=2))
            elif kind=="volume":q.append(_num_mcq(f"Find the volume of a cuboid {l} cm × {w} cm × {h} cm.",l*w*h,rng,spread=h))
            else:
                base=2*rng.randint(2,10);height=rng.randint(2,12);q.append(_num_mcq(f"Find the area of a triangle with base {base} cm and height {height} cm.",base*height//2,rng,spread=height))
    elif topic=="Statistics and Data Interpretation":
        for _ in range(10):
            vals=[rng.randint(5,50) for _ in range(4)];vals[-1]+=(-sum(vals))%4;kind=rng.choice(["mean","range","total"])
            if kind=="mean":q.append(_num_mcq(f"Find the mean of {vals}.",sum(vals)//4,rng,spread=5))
            elif kind=="range":q.append(_num_mcq(f"Find the range of {vals}.",max(vals)-min(vals),rng,spread=5))
            else:q.append(_num_mcq(f"Find the total of {vals}.",sum(vals),rng,spread=10))
    elif topic=="Negative Numbers":
        for _ in range(10):
            a,b=rng.randint(-20,10),rng.randint(-10,20);kind=rng.choice(["add","difference","compare"])
            if kind=="add":q.append(_num_mcq(f"Calculate {a} + {b}.",a+b,rng,spread=5))
            elif kind=="difference":q.append(_num_mcq(f"What is the difference between {a} and {b}?",abs(a-b),rng,spread=5))
            else:
                ans=str(max(a,b));q.append(make_mcq(f"Which number is greater: {a} or {b}?",ans,[str(min(a,b)),"They are equal","Cannot tell"],rng))
    elif topic in {"SATs Preparation","Complex Problem Solving"}:
        for _ in range(10):
            kind=rng.choice(["multi","fraction","percent","ratio"])
            if kind=="multi":
                packs,each,used=rng.randint(8,30),rng.randint(12,40),rng.randint(20,100);q.append(_num_mcq(f"A school buys {packs} packs of {each} books and gives away {used}. How many remain?",packs*each-used,rng,spread=10))
            elif kind=="fraction":
                total=rng.choice([60,80,100,120,200]);den=rng.choice([4,5,10]);num=rng.randint(1,den-1);q.append(_num_mcq(f"What is {num}/{den} of {total}?",total*num//den,rng,spread=10))
            elif kind=="percent":
                total=rng.choice([80,100,120,200,400]);pct=rng.choice([10,20,25,50,75]);q.append(_num_mcq(f"A price of £{total} is reduced by {pct}%. What is the reduction in pounds?",total*pct//100,rng,spread=10))
            else:
                a,b=rng.randint(1,5),rng.randint(1,5);total=(a+b)*rng.randint(3,15);q.append(_num_mcq(f"Red and blue counters are in the ratio {a}:{b}. There are {total} counters. How many are red?",total*a//(a+b),rng,spread=5))
    else: raise ValueError(f"Unknown Year 6 Maths topic: {topic}")
    return render_homework("Maths",6,topic,index,q)


def generate_math_homework(year_group: int, topic: str, index: int) -> tuple[str, list[str]]:
    generators={1:_year1,2:_year2,3:_year3,4:_year4,5:_year5,6:_year6}
    if year_group not in generators: raise ValueError("year_group must be between 1 and 6")
    return generators[year_group](topic,index)


def generate_year_homework(year_group: int, count: int = 500) -> list:
    topics=MATH_TOPICS_BY_YEAR.get(year_group,[])
    if not topics:return []
    config=YEAR_CONFIG[year_group];batch=[]
    for i in range(1,count+1):
        topic=topics[(i-1)%len(topics)]
        content,answers=generate_math_homework(year_group,topic,i)
        batch.append(build_batch_item(content=content,answers=answers,year_group=year_group,subject="Maths",topic=topic,homework_minutes=config["homework_minutes"],key_stage=config["key_stage"],doc_id=f"maths_y{year_group}_{i:04d}"))
        if i%100==0: print(f"  Generated {i}/{count}")
    return batch


def main():
    parser=argparse.ArgumentParser(description="Generate UK primary Maths homework into the configured RAG store.")
    parser.add_argument("--year",type=int,action="append",choices=range(1,7))
    parser.add_argument("--count",type=int,default=None)
    parser.add_argument("--allow-sqlite",action="store_true")
    args=parser.parse_args()
    store=get_homework_rag_store();print(f"RAG target: {store.store.database_target}")
    if not store.store.is_postgres and not args.allow_sqlite:
        raise RuntimeError("Maths ingestion is not connected to PostgreSQL/pgvector. Set PGVECTOR_DATABASE_URL or DATABASE_URL, or pass --allow-sqlite for local development.")
    years=args.year or list(range(1,7))
    for year in years:
        expected=args.count if args.count is not None else HOMEWORK_COUNT[year]
        existing=count_year_homework(store,year,"Maths")
        if existing>=expected:
            print(f"Year {year}: complete ({existing}/{expected})");continue
        data=generate_year_homework(year,expected)
        added=add_homework_in_batches(store,data)
        print(f"Year {year}: added {added}; target {len(data)}")
    get_rag_stats(store)


if __name__=="__main__":
    main()
