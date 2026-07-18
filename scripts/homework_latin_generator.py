#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate age-appropriate Latin homework for England Years 1-6. Years 1-2 are optional enrichment; Years 3-6 follow the KS2 ancient-language focus on reading comprehension, linguistic foundations and appreciation of classical civilisation.

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

LATIN_TOPICS_BY_YEAR = {1: ['Greetings and simple words', 'Numbers and Roman numerals', 'Family words', 'Roman objects and places'],
 2: ['Animals', 'Everyday nouns', 'Latin roots in English', 'Roman daily life'],
 3: ['Pronunciation and reading', 'Nouns as subjects', 'Present-tense verbs', 'Roman Britain'],
 4: ['Subjects and objects', 'Adjective agreement', 'Plural forms', 'Reading simple sentences'],
 5: ['Verb endings', 'Noun patterns', 'Prepositions', 'Roman civilisation'],
 6: ['Translation strategies',
     'Time and tense clues',
     'Longer sentences',
     'Classical civilisation and legacy']}

YEAR_CONFIG = {
    1: {"key_stage": "KS1" if False else "Optional enrichment", "homework_minutes": "10-15" if False else "5-10"},
    2: {"key_stage": "KS1" if False else "Optional enrichment", "homework_minutes": "10-15" if False else "5-10"},
    3: {"key_stage": "KS2", "homework_minutes": "15-20" if False else "10-15"},
    4: {"key_stage": "KS2", "homework_minutes": "15-20"},
    5: {"key_stage": "KS2", "homework_minutes": "20-25"},
    6: {"key_stage": "KS2", "homework_minutes": "20-25"},
}

