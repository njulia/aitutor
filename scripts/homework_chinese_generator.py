#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate age-appropriate Chinese homework for England Years 1-6 using simplified Chinese, pinyin support and exact-answer multiple choice. Years 1-2 are optional enrichment; Years 3-6 follow KS2 foreign-language expectations.

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

CHINESE_TOPICS_BY_YEAR = {1: ['Greetings', 'Numbers 1-10', 'Colours', 'Family'],
 2: ['Numbers 11-20', 'Animals', 'Body parts', 'Classroom words'],
 3: ['Pinyin and tones', 'Introductions', 'Dates and birthdays', 'Likes and dislikes'],
 4: ['Daily routine and time', 'Food and drink', 'Places and directions', 'Measure words'],
 5: ['Common verbs', 'School and leisure', 'Opinions and reasons', 'Short reading'],
 6: ['Future and time phrases',
     'Reading comprehension',
     'China and the Chinese-speaking world',
     'Sentence building']}

YEAR_CONFIG = {
    1: {"key_stage": "KS1" if False else "Optional enrichment", "homework_minutes": "10-15" if False else "5-10"},
    2: {"key_stage": "KS1" if False else "Optional enrichment", "homework_minutes": "10-15" if False else "5-10"},
    3: {"key_stage": "KS2", "homework_minutes": "15-20" if False else "10-15"},
    4: {"key_stage": "KS2", "homework_minutes": "15-20"},
    5: {"key_stage": "KS2", "homework_minutes": "20-25"},
    6: {"key_stage": "KS2", "homework_minutes": "20-25"},
}

