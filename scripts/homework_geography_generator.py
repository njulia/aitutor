#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate objective Geography homework for England Years 1-6, covering locational and place knowledge, physical and human geography, mapping and fieldwork.

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

GEOGRAPHY_TOPICS_BY_YEAR = {1: ['United Kingdom', 'Continents and oceans', 'Weather and seasons', 'Maps and directions'],
 2: ['UK seas and coasts', 'Hot and cold places', 'Human and physical features', 'Local fieldwork'],
 3: ['UK counties cities and regions', 'Europe', 'Rivers and the water cycle', 'Compass and grid basics'],
 4: ['North and South America',
     'Mountains volcanoes and earthquakes',
     'Settlements and land use',
     'Maps and grid references'],
 5: ['Latitude longitude and time zones',
     'Climate zones and biomes',
     'Trade and natural resources',
     'Comparing regions'],
 6: ['Physical and human interaction',
     'Changing landscapes',
     'Fieldwork and data',
     'World regions and location']}

YEAR_CONFIG = {
    1: {"key_stage": "KS1" if True else "Optional enrichment", "homework_minutes": "10-15" if True else "5-10"},
    2: {"key_stage": "KS1" if True else "Optional enrichment", "homework_minutes": "10-15" if True else "5-10"},
    3: {"key_stage": "KS2", "homework_minutes": "15-20" if True else "10-15"},
    4: {"key_stage": "KS2", "homework_minutes": "15-20"},
    5: {"key_stage": "KS2", "homework_minutes": "20-25"},
    6: {"key_stage": "KS2", "homework_minutes": "20-25"},
}

