#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
11+ (Eleven Plus) English Practice Generator
==============================================

Generates ORIGINAL 11+-style English practice questions and stores them in
the RAG store, mirroring the structure of elevenplus_math_generator.py.

Usage: Run this script directly to check whether 11+ English homework already
exists in the RAG store, and if not, generate a batch of 500 sets and add it.
"""

import sys
import os
import json
import random
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from src.elevenplus.elevenplus_rag import get_elevenplus_rag_store
except ImportError:
    get_elevenplus_rag_store = None

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ---------------------------------------------------------------------------
# Topic list + weights, based on GL Assessment's published English question
# mix (Spelling 8 : Punctuation 8 : Vocabulary-cloze 8 : Word meaning 4 :
# Grammar 3), plus a Reading Comprehension topic.
# ---------------------------------------------------------------------------
ELEVEN_PLUS_ENGLISH_TOPICS = [
    ("Spelling", 8),
    ("Capital Letters and Punctuation", 8),
    ("Vocabulary: Word Choice (Cloze)", 8),
    ("Vocabulary: Synonyms and Antonyms", 4),
    ("Grammar", 3),
    ("Reading Comprehension", 5),
]

EXAM_STYLE = "GL Assessment"
HOMEWORK_MINUTES = "45-50"
KEY_STAGE = "11+"
YEAR_GROUP = 6

# ---------------------------------------------------------------------------
# Word bank and spelling word details
# ---------------------------------------------------------------------------
WORD_BANK = [
    {"word": "abundant", "synonym": "plentiful", "antonym": "scarce", "clue": "existing in large quantities"},
    {"word": "diligent", "synonym": "hard-working", "antonym": "lazy", "clue": "showing care and effort in work"},
    {"word": "eloquent", "synonym": "articulate", "antonym": "inarticulate", "clue": "fluent and persuasive in speech"},
    {"word": "resilient", "synonym": "tough", "antonym": "fragile", "clue": "able to recover quickly from difficulty"},
    {"word": "tenacious", "synonym": "persistent", "antonym": "yielding",
     "clue": "holding firmly to a course of action"},
    {"word": "benevolent", "synonym": "kind", "antonym": "cruel", "clue": "well meaning and kindly"},
    {"word": "formidable", "synonym": "daunting", "antonym": "unimpressive",
     "clue": "inspiring fear or respect through being impressive"},
    {"word": "meticulous", "synonym": "careful", "antonym": "careless", "clue": "showing great attention to detail"},
    {"word": "melancholy", "synonym": "sad", "antonym": "cheerful", "clue": "a feeling of deep sadness"},
    {"word": "versatile", "synonym": "adaptable", "antonym": "limited",
     "clue": "able to adapt to many different functions"},
    {"word": "vivacious", "synonym": "lively", "antonym": "dull", "clue": "attractively energetic and full of life"},
    {"word": "audacious", "synonym": "bold", "antonym": "timid", "clue": "showing a willingness to take bold risks"},
    {"word": "belligerent", "synonym": "hostile", "antonym": "peaceful", "clue": "aggressive and eager to fight"},
    {"word": "indignant", "synonym": "annoyed", "antonym": "content", "clue": "feeling anger at unfair treatment"},
    {"word": "alleviate", "synonym": "ease", "antonym": "worsen", "clue": "to make suffering less severe"},
    {"word": "articulate", "synonym": "fluent", "antonym": "tongue-tied", "clue": "able to express thoughts clearly"},
    {"word": "generous", "synonym": "giving", "antonym": "stingy", "clue": "willing to give more than is necessary"},
    {"word": "cautious", "synonym": "careful", "antonym": "reckless", "clue": "careful to avoid danger or mistakes"},
    {"word": "ancient", "synonym": "old", "antonym": "modern", "clue": "belonging to the very distant past"},
    {"word": "enormous", "synonym": "huge", "antonym": "tiny", "clue": "very large in size or amount"},
    {"word": "brilliant", "synonym": "outstanding", "antonym": "dreadful",
     "clue": "exceptionally clever or impressive"},
    {"word": "peculiar", "synonym": "strange", "antonym": "ordinary", "clue": "unusual or odd"},
    {"word": "genuine", "synonym": "authentic", "antonym": "fake", "clue": "truly what it is said to be"},
    {"word": "reluctant", "synonym": "unwilling", "antonym": "eager", "clue": "hesitant before doing something"},
    {"word": "furious", "synonym": "enraged", "antonym": "calm", "clue": "extremely angry"},
    {"word": "timid", "synonym": "shy", "antonym": "bold", "clue": "showing a lack of courage or confidence"},
    {"word": "vast", "synonym": "immense", "antonym": "minute", "clue": "of very great extent"},
    {"word": "fragile", "synonym": "delicate", "antonym": "sturdy", "clue": "easily broken or damaged"},
    {"word": "curious", "synonym": "inquisitive", "antonym": "indifferent", "clue": "eager to know or learn something"},
    {"word": "silent", "synonym": "quiet", "antonym": "noisy", "clue": "making no sound at all"},
]

SPELLING_WORDS = [
    "necessary", "separate", "definitely", "occasion", "embarrass",
    "rhythm", "conscience", "parliament", "questionnaire", "vehicle",
    "beautiful", "believe", "receive", "achieve", "surprise",
    "immediately", "disappear", "accommodate", "guarantee", "unnecessary",
    "government", "environment", "argument", "occurred", "misspell",
    "restaurant", "February", "library", "particular", "temperature",
]

SPELLING_DETAILS = {
    "necessary": {
        "explanation": "The correct spelling is 'necessary'. A common error is to double the 'c' or write a single 's'. Think of it as: 1 collar (one 'c') and 2 sleeves (two 's's) to be dressed appropriately.",
        "tip": "Remember: 1 Collar (C), 2 Sleeves (S) is the ultimate trick!"
    },
    "separate": {
        "explanation": "The correct spelling is 'separate'. A very common mistake is spelling it as 'seperate' with an 'e'.",
        "tip": "Look out for the word 'a rat' in sep-a-rat-e!"
    },
    "definitely": {
        "explanation": "The correct spelling is 'definitely'. It comes from the root word 'finite'. Common misspellings include 'definately' or 'definitly'.",
        "tip": "Remember that 'finite' is inside 'definitely'!"
    },
    "occasion": {
        "explanation": "The correct spelling is 'occasion'. It has double 'c' but a single 's'. Common mistakes include 'ocassion' or 'occassion'.",
        "tip": "Two Cups of Coffee (CC) on one special occaSion!"
    },
    "embarrass": {
        "explanation": "The correct spelling is 'embarrass'. It requires double 'r' and double 's'. Common errors often omit one 'r' or one 's'.",
        "tip": "Think of turning double Red (RR) and feeling double Shy (SS) when embarrassed."
    },
    "rhythm": {
        "explanation": "The correct spelling is 'rhythm'. It is unusual because it doesn't contain any traditional vowels (a, e, i, o, u) except 'y'.",
        "tip": "Use the mnemonic: Rhythm Helps Your Two Feet Move!"
    },
    "conscience": {
        "explanation": "The correct spelling is 'conscience'. It contains 'science' at the end. A common error is writing 'conscience' without the 'sci'.",
        "tip": "Your conscience is your inner 'con' + 'science'!"
    },
    "parliament": {
        "explanation": "The correct spelling is 'parliament'. People often forget the 'a' before 'ment' and write 'parliment'. It comes from the French 'parler' (to speak).",
        "tip": "Think of a parliament of owls talking: 'parlia-ment'!"
    },
    "questionnaire": {
        "explanation": "The correct spelling is 'questionnaire'. It has double 'n' and ends in 'aire'. It is frequently misspelled with a single 'n'.",
        "tip": "It is a 'question' with a double 'n' and 'aire' suffix!"
    },
    "vehicle": {
        "explanation": "The correct spelling is 'vehicle'. The silent 'h' is a common omission, resulting in 'veicle' or 'vehical'.",
        "tip": "Pronounce the silent 'h' in your head to remember its placement!"
    },
    "beautiful": {
        "explanation": "The correct spelling is 'beautiful'. It starts with the vowel string 'eau'. Common errors include 'beautifull' or 'beutiful'.",
        "tip": "Remember: Big Elephants Are Ugly (B-E-A-U-tiful)!"
    },
    "believe": {
        "explanation": "The correct spelling is 'believe'. It follows the 'i before e except after c' rule.",
        "tip": "Never believe a lie: there is a 'lie' in believe!"
    },
    "receive": {
        "explanation": "The correct spelling is 'receive'. It follows the 'i before e except after c' rule, so 'e' comes before 'i' because it follows 'c'.",
        "tip": "Remember the classic rule: I before E except after C!"
    },
    "achieve": {
        "explanation": "The correct spelling is 'achieve'. It follows the 'i before e' rule as there is no 'c' preceding it.",
        "tip": "You must 'ach-ieve' with an 'i' before 'e'!"
    },
    "surprise": {
        "explanation": "The correct spelling is 'surprise'. People often forget the first 'r' and spell or pronounce it as 'suprise'.",
        "tip": "Don't let the first 'r' surprise you!"
    },
    "immediately": {
        "explanation": "The correct spelling is 'immediately'. It has double 'm' and ends in 'ately'. Common errors include 'imediately' or 'immediatly'.",
        "tip": "It contains 'immediate' + 'ly'. Watch out for the double 'm'!"
    },
    "disappear": {
        "explanation": "The correct spelling is 'disappear'. It has a single 's' but a double 'p'. It is formed by the prefix 'dis-' and the root 'appear'.",
        "tip": "Prefix 'dis-' + 'appear'. Single 's', double 'p'!"
    },
    "accommodate": {
        "explanation": "The correct spelling is 'accommodate'. It is famous for requiring double 'c' and double 'm'.",
        "tip": "The word has room to accommodate double C and double M!"
    },
    "guarantee": {
        "explanation": "The correct spelling is 'guarantee'. It starts with 'gua' and ends with double 'e'.",
        "tip": "It begins with 'gua' like guard, followed by ran-tee!"
    },
    "unnecessary": {
        "explanation": "The correct spelling is 'unnecessary'. It is formed by the prefix 'un-' and 'necessary'. This creates a double 'n', while keeping a single 'c' and double 's'.",
        "tip": "Un- + necessary. Double 'n', single 'c', double 's'!"
    },
    "government": {
        "explanation": "The correct spelling is 'government'. The silent 'n' is a very common mistake when people spell it phonetically.",
        "tip": "Remember that the government 'governs' the nation, so keep the 'n'!"
    },
    "environment": {
        "explanation": "The correct spelling is 'environment'. The silent 'n' before 'ment' is frequently omitted.",
        "tip": "Our environment has 'environ' (to surround) at its core, so don't drop the 'n'!"
    },
    "argument": {
        "explanation": "The correct spelling is 'argument'. Unlike 'argue', the 'e' is dropped when adding the suffix '-ment'.",
        "tip": "Drop the 'e' from 'argue' to get 'argument'!"
    },
    "occurred": {
        "explanation": "The correct spelling is 'occurred'. It has double 'c' and double 'r'. Because the stress is on the second syllable of 'occur', the final consonant is doubled before adding '-ed'.",
        "tip": "Double C, double R for occurred!"
    },
    "misspell": {
        "explanation": "The correct spelling is 'misspell'. It is formed from the prefix 'mis-' and 'spell', resulting in a double 's'.",
        "tip": "Mis- + spell = misspell. Do not misspell with one 's'!"
    },
    "restaurant": {
        "explanation": "The correct spelling is 'restaurant'. The vowel combination 'au' in the final syllable 'rant' is a common source of errors.",
        "tip": "Think of a 'rest' + 'au' (gold) + 'rant'!"
    },
    "February": {
        "explanation": "The correct spelling is 'February'. The first 'r' is often silent in spoken English, leading to 'Febuary'.",
        "tip": "Remember 'Feb-ru-ary' with the 'r' pronounced clearly in your mind!"
    },
    "library": {
        "explanation": "The correct spelling is 'library'. Pronouncing it as 'libry' is a common speech error that causes spelling mistakes.",
        "tip": "There is a 'bra' (and a 'li') in the li-bra-ry!"
    },
    "particular": {
        "explanation": "The correct spelling is 'particular'. Make sure to include the 'u' in the middle syllable 'cul'.",
        "tip": "Pay particular attention to the 'u' in par-tic-u-lar!"
    },
    "temperature": {
        "explanation": "The correct spelling is 'temperature'. The 'er' in the middle is often dropped or misspelled in writing.",
        "tip": "Think of 'temper' + 'ature' to make spelling it easy!"
    }
}

COMPREHENSION_ANIMALS = ["fox", "otter", "owl", "badger", "hedgehog", "heron", "squirrel"]
COMPREHENSION_HABITATS = ["riverbank", "old oak forest", "hillside burrow", "reedy marsh", "quiet hedgerow"]
COMPREHENSION_DAY_PERIODS = ["morning", "evening", "dusk", "early afternoon"]
COMPREHENSION_ACTIVITY1 = ["searched for food", "groomed its fur", "watched the sky", "explored the riverbank",
                           "rested in the shade"]
COMPREHENSION_ACTIVITY2 = ["returning to its den", "settling down to sleep", "meeting the rest of its family",
                           "moving on to a new spot"]
COMPREHENSION_EVENTS = ["a sudden storm", "a loud noise nearby", "an unfamiliar visitor",
                        "a fallen branch blocking the path", "a sudden burst of rain"]
COMPREHENSION_RESPONSES = ["find shelter quickly", "stay very still and watch", "hurry back the way it came",
                           "investigate carefully", "call out to the rest of its family"]
COMPREHENSION_EMOTIONS = ["relieved", "curious", "tired but content", "cautious", "quietly proud"]


# ---------------------------------------------------------------------------
# MCQ helpers
# ---------------------------------------------------------------------------
def _build_question(num, text, correct, distractors, explanation, tip="", difficulty="standard"):
    """Render one MCQ block and return its structured answer record."""
    options = list(distractors) + [correct]
    random.shuffle(options)
    letters = ["A", "B", "C", "D", "E"]
    correct_letter = letters[options.index(correct)]

    lines = [f"{num}. {text}"]
    for letter, opt in zip(letters, options):
        lines.append(f"   {letter}) {opt}")
    block = "\n".join(lines)

    answer_record = {
        "q": num,
        "correct_letter": correct_letter,
        "correct_value": str(correct),
        "explanation": explanation,
        "tip": tip,
        "difficulty": difficulty,
    }
    return block, answer_record


def _misspell(word: str) -> str:
    """Produce a plausible wrong spelling of `word` using common error patterns."""
    word_list = list(word)
    pattern = random.choice(["double", "drop", "swap", "substitute"])

    if pattern == "double" and len(word_list) > 2:
        i = random.randint(0, len(word_list) - 1)
        word_list.insert(i, word_list[i])
    elif pattern == "drop" and len(word_list) > 3:
        i = random.randint(1, len(word_list) - 2)
        del word_list[i]
    elif pattern == "swap" and len(word_list) > 3:
        i = random.randint(0, len(word_list) - 2)
        word_list[i], word_list[i + 1] = word_list[i + 1], word_list[i]
    else:
        subs = {"ie": "ei", "ei": "ie", "ph": "f", "c": "s", "ance": "ence", "able": "ible"}
        joined = "".join(word_list)
        applied = False
        for a, b in subs.items():
            if a in joined:
                joined = joined.replace(a, b, 1)
                applied = True
                break
        if not applied:
            i = random.randint(0, len(word_list) - 1)
            word_list[i] = random.choice("aeiou") if word_list[i] not in "aeiou" else random.choice("bcdfg")
            joined = "".join(word_list)
        word_list = list(joined)

    result = "".join(word_list)
    return result if result != word else result + "e"


# ---------------------------------------------------------------------------
# Topic generators
# ---------------------------------------------------------------------------
def _gen_spelling(index: int) -> tuple:
    blocks, records = [], []
    words = random.sample(SPELLING_WORDS, min(10, len(SPELLING_WORDS)))
    while len(words) < 10:
        words.append(random.choice(SPELLING_WORDS))

    for i, word in enumerate(words, start=1):
        ask_correct = random.choice([True, False])
        misspellings = set()
        attempts = 0
        while len(misspellings) < 4 and attempts < 30:
            attempts += 1
            m = _misspell(word)
            if m != word:
                misspellings.add(m)
        misspellings = list(misspellings)[:4]
        while len(misspellings) < 4:
            misspellings.append(word + "e")

        details = SPELLING_DETAILS.get(word, {
            "explanation": f"The correct spelling of the word is '{word}'. Make sure you remember its standard syllable divisions and prefix/suffix rules.",
            "tip": f"Be careful with syllables in '{word}'!"
        })

        if ask_correct:
            text = "Which word is spelled correctly?"
            correct = word
            distractors = misspellings
            explanation = f"'{word}' is correct. {details['explanation']}"
        else:
            text = "Which word is spelled INCORRECTLY?"
            correct = misspellings[0]
            distractors = [word] + misspellings[1:4]
            while len(distractors) < 4:
                distractors.append(_misspell(word))
            explanation = f"'{misspellings[0]}' is misspelled. The correct spelling is '{word}'. {details['explanation']}"

        block, rec = _build_question(
            i, text, correct, distractors[:4],
            explanation=explanation, tip=details["tip"], difficulty="standard"
        )
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records


PUNCTUATION_TEMPLATES = [
    ("the dog ran across the field and barked loudly", "The dog ran across the field and barked loudly.",
     "Sentences must begin with a capital letter and end with appropriate final punctuation (such as a full stop).",
     "Always check both the start and end of a sentence first!"),
    ("sarah picked up her bag and left for school", "Sarah picked up her bag and left for school.",
     "Proper nouns (like names of people, e.g. 'Sarah') must always be capitalised. The sentence must also start with a capital and end with a full stop.",
     "Names of people like Sarah always take capital letters!"),
    ("can you believe it started raining again", "Can you believe it started raining again?",
     "This sentence is a direct question, so it must end with a question mark ('?') rather than a full stop.",
     "If the sentence asks something, make sure it ends with a question mark '?'!"),
    ("what a wonderful surprise this is", "What a wonderful surprise this is!",
     "This sentence is an exclamation expressing strong emotion, so it must begin with a capital and end with an exclamation mark ('!').",
     "Exclamatory sentences starting with 'What a...' or 'How...' usually end with '!'"),
    ("the childrens toys were scattered across the floor", "The children's toys were scattered across the floor.",
     "Since the toys belong to the children, we need a possessive apostrophe. 'Children' is plural but does not end in 's', so we add apostrophe-S ('s).",
     "For irregular plural nouns like children and men, add apostrophe-S ('s) to show possession!"),
    ("james said i will be there at six oclock", "James said, \"I will be there at six o'clock.\"",
     "This sentence contains direct speech. It needs: capital J for James; a comma before speech; opening speech marks; capital I for 'I'; an apostrophe in 'o'clock'; and final punctuation inside speech marks.",
     "Spoken words need speech marks, and the first spoken word inside them must start with a capital letter!"),
    ("we visited london paris and rome last summer", "We visited London, Paris, and Rome last summer.",
     "Proper nouns for cities ('London', 'Paris', 'Rome') must be capitalised. It also contains a list of items, requiring a comma to separate them.",
     "Proper nouns for cities must always be capitalised, and lists of items must be separated with commas!"),
    ("the cat sat quietly it did not move at all", "The cat sat quietly; it did not move at all.",
     "This sentence consists of two closely related independent clauses. To avoid a run-on sentence, we use a semicolon (';') to separate them.",
     "Use a semicolon ';' to join two complete, closely related thoughts without using a conjunction like 'and' or 'but'!")
]


def _gen_punctuation(index: int) -> tuple:
    blocks, records = [], []
    templates = random.sample(PUNCTUATION_TEMPLATES, min(10, len(PUNCTUATION_TEMPLATES)))
    while len(templates) < 10:
        templates.append(random.choice(PUNCTUATION_TEMPLATES))

    for i, (raw, correct, exp, tip) in enumerate(templates, start=1):
        wrong_versions = set()
        wrong_versions.add(correct.rstrip(".!?;\"") if correct[-1] in ".!?" else correct + ".")
        wrong_versions.add(correct[0].lower() + correct[1:])
        wrong_versions.add(raw)
        if correct[-1] in ".!?":
            wrong_versions.add(correct[:-1] + correct[-1] * 2)
        wrong_versions.discard(correct)
        wrong_versions = list(wrong_versions)[:4]
        while len(wrong_versions) < 4:
            wrong_versions.append(raw + "..")

        text = "Which sentence is correctly punctuated and capitalised?"
        block, rec = _build_question(
            i, text, correct, wrong_versions[:4],
            explanation=exp, tip=tip, difficulty="standard"
        )
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records


CLOZE_TEMPLATES = [
    ("The explorer felt {} when she finally reached the summit after months of preparation.", "elated",
     ["furious", "indifferent", "embarrassed", "confused"],
     "'Elated' means extremely happy and excited, which perfectly fits the context of reaching a mountain summit after months of preparation.",
     "Look for clues in the sentence. 'Reached the summit after months of preparation' suggests a triumphant feeling!"),
    ("Despite the {} weather, the match went ahead as planned.", "dreadful", ["pleasant", "mild", "sunny", "calm"],
     "The word 'Despite' introduces a contrast. The fact that the match 'went ahead as planned' despite the weather indicates the weather must have been bad/unfavourable.",
     "Contrast words like 'Despite' signal that the blank will have the opposite tone of the surrounding words."),
    ("The old bridge looked far too {} to hold the weight of a lorry.", "fragile",
     ["sturdy", "modern", "colourful", "narrow"],
     "A bridge that cannot hold a lorry's weight must be weak or easily broken. 'Fragile' means delicate or easily broken.",
     "Identify cause-and-effect: not being able to hold weight means the bridge must be weak or fragile."),
    ("Everyone was {} by how quickly the young pianist learned the piece.", "astonished",
     ["bored", "annoyed", "unsurprised", "confused"],
     "'Astonished' means extremely surprised or impressed, which is the most natural reaction to an impressive, rapid feat.",
     "Excellence usually evokes astonishment or admiration from observers!"),
    ("The detective examined every clue with {} attention to detail.", "meticulous",
     ["careless", "hurried", "casual", "brief"],
     "'Meticulous' means showing great attention to detail and being extremely careful, which is a key trait of a skilled detective.",
     "A professional detective is expected to be highly careful and detailed."),
    ("Although the twins looked alike, their personalities were completely {}.", "different",
     ["identical", "similar", "matching", "alike"],
     "The word 'Although' indicates contrast. Since the twins 'looked alike' (similar), their personalities must be the opposite, which is 'different'.",
     "Use the contrast of 'Although' to find an opposite trait."),
    ("The manager praised the team for their {} effort throughout the difficult project.", "tireless",
     ["lazy", "half-hearted", "occasional", "reluctant"],
     "Praise from a manager on a 'difficult project' implies positive, high-energy effort. 'Tireless' means working with great energy and without tiring.",
     "Look at the verb 'praised' - it requires a highly positive descriptor for the effort!"),
    ("It was such a {} day that we decided to stay inside and read.", "gloomy",
     ["glorious", "bright", "warm", "cloudless"],
     "Staying inside to read is typical of a dark, cold, or wet day. 'Gloomy' means dark or depressing, which matches the context.",
     "If people choose to stay inside, the weather is likely unfavorable or gloomy!")
]


def _gen_cloze(index: int) -> tuple:
    blocks, records = [], []
    templates = random.sample(CLOZE_TEMPLATES, min(10, len(CLOZE_TEMPLATES)))
    while len(templates) < 10:
        templates.append(random.choice(CLOZE_TEMPLATES))

    for i, (sentence, correct, wrong_options, exp, tip) in enumerate(templates, start=1):
        text = f"Choose the best word to complete the sentence:\n   \"{sentence.format('_____')}\""
        block, rec = _build_question(
            i, text, correct, wrong_options[:4],
            explanation=exp, tip=tip, difficulty="standard"
        )
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records


def _gen_synonyms_antonyms(index: int) -> tuple:
    blocks, records = [], []
    entries = random.sample(WORD_BANK, min(10, len(WORD_BANK)))
    while len(entries) < 10:
        entries.append(random.choice(WORD_BANK))

    for i, entry in enumerate(entries, start=1):
        ask_synonym = random.choice([True, False])
        target_word = entry["word"]
        correct = entry["synonym"] if ask_synonym else entry["antonym"]

        pool = [e for e in WORD_BANK if e["word"] != target_word]
        distractor_entries = random.sample(pool, min(4, len(pool)))
        distractors = [(e["antonym"] if ask_synonym else e["synonym"]) for e in distractor_entries]
        distractors = [d for d in distractors if d != correct][:4]
        while len(distractors) < 4:
            extra = random.choice(pool)
            candidate = extra["synonym"] if ask_synonym else extra["antonym"]
            if candidate != correct and candidate not in distractors:
                distractors.append(candidate)

        if ask_synonym:
            text = f"Which word means most nearly the SAME as '{target_word}'?"
            exp = f"'{target_word}' means {entry['clue']}. The word '{entry['synonym']}' shares this meaning closely, so they are synonyms."
            tip = f"Remember that '{target_word}' represents '{entry['synonym']}'!"
        else:
            text = f"Which word means most nearly the OPPOSITE of '{target_word}'?"
            exp = f"'{target_word}' means {entry['clue']}. The word '{entry['antonym']}' represents the opposite meaning (e.g. {entry['antonym']} means the opposite of {entry['synonym']})."
            tip = f"First think of a synonym for '{target_word}' (which is '{entry['synonym']}'), then find the opposite of that!"

        block, rec = _build_question(
            i, text, correct, distractors[:4],
            explanation=exp, tip=tip, difficulty="standard"
        )
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records


GRAMMAR_TEMPLATES = [
    ("The group of tourists {} arriving at the museum every hour.", "is", ["are", "were", "be", "being"],
     "This question tests subject-verb agreement. The subject of the sentence is 'The group' (singular), not 'tourists' (plural). Therefore, it requires the singular verb 'is'.",
     "Don't be distracted by plural nouns inside a prepositional phrase! Look for the main noun of the subject, which is 'The group' (singular)."),
    ("Neither of the boys {} finished their homework.", "has", ["have", "were", "are", "having"],
     "The pronoun 'Neither' is singular and requires a singular verb. 'Has' is singular, whereas 'have', 'were', and 'are' are plural.",
     "Pronouns like 'each', 'either', and 'neither' are grammatically singular and always take singular verbs!"),
    ("By the time we arrived, the film {} already started.", "had", ["has", "was", "did", "have"],
     "This sentence uses the past perfect tense because one past action (the film starting) occurred before another past action (arriving). The past perfect is formed with 'had' + past participle.",
     "When talking about two things that happened in the past, use 'had' for the action that happened first!"),
    ("She is the girl {} won the spelling competition.", "who", ["which", "whom", "whose", "what"],
     "The relative pronoun 'who' is used to refer to people, while 'which' refers to things. Since 'girl' is a person, 'who' is correct.",
     "Use 'who' for people and 'which' for animals or objects!"),
    ("The books, along with the box, {} on the top shelf.", "are", ["is", "was", "be", "being"],
     "The subject 'The books' is plural. Parenthetical phrases like 'along with the box' do not change the number of the subject. Therefore, the plural verb 'are' must be used.",
     "Ignore phrases set off by commas like 'along with...' when deciding if the verb should be singular or plural!"),
    ("If I {} known about the storm, I would have stayed home.", "had", ["have", "did", "was", "having"],
     "This is a conditional sentence expressing a past hypothesis (third conditional). It requires the past perfect tense ('had' + past participle) in the 'if' clause.",
     "For hypothetical past situations, always use 'If I had [done something], I would have [done something]...'"),
    ("Each of the students {} given their own locker.", "was", ["were", "are", "be", "being"],
     "The pronoun 'Each' is grammatically singular and requires a singular verb. Since the sentence is in the past tense, the singular 'was' is correct.",
     "Remember: 'Each' means 'each single one', so it is always singular!"),
    ("This is the best film {} I have ever seen.", "that", ["who", "whose", "when", "whom"],
     "The relative pronoun 'that' (or 'which') is used to introduce restrictive clauses referring to things like 'film'. 'Who' and 'whom' are only used for people.",
     "Use 'that' or 'which' when referring back to objects or things like a movie!")
]


def _gen_grammar(index: int) -> tuple:
    blocks, records = [], []
    templates = random.sample(GRAMMAR_TEMPLATES, min(10, len(GRAMMAR_TEMPLATES)))
    while len(templates) < 10:
        templates.append(random.choice(GRAMMAR_TEMPLATES))

    for i, (sentence, correct, wrong_options, exp, tip) in enumerate(templates, start=1):
        text = f"Choose the correct word to complete the sentence:\n   \"{sentence.format('_____')}\""
        block, rec = _build_question(
            i, text, correct, wrong_options[:4],
            explanation=exp, tip=tip, difficulty="standard"
        )
        blocks.append(block)
        records.append(rec)
    return "\n\n".join(blocks), records


def _build_passage(seed_val):
    """Build one short, entirely original comprehension passage plus questions."""
    random.seed(seed_val)
    animal = random.choice(COMPREHENSION_ANIMALS)
    habitat = random.choice(COMPREHENSION_HABITATS)
    day_period = random.choice(COMPREHENSION_DAY_PERIODS)
    activity1 = random.choice(COMPREHENSION_ACTIVITY1)
    activity2 = random.choice(COMPREHENSION_ACTIVITY2)
    event = random.choice(COMPREHENSION_EVENTS)
    response = random.choice(COMPREHENSION_RESPONSES)
    emotion = random.choice(COMPREHENSION_EMOTIONS)

    passage = (
        f"The {animal} lived quietly in the {habitat}. Every {day_period}, it "
        f"{activity1} before {activity2}. One day, {event} disturbed its "
        f"routine, and the {animal} had to {response}. By the time things had "
        f"settled, the {animal} felt {emotion}, and it carried on as before."
    )

    questions = [
        (f"Where did the {animal} live?", habitat,
         random.sample([h for h in COMPREHENSION_HABITATS if h != habitat], 4),
         f"The first sentence of the passage states: 'The {animal} lived quietly in the {habitat}.' This confirms the habitat.",
         "Look for the setting or location details in the opening sentence of a passage!"),
        (f"What did the {animal} do every {day_period}, before {activity2}?", activity1,
         random.sample([a for a in COMPREHENSION_ACTIVITY1 if a != activity1], 4),
         f"The second sentence says: 'Every {day_period}, it {activity1} before {activity2}.' This shows {activity1} was the regular routine.",
         "Scan for frequency keywords like 'every' or 'usually' to locate routine activities."),
        ("What disturbed the animal's routine?", event,
         random.sample([e for e in COMPREHENSION_EVENTS if e != event], 4),
         f"The passage states: 'One day, {event} disturbed its routine...' This describes the interrupting event.",
         "Look out for turning points or transition words like 'One day' to find the conflict."),
        ("How did the animal respond?", response,
         random.sample([r for r in COMPREHENSION_RESPONSES if r != response], 4),
         f"The passage notes that the {animal} had to {response} in reaction to the disturbance.",
         "Read the sentence immediately following the conflict to find how characters react."),
        ("How did the animal feel once things had settled?", emotion,
         random.sample([e for e in COMPREHENSION_EMOTIONS if e != emotion], 4),
         f"The passage states that after things settled, 'the {animal} felt {emotion}'.",
         "Character feelings are usually described towards the end of a narrative paragraph.")
    ]
    return passage, questions


def _gen_comprehension(index: int) -> tuple:
    blocks, records = [], []

    # First passage
    passage1, questions1 = _build_passage(index * 123)
    blocks.append(f"Read the passage, then answer the questions below.\n\n{passage1}\n")
    for i, (q_text, correct, distractors, exp, tip) in enumerate(questions1, start=1):
        block, rec = _build_question(
            i, q_text, correct, distractors[:4],
            explanation=exp, tip=tip, difficulty="standard"
        )
        blocks.append(block)
        records.append(rec)

    # Second passage (gives a full 10-question paper)
    passage2, questions2 = _build_passage(index * 456 + 1)
    blocks.append(f"\nRead the second passage, then answer the questions below.\n\n{passage2}\n")
    for j, (q_text, correct, distractors, exp, tip) in enumerate(questions2, start=len(questions1) + 1):
        block, rec = _build_question(
            j, q_text, correct, distractors[:4],
            explanation=exp, tip=tip, difficulty="standard"
        )
        blocks.append(block)
        records.append(rec)

    return "\n\n".join(blocks), records


TOPIC_GENERATORS = {
    "Spelling": _gen_spelling,
    "Capital Letters and Punctuation": _gen_punctuation,
    "Vocabulary: Word Choice (Cloze)": _gen_cloze,
    "Vocabulary: Synonyms and Antonyms": _gen_synonyms_antonyms,
    "Grammar": _gen_grammar,
    "Reading Comprehension": _gen_comprehension,
}


def generate_11plus_english_homework(topic: str, index: int) -> tuple:
    """Generate one 11+ English practice worksheet (10 MCQ questions) for a topic.

    Returns:
        (content, answer_records) where content is the student-facing
        worksheet text and answer_records is a list of structured dicts.
    """
    generator = TOPIC_GENERATORS.get(topic)
    if generator is None:
        raise ValueError(f"Unknown 11+ English topic: {topic}")
    body, answer_records = generator(index)
    header = (
        f"11+ English Practice (GL Assessment style) - {topic} (Set {index})\n"
        f"Answer each question by choosing the correct option A-E.\n\n"
    )
    return header + body, answer_records


# ---------------------------------------------------------------------------
# Batch generation / RAG store integration
# ---------------------------------------------------------------------------
def _weighted_topic_sequence(count: int) -> list:
    """Build an ordered topic list respecting published weight ratios."""
    topics, weights = zip(*ELEVEN_PLUS_ENGLISH_TOPICS)
    return random.choices(topics, weights=weights, k=count)


def check_11plus_english_exists() -> bool:
    """检查是否已有 11+ 英语练习"""
    try:
        store = get_elevenplus_rag_store()
        results = store.search(query="english", k=1, filters={"subject": "English"})
        return len(results) > 0
    except Exception:
        return False


def clean_11plus_english() -> int:
    """清理所有已有的 11+ 英语练习"""
    store = get_elevenplus_rag_store()
    results = store.search_by_metadata({"subject": "English"})

    if not results:
        print("  没有找到需要清理的 11+ 英语作业")
        return 0

    deleted = 0
    for item in results:
        doc_id = item.get("doc_id")
        if doc_id and store.delete_homework(doc_id):
            deleted += 1

    print(f"  已清理 {deleted} 份 11+ 英语作业")
    return deleted


def generate_11plus_english_batch(count: int = 500) -> list:
    """生成指定数量的 11+ 英语练习，主题按权重分布"""
    topic_sequence = _weighted_topic_sequence(count)
    batch_data = []

    for i, topic in enumerate(topic_sequence, start=1):
        content, answer_records = generate_11plus_english_homework(topic, i)

        metadata = {
            "year_group": YEAR_GROUP,
            "subject": "English",
            "homework_minutes": HOMEWORK_MINUTES,
            "key_stage": KEY_STAGE,
            "topic": topic,
            "exam_style": EXAM_STYLE,
            "question_format": "multiple_choice_5_options",
            "student_id": None,
            "correct_answers": json.dumps(answer_records, ensure_ascii=False),
        }
        doc_id = f"elevenplus_english_{i:03d}"
        batch_data.append({
            "content": content,
            "metadata": metadata,
            "doc_id": doc_id,
        })

        if i % 10 == 0:
            print(f"  已生成 {i}/{count} 份 11+ 英语作业")

    return batch_data


def main():
    """主函数：检查 11+ English 练习是否存在，缺失则生成"""
    print("==========================================================")
    print("       11+ English Practice Homework Generator           ")
    print("==========================================================\n")

    store = get_elevenplus_rag_store()
    exists = check_11plus_english_exists()
    status = "已有" if exists else "缺失"
    print(f"  11+ English: {status}")

    if exists:
        print("\n11+ English 练习已存在，无需生成。")
        return

    print("\n开始生成 11+ English 练习 (GL Assessment 风格, MCQ, 按官方主题权重分布)...")
    batch_data = generate_11plus_english_batch(count=500)

    if batch_data:
        store.add_batch_homework(batch_data)
        print(f"成功添加 {len(batch_data)} 份 11+ English 练习到 RAG 存储")

    stats = store.get_stats()
    print("\nRAG 存储统计:")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  按主题分布: {stats['by_subject']}")
    print(f"  按年级分布: {stats['by_year_group']}")


if __name__ == "__main__":
    main()