QUESTION_BANKS = {1: {'Colours': [("What colour is '红色 (hóngsè)'?", 'red', ['blue', 'green', 'yellow']),
                 ('How do you say blue in Chinese?', '蓝色 (lánsè)', ['绿色 (lǜsè)', '红色 (hóngsè)', '黑色 (hēisè)']),
                 ("What colour is '绿色 (lǜsè)'?", 'green', ['orange', 'white', 'pink']),
                 ('How do you say yellow in Chinese?', '黄色 (huángsè)', ['紫色 (zǐsè)', '白色 (báisè)', '灰色 (huīsè)']),
                 ("What colour is '黑色 (hēisè)'?", 'black', ['white', 'brown', 'purple'])],
     'Family': [("What does '妈妈 (māma)' mean?", 'mother', ['father', 'sister', 'brother']),
                ('How do you say father in Chinese?', '爸爸 (bàba)', ['奶奶 (nǎinai)', '姐姐 (jiějie)', '阿姨 (āyí)']),
                ("What does '哥哥 (gēge)' mean?", 'older brother', ['older sister', 'grandfather', 'cousin']),
                ('How do you say older sister in Chinese?', '姐姐 (jiějie)', ['哥哥 (gēge)', '妈妈 (māma)', '妹妹 (mèimei)']),
                ("What does '家 (jiā)' mean in this topic?", 'home or family', ['school', 'book', 'animal'])],
     'Greetings': [("What does '你好 (nǐ hǎo)' mean?", 'hello', ['goodbye', 'thank you', 'please']),
                   ("Which Chinese word means 'goodbye'?", '再见 (zàijiàn)', ['你好 (nǐ hǎo)', '谢谢 (xièxie)', '是 (shì)']),
                   ("What does '谢谢 (xièxie)' mean?", 'thank you', ['hello', 'sorry', 'no']),
                   ("Which phrase means 'my name is...'?", '我叫… (wǒ jiào…)', ['你好吗？(nǐ hǎo ma?)', '明天见 (míngtiān jiàn)', '请 (qǐng)']),
                   ("What does '请 (qǐng)' mean?", 'please', ['goodbye', 'today', 'friend'])],
     'Numbers 1-10': [("What number is '一 (yī)'?", '1', ['2', '3', '10']),
                      ('How do you say 5 in Chinese?', '五 (wǔ)', ['四 (sì)', '六 (liù)', '十 (shí)']),
                      ("What number is '八 (bā)'?", '8', ['6', '7', '9']),
                      ('How do you say 10 in Chinese?', '十 (shí)', ['二 (èr)', '三 (sān)', '九 (jiǔ)']),
                      ('Which sequence is correct?', '一，二，三', ['一，三，二', '二，一，四', '三，一，二'])]},
 2: {'Animals': [("What animal is '猫 (māo)'?", 'cat', ['dog', 'fish', 'bird']),
                 ('How do you say dog in Chinese?', '狗 (gǒu)', ['鸟 (niǎo)', '鱼 (yú)', '兔子 (tùzi)']),
                 ("What animal is '鱼 (yú)'?", 'fish', ['horse', 'rabbit', 'cow']),
                 ('How do you say bird in Chinese?', '鸟 (niǎo)', ['猫 (māo)', '猪 (zhū)', '马 (mǎ)']),
                 ("What animal is '兔子 (tùzi)'?", 'rabbit', ['cow', 'pig', 'cat'])],
     'Body parts': [("What does '头 (tóu)' mean?", 'head', ['hand', 'foot', 'arm']),
                    ('How do you say hand in Chinese?', '手 (shǒu)', ['脚 (jiǎo)', '眼睛 (yǎnjing)', '嘴 (zuǐ)']),
                    ("What does '眼睛 (yǎnjing)' mean?", 'eyes', ['ears', 'legs', 'teeth']),
                    ('How do you say nose in Chinese?', '鼻子 (bízi)', ['耳朵 (ěrduo)', '胳膊 (gēbo)', '头发 (tóufa)']),
                    ("What does '嘴 (zuǐ)' mean?", 'mouth', ['head', 'finger', 'knee'])],
     'Classroom words': [("What does '书 (shū)' mean?", 'book', ['pencil', 'chair', 'door']),
                         ('How do you say pencil in Chinese?', '铅笔 (qiānbǐ)', ['桌子 (zhuōzi)', '书 (shū)', '椅子 (yǐzi)']),
                         ("What does '听 (tīng)' mean?", 'listen', ['write', 'run', 'sleep']),
                         ('Which word means table or desk?', '桌子 (zhuōzi)', ['门 (mén)', '窗户 (chuānghu)', '书包 (shūbāo)']),
                         ("What does '看 (kàn)' mean?", 'look or read', ['sit', 'eat', 'close'])],
     'Numbers 11-20': [("What number is '十二 (shí'èr)'?", '12', ['11', '13', '20']),
                       ('How do you say 15 in Chinese?', '十五 (shíwǔ)', ['十四 (shísì)', '十六 (shíliù)', '五 (wǔ)']),
                       ("What number is '十八 (shíbā)'?", '18', ['16', '17', '19']),
                       ('How do you say 20 in Chinese?', '二十 (èrshí)', ['九 (jiǔ)', '十 (shí)', '十九 (shíjiǔ)']),
                       ("Which comes after '十三 (shísān)'?", '十四 (shísì)', ["十二 (shí'èr)", '十五 (shíwǔ)', '十一 (shíyī)'])]},
 3: {'Dates and birthdays': [("What does '星期一 (xīngqīyī)' mean?", 'Monday', ['Tuesday', 'month', 'morning']),
                             ("Which month is '一月 (yīyuè)'?", 'January', ['June', 'July', 'December']),
                             ("What does '生日 (shēngrì)' mean?", 'birthday', ['school day', 'holiday', 'family']),
                             ("How do you say '1 May' in Chinese date order?", '五月一日', ['一日五月', '五月第一', '一五月日']),
                             ("What number is '三十 (sānshí)'?", '30', ['13', '20', '40'])],
     'Introductions': [("What does '你叫什么名字？' mean?", 'What is your name?', ['How old are you?', 'Where do you live?', 'What do you like?']),
                       ("Which reply matches '你叫什么名字？'?", '我叫安娜。', ['我十岁。', '我住在伦敦。', '我喜欢足球。']),
                       ("What does '我十岁' mean?", 'I am ten years old', ['I have ten books', 'I live in ten houses', 'I like ten sports']),
                       ("How do you say 'I live in London'?", '我住在伦敦。', ['我叫伦敦。', '我是伦敦。', '我有伦敦。']),
                       ("What does '朋友 (péngyou)' mean?", 'friend', ['teacher', 'family', 'school'])],
     'Likes and dislikes': [("What does '我喜欢' mean?", 'I like', ['I dislike', 'I have', 'I am']),
                            ("What does '我不喜欢' mean?", 'I do not like', ['I love', 'I can', 'I want']),
                            ("Which sentence means 'I like music'?", '我喜欢音乐。', ['我有音乐。', '我是音乐。', '音乐喜欢我。']),
                            ("What does '因为 (yīnwèi)' mean?", 'because', ['but', 'and', 'also']),
                            ('Which sentence gives a reason?', '我喜欢运动，因为很有意思。', ['我喜欢运动。', '运动有意思。', '因为运动。'])],
     'Pinyin and tones': [('What is pinyin?',
                           'a Roman-letter system for writing Chinese pronunciation',
                           ['a Chinese food', 'a type of map', 'a number system only']),
                          ('Which tone mark shows the first tone?', 'ā', ['á', 'ǎ', 'à']),
                          ('Which tone mark shows the second tone?', 'á', ['ā', 'ǎ', 'à']),
                          ('Which tone mark shows the third tone?', 'ǎ', ['ā', 'á', 'à']),
                          ('Which tone mark shows the fourth tone?', 'à', ['ā', 'á', 'ǎ'])]},
 4: {'Daily routine and time': [("What does '我起床' mean?", 'I get up', ['I go to bed', 'I eat lunch', 'I go home']),
                                ("How do you say 'I go to school'?", '我去上学。', ['我是学校。', '我有学校。', '我做学校。']),
                                ("What time is '八点'?", "8 o'clock", ["7 o'clock", "9 o'clock", "10 o'clock"]),
                                ("What does '早上' mean?", 'morning', ['evening', 'night', 'midday']),
                                ("Which phrase means 'after school'?", '放学以后', ['上学以前', '在学校', '学校里面 only'])],
     'Food and drink': [("What does '米饭 (mǐfàn)' mean?", 'cooked rice', ['milk', 'cheese', 'water']),
                        ('How do you say water in Chinese?', '水 (shuǐ)', ['牛奶 (niúnǎi)', '果汁 (guǒzhī)', '汤 (tāng)']),
                        ("What does '苹果 (píngguǒ)' mean?", 'apple', ['pear', 'orange', 'banana']),
                        ("Which phrase means 'I would like...'?", '我想要…', ['我要去…', '我有…', '我是…']),
                        ("What does '好吃 (hǎochī)' mean?", 'tasty', ['expensive', 'cold', 'small'])],
     'Measure words': [('Which measure word is commonly used for books?', '本 (běn)', ['个 (gè)', '只 (zhī)', '杯 (bēi)']),
                       ('Which measure word is commonly used for cups of drink?', '杯 (bēi)', ['本 (běn)', '张 (zhāng)', '只 (zhī)']),
                       ('Which measure word is often used for many animals?', '只 (zhī)', ['本 (běn)', '杯 (bēi)', '件 (jiàn)']),
                       ("Which phrase means 'three books'?", '三本书', ['三个书', '三杯书', '三只书']),
                       ('Which measure word is a common general classifier for people and many objects?',
                        '个 (gè)',
                        ['本 (běn)', '杯 (bēi)', '条 (tiáo)'])],
     'Places and directions': [("What does '火车站 (huǒchēzhàn)' mean?", 'train station', ['school', 'shop', 'park']),
                               ("How do you say 'turn left'?", '向左转', ['向右转', '一直走', '停']),
                               ("What does '一直走' mean?", 'go straight on', ['turn left', 'go behind', 'stay near']),
                               ('Which word means library?', '图书馆 (túshūguǎn)', ['面包店 (miànbāodiàn)', '游泳池 (yóuyǒngchí)', '市政府 (shìzhèngfǔ)']),
                               ("What does '附近 (fùjìn)' mean?", 'nearby', ['far away', 'opposite', 'between'])]},
 5: {'Common verbs': [("What does '我看' mean?", 'I look, watch or read', ['I sleep', 'I eat', 'I run']),
                      ("How do you say 'we eat'?", '我们吃', ['我吃', '他们看', '你喝']),
                      ("What does '他写' mean?", 'he writes', ['he listens', 'he walks', 'he buys']),
                      ("Which verb means 'to drink'?", '喝 (hē)', ['吃 (chī)', '说 (shuō)', '去 (qù)']),
                      ("What does '可以 (kěyǐ)' often mean?", 'can or may', ['must', 'never', 'yesterday'])],
     'Opinions and reasons': [("What does '我觉得很有用' mean?", 'I think it is useful', ['I know it is easy', 'I do not like it', 'It is always useful']),
                              ("Which phrase means 'because it is exciting'?", '因为很精彩', ['但是很精彩', '也很精彩', '精彩因为 only']),
                              ("How do you say 'In my opinion'?", '我觉得', ['在我家', '早上', '有时候']),
                              ("What does '我更喜欢' mean?", 'I prefer', ['I promise', 'I practise', 'I prepare']),
                              ('Choose the best justified opinion.', '我喜欢科学，因为很有意思。', ['我喜欢科学。', '科学因为。', '有意思科学我。'])],
     'School and leisure': [("What does '我最喜欢的科目' mean?", 'my favourite subject', ['my school bag', 'my classroom', 'my timetable']),
                            ("How do you say 'I play football'?", '我踢足球。', ['我做足球。', '我去足球。', '我是足球。']),
                            ("What does '周末' mean?", 'weekend', ['Monday', 'summer', 'after school only']),
                            ("Which sentence means 'I read books in my free time'?", '我有空的时候看书。', ['我在课上写书。', '我有时间和书。', '书看我的时间。']),
                            ('How do you say homework?', '作业 (zuòyè)', ['课间 (kèjiān)', '食堂 (shítáng)', '校服 (xiàofú)'])],
     'Short reading': [("Read: '小丽住在北京，坐公共汽车上学。' Where does Xiaoli live?", 'Beijing', ['Shanghai', 'London', 'Paris']),
                       ("Read: '星期六我和哥哥打网球。' When does the speaker play tennis?", 'on Saturday', ['on Sunday', 'every morning', 'on Monday']),
                       ("Read: '我的狗很小，是白色的。' What colour is the dog?", 'white', ['black', 'brown', 'grey']),
                       ("Read: '我喜欢苹果，因为苹果很健康。' Why are apples liked?",
                        'because they are healthy',
                        ['because they are expensive', 'because they are blue', 'because they are hot']),
                       ("Read: '明天我们坐飞机去旅行。' How will they travel?", 'by plane', ['by train', 'by bus', 'on foot'])]},
 6: {'China and the Chinese-speaking world': [('What is the capital of China?', 'Beijing', ['Shanghai', 'Guangzhou', 'Shenzhen']),
                                              ('Which river is the longest in China?', 'Yangtze River', ['Yellow River', 'Pearl River', 'Thames']),
                                              ('Which writing system is used for standard written Chinese?',
                                               'Chinese characters',
                                               ['Roman numerals only', 'Greek alphabet', 'Cyrillic alphabet']),
                                              ('Which festival is linked with the lunar new year?',
                                               'Spring Festival',
                                               ['Mid-Autumn Festival only', 'Dragon Boat Festival only', 'Qingming Festival only']),
                                              ('Which place also uses Chinese as an official language?',
                                               'Singapore',
                                               ['Brazil', 'Portugal', 'Italy'])],
     'Future and time phrases': [("What does '我明天要学习' mean?",
                                  'I am going to study tomorrow',
                                  ['I studied yesterday', 'I study every day', 'I do not study']),
                                 ("Which phrase means 'next week'?", '下个星期', ['上个星期', '今天早上', '昨天']),
                                 ("What does '昨天' mean?", 'yesterday', ['tomorrow', 'today', 'next year']),
                                 ('Which sentence refers to the future?', '星期六我们要踢足球。', ['上星期六我们踢了足球。', '我们每星期六踢足球。', '昨天我们踢足球。']),
                                 ('Which sentence refers to the past?', '昨天我去了博物馆。', ['明天我要去博物馆。', '我常常去博物馆。', '我现在去博物馆。'])],
     'Reading comprehension': [("Read: '虽然下雨了，小美还是去公园跑步。' Why did Xiaomei go to the park?",
                                'to run',
                                ['to swim', 'to buy a book', 'to meet a teacher']),
                               ("Read: '小王在存钱买一辆新自行车。' What is Xiaowang saving for?", 'a new bicycle', ['a computer', 'a holiday', 'a football']),
                               ("Read: '火车晚点了，所以我们九点才到。' Why did they arrive at nine?",
                                'the train was late',
                                ['they missed the bus', 'the station closed', 'they walked slowly']),
                               ("Read: '安娜喜欢住在农村，因为那里很安静。' Where does Anna prefer to live?",
                                'in the countryside',
                                ['in a city centre', 'near an airport', 'at school']),
                               ("Read: '吃完晚饭以后，我做完作业，看了电影。' What happened first?",
                                'the speaker had dinner',
                                ['the speaker watched a film', 'the speaker finished homework', 'the speaker went to school'])],
     'Sentence building': [("Which sentence has a common Chinese word order for 'I study Chinese today'?",
                            '我今天学中文。',
                            ['今天中文我学。', '学我今天中文。', '中文今天学我。']),
                           ('Which word makes a simple negative before many verbs?', '不 (bù)', ['很 (hěn)', '也 (yě)', '都 (dōu)']),
                           ("Complete: '我喜欢看书，___ 很有意思。' ", '因为', ['但是', '和', '还是']),
                           ("Which word can mean 'also'?", '也 (yě)', ['不 (bù)', '没 (méi)', '吗 (ma)']),
                           ('Which sentence is a yes-no question?', '你喜欢音乐吗？', ['你喜欢什么音乐？', '我喜欢音乐。', '因为音乐很好听。'])]}}


