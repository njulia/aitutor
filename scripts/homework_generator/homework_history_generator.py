#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate objective History homework for England Years 1-6, covering chronological knowledge, British, local and world history, sources, enquiry and interpretation.

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

HOMEWORK_COUNT = {1: 500, 2: 500, 3: 800, 4: 800, 5: 1000, 6: 1000}

HISTORY_TOPICS_BY_YEAR = {1: ['Past and present',
     'Changes within living memory',
     'Significant people',
     'Historical sources and local history'],
 2: ['Great Fire of London', 'Early flight', 'Nurses and healthcare', 'Timelines and evidence'],
 3: ['Stone Age to Iron Age', 'Roman Britain', 'Ancient Egypt', 'Chronology and evidence'],
 4: ['Anglo-Saxons and Scots', 'Vikings', 'Ancient Greece', 'Local history study'],
 5: ['Maya civilisation', 'Baghdad around AD 900', 'Britain beyond 1066', 'Historical enquiry'],
 6: ['Benin Kingdom', 'Shang Dynasty', 'Monarchy and Parliament', 'Cause consequence and interpretation']}

YEAR_CONFIG = {
    1: {"key_stage": "KS1" if True else "Optional enrichment", "homework_minutes": "10-15" if True else "5-10"},
    2: {"key_stage": "KS1" if True else "Optional enrichment", "homework_minutes": "10-15" if True else "5-10"},
    3: {"key_stage": "KS2", "homework_minutes": "15-20" if True else "10-15"},
    4: {"key_stage": "KS2", "homework_minutes": "15-20"},
    5: {"key_stage": "KS2", "homework_minutes": "20-25"},
    6: {"key_stage": "KS2", "homework_minutes": "20-25"},
}

