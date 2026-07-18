#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate age-appropriate French homework for England Years 1-6. Years 1-2 are optional enrichment; Years 3-6 follow the KS2 foreign-language emphasis on phonology, vocabulary, grammar, reading and practical communication.

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

FRENCH_TOPICS_BY_YEAR = {1: ['Greetings', 'Numbers 1-10', 'Colours', 'Classroom words'],
 2: ['Numbers 11-20', 'Family', 'Weather', 'Animals'],
 3: ['French sounds and greetings', 'Dates and birthdays', 'People and descriptions', 'Likes and dislikes'],
 4: ['Daily routine and time', 'Food and drink', 'Town and directions', 'Adjective agreement'],
 5: ['Common present-tense verbs', 'School and leisure', 'Opinions and reasons', 'Short reading'],
 6: ['Near future', 'Past and future time phrases', 'Reading comprehension', 'French-speaking world']}

YEAR_CONFIG = {
    1: {"key_stage": "KS1" if False else "Optional enrichment", "homework_minutes": "10-15" if False else "5-10"},
    2: {"key_stage": "KS1" if False else "Optional enrichment", "homework_minutes": "10-15" if False else "5-10"},
    3: {"key_stage": "KS2", "homework_minutes": "15-20" if False else "10-15"},
    4: {"key_stage": "KS2", "homework_minutes": "15-20"},
    5: {"key_stage": "KS2", "homework_minutes": "20-25"},
    6: {"key_stage": "KS2", "homework_minutes": "20-25"},
}

