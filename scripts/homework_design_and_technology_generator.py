#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate objective Design and Technology homework for England Years 1-6, covering design, make, evaluate, technical knowledge, cooking and nutrition.

The public generation and review contract is unchanged: each worksheet contains
10 numbered four-option questions and returns a positional list of 10 exact
answers for storage in ``correct_answers`` by ``src/homework_rag.py``.
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
from scripts.homework_generator_utils import (
    add_homework_in_batches,
    build_batch_item,
    count_year_homework,
    get_rag_stats,
    make_mcq,
    render_homework,
    stable_random,
)

os.environ["TOKENIZERS_PARALLELISM"] = "false"

HOMEWORK_COUNT = {1: 500, 2: 500, 3: 800, 4: 800, 5: 1000, 6: 1000}

DESIGN_AND_TECHNOLOGY_TOPICS_BY_YEAR = {1: ['Designing for a user', 'Tools materials and safety', 'Structures', 'Healthy food'],
 2: ['Mechanisms', 'Joining materials', 'Textiles and templates', 'Where food comes from'],
 3: ['Design criteria and prototypes', 'Shell structures', 'Levers and linkages', 'Seasonal ingredients'],
 4: ['Electrical circuits and switches',
     'Textile fastenings',
     'Strengthening structures',
     'Cooking techniques'],
 5: ['Gears pulleys and cams', 'Frame structures', 'Product evaluation', 'Nutrition and recipes'],
 6: ['Programmed products', 'Electrical systems', 'Sustainable design', 'Safe food preparation']}

YEAR_CONFIG = {
    1: {"key_stage": "KS1" if True else "Optional enrichment", "homework_minutes": "10-15" if True else "5-10"},
    2: {"key_stage": "KS1" if True else "Optional enrichment", "homework_minutes": "10-15" if True else "5-10"},
    3: {"key_stage": "KS2", "homework_minutes": "15-20" if True else "10-15"},
    4: {"key_stage": "KS2", "homework_minutes": "15-20"},
    5: {"key_stage": "KS2", "homework_minutes": "20-25"},
    6: {"key_stage": "KS2", "homework_minutes": "20-25"},
}