def _repeat(items, rng, index):
    questions = []
    for offset in range(10):
        stem, answer, distractors = items[(offset + index) % len(items)]
        questions.append(make_mcq(stem, answer, distractors, rng))
    return questions


def generate_chinese_homework(
    year_group: int,
    topic: str,
    index: int,
) -> tuple[str, list[str]]:
    if year_group not in CHINESE_TOPICS_BY_YEAR:
        raise ValueError("year_group must be between 1 and 6")
    if topic not in CHINESE_TOPICS_BY_YEAR[year_group]:
        raise ValueError(f"Unknown Year {year_group} Chinese topic: {topic}")

    items = QUESTION_BANKS[year_group][topic]
    rng = stable_random("Chinese", year_group, topic, index)
    note = "Optional language enrichment for Years 1-2; foreign languages are statutory from KS2." if year_group in {1, 2} else ""
    return render_homework(
        "Chinese",
        year_group,
        topic,
        index,
        _repeat(items, rng, index),
        note=note,
    )


def generate_year_homework(year_group: int, count: int = 300) -> list:
    topics = CHINESE_TOPICS_BY_YEAR.get(year_group, [])
    config = YEAR_CONFIG.get(year_group)
    if not topics or not config:
        return []

    batch = []
    for index in range(1, count + 1):
        topic = topics[(index - 1) % len(topics)]
        content, answers = generate_chinese_homework(year_group, topic, index)
        batch.append(
            build_batch_item(
                content=content,
                answers=answers,
                year_group=year_group,
                subject="Chinese",
                topic=topic,
                homework_minutes=config["homework_minutes"],
                key_stage=config["key_stage"],
                doc_id=f"chinese_y{year_group}_{index:04d}",
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
        existing = count_year_homework(store, year_group, "Chinese")
        if existing >= expected:
            print(f"Year {year_group}: complete ({existing}/{expected})")
            continue
        homework = generate_year_homework(year_group, expected)
        added = add_homework_in_batches(store, homework)
        print(f"Year {year_group}: added {added}; target {len(homework)}")
    get_rag_stats(store)


if __name__ == "__main__":
    main()