QUESTION_BANKS = {1: {'Family words': [("What does 'mater' mean?", 'mother', ['father', 'sister', 'brother']),
                      ("What does 'pater' mean?", 'father', ['mother', 'son', 'daughter']),
                      ("What does 'frater' mean?", 'brother', ['sister', 'uncle', 'grandfather']),
                      ("What does 'soror' mean?", 'sister', ['brother', 'mother', 'friend']),
                      ("What does 'familia' mean?", 'household or family', ['school', 'army', 'market'])],
     'Greetings and simple words': [("What does 'salve' mean when speaking to one person?", 'hello', ['goodbye', 'thank you', 'please']),
                                    ("What does 'vale' mean when speaking to one person?", 'goodbye', ['hello', 'yes', 'friend']),
                                    ("What does 'gratias' express in 'gratias tibi ago'?", 'thanks', ['anger', 'a question', 'a number']),
                                    ("What does 'amicus' mean?", 'male friend', ['teacher', 'house', 'road']),
                                    ("What does 'aqua' mean?", 'water', ['fire', 'earth', 'air'])],
     'Numbers and Roman numerals': [('What number does Roman numeral I represent?', '1', ['5', '10', '50']),
                                    ('What number does Roman numeral V represent?', '5', ['1', '10', '100']),
                                    ('What number does Roman numeral X represent?', '10', ['5', '50', '100']),
                                    ("What does Latin 'unus' mean?", 'one', ['two', 'three', 'ten']),
                                    ("What does Latin 'duo' mean?", 'two', ['one', 'four', 'five'])],
     'Roman objects and places': [("What does 'via' mean?", 'road', ['house', 'river', 'food']),
                                  ("What does 'casa' mean?", 'house', ['ship', 'wall', 'field']),
                                  ("What does 'forum' refer to in a Roman town?",
                                   'public square and meeting place',
                                   ['private bedroom', 'farm field', 'military helmet']),
                                  ("What does 'templum' mean?", 'temple', ['shop', 'bridge', 'school bag']),
                                  ("What does 'gladius' mean?", 'sword', ['shield', 'shoe', 'book'])]},
 2: {'Animals': [("What does 'canis' mean?", 'dog', ['cat', 'horse', 'bird']),
                 ("What does 'equus' mean?", 'horse', ['dog', 'fish', 'rabbit']),
                 ("What does 'avis' mean?", 'bird', ['cow', 'pig', 'lion']),
                 ("What does 'piscis' mean?", 'fish', ['bird', 'dog', 'wolf']),
                 ("What does 'leo' mean?", 'lion', ['horse', 'bear', 'goat'])],
     'Everyday nouns': [("What does 'liber' mean in the sense of an object for reading?", 'book', ['child', 'free person', 'tree']),
                        ("What does 'mensa' mean?", 'table', ['chair', 'door', 'window']),
                        ("What does 'porta' mean?", 'gate or door', ['road', 'cup', 'garden']),
                        ("What does 'panis' mean?", 'bread', ['milk', 'cheese', 'apple']),
                        ("What does 'sol' mean?", 'sun', ['moon', 'star', 'cloud'])],
     'Latin roots in English': [("Which English word comes from Latin 'aqua' meaning water?", 'aquarium', ['aviation', 'audience', 'annual']),
                                ("Which English word is linked to Latin 'terra' meaning earth or land?",
                                 'territory',
                                 ['telescope', 'temperature', 'triangle']),
                                ("Which English word is linked to Latin 'portare' meaning to carry?",
                                 'transport',
                                 ['telephone', 'tropical', 'texture']),
                                ("Which English word is linked to Latin 'scribere' meaning to write?",
                                 'describe',
                                 ['decimal', 'distance', 'domestic']),
                                ("Which English word is linked to Latin 'audire' meaning to hear?",
                                 'audience',
                                 ['aquatic', 'agriculture', 'architecture'])],
     'Roman daily life': [('Where did Romans often go to wash, exercise and meet others?',
                           'public baths',
                           ['airports', 'cinemas', 'railway stations']),
                          ('What was a Roman aqueduct built to carry?', 'water', ['soldiers', 'grain only', 'messages']),
                          ('What was a toga?', 'a garment worn by some Roman citizens', ['a shield', 'a house', 'a cooking pot']),
                          ('What was an amphitheatre used for?',
                           'public spectacles and entertainment',
                           ['growing crops', 'storing water', 'teaching only']),
                          ('What was a Roman insula?', 'a block of flats or apartment building', ['a palace only', 'a temple', 'a bridge'])]},
 3: {'Nouns as subjects': [("In 'puella currit', who is running?", 'the girl', ['the boy', 'the dog', 'the teacher']),
                           ("What does 'puer' mean?", 'boy', ['girl', 'man', 'woman']),
                           ("What does 'puella' mean?", 'girl', ['boy', 'mother', 'queen']),
                           ("In 'canis latrat', what is the subject?", 'canis', ['latrat', 'there is no subject', 'both words are verbs']),
                           ('What does the subject of a sentence do?',
                            'performs or experiences the action',
                            ['always receives the action', 'only gives the time', 'shows punctuation'])],
     'Present-tense verbs': [("What does 'currit' mean?", 'he, she or it runs', ['they run', 'I run', 'to run']),
                             ("What does 'amat' mean?", 'he, she or it loves', ['they love', 'we love', 'to love']),
                             ("What does 'videt' mean?", 'he, she or it sees', ['they see', 'I see', 'to see']),
                             ("What does 'audit' mean?", 'he, she or it hears', ['they hear', 'we hear', 'to hear']),
                             ("What does 'portat' mean?", 'he, she or it carries', ['they carry', 'I carry', 'to carry'])],
     'Pronunciation and reading': [('In classroom Latin, every written vowel should usually be...',
                                    'noticed and pronounced clearly',
                                    ['always silent', 'changed into English spelling', 'read as a number']),
                                   ('Which Latin word has three syllables?', 'familia', ['rex', 'sol', 'nox']),
                                   ('Why is reading Latin aloud useful?',
                                    'it helps connect spelling, sound and meaning',
                                    ['it removes the need to understand words', 'it changes noun endings', 'it proves every translation']),
                                   ("Which letter combination in 'regina' is pronounced with a hard g in classical Latin?",
                                    'g',
                                    ['gi as English j', 'reg as French', 'the g is silent']),
                                   ('What should a reader do first with an unfamiliar Latin sentence?',
                                    'look for known words and endings',
                                    ['translate only the first letter', 'ignore the verb', 'guess from punctuation alone'])],
     'Roman Britain': [('What was the Latin name for Britain?', 'Britannia', ['Gallia', 'Italia', 'Hispania']),
                       ("What does 'via Romana' mean?", 'Roman road', ['Roman house', 'Roman bath', 'Roman army']),
                       ('Why did Romans build roads in Britain?',
                        'to move soldiers, messages and goods efficiently',
                        ['to mark time zones', 'to stop all trade', 'to grow crops']),
                       ("What was Hadrian's Wall?",
                        'a frontier structure in northern Britain',
                        ['an aqueduct in Rome', 'a temple in Athens', 'a road in Egypt']),
                       ('Which language influenced many English words after Roman contact and later learning?',
                        'Latin',
                        ['Mayan', 'Old Norse only', 'Mandarin only'])]},
 4: {'Adjective agreement': [("Choose the correct phrase for 'a good girl'.", 'puella bona', ['puella bonus', 'puer bona', 'puellam bonus']),
                             ("Choose the correct phrase for 'a good boy'.", 'puer bonus', ['puer bona', 'puella bonus', 'puer bonum']),
                             ("Choose the correct phrase for 'a large temple'.",
                              'templum magnum',
                              ['templum magnus', 'templum magna', 'templa magnus']),
                             ('Why do Latin adjectives change their endings?',
                              'to agree with the noun in gender, number and case',
                              ['to show punctuation only', 'to mark every verb tense', 'to replace the noun']),
                             ('Which pair agrees correctly?', 'regina laeta', ['regina laetus', 'rex laeta', 'templum laetus'])],
     'Plural forms': [("What does 'puellae' mean when it is nominative plural?", 'girls', ['girl', 'of the girl', 'to the girl']),
                      ("What does 'pueri' mean when it is nominative plural?", 'boys', ['boy', 'the boy as object', 'with the boy']),
                      ("What does 'currunt' mean?", 'they run', ['he runs', 'I run', 'to run']),
                      ("What does 'amant' mean?", 'they love', ['she loves', 'we love', 'to love']),
                      ("In 'pueri laborant', who works?", 'the boys', ['the girl', 'the teacher', 'one boy'])],
     'Reading simple sentences': [("Translate: 'puella canem videt'.",
                                   'The girl sees the dog.',
                                   ['The dog sees the girl.', 'The girl hears the dog.', 'The boy sees the dog.']),
                                  ("Translate: 'puer aquam bibit'.",
                                   'The boy drinks water.',
                                   ['The boy carries water.', 'The girl drinks water.', 'The water sees the boy.']),
                                  ("Translate: 'canis currit'.", 'The dog runs.', ['The dog sleeps.', 'The dogs run.', 'The girl runs.']),
                                  ("Translate: 'mater panem parat'.",
                                   'The mother prepares bread.',
                                   ['The mother eats an apple.', 'The father prepares bread.', 'The bread prepares the mother.']),
                                  ("Translate: 'servi laborant'.",
                                   'The enslaved men work.',
                                   ['The enslaved man works.', 'The girls work.', 'The men sleep.'])],
     'Subjects and objects': [('Which case commonly marks the subject in Latin?', 'nominative', ['accusative', 'genitive', 'ablative']),
                              ('Which case commonly marks the direct object?', 'accusative', ['nominative', 'vocative', 'dative only']),
                              ("In 'puella aquam portat', what is carried?", 'water', ['the girl', 'a dog', 'a road']),
                              ("Which form is the accusative singular of 'puella'?", 'puellam', ['puella', 'puellae', 'puellarum']),
                              ("Which form is the accusative singular of 'puer'?", 'puerum', ['puer', 'pueri', 'pueris'])]},
 5: {'Noun patterns': [('What is a declension?', 'a pattern of noun endings', ['a verb tense', 'a punctuation system', 'a Roman building']),
                       ('Which pair shows nominative then accusative singular for a first-declension noun?',
                        'puella, puellam',
                        ['puellam, puella', 'puellae, puellas', 'puellarum, puellis']),
                       ("Which pair shows nominative then accusative singular for 'servus'?",
                        'servus, servum',
                        ['servum, servus', 'servi, servos', 'servo, servi']),
                       ('Why are noun endings important in Latin?',
                        "they show a word's role in the sentence",
                        ['word order alone always shows every role', 'they only show pronunciation', 'they replace verbs']),
                       ("Which form most likely means 'the girls' as a direct object?", 'puellas', ['puellae', 'puella', 'puellam'])],
     'Prepositions': [("What does 'ad' commonly mean?", 'to or towards', ['with', 'without', 'under']),
                      ("What does 'cum' commonly mean?", 'with', ['to', 'against', 'after']),
                      ("What does 'in villa' mean when describing location?",
                       'in the house or country house',
                       ['into the house', 'from the house', 'around the house']),
                      ("What does 'ad forum' mean?", 'to the forum', ['in the forum', 'with the forum', 'from the forum']),
                      ("Which phrase means 'with a friend'?", 'cum amico', ['ad amicum', 'in amicum', 'sine amicus'])],
     'Roman civilisation': [('What was the Roman Forum?',
                             'a centre for public, political and commercial life',
                             ['a private bedroom', 'a farm tool', 'a frontier wall']),
                            ('What did aqueducts supply to towns?', 'water', ['electricity', 'coal', 'paper']),
                            ('What was a legion?', 'a large unit of the Roman army', ['a temple priest', 'a market stall', 'a family meal']),
                            ('What happened at Pompeii in AD 79?',
                             'Mount Vesuvius erupted and buried the town',
                             ["Hadrian's Wall was built", 'Rome was founded', 'Britain left the empire']),
                            ('Which Roman building was used for chariot racing?', 'circus', ['basilica', 'aqueduct', 'insula'])],
     'Verb endings': [("What does the ending '-o' often show in a present-tense verb such as 'amo'?", 'I', ['you singular', 'he or she', 'they']),
                      ("What does the ending '-s' often show in 'amas'?", 'you singular', ['I', 'we', 'they']),
                      ("What does the ending '-t' often show in 'amat'?", 'he, she or it', ['I', 'you plural', 'they']),
                      ("What does the ending '-mus' often show in 'amamus'?", 'we', ['I', 'he', 'they']),
                      ("What does the ending '-nt' often show in 'amant'?", 'they', ['we', 'you singular', 'he'])]},
 6: {'Classical civilisation and legacy': [('Which modern language group developed directly from spoken Latin?',
                                            'Romance languages',
                                            ['Germanic languages only', 'Slavic languages only', 'Celtic languages only']),
                                           ('Which English field uses many Latin terms?',
                                            'law, medicine and science',
                                            ['only playground games', 'only weather forecasts', 'none']),
                                           ("What does 'SPQR' refer to?",
                                            'the Senate and People of Rome',
                                            ['a Roman number', 'a type of sword', 'a road measurement']),
                                           ('Why is Roman architecture influential?',
                                            'features such as arches, domes and columns inspired later buildings',
                                            ['Romans invented every modern building',
                                             'Roman buildings used no engineering',
                                             'architecture had no later impact']),
                                           ('Why can Latin support reading unfamiliar English words?',
                                            'many English words contain Latin roots and prefixes',
                                            ['English and Latin are identical', 'Latin has no word families', 'every English word is Latin'])],
     'Longer sentences': [("Translate: 'puella, quae in villa habitat, librum legit'.",
                           'The girl, who lives in the house, reads a book.',
                           ['The book lives in the house.', 'The girl writes a house.', 'The house reads the girl.']),
                          ("What does 'sed' mean?", 'but', ['and', 'because', 'therefore']),
                          ("What does 'quia' mean?", 'because', ['but', 'or', 'then']),
                          ("Translate: 'puer ad forum currit quod amicum videt'.",
                           'The boy runs to the forum because he sees a friend.',
                           ['The friend runs from the forum.', 'The boy hears a friend at home.', 'The forum sees the boy.']),
                          ("Which word commonly joins two equal ideas and means 'and'?", 'et', ['sed', 'quia', 'non'])],
     'Time and tense clues': [("What does 'heri' mean?", 'yesterday', ['today', 'tomorrow', 'always']),
                              ("What does 'hodie' mean?", 'today', ['yesterday', 'tomorrow', 'never']),
                              ("What does 'cras' mean?", 'tomorrow', ['today', 'yesterday', 'often']),
                              ("Which verb form means 'he or she was carrying'?", 'portabat', ['portat', 'portabit', 'portare']),
                              ("Which verb form means 'he or she will carry'?", 'portabit', ['portat', 'portabat', 'portavit only'])],
     'Translation strategies': [('What should be identified early in a Latin sentence?',
                                 'the main verb and its ending',
                                 ['only the longest noun', 'only the first word', 'the English word order']),
                                ('Why should a translator check noun endings?',
                                 "to identify each noun's role",
                                 ['to choose the prettiest word', 'to ignore the verb', 'to remove uncertainty completely']),
                                ('What is the best use of a Latin dictionary?',
                                 'look up the base form and choose a meaning that fits the context',
                                 ['copy the first meaning without reading', 'search only inflected endings', 'ignore parts of speech']),
                                ('Why should a translation sound natural in English?',
                                 'it should communicate the Latin meaning clearly',
                                 ['it must copy Latin word order exactly', 'it should add new events', 'it should remove every subject']),
                                ('What should happen after a first translation?',
                                 'check it against every Latin word and ending',
                                 ['submit without rereading', 'delete the verb', 'change all nouns to plural'])]}}


