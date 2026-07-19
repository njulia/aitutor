#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate England-curriculum Computing homework for Years 1-6.

The RAG and review interfaces are unchanged.  Worksheets still contain numbered
questions and a positional answer list.  Topics progress from KS1 algorithms,
simple programs, purposeful technology use and online safety to KS2 sequence,
selection, repetition, variables, networks, search, data and responsible use.
"""
from __future__ import annotations

import os
import sys
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

HOMEWORK_COUNT = {1: 100, 2: 200, 3: 300, 4: 400, 5: 500, 6: 600}

COMPUTING_TOPICS_BY_YEAR = {
    1: ["Algorithms and instructions", "Simple programs", "Digital content", "Technology around us", "Online safety"],
    2: ["Programs and debugging", "Logical prediction", "Creating and organising content", "Information technology uses", "Online privacy and reporting"],
    3: ["Sequence and repetition", "Input and output", "Computer networks", "Search basics", "Digital creation", "Safe and responsible use"],
    4: ["Selection and variables", "Debugging and decomposition", "Internet and the World Wide Web", "Search results and reliability", "Data presentation", "Online behaviour"],
    5: ["Designing programs for goals", "Sequence selection and repetition", "Variables input and output", "Networks and internet services", "Evaluating digital content", "Combining software and data", "Privacy and security"],
    6: ["Decomposition and efficient solutions", "Explaining and correcting algorithms", "Programming constructs", "Networks communication and collaboration", "Search and source evaluation", "Data systems", "Responsible technology use"],
}

TOPIC_ALIASES = {
    "Introduction to computers": "Technology around us",
    "Input and output devices": "Technology around us",
    "Simple sequences and commands": "Algorithms and instructions",
    "Digital safety online": "Online safety",
    "Basic algorithms": "Algorithms and instructions",
    "Programmable toys and robots": "Simple programs",
    "Working with digital tools": "Digital content",
    "Saving and opening files": "Digital content",
    "Programs and programming": "Programs and debugging",
    "Debugging programs": "Programs and debugging",
    "Sequences and patterns": "Logical prediction",
    "Simple algorithms": "Logical prediction",
    "Digital citizenship": "Online privacy and reporting",
    "Working with images and text": "Creating and organising content",
    "Using applications": "Creating and organising content",
    "Online safety and privacy": "Online privacy and reporting",
    "Programming (Scratch or similar)": "Sequence and repetition",
    "Loops and repetition": "Sequence and repetition",
    "Debugging and testing": "Sequence and repetition",
    "Algorithms and problem-solving": "Sequence and repetition",
    "Digital literacy": "Digital creation",
    "Networks and the internet": "Computer networks",
    "File management": "Digital creation",
    "Hardware and networks": "Computer networks",
    "Programming (loops and conditions)": "Selection and variables",
    "Variables and data types": "Selection and variables",
    "Boolean logic": "Selection and variables",
    "Debugging techniques": "Debugging and decomposition",
    "File handling and storage": "Data presentation",
    "Cybersecurity basics": "Online behaviour",
    "Networks and internet": "Internet and the World Wide Web",
    "Computer systems and components": "Internet and the World Wide Web",
    "Programming (complex programs)": "Designing programs for goals",
    "Conditional statements and logic": "Sequence selection and repetition",
    "Subroutines and functions": "Designing programs for goals",
    "Data representation": "Combining software and data",
    "Cybersecurity and encryption": "Privacy and security",
    "Computer networks": "Networks and internet services",
    "Online privacy and safety": "Privacy and security",
    "IT applications and systems": "Combining software and data",
    "Programming (multi-step algorithms)": "Programming constructs",
    "Object-oriented thinking": "Decomposition and efficient solutions",
    "Advanced debugging": "Explaining and correcting algorithms",
    "Data encoding and representation": "Data systems",
    "Network architecture": "Networks communication and collaboration",
    "Digital ethics and responsibility": "Responsible technology use",
    "Cybersecurity and protection": "Responsible technology use",
    "Emerging technologies": "Search and source evaluation",
}

YEAR_CONFIG = {
    1: {"key_stage": "KS1", "homework_minutes": "10-15"},
    2: {"key_stage": "KS1", "homework_minutes": "10-20"},
    3: {"key_stage": "KS2", "homework_minutes": "15-20"},
    4: {"key_stage": "KS2", "homework_minutes": "20-25"},
    5: {"key_stage": "KS2", "homework_minutes": "20-30"},
    6: {"key_stage": "KS2", "homework_minutes": "25-30"},
}


def _repeat(items, rng, index):
    q=[]
    for i in range(10):
        stem,ans,wrong=items[(i+index)%len(items)]
        q.append(make_mcq(stem,ans,wrong,rng))
    return q


def _year1(topic,index):
    rng=stable_random("Computing",1,topic,index)
    if topic=="Algorithms and instructions":items=[("What is an algorithm?","a clear set of steps for completing a task",["a computer screen","a random guess","a picture with no instructions"]),("Which instruction is precise?","Move forward 2 steps.",["Move a bit.","Go somewhere.","Do something."]),("Which order makes sense for brushing teeth?","put toothpaste on brush → brush teeth → rinse",["rinse → put toothpaste on brush → brush teeth","brush teeth → sleep → find brush","put toothpaste away → brush without a brush → rinse"]),("Why must instructions be in the correct order?","The order affects the result.",["Computers can guess every missing step.","Order never matters.","Instructions are only pictures."]),("Which is a sequence?","turn on tablet → open app → choose activity",["choose activity → no device → turn off before starting","three unrelated words","a single colour"])]
    elif topic=="Simple programs":items=[("What is a program?","instructions that a digital device follows",["a type of chair","a paper-only picture","a battery with no instructions"]),("A Bee-Bot follows forward, forward, right. What is the third command?","right",["forward","left","stop"]),("What does debugging mean?","finding and fixing a mistake in a program",["adding random commands","turning off every device","deleting the goal"]),("If a character follows 'move 1 step' twice, how many steps does it move?","2",["1","3","0"]),("Which command would make a character turn?","turn left",["say hello","wait","change colour"])]
    elif topic=="Digital content":items=[("Which tool is best for typing a short sentence?","word-processing app",["camera only","calculator only","torch"]),("What does 'save' do?","stores work so it can be opened later",["prints every file","deletes the work","turns off the internet"]),("Which action organises digital work?","give the file a clear name",["use the same name for everything","never save it","hide it randomly"]),("Which tool can create a digital picture?","drawing app",["paper clip","speaker only","charging cable"]),("What does 'open a file' mean?","display stored work so it can be used",["destroy the file","send it to everyone","turn it into paper automatically"])]
    elif topic=="Technology around us":items=[("Which is an input device?","keyboard",["screen","speaker","printer"]),("Which is an output device?","screen",["mouse","microphone","keyboard"]),("Where might information technology be used?","a supermarket checkout",["only inside a school computer room","nowhere outside homes","only in storybooks"]),("What does a mouse help a user do?","point and select items",["print paper by itself","make electricity","store food"]),("Which device can take a digital photograph?","camera",["speaker","printer","keyboard"])]
    elif topic=="Online safety":items=[("Which information should be kept private online?","home address",["favourite colour","a made-up game name","the weather"]),("What should a child do if an online message makes them worried?","tell a trusted adult",["reply with personal details","keep it secret forever","meet the sender alone"]),("Which password is safer?","a long password known only to the user and adult carer",["1234","password","the child's first name"]),("How should people behave online?","kindly and respectfully",["share other people's secrets","send hurtful messages","pretend rules do not apply"]),("Before clicking an unfamiliar link, what should a child do?","ask a trusted adult",["enter an address and password","download everything","forward it to strangers"])]
    else:raise ValueError(f"Unknown Year 1 Computing topic: {topic}")
    return render_homework("Computing",1,topic,index,_repeat(items,rng,index))


def _year2(topic,index):
    rng=stable_random("Computing",2,topic,index)
    if topic=="Programs and debugging":items=[("A program should move 3 steps but moves 2. What should be checked?","the sequence of commands",["the colour of the table","the weather","the user's shoes"]),("What is a bug?","an error in a program",["an insect inside every computer","a finished algorithm","a saved picture"]),("Which action is part of debugging?","test, find the error, change the command, test again",["guess and never test","delete the goal","add unrelated commands"]),("Which program reaches a square 2 steps ahead?","forward, forward",["turn left, stop","forward, turn right","backward, backward"]),("Why test a program?","to check whether it works as intended",["to make the screen larger","to hide mistakes","to avoid using instructions"])]
    elif topic=="Logical prediction":items=[("A sprite follows: move 2, turn right, move 1. What happens first?","It moves 2 steps.",["It turns left.","It moves 1 step.","It stops forever."]),("A loop says 'clap' 3 times. How many claps occur?","3",["1","2","4"]),("Which prediction uses logical reasoning?","The sprite will stop because the next command is stop.",["The sprite will become a real animal.","The program will guess a new goal.","The screen will turn into paper."]),("What comes next in the repeating command pattern: forward, right, forward, right, ...?","forward",["left","stop","backward"]),("If a condition is 'if touching red, stop' and the sprite touches red, what happens?","It stops.",["It speeds up.","It changes into a file.","Nothing can be predicted."])]
    elif topic=="Creating and organising content":items=[("Which filename is clearest for a poster about bees?","bees_poster",["file1","stuff","untitled"]),("Which tool changes the size of text?","font size control",["volume control","camera shutter","power cable"]),("Why use folders?","to group related files",["to make files impossible to find","to delete all work","to change pictures into sound"]),("Which action retrieves digital content?","open a saved file",["throw away the device","erase the storage","close every app"]),("Which app is suitable for combining text and pictures in a poster?","presentation or publishing app",["calculator only","clock only","torch app"])]
    elif topic=="Information technology uses":items=[("How can a barcode scanner help a shop?","identify products quickly",["grow food","drive every customer home","replace all prices with guesses"]),("How can a hospital use IT?","store and access patient records securely",["publish private records publicly","avoid checking identity","remove all medical information"]),("Which technology helps traffic lights change in sequence?","a programmed control system",["a paper book","a paintbrush","a non-digital ruler"]),("What is one use of a satellite navigation system?","give route directions",["cook food","print books without a printer","measure body temperature"]),("Why do libraries use computer systems?","to record loans and find books",["to make books invisible","to remove authors' names","to stop people reading"])]
    elif topic=="Online privacy and reporting":items=[("Which detail should not be posted publicly by a child?","school address and daily route",["favourite book","favourite animal","a made-up character"]),("What should you do if someone asks for a password?","do not share it and tell a trusted adult",["send it immediately","post it publicly","use the same password everywhere"]),("Where can a child report worrying online content?","to a trusted adult and the platform's report tool",["only to the stranger who posted it","nowhere","in a public comment with private details"]),("What does respectful online behaviour include?","asking permission before sharing someone's photo",["sharing photos secretly","writing hurtful comments","copying private messages"]),("Why log out of a shared device?","to protect the account",["to make the device heavier","to delete the internet","to increase screen brightness"])]
    else:raise ValueError(f"Unknown Year 2 Computing topic: {topic}")
    return render_homework("Computing",2,topic,index,_repeat(items,rng,index))


def _ks2_items(year,topic):
    banks={
      "Sequence and repetition":[("Which construct repeats instructions?","loop",["variable","file","network"]),("What does this algorithm output: repeat 4 times [print star]?","four stars",["one star","three stars","five stars"]),("Why use repetition?","to avoid writing the same commands many times",["to remove every command","to make results random","to prevent testing"]),("Which program draws a square?","repeat 4 times [move, turn 90°]",["repeat 3 times [move, turn 90°]","move once","turn 45° twice"]),("What is sequence in programming?","instructions carried out in a chosen order",["a password","a network cable","a picture format"])],
      "Input and output":[("Which is an input?","a button press",["a sound from a speaker","a picture on a screen","a printed page"]),("Which is an output?","a message shown on screen",["a key press","a mouse click","a temperature sensor reading entering a program"]),("A temperature sensor provides what?","input data",["a paper output","a password","a folder"]),("Which output could warn a user?","an alarm sound",["a button press","typing a letter","moving a mouse"]),("Why use input in a program?","to let data or user actions affect what happens",["to make every run identical with no data","to remove all outputs","to stop the program being tested"])],
      "Computer networks":[("What is a computer network?","connected devices that can share data and resources",["one device with no connections","a printed map","a programming error"]),("What does a router help do?","direct data between networks",["type documents","draw pictures by hand","store food"]),("What is the internet?","a global network of networks",["one website","one computer","a word-processing app"]),("Which is a service provided through a network?","email",["a wooden ruler","a paper notebook","a non-digital clock"]),("Why might a school use a network?","to share files and printers securely",["to publish every private file","to stop devices communicating","to remove user accounts"])] ,
      "Search basics":[("Which search phrase is most specific?","Roman roads in Britain for children",["roads","things","internet"]),("What should a user check in search results?","whether the result is relevant and trustworthy",["only the first result's colour","whether it has the longest title","whether it agrees with every guess"]),("Why do search engines use keywords?","to match a query with relevant pages",["to turn websites into paper","to hide all results","to remove the internet"]),("Which action improves a search?","add precise subject words",["remove every useful word","type random letters","share a password"]),("Is every search result equally reliable?","No",["Yes","Only if it has pictures","Only the shortest result"])],
      "Digital creation":[("Which software is best for making a slide presentation?","presentation software",["calculator only","clock only","file bin"]),("Why combine text, images and charts?","to communicate information clearly",["to hide the purpose","to make data impossible to read","to avoid an audience"]),("Which chart suits comparing categories?","bar chart",["unordered sentence","password list","blank page"]),("What should be checked before using an online image?","permission or licence",["whether it is the first image","whether it is very large","whether nobody knows the creator"]),("Why evaluate a finished digital product?","to see whether it meets the goal and audience needs",["to avoid improvements","to delete the goal","to stop saving work"])],
      "Safe and responsible use":[("Which behaviour is responsible?","use kind language and report concerns",["share passwords","post private details","ignore harmful content"]),("What is personal data?","information that can identify a person",["a fictional dragon's colour","a public weather forecast","a maths fact"]),("What should happen before sharing another person's work?","ask permission and credit the creator",["remove their name","claim it as your own","publish it secretly"]),("What is a strong response to cyberbullying?","save evidence, block or report, and tell a trusted adult",["reply with more bullying","share private details","keep it secret"]),("Why use privacy settings?","to control who can see information",["to make passwords public","to disable all safety tools","to guarantee all content is true"])],
      "Selection and variables":[("Which construct makes a choice?","selection",["sequence only","file storage","network cable"]),("What does a variable store?","a value that a program can use or change",["only a picture on paper","a permanent hardware fault","a network address only"]),("What happens in: if score > 10 then print 'win', when score is 12?","win is printed",["nothing is printed","lose is printed","the score becomes zero"]),("Which condition is true when lives = 0?","lives equals 0",["lives is greater than 0","lives equals 3","there is no variable"]),("Why use selection in a quiz?","to respond differently to correct and incorrect answers",["to repeat forever only","to remove all inputs","to prevent decisions"])] ,
      "Debugging and decomposition":[("What is decomposition?","breaking a problem into smaller parts",["making a problem less clear","deleting the goal","joining every task into one unexplained step"]),("Which method helps locate a bug?","test one part at a time",["change everything at once","never run the program","ignore the output"]),("A loop runs one time too many. What is most likely wrong?","the repeat count",["the screen colour","the filename","the internet speed"]),("Why predict before testing?","to compare expected and actual behaviour",["to guarantee no bugs","to avoid understanding the algorithm","to remove evidence"]),("What should happen after a bug is fixed?","test the program again",["assume it works","delete the program","remove the goal"])] ,
      "Internet and the World Wide Web":[("How is the Web related to the internet?","The Web is a service that uses the internet.",["They are exactly the same thing.","The internet is one web page.","The Web is a physical keyboard."]),("What is a web browser?","software used to access web pages",["a network cable","a paper book","a printer cartridge"]),("Where are web pages commonly stored?","web servers",["only on the user's screen","inside a mouse","in a paper folder"]),("Which internet service supports live video calls?","video conferencing",["a non-digital ruler","a local paintbrush","a printed timetable"]),("What does a hyperlink do?","connects to another page or resource",["turns off a router","creates a password","deletes a website"])] ,
      "Search results and reliability":[("Why can search results appear in a particular order?","search systems rank results using many signals",["results are always random","the alphabet decides every search","the user has already read them"]),("Which source is usually best for a school's opening time?","the school's official website",["an anonymous old comment","an unrelated advert","a fictional story"]),("What does 'cross-check' mean?","compare information with another reliable source",["copy the first result","ignore the author","share it without reading"]),("Which clue may reduce reliability?","no author, date or evidence for a strong claim",["clear sources and recent date","an official organisation","evidence linked in the article"]),("Why distinguish fact from opinion?","opinions express viewpoints while facts can be checked",["all opinions are facts","facts never need evidence","viewpoints cannot be discussed"])] ,
      "Data presentation":[("Which chart is best for comparing class survey categories?","bar chart",["paragraph only","password table","blank slide"]),("What should a chart axis include?","a clear label and suitable scale",["a secret password","random colours only","no units ever"]),("Why validate entered data?","to find impossible or incorrect values",["to guarantee a preferred result","to remove every unusual result","to avoid checking"]),("Which formula finds a total in a spreadsheet?","SUM",["PRINT","DRAW","LOGIN"]),("What is a database record?","a set of fields about one item",["one letter in a password","a network cable","an animation frame"])] ,
      "Online behaviour":[("Which message is acceptable?","I disagree, but here is my reason.",["You are stupid.","I will share your address.","Everyone should bully them."]),("What should be reported?","threatening or harmful contact",["a normal school reminder","a saved homework file","a weather forecast"]),("Why credit online sources?","to acknowledge the creator and avoid plagiarism",["to hide where information came from","to claim the work","to make the source less reliable"]),("What is phishing?","an attempt to trick someone into giving sensitive information",["a method for drawing charts","a safe school login","a type of printer"]),("Which action protects an account?","use a unique strong password and multi-factor authentication when available",["reuse 1234 everywhere","share login details","leave a shared device signed in"])] ,
    }
    # Later-year topic aliases reuse and deepen the closest statutory bank.
    mapping={
      "Designing programs for goals":"Debugging and decomposition","Sequence selection and repetition":"Selection and variables","Variables input and output":"Selection and variables","Networks and internet services":"Internet and the World Wide Web","Evaluating digital content":"Search results and reliability","Combining software and data":"Data presentation","Privacy and security":"Online behaviour",
      "Decomposition and efficient solutions":"Debugging and decomposition","Explaining and correcting algorithms":"Debugging and decomposition","Programming constructs":"Selection and variables","Networks communication and collaboration":"Internet and the World Wide Web","Search and source evaluation":"Search results and reliability","Data systems":"Data presentation","Responsible technology use":"Online behaviour",
    }
    key=mapping.get(topic,topic)
    if key not in banks:raise ValueError(f"Unknown KS2 Computing topic: {topic}")
    items=list(banks[key])
    # Add age-appropriate depth for Years 5-6 without moving into KS3-only content.
    if year>=5 and key=="Selection and variables":
        items += [("What is the output of: set total = 4; repeat 3 times [total = total + 2]?","10",["6","8","12"]),("Which construct is best for repeating until a goal is reached?","a condition-controlled loop",["a filename","a static image","a network cable"])]
    if year>=5 and key=="Debugging and decomposition":
        items += [("Which solution is usually easier to test?","separate small modules with clear purposes",["one unexplained block of commands","a program with no goal","random commands copied together"]),("What makes an algorithm efficient?","it solves the problem using appropriate steps and resources",["it is always the longest","it uses no input","it cannot be explained"])]
    return items


def _ks2(year,topic,index):
    rng=stable_random("Computing",year,topic,index)
    return render_homework("Computing",year,topic,index,_repeat(_ks2_items(year,topic),rng,index))


def generate_computing_homework(year_group:int,topic:str,index:int)->tuple[str,list[str]]:
    canonical=TOPIC_ALIASES.get(topic,topic)
    if year_group==1:return _year1(canonical,index)
    if year_group==2:return _year2(canonical,index)
    if year_group in {3,4,5,6}:return _ks2(year_group,canonical,index)
    raise ValueError("year_group must be between 1 and 6")


def generate_year_homework(year_group:int,count:int=500)->list:
    topics=COMPUTING_TOPICS_BY_YEAR.get(year_group,[]);config=YEAR_CONFIG.get(year_group)
    if not topics or not config:return []
    batch=[]
    for i in range(1,count+1):
        topic=topics[(i-1)%len(topics)];content,answers=generate_computing_homework(year_group,topic,i)
        batch.append(build_batch_item(content=content,answers=answers,year_group=year_group,subject="Computing",topic=topic,homework_minutes=config["homework_minutes"],key_stage=config["key_stage"],doc_id=f"computing_y{year_group}_{i:04d}"))
        if i%100==0:print(f"  Generated {i}/{count}")
    return batch


def main():
    store=get_homework_rag_store();print(f"RAG target: {store.store.database_target}")
    for year in range(1,7):
        expected=HOMEWORK_COUNT[year];existing=count_year_homework(store,year,"Computing")
        if existing>=expected:
            print(f"Year {year}: complete ({existing}/{expected})");continue
        data=generate_year_homework(year,expected);added=add_homework_in_batches(store,data)
        print(f"Year {year}: added {added}; target {len(data)}")
    get_rag_stats(store)


if __name__=="__main__":main()