QUESTION_BANKS = {1: {'Designing for a user': [('Who is the user of a product?',
                               'the person who will use it',
                               ['the person who drew the classroom map', 'only the shop owner', 'the material it is made from']),
                              ('What does purpose mean in design?',
                               'what a product is meant to do',
                               ['the colour of every product', 'the price only', "the designer's age"]),
                              ('Which is a design criterion for a lunchbox?',
                               'It must keep food safely inside.',
                               ['It must be made without measuring.', 'It must have no lid.', 'It must be too heavy to carry.']),
                              ('Why might a designer draw more than one idea?',
                               'to compare possible solutions',
                               ['because the first idea is always wrong', 'to avoid choosing a user', 'to make the page full']),
                              ('Which product is designed to help carry books?', 'school bag', ['plate', 'toothbrush', 'lamp shade'])],
     'Healthy food': [('Why should hands be washed before preparing food?',
                       'to reduce germs',
                       ['to make food sweeter', 'to change the recipe', 'to cool the room']),
                      ('Which food is a fruit?', 'apple', ['carrot', 'bread', 'cheese']),
                      ('Which food is a vegetable?', 'carrot', ['banana', 'yoghurt', 'rice']),
                      ('Which choice makes a snack more varied?', 'apple slices with yoghurt', ['only sweets', 'only crisps', 'only fizzy drink']),
                      ('Where does milk originally come from?', 'an animal such as a cow', ['a tree', 'a mine', 'the sea'])],
     'Structures': [('What is a structure?', 'something made from parts that supports or contains', ['a colour pattern', 'a recipe', 'a sound']),
                    ('Which shape often helps make a frame strong?', 'triangle', ['open curve', 'single dot', 'spiral only']),
                    ('How can a paper tower be made more stable?',
                     'give it a wider base',
                     ['make the base narrower', 'put all weight at the top', 'remove every fold']),
                    ('What does stiff mean?', 'not easy to bend', ['easy to pour', 'soft and stretchy', 'transparent']),
                    ('Which object is a structure?', 'bridge', ['orange juice', 'paint colour', 'song'])],
     'Tools materials and safety': [('Which tool is used to measure a straight length?', 'ruler', ['glue stick', 'paintbrush', 'rolling pin']),
                                    ('Which tool is suitable for cutting paper safely in class?',
                                     'child-safe scissors',
                                     ['saw without supervision', 'sharp kitchen knife', 'drill']),
                                    ('Why should tools be carried carefully?',
                                     'to reduce the risk of injury',
                                     ['to make them heavier', 'to change their colour', 'to stop measuring']),
                                    ('Which material is flexible?', 'fabric', ['brick', 'thick glass', 'stone block']),
                                    ('Which material is waterproof?', 'plastic sheet', ['tissue paper', 'cotton wool', 'dry cardboard'])]},
 2: {'Joining materials': [('Which join is suitable for two pieces of paper?', 'glue tab', ['boiling', 'weaving metal', 'freezing']),
                           ('Which fastener can join card but still allow movement?', 'split pin', ['paint', 'chalk', 'flour']),
                           ('What should be done before gluing a final model?',
                            'test that the pieces fit',
                            ['soak the card in water', 'remove all measurements', 'paint the table']),
                           ('Which join is usually strongest for two pieces of fabric?',
                            'stitched seam',
                            ['pencil line', 'paper clip only', 'water']),
                           ('Why might masking tape be useful in a prototype?',
                            'it allows quick temporary joins',
                            ['it cooks ingredients', 'it measures mass', 'it powers a motor'])],
     'Mechanisms': [('Which mechanism turns around a fixed centre?', 'wheel and axle', ['glue tab', 'seam', 'fold']),
                    ('What does a slider do?',
                     'moves backwards and forwards along a path',
                     ['turns electricity into light', 'joins fabric with thread', 'stores food']),
                    ('What does a lever do?', 'moves around a pivot', ['melts plastic', 'measures temperature', 'makes fabric waterproof']),
                    ('What is a pivot?', 'the point a lever turns around', ['the end of a ruler', 'a type of fabric', 'a food ingredient']),
                    ('Which product commonly uses a wheel and axle?', 'toy car', ['paper envelope', 'fabric puppet', 'sandwich'])],
     'Textiles and templates': [('What is a textile?', 'fabric made from fibres', ['a metal gear', 'a glass cup', 'a wooden wheel']),
                                ('What is a template?',
                                 'a shape used as a guide for cutting or marking',
                                 ['a finished meal', 'an electrical switch', 'a moving axle']),
                                ('Why pin a paper template to fabric?',
                                 'to hold it in place while marking or cutting',
                                 ['to make the fabric waterproof', 'to change its colour', 'to sharpen scissors']),
                                ('What is a seam?',
                                 'a line where pieces of fabric are joined',
                                 ['a wheel centre', 'a paper fold only', 'a food label']),
                                ('Which tool is used to sew by hand?', 'needle', ['hammer', 'spanner', 'whisk'])],
     'Where food comes from': [('Which food is grown as a crop?', 'wheat', ['milk', 'egg', 'fish']),
                               ('Which food is reared on a farm?', 'chicken', ['apple', 'potato', 'rice']),
                               ('Which food may be caught from the sea?', 'fish', ['bread', 'cheese', 'carrot']),
                               ('What is flour commonly made from?', 'ground wheat', ['milk', 'eggs', 'fish']),
                               ('What ingredient is used to make yoghurt?', 'milk', ['wood', 'sand', 'paper'])]},
 3: {'Design criteria and prototypes': [('What are design criteria?',
                                         'clear requirements a product should meet',
                                         ['random colours chosen at the end', 'a list of tools only', 'the shop price']),
                                        ('What is a prototype?',
                                         'an early model used for testing',
                                         ['the final product sold to every user', 'a food group', 'a permanent building only']),
                                        ('Why test a prototype?',
                                         'to find problems and improve the design',
                                         ['to prove no changes are allowed', 'to avoid listening to users', 'to remove the purpose']),
                                        ('Which criterion is measurable?',
                                         'The box must hold six pencils.',
                                         ['The box should be nice.', 'The box should feel good.', 'The box should be interesting.']),
                                        ('What is an annotated sketch?',
                                         'a drawing with useful labels and notes',
                                         ['a drawing with no explanation', 'a photograph only', 'a list of ingredients'])],
     'Levers and linkages': [('What is a linkage?',
                              'connected levers that transfer movement',
                              ['a food ingredient', 'a textile pattern', 'a circuit bulb']),
                             ('What does an input movement do?',
                              'starts or controls the mechanism',
                              ["finishes the product's decoration", 'changes food flavour', 'measures voltage']),
                             ('What is the output movement?',
                              'the movement produced by the mechanism',
                              ['the drawing before making', 'the material list', 'the user interview']),
                             ('Which mechanism can make two parts move in opposite directions?',
                              'a simple linkage',
                              ['a fixed seam', 'a glued box', 'a recipe']),
                             ('Why use a split pin in a linkage?',
                              'it forms a pivot that can move',
                              ['it permanently blocks movement', 'it powers the mechanism', 'it cuts card'])],
     'Seasonal ingredients': [('What does seasonal food mean?',
                               'food grown or produced naturally at a certain time of year',
                               ['food eaten only at school', 'food with no ingredients', 'food that is always frozen']),
                              ('Which fruit is commonly harvested in the UK in autumn?', 'apple', ['pineapple', 'mango', 'banana']),
                              ('Why can seasonal produce need less long-distance transport?',
                               'it may be grown nearer when naturally available',
                               ['it is always made of metal', 'it never needs harvesting', 'it grows in shops']),
                              ('Which information belongs in a recipe?',
                               'ingredients and method',
                               ['only the product price', 'only a picture', "the designer's postcode"]),
                              ('Why weigh ingredients?',
                               'to use the planned amount',
                               ['to change their colour', 'to remove all germs', 'to make the bowl larger'])],
     'Shell structures': [('What is a shell structure?',
                           'a hollow structure with a thin outer surface',
                           ['a solid block with no inside', 'a fabric seam', 'a lever']),
                          ('Which object is a shell structure?', 'cardboard box', ['solid brick', 'metal rod', 'piece of string']),
                          ('How can card be made stiffer?',
                           'fold it into flanges or corrugations',
                           ['soak it in water', 'tear it into tiny pieces', 'remove every corner']),
                          ('What is a net?',
                           'a flat pattern that folds into a 3D shape',
                           ['a fishing tool only', 'a type of glue', 'a moving mechanism']),
                          ('Which net can form a cube?', 'six connected squares', ['one circle', 'two triangles only', 'one long line'])]},
 4: {'Cooking techniques': [('Which technique uses a knife to make small pieces?', 'chopping', ['grating', 'whisking', 'kneading']),
                            ('Which technique rubs food against a surface with sharp holes?', 'grating', ['boiling', 'folding', 'sieving']),
                            ('Which technique mixes quickly to add air?', 'whisking', ['peeling', 'slicing', 'baking']),
                            ('Why use a chopping board?',
                             'to provide a stable clean cutting surface',
                             ['to make food sweeter', 'to heat food', 'to weigh ingredients']),
                            ('Which instruction is safest when using a vegetable peeler?',
                             'peel away from fingers and body',
                             ['peel towards the hand', 'hold food in the air', 'use it without looking'])],
     'Electrical circuits and switches': [('What must a simple electrical circuit have to work?',
                                           'a complete closed path',
                                           ['a gap in every wire', 'only one loose wire', 'no power source']),
                                          ('What does a switch do?',
                                           'opens or closes a circuit',
                                           ['stores ingredients', 'cuts fabric', 'strengthens a beam']),
                                          ('Which component provides electrical energy in a simple model?',
                                           'cell or battery',
                                           ['bulb', 'buzzer', 'switch']),
                                          ('Which component produces light?', 'bulb or LED', ['motor', 'axle', 'pulley']),
                                          ('Which component produces movement?', 'motor', ['buzzer', 'switch', 'resistor only'])],
     'Strengthening structures': [('What does reinforce mean?',
                                   'add support to make something stronger',
                                   ['remove every support', 'make something transparent', 'decorate with one colour']),
                                  ('Which beam shape often resists bending better than a flat strip of the same card?',
                                   'folded I- or box-shaped beam',
                                   ['wet flat strip', 'single thread', 'open paper circle']),
                                  ('Why are triangles used in frameworks?',
                                   'their shape resists changing',
                                   ['they always roll', 'they contain no corners', 'they make materials softer']),
                                  ('What is a gusset?',
                                   'a piece added to strengthen a joint',
                                   ['a type of battery', 'a food seasoning', 'a textile fastener']),
                                  ('What should be tested on a model bridge?',
                                   'how much load it supports safely',
                                   ['how loudly it sounds only', 'how many colours it has', 'how quickly paint dries'])],
     'Textile fastenings': [('Which fastening can be opened and closed many times?', 'zip', ['permanent glue seam', 'paint', 'chalk line']),
                            ('Which fastening uses two matching strips that press together?',
                             'hook-and-loop tape',
                             ['buttonhole only', 'staple', 'paper glue']),
                            ('What is a buttonhole for?',
                             'allowing a button to pass through and fasten fabric',
                             ['holding a motor', 'measuring cloth', 'cutting thread']),
                            ('Why add a seam allowance to a pattern piece?',
                             'to leave fabric for joining',
                             ['to make the design smaller than planned', 'to remove the edge', 'to colour the fabric']),
                            ('Which stitch is commonly used for a strong simple hand-sewn seam?',
                             'backstitch',
                             ['random loop', 'no stitch', 'paint line'])]},
 5: {'Frame structures': [('What is a frame structure?',
                           'a structure made from joined supporting members',
                           ['a hollow skin only', 'a solid block', 'a textile bag']),
                          ('Which part of a frame helps stop it from swaying sideways?', 'diagonal brace', ['paint layer', 'label', 'wheel']),
                          ('What is triangulation?',
                           'using triangles to make a framework rigid',
                           ['making every piece circular', 'removing joints', 'adding water']),
                          ('Why make accurate cuts in a frame?',
                           'joints fit properly and loads transfer safely',
                           ['colour becomes brighter', 'the frame weighs nothing', 'no testing is needed']),
                          ('Which structure is mainly a frame structure?', 'bicycle frame', ['cardboard carton', 'ceramic bowl', 'plastic bottle'])],
     'Gears pulleys and cams': [('What do meshing gears do?',
                                 'transfer rotary movement',
                                 ['join fabric', 'store electricity', 'measure temperature']),
                                ('If a small gear drives a larger gear, the larger gear usually turns...',
                                 'more slowly',
                                 ['more quickly', 'at exactly twice the speed always', 'not at all']),
                                ('What does a pulley use to transfer movement or lift loads?',
                                 'a wheel with a rope or belt',
                                 ['a fabric seam', 'a shell net', 'a battery only']),
                                ('What does a cam change rotary movement into?',
                                 'reciprocating or oscillating movement',
                                 ['electrical energy', 'heat only', 'a fixed joint']),
                                ('What is a follower in a cam mechanism?',
                                 'the part moved by the cam',
                                 ['the power source', 'the product user', 'the design criterion'])],
     'Nutrition and recipes': [("Which nutrient is the body's main source of energy?",
                                'carbohydrate',
                                ['water only', 'vitamin C only', 'fibre only']),
                               ('Which nutrient supports growth and repair?', 'protein', ['salt', 'sugar', 'water vapour']),
                               ('Why is fibre important?',
                                'it supports healthy digestion',
                                ['it powers electrical circuits', 'it replaces all water', 'it makes food metal']),
                               ('What does a balanced diet include?',
                                'a variety of foods in suitable proportions',
                                ['only one food group', 'only sugary foods', 'no fruit or vegetables']),
                               ('Why should a recipe state serving size?',
                                'to show how many portions the quantities make',
                                ['to set the oven colour', 'to name the designer', 'to remove measurements'])],
     'Product evaluation': [('Which question best evaluates fitness for purpose?',
                             'Does the product do the job safely for its intended user?',
                             ["Is it the designer's favourite colour?", 'Was it made on a Tuesday?', 'Does it use the most materials?']),
                            ('Why collect user feedback?',
                             "to identify improvements from the user's experience",
                             ['to prove the first idea is perfect', 'to avoid testing', 'to replace design criteria']),
                            ('What is a fair test?',
                             'a test where relevant conditions are kept consistent',
                             ['a test changed randomly each time', 'a test with no measurements', 'a test based only on guessing']),
                            ('Which result is quantitative evidence?',
                             'The bridge held 2 kilograms.',
                             ['The bridge looks good.', 'The user likes blue.', 'The model feels interesting.']),
                            ('What should happen after finding a weakness?',
                             'modify and retest the design',
                             ['hide the result', 'remove the criteria', 'stop recording evidence'])]},
 6: {'Electrical systems': [('In a series circuit, what happens if one connection is broken?',
                             'the whole circuit stops',
                             ['every component gets brighter', 'the battery charges itself', 'the motor becomes a switch']),
                            ('Which component can make sound?', 'buzzer', ['cell', 'wire', 'switch only']),
                            ('Why use a switch in a product?',
                             'to let the user control the circuit',
                             ['to strengthen the case', 'to measure fabric', 'to flavour food']),
                            ('What should be checked before connecting a motor?',
                             'its voltage and circuit arrangement are suitable',
                             ['its colour matches the box', 'its axle is made of paper only', 'the user has no need']),
                            ('Why insulate exposed wire connections?',
                             'to reduce accidental contact and short circuits',
                             ['to increase food temperature', 'to make gears turn', 'to decorate fabric'])],
     'Programmed products': [('What is an input in a programmed product?',
                              'information detected or entered',
                              ['the action produced at the end only', 'the product casing', 'the decoration']),
                             ('What is an output?',
                              'an action such as light, sound or movement',
                              ['a sensor reading only', 'a design sketch', 'a user need']),
                             ('Which component can detect light?', 'light sensor', ['motor', 'buzzer', 'axle']),
                             ('What does an algorithm provide?',
                              'ordered instructions for a system',
                              ['a random decoration', 'a food label', 'a material property']),
                             ('Why test a program with different inputs?',
                              'to check it responds correctly in varied conditions',
                              ['to avoid finding faults', 'to make the battery larger', 'to remove the user'])],
     'Safe food preparation': [('Why keep raw meat separate from ready-to-eat food?',
                                'to reduce cross-contamination',
                                ['to make both foods sweeter', 'to cool the kitchen', 'to change portion size']),
                               ('What is cross-contamination?',
                                'harmful microbes moving from one food or surface to another',
                                ['mixing two safe flavours', 'measuring ingredients', 'freezing water']),
                               ('Which food should be cooked thoroughly according to safe guidance?',
                                'poultry',
                                ['whole apple', 'bread roll', 'washed lettuce']),
                               ('Why check a food allergy before serving a dish?',
                                'some ingredients can cause a serious reaction',
                                ['all allergies are preferences', 'it changes the oven time only', 'it makes food cheaper']),
                               ('What should happen to chilled food that is not being prepared?',
                                'keep it refrigerated',
                                ['leave it in sunlight', 'place it beside a heater', 'store it uncovered on the floor'])],
     'Sustainable design': [('What does sustainable design aim to reduce?',
                             'harmful use of resources and environmental impact',
                             ['all product usefulness', 'all repair', 'all user feedback']),
                            ('Which material choice supports reuse?',
                             'a durable part that can be removed and used again',
                             ['a single-use mixed material that cannot be separated',
                              'extra packaging without purpose',
                              'a part designed to break quickly']),
                            ('What is a life cycle in product design?',
                             'stages from raw material to use and disposal',
                             ['one drawing lesson', 'the time a switch is pressed', 'a food recipe']),
                            ('Why design a product to be repairable?',
                             'it can last longer and create less waste',
                             ['it must be thrown away sooner', 'it uses more packaging', 'it prevents maintenance']),
                            ('Which choice may reduce transport impact?',
                             'using suitable locally available materials',
                             ['shipping tiny parts separately from far away', 'adding unnecessary weight', 'using more packaging'])]}}