QUESTION_BANKS = {1: {'Classroom words': [("What does 'livre' mean?", 'book', ['pencil', 'chair', 'door']),
                         ('How do you say pencil in French?', 'crayon', ['table', 'livre', 'chaise']),
                         ("What does 'écoutez' mean?", 'listen', ['write', 'run', 'sleep']),
                         ('Which word means table?', 'table', ['porte', 'fenêtre', 'sac']),
                         ("What does 'regardez' mean?", 'look', ['sit', 'eat', 'close'])],
     'Colours': [("What colour is 'rouge'?", 'red', ['blue', 'green', 'yellow']),
                 ('How do you say blue in French?', 'bleu', ['vert', 'rouge', 'noir']),
                 ("What colour is 'vert'?", 'green', ['orange', 'white', 'pink']),
                 ('How do you say yellow in French?', 'jaune', ['violet', 'blanc', 'gris']),
                 ("What colour is 'noir'?", 'black', ['white', 'brown', 'purple'])],
     'Greetings': [("What does 'bonjour' mean?", 'hello or good morning', ['goodbye', 'thank you', 'please']),
                   ("Which French word means 'goodbye'?", 'au revoir', ['bonjour', 'merci', 'oui']),
                   ("What does 'merci' mean?", 'thank you', ['hello', 'no', 'good night']),
                   ("Which phrase means 'my name is...'?", "je m'appelle...", ['comment ça va ?', 'à bientôt', "s'il vous plaît"]),
                   ("What does 's'il vous plaît' mean?", 'please', ['sorry', 'yes', 'see you tomorrow'])],
     'Numbers 1-10': [("What number is 'un'?", '1', ['2', '3', '10']),
                      ('How do you say 5 in French?', 'cinq', ['quatre', 'six', 'dix']),
                      ("What number is 'huit'?", '8', ['6', '7', '9']),
                      ('How do you say 10 in French?', 'dix', ['deux', 'trois', 'neuf']),
                      ('Which sequence is correct?', 'un, deux, trois', ['un, trois, deux', 'deux, un, quatre', 'trois, un, deux'])]},
 2: {'Animals': [("What animal is 'chat'?", 'cat', ['dog', 'fish', 'bird']),
                 ('How do you say dog in French?', 'chien', ['oiseau', 'poisson', 'lapin']),
                 ("What animal is 'poisson'?", 'fish', ['horse', 'rabbit', 'cow']),
                 ('How do you say bird in French?', 'oiseau', ['chat', 'cochon', 'cheval']),
                 ("What animal is 'lapin'?", 'rabbit', ['cow', 'pig', 'cat'])],
     'Family': [("What does 'mère' mean?", 'mother', ['father', 'sister', 'brother']),
                ('How do you say father in French?', 'père', ['grand-mère', 'sœur', 'tante']),
                ("What does 'frère' mean?", 'brother', ['sister', 'grandfather', 'cousin']),
                ('How do you say grandmother in French?', 'grand-mère', ['grand-père', 'mère', 'cousine']),
                ("What does 'famille' mean?", 'family', ['school', 'house', 'friend'])],
     'Numbers 11-20': [("What number is 'douze'?", '12', ['11', '13', '20']),
                       ('How do you say 15 in French?', 'quinze', ['quatorze', 'seize', 'cinq']),
                       ("What number is 'dix-huit'?", '18', ['16', '17', '19']),
                       ('How do you say 20 in French?', 'vingt', ['neuf', 'dix', 'dix-neuf']),
                       ("Which comes after 'treize'?", 'quatorze', ['douze', 'quinze', 'onze'])],
     'Weather': [("What does 'il fait beau' mean?", 'the weather is fine', ['it is raining', 'it is cold', 'it is windy']),
                 ("How do you say 'it is raining'?", 'il pleut', ['il neige', 'il fait chaud', 'il fait beau']),
                 ("What does 'il fait froid' mean?", 'it is cold', ['it is hot', 'it is sunny', 'it is cloudy']),
                 ("How do you say 'it is windy'?", 'il y a du vent', ['il fait beau', 'il pleut', 'il neige']),
                 ("What does 'il neige' mean?", 'it is snowing', ['it is raining', 'it is hot', 'it is foggy'])]},
 3: {'Dates and birthdays': [("What does 'lundi' mean?", 'Monday', ['Tuesday', 'month', 'morning']),
                             ("Which month is 'janvier'?", 'January', ['June', 'July', 'December']),
                             ("What does 'mon anniversaire' mean?", 'my birthday', ['my school', 'my family', 'my holiday']),
                             ("How do you say 'the first of May'?", 'le premier mai', ['le un mai', 'mai premier le', 'le mai un']),
                             ("What number is 'trente'?", '30', ['13', '20', '40'])],
     'French sounds and greetings': [("Which reply matches 'Comment t'appelles-tu ?'?",
                                      "Je m'appelle Sam.",
                                      ["J'ai neuf ans.", "J'habite à Londres.", "J'aime le tennis."]),
                                     ("What does 'Comment ça va ?' mean?",
                                      'How are you?',
                                      ['What is your name?', 'How old are you?', 'Where do you live?']),
                                     ("Which phrase means 'See you soon'?", 'À bientôt', ['Bonjour', 'Merci', 'Pardon']),
                                     ("Which reply matches 'Ça va bien ?'?",
                                      'Oui, ça va bien.',
                                      ["Je m'appelle Alex.", "J'ai un chien.", 'Il pleut.']),
                                     ('In French, many final consonants are...',
                                      'often not pronounced',
                                      ['always pronounced twice', 'always stressed', 'changed into vowels'])],
     'Likes and dislikes': [("What does 'j'aime' mean?", 'I like', ['I dislike', 'I have', 'I am']),
                            ("What does 'je n'aime pas' mean?", 'I do not like', ['I love', 'I can', 'I want']),
                            ("Which phrase means 'I love music'?",
                             "J'adore la musique.",
                             ['Je déteste la musique.', "J'ai la musique.", 'Je suis musique.']),
                            ("What does 'parce que' mean?", 'because', ['but', 'and', 'also']),
                            ('Which sentence gives a reason?',
                             "J'aime le sport parce que c'est amusant.",
                             ["J'aime le sport.", 'Le sport amusant.', 'Parce que sport.'])],
     'People and descriptions': [("What does 'grand' mean when describing a boy or man?", 'tall', ['small', 'kind', 'young']),
                                 ("What is the feminine form of 'petit'?", 'petite', ['petits', 'petites', 'petito']),
                                 ("Which phrase means 'brown hair'?", 'les cheveux bruns', ['les yeux bleus', 'les cheveux longs', 'les yeux verts']),
                                 ("What does 'sympathique' mean?", 'friendly or nice', ['angry', 'old', 'short']),
                                 ("Which sentence means 'She is funny'?", 'Elle est drôle.', ['Il est drôle.', 'Elle a drôle.', 'Elle drôle est.'])]},
 4: {'Adjective agreement': [("Choose the correct phrase for 'a small girl'.",
                              'une petite fille',
                              ['une petit fille', 'un petite fille', 'une fille petit']),
                             ("What is the feminine form of 'grand'?", 'grande', ['grands', 'grandes', 'grando']),
                             ("Choose the correct phrase for 'two black cats'.",
                              'deux chats noirs',
                              ['deux chats noir', 'deux chattes noir for male cats', 'deux noirs chat']),
                             ("Which adjective agrees with 'les voitures'?", 'rouges', ['rouge', 'rougeses', 'rougeo']),
                             ("Choose the correct phrase for 'the white house'.",
                              'la maison blanche',
                              ['la maison blanc', 'le maison blanche', 'la blanche maison always'])],
     'Daily routine and time': [("What does 'je me lève' mean?", 'I get up', ['I go to bed', 'I eat lunch', 'I go home']),
                                ("How do you say 'I go to school'?", "Je vais à l'école.", ['Je suis école.', "J'ai l'école.", 'Je faire école.']),
                                ("What time is 'huit heures'?", "8 o'clock", ["7 o'clock", "9 o'clock", "10 o'clock"]),
                                ("What does 'le matin' mean?", 'in the morning', ['in the evening', 'at night', 'at midday']),
                                ("Which phrase means 'after school'?", "après l'école", ["avant l'école", "à l'école", "dans l'école"])],
     'Food and drink': [("What does 'pain' mean?", 'bread', ['milk', 'cheese', 'water']),
                        ('How do you say water in French?', 'eau', ['lait', 'jus', 'soupe']),
                        ("What does 'pomme' mean?", 'apple', ['pear', 'orange', 'banana']),
                        ("Which phrase means 'I would like...'?", 'Je voudrais...', ['Je vais...', "J'ai...", 'Je suis...']),
                        ("What does 'délicieux' mean?", 'delicious', ['expensive', 'cold', 'small'])],
     'Town and directions': [("What does 'la gare' mean?", 'station', ['school', 'shop', 'park']),
                             ("How do you say 'turn left'?", 'tournez à gauche', ['tournez à droite', 'allez tout droit', 'arrêtez']),
                             ("What does 'tout droit' mean?", 'straight ahead', ['to the left', 'behind', 'near']),
                             ("Which word means 'library'?", 'bibliothèque', ['boulangerie', 'piscine', 'mairie']),
                             ("What does 'près de' mean?", 'near', ['far from', 'opposite', 'between'])]},
 5: {'Common present-tense verbs': [("Choose the correct form: 'I speak'.", 'je parle', ['tu parles', 'il parle', 'nous parlons']),
                                    ("What does 'nous avons' mean?", 'we have', ['I have', 'they have', 'you have singular']),
                                    ("Choose the correct form: 'They play'.", 'ils jouent', ['il joue', 'nous jouons', 'jouer']),
                                    ("What does 'je peux' mean?", 'I can', ['I want', 'I must', 'I know']),
                                    ("Which infinitive means 'to eat'?", 'manger', ['mange', 'manges', 'mangeons'])],
     'Opinions and reasons': [("What does 'je pense que c'est utile' mean?",
                               'I think it is useful',
                               ['I know it is easy', 'I do not like it', 'It is always useful']),
                              ("Which phrase means 'because it is exciting'?",
                               "parce que c'est passionnant",
                               ["mais c'est passionnant", 'aussi passionnant', 'passionnant parce only']),
                              ("How do you say 'In my opinion'?", 'À mon avis', ['Chez moi', 'Le matin', 'Parfois']),
                              ("What does 'je préfère' mean?", 'I prefer', ['I promise', 'I practise', 'I prepare']),
                              ('Choose the best justified opinion.',
                               "J'aime les sciences parce que c'est intéressant.",
                               ["J'aime les sciences.", 'Les sciences parce que.', 'Intéressant sciences moi.'])],
     'School and leisure': [("What does 'ma matière préférée' mean?", 'my favourite subject', ['my school bag', 'my classroom', 'my timetable']),
                            ("How do you say 'I play football'?",
                             'Je joue au football.',
                             ['Je fais le football.', 'Je vais football.', 'Je suis football.']),
                            ("What does 'le week-end' mean?", 'at the weekend', ['on Monday', 'in summer', 'after school only']),
                            ("Which sentence means 'I read books in my free time'?",
                             'Je lis des livres pendant mon temps libre.',
                             ["J'écris des livres en classe.", "J'ai du temps et des livres.", 'Les livres lisent mon temps.']),
                            ("How do you say 'homework'?", 'les devoirs', ['la récréation', 'la cantine', "l'uniforme"])],
     'Short reading': [("Read: 'Lucie habite à Lyon et va à l'école en bus.' Where does Lucie live?", 'Lyon', ['Paris', 'London', 'Nice']),
                       ("Read: 'Le samedi, je joue au tennis avec mon frère.' When does the speaker play tennis?",
                        'on Saturday',
                        ['on Sunday', 'every morning', 'on Monday']),
                       ("Read: 'Mon chien est petit, blanc et très gentil.' What colour is the dog?", 'white', ['black', 'brown', 'grey']),
                       ("Read: 'Je préfère les pommes parce qu'elles sont bonnes pour la santé.' Why are apples preferred?",
                        'because they are healthy',
                        ['because they are expensive', 'because they are blue', 'because they are hot']),
                       ("Read: 'Demain, nous allons voyager en avion.' How will they travel?", 'by plane', ['by train', 'by bus', 'on foot'])]},
 6: {'French-speaking world': [('What is the capital of France?', 'Paris', ['Lyon', 'Marseille', 'Bordeaux']),
                               ('Which country has French and English as federal official languages?', 'Canada', ['Brazil', 'Japan', 'Portugal']),
                               ('Which European country uses French as one of its official languages?',
                                'Belgium',
                                ['Italy only', 'Greece', 'Poland']),
                               ('Which African country uses French as an official language?', 'Senegal', ['Egypt only', 'Ethiopia', 'Somalia']),
                               ("What does 'la francophonie' refer to?",
                                'French-speaking people and places around the world',
                                ['France only', 'one French city', 'a type of food'])],
     'Near future': [("What does 'je vais étudier' mean?", 'I am going to study', ['I studied', 'I study every day', 'I do not study']),
                     ("Choose the correct near-future form: 'We are going to travel'.",
                      'Nous allons voyager.',
                      ['Nous voyageons hier.', 'Aller voyager nous.', 'Nous allons voyager à.']),
                     ("What does 'il va pleuvoir' mean?", 'it is going to rain', ['it rained', 'it rains every day', 'it is sunny']),
                     ('Which sentence is present tense?',
                      'Je joue au football le mardi.',
                      ['Je vais jouer demain.', "J'ai joué hier.", 'Jouer au football.']),
                     ('Which time phrase matches the near future?', 'demain', ['hier', "l'année dernière", 'avant'])],
     'Past and future time phrases': [("What does 'hier' mean?", 'yesterday', ['tomorrow', 'today', 'next week']),
                                      ("Which phrase means 'last weekend'?",
                                       'le week-end dernier',
                                       ['le week-end prochain', 'ce week-end', 'chaque week-end']),
                                      ("What does 'la semaine prochaine' mean?", 'next week', ['last week', 'this morning', 'yesterday']),
                                      ('Which sentence refers to the past?',
                                       "Hier, j'ai visité un musée.",
                                       ['Demain, je vais visiter un musée.', 'Je visite des musées le samedi.', 'Je vais au musée maintenant.']),
                                      ('Which sentence refers to the future?',
                                       'Samedi, nous allons jouer.',
                                       ['Samedi dernier, nous avons joué.', 'Nous jouons chaque samedi.', 'Hier, nous avons joué.'])],
     'Reading comprehension': [("Read: 'Même s'il pleuvait, Marie est allée au parc parce qu'elle voulait courir.' Why did Marie go to the park?",
                                'because she wanted to run',
                                ['because it was sunny', 'because she lost a book', 'because she wanted to swim']),
                               ("Read: 'Paul économise pour acheter un nouveau vélo.' What is Paul saving for?",
                                'a new bicycle',
                                ['a computer', 'a holiday', 'a football']),
                               ("Read: 'Le train est parti en retard, donc nous sommes arrivés à neuf heures.' Why did they arrive at nine?",
                                'the train left late',
                                ['they missed the bus', 'the station closed', 'they walked slowly']),
                               ("Read: 'Ana préfère vivre à la campagne parce que c'est calme.' Where does Ana prefer to live?",
                                'in the countryside',
                                ['in a city centre', 'near an airport', 'at school']),
                               ("Read: 'Après le dîner, j'ai fini mes devoirs et j'ai regardé un film.' What happened first?",
                                'the speaker had dinner',
                                ['the speaker watched a film', 'the speaker finished homework', 'the speaker went to school'])]}}


def _repeat(items, rng, index):
    questions = []
    for offset in range(10):
        stem, answer, distractors = items[(offset + index) % len(items)]
        questions.append(make_mcq(stem, answer, distractors, rng))
    return questions


def generate_french_homework(
    year_group: int,
    topic: str,
    index: int,
) -> tuple[str, list[str]]:
    if year_group not in FRENCH_TOPICS_BY_YEAR:
        raise ValueError("year_group must be between 1 and 6")
    if topic not in FRENCH_TOPICS_BY_YEAR[year_group]:
        raise ValueError(f"Unknown Year {year_group} French topic: {topic}")

    items = QUESTION_BANKS[year_group][topic]
    rng = stable_random("French", year_group, topic, index)
    note = "Optional language enrichment for Years 1-2; foreign languages are statutory from KS2." if year_group in {1, 2} else ""
    return render_homework(
        "French",
        year_group,
        topic,
        index,
        _repeat(items, rng, index),
        note=note,
    )


def generate_year_homework(year_group: int, count: int = 300) -> list:
    topics = FRENCH_TOPICS_BY_YEAR.get(year_group, [])
    config = YEAR_CONFIG.get(year_group)
    if not topics or not config:
        return []

    batch = []
    for index in range(1, count + 1):
        topic = topics[(index - 1) % len(topics)]
        content, answers = generate_french_homework(year_group, topic, index)
        batch.append(
            build_batch_item(
                content=content,
                answers=answers,
                year_group=year_group,
                subject="French",
                topic=topic,
                homework_minutes=config["homework_minutes"],
                key_stage=config["key_stage"],
                doc_id=f"french_y{year_group}_{index:04d}",
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
        existing = count_year_homework(store, year_group, "French")
        if existing >= expected:
            print(f"Year {year_group}: complete ({existing}/{expected})")
            continue
        homework = generate_year_homework(year_group, expected)
        added = add_homework_in_batches(store, homework)
        print(f"Year {year_group}: added {added}; target {len(homework)}")
    get_rag_stats(store)


if __name__ == "__main__":
    main()