QUESTION_BANKS = {1: {'Continents and oceans': [('How many continents are there?', '7', ['5', '6', '8']),
                               ('Which continent is the United Kingdom in?', 'Europe', ['Asia', 'Africa', 'South America']),
                               ('Which is the largest ocean?', 'Pacific Ocean', ['Atlantic Ocean', 'Indian Ocean', 'Arctic Ocean']),
                               ('Which continent is at the South Pole?', 'Antarctica', ['Europe', 'Asia', 'Africa']),
                               ('Which ocean lies between the Americas and Europe and Africa?',
                                'Atlantic Ocean',
                                ['Pacific Ocean', 'Southern Ocean', 'Arctic Ocean'])],
     'Maps and directions': [('Which direction is opposite north?', 'south', ['east', 'west', 'north-east']),
                             ('Which direction is opposite east?', 'west', ['north', 'south', 'north-east']),
                             ('What does a map key explain?',
                              'what symbols mean',
                              ['the weather tomorrow', 'the age of the map reader', 'the price of the map']),
                             ('Which symbol might show a school on a simple map?',
                              'a symbol named in the key',
                              ['any random mark', 'a temperature number', 'a compass needle only']),
                             ('What is a route?',
                              'the path followed from one place to another',
                              ['the title of a map', 'a type of weather', 'a country'])],
     'United Kingdom': [('How many countries make up the United Kingdom?', '4', ['3', '5', '6']),
                        ('What is the capital city of England?', 'London', ['Edinburgh', 'Cardiff', 'Belfast']),
                        ('What is the capital city of Scotland?', 'Edinburgh', ['London', 'Cardiff', 'Belfast']),
                        ('What is the capital city of Wales?', 'Cardiff', ['Edinburgh', 'London', 'Belfast']),
                        ('What is the capital city of Northern Ireland?', 'Belfast', ['Cardiff', 'Edinburgh', 'London'])],
     'Weather and seasons': [('Which instrument measures temperature?', 'thermometer', ['rain gauge', 'wind vane', 'compass']),
                             ('Which instrument measures rainfall?', 'rain gauge', ['thermometer', 'clock', 'ruler']),
                             ('Which season comes after spring in the UK?', 'summer', ['winter', 'autumn', 'spring']),
                             ('Which weather word means water falling from clouds as drops?', 'rain', ['wind', 'fog', 'sunshine']),
                             ('Which season usually has the shortest days in the UK?', 'winter', ['summer', 'spring', 'autumn'])]},
 2: {'Hot and cold places': [('Which line circles Earth halfway between the poles?',
                              'Equator',
                              ['Prime Meridian', 'Arctic Circle', 'Tropic of Capricorn']),
                             ('Places near the Equator are generally...', 'hotter', ['colder', 'always snowy', 'always dark']),
                             ('Which place is near the North Pole?', 'Arctic', ['Sahara', 'Amazon Basin', 'Mediterranean']),
                             ('Which place is near the South Pole?', 'Antarctica', ['Europe', 'India', 'Mexico']),
                             ('Why are polar regions cold?',
                              'they receive less direct sunlight',
                              ['they are closest to the Sun', 'they have no air', 'they are all mountains'])],
     'Human and physical features': [('Which is a physical geographical feature?', 'river', ['factory', 'shop', 'road']),
                                     ('Which is a human geographical feature?', 'village', ['mountain', 'beach', 'forest']),
                                     ('Which is a physical feature?', 'valley', ['office', 'harbour wall', 'railway']),
                                     ('Which is a human feature?', 'port', ['ocean', 'hill', 'soil']),
                                     ('What is a settlement?',
                                      'a place where people live',
                                      ['a weather instrument', 'a type of rock', 'a sea current'])],
     'Local fieldwork': [('What is fieldwork?',
                          'studying places by observing and collecting information',
                          ['reading only a fiction book', 'drawing from imagination only', 'guessing without looking']),
                         ('Which tool could count traffic passing a school?', 'tally chart', ['thermometer', 'paintbrush', 'globe']),
                         ('Which is an observation?',
                          'There are three shops on the street.',
                          ['The street might be on Mars.', 'I did not look at the street.', 'Every street is identical.']),
                         ('Why use a simple sketch map?',
                          'to show the position of local features',
                          ['to measure body temperature', "to predict a person's age", 'to write a recipe']),
                         ('Which action is safest during local fieldwork?',
                          'follow adult instructions and stay with the group',
                          ['cross roads alone', 'touch unknown objects', 'leave the planned route'])],
     'UK seas and coasts': [('Which sea is east of Great Britain?', 'North Sea', ['Irish Sea', 'Mediterranean Sea', 'Red Sea']),
                            ('Which body of water is south of England?', 'English Channel', ['North Sea', 'Irish Sea', 'Baltic Sea']),
                            ('Which sea lies between Great Britain and Ireland?', 'Irish Sea', ['North Sea', 'Black Sea', 'Arabian Sea']),
                            ('What is a coast?', 'land beside the sea', ['land far from any water', 'a city centre', 'a mountain top']),
                            ('What is a cliff?', 'a steep rock face, often by the sea', ['a flat field', 'a river source', 'a road junction'])]},
 3: {'Compass and grid basics': [('How many main compass points are there?', '4', ['3', '6', '8']),
                                 ('Which direction lies between north and east?', 'north-east', ['south-west', 'north-west', 'south-east']),
                                 ('On a simple grid, which coordinate is usually read first?', 'across', ['up', 'down', 'diagonally']),
                                 ('What is a grid square used for?',
                                  'locating an area on a map',
                                  ['measuring rainfall', 'naming a continent', 'showing temperature only']),
                                 ('Which phrase helps remember grid references?',
                                  'along the corridor, then up the stairs',
                                  ['up first, then across', 'read the title twice', 'start at the top right always'])],
     'Europe': [('Which country is in Europe?', 'France', ['Brazil', 'Kenya', 'Japan']),
                ('What is the capital of France?', 'Paris', ['Rome', 'Madrid', 'Berlin']),
                ('What is the capital of Italy?', 'Rome', ['Paris', 'Lisbon', 'Vienna']),
                ('Which large country spans eastern Europe and northern Asia?', 'Russia', ['Portugal', 'Ireland', 'Belgium']),
                ('Which mountain range includes Mont Blanc?', 'Alps', ['Andes', 'Himalayas', 'Rockies'])],
     'Rivers and the water cycle': [('What is the source of a river?',
                                     'the place where it begins',
                                     ['the place where it enters the sea only', 'a bridge', 'a harbour']),
                                    ('What is the mouth of a river?',
                                     'where it flows into a sea, lake or another river',
                                     ['where it begins', 'the highest mountain', 'a weather station']),
                                    ('What is evaporation?',
                                     'liquid water changing into water vapour',
                                     ['water vapour changing into liquid', 'rain falling', 'ice melting only']),
                                    ('What is condensation?',
                                     'water vapour cooling into liquid droplets',
                                     ['liquid turning into vapour', 'a river flooding', 'snow becoming ice']),
                                    ('What is precipitation?',
                                     'water falling from clouds',
                                     ['water soaking into rock only', 'sunlight heating land', 'wind moving sand'])],
     'UK counties cities and regions': [('Which city is in the north-west of England?', 'Manchester', ['Brighton', 'Norwich', 'Canterbury']),
                                        ('Which city is the capital of Scotland?', 'Edinburgh', ['Glasgow', 'Aberdeen', 'Dundee']),
                                        ('Which county contains the city of York?', 'North Yorkshire', ['Kent', 'Cornwall', 'Essex']),
                                        ('Which region is known for the Lake District?',
                                         'north-west England',
                                         ['south-east England', 'East Anglia', 'Greater London']),
                                        ('Which topographical feature is common in the Scottish Highlands?',
                                         'mountains',
                                         ['coral reefs', 'tropical rainforest', 'sand desert'])]},
 4: {'Maps and grid references': [('How many points are on an eight-point compass?', '8', ['4', '6', '10']),
                                  ('Which direction is halfway between south and west?', 'south-west', ['south-east', 'north-west', 'west-north']),
                                  ('What do contour lines show on a map?',
                                   'height and shape of land',
                                   ['population names', 'weather tomorrow', 'road speed only']),
                                  ('What do close contour lines usually show?',
                                   'a steep slope',
                                   ['flat land', 'sea level everywhere', 'a city centre']),
                                  ('A four-figure grid reference identifies...',
                                   'a grid square',
                                   ['an exact building corner', 'a whole country', 'a compass direction'])],
     'Mountains volcanoes and earthquakes': [("What is magma called after it reaches Earth's surface?", 'lava', ['soil', 'steam', 'sediment']),
                                             ('What causes most earthquakes?',
                                              'movement of tectonic plates',
                                              ['daily rainfall', 'river flow', 'plant growth']),
                                             ('What is the summit of a mountain?', 'its highest point', ['its base', 'a valley', 'a river mouth']),
                                             ('Which feature may form where tectonic plates meet?', 'volcano', ['canal', 'factory', 'harbour wall']),
                                             ('What instrument records earthquake waves?',
                                              'seismograph',
                                              ['thermometer', 'rain gauge', 'anemometer'])],
     'North and South America': [('Which country is in North America?', 'Canada', ['Brazil', 'Argentina', 'Chile']),
                                 ('Which country is in South America?', 'Brazil', ['Canada', 'Mexico', 'United States']),
                                 ('What is the capital of the United States?', 'Washington, D.C.', ['New York City', 'Los Angeles', 'Chicago']),
                                 ("Which river basin contains the world's largest tropical rainforest?",
                                  'Amazon Basin',
                                  ['Thames Basin', 'Nile Delta', 'Rhine Valley']),
                                 ('Which mountain range runs along western South America?', 'Andes', ['Alps', 'Himalayas', 'Pennines'])],
     'Settlements and land use': [('Which settlement is usually larger than a village?', 'town', ['hamlet', 'farm', 'campsite']),
                                  ('What is land use?',
                                   'how people use an area of land',
                                   ['the age of the rocks only', 'the direction of wind', 'the height of clouds']),
                                  ('Which is an example of residential land use?', 'houses', ['factory', 'farm field', 'airport runway']),
                                  ('Which is an example of industrial land use?', 'factory', ['park', 'school playground', 'woodland']),
                                  ('Why do many settlements grow near rivers?',
                                   'water, transport and flat land can support people and trade',
                                   ['rivers always prevent travel', 'rivers have no resources', 'all mountains are nearby'])]},
 5: {'Climate zones and biomes': [('What is climate?',
                                   'the usual pattern of weather over a long period',
                                   ['weather at one moment', 'a map symbol', 'a river source']),
                                  ('Which biome has very low rainfall and sparse vegetation?',
                                   'desert',
                                   ['tropical rainforest', 'temperate forest', 'grassland']),
                                  ('Which biome is hot, wet and rich in plant life?', 'tropical rainforest', ['tundra', 'hot desert', 'polar ice']),
                                  ('Which climate zone lies around the Equator?', 'tropical', ['polar', 'temperate only', 'alpine only']),
                                  ('What is vegetation?', 'plant life in an area', ['only wild animals', 'human buildings', 'rock type'])],
     'Comparing regions': [('Which is useful when comparing two regions?',
                            'use the same categories for both places',
                            ['use facts for one and guesses for the other', 'ignore scale', 'compare only their names']),
                           ('Which category is physical geography?', 'climate', ['language', 'industry', 'population']),
                           ('Which category is human geography?', 'settlement', ['river', 'mountain', 'climate']),
                           ('What is a similarity?', 'a feature both places share', ['a feature only one place has', 'a map error', 'a time zone']),
                           ('What is a difference?',
                            'a way the places are not the same',
                            ['a feature both share', 'a compass point', 'a weather instrument'])],
     'Latitude longitude and time zones': [('What is latitude?',
                                            'distance north or south of the Equator',
                                            ['distance east or west of the Prime Meridian', 'height above sea level', 'distance from a city']),
                                           ('What is longitude?',
                                            'distance east or west of the Prime Meridian',
                                            ['distance north or south of the Equator', 'depth of an ocean', 'rainfall amount']),
                                           ('What latitude is the Equator?', '0°', ['90° N', '180°', '23.5° N']),
                                           ('What longitude is the Prime Meridian?', '0°', ['90° E', '180° W', '23.5° S']),
                                           ('Why do time zones exist?',
                                            'Earth rotates, so places experience daylight at different times',
                                            ['all countries choose random clocks', 'the Moon blocks every sunrise', 'longitude never changes'])],
     'Trade and natural resources': [('What is trade?',
                                      'buying and selling goods and services',
                                      ['only moving house', 'measuring rainfall', 'naming mountains']),
                                     ('Which is a natural resource?', 'fresh water', ['plastic toy', 'computer program', 'brick wall']),
                                     ('Which resource is used to generate hydroelectric power?', 'moving water', ['coal only', 'sand', 'cotton']),
                                     ('What is an import?',
                                      'a good or service brought into a country',
                                      ['a good sent out of a country', 'a local footpath', 'a mountain pass']),
                                     ('What is an export?',
                                      'a good or service sold to another country',
                                      ['a good brought into a country', 'a type of rainfall', 'a map key'])]},
 6: {'Changing landscapes': [('What is erosion?',
                              'wearing away and removal of material',
                              ['depositing material only', 'building a factory', 'measuring temperature']),
                             ('What is deposition?',
                              'dropping material that has been transported',
                              ['breaking rock at source only', 'evaporation', 'urban growth']),
                             ('Which process can widen a river valley over time?', 'erosion', ['trade', 'time zones', 'migration only']),
                             ('How can glaciers shape land?',
                              'by eroding and depositing rock',
                              ['by creating tropical heat', 'by building cities', 'by stopping gravity']),
                             ('Which evidence can show land-use change?',
                              'maps or aerial photographs from different dates',
                              ['one map with no date', 'a weather forecast only', 'a single opinion'])],
     'Fieldwork and data': [('Which method measures pedestrian flow?',
                             'count people passing a point for a set time',
                             ['guess the busiest place', 'measure temperature only', 'draw a country flag']),
                            ('What should a fieldwork enquiry begin with?',
                             'a clear geographical question',
                             ['a conclusion', 'a random answer', 'a finished graph']),
                            ('Which graph is suitable for comparing counts in categories?',
                             'bar chart',
                             ['unlabelled sketch', 'paragraph only', 'compass rose']),
                            ('Why repeat measurements?',
                             'to improve reliability and notice variation',
                             ['to guarantee the first result', 'to avoid recording', 'to change the question']),
                            ('What is a conclusion?',
                             'an answer supported by the collected evidence',
                             ['a list of equipment only', 'a map title', 'a prediction with no data'])],
     'Physical and human interaction': [('How can a river influence human settlement?',
                                         'it can provide water, transport and fertile land',
                                         ['it removes all need for roads', 'it prevents farming everywhere', 'it makes every place identical']),
                                        ('How can farming change a landscape?',
                                         'fields, boundaries and drainage may be created',
                                         ['mountains disappear instantly', 'time zones change', 'oceans become fresh water']),
                                        ('Why are floodplains often farmed?',
                                         'their soils can be fertile',
                                         ['they are always dry', 'they have no rivers', 'they are made of concrete']),
                                        ('What is urbanisation?',
                                         'growth in the proportion of people living in towns and cities',
                                         ['formation of mountains', 'movement of ocean currents', 'daily weather change']),
                                        ('Which is an example of human response to coastal erosion?',
                                         'building sea defences',
                                         ['moving the Equator', 'stopping tides globally', 'changing longitude'])],
     'World regions and location': [('Which continent contains the Sahara Desert?', 'Africa', ['Europe', 'South America', 'Antarctica']),
                                    ('Which continent contains China and India?', 'Asia', ['Europe', 'Africa', 'North America']),
                                    ('Which ocean is east of Africa and west of Australia?',
                                     'Indian Ocean',
                                     ['Atlantic Ocean', 'Arctic Ocean', 'Southern Ocean']),
                                    ('Which line marks 23.5° north latitude?',
                                     'Tropic of Cancer',
                                     ['Tropic of Capricorn', 'Equator', 'Prime Meridian']),
                                    ('Which line marks 23.5° south latitude?',
                                     'Tropic of Capricorn',
                                     ['Tropic of Cancer', 'Arctic Circle', 'Prime Meridian'])]}}


