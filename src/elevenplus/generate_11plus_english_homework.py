#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
11+ (Eleven Plus) English Practice Generator
==============================================

Generates ORIGINAL 11+-style English practice questions and stores them in
the RAG store, mirroring the structure of generate_all_math_homework.py /
generate_11plus_math_homework.py.

Why this doesn't scrape/copy real past papers
----------------------------------------------
Actual 11+ English past papers (GL Assessment, CEM/CSSE, Bond, CGP, and
individual grammar schools' specimen papers) are copyrighted — including
any comprehension passages they use. This script does NOT reproduce or
paraphrase any of that content. Instead it generates brand-new sentences,
passages and word lists, but weights topics and format to match the
*publicly documented* structure of the exam board most top-ranking grammar
schools actually use:

  GL Assessment (the successor to NFER, used by the majority of grammar
  school consortia in England):
    - English paper: multiple-choice, generally 5 answer options (A-E).
    - GL's own published breakdown of a typical English component gives
      roughly: Spelling (8 questions), Capital letters & punctuation
      (8 questions), Vocabulary/word-choice cloze (8 questions), Word
      meaning / synonyms & antonyms (4 questions), Grammar (3 questions) —
      so this generator weights Spelling, Punctuation and Vocabulary-cloze
      heaviest, Word meaning next, and Grammar lightest, in that same
      rough ratio.
    - GL English papers are also documented as testing reading
      comprehension, use of capital letters and punctuation, spelling,
      and word choice/grammar — so a Reading Comprehension topic is
      included too, using entirely invented short passages (never real
      literary extracts, which are copyrighted).

Sources for the above structural facts (topic weighting, format) are public
exam-board / tutoring-company explainer pages, not exam content itself — no
verbatim question, sentence, passage, or answer key from any real paper is
used anywhere in this file.

Usage mirrors generate_11plus_math_homework.py: run this script directly to
check whether 11+ English homework already exists in the RAG store, and if
not, generate a batch and add it.
"""
import sys
import os
import random

# 添加项目根目录到路径 (same pattern as generate_all_math_homework.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.elevenplus.elevenplus_rag import get_elevenplus_rag_store

os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ---------------------------------------------------------------------------
# Topic list + weights, based on GL Assessment's published English question
# mix (Spelling 8 : Punctuation 8 : Vocabulary-cloze 8 : Word meaning 4 :
# Grammar 3), plus a Reading Comprehension topic (also documented as part
# of the GL English component).
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
YEAR_GROUP = 6  # 11+ is sat at the start of Year 6 (some in Year 5)


# ---------------------------------------------------------------------------
# Word bank: common words with synonym/antonym/definition, general English
# knowledge (not copied from any specific book or exam). Includes some of
# the higher-tier words publicly noted as recurring in 11+ vocabulary
# practice, alongside everyday KS2 words for spelling/grammar work.
# ---------------------------------------------------------------------------
WORD_BANK = [
    {"word": "abundant", "synonym": "plentiful", "antonym": "scarce", "clue": "existing in large quantities"},
    {"word": "diligent", "synonym": "hard-working", "antonym": "lazy", "clue": "showing care and effort in work"},
    {"word": "eloquent", "synonym": "articulate", "antonym": "inarticulate", "clue": "fluent and persuasive in speech"},
    {"word": "resilient", "synonym": "tough", "antonym": "fragile", "clue": "able to recover quickly from difficulty"},
    {"word": "tenacious", "synonym": "persistent", "antonym": "yielding", "clue": "holding firmly to a course of action"},
    {"word": "benevolent", "synonym": "kind", "antonym": "cruel", "clue": "well meaning and kindly"},
    {"word": "formidable", "synonym": "daunting", "antonym": "unimpressive", "clue": "inspiring fear or respect through being impressive"},
    {"word": "meticulous", "synonym": "careful", "antonym": "careless", "clue": "showing great attention to detail"},
    {"word": "melancholy", "synonym": "sad", "antonym": "cheerful", "clue": "a feeling of deep sadness"},
    {"word": "versatile", "synonym": "adaptable", "antonym": "limited", "clue": "able to adapt to many different functions"},
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
    {"word": "brilliant", "synonym": "outstanding", "antonym": "dreadful", "clue": "exceptionally clever or impressive"},
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

# Common spelling-pattern words for the Spelling topic (kept separate from
# the higher-tier vocab bank so spelling practice stays age-appropriate).
SPELLING_WORDS = [
    "necessary", "separate", "definitely", "occasion", "embarrass",
    "rhythm", "conscience", "parliament", "questionnaire", "vehicle",
    "beautiful", "believe", "receive", "achieve", "surprise",
    "immediately", "disappear", "accommodate", "guarantee", "unnecessary",
    "government", "environment", "argument", "occurred", "misspell",
    "restaurant", "February", "library", "particular", "temperature",
]

COMPREHENSION_ANIMALS = ["fox", "otter", "owl", "badger", "hedgehog", "heron", "squirrel"]
COMPREHENSION_HABITATS = ["riverbank", "old oak forest", "hillside burrow", "reedy marsh", "quiet hedgerow"]
COMPREHENSION_DAY_PERIODS = ["morning", "evening", "dusk", "early afternoon"]
COMPREHENSION_ACTIVITY1 = ["searched for food", "groomed its fur", "watched the sky", "explored the riverbank", "rested in the shade"]
COMPREHENSION_ACTIVITY2 = ["returning to its den", "settling down to sleep", "meeting the rest of its family", "moving on to a new spot"]
COMPREHENSION_EVENTS = ["a sudden storm", "a loud noise nearby", "an unfamiliar visitor", "a fallen branch blocking the path", "a sudden burst of rain"]
COMPREHENSION_RESPONSES = ["find shelter quickly", "stay very still and watch", "hurry back the way it came", "investigate carefully", "call out to the rest of its family"]
COMPREHENSION_EMOTIONS = ["relieved", "curious", "tired but content", "cautious", "quietly proud"]


# ---------------------------------------------------------------------------
# MCQ helper (same approach as the maths generator: 5 options, A-E)
# ---------------------------------------------------------------------------
def _format_mcq(question_num: int, question_text: str, correct, distractors):
    """Return (question_block_text, correct_letter) for a 5-option MCQ."""
    options = list(distractors) + [correct]
    random.shuffle(options)
    letters = ["A", "B", "C", "D", "E"]
    correct_letter = letters[options.index(correct)]
    lines = [f"{question_num}. {question_text}"]
    for letter, opt in zip(letters, options):
        lines.append(f"   {letter}) {opt}")
    return "\n".join(lines), correct_letter


def _misspell(word: str) -> str:
    """Produce a plausible wrong spelling of `word` using common error
    patterns (double a letter, drop a letter, swap adjacent letters, or
    substitute a common confusable pair)."""
    word = list(word)
    pattern = random.choice(["double", "drop", "swap", "substitute"])

    if pattern == "double" and len(word) > 2:
        i = random.randint(0, len(word) - 1)
        word.insert(i, word[i])
    elif pattern == "drop" and len(word) > 3:
        i = random.randint(1, len(word) - 2)
        del word[i]
    elif pattern == "swap" and len(word) > 3:
        i = random.randint(0, len(word) - 2)
        word[i], word[i + 1] = word[i + 1], word[i]
    else:
        subs = {"ie": "ei", "ei": "ie", "ph": "f", "c": "s", "ance": "ence", "able": "ible"}
        joined = "".join(word)
        applied = False
        for a, b in subs.items():
            if a in joined:
                joined = joined.replace(a, b, 1)
                applied = True
                break
        if not applied:
            i = random.randint(0, len(word) - 1)
            word[i] = random.choice("aeiou") if word[i] not in "aeiou" else random.choice("bcdfg")
            joined = "".join(word)
        word = list(joined)

    result = "".join(word)
    return result if result != "".join(word) or True else result


# ---------------------------------------------------------------------------
# Topic generators — each returns (content_str, correct_answers_list)
# ---------------------------------------------------------------------------
def _gen_spelling(index: int) -> tuple:
    blocks, answers = [], []
    words = random.sample(SPELLING_WORDS, min(10, len(SPELLING_WORDS)))
    while len(words) < 10:
        words.append(random.choice(SPELLING_WORDS))
    for i, word in enumerate(words, start=1):
        ask_correct = random.choice([True, False])
        misspellings = set()
        attempts = 0
        while len(misspellings) < 4 and attempts < 20:
            attempts += 1
            m = _misspell(word)
            if m != word:
                misspellings.add(m)
        misspellings = list(misspellings)[:4]
        while len(misspellings) < 4:
            misspellings.append(word + "e")

        if ask_correct:
            text = "Which word is spelled correctly?"
            correct = word
            distractors = misspellings
        else:
            text = "Which word is spelled INCORRECTLY?"
            correct = misspellings[0]
            distractors = [word] + misspellings[1:4]
            while len(distractors) < 4:
                distractors.append(_misspell(word))
        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


PUNCTUATION_TEMPLATES = [
    ("the dog ran across the field and barked loudly", "The dog ran across the field and barked loudly."),
    ("sarah picked up her bag and left for school", "Sarah picked up her bag and left for school."),
    ("can you believe it started raining again", "Can you believe it started raining again?"),
    ("what a wonderful surprise this is", "What a wonderful surprise this is!"),
    ("the childrens toys were scattered across the floor", "The children's toys were scattered across the floor."),
    ("james said i will be there at six oclock", "James said, \"I will be there at six o'clock.\""),
    ("we visited london paris and rome last summer", "We visited London, Paris, and Rome last summer."),
    ("the cat sat quietly it did not move at all", "The cat sat quietly; it did not move at all."),
]


def _gen_punctuation(index: int) -> tuple:
    blocks, answers = [], []
    templates = random.sample(PUNCTUATION_TEMPLATES, min(10, len(PUNCTUATION_TEMPLATES)))
    while len(templates) < 10:
        templates.append(random.choice(PUNCTUATION_TEMPLATES))

    for i, (raw, correct) in enumerate(templates, start=1):
        wrong_versions = set()
        # missing final punctuation
        wrong_versions.add(correct.rstrip(".!?;\"") if correct[-1] in ".!?" else correct + ".")
        # no capital at the start
        wrong_versions.add(correct[0].lower() + correct[1:])
        # all lower case, no punctuation at all (the raw form)
        wrong_versions.add(raw)
        # double punctuation error
        if correct[-1] in ".!?":
            wrong_versions.add(correct[:-1] + correct[-1] * 2)
        wrong_versions.discard(correct)
        wrong_versions = list(wrong_versions)[:4]
        while len(wrong_versions) < 4:
            wrong_versions.append(raw + "..")

        text = "Which sentence is correctly punctuated and capitalised?"
        block, letter = _format_mcq(i, text, correct, wrong_versions[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


CLOZE_TEMPLATES = [
    ("The explorer felt {} when she finally reached the summit after months of preparation.", "elated", ["furious", "indifferent", "embarrassed", "confused"]),
    ("Despite the {} weather, the match went ahead as planned.", "dreadful", ["pleasant", "mild", "sunny", "calm"]),
    ("The old bridge looked far too {} to hold the weight of a lorry.", "fragile", ["sturdy", "modern", "colourful", "narrow"]),
    ("Everyone was {} by how quickly the young pianist learned the piece.", "astonished", ["bored", "annoyed", "unsurprised", "confused"]),
    ("The detective examined every clue with {} attention to detail.", "meticulous", ["careless", "hurried", "casual", "brief"]),
    ("Although the twins looked alike, their personalities were completely {}.", "different", ["identical", "similar", "matching", "alike"]),
    ("The manager praised the team for their {} effort throughout the difficult project.", "tireless", ["lazy", "half-hearted", "occasional", "reluctant"]),
    ("It was such a {} day that we decided to stay inside and read.", "gloomy", ["glorious", "bright", "warm", "cloudless"]),
]


def _gen_cloze(index: int) -> tuple:
    blocks, answers = [], []
    templates = random.sample(CLOZE_TEMPLATES, min(10, len(CLOZE_TEMPLATES)))
    while len(templates) < 10:
        templates.append(random.choice(CLOZE_TEMPLATES))

    for i, (sentence, correct, wrong_options) in enumerate(templates, start=1):
        text = f"Choose the best word to complete the sentence:\n   \"{sentence.format('_____')}\""
        block, letter = _format_mcq(i, text, correct, wrong_options[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _gen_synonyms_antonyms(index: int) -> tuple:
    blocks, answers = [], []
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
        else:
            text = f"Which word means most nearly the OPPOSITE of '{target_word}'?"

        block, letter = _format_mcq(i, text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


GRAMMAR_TEMPLATES = [
    ("The group of tourists {} arriving at the museum every hour.", "is", ["are", "were", "be", "being"]),
    ("Neither of the boys {} finished their homework.", "has", ["have", "were", "are", "having"]),
    ("By the time we arrived, the film {} already started.", "had", ["has", "was", "did", "have"]),
    ("She is the girl {} won the spelling competition.", "who", ["which", "whom", "whose", "what"]),
    ("The books, along with the box, {} on the top shelf.", "are", ["is", "was", "be", "being"]),
    ("If I {} known about the storm, I would have stayed home.", "had", ["have", "did", "was", "having"]),
    ("Each of the students {} given their own locker.", "was", ["were", "are", "be", "being"]),
    ("This is the best film {} I have ever seen.", "that", ["who", "whose", "when", "whom"]),
]


def _gen_grammar(index: int) -> tuple:
    blocks, answers = [], []
    templates = random.sample(GRAMMAR_TEMPLATES, min(10, len(GRAMMAR_TEMPLATES)))
    while len(templates) < 10:
        templates.append(random.choice(GRAMMAR_TEMPLATES))

    for i, (sentence, correct, wrong_options) in enumerate(templates, start=1):
        text = f"Choose the correct word to complete the sentence:\n   \"{sentence.format('_____')}\""
        block, letter = _format_mcq(i, text, correct, wrong_options[:4])
        blocks.append(block)
        answers.append(letter)
    return "\n\n".join(blocks), answers


def _build_passage():
    """Build one short, entirely original comprehension passage plus a set
    of (question, correct_answer, distractors) tuples with guaranteed
    correct answers, since the facts are generated alongside the text."""
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
        (f"Where did the {animal} live?", habitat, random.sample([h for h in COMPREHENSION_HABITATS if h != habitat], 4)),
        (f"What did the {animal} do every {day_period}, before {activity2}?", activity1, random.sample([a for a in COMPREHENSION_ACTIVITY1 if a != activity1], 4)),
        ("What disturbed the animal's routine?", event, random.sample([e for e in COMPREHENSION_EVENTS if e != event], 4)),
        ("How did the animal respond?", response, random.sample([r for r in COMPREHENSION_RESPONSES if r != response], 4)),
        ("How did the animal feel once things had settled?", emotion, random.sample([e for e in COMPREHENSION_EMOTIONS if e != emotion], 4)),
    ]
    return passage, questions


def _gen_comprehension(index: int) -> tuple:
    passage, questions = _build_passage()
    blocks = [f"Read the passage, then answer the questions below.\n\n{passage}\n"]
    answers = []
    for i, (q_text, correct, distractors) in enumerate(questions, start=1):
        block, letter = _format_mcq(i, q_text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)

    # Two passages per worksheet to reach a full 10-question set
    passage2, questions2 = _build_passage()
    blocks.append(f"\nRead the second passage, then answer the questions below.\n\n{passage2}\n")
    for j, (q_text, correct, distractors) in enumerate(questions2, start=len(questions) + 1):
        block, letter = _format_mcq(j, q_text, correct, distractors[:4])
        blocks.append(block)
        answers.append(letter)

    return "\n\n".join(blocks), answers


TOPIC_GENERATORS = {
    "Spelling": _gen_spelling,
    "Capital Letters and Punctuation": _gen_punctuation,
    "Vocabulary: Word Choice (Cloze)": _gen_cloze,
    "Vocabulary: Synonyms and Antonyms": _gen_synonyms_antonyms,
    "Grammar": _gen_grammar,
    "Reading Comprehension": _gen_comprehension,
}


def generate_11plus_english(topic: str, index: int) -> tuple:
    """Generate one 11+ English worksheet (MCQ) for a given topic."""
    generator = TOPIC_GENERATORS.get(topic)
    if generator is None:
        raise ValueError(f"Unknown 11+ English topic: {topic}")
    body, correct_answers = generator(index)
    header = (
        f"11+ English Practice (GL Assessment style) - {topic} (Set {index})\n"
        f"Answer each question by choosing the correct option A-E.\n\n"
    )
    return header + body, correct_answers


# ---------------------------------------------------------------------------
# Batch generation / RAG store integration (mirrors generate_11plus_math_homework.py)
# ---------------------------------------------------------------------------
def _weighted_topic_sequence(count: int) -> list:
    """Build an ordered topic list of length `count`, respecting the weights
    in ELEVEN_PLUS_ENGLISH_TOPICS so the mix matches GL's published English
    question breakdown (Spelling/Punctuation/Cloze heaviest, Grammar lightest)."""
    topics, weights = zip(*ELEVEN_PLUS_ENGLISH_TOPICS)
    return random.choices(topics, weights=weights, k=count)


def check_11plus_english_exists() -> bool:
    """检查是否已有 11+ 英语练习"""
    store = get_elevenplus_rag_store()
    results = store.search(query="english", k=1, filters={"subject": "English"})
    return len(results) > 0


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
    """生成指定数量的 11+ 英语练习，主题按权重分布 (Spelling/标点/词汇填空 权重最高)"""
    topic_sequence = _weighted_topic_sequence(count)
    batch_data = []

    for i, topic in enumerate(topic_sequence, start=1):
        content, correct_answers = generate_11plus_english(topic, i)

        metadata = {
            "year_group": YEAR_GROUP,
            "subject": "English",
            "homework_minutes": HOMEWORK_MINUTES,
            "key_stage": KEY_STAGE,
            "topic": topic,
            "exam_style": EXAM_STYLE,
            "question_format": "multiple_choice_5_options",
            "student_id": None,
            "correct_answers": ", ".join(correct_answers),
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
    print("检查 11+ English 练习是否存在...\n")

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