#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared deterministic generators for additional UK primary subjects.

Each public subject module is a small runnable wrapper around this file.  The
output deliberately matches ``homework_english_generator.py``: ten numbered
four-option questions plus ten positional answers, ready for the existing RAG
store and deterministic review path.
"""
from __future__ import annotations

from typing import Any

from scripts.homework_generator.homework_generator_utils import (
    add_homework_in_batches,
    build_batch_item,
    count_year_homework,
    get_rag_stats,
    make_mcq,
    render_homework,
    stable_random,
)


HOMEWORK_COUNT = {1: 500, 2: 500, 3: 800, 4: 800, 5: 1000, 6: 1000}
YEAR_CONFIG = {
    1: {"key_stage": "KS1", "homework_minutes": "5-10"},
    2: {"key_stage": "KS1", "homework_minutes": "10-15"},
    3: {"key_stage": "KS2", "homework_minutes": "10-15"},
    4: {"key_stage": "KS2", "homework_minutes": "15-20"},
    5: {"key_stage": "KS2", "homework_minutes": "20-25"},
    6: {"key_stage": "KS2", "homework_minutes": "20-25"},
}


LANGUAGE_TOPICS = {
    "early": ["Greetings and manners", "Numbers and colours", "Family and animals"],
    "middle": ["Classroom and school", "Food and drink", "Weather and daily routine"],
    "upper": ["Opinions and reasons", "Time and plans", "Short reading"],
}


LANGUAGE_BANKS: dict[str, dict[str, list[tuple[str, str]]]] = {
    "German": {
        "Greetings and manners": [("hallo", "hello"), ("guten Morgen", "good morning"), ("auf Wiedersehen", "goodbye"), ("bitte", "please"), ("danke", "thank you"), ("Wie geht's?", "How are you?")],
        "Numbers and colours": [("eins", "one"), ("fünf", "five"), ("zehn", "ten"), ("rot", "red"), ("blau", "blue"), ("grün", "green")],
        "Family and animals": [("Mutter", "mother"), ("Bruder", "brother"), ("Familie", "family"), ("Hund", "dog"), ("Katze", "cat"), ("Vogel", "bird")],
        "Classroom and school": [("Buch", "book"), ("Bleistift", "pencil"), ("Schule", "school"), ("Lehrer", "teacher"), ("lesen", "to read"), ("schreiben", "to write")],
        "Food and drink": [("Brot", "bread"), ("Wasser", "water"), ("Apfel", "apple"), ("Käse", "cheese"), ("Milch", "milk"), ("Ich möchte...", "I would like...")],
        "Weather and daily routine": [("Es regnet.", "It is raining."), ("sonnig", "sunny"), ("kalt", "cold"), ("Ich stehe auf.", "I get up."), ("Ich gehe zur Schule.", "I go to school."), ("am Morgen", "in the morning")],
        "Opinions and reasons": [("Ich mag...", "I like..."), ("Ich mag ... nicht.", "I do not like..."), ("weil", "because"), ("interessant", "interesting"), ("langweilig", "boring"), ("mein Lieblingsfach", "my favourite subject")],
        "Time and plans": [("heute", "today"), ("morgen", "tomorrow"), ("gestern", "yesterday"), ("nächste Woche", "next week"), ("Ich werde lernen.", "I will study."), ("um acht Uhr", "at eight o'clock")],
        "Short reading": [("Lina hat einen roten Hund.", "Lina has a red dog."), ("Wir trinken Wasser.", "We drink water."), ("Am Montag spiele ich Fußball.", "On Monday I play football."), ("Mein Bruder liest ein Buch.", "My brother reads a book."), ("Es ist kalt, aber sonnig.", "It is cold but sunny."), ("Nächste Woche besuche ich Berlin.", "Next week I will visit Berlin.")],
    },
    "Italian": {
        "Greetings and manners": [("ciao", "hello"), ("buongiorno", "good morning"), ("arrivederci", "goodbye"), ("per favore", "please"), ("grazie", "thank you"), ("Come stai?", "How are you?")],
        "Numbers and colours": [("uno", "one"), ("cinque", "five"), ("dieci", "ten"), ("rosso", "red"), ("blu", "blue"), ("verde", "green")],
        "Family and animals": [("madre", "mother"), ("fratello", "brother"), ("famiglia", "family"), ("cane", "dog"), ("gatto", "cat"), ("uccello", "bird")],
        "Classroom and school": [("libro", "book"), ("matita", "pencil"), ("scuola", "school"), ("insegnante", "teacher"), ("leggere", "to read"), ("scrivere", "to write")],
        "Food and drink": [("pane", "bread"), ("acqua", "water"), ("mela", "apple"), ("formaggio", "cheese"), ("latte", "milk"), ("Vorrei...", "I would like...")],
        "Weather and daily routine": [("Piove.", "It is raining."), ("soleggiato", "sunny"), ("freddo", "cold"), ("Mi alzo.", "I get up."), ("Vado a scuola.", "I go to school."), ("la mattina", "in the morning")],
        "Opinions and reasons": [("Mi piace...", "I like..."), ("Non mi piace...", "I do not like..."), ("perché", "because"), ("interessante", "interesting"), ("noioso", "boring"), ("la mia materia preferita", "my favourite subject")],
        "Time and plans": [("oggi", "today"), ("domani", "tomorrow"), ("ieri", "yesterday"), ("la settimana prossima", "next week"), ("Studierò.", "I will study."), ("alle otto", "at eight o'clock")],
        "Short reading": [("Lina ha un cane rosso.", "Lina has a red dog."), ("Beviamo acqua.", "We drink water."), ("Lunedì gioco a calcio.", "On Monday I play football."), ("Mio fratello legge un libro.", "My brother reads a book."), ("Fa freddo ma c'è il sole.", "It is cold but sunny."), ("La settimana prossima visiterò Roma.", "Next week I will visit Rome.")],
    },
    "Polish": {
        "Greetings and manners": [("cześć", "hello"), ("dzień dobry", "good morning"), ("do widzenia", "goodbye"), ("proszę", "please"), ("dziękuję", "thank you"), ("Jak się masz?", "How are you?")],
        "Numbers and colours": [("jeden", "one"), ("pięć", "five"), ("dziesięć", "ten"), ("czerwony", "red"), ("niebieski", "blue"), ("zielony", "green")],
        "Family and animals": [("mama", "mother"), ("brat", "brother"), ("rodzina", "family"), ("pies", "dog"), ("kot", "cat"), ("ptak", "bird")],
        "Classroom and school": [("książka", "book"), ("ołówek", "pencil"), ("szkoła", "school"), ("nauczyciel", "teacher"), ("czytać", "to read"), ("pisać", "to write")],
        "Food and drink": [("chleb", "bread"), ("woda", "water"), ("jabłko", "apple"), ("ser", "cheese"), ("mleko", "milk"), ("Poproszę...", "I would like...")],
        "Weather and daily routine": [("Pada deszcz.", "It is raining."), ("słonecznie", "sunny"), ("zimno", "cold"), ("Wstaję.", "I get up."), ("Idę do szkoły.", "I go to school."), ("rano", "in the morning")],
        "Opinions and reasons": [("Lubię...", "I like..."), ("Nie lubię...", "I do not like..."), ("ponieważ", "because"), ("interesujący", "interesting"), ("nudny", "boring"), ("mój ulubiony przedmiot", "my favourite subject")],
        "Time and plans": [("dzisiaj", "today"), ("jutro", "tomorrow"), ("wczoraj", "yesterday"), ("w przyszłym tygodniu", "next week"), ("Będę się uczyć.", "I will study."), ("o ósmej", "at eight o'clock")],
        "Short reading": [("Lina ma czerwonego psa.", "Lina has a red dog."), ("Pijemy wodę.", "We drink water."), ("W poniedziałek gram w piłkę nożną.", "On Monday I play football."), ("Mój brat czyta książkę.", "My brother reads a book."), ("Jest zimno, ale słonecznie.", "It is cold but sunny."), ("W przyszłym tygodniu odwiedzę Warszawę.", "Next week I will visit Warsaw.")],
    },
    "Arabic": {
        "Greetings and manners": [("مرحبا", "hello"), ("صباح الخير", "good morning"), ("مع السلامة", "goodbye"), ("من فضلك", "please"), ("شكرا", "thank you"), ("كيف حالك؟", "How are you?")],
        "Numbers and colours": [("واحد", "one"), ("خمسة", "five"), ("عشرة", "ten"), ("أحمر", "red"), ("أزرق", "blue"), ("أخضر", "green")],
        "Family and animals": [("أم", "mother"), ("أخ", "brother"), ("عائلة", "family"), ("كلب", "dog"), ("قطة", "cat"), ("طائر", "bird")],
        "Classroom and school": [("كتاب", "book"), ("قلم رصاص", "pencil"), ("مدرسة", "school"), ("معلم", "teacher"), ("يقرأ", "to read"), ("يكتب", "to write")],
        "Food and drink": [("خبز", "bread"), ("ماء", "water"), ("تفاحة", "apple"), ("جبن", "cheese"), ("حليب", "milk"), ("أريد...", "I would like...")],
        "Weather and daily routine": [("إنها تمطر.", "It is raining."), ("مشمس", "sunny"), ("بارد", "cold"), ("أستيقظ.", "I get up."), ("أذهب إلى المدرسة.", "I go to school."), ("في الصباح", "in the morning")],
        "Opinions and reasons": [("أحب...", "I like..."), ("لا أحب...", "I do not like..."), ("لأن", "because"), ("ممتع", "interesting"), ("ممل", "boring"), ("مادتي المفضلة", "my favourite subject")],
        "Time and plans": [("اليوم", "today"), ("غدا", "tomorrow"), ("أمس", "yesterday"), ("الأسبوع القادم", "next week"), ("سأدرس.", "I will study."), ("الساعة الثامنة", "at eight o'clock")],
        "Short reading": [("لينا لديها كلب أحمر.", "Lina has a red dog."), ("نحن نشرب الماء.", "We drink water."), ("ألعب كرة القدم يوم الاثنين.", "On Monday I play football."), ("أخي يقرأ كتابا.", "My brother reads a book."), ("الجو بارد لكنه مشمس.", "It is cold but sunny."), ("سأزور القاهرة الأسبوع القادم.", "Next week I will visit Cairo.")],
    },
}


FOUNDATION_CONFIGS: dict[str, dict[str, Any]] = {
    "Music": {
        "topics": {
            "early": ["Beat and rhythm", "Pitch and dynamics", "Instrument sounds"],
            "middle": ["Notes and metre", "Orchestra families", "Melody and structure"],
            "upper": ["Reading notation", "Harmony and texture", "Music history and listening"],
        },
        "banks": {
            "Beat and rhythm": [("What is the steady pulse in music called?", "beat", ["colour", "verse", "instrument"]), ("Which action can show a beat?", "clapping steadily", ["reading silently", "standing still", "drawing a map"]), ("A rhythm is made from...", "long and short sounds", ["only colours", "only pictures", "map symbols"]), ("Which word means to perform at the same speed?", "keep a steady tempo", ["change instrument", "whisper words", "stop listening"])],
            "Pitch and dynamics": [("Which word describes how high or low a sound is?", "pitch", ["beat", "texture", "verse"]), ("Which word means quiet in music?", "piano", ["forte", "allegro", "solo"]), ("Which word means loud in music?", "forte", ["piano", "rest", "duet"]), ("A small bird usually makes a sound with...", "a high pitch", ["a low pitch", "no pitch", "only a beat"])],
            "Instrument sounds": [("Which instrument is played by hitting it?", "drum", ["flute", "violin", "trumpet"]), ("Which instrument is played by blowing?", "recorder", ["triangle", "drum", "xylophone"]), ("Which instrument has strings?", "violin", ["tambourine", "trumpet", "cymbals"]), ("Which instrument has black and white keys?", "piano", ["guitar", "flute", "drum"] )],
            "Notes and metre": [("How many beats does a crotchet usually last?", "1", ["2", "3", "4"]), ("How many beats does a minim usually last?", "2", ["1", "3", "4"]), ("What does a rest tell a performer to do?", "be silent for a set time", ["play louder", "speed up", "repeat forever"]), ("In 4/4 time, how many crotchet beats are in each bar?", "4", ["2", "3", "6"])],
            "Orchestra families": [("Which family does the violin belong to?", "strings", ["woodwind", "brass", "percussion"]), ("Which family does the trumpet belong to?", "brass", ["strings", "woodwind", "keyboard"]), ("Which family does the flute belong to?", "woodwind", ["brass", "strings", "percussion"]), ("Which family does the timpani belong to?", "percussion", ["strings", "brass", "woodwind"])],
            "Melody and structure": [("What is a melody?", "a pattern of pitches forming a tune", ["a list of instruments", "only the volume", "a silent bar"]), ("What is an ostinato?", "a repeated musical pattern", ["a broken instrument", "a very high note", "the final applause"]), ("What does ABA describe?", "a musical structure", ["three instrument families", "three volume levels", "a type of microphone"]), ("A phrase in music is...", "a short musical idea", ["only one beat", "the concert ticket", "a written review"] )],
            "Reading notation": [("Where are musical notes written?", "on a stave", ["on a compass", "on a timeline", "on a bar chart"]), ("What does a treble clef help show?", "the pitch of written notes", ["the composer's age", "the ticket price", "the instrument colour"]), ("What raises a note by one semitone?", "a sharp", ["a rest", "a bar line", "a repeat mark"]), ("What divides music into bars?", "bar lines", ["clefs", "lyrics", "note stems"] )],
            "Harmony and texture": [("What is harmony?", "notes sounding together to support a melody", ["one silent beat", "the speed only", "a list of lyrics"]), ("What is a chord?", "three or more notes sounded together", ["one bar line", "one instrument case", "a single rest"]), ("What does texture describe?", "how musical parts are layered", ["the paper used for music", "the age of a song", "the concert location"]), ("A solo is performed by...", "one performer", ["two performers", "a full choir only", "no performers"] )],
            "Music history and listening": [("Who composed The Four Seasons?", "Antonio Vivaldi", ["William Shakespeare", "Isaac Newton", "Mary Anning"]), ("Which instrument is strongly linked with West African djembe music?", "drum", ["violin", "organ", "clarinet"]), ("A composer is someone who...", "creates music", ["builds concert halls", "sells tickets only", "tunes radios"]), ("When listening critically, what should you identify?", "musical features and evidence", ["the performer's address", "private details", "a random guess"] )],
        },
    },
    "Physical Education": {
        "topics": {
            "early": ["Movement skills", "Safe activity", "Games and teamwork"],
            "middle": ["Fitness", "Game skills and tactics", "Dance and gymnastics"],
            "upper": ["Health and training", "Tactics and fair play", "Outdoor and water safety"],
        },
        "banks": {
            "Movement skills": [("Which is a travelling movement?", "running", ["balancing still", "stretching one arm", "standing quietly"]), ("Which action uses balance?", "holding still on one foot", ["reading a book", "clapping a rhythm", "naming colours"]), ("When catching a soft ball, your eyes should...", "watch the ball", ["close", "look behind you", "look at the floor"]), ("Which movement sends a ball along the ground with your foot?", "dribbling", ["catching", "balancing", "jumping"] )],
            "Safe activity": [("What should happen before vigorous exercise?", "a gradual warm-up", ["a large meal", "sitting completely still", "wearing unsafe jewellery"]), ("Why is drinking water important during activity?", "it helps replace fluid", ["it changes the score", "it makes shoes faster", "it replaces sleep"]), ("Which footwear is safest for running?", "well-fitting trainers", ["loose slippers", "bare feet on a road", "shoes with untied laces"]), ("If an activity causes sharp pain, what should a pupil do?", "stop and tell a trusted adult", ["hide it", "continue faster", "leave without telling anyone"] )],
            "Games and teamwork": [("What helps a team work well?", "clear communication", ["ignoring teammates", "changing every rule", "keeping the ball always"]), ("What should happen after the whistle stops play?", "players stop safely", ["players keep running", "the score doubles", "everyone leaves silently"]), ("Which action shows sharing in a game?", "passing to a teammate", ["holding the ball all game", "moving the goal", "ignoring the rules"]), ("Why do games have rules?", "to make play fair and safe", ["to hide the score", "to stop teamwork", "to choose private information"] )],
            "Fitness": [("Which activity mainly develops stamina?", "steady running", ["one short stretch", "sitting down", "holding a pencil"]), ("Which activity can develop strength?", "controlled bodyweight exercises", ["watching television", "whispering", "reading a sign"]), ("What does flexibility describe?", "how freely joints can move", ["how loud a whistle is", "how fast a clock moves", "how many players score"]), ("Why should exercise intensity increase gradually?", "to help the body adapt safely", ["to avoid all movement", "to change the rules", "to guarantee winning"] )],
            "Game skills and tactics": [("What is finding space in a game?", "moving where a teammate can pass", ["standing behind every player", "leaving the playing area", "holding an opponent"]), ("Why use a short pass?", "to send the ball accurately to a nearby teammate", ["to stop the game", "to make the pitch smaller", "to avoid teammates"]), ("What is marking?", "staying near an opponent to limit options", ["writing the score", "drawing pitch lines", "choosing team colours"]), ("When should a team change tactics?", "when evidence shows the current plan is not working", ["after every second", "only when winning", "without watching play"] )],
            "Dance and gymnastics": [("What is a sequence?", "movements performed in an order", ["one still shape only", "a list of scores", "a type of shoe"]), ("What makes a safe gymnastics landing?", "bent knees and control", ["locked knees", "landing on another person", "looking away"]), ("What does unison mean in dance?", "performers move together at the same time", ["everyone moves randomly", "one performer is silent", "the music stops"]), ("What is a transition?", "a controlled link between movements", ["the final score", "a sports drink", "a team name"] )],
            "Health and training": [("What usually happens to heart rate during exercise?", "it increases", ["it always stops", "it becomes a temperature", "it becomes the score"]), ("Why are rest days useful?", "they allow recovery and adaptation", ["they remove the need for sleep", "they guarantee a win", "they replace food"]), ("Which plan best supports fitness?", "regular varied activity with recovery", ["one extreme session each year", "no warm-up or rest", "only watching sport"]), ("What is endurance?", "the ability to sustain activity", ["the colour of equipment", "a type of whistle", "the number on a shirt"] )],
            "Tactics and fair play": [("What does fair play include?", "respecting rules, officials and opponents", ["arguing every decision", "hiding fouls", "changing the score"]), ("Why create width in an invasion game?", "to spread defenders and create space", ["to make the pitch narrower", "to stop passing", "to crowd one spot"]), ("What is feedback for?", "helping performance improve", ["embarrassing a player", "revealing private data", "changing the weather"]), ("What should a captain model?", "calm communication and respect", ["blaming others", "ignoring safety", "breaking rules to win"] )],
            "Outdoor and water safety": [("What should pupils do before an outdoor activity?", "follow the adult's safety briefing", ["leave the group", "hide the route", "ignore weather advice"]), ("Where should swimming lessons take place?", "in a supervised safe area", ["alone in unknown water", "where signs forbid swimming", "without an adult knowing"]), ("If someone is in difficulty in water, a child should...", "call a trained adult or emergency help", ["jump in without training", "walk away", "keep it secret"]), ("Why check weather and equipment?", "to manage foreseeable risks", ["to choose a winner", "to collect addresses", "to avoid teamwork"] )],
        },
    },
    "Religious Education": {
        "topics": {
            "early": ["Belonging and belief", "Special places", "Festivals and stories"],
            "middle": ["Christianity", "Judaism and Islam", "Hinduism, Sikhism and Buddhism"],
            "upper": ["Comparing beliefs", "Ethics and values", "Religion in modern Britain"],
        },
        "banks": {
            "Belonging and belief": [("A belief is...", "an idea someone accepts as true", ["a type of building", "a musical beat", "a sports score"]), ("Which action shows respect for another person's belief?", "listening without mocking", ["interrupting", "calling it silly", "refusing all discussion"]), ("A religious community is a group of people who...", "share a faith or tradition", ["all play one sport", "all live at one address", "must be the same age"]), ("Which statement is respectful?", "People may have different beliefs or no religious belief.", ["Everyone must believe the same thing.", "Only one pupil may speak.", "Questions are never allowed."])],
            "Special places": [("What is a church?", "a Christian place of worship", ["a Sikh place of worship", "a Jewish place of worship", "a Muslim place of worship"]), ("What is a mosque?", "a Muslim place of worship", ["a Christian place of worship", "a Hindu festival", "a Jewish holy book"]), ("What is a synagogue?", "a Jewish place of worship", ["a Buddhist festival", "a Muslim holy book", "a Christian ceremony"]), ("What is a gurdwara?", "a Sikh place of worship", ["a Jewish festival", "a Christian holy book", "a Hindu god"] )],
            "Festivals and stories": [("Which festival celebrates the birth of Jesus for Christians?", "Christmas", ["Eid al-Fitr", "Diwali", "Vaisakhi"]), ("Which festival is often called the festival of lights by Hindus, Sikhs and Jains?", "Diwali", ["Lent", "Passover", "Ramadan"]), ("Which celebration marks the end of Ramadan?", "Eid al-Fitr", ["Hanukkah", "Easter", "Vaisakhi"]), ("Why are religious stories studied?", "they can teach beliefs and values", ["they reveal passwords", "they replace every history source", "they give every person the same view"] )],
            "Christianity": [("What is the Christian holy book?", "the Bible", ["the Qur'an", "the Torah scrolls", "the Guru Granth Sahib"]), ("Who is central to Christian belief?", "Jesus", ["Moses only", "Guru Nanak", "the Buddha"]), ("What does Easter remember for Christians?", "the death and resurrection of Jesus", ["the end of Ramadan", "the Exodus", "the birth of Guru Nanak"]), ("Which practice is common in Christian worship?", "prayer", ["sharing passwords", "ignoring others", "collecting private addresses"] )],
            "Judaism and Islam": [("What is the Jewish holy text at the centre of the Torah?", "the Five Books of Moses", ["the New Testament", "the Vedas", "the Guru Granth Sahib"]), ("What is the Muslim holy book?", "the Qur'an", ["the Bible", "the Torah", "the Tripitaka"]), ("What is Ramadan?", "a month when many Muslims fast during daylight", ["a Jewish new year", "a Christian pilgrimage place", "a Sikh holy book"]), ("What does Shabbat mean in Judaism?", "a weekly day of rest and worship", ["a harvest tool", "a type of church", "a month of fasting"] )],
            "Hinduism, Sikhism and Buddhism": [("Which text is the Sikh holy scripture?", "the Guru Granth Sahib", ["the Qur'an", "the Bible", "the Torah"]), ("Who founded Sikhism?", "Guru Nanak", ["Moses", "St Paul", "Emperor Ashoka"]), ("What is puja in Hindu traditions?", "worship", ["a sports contest", "a map", "a school timetable"]), ("What is meditation?", "a practice of focused attention", ["a type of building", "a festival meal only", "a holy book"] )],
            "Comparing beliefs": [("What is a fair way to compare religions?", "use accurate sources and note similarities and differences", ["rank people", "use stereotypes", "assume every follower is identical"]), ("Which idea appears in many religious and non-religious worldviews?", "care for other people", ["share passwords", "ignore suffering", "avoid all questions"]), ("Why might followers practise a religion differently?", "traditions and interpretations can vary", ["all followers are identical", "facts do not matter", "places control every choice"]), ("A worldview is...", "a way of understanding life and the world", ["a weather forecast", "a sports formation", "a private account"] )],
            "Ethics and values": [("What is an ethical question?", "a question about what is right or wrong", ["a question about shoe size", "a times-table fact", "a map coordinate"]), ("Which action best shows justice?", "using fair rules", ["favouring friends", "hiding evidence", "mocking a minority"]), ("What does compassion mean?", "noticing suffering and wanting to help", ["winning every argument", "keeping all resources", "avoiding responsibility"]), ("Why give reasons in an ethical discussion?", "to support a view with evidence and values", ["to reveal private details", "to silence others", "to guarantee agreement"] )],
            "Religion in modern Britain": [("Britain today includes people who...", "follow many religions or no religion", ["all share one belief", "must attend one place", "cannot change a view"]), ("What protects freedom of religion or belief?", "human rights law", ["a sports rule", "a school password", "a weather warning"]), ("What is interfaith dialogue?", "people of different faiths talking and learning together", ["a contest to choose a winner", "a private account", "a ban on questions"]), ("Which source best shows what a community believes?", "reliable accounts from that community and scholars", ["a stereotype", "an anonymous insult", "one unsupported guess"] )],
        },
    },
    "PSHE": {
        "topics": {
            "early": ["Feelings and friendship", "Healthy routines", "Trusted adults and privacy"],
            "middle": ["Respectful relationships", "Online safety", "Money and community"],
            "upper": ["Wellbeing and resilience", "Consent and boundaries", "Decisions and first response"],
        },
        "banks": {
            "Feelings and friendship": [("What is a kind way to join a game?", "ask politely", ["push in", "take equipment", "shout at players"]), ("If a friend looks upset, what is a helpful first step?", "ask if they want to talk", ["laugh", "share it online", "demand private details"]), ("Which action can help with a strong feeling?", "pause and take slow breaths", ["hurt someone", "break an object", "keep every worry secret"]), ("A good friend should...", "respect boundaries", ["control every choice", "demand passwords", "spread rumours"] )],
            "Healthy routines": [("Which habit helps protect teeth?", "brushing twice a day", ["sharing a toothbrush", "never visiting a dentist", "eating sweets all day"]), ("Why is sleep important?", "it supports growth, learning and wellbeing", ["it replaces water", "it guarantees winning", "it removes the need for food"]), ("Which is part of a balanced day?", "food, activity, rest and sleep", ["screens all night", "only one type of food", "no movement"]), ("When should hands be washed?", "after using the toilet and before eating", ["only once a week", "only when an adult watches", "never after outdoor play"] )],
            "Trusted adults and privacy": [("Which information should not be posted publicly?", "a home address", ["a favourite colour", "a book title", "a made-up character"]), ("If something makes a child feel unsafe, they should...", "tell a trusted adult", ["keep it secret", "deal with it alone", "post private details"]), ("Should a password be shared with friends?", "No, keep it private and tell a trusted adult if help is needed.", ["Yes, with everyone.", "Yes, post it publicly.", "Only if asked by a stranger."]), ("What is a trusted adult?", "an adult chosen for safe help and support", ["any stranger online", "someone demanding secrecy", "a person asking for passwords"] )],
            "Respectful relationships": [("What does respect include?", "listening and accepting boundaries", ["controlling others", "mocking differences", "sharing secrets"]), ("What is bullying?", "repeated behaviour intended to hurt or intimidate", ["one polite disagreement", "asking for help", "taking turns"]), ("If someone is bullied, what should a pupil do?", "tell a trusted adult and keep seeking help", ["join in", "hide all evidence", "promise secrecy"]), ("A healthy friendship allows people to...", "have other friends and make choices", ["control each other", "demand live locations", "share every password"] )],
            "Online safety": [("What should a pupil do with an unexpected message asking for a photo?", "do not send it; block or report and tell a trusted adult", ["send it quickly", "give an address too", "keep the request secret"]), ("Why can online information be unreliable?", "people can post mistakes or pretend to be someone else", ["everything online is checked", "websites cannot change", "screens always prove truth"]), ("Which is a strong password habit?", "use a unique password and keep it private", ["use 1234 everywhere", "share it in a group chat", "write it publicly"]), ("What is cyberbullying?", "bullying using digital services", ["a software update", "a school lesson", "a private bookmark"] )],
            "Money and community": [("What is a need?", "something essential such as food or shelter", ["every new toy", "the latest game", "a luxury holiday"]), ("What is a budget?", "a plan for money coming in and going out", ["a secret password", "a shopping advert", "a type of banknote"]), ("Why compare prices?", "to make an informed choice", ["to guarantee free goods", "to reveal account details", "to avoid a receipt"]), ("Which action supports a community?", "looking after shared spaces", ["damaging equipment", "excluding neighbours", "dropping litter"] )],
            "Wellbeing and resilience": [("What does resilience mean?", "coping with difficulties and trying helpful next steps", ["never feeling upset", "solving everything alone", "hiding every mistake"]), ("Which action can support wellbeing?", "talking to someone trusted", ["avoiding sleep", "keeping serious worries secret", "reading hurtful comments"]), ("What is a realistic response to a mistake?", "learn from it and try a new strategy", ["give up forever", "blame someone else", "hide the evidence"]), ("When a worry affects daily life, what is a good step?", "seek support from a trusted adult", ["self-diagnose online", "share private details publicly", "ignore it indefinitely"] )],
            "Consent and boundaries": [("What does consent mean?", "freely agreeing to something", ["staying silent under pressure", "being forced", "agreeing once forever"]), ("Can someone change their mind after saying yes?", "Yes", ["No", "Only online", "Only if a friend agrees"]), ("What should happen when someone says stop?", "the action should stop", ["pressure them", "laugh", "ask for a password"]), ("Which is a healthy boundary?", "choosing not to share private information", ["demanding another person's messages", "tracking someone secretly", "ignoring discomfort"] )],
            "Decisions and first response": [("What is the first step in a careful decision?", "identify the choices and possible consequences", ["copy a stranger", "hide the problem", "share passwords"]), ("In a serious emergency, which UK number can call emergency services?", "999", ["111 for every emergency", "123", "411"]), ("Before helping in an accident, a child should first...", "check for danger and get an adult or emergency help", ["rush into danger", "film the scene", "move everyone immediately"]), ("If medicine is found unattended, a child should...", "leave it alone and tell a trusted adult", ["taste it", "give it to a friend", "post a photo with the location"] )],
        },
    },
}


def _band(year_group: int) -> str:
    if year_group in {1, 2}:
        return "early"
    if year_group in {3, 4}:
        return "middle"
    if year_group in {5, 6}:
        return "upper"
    raise ValueError("year_group must be between 1 and 6")


def topics_for_subject(subject: str, year_group: int) -> list[str]:
    band = _band(year_group)
    if subject in LANGUAGE_BANKS:
        return list(LANGUAGE_TOPICS[band])
    config = FOUNDATION_CONFIGS.get(subject)
    if not config:
        raise ValueError(f"Unsupported additional subject: {subject}")
    return list(config["topics"][band])


def _language_questions(subject: str, topic: str, year_group: int, index: int) -> list[tuple[str, str]]:
    entries = LANGUAGE_BANKS[subject][topic]
    rng = stable_random(subject, year_group, topic, index)
    questions: list[tuple[str, str]] = []
    foreign_values = [foreign for foreign, _english in entries]
    english_values = [english for _foreign, english in entries]
    for offset in range(10):
        foreign, english = entries[(offset + index) % len(entries)]
        if offset % 2 == 0:
            wrong = [value for value in english_values if value.casefold() != english.casefold()]
            questions.append(make_mcq(f"What does '{foreign}' mean?", english, wrong, rng))
        else:
            wrong = [value for value in foreign_values if value.casefold() != foreign.casefold()]
            questions.append(make_mcq(f"Which {subject} expression means '{english}'?", foreign, wrong, rng))
    return questions


def _foundation_questions(subject: str, topic: str, year_group: int, index: int) -> list[tuple[str, str]]:
    items = FOUNDATION_CONFIGS[subject]["banks"][topic]
    rng = stable_random(subject, year_group, topic, index)
    return [
        make_mcq(*items[(offset + index) % len(items)], rng)
        for offset in range(10)
    ]


def generate_subject_homework(subject: str, year_group: int, topic: str, index: int) -> tuple[str, list[str]]:
    topics = topics_for_subject(subject, year_group)
    if topic not in topics:
        raise ValueError(f"Unknown Year {year_group} {subject} topic: {topic}")
    if subject in LANGUAGE_BANKS:
        questions = _language_questions(subject, topic, year_group, index)
        note = "Optional language enrichment for Years 1-2; foreign languages are statutory from KS2." if year_group in {1, 2} else ""
    else:
        questions = _foundation_questions(subject, topic, year_group, index)
        note = "Use imaginary examples only; never include a child's private information." if subject == "PSHE" else ""
    return render_homework(subject, year_group, topic, index, questions, note=note)


def generate_subject_year(subject: str, slug: str, year_group: int, count: int = 300) -> list[dict]:
    topics = topics_for_subject(subject, year_group)
    config = YEAR_CONFIG[year_group]
    batch: list[dict] = []
    for index in range(1, count + 1):
        topic = topics[(index - 1) % len(topics)]
        content, answers = generate_subject_homework(subject, year_group, topic, index)
        batch.append(build_batch_item(
            content=content,
            answers=answers,
            year_group=year_group,
            subject=subject,
            topic=topic,
            homework_minutes=config["homework_minutes"],
            key_stage=config["key_stage"],
            doc_id=f"{slug}_y{year_group}_{index:04d}",
        ))
        if index % 100 == 0:
            print(f"  Generated {index}/{count}")
    return batch


def populate_subject(store: Any, subject: str, slug: str) -> None:
    print(f"RAG target: {store.store.database_target}")
    for year_group in range(1, 7):
        expected = HOMEWORK_COUNT[year_group]
        existing = count_year_homework(store, year_group, subject)
        if existing >= expected:
            print(f"Year {year_group}: complete ({existing}/{expected})")
            continue
        homework = generate_subject_year(subject, slug, year_group, expected)
        added = add_homework_in_batches(store, homework)
        print(f"Year {year_group}: added {added}; target {len(homework)}")
    get_rag_stats(store)