def _repeat(items, rng, index):
    questions = []
    for offset in range(10):
        stem, answer, distractors = items[(offset + index) % len(items)]
        questions.append(make_mcq(stem, answer, distractors, rng))
    return questions


def generate_geography_homework(
    year_group: int,
    topic: str,
    index: int,
) -> tuple[str, list[str]]:
    if year_group not in GEOGRAPHY_TOPICS_BY_YEAR:
        raise ValueError("year_group must be between 1 and 6")
    if topic not in GEOGRAPHY_TOPICS_BY_YEAR[year_group]:
        raise ValueError(f"Unknown Year {year_group} Geography topic: {topic}")

    items = QUESTION_BANKS[year_group][topic]
    rng = stable_random("Geography", year_group, topic, index)
    note = ""
    return render_homework(
        "Geography",
        year_group,
        topic,
        index,
        _repeat(items, rng, index),
        note=note,
    )


def generate_year_homework(year_group: int, count: int = 300) -> list:
    topics = GEOGRAPHY_TOPICS_BY_YEAR.get(year_group, [])
    config = YEAR_CONFIG.get(year_group)
    if not topics or not config:
        return []

    batch = []
    for index in range(1, count + 1):
        topic = topics[(index - 1) % len(topics)]
        content, answers = generate_geography_homework(year_group, topic, index)
        batch.append(
            build_batch_item(
                content=content,
                answers=answers,
                year_group=year_group,
                subject="Geography",
                topic=topic,
                homework_minutes=config["homework_minutes"],
                key_stage=config["key_stage"],
                doc_id=f"geography_y{year_group}_{index:04d}",
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
        existing = count_year_homework(store, year_group, "Geography")
        if existing >= expected:
            print(f"Year {year_group}: complete ({existing}/{expected})")
            continue
        homework = generate_year_homework(year_group, expected)
        added = add_homework_in_batches(store, homework)
        print(f"Year {year_group}: added {added}; target {len(homework)}")
    get_rag_stats(store)


if __name__ == "__main__":
    main()
