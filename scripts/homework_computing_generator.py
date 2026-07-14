#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
检查各年级Computing作业是否存在，缺失则生成 500 份作业并添加到 RAG 存储
支持 Year 1-6 所有年级

Curriculum alignment note (Years 1-6)
--------------------------------------
Computing topics below have been checked against the statutory National Curriculum
in England: Computing programmes of study (DfE, 2014, updated 2021) -
https://www.gov.uk/government/publications/national-curriculum-in-england-computing-programmes-of-study

The computing curriculum focuses on three main pillars:
1. Computer Science — computational thinking, algorithms, programming
2. Information Technology — digital tools, applications, productivity
3. Digital Literacy — online safety, responsible use, digital citizenship

Each year group builds on previous knowledge with increasing complexity:
Year 1: Basic input/output, sequences, algorithms
Year 2: Programs, debugging, digital safety
Year 3: Programming (text), algorithms, networks
Year 4: Programming (loops, conditions), file handling, cybersecurity
Year 5: Programming (advanced), data representation, online safety
Year 6: Programming (complex), network concepts, digital ethics

All questions are original and curriculum-aligned, using only free public sources
(no proprietary textbooks or materials reproduced).
"""

import sys
import os
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.homework_rag import get_homework_rag_store
from scripts.homework_generator_utils import count_year_homework, add_homework_in_batches, get_rag_stats

os.environ["TOKENIZERS_PARALLELISM"] = "false"

HOMEWORK_COUNT = {1: 100, 2: 200, 3: 300, 4: 400, 5: 500, 6: 600}

# 各年级Computing主题（英国小学课程）
COMPUTING_TOPICS_BY_YEAR = {
    1: [
        "Introduction to computers",
        "Input and output devices",
        "Simple sequences and commands",
        "Digital safety online",
        "Basic algorithms",
        "Programmable toys and robots",
        "Working with digital tools",
        "Saving and opening files",
    ],
    2: [
        "Programs and programming",
        "Debugging programs",
        "Sequences and patterns",
        "Simple algorithms",
        "Digital citizenship",
        "Working with images and text",
        "Using applications",
        "Online safety and privacy",
    ],
    3: [
        "Programming (Scratch or similar)",
        "Loops and repetition",
        "Debugging and testing",
        "Algorithms and problem-solving",
        "Digital literacy",
        "Networks and the internet",
        "File management",
        "Hardware and networks",
    ],
    4: [
        "Programming (loops and conditions)",
        "Variables and data types",
        "Boolean logic",
        "Debugging techniques",
        "File handling and storage",
        "Cybersecurity basics",
        "Networks and internet",
        "Computer systems and components",
    ],
    5: [
        "Programming (complex programs)",
        "Conditional statements and logic",
        "Subroutines and functions",
        "Data representation",
        "Cybersecurity and encryption",
        "Computer networks",
        "Online privacy and safety",
        "IT applications and systems",
    ],
    6: [
        "Programming (multi-step algorithms)",
        "Object-oriented thinking",
        "Advanced debugging",
        "Data encoding and representation",
        "Network architecture",
        "Digital ethics and responsibility",
        "Cybersecurity and protection",
        "Emerging technologies",
    ],
}


def generate_computing_homework(year_group: int, topic: str, index: int) -> tuple:
    """根据年级、主题生成Computing作业，返回 (content, correct_answers)"""

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
    """Year 1 Computing作业（5-6 岁），返回 (content, correct_answers)"""
    if topic == "Introduction to computers":
        questions = [
            "1. What is a computer?",
            "2. Name 3 things a computer can do.",
            "3. What is a screen used for?",
            "4. What is a keyboard used for?",
            "5. What is a mouse used for?",
            "6. Can you use a computer to play games?",
            "7. Can you use a computer to watch videos?",
            "8. Name a computer you use at home or school.",
            "9. What does a computer need to work?",
            "10. Draw a picture of a computer.",
        ]
        answers = [
            "a machine that processes information",
            "student's own answer (e.g., play games, watch videos, write stories)",
            "to show information and pictures",
            "to type and give commands to computer",
            "to point and click on things",
            "yes",
            "yes",
            "student's own answer (e.g., laptop, tablet, desktop, classroom computer)",
            "electricity/power",
            "drawing (with screen, keyboard, mouse)",
        ]
    elif topic == "Input and output devices":
        questions = [
            "1. What is an input device?",
            "2. What is an output device?",
            "3. Name 3 input devices.",
            "4. Name 3 output devices.",
            "5. Is a keyboard an input or output device?",
            "6. Is a screen an input or output device?",
            "7. Is a printer an input or output device?",
            "8. What do you use to listen to sound from a computer?",
            "9. What do you use to see pictures on a computer?",
            "10. What do you use to tell a computer what to do?",
        ]
        answers = [
            "a device that sends information to a computer",
            "a device that shows information from a computer",
            "student's own answer (keyboard, mouse, microphone, camera, scanner)",
            "student's own answer (screen, printer, speaker, headphones)",
            "input",
            "output",
            "output",
            "speakers or headphones",
            "a screen (monitor)",
            "keyboard, mouse, or other input device",
        ]
    elif topic == "Simple sequences and commands":
        questions = [
            "1. What is a sequence?",
            "2. What is a command?",
            "3. Give an example of a sequence in your daily life.",
            "4. List steps to make a sandwich.",
            "5. Do sequences always happen in the same order?",
            "6. What happens if you follow steps in the wrong order?",
            "7. Can a computer follow sequences?",
            "8. How does a computer know what to do?",
            "9. What happens if a computer gets the wrong command?",
            "10. Write a sequence: getting ready for school.",
        ]
        answers = [
            "a set of steps done in order",
            "an instruction that tells a computer what to do",
            "student's own answer (e.g., eating breakfast, getting dressed)",
            "student's own answer (e.g., get bread → add filling → close)",
            "yes (usually)",
            "it might not work correctly",
            "yes",
            "through commands (instructions)",
            "it does what the command says (it might produce wrong output)",
            "student's own sequence (wake up → wash → get dressed → eat → go to school)",
        ]
    elif topic == "Digital safety online":
        questions = [
            "1. What is digital safety?",
            "2. Is it safe to tell strangers personal information online?",
            "3. What should you do if someone online makes you uncomfortable?",
            "4. Should you click on unknown links?",
            "5. Why should you not share your password?",
            "6. Who should help you stay safe online?",
            "7. Is it safe to meet someone from the internet in real life?",
            "8. What should you do if you see something that scares you online?",
            "9. How can you protect your privacy online?",
            "10. Name 3 rules for staying safe online.",
        ]
        answers = [
            "practicing safe behavior when using the internet",
            "no (never)",
            "tell a trusted adult immediately",
            "no (they could contain viruses)",
            "so others cannot access your accounts",
            "parents, teachers, or trusted adults",
            "no (it could be dangerous)",
            "tell a trusted adult immediately",
            "don't share personal information, use strong passwords, be careful online",
            "student's own answer (don't share info, don't click links, tell adults)",
        ]
    elif topic == "Basic algorithms":
        questions = [
            "1. What is an algorithm?",
            "2. Give an example of an algorithm.",
            "3. Do algorithms need to be in order?",
            "4. Can an algorithm be wrong?",
            "5. What is a step-by-step instruction?",
            "6. How do you test if an algorithm works?",
            "7. Write steps to brush your teeth.",
            "8. Can computers follow algorithms?",
            "9. What happens if an algorithm has a mistake?",
            "10. Is cooking a recipe an algorithm?",
        ]
        answers = [
            "a set of step-by-step instructions to solve a problem",
            "student's own answer (recipe, directions, instructions)",
            "yes (order matters)",
            "yes (if steps are wrong or missing)",
            "a list of steps that must be followed in order",
            "by following the steps and seeing if you get the right result",
            "student's own answer (wet toothbrush → apply paste → brush → rinse)",
            "yes",
            "it doesn't work correctly",
            "yes (it's a series of steps to make food)",
        ]
    elif topic == "Programmable toys and robots":
        questions = [
            "1. What is a robot?",
            "2. What is a programmable toy?",
            "3. Can a robot do exactly what you tell it to do?",
            "4. What do you need to program a robot?",
            "5. What is an instruction for a robot?",
            "6. Can a robot make its own decisions?",
            "7. Name a robot or programmable toy you know.",
            "8. How do you tell a robot to move forward?",
            "9. Can robots learn?",
            "10. What can a programmable toy do?",
        ]
        answers = [
            "a machine that can be programmed to perform tasks",
            "a toy that you can give instructions to",
            "yes (if programmed correctly)",
            "instructions (a program)",
            "a command that tells the robot what to do (e.g., 'move forward')",
            "no (it only follows its program)",
            "student's own answer (e.g., Bee-Bot, Cubetto, toy robot)",
            "send a 'forward' command",
            "not in the traditional sense (only what they're programmed to do)",
            "move, change direction, make sounds, light up",
        ]
    elif topic == "Working with digital tools":
        questions = [
            "1. What is a digital tool?",
            "2. Name 5 digital tools you use.",
            "3. What can you do with a word processor?",
            "4. What can you do with painting software?",
            "5. Can you save your work on a computer?",
            "6. Why would you save a file?",
            "7. How do you open a saved file?",
            "8. Can you undo a mistake in digital tools?",
            "9. What is formatting text?",
            "10. Can you share digital files with others?",
        ]
        answers = [
            "a program or app you use to complete tasks",
            "student's own answer (word processor, email, paint, web browser, calculator)",
            "write and edit text, format, save, print",
            "draw, paint, add colors, create pictures",
            "yes",
            "so you don't lose your work",
            "open file menu or browse to location and click",
            "yes (undo button or Ctrl+Z)",
            "changing appearance (bold, color, size, font)",
            "yes (email, cloud storage, USB drive)",
        ]
    elif topic == "Saving and opening files":
        questions = [
            "1. What does it mean to save a file?",
            "2. Why is it important to save your work?",
            "3. How often should you save?",
            "4. What happens if you don't save?",
            "5. Where can files be saved?",
            "6. What is a file name?",
            "7. Should file names be helpful?",
            "8. How do you open a saved file?",
            "9. Can you save a file with a new name?",
            "10. What is a folder used for?",
        ]
        answers = [
            "storing your work so it doesn't get lost",
            "so you don't lose your work if computer shuts down",
            "regularly (every few minutes)",
            "you lose your work",
            "hard drive, USB drive, cloud storage",
            "the name you give a file",
            "yes (so you remember what it contains)",
            "use File menu → Open or browse and double-click",
            "yes (File → Save As)",
            "to organize and group files together",
        ]
    else:
        questions = [f"{i + 1}. Year 1 Computing practice question {i + 1}" for i in range(10)]
        answers = [f"answer {i + 1}" for i in range(10)]

    content = f"Computing Homework - Year 1 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year2_homework(topic: str, index: int) -> tuple:
    """Year 2 Computing作业（6-7 岁），返回 (content, correct_answers)"""
    if topic == "Programs and programming":
        questions = [
            "1. What is a program?",
            "2. What is programming?",
            "3. Can a computer do anything without a program?",
            "4. Who writes programs?",
            "5. What language do programmers use?",
            "6. Name 3 programs you use at school.",
            "7. Can you see the code that makes a program work?",
            "8. What does a program need to work?",
            "9. Can programs have bugs?",
            "10. Is a game a program?",
        ]
        answers = [
            "a set of instructions that tells a computer what to do",
            "writing instructions for computers to follow",
            "no (it needs a program to do anything useful)",
            "programmers or software developers",
            "programming languages (Python, Java, C++, Scratch, etc.)",
            "student's own answer (Word, Paint, Email, web browser)",
            "usually no (it's hidden)",
            "input (code/instructions) and processing",
            "yes (bugs are errors in code)",
            "yes",
        ]
    elif topic == "Debugging programs":
        questions = [
            "1. What is a bug in a program?",
            "2. What is debugging?",
            "3. How do you find a bug?",
            "4. How do you fix a bug?",
            "5. Can computers have bugs?",
            "6. Why are bugs a problem?",
            "7. Do all programs have bugs?",
            "8. How do you test a program?",
            "9. What should you do if a program doesn't work?",
            "10. Is it easy to find every bug?",
        ]
        answers = [
            "an error or mistake in a program",
            "finding and fixing errors in code",
            "by testing the program and looking for mistakes",
            "by changing the code",
            "yes",
            "they make programs not work correctly",
            "most do at some point",
            "by running it and checking if it does what it should",
            "check the code, look for mistakes, test again",
            "no (some bugs are hard to find)",
        ]
    elif topic == "Sequences and patterns":
        questions = [
            "1. What is a sequence in computing?",
            "2. What is a pattern?",
            "3. Do computers follow sequences?",
            "4. Give an example of a sequence.",
            "5. Can you predict a pattern?",
            "6. Write a sequence: making tea.",
            "7. What happens if sequence steps are wrong?",
            "8. Are all sequences in the same order?",
            "9. Can patterns repeat?",
            "10. How do computers use patterns?",
        ]
        answers = [
            "a series of steps done one after another in order",
            "something that repeats in a predictable way",
            "yes (they follow programs which are sequences)",
            "student's own answer (steps to open file, make sandwich)",
            "yes (by recognizing the pattern)",
            "student's own answer (boil water → add tea bag → pour → add milk)",
            "it doesn't work correctly or produces wrong result",
            "yes (order is very important)",
            "yes (colors, numbers, shapes, etc.)",
            "to recognize data, optimize code, predict behavior",
        ]
    elif topic == "Simple algorithms":
        questions = [
            "1. What is an algorithm in computing?",
            "2. Is an algorithm different from a sequence?",
            "3. What makes a good algorithm?",
            "4. Can you write an algorithm?",
            "5. Give an example of an algorithm.",
            "6. What is computational thinking?",
            "7. Can algorithms be simple or complex?",
            "8. How do you test an algorithm?",
            "9. Is a search an algorithm?",
            "10. Why are algorithms important in computing?",
        ]
        answers = [
            "a step-by-step procedure to solve a problem",
            "not really (algorithms solve problems, sequences just follow steps)",
            "clear, efficient, correct, uses least steps",
            "yes",
            "student's own answer (sorting, finding, recipe, directions)",
            "thinking like a computer to solve problems step-by-step",
            "both (can be simple or complex)",
            "by running it with different inputs and checking outputs",
            "yes (searching is an algorithm)",
            "they tell computers how to solve problems efficiently",
        ]
    elif topic == "Digital citizenship":
        questions = [
            "1. What is digital citizenship?",
            "2. Should you be kind online?",
            "3. What is cyberbullying?",
            "4. Is it okay to copy others' work online?",
            "5. How should you behave online?",
            "6. What should you do if someone is mean to you online?",
            "7. Is everything online true?",
            "8. Should you respect others online?",
            "9. How do you know if a website is trustworthy?",
            "10. Give 3 rules for good digital citizenship.",
        ]
        answers = [
            "being a responsible and respectful user of digital technology",
            "yes (always)",
            "using internet to bully or hurt others",
            "no (it's plagiarism)",
            "respectfully, responsibly, safely, honestly",
            "tell a trusted adult",
            "no (you should check sources)",
            "yes (always)",
            "check if it's from a trusted source, has good design, real information",
            "be kind, be honest, respect others, follow rules, ask permission",
        ]
    elif topic == "Working with images and text":
        questions = [
            "1. Can you edit images on a computer?",
            "2. What can you do to text on a computer?",
            "3. Name 3 ways to format text.",
            "4. Can you resize an image?",
            "5. Can you change the color of text?",
            "6. What is copy and paste?",
            "7. Can you combine text and images?",
            "8. What software can you use for text and images?",
            "9. Can you undo changes to images?",
            "10. How do you insert an image into a document?",
        ]
        answers = [
            "yes",
            "change size, color, font, make bold/italic, move, copy, delete",
            "student's own answer (bold, italic, underline, change color, change size)",
            "yes",
            "yes",
            "copying text and inserting it elsewhere",
            "yes",
            "Word, Paint, PowerPoint, Publisher, Google Docs",
            "yes (undo button)",
            "Insert menu → Image → choose file",
        ]
    elif topic == "Using applications":
        questions = [
            "1. What is an application?",
            "2. Name 5 applications you use.",
            "3. What is an app on a tablet or phone?",
            "4. Can you use multiple applications at once?",
            "5. What is a web browser?",
            "6. Name 3 web browsers.",
            "7. How do you find a website?",
            "8. Can you search for information online?",
            "9. What is email?",
            "10. How do applications help us?",
        ]
        answers = [
            "a program that does a specific task",
            "student's own answer (Word, Chrome, Paint, Email, Calculator)",
            "a program on a mobile device",
            "yes (switch between them)",
            "software that accesses websites",
            "Chrome, Firefox, Safari, Edge",
            "type address in address bar or search",
            "yes (using a search engine)",
            "a way to send messages electronically",
            "help us work, learn, communicate, create, find information",
        ]
    elif topic == "Online safety and privacy":
        questions = [
            "1. What is online privacy?",
            "2. What personal information should you never share online?",
            "3. Is a password important?",
            "4. Should you use the same password for everything?",
            "5. What is a strong password?",
            "6. What should you do if you forget a password?",
            "7. Who should know your password?",
            "8. Is it safe to download from any website?",
            "9. What is a virus?",
            "10. How can you protect your privacy online?",
        ]
        answers = [
            "keeping your personal information safe and secret",
            "name, address, phone number, password, school name, birthday",
            "yes (very)",
            "no (use different passwords)",
            "long, uses numbers and letters, hard to guess",
            "use reset option or ask a trusted adult",
            "only you (and maybe parents/teachers)",
            "no (could have viruses)",
            "harmful software that damages computers",
            "don't share info, use strong passwords, check websites, ask adults",
        ]
    else:
        questions = [f"{i + 1}. Year 2 Computing practice question {i + 1}" for i in range(10)]
        answers = [f"answer {i + 1}" for i in range(10)]

    content = f"Computing Homework - Year 2 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year3_homework(topic: str, index: int) -> tuple:
    """Year 3 Computing作业（7-8 岁），返回 (content, correct_answers)"""
    if topic == "Programming (Scratch or similar)":
        questions = [
            "1. What is Scratch?",
            "2. What can you create with block-based programming?",
            "3. What is a sprite?",
            "4. What is the stage in Scratch?",
            "5. What are blocks used for?",
            "6. Can you create animations with Scratch?",
            "7. Can you add sounds to a Scratch project?",
            "8. What is an event in Scratch?",
            "9. How do you start a Scratch program?",
            "10. What can you make with visual programming?",
        ]
        answers = [
            "a visual block-based programming language for beginners",
            "games, animations, stories, interactive projects",
            "a character or object in a Scratch program",
            "the background where sprites move and act",
            "to give commands to sprites",
            "yes (using movement blocks)",
            "yes (using sound blocks)",
            "something that triggers an action (clicking, key press, etc.)",
            "by clicking the green flag",
            "stories, games, animations, simulations, learning tools",
        ]
    elif topic == "Loops and repetition":
        questions = [
            "1. What is a loop?",
            "2. What is repetition in programming?",
            "3. Why use loops instead of repeating code?",
            "4. What is a 'repeat' block?",
            "5. What is a 'forever' loop?",
            "6. Can loops have conditions?",
            "7. Give an example of when you'd use a loop.",
            "8. What happens if a loop has no end?",
            "9. Are loops efficient?",
            "10. How many times can a loop repeat?",
        ]
        answers = [
            "a way to repeat code multiple times",
            "doing the same thing over and over",
            "saves space, easier to read, more efficient",
            "a block that repeats code a set number of times",
            "a block that repeats forever until stopped",
            "yes (conditional loops)",
            "drawing shapes, moving characters, checking conditions repeatedly",
            "it loops forever (infinite loop)",
            "yes (avoid writing same code many times)",
            "any number (based on the loop condition)",
        ]
    elif topic == "Debugging and testing":
        questions = [
            "1. What is testing in programming?",
            "2. How do you test a program?",
            "3. What should you look for when testing?",
            "4. What is a test case?",
            "5. How do you know if a program has bugs?",
            "6. What is systematic testing?",
            "7. Should you test edge cases?",
            "8. How do you document bugs?",
            "9. Can you prevent all bugs?",
            "10. Why is testing important?",
        ]
        answers = [
            "running a program to find errors",
            "by running it with different inputs and checking outputs",
            "does it do what it should? are there errors? does it crash?",
            "a set of inputs and expected outputs for testing",
            "it doesn't work as expected, crashes, or produces wrong output",
            "testing methodically with planned test cases",
            "yes (test at boundaries of acceptable values)",
            "write down what went wrong and how to reproduce it",
            "mostly (but some are hard to predict)",
            "ensures programs work correctly before release",
        ]
    elif topic == "Algorithms and problem-solving":
        questions = [
            "1. What is computational thinking?",
            "2. What are the steps to solve a problem with a computer?",
            "3. What is decomposition?",
            "4. What is pattern recognition?",
            "5. What is abstraction?",
            "6. Give an example of decomposition.",
            "7. How do you plan an algorithm?",
            "8. Should you test your algorithm?",
            "9. Can the same problem have multiple solutions?",
            "10. Is algorithmic thinking only for programmers?",
        ]
        answers = [
            "thinking like a computer to solve problems step-by-step",
            "understand problem → plan algorithm → write code → test → debug",
            "breaking a big problem into smaller pieces",
            "finding similarities and patterns in data",
            "focusing on important details while ignoring others",
            "student's own answer (make game: plan story → design sprites → code)",
            "write steps, organize them, check for missing steps",
            "yes (with different inputs)",
            "yes (different algorithms can solve same problem)",
            "no (everyone uses computational thinking daily)",
        ]
    elif topic == "Digital literacy":
        questions = [
            "1. What is digital literacy?",
            "2. Why is digital literacy important?",
            "3. What skills does digital literacy include?",
            "4. How do you search effectively online?",
            "5. How do you know if online information is reliable?",
            "6. What is a search engine?",
            "7. Should you trust everything you read online?",
            "8. How do you cite sources?",
            "9. What is plagiarism?",
            "10. Name 3 digital literacy skills.",
        ]
        answers = [
            "the ability to use digital technology effectively and responsibly",
            "so you can find information, create content, communicate safely",
            "typing, searching, using apps, evaluating information, creating content",
            "use specific keywords, use quotes for exact phrases, refine search",
            "check author/source, look for real evidence, check multiple sources",
            "a tool to find information on the internet (Google, Bing, etc.)",
            "no (verify information from multiple sources)",
            "write author name, website, date, URL",
            "copying others' work without permission",
            "search skills, evaluating sources, proper citing, creating content",
        ]
    elif topic == "Networks and the internet":
        questions = [
            "1. What is a network?",
            "2. What is the internet?",
            "3. How are computers connected in a network?",
            "4. What is a server?",
            "5. What is an IP address?",
            "6. What is WiFi?",
            "7. Can networks be wired or wireless?",
            "8. What happens when you connect to the internet?",
            "9. How fast is the internet?",
            "10. What is the world wide web?",
        ]
        answers = [
            "two or more computers connected together",
            "a global system of connected networks",
            "using cables or WiFi",
            "a computer that stores and shares information",
            "a unique number that identifies a computer on network",
            "wireless technology for connecting to networks",
            "yes (both wired and wireless)",
            "your computer connects to servers and accesses information",
            "varies (measured in Mbps or Gbps)",
            "a system of connected documents and resources on the internet",
        ]
    elif topic == "File management":
        questions = [
            "1. What is file management?",
            "2. Why should you organize your files?",
            "3. What is a folder (directory)?",
            "4. How do you create a new folder?",
            "5. How do you move a file to a folder?",
            "6. What makes a good file name?",
            "7. Can you delete files?",
            "8. Is it possible to recover deleted files?",
            "9. How much storage space do computers have?",
            "10. What is backing up files?",
        ]
        answers = [
            "organizing and storing files on a computer",
            "so you can find files easily",
            "a container for storing files and other folders",
            "right-click → New → Folder (or File menu)",
            "drag and drop or cut and paste",
            "descriptive, clear, not too long, use underscores or hyphens",
            "yes (usually to trash/recycle bin)",
            "yes (usually from recycle bin before it's permanently deleted)",
            "varies (hundreds of GB to TB depending on drive)",
            "making copies of files in case originals get lost",
        ]
    elif topic == "Hardware and networks":
        questions = [
            "1. What is hardware?",
            "2. Name 5 pieces of computer hardware.",
            "3. What is a network card?",
            "4. What is a router?",
            "5. What does a modem do?",
            "6. What connects computers in a local network?",
            "7. Can hardware affect network speed?",
            "8. What is bandwidth?",
            "9. What are USB ports used for?",
            "10. How does data travel over networks?",
        ]
        answers = [
            "physical parts of a computer you can touch",
            "student's own answer (CPU, RAM, screen, keyboard, mouse, hard drive)",
            "hardware that allows a computer to connect to a network",
            "device that distributes internet to multiple devices",
            "connects your home to internet service provider",
            "cables, WiFi, network adapters",
            "yes (better hardware = faster speed)",
            "amount of data that can be transmitted",
            "connecting devices (USB drive, printer, external drive)",
            "as packets of data through cables or wireless signals",
        ]
    else:
        questions = [f"{i + 1}. Year 3 Computing practice question {i + 1}" for i in range(10)]
        answers = [f"answer {i + 1}" for i in range(10)]

    content = f"Computing Homework - Year 3 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year4_homework(topic: str, index: int) -> tuple:
    """Year 4 Computing作业（8-9 岁），返回 (content, correct_answers)"""
    if topic == "Programming (loops and conditions)":
        questions = [
            "1. What is a conditional statement?",
            "2. What is an 'if' statement?",
            "3. What is an 'if-else' statement?",
            "4. What is a boolean value?",
            "5. Give an example of a condition.",
            "6. How do loops and conditions work together?",
            "7. What is a comparison operator?",
            "8. Name 3 comparison operators.",
            "9. How do you test conditions?",
            "10. Can conditions be nested (one inside another)?",
        ]
        answers = [
            "a statement that executes code based on whether a condition is true",
            "a statement that runs code if a condition is true",
            "a statement that runs one code if true, different code if false",
            "a value that is either true or false",
            "student's own answer (if score > 10, if name == 'Ali')",
            "conditions control what loops do, loops repeat conditions",
            "symbols used to compare values (==, !=, <, >, <=, >=)",
            "==, <, >, !=, <=, >=",
            "by running code with different inputs and checking results",
            "yes (if inside another if)",
        ]
    elif topic == "Variables and data types":
        questions = [
            "1. What is a variable?",
            "2. Why do you need variables?",
            "3. What are data types?",
            "4. Name 4 data types.",
            "5. What is a string?",
            "6. What is an integer?",
            "7. What is a boolean?",
            "8. How do you assign a value to a variable?",
            "9. Can you change a variable's value?",
            "10. What is variable naming?",
        ]
        answers = [
            "a container for storing data",
            "to store and work with information in programs",
            "categories of data (numbers, text, true/false, etc.)",
            "string, integer, boolean, float/decimal",
            "text data (words, sentences, letters)",
            "whole number data",
            "true or false",
            "variableName = value",
            "yes",
            "giving variables descriptive names (playerScore, userName, etc.)",
        ]
    elif topic == "Boolean logic":
        questions = [
            "1. What is boolean logic?",
            "2. What are the basic boolean operators?",
            "3. What is AND logic?",
            "4. What is OR logic?",
            "5. What is NOT logic?",
            "6. Give an example of AND.",
            "7. Give an example of OR.",
            "8. Give an example of NOT.",
            "9. How do you combine boolean logic?",
            "10. Why is boolean logic important in programming?",
        ]
        answers = [
            "using true/false values to make decisions in code",
            "AND, OR, NOT",
            "both conditions must be true",
            "at least one condition must be true",
            "reverses a true/false value",
            "student's own answer (if age > 18 AND hasLicense)",
            "student's own answer (if nameIsBob OR nameIsAlice)",
            "student's own answer (if NOT isRaining)",
            "use parentheses: (condition1 AND condition2) OR condition3",
            "controls program flow, makes decisions, handles complexity",
        ]
    elif topic == "Debugging techniques":
        questions = [
            "1. What is a syntax error?",
            "2. What is a logic error?",
            "3. What is a runtime error?",
            "4. What is a breakpoint?",
            "5. How do you find bugs systematically?",
            "6. What is printing for debugging?",
            "7. Can you use a debugger?",
            "8. What should you document about bugs?",
            "9. How do you prevent bugs?",
            "10. Is debugging a skill?",
        ]
        answers = [
            "error in code structure (missing bracket, wrong spelling)",
            "code runs but doesn't do what it should",
            "error that happens when program runs (division by zero)",
            "a point where debugger pauses to inspect code",
            "break problem into parts, test each part, narrow down issue",
            "using print statements to check variable values",
            "yes (most IDEs have built-in debuggers)",
            "what went wrong, when, how to reproduce, what you tried",
            "write clear code, test frequently, think through logic",
            "yes (improves with practice)",
        ]
    elif topic == "File handling and storage":
        questions = [
            "1. What is file handling in programming?",
            "2. Can programs read files?",
            "3. Can programs write to files?",
            "4. What is a file path?",
            "5. What file formats exist?",
            "6. What is data persistence?",
            "7. How do you save data from a program?",
            "8. What is a database?",
            "9. Can you encrypt files?",
            "10. Why is backing up files important?",
        ]
        answers = [
            "reading, writing, and managing files in programs",
            "yes (to access stored data)",
            "yes (to save program data)",
            "location of a file on a computer (C:/Users/Documents/file.txt)",
            "student's own answer (.txt, .pdf, .jpg, .mp3, .doc, etc.)",
            "saving data so it remains even after program closes",
            "write to file using file handling code",
            "organized collection of related data",
            "yes (with encryption software)",
            "protects against data loss from hardware failure",
        ]
    elif topic == "Cybersecurity basics":
        questions = [
            "1. What is cybersecurity?",
            "2. What is a cyberattack?",
            "3. What is malware?",
            "4. What is phishing?",
            "5. What is a firewall?",
            "6. What is antivirus software?",
            "7. How can you keep passwords secure?",
            "8. What should you do if hacked?",
            "9. What is two-factor authentication?",
            "10. How do you stay safe online?",
        ]
        answers = [
            "protecting computers and networks from digital attacks",
            "an attempt to damage, steal, or disrupt computer systems",
            "harmful software that damages computers",
            "fake emails/messages trying to steal information",
            "software that blocks unauthorized access to network",
            "software that detects and removes malware",
            "use strong passwords, don't share, change regularly",
            "tell an adult, change password, scan for viruses, monitor account",
            "extra security step (password + another verification method)",
            "strong passwords, keep software updated, don't trust suspicious links",
        ]
    elif topic == "Networks and internet":
        questions = [
            "1. What is a LAN?",
            "2. What is a WAN?",
            "3. What is DNS?",
            "4. What is an HTTP/HTTPS?",
            "5. How do packets travel on the internet?",
            "6. What is bandwidth?",
            "7. What is latency?",
            "8. Can you trace data across networks?",
            "9. What is VPN?",
            "10. How does cloud storage work?",
        ]
        answers = [
            "Local Area Network (connected computers in small area)",
            "Wide Area Network (connected computers across large distance)",
            "Domain Name System (translates domain names to IP addresses)",
            "protocols for transferring data on web (HTTP is unsecured, HTTPS secured)",
            "broken into packets, routed through network, reassembled at destination",
            "amount of data that can be transferred per unit of time",
            "delay in data transmission",
            "yes (using tools like traceroute)",
            "Virtual Private Network (encrypts data for privacy)",
            "files stored on remote servers accessed via internet",
        ]
    elif topic == "Computer systems and components":
        questions = [
            "1. What is a CPU?",
            "2. What is RAM?",
            "3. What is ROM?",
            "4. What is storage?",
            "5. What is the motherboard?",
            "6. How do components communicate?",
            "7. What is the difference between RAM and storage?",
            "8. How does a computer process instructions?",
            "9. What is thermal management?",
            "10. Why are computer components designed to work together?",
        ]
        answers = [
            "Central Processing Unit (brain of computer)",
            "Random Access Memory (fast, temporary memory for running programs)",
            "Read-Only Memory (permanent memory for basic instructions)",
            "long-term memory (hard drive, SSD) for keeping files",
            "main circuit board connecting all components",
            "through buses (communication pathways)",
            "RAM is fast but temporary, storage is slow but permanent",
            "fetch instruction → decode → execute → store result",
            "keeping computer cool (fans, heat sinks)",
            "for compatibility, efficiency, and optimal performance",
        ]
    else:
        questions = [f"{i + 1}. Year 4 Computing practice question {i + 1}" for i in range(10)]
        answers = [f"answer {i + 1}" for i in range(10)]

    content = f"Computing Homework - Year 4 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year5_homework(topic: str, index: int) -> tuple:
    """Year 5 Computing作业（9-10 岁），返回 (content, correct_answers)"""
    if topic == "Programming (complex programs)":
        questions = [
            "1. What makes a program complex?",
            "2. How do you structure complex programs?",
            "3. What is modularity?",
            "4. What is code reuse?",
            "5. What are design patterns?",
            "6. How do you document complex code?",
            "7. What is version control?",
            "8. How do you test complex programs?",
            "9. What is refactoring?",
            "10. How do professional programmers manage complexity?",
        ]
        answers = [
            "many features, lots of code, multiple interactions",
            "break into modules, use functions, organize logically",
            "dividing code into independent, reusable parts",
            "using same code in multiple places (through functions/libraries)",
            "proven solutions to common programming problems",
            "comments, docstrings, clear variable names, README files",
            "system for tracking code changes (Git, GitHub)",
            "unit tests, integration tests, user testing, debugging",
            "improving code without changing functionality",
            "teamwork, code review, documentation, testing, planning",
        ]
    elif topic == "Conditional statements and logic":
        questions = [
            "1. What is nested conditionals?",
            "2. What is switch-case logic?",
            "3. How do you optimize conditions?",
            "4. What is short-circuit evaluation?",
            "5. Give an example of complex logic.",
            "6. How do you test conditionals?",
            "7. What are ternary operators?",
            "8. Can conditions be chained?",
            "9. What is guard clause?",
            "10. Why is logical order important?",
        ]
        answers = [
            "conditions inside conditions",
            "statement that checks one value against multiple cases",
            "put most common conditions first, simplify logic",
            "stopping evaluation when result is known",
            "student's own answer (if age >= 18 AND hasLicense AND car != null)",
            "test with true/false cases, edge cases, all branches",
            "shortened if-else (condition ? valueIfTrue : valueIfFalse)",
            "yes (if condition1 && condition2 && condition3)",
            "early return to avoid nested conditions",
            "affects readability, performance, and correctness",
        ]
    elif topic == "Subroutines and functions":
        questions = [
            "1. What is a subroutine (function)?",
            "2. Why use functions?",
            "3. What is a parameter?",
            "4. What is a return value?",
            "5. What is function scope?",
            "6. What is recursion?",
            "7. Give an example of recursion.",
            "8. What is a callback function?",
            "9. How do you write good functions?",
            "10. What are built-in functions?",
        ]
        answers = [
            "reusable block of code that performs a task",
            "avoid repetition, make code organized, improve readability",
            "input value passed to a function",
            "output value returned by a function",
            "which variables a function can access",
            "function calling itself",
            "factorial, Fibonacci, tree traversal",
            "function passed as argument to another function",
            "single responsibility, clear name, handle errors, test",
            "pre-written functions in programming languages (print, len, etc.)",
        ]
    elif topic == "Data representation":
        questions = [
            "1. How is data represented in computers?",
            "2. What is binary?",
            "3. What is hexadecimal?",
            "4. How do numbers get converted to binary?",
            "5. What is ASCII?",
            "6. How is text stored in computers?",
            "7. What is Unicode?",
            "8. How are images represented digitally?",
            "9. What is compression?",
            "10. Why is data representation important?",
        ]
        answers = [
            "using binary digits (0 and 1)",
            "base-2 number system (0 and 1 only)",
            "base-16 number system (0-9, A-F)",
            "divide by 2 repeatedly, read remainders backwards",
            "standard for representing text using numbers",
            "as ASCII or Unicode numbers (one byte per character)",
            "international character standard (can represent any language)",
            "as pixels with color values (red, green, blue)",
            "reducing file size by removing redundant data",
            "affects storage size, transmission speed, accuracy",
        ]
    elif topic == "Cybersecurity and encryption":
        questions = [
            "1. What is encryption?",
            "2. What is a cipher?",
            "3. What is symmetric encryption?",
            "4. What is asymmetric encryption?",
            "5. What is a hash?",
            "6. What is a digital signature?",
            "7. How do you create a secure password?",
            "8. What is multi-factor authentication?",
            "9. What is a certificate?",
            "10. How does SSL/TLS work?",
        ]
        answers = [
            "converting data to unreadable form to protect it",
            "method of encryption/decryption",
            "same key encrypts and decrypts (fast, risky if key stolen)",
            "different keys for encryption and decryption (slower, more secure)",
            "one-way function converting data to unique fingerprint",
            "proves data came from correct source",
            "long, mix of uppercase/lowercase/numbers/symbols, unique",
            "two or more verification methods",
            "proves website/server is legitimate",
            "encrypts data in transit between browser and server",
        ]
    elif topic == "Computer networks":
        questions = [
            "1. What is network topology?",
            "2. Name 3 network topologies.",
            "3. What is a bus topology?",
            "4. What is a star topology?",
            "5. What is a mesh topology?",
            "6. What are advantages of mesh networks?",
            "7. What is network protocol?",
            "8. What is TCP/IP?",
            "9. How do routers work?",
            "10. What is network congestion?",
        ]
        answers = [
            "how computers are arranged in a network",
            "bus, star, mesh, ring, tree",
            "all computers connected to central cable",
            "all computers connected to central hub/switch",
            "each computer connected to multiple others",
            "redundancy (if one fails, others still connected), load balancing",
            "set of rules for communication between computers",
            "core protocols for internet (Transmission Control Protocol/Internet Protocol)",
            "forward data packets to destination based on IP address",
            "too much data on network, causes slowdown",
        ]
    elif topic == "Online privacy and safety":
        questions = [
            "1. What is a digital footprint?",
            "2. What can you do about your digital footprint?",
            "3. What is privacy protection?",
            "4. What should you never do online?",
            "5. What is identity theft?",
            "6. How do you recognize scams?",
            "7. What is social engineering?",
            "8. Should you trust public WiFi?",
            "9. What is a VPN?",
            "10. How do you report cybercrime?",
        ]
        answers = [
            "all information about you on the internet",
            "delete old posts, use privacy settings, be careful what you share",
            "keeping personal information secure",
            "share personal info, click unknown links, give passwords, meet strangers",
            "someone using your identity for criminal purposes",
            "suspicious links, too-good-to-be-true offers, urgent requests",
            "manipulating people into revealing information",
            "no (not secure, others can intercept data)",
            "Virtual Private Network (encrypts internet connection)",
            "report to authorities, FBI IC3, or relevant agency",
        ]
    elif topic == "IT applications and systems":
        questions = [
            "1. What are enterprise systems?",
            "2. What is ERP?",
            "3. What is CRM?",
            "4. What is cloud computing?",
            "5. What are advantages of cloud systems?",
            "6. What is SaaS?",
            "7. What is PaaS?",
            "8. What is IaaS?",
            "9. What are business applications?",
            "10. How do IT systems help businesses?",
        ]
        answers = [
            "large computer systems used by organizations",
            "Enterprise Resource Planning (integrates business processes)",
            "Customer Relationship Management (manages customer interactions)",
            "delivering computing services over internet",
            "scalability, accessibility, cost-effective, automatic updates",
            "Software as a Service (access software online, e.g., Gmail)",
            "Platform as a Service (build apps on cloud platform)",
            "Infrastructure as a Service (rent computing resources)",
            "software for business tasks (spreadsheets, email, project management)",
            "improve efficiency, reduce costs, automate tasks, enable collaboration",
        ]
    else:
        questions = [f"{i + 1}. Year 5 Computing practice question {i + 1}" for i in range(10)]
        answers = [f"answer {i + 1}" for i in range(10)]

    content = f"Computing Homework - Year 5 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year6_homework(topic: str, index: int) -> tuple:
    """Year 6 Computing作业（10-11 岁），返回 (content, correct_answers)"""
    if topic == "Programming (multi-step algorithms)":
        questions = [
            "1. What is algorithmic complexity?",
            "2. What is Big O notation?",
            "3. What is an efficient algorithm?",
            "4. Give examples of O(1) operations.",
            "5. What is O(n) time complexity?",
            "6. What is O(n²) time complexity?",
            "7. How do you optimize algorithms?",
            "8. What is trade-off between time and space?",
            "9. How do you measure algorithm performance?",
            "10. Why is algorithm efficiency important?",
        ]
        answers = [
            "how computational resources scale with input size",
            "notation describing algorithm performance as input grows",
            "uses least time and memory to complete task",
            "student's own answer (accessing array element, simple math)",
            "time grows linearly with input size",
            "time grows quadratically with input size",
            "use better algorithm, reduce unnecessary operations, cache results",
            "faster algorithms often use more memory",
            "timing, profiling tools, Big O analysis",
            "affects program speed, resource usage, user experience",
        ]
    elif topic == "Object-oriented thinking":
        questions = [
            "1. What is object-oriented programming?",
            "2. What is a class?",
            "3. What is an object?",
            "4. What are attributes?",
            "5. What are methods?",
            "6. What is inheritance?",
            "7. What is encapsulation?",
            "8. What is polymorphism?",
            "9. Give an example of OOP.",
            "10. What are advantages of OOP?",
        ]
        answers = [
            "programming approach using objects and classes",
            "blueprint or template for creating objects",
            "instance of a class with specific data",
            "data/properties of an object",
            "actions/behaviors of an object",
            "class inherits properties from another class",
            "hiding internal details, exposing only necessary interface",
            "same method name behaves differently in different classes",
            "student's own answer (Car class: color, speed attributes; drive method)",
            "organized code, reusability, easier maintenance, clear structure",
        ]
    elif topic == "Advanced debugging":
        questions = [
            "1. What is profiling?",
            "2. What is a memory leak?",
            "3. How do you find memory leaks?",
            "4. What is a stack trace?",
            "5. How do you use logging?",
            "6. What is unit testing?",
            "7. What is integration testing?",
            "8. What is regression testing?",
            "9. How do you create test cases?",
            "10. What is debugging in production?",
        ]
        answers = [
            "measuring program performance (time, memory, CPU)",
            "program allocating memory and not releasing it",
            "using profilers and memory analysis tools",
            "showing function calls leading to error",
            "recording program events for debugging",
            "testing individual functions/components",
            "testing how components work together",
            "testing that new changes don't break existing features",
            "think of normal inputs, edge cases, invalid inputs",
            "fixing bugs in live systems (careful, use rollback plans)",
        ]
    elif topic == "Data encoding and representation":
        questions = [
            "1. What is character encoding?",
            "2. What is color depth?",
            "3. What is sampling rate?",
            "4. How is video encoded?",
            "5. What is lossless compression?",
            "6. What is lossy compression?",
            "7. What is the difference between lossless and lossy?",
            "8. What formats use lossless compression?",
            "9. What formats use lossy compression?",
            "10. Why does encoding matter?",
        ]
        answers = [
            "mapping characters to numbers (ASCII, Unicode, UTF-8)",
            "number of colors each pixel can display (8-bit = 256 colors)",
            "number of audio samples per second",
            "as frames (images) played in sequence at high speed",
            "no data lost when decompressed",
            "some data lost when decompressed",
            "lossless preserves all data, lossy reduces file size by removing data",
            "PNG, GIF, TIFF, ZIP, RAW",
            "JPG, MP3, MP4, AAC, WebP",
            "affects file size, quality, compatibility, transmission speed",
        ]
    elif topic == "Network architecture":
        questions = [
            "1. What is OSI model?",
            "2. Name the 7 layers of OSI model.",
            "3. What is IP addressing?",
            "4. What is IPv4 vs IPv6?",
            "5. What is subnetting?",
            "6. What is a gateway?",
            "7. What is a proxy server?",
            "8. What is load balancing?",
            "9. What is network redundancy?",
            "10. How are large networks organized?",
        ]
        answers = [
            "Open Systems Interconnection model (layers of network communication)",
            "Physical, Data Link, Network, Transport, Session, Presentation, Application",
            "unique number identifying device on network",
            "IPv4: 32-bit (4 billion addresses), IPv6: 128-bit (huge addresses)",
            "dividing network into subnetworks",
            "device connecting different networks",
            "server that acts as intermediary between client and server",
            "distributing load across multiple servers",
            "backup systems if primary fails",
            "hierarchically with subnets, routers, firewalls, servers",
        ]
    elif topic == "Digital ethics and responsibility":
        questions = [
            "1. What is digital ethics?",
            "2. What is intellectual property online?",
            "3. What should you consider about AI?",
            "4. What is digital divide?",
            "5. How can technology harm people?",
            "6. What is responsible computing?",
            "7. What is an accessibility requirement?",
            "8. How should data be used ethically?",
            "9. What is surveillance?",
            "10. Why are digital ethics important?",
        ]
        answers = [
            "moral principles guiding technology use",
            "creative works protected by copyright/patents/trademarks",
            "bias in AI, job displacement, transparency needed",
            "gap between those with technology access and those without",
            "cyberbullying, misinformation, addiction, privacy violation",
            "considering impact on users and society",
            "designing for people with disabilities",
            "collect only necessary data, protect privacy, be transparent",
            "monitoring activities without consent",
            "ensures technology benefits everyone fairly and safely",
        ]
    elif topic == "Cybersecurity and protection":
        questions = [
            "1. What is a security policy?",
            "2. What is penetration testing?",
            "3. What is a security audit?",
            "4. What are common vulnerabilities?",
            "5. What is a patch?",
            "6. Why update software regularly?",
            "7. What is endpoint security?",
            "8. What is network segmentation?",
            "9. How do you respond to breaches?",
            "10. What is zero-trust security?",
        ]
        answers = [
            "rules and procedures for protecting systems",
            "authorized testing to find security weaknesses",
            "review of security measures",
            "SQL injection, cross-site scripting, weak passwords, unpatched software",
            "update fixing security vulnerabilities",
            "patches fix security holes, prevent attacks",
            "security for individual devices (antivirus, firewall)",
            "dividing network into separate secure zones",
            "assess damage, isolate systems, notify users, fix vulnerabilities",
            "assume all users/devices are untrusted, verify everything",
        ]
    elif topic == "Emerging technologies":
        questions = [
            "1. What is artificial intelligence?",
            "2. What is machine learning?",
            "3. What is IoT (Internet of Things)?",
            "4. What is blockchain?",
            "5. What are applications of AI?",
            "6. What are concerns about AI?",
            "7. What is quantum computing?",
            "8. What is augmented reality?",
            "9. What is virtual reality?",
            "10. How will technology change in future?",
        ]
        answers = [
            "computer systems that mimic human intelligence",
            "algorithms that improve by learning from data",
            "physical devices connected to internet",
            "distributed digital ledger technology (cryptocurrency, smart contracts)",
            "healthcare, transportation, finance, entertainment, education",
            "bias, job loss, privacy, security, ethical concerns",
            "computers using quantum mechanics for computation",
            "overlaying digital content on real world",
            "immersive digital environment",
            "student's own answer (AI advancement, quantum computing, new applications)",
        ]
    else:
        questions = [f"{i + 1}. Year 6 Computing practice question {i + 1}" for i in range(10)]
        answers = [f"answer {i + 1}" for i in range(10)]

    content = f"Computing Homework - Year 6 - {topic} (Set {index})\n\n" + "\n".join(questions)
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


def generate_year_homework(year_group: int, count: int = 500) -> list:
    """为指定年级生成指定数量的Computing作业"""
    topics = COMPUTING_TOPICS_BY_YEAR.get(year_group, [])
    if not topics:
        print(f"警告：未找到 Year {year_group} 的Computing主题")
        return []

    config = YEAR_CONFIG.get(year_group, {"key_stage": "KS2", "homework_minutes": "20-30"})
    batch_data = []

    for i in range(1, count + 1):
        topic = topics[(i - 1) % len(topics)]
        content, correct_answers = generate_computing_homework(year_group, topic, i)
        if content is None or correct_answers is None:
            print(f"  Year {year_group}: Failed to generate question {i}, skipping...")
            continue

        metadata = {
            "year_group": year_group,
            "subject": "Computing",
            "homework_minutes": config["homework_minutes"],
            "key_stage": config["key_stage"],
            "topic": topic,
            "student_id": None,
            "correct_answers": json.dumps(correct_answers),  # Convert list to JSON string for ChromaDB
        }

        doc_id = f"computing_y{year_group}_{i:03d}"
        batch_data.append({
            "content": content,
            "metadata": metadata,
            "doc_id": doc_id,
        })

        if i % 10 == 0:
            print(f"  已生成 {i}/{count} 份作业")

    return batch_data


def main():
    """主函数：检查各年级Computing作业，缺失则生成"""
    print("检查各年级Computing作业是否存在...\n")

    store = get_homework_rag_store()
    years_to_generate = []

    for year in range(1, 7):
        expected = HOMEWORK_COUNT.get(year, 500)
        existing = count_year_homework(store, year, "Computing")

        if existing >= expected:
            print(f"  Year {year}: complete ({existing}/{expected})")
        else:
            print(f"  Year {year}: incomplete ({existing}/{expected})")
            years_to_generate.append(year)

    if not years_to_generate:
        print("\n所有年级Computing作业已存在，无需生成。")
        return

    print(f"\n需要生成的年级: {', '.join(f'Year {y}' for y in years_to_generate)}")

    for year in years_to_generate:
        print(f"\n开始生成 Year {year} Computing作业...")
        count = HOMEWORK_COUNT.get(year, 1000)
        batch_data = generate_year_homework(year, count=count)

        if batch_data:
            added = add_homework_in_batches(store, batch_data)
            print(
                f"Year {year}: added {added} new Computing homework documents; "
                f"target total is {len(batch_data)}"
            )

    get_rag_stats(store)


if __name__ == "__main__":
    main()