QUESTION_BANKS = {1: {'Changes within living memory': [('What does living memory mean?',
                                       'a time remembered by people alive today',
                                       ['all of prehistory', 'only the Roman period', 'a time before humans']),
                                      ("Which source can show how a local street changed during a grandparent's lifetime?",
                                       'dated photographs',
                                       ['a dinosaur fossil', 'a Roman mosaic', 'a fairy tale']),
                                      ('Which item has changed greatly within living memory?',
                                       'mobile phone',
                                       ['the number of continents', 'the shape of Earth', 'the existence of day and night']),
                                      ('Which question helps compare schools past and present?',
                                       'What equipment did pupils use?',
                                       ['Which planet is largest?', 'How deep is the ocean?', 'What is a triangle?']),
                                      ('Which statement describes change over time?',
                                       'Many homes now use digital devices that older homes did not have.',
                                       ['Every home has always been identical.',
                                        'Nothing changes within living memory.',
                                        'Only ancient history can change.'])],
     'Historical sources and local history': [('What is a historical source?',
                                               'evidence that helps us learn about the past',
                                               ['a prediction about tomorrow', 'a made-up answer', 'a map with no connection to the past']),
                                              ('Which is a primary source for a past event?',
                                               'an object made at the time',
                                               ['a textbook written much later', 'a modern film inspired by it', 'a recent worksheet']),
                                              ('Which place can help with local history?',
                                               'local museum',
                                               ['weather satellite only', 'airport departure board', 'online game score']),
                                              ('Why should a source have a date when possible?',
                                               'it helps place it in time',
                                               ['it proves every detail is true', 'it makes it larger', 'it changes the material']),
                                              ('Which question is about local history?',
                                               'How has our town centre changed?',
                                               ['How many oceans are there?', 'What is 7 × 8?', 'Which material is waterproof?'])],
     'Past and present': [('Which word means happening now?', 'present', ['past', 'ancient', 'future']),
                          ('Which word describes something that happened before now?', 'past', ['present', 'tomorrow', 'next']),
                          ('Which phrase usually refers to the most recent event?',
                           'yesterday',
                           ['a century ago', 'in ancient times', 'before writing']),
                          ('Which object is most likely from the present day?',
                           'smartphone',
                           ['Roman coin', 'Victorian slate', 'Stone Age hand axe']),
                          ('What does chronological order mean?',
                           'putting events in time order',
                           ['putting events in size order', 'grouping by colour', 'choosing a favourite'])],
     'Significant people': [('Who was the first person to walk on the Moon?',
                             'Neil Armstrong',
                             ['Tim Berners-Lee', 'William Caxton', 'Samuel Pepys']),
                            ('Who is associated with inventing the World Wide Web?',
                             'Tim Berners-Lee',
                             ['Neil Armstrong', 'Florence Nightingale', 'Christopher Columbus']),
                            ('Why is Rosa Parks historically significant?',
                             'her refusal to give up her bus seat became important in the US civil rights movement',
                             ['she invented the telephone', 'she was the first person on the Moon', "she built Hadrian's Wall"]),
                            ('What does historically significant mean?',
                             'important enough to help us understand the past',
                             ['the oldest person only', 'the richest person only', 'someone from a story with no evidence']),
                            ("Which source can tell us about a significant person's own words?",
                             'a letter or diary they wrote',
                             ['a random modern advert', 'an unlabeled stone', 'a weather forecast'])]},
 2: {'Early flight': [('Who made the first successful powered, controlled aeroplane flight in 1903?',
                       'the Wright brothers',
                       ['the Romans', 'the Vikings', 'the Tudors']),
                      ("Where did the Wright brothers' famous 1903 flight take place?", 'Kitty Hawk, North Carolina', ['London', 'Paris', 'Rome']),
                      ("What made the Wright brothers' flight historically important?",
                       'it was powered, controlled and sustained',
                       ['it used no wings', 'it crossed the Atlantic', 'it carried hundreds of passengers']),
                      ('Who flew solo from England to Australia in 1930?', 'Amy Johnson', ['Florence Nightingale', 'Mary Seacole', 'Rosa Parks']),
                      ('Which source would best show the shape of an early aeroplane?',
                       'a dated photograph',
                       ['a modern train timetable', 'a recipe', 'a weather symbol'])],
     'Great Fire of London': [('In which year did the Great Fire of London begin?', '1666', ['1066', '1766', '1966']),
                              ('Where did the Great Fire of London begin?',
                               'a bakery in Pudding Lane',
                               ['Buckingham Palace', 'the Tower of London moat', "St Paul's School"]),
                              ('Which factor helped the fire spread quickly?',
                               'many buildings were made of wood and stood close together',
                               ['heavy snow covered the city', 'all streets were very wide', 'every building had sprinklers']),
                              ('Whose diary is an important source about the fire?',
                               'Samuel Pepys',
                               ['Neil Armstrong', 'Alfred the Great', 'Julius Caesar']),
                              ('Which change followed the fire in rebuilding London?',
                               'more use of brick and stone',
                               ['all houses were rebuilt from straw', 'streets became narrower everywhere', 'fire safety was ignored'])],
     'Nurses and healthcare': [('Which nurse became known for improving hospital conditions during the Crimean War?',
                                'Florence Nightingale',
                                ['Queen Victoria', 'Amy Johnson', 'Emily Davison']),
                               ('Which nurse travelled to Crimea and cared for soldiers near the fighting?',
                                'Mary Seacole',
                                ['Rosa Parks', 'Edith Cavell', 'Boudica']),
                               ('Why were cleaner hospital wards important?',
                                'they reduced infection',
                                ['they made beds heavier', 'they changed the weather', 'they removed the need for doctors']),
                               ('Which source could show how a hospital ward looked in the past?',
                                'a contemporary drawing or photograph',
                                ['a modern shopping list', 'a fictional spell', 'a map of oceans']),
                               ('What is one similarity between Florence Nightingale and Mary Seacole?',
                                'both cared for sick and wounded people during the Crimean War',
                                ['both were astronauts', 'both ruled England', 'both invented aeroplanes'])],
     'Timelines and evidence': [('Which date comes first?', '1903', ['1930', '1969', '2000']),
                                ('What does decade mean?', '10 years', ['100 years', '1,000 years', '12 months']),
                                ('What does century mean?', '100 years', ['10 years', '50 years', '1,000 years']),
                                ('Why put events on a timeline?',
                                 'to show their order and distance in time',
                                 ['to prove one source is perfect', 'to sort by colour', 'to measure temperature']),
                                ('Which statement is evidence-based?',
                                 'A dated photograph shows the aircraft had two wings.',
                                 ['I imagine the aircraft was invisible.', 'Every old story must be exact.', 'Dates are not useful.'])]},
 3: {'Ancient Egypt': [('Which river was central to Ancient Egyptian farming?', 'Nile', ['Thames', 'Amazon', 'Danube']),
                       ('What was an Egyptian ruler called?', 'pharaoh', ['consul', 'emperor of Rome', 'prime minister']),
                       ('What were hieroglyphs?', 'a system of picture-like writing', ['Roman roads', 'Greek columns', 'Viking ships']),
                       ('Why were many pyramids built?', 'as tombs for rulers', ['as railway stations', 'as factories', 'as football grounds']),
                       ('What was mummification intended to preserve?', 'a dead body', ['a wooden boat only', 'a clay tablet', 'a city wall'])],
     'Chronology and evidence': [('Which event happened earliest?',
                                  'the first Stone Age communities',
                                  ['the Roman invasion of AD 43', 'the Viking raids', 'the Great Fire of London']),
                                 ('What does BC mean on a historical date?',
                                  'Before Christ',
                                  ['British Century', 'Before Clocks', 'Bronze Calendar']),
                                 ('What does AD traditionally label?',
                                  "years in the Common Era after the traditional date of Christ's birth",
                                  ['only years before the Stone Age', 'a type of artefact', 'an ancient map']),
                                 ('What is an artefact?',
                                  'an object made or used by people in the past',
                                  ['a weather event', 'a future plan', 'a natural mountain only']),
                                 ('Why compare more than one source?',
                                  'sources may provide different evidence or viewpoints',
                                  ['one source always contains everything', 'dates become unnecessary', 'objects cannot be evidence'])],
     'Roman Britain': [('Which Roman emperor ordered the successful invasion of Britain in AD 43?', 'Claudius', ['Augustus', 'Nero', 'Constantine']),
                       ('Who led a major rebellion against Roman rule in Britain?',
                        'Boudica',
                        ['Cleopatra', 'Florence Nightingale', 'Queen Victoria']),
                       ("What was Hadrian's Wall built to do?",
                        'help control the northern frontier of Roman Britain',
                        ['carry water to Rome', 'divide London after the fire', 'mark the Equator']),
                       ('Which feature did Roman rule spread in Britain?', 'roads and towns', ['steam railways', 'electric lighting', 'airports']),
                       ('Which source can reveal Roman daily life?',
                        'pottery and coins',
                        ['a modern bus ticket', 'a satellite forecast', 'a mobile phone'])],
     'Stone Age to Iron Age': [('Which period came first in Britain?', 'Stone Age', ['Bronze Age', 'Iron Age', 'Roman period']),
                               ('Bronze is mainly an alloy of which two metals?',
                                'copper and tin',
                                ['iron and gold', 'silver and lead', 'aluminium and steel']),
                               ('Which settlement is linked with Neolithic life in Britain?', 'Skara Brae', ['Pompeii', 'Baghdad', 'Athens']),
                               ('What were Iron Age hill forts?',
                                'defended settlements built on high ground',
                                ['Roman bathhouses', 'medieval castles with cannons', 'modern factories']),
                               ('Why is the period before writing called prehistory?',
                                'there are no written records from that society',
                                ['there were no people', 'nothing changed', 'only dinosaurs lived then'])]},
 4: {'Ancient Greece': [('What was a polis?', 'a Greek city-state', ['a Roman road', 'an Egyptian tomb', 'a Viking ship']),
                        ('Which city-state is associated with an early form of democracy?', 'Athens', ['Sparta only', 'Rome', 'Alexandria']),
                        ('Where were the ancient Olympic Games held?', 'Olympia', ['London', 'Pompeii', 'Carthage']),
                        ('Which structure is strongly associated with classical Greek architecture?',
                         'columned temple',
                         ['longship', 'hill fort', 'steam factory']),
                        ('Who could vote in ancient Athenian democracy?',
                         'adult male citizens',
                         ['all adults and children', 'enslaved people only', 'visitors from every country'])],
     'Anglo-Saxons and Scots': [('Around what time did Roman rule in Britain end?', 'AD 410', ['AD 43', '1066', '1666']),
                                ('From which areas did many Anglo-Saxon groups come?',
                                 'parts of present-day Germany, Denmark and the Netherlands',
                                 ['South America', 'Australia', 'southern Africa']),
                                ('What can place-name endings such as -ham and -ton suggest?',
                                 'Anglo-Saxon settlement',
                                 ['Roman numerals', 'modern airports', 'Viking longships only']),
                                ('What is Sutton Hoo famous for?',
                                 'an Anglo-Saxon ship burial',
                                 ['a Roman aqueduct', 'a Tudor palace', 'a Victorian railway']),
                                ('Which development helped spread Christianity in Anglo-Saxon England?',
                                 'missions and monasteries',
                                 ['steam engines', 'printing newspapers', 'air travel'])],
     'Local history study': [('Which source is especially useful for studying a local building?',
                              'plans, photographs and records from the area',
                              ['a map of another continent only', 'a Roman myth with no local link', 'a future weather forecast']),
                             ('What does continuity mean in history?',
                              'something that remains similar over time',
                              ['a sudden change only', 'a source with no date', 'a fictional event']),
                             ('Which question studies change in a locality?',
                              'How has the railway changed the town?',
                              ['What is the capital of France?', 'How many sides has a square?', 'What colour is blue?']),
                             ('Why visit a local historic site?',
                              'to observe physical evidence in its setting',
                              ['to guarantee every story is true', 'to replace all other sources', 'to avoid asking questions']),
                             ('Which evidence could show a local population grew?',
                              'census records from different dates',
                              ['one undated drawing', 'a recipe', 'a compass'])],
     'Vikings': [('Where did the Vikings come from?', 'Scandinavia', ['North Africa', 'South America', 'India']),
                 ('What type of ship helped Vikings travel quickly?', 'longship', ['steamship', 'submarine', 'aircraft carrier']),
                 ('What was the Danelaw?',
                  'an area of England under Danish law and influence',
                  ['a Roman road', 'a Greek city-state', 'a Victorian factory']),
                 ('Which English ruler is remembered for resisting Viking attacks?',
                  'Alfred the Great',
                  ['Henry VIII', 'Charles II', 'Julius Caesar']),
                 ('Why were monasteries often targets of early Viking raids?',
                  'they held valuables and were sometimes poorly defended',
                  ['they had airports', 'they were built underwater', 'they controlled Roman armies'])]},
 5: {'Baghdad around AD 900': [('Which empire ruled Baghdad around AD 900?', 'Abbasid Caliphate', ['Roman Empire', 'British Empire', 'Maya Empire']),
                               ('Which river flows through Baghdad?', 'Tigris', ['Thames', 'Nile', 'Seine']),
                               ('What was the House of Wisdom associated with?',
                                'learning, translation and scholarship',
                                ['Viking shipbuilding', 'Roman gladiators', 'Victorian factories']),
                               ('Why was Baghdad an important trading city?',
                                'it connected routes linking different regions',
                                ['it was isolated from all travel', 'it had no markets', 'it banned scholarship']),
                               ('Which subjects were studied by scholars in the Islamic world?',
                                'mathematics, medicine and astronomy',
                                ['only sport', 'only painting', 'no written subjects'])],
     'Britain beyond 1066': [('Which event in 1066 changed the ruling dynasty of England?',
                              'Norman Conquest',
                              ['Great Fire of London', 'Roman invasion', 'Industrial Revolution']),
                             ('What was one effect of the early railways?',
                              'people and goods could travel faster',
                              ['Roman rule returned', 'all roads disappeared', 'cities became smaller immediately']),
                             ('Which period saw rapid growth of factories and machine production?',
                              'Industrial Revolution',
                              ['Stone Age', 'Iron Age Britain only', 'Roman withdrawal']),
                             ('What was the Battle of Britain?',
                              'an air campaign in 1940',
                              ['a Viking raid in 793', 'a Roman invasion in AD 43', 'a fire in 1666']),
                             ('Which source could show working conditions in a Victorian factory?',
                              'reports, testimony and photographs',
                              ['a Stone Age hand axe only', 'a modern menu', 'a weather symbol'])],
     'Historical enquiry': [('What is a historical enquiry question?',
                             'a focused question investigated using evidence',
                             ['an answer chosen before looking', 'a random date', 'a fictional spell']),
                            ('What is reliability?',
                             'how far a source can be trusted for a particular question',
                             ['the size of a source', 'how colourful it is', 'whether it is old enough']),
                            ('Why consider who made a source?',
                             "the creator's purpose and viewpoint may affect it",
                             ['the creator never matters', 'it changes the date', 'it proves the source is false']),
                            ('What is corroboration?',
                             'checking evidence against other sources',
                             ['copying one source exactly', 'removing dates', 'using only opinions']),
                            ('Which response is best supported?',
                             'a claim linked to relevant evidence',
                             ['a guess with no source', 'a list of unrelated facts', 'a copied title only'])],
     'Maya civilisation': [('Where did the Maya civilisation develop?', 'Mesoamerica', ['northern Europe', 'Australia', 'southern Africa']),
                           ('What was a major Maya food crop?', 'maize', ['wheat only', 'rice only', 'potato only']),
                           ('How were many Maya communities organised?',
                            'as city-states',
                            ['as one modern nation-state', 'as Roman provinces', 'as Viking kingdoms']),
                           ('What kind of writing did the Maya use?',
                            'a glyph writing system',
                            ['only Roman numerals', 'no symbols at all', 'modern English alphabet only']),
                           ('Which evidence helps historians study Maya rulers?',
                            'carved stelae and inscriptions',
                            ['Victorian photographs', 'Roman road maps', 'modern train tickets'])]},
 6: {'Benin Kingdom': [('Where was the historic Kingdom of Benin located?',
                        'West Africa in present-day southern Nigeria',
                        ['South America', 'northern Europe', 'Australia']),
                       ('What title was used for the ruler of Benin?', 'Oba', ['pharaoh', 'consul', 'shogun']),
                       ('What are the Benin Bronzes?',
                        'metal plaques and sculptures made by skilled court artists',
                        ['coins from Roman Britain only', 'Victorian engines', 'Maya books']),
                       ('What do Benin artworks help historians study?',
                        'court life, rulers and beliefs',
                        ['Stone Age farming in Britain', 'Viking navigation only', 'the Great Fire']),
                       ("Which activity supported Benin's wealth and influence?",
                        'regional and long-distance trade',
                        ['complete isolation', 'steam railway building', 'Atlantic air travel'])],
     'Cause consequence and interpretation': [('What is a cause?',
                                               'something that helps make an event happen',
                                               ['what happens because of an event', 'a date only', 'a historical object']),
                                              ('What is a consequence?',
                                               'a result of an event or action',
                                               ['the reason before an event', 'a source creator', 'a timeline scale']),
                                              ('Why can historians produce different interpretations?',
                                               'they may select and weigh evidence differently',
                                               ['there is never any evidence', 'dates have no meaning', 'all interpretations are guesses']),
                                              ('Which statement explains significance?',
                                               'The event mattered because it changed laws for many people.',
                                               ['The event happened on a Tuesday.', 'The source is blue.', 'The person had a long name.']),
                                              ('Which answer best handles uncertainty?',
                                               'The evidence suggests this, but another source gives a different view.',
                                               ['This must be true because I prefer it.',
                                                'One source proves every detail.',
                                                'No source needs checking.'])],
     'Monarchy and Parliament': [('What was Magna Carta, agreed in 1215?',
                                  'a charter that limited some powers of the king',
                                  ['a Roman road map', 'a Viking ship law', 'a railway timetable']),
                                 ('What is Parliament?',
                                  'an institution that makes laws and holds government to account',
                                  ['a royal palace only', 'a type of army', 'a medieval market']),
                                 ('Which monarch reigned from 1837 to 1901?', 'Queen Victoria', ['Elizabeth I', 'Henry VIII', 'Anne']),
                                 ('What does constitutional change mean?',
                                  'change in how a country is governed',
                                  ['change in daily weather', 'change in river direction only', 'change in paint colour']),
                                 ('Which evidence could reveal changing voting rights?',
                                  'laws and election records from different dates',
                                  ['a Roman coin only', 'a landscape painting', 'a recipe'])],
     'Shang Dynasty': [('Where did the Shang Dynasty develop?', 'ancient China', ['ancient Greece', 'Roman Britain', 'Mesoamerica']),
                       ('Which site is linked with the late Shang capital?', 'Anyang', ['Athens', 'Baghdad', 'York']),
                       ('What were oracle bones used for?',
                        'recording questions and divination',
                        ['building roads', 'printing books', 'making sails']),
                       ('Which material were Shang craftspeople especially skilled at casting?', 'bronze', ['plastic', 'aluminium', 'concrete']),
                       ('What do oracle-bone inscriptions provide?',
                        'some of the earliest known Chinese writing',
                        ['Roman laws', 'Viking poems', 'Victorian census records'])]}}