def _repeat(items, rng, index):
    questions = []
    for offset in range(10):
        stem, answer, distractors = items[(offset + index) % len(items)]
        questions.append(make_mcq(stem, answer, distractors, rng))
    return questions


def generate_latin_homework(
    year_group: int,
    topic: str,
    index: int,
) -> tuple[str, list[str]]:
    if year_group not in LATIN_TOPICS_BY_YEAR:
        raise ValueError("year_group must be between 1 and 6")
    if topic not in LATIN_TOPICS_BY_YEAR[year_group]:
        raise ValueError(f"Unknown Year {year_group} Latin topic: {topic}")

    items = QUESTION_BANKS[year_group][topic]
    rng = stable_random("Latin", year_group, topic, index)
    note = "Optional language enrichment for Years 1-2; foreign languages are statutory from KS2." if year_group in {1, 2} else ""
    return render_homework(
        "Latin",
        year_group,
        topic,
        index,
        _repeat(items, rng, index),
        note=note,
    )


def generate_year_homework(year_group: int, count: int = 300) -> list:
    topics = LATIN_TOPICS_BY_YEAR.get(year_group, [])
    config = YEAR_CONFIG.get(year_group)
    if not topics or not config:
        return []

    batch = []
    for index in range(1, count + 1):
        topic = topics[(index - 1) % len(topics)]
        content, answers = generate_latin_homework(year_group, topic, index)
        batch.append(
            build_batch_item(
                content=content,
                answers=answers,
                year_group=year_group,
                subject="Latin",
                topic=topic,
                homework_minutes=config["homework_minutes"],
                key_stage=config["key_stage"],
                doc_id=f"latin_y{year_group}_{index:04d}",
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
        existing = count_year_homework(store, year_group, "Latin")
        if existing >= expected:
            print(f"Year {year_group}: complete ({existing}/{expected})")
            continue
        homework = generate_year_homework(year_group, expected)
        added = add_homework_in_batches(store, homework)
        print(f"Year {year_group}: added {added}; target {len(homework)}")
    get_rag_stats(store)


if __name__ == "__main__":
    main()