def _repeat(items, rng, index):
    questions = []
    for offset in range(10):
        stem, answer, distractors = items[(offset + index) % len(items)]
        questions.append(make_mcq(stem, answer, distractors, rng))
    return questions


def generate_design_and_technology_homework(
    year_group: int,
    topic: str,
    index: int,
) -> tuple[str, list[str]]:
    if year_group not in DESIGN_AND_TECHNOLOGY_TOPICS_BY_YEAR:
        raise ValueError("year_group must be between 1 and 6")
    if topic not in DESIGN_AND_TECHNOLOGY_TOPICS_BY_YEAR[year_group]:
        raise ValueError(f"Unknown Year {year_group} Design and Technology topic: {topic}")

    items = QUESTION_BANKS[year_group][topic]
    rng = stable_random("Design and Technology", year_group, topic, index)
    note = ""
    return render_homework(
        "Design and Technology",
        year_group,
        topic,
        index,
        _repeat(items, rng, index),
        note=note,
    )


def generate_year_homework(year_group: int, count: int = 300) -> list:
    topics = DESIGN_AND_TECHNOLOGY_TOPICS_BY_YEAR.get(year_group, [])
    config = YEAR_CONFIG.get(year_group)
    if not topics or not config:
        return []

    batch = []
    for index in range(1, count + 1):
        topic = topics[(index - 1) % len(topics)]
        content, answers = generate_design_and_technology_homework(year_group, topic, index)
        batch.append(
            build_batch_item(
                content=content,
                answers=answers,
                year_group=year_group,
                subject="Design and Technology",
                topic=topic,
                homework_minutes=config["homework_minutes"],
                key_stage=config["key_stage"],
                doc_id=f"design_and_technology_y{year_group}_{index:04d}",
            )
        )
        if index % 100 == 0:
            print(f"  Generated {index}/{count}")
    return batch


def main():
    store = get_homework_rag_store()
    print(f"RAG target: {store.store.database_target}")
    for year_group in range(1, 7):
        expected = HOMEWORK_COUNT[year_group]
        existing = count_year_homework(store, year_group, "Design and Technology")
        if existing >= expected:
            print(f"Year {year_group}: complete ({existing}/{expected})")
            continue
        homework = generate_year_homework(year_group, expected)
        added = add_homework_in_batches(store, homework)
        print(f"Year {year_group}: added {added}; target {len(homework)}")
    get_rag_stats(store)


if __name__ == "__main__":
    main()