def _repeat(items, rng, index):
    questions = []
    for offset in range(10):
        stem, answer, distractors = items[(offset + index) % len(items)]
        questions.append(make_mcq(stem, answer, distractors, rng))
    return questions


def generate_history_homework(
    year_group: int,
    topic: str,
    index: int,
) -> tuple[str, list[str]]:
    if year_group not in HISTORY_TOPICS_BY_YEAR:
        raise ValueError("year_group must be between 1 and 6")
    if topic not in HISTORY_TOPICS_BY_YEAR[year_group]:
        raise ValueError(f"Unknown Year {year_group} History topic: {topic}")

    items = QUESTION_BANKS[year_group][topic]
    rng = stable_random("History", year_group, topic, index)
    note = ""
    return render_homework(
        "History",
        year_group,
        topic,
        index,
        _repeat(items, rng, index),
        note=note,
    )


def generate_year_homework(year_group: int, count: int = 300) -> list:
    topics = HISTORY_TOPICS_BY_YEAR.get(year_group, [])
    config = YEAR_CONFIG.get(year_group)
    if not topics or not config:
        return []

    batch = []
    for index in range(1, count + 1):
        topic = topics[(index - 1) % len(topics)]
        content, answers = generate_history_homework(year_group, topic, index)
        batch.append(
            build_batch_item(
                content=content,
                answers=answers,
                year_group=year_group,
                subject="History",
                topic=topic,
                homework_minutes=config["homework_minutes"],
                key_stage=config["key_stage"],
                doc_id=f"history_y{year_group}_{index:04d}",
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
        existing = count_year_homework(store, year_group, "History")
        if existing >= expected:
            print(f"Year {year_group}: complete ({existing}/{expected})")
            continue
        homework = generate_year_homework(year_group, expected)
        added = add_homework_in_batches(store, homework)
        print(f"Year {year_group}: added {added}; target {len(homework)}")
    get_rag_stats(store)


if __name__ == "__main__":
    main()
