#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
检查各年级English作业是否存在，缺失则生成 100 份作业并添加到 RAG 存储
支持 Year 1-6 所有年级
"""
import sys
import os
import random

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from homework_rag import get_homework_rag_store


# 各年级英语主题（英国小学课程）
ENGLISH_TOPICS_BY_YEAR = {
    1: [
        "Phonics and Letter Sounds",
        "Sight Words",
        "Simple Sentence Writing",
        "Reading Comprehension (Simple)",
        "Capital Letters and Full Stops",
        "Rhyming Words",
        "Story Sequencing",
        "Describing Pictures",
    ],
    2: [
        "Spelling Patterns",
        "Punctuation (Full Stops, Capital Letters, Question Marks)",
        "Sentence Structure",
        "Reading Comprehension (Short Texts)",
        "Creative Writing (Simple Stories)",
        "Word Classes (Nouns, Verbs, Adjectives)",
        "Prefixes and Suffixes",
        "Writing Instructions",
    ],
    3: [
        "Grammar (Tenses)",
        "Paragraph Writing",
        "Reading Comprehension",
        "Spelling Rules",
        "Creative Writing",
        "Punctuation (Commas, Speech Marks)",
        "Word Classes (Adverbs, Prepositions)",
        "Editing and Proofreading",
    ],
    4: [
        "Advanced Grammar",
        "Formal and Informal Writing",
        "Reading Inference",
        "Creative Writing (Descriptions)",
        "Report Writing",
        "Punctuation (Colons, Semi-colons)",
        "Figurative Language",
        "Sentence Variety",
    ],
    5: [
        "Complex Sentences",
        "Persuasive Writing",
        "Reading Analysis",
        "Creative Writing (Narratives)",
        "Newspaper Reports",
        "Grammar (Modal Verbs, Passive Voice)",
        "Vocabulary Development",
        "Essay Structure",
    ],
    6: [
        "Advanced Writing Techniques",
        "Analytical Writing",
        "Reading Comprehension (Complex Texts)",
        "Creative Writing (Advanced)",
        "Debate and Argument",
        "SATs Writing Preparation",
        "Literary Devices",
        "Editing for Impact",
    ],
}


def generate_english_homework(year_group: int, topic: str, index: int) -> str:
    """根据年级、主题生成英语作业"""

    if year_group == 1:
        return _generate_year1_homework(topic, index)
    elif year_group == 2:
        return _generate_year2_homework(topic, index)
    elif year_group == 3:
        return _generate_year3_homework(topic, index)
    elif year_group == 4:
        return _generate_year4_homework(topic, index)
    elif year_group == 5:
        return _generate_year5_homework(topic, index)
    elif year_group == 6:
        return _generate_year6_homework(topic, index)


def _generate_year1_homework(topic: str, index: int) -> str:
    """Year 1 英语作业（5-6 岁）"""
    if topic == "Phonics and Letter Sounds":
        words = ["cat", "dog", "fish", "bird", "sun", "moon", "star", "tree", "book", "pen"]
        questions = [f"{i+1}. What sound does '{w}' start with?" for i, w in enumerate(words)]
    elif topic == "Sight Words":
        sight_words = ["the", "and", "is", "it", "to", "in", "on", "was", "for", "are"]
        questions = [f"{i+1}. Read the word: '{w}'. Write a sentence using it." for i, w in enumerate(sight_words)]
    elif topic == "Simple Sentence Writing":
        prompts = [
            "a cat",
            "a big dog",
            "the red ball",
            "a happy child",
            "the blue sky",
            "a small fish",
            "the green tree",
            "a fast car",
            "the sun",
            "a yellow flower",
        ]
        questions = [f"{i+1}. Write a sentence about {p}." for i, p in enumerate(prompts)]
    elif topic == "Reading Comprehension (Simple)":
        questions = [
            "Read: 'The cat is big. It sits on the mat.'",
            "1. What animal is in the story?",
            "2. Where does it sit?",
            "3. Is the cat small?",
            "4. Draw the cat.",
            "5. What colour is the cat?",
            "6. Does the cat run?",
            "7. Where is the mat?",
            "8. Is the cat happy or sad?",
            "9. Write one word about the cat.",
            "10. Do you like cats?",
        ]
    elif topic == "Capital Letters and Full Stops":
        sentences = [
            "the dog ran fast",
            "i like to play",
            "she has a red bag",
            "we went to the park",
            "he is my friend",
            "the sun is hot",
            "they are happy",
            "i can swim",
            "the bird can fly",
            "my mum is kind",
        ]
        questions = [f"{i+1}. Add capital letters and full stops: '{s}'" for i, s in enumerate(sentences)]
    elif topic == "Rhyming Words":
        words = ["cat", "dog", "hat", "ball", "tree", "book", "star", "fish", "moon", "pen"]
        questions = [f"{i+1}. Write a word that rhymes with '{w}'" for i, w in enumerate(words)]
    elif topic == "Story Sequencing":
        questions = [
            "Put the story in order:",
            "1. The boy goes to school.",
            "2. The boy wakes up.",
            "3. The boy eats breakfast.",
            "4. The boy plays with friends.",
            "5. The boy goes to bed.",
            "",
            "Write the correct order: __, __, __, __, __",
            "",
            "Now write the story in 3 sentences.",
            "",
            "Draw a picture of the boy at school.",
            "",
            "What happens next?",
        ]
    elif topic == "Describing Pictures":
        questions = [
            "Look at a picture of a park.",
            "1. What can you see?",
            "2. How many people are there?",
            "3. What colour is the sky?",
            "4. Are there trees?",
            "5. Is there a dog?",
            "6. What are the children doing?",
            "7. Is it sunny or cloudy?",
            "8. Write 2 sentences about the park.",
            "9. Would you like to go there?",
            "10. Draw your favourite part.",
        ]
    else:
        questions = [f"{i+1}. Year 1 English practice question {i+1}" for i in range(10)]

    return f"English Homework - Year 1 - {topic} (Set {index})\n\n" + "\n".join(questions)


def _generate_year2_homework(topic: str, index: int) -> str:
    """Year 2 英语作业（6-7 岁）"""
    if topic == "Spelling Patterns":
        patterns = [
            ("ight", ["light", "night", "right", "sight", "might"]),
            ("ough", ["tough", "cough", "rough", "dough", "bough"]),
            ("tion", ["station", "action", "motion", "option", "nation"]),
            ("sion", ["vision", "mission", "passion", "tension", "fusion"]),
            ("ture", ["future", "nature", "picture", "capture", "creature"]),
        ]
        pattern, examples = random.choice(patterns)
        questions = [
            f"Learn words ending in '{pattern}': {', '.join(examples[:5])}",
            f"1. Write 3 words ending in '{pattern}'",
            f"2. Use 'light' in a sentence",
            f"3. What sound does '{pattern}' make?",
            "4. Find 2 more words with this pattern",
            "5. Write a sentence with two pattern words",
            "6. Circle the pattern in: station, action, future",
            "7. Which is correct: lite or light?",
            "8. Write the pattern for 'picture'",
            "9. Read aloud the pattern words",
            "10. Test: spell 'station'",
        ]
    elif topic == "Punctuation (Full Stops, Capital Letters, Question Marks)":
        sentences = [
            "where are you going",
            "i live in london",
            "do you like cats",
            "the dog is very big",
            "what time is it",
            "she has three brothers",
            "can i have some water",
            "my favourite colour is blue",
            "how old are you",
            "the cat sat on the mat",
        ]
        questions = [f"{i+1}. Add correct punctuation: '{s}'" for i, s in enumerate(sentences)]
    elif topic == "Sentence Structure":
        questions = [
            "1. Write a sentence with a noun and a verb",
            "2. Write a sentence with an adjective",
            "3. Make this better: 'The dog ran.' (add 2 adjectives)",
            "4. Join: 'I like apples. I like oranges.' (use 'and')",
            "5. Write a question",
            "6. Write an exclamation",
            "7. Write a sentence with 'because'",
            "8. Make this longer: 'It rained.'",
            "9. Write a sentence with 'but'",
            "10. Write about your favourite toy",
        ]
    elif topic == "Reading Comprehension (Short Texts)":
        questions = [
            "Read: 'Tom has a red bike. He rides it every day. His friend Sam has a blue bike. They race in the park.'",
            "1. What colour is Tom's bike?",
            "2. When does Tom ride his bike?",
            "3. What colour is Sam's bike?",
            "4. Where do they race?",
            "5. Do they have bikes?",
            "6. Who has a red bike?",
            "7. Is Tom's bike blue?",
            "8. Do they race at school?",
            "9. Write one sentence about the story",
            "10. Draw the bikes",
        ]
    elif topic == "Creative Writing (Simple Stories)":
        questions = [
            "Write a short story (5-8 sentences) about:",
            "",
            "Title: 'The Magic Key'",
            "",
            "Questions to help:",
            "1. Who finds the key?",
            "2. What does the key look like?",
            "3. What does the key open?",
            "4. What happens next?",
            "5. How does the story end?",
            "",
            "Remember to use capital letters and full stops.",
            "",
            "Draw a picture of the magic key.",
        ]
    elif topic == "Word Classes (Nouns, Verbs, Adjectives)":
        questions = [
            "1. Circle the nouns: dog, run, happy, table, jump, cat, big, book",
            "2. Circle the verbs: sing, tall, dance, red, write, small, read, green",
            "3. Circle the adjectives: fast, slow, book, pen, happy, sad, run, jump",
            "4. Write 3 nouns",
            "5. Write 3 verbs",
            "6. Write 3 adjectives",
            "7. Use a noun and a verb in a sentence",
            "8. Use an adjective and a noun in a sentence",
            "9. Is 'beautiful' a noun, verb, or adjective?",
            "10. Is 'swim' a noun, verb, or adjective?",
        ]
    elif topic == "Prefixes and Suffixes":
        questions = [
            "1. Add 'un-' to 'happy' = ?",
            "2. Add 'un-' to 'kind' = ?",
            "3. Add '-ful' to 'help' = ?",
            "4. Add '-ful' to 'care' = ?",
            "5. Add '-less' to 'hope' = ?",
            "6. Add '-less' to 'fear' = ?",
            "7. What does 'un-' mean?",
            "8. What does '-ful' mean?",
            "9. Write 2 words with 'un-'",
            "10. Write 2 words with '-ful'",
        ]
    elif topic == "Writing Instructions":
        questions = [
            "Write instructions for making a sandwich:",
            "",
            "1. First, ...",
            "2. Next, ...",
            "3. Then, ...",
            "4. After that, ...",
            "5. Finally, ...",
            "",
            "Use imperative verbs (get, put, spread, cut)",
            "Use time words (first, next, then, finally)",
            "Write 5 clear steps",
        ]
    else:
        questions = [f"{i+1}. Year 2 English practice question {i+1}" for i in range(10)]

    return f"English Homework - Year 2 - {topic} (Set {index})\n\n" + "\n".join(questions)


def _generate_year3_homework(topic: str, index: int) -> str:
    """Year 3 英语作业（7-8 岁）"""
    if topic == "Grammar (Tenses)":
        questions = [
            "1. Change to past tense: 'I walk to school' -> ?",
            "2. Change to past tense: 'She eats an apple' -> ?",
            "3. Change to future tense: 'They play football' -> ?",
            "4. Change to past tense: 'He reads a book' -> ?",
            "5. Change to present tense: 'We went to the park' -> ?",
            "6. Write 3 sentences in past tense",
            "7. Write 3 sentences in future tense",
            "8. Identify tense: 'She is running' (past, present, or future?)",
            "9. Identify tense: 'They will sing' (past, present, or future?)",
            "10. Write a sentence in each tense",
        ]
    elif topic == "Paragraph Writing":
        questions = [
            "Write a paragraph about 'My Favourite Animal':",
            "",
            "Include:",
            "1. Topic sentence introducing the animal",
            "2. What it looks like",
            "3. Where it lives",
            "4. What it eats",
            "5. Why you like it",
            "6. Closing sentence",
            "",
            "Use at least 6 sentences.",
            "Use adjectives to describe it.",
            "Check your spelling and punctuation.",
        ]
    elif topic == "Reading Comprehension":
        questions = [
            "Read: 'The rainforest is home to many animals. It rains almost every day. The trees are very tall. Monkeys swing from branch to branch. Colourful birds fly through the trees. The forest floor is dark and wet.'",
            "1. Where do many animals live?",
            "2. How often does it rain?",
            "3. Are the trees short or tall?",
            "4. What do monkeys swing on?",
            "5. What flies through the trees?",
            "6. What is the forest floor like?",
            "7. Name two animals mentioned",
            "8. Why are rainforests important?",
            "9. Would you like to visit? Why?",
            "10. Find a word meaning 'almost the same as' 'house'",
        ]
    elif topic == "Spelling Rules":
        questions = [
            "1. Add '-ing' to 'run' (double the consonant?)",
            "2. Add '-ed' to 'stop' (double the consonant?)",
            "3. Add '-er' to 'big' (double the consonant?)",
            "4. Change 'y' to 'i' in 'happy' + '-er' = ?",
            "5. Change 'y' to 'i' in 'carry' + '-ed' = ?",
            "6. Spell: be-cause or becuase?",
            "7. Spell: fri-end or freind?",
            "8. Spell: peo-ple or peopl?",
            "9. Write the rule for doubling consonants",
            "10. Write the rule for changing 'y' to 'i'",
        ]
    elif topic == "Creative Writing":
        questions = [
            "Write a story (8-12 sentences) about:",
            "",
            "Title: 'The Lost Puppy'",
            "",
            "Include:",
            "1. Where does the puppy get lost?",
            "2. Who finds the puppy?",
            "3. What does the puppy look like?",
            "4. How do they help the puppy?",
            "5. How does the story end?",
            "",
            "Use:",
            "- Adjectives to describe",
            "- Time words (first, then, finally)",
            "- Dialogue (speech marks)",
            "- Varied sentence types",
        ]
    elif topic == "Punctuation (Commas, Speech Marks)":
        questions = [
            "1. Add speech marks: Hello, said Tom.",
            "2. Add speech marks: I love reading, said Mary.",
            "3. Add commas in a list: I bought apples bananas oranges grapes",
            "4. Add speech marks and commas: Watch out shouted Dad",
            "5. Add speech marks: Can I come too asked Sam",
            "6. Write a sentence with a list (use commas)",
            "7. Write a sentence with dialogue (use speech marks)",
            "8. Correct: she said i am tired",
            "9. Correct: we need pens pencils rulers and paper",
            "10. Write 2 sentences with both commas and speech marks",
        ]
    elif topic == "Word Classes (Adverbs, Prepositions)":
        questions = [
            "1. Circle the adverbs: quickly, happy, slowly, big, carefully, tall",
            "2. Circle the prepositions: under, run, over, beside, jump, between",
            "3. Add an adverb: 'She ran ___'",
            "4. Add a preposition: 'The cat is ___ the table'",
            "5. Write 3 adverbs",
            "6. Write 3 prepositions",
            "7. What do adverbs describe?",
            "8. What do prepositions show?",
            "9. Use 'quickly' in a sentence",
            "10. Use 'beside' in a sentence",
        ]
    elif topic == "Editing and Proofreading":
        questions = [
            "Find and correct 5 errors in this text:",
            "",
            "'i went to the park yesterday it was a lovely day me and my friend played on the swing we see a small dog it was very cute we give it some water'",
            "",
            "1. Find capital letter errors",
            "2. Find full stop errors",
            "3. Find spelling/grammar errors",
            "4. Rewrite the text correctly",
            "5. Count how many errors you found",
            "",
            "Now edit your own writing from last week.",
            "",
            "Check: capitals, full stops, spelling, sense",
        ]
    else:
        questions = [f"{i+1}. Year 3 English practice question {i+1}" for i in range(10)]

    return f"English Homework - Year 3 - {topic} (Set {index})\n\n" + "\n".join(questions)


def _generate_year4_homework(topic: str, index: int) -> str:
    """Year 4 英语作业（8-9 岁）"""
    if topic == "Advanced Grammar":
        questions = [
            "1. Identify the verb tense: 'She will have finished by noon'",
            "2. Identify the verb tense: 'They had already left'",
            "3. Change to passive: 'The cat chased the mouse'",
            "4. Change to passive: 'The boy kicked the ball'",
            "5. Write a sentence in present perfect tense",
            "6. Write a sentence in past perfect tense",
            "7. What is a subordinate clause?",
            "8. Find the subordinate clause: 'I went home because it was raining'",
            "9. Write a sentence with a relative clause (who, which, that)",
            "10. Correct: 'Me and him went to the shop'",
        ]
    elif topic == "Formal and Informal Writing":
        questions = [
            "Rewrite these informal sentences in formal style:",
            "1. 'I wanna go to the park' -> ?",
            "2. 'The film was really good' -> ?",
            "3. 'She's got loads of friends' -> ?",
            "4. 'I don't think that's fair' -> ?",
            "5. 'The food was kinda cold' -> ?",
            "",
            "Now write:",
            "6. A formal letter asking for information",
            "7. An informal letter to a friend",
            "8. List 3 differences between formal and informal writing",
            "9. Which is formal: 'I am writing to enquire' or 'I'm writing to ask'?",
            "10. Write a formal email to your teacher",
        ]
    elif topic == "Reading Inference":
        questions = [
            "Read: 'Emma looked at her shoes. They had holes in them. She sighed and put them back in the box.'",
            "1. How does Emma feel?",
            "2. Why does she sigh?",
            "3. What can you infer about Emma's family?",
            "4. What season might it be?",
            "5. Why does she put them back?",
            "",
            "Read: 'The crowd cheered. John raised the trophy above his head. His teammates hugged him.'",
            "6. What just happened?",
            "7. How does John feel?",
            "8. What sport might they play?",
            "9. What happened just before this moment?",
            "10. What will happen next?",
        ]
    elif topic == "Creative Writing (Descriptions)":
        questions = [
            "Write a descriptive paragraph (10-15 sentences) about:",
            "",
            "Title: 'A Stormy Night'",
            "",
            "Include:",
            "1. What you can see (lightning, dark clouds, rain)",
            "2. What you can hear (thunder, wind, rain on windows)",
            "3. What you can feel (cold, scared, excited)",
            "4. Use similes (like, as)",
            "5. Use metaphors",
            "6. Use personification",
            "7. Use varied sentence lengths",
            "8. Create atmosphere",
            "",
            "Do not just list events. Focus on description.",
        ]
    elif topic == "Report Writing":
        questions = [
            "Write a report about 'Dolphins':",
            "",
            "Structure:",
            "1. Introduction (what are dolphins?)",
            "2. Habitat (where do they live?)",
            "3. Diet (what do they eat?)",
            "4. Behaviour (how do they act?)",
            "5. Interesting facts",
            "6. Conclusion",
            "",
            "Use:",
            "- Formal language",
            "- Present tense",
            "- Technical vocabulary",
            "- Subheadings",
            "- Facts, not opinions",
        ]
    elif topic == "Punctuation (Colons, Semi-colons)":
        questions = [
            "1. Add a colon to introduce a list: I need three things paper, pens, and rulers",
            "2. Add a semi-colon to join related sentences: It was raining. We stayed inside.",
            "3. Add a colon: The winner is Sarah",
            "4. Add a semi-colon: I love reading it is my favourite hobby",
            "5. When do you use a colon?",
            "6. When do you use a semi-colon?",
            "7. Write a sentence with a colon introducing a list",
            "8. Write a sentence with a semi-colon joining two clauses",
            "9. Correct: The colours are red blue green yellow",
            "10. Correct: She was tired she went to bed early",
        ]
    elif topic == "Figurative Language":
        questions = [
            "1. Identify the simile: 'She is as brave as a lion'",
            "2. Identify the metaphor: 'He is a shining star'",
            "3. Identify the personification: 'The wind howled through the trees'",
            "4. Write a simile using 'like'",
            "5. Write a simile using 'as'",
            "6. Write a metaphor about the sun",
            "7. Write a metaphor about the sea",
            "8. Write personification for 'the flowers'",
            "9. Write personification for 'the moon'",
            "10. Explain the difference between simile and metaphor",
        ]
    elif topic == "Sentence Variety":
        questions = [
            "Improve these sentences by varying structure:",
            "1. 'I went to the shop. I bought bread. I went home.'",
            "2. 'The dog was big. The dog was brown. The dog was friendly.'",
            "3. 'It rained. We stayed inside. We played games.'",
            "",
            "Now write:",
            "4. A sentence starting with an adverb",
            "5. A sentence starting with a preposition",
            "6. A sentence with a subordinate clause first",
            "7. A question",
            "8. An exclamation",
            "9. A sentence with dialogue",
            "10. A complex sentence with 'although'",
        ]
    else:
        questions = [f"{i+1}. Year 4 English practice question {i+1}" for i in range(10)]

    return f"English Homework - Year 4 - {topic} (Set {index})\n\n" + "\n".join(questions)


def _generate_year5_homework(topic: str, index: int) -> str:
    """Year 5 英语作业（9-10 岁）"""
    if topic == "Complex Sentences":
        questions = [
            "1. Join using 'although': It was cold. We went outside.",
            "2. Join using 'despite': It rained. The match continued.",
            "3. Join using 'whereas': Tom likes football. Sam likes rugby.",
            "4. Join using 'unless': You must hurry. You will be late.",
            "5. Write a sentence with a relative clause (who, which, that)",
            "6. Write a sentence with a conditional clause (if, when)",
            "7. Write a sentence with a subordinate clause of reason (because, since)",
            "8. Write a sentence with a participle clause",
            "9. Identify clauses: 'After the bell rang, the students ran outside'",
            "10. Write a paragraph using at least 5 different complex sentence types",
        ]
    elif topic == "Persuasive Writing":
        questions = [
            "Write a persuasive letter (12-15 sentences) arguing that:",
            "",
            "'School should start at 10am instead of 9am'",
            "",
            "Include:",
            "1. Clear introduction stating your position",
            "2. At least 3 strong arguments",
            "3. Evidence or examples for each argument",
            "4. Address a counter-argument",
            "5. Rhetorical questions",
            "6. Emotive language",
            "7. Formal tone",
            "8. Strong conclusion",
            "",
            "Remember: AIDA (Attention, Interest, Desire, Action)",
        ]
    elif topic == "Reading Analysis":
        questions = [
            "Read: 'The old house stood alone at the end of the lane. Its windows were broken, and the front door hung open. No one had lived there for years, or so the villagers said. But sometimes, on quiet nights, a faint light could be seen flickering in an upstairs window.'",
            "1. What atmosphere is created?",
            "2. How does the writer build tension?",
            "3. Find an example of descriptive language",
            "4. What is the effect of 'or so the villagers said'?",
            "5. What does the flickering light suggest?",
            "6. What genre might this be?",
            "7. How would you describe the setting?",
            "8. What might happen next?",
            "9. Find a word showing the house is abandoned",
            "10. How does the writer make the reader curious?",
        ]
    elif topic == "Creative Writing (Narratives)":
        questions = [
            "Write a story (15-20 sentences) starting with:",
            "",
            "'The door creaked open, revealing a room I had never seen before...'",
            "",
            "Include:",
            "1. Clear beginning, middle, and end",
            "2. Description of the room",
            "3. A problem or challenge",
            "4. How the problem is resolved",
            "5. Dialogue between characters",
            "6. Varied sentence structures",
            "7. Figurative language",
            "8. Show, don't tell",
            "9. A twist or surprise",
            "10. A satisfying ending",
        ]
    elif topic == "Newspaper Reports":
        questions = [
            "Write a newspaper report about:",
            "",
            "'Local pupils win national science competition'",
            "",
            "Structure:",
            "1. Headline (short, catchy)",
            "2. Introduction (who, what, where, when)",
            "3. Main body (details, quotes, background)",
            "4. Quotes from people involved",
            "5. Background information",
            "6. Conclusion (what happens next)",
            "",
            "Use:",
            "- Formal, objective tone",
            "- Third person",
            "- Past tense",
            "- Direct and reported speech",
            "- Short paragraphs",
        ]
    elif topic == "Grammar (Modal Verbs, Passive Voice)":
        questions = [
            "1. Identify the modal verb: 'She might come to the party'",
            "2. Identify the modal verb: 'You must finish your homework'",
            "3. Write a sentence with 'could' showing possibility",
            "4. Write a sentence with 'should' giving advice",
            "5. Write a sentence with 'would' showing condition",
            "6. Change to passive: 'The teacher marked the papers'",
            "7. Change to passive: 'The company will build a new school'",
            "8. Change to active: 'The cake was eaten by the children'",
            "9. When is passive voice appropriate?",
            "10. Rewrite in active voice: 'Mistakes were made'",
        ]
    elif topic == "Vocabulary Development":
        questions = [
            "Replace the underlined word with a more sophisticated alternative:",
            "1. The film was 'very good'",
            "2. She felt 'sad' when she heard the news",
            "3. The house was 'big'",
            "4. He ran 'quickly' to catch the bus",
            "5. The weather was 'nice'",
            "",
            "Now write:",
            "6. 5 synonyms for 'important'",
            "7. 5 synonyms for 'beautiful'",
            "8. 5 synonyms for 'angry'",
            "9. Use 3 new vocabulary words in sentences",
            "10. Explain the difference between 'happy' and 'elated'",
        ]
    elif topic == "Essay Structure":
        questions = [
            "Plan an essay on: 'Should school uniforms be compulsory?'",
            "",
            "Structure:",
            "1. Introduction (introduce topic, state your view)",
            "2. Paragraph 1: First argument for your view",
            "3. Paragraph 2: Second argument for your view",
            "4. Paragraph 3: Counter-argument and rebuttal",
            "5. Conclusion (summarise, restate view)",
            "",
            "Now write the essay (15-20 sentences).",
            "",
            "Include:",
            "- Formal language",
            "- Linking words (furthermore, however, therefore)",
            "- Evidence and examples",
            "- Clear topic sentences",
        ]
    else:
        questions = [f"{i+1}. Year 5 English practice question {i+1}" for i in range(10)]

    return f"English Homework - Year 5 - {topic} (Set {index})\n\n" + "\n".join(questions)


def _generate_year6_homework(topic: str, index: int) -> str:
    """Year 6 英语作业（10-11 岁）"""
    if topic == "Advanced Writing Techniques":
        questions = [
            "Write a descriptive passage (15-20 sentences) about:",
            "",
            "'A Busy Market'",
            "",
            "Include:",
            "1. Sensory details (sight, sound, smell, touch, taste)",
            "2. Figurative language (similes, metaphors, personification)",
            "3. Varied sentence structures (simple, compound, complex)",
            "4. Fronted adverbials",
            "5. Precise vocabulary",
            "6. Show, don't tell",
            "7. Atmosphere and mood",
            "8. Focus on description, not narrative",
            "",
            "Avoid cliches. Be original and specific.",
        ]
    elif topic == "Analytical Writing":
        questions = [
            "Analyse this poem excerpt:",
            "",
            "'The fog comes on little cat feet. It sits looking over harbour and city on silent haunches and then moves on.'",
            "",
            "Write an analysis (12-15 sentences) covering:",
            "1. What is the poem about?",
            "2. What metaphor is used?",
            "3. How does the metaphor work?",
            "4. What is the mood/atmosphere?",
            "5. How does the language create this mood?",
            "6. What is the effect of 'silent haunches'?",
            "7. How does the poem end?",
            "8. What is your interpretation?",
            "",
            "Use quotes from the poem. Use analytical language.",
        ]
    elif topic == "Reading Comprehension (Complex Texts)":
        questions = [
            "Read: 'History is not merely a record of events; it is the story of human experience, shaped by memory, interpretation, and perspective. What we choose to remember, and how we choose to remember it, reveals as much about ourselves as it does about the past.'",
            "1. What is the writer's main argument?",
            "2. What does 'not merely' suggest?",
            "3. What three things shape history?",
            "4. What does the writer say about memory?",
            "5. What is revealed by what we choose to remember?",
            "6. Find a word meaning 'point of view'",
            "7. Do you agree with the writer? Why?",
            "8. What is the difference between 'record' and 'story'?",
            "9. How might two people remember the same event differently?",
            "10. Summarise the passage in one sentence",
        ]
    elif topic == "Creative Writing (Advanced)":
        questions = [
            "Write a story (20-25 sentences) based on this prompt:",
            "",
            "'She opened the letter. The words inside would change everything.'",
            "",
            "Include:",
            "1. Build tension gradually",
            "2. Reveal information slowly",
            "3. Use flashback or foreshadowing",
            "4. Multiple characters with dialogue",
            "5. Clear character motivation",
            "6. A meaningful conflict",
            "7. A resolution that satisfies",
            "8. Sophisticated vocabulary and structure",
            "9. Varied paragraph lengths",
            "10. A memorable final sentence",
        ]
    elif topic == "Debate and Argument":
        questions = [
            "Prepare arguments for BOTH sides of this debate:",
            "",
            "'Social media does more harm than good'",
            "",
            "FOR the motion (3 arguments):",
            "1. Argument 1 + evidence",
            "2. Argument 2 + evidence",
            "3. Argument 3 + evidence",
            "",
            "AGAINST the motion (3 arguments):",
            "4. Argument 1 + evidence",
            "5. Argument 2 + evidence",
            "6. Argument 3 + evidence",
            "",
            "Now write a speech (10-12 sentences) supporting ONE side.",
            "Use persuasive techniques and formal language.",
        ]
    elif topic == "SATs Writing Preparation":
        questions = [
            "SPaG (Spelling, Punctuation and Grammar) Practice:",
            "",
            "1. Identify the sentence type: 'Although it was late, she continued reading.'",
            "2. Identify the sentence type: 'Stop!'",
            "3. What is a relative clause? Give an example.",
            "4. Add semi-colons where needed: 'It was dark we could see nothing we decided to wait'",
            "5. Correct the spelling: accomodation, neccessary, occassion, definately",
            "6. Write a sentence using a colon correctly",
            "7. Write a sentence using the passive voice",
            "8. Write a sentence with a modal verb",
            "9. What is the subjunctive mood? Give an example.",
            "10. Identify all word classes in: 'The quick brown fox jumps over the lazy dog'",
        ]
    elif topic == "Literary Devices":
        questions = [
            "1. Define and give an example of: alliteration",
            "2. Define and give an example of: onomatopoeia",
            "3. Define and give an example of: hyperbole",
            "4. Define and give an example of: irony",
            "5. Define and give an example of: foreshadowing",
            "6. Find alliteration in: 'Peter Piper picked a peck of pickled peppers'",
            "7. Write 2 lines using onomatopoeia",
            "8. Write a sentence using hyperbole about homework",
            "9. Explain irony in your own words",
            "10. Write a paragraph using at least 3 different literary devices",
        ]
    elif topic == "Editing for Impact":
        questions = [
            "Improve this paragraph by editing for impact:",
            "",
            "'The boy went to the shop. He bought some sweets. He ate them on the way home. He felt happy. It was a good day.'",
            "",
            "Tasks:",
            "1. Replace simple vocabulary with sophisticated alternatives",
            "2. Add descriptive details",
            "3. Vary sentence structures",
            "4. Add figurative language",
            "5. Show emotions instead of telling",
            "6. Combine short sentences",
            "7. Add sensory details",
            "8. Rewrite the improved paragraph",
            "9. Explain what changes you made and why",
            "10. Rate the original (1-10) and your version (1-10)",
        ]
    else:
        questions = [f"{i+1}. Year 6 English practice question {i+1}" for i in range(10)]

    return f"English Homework - Year 6 - {topic} (Set {index})\n\n" + "\n".join(questions)


# 各年级 Key Stage 和作业时间设置
YEAR_CONFIG = {
    1: {"key_stage": "KS1", "homework_minutes": "10-15"},
    2: {"key_stage": "KS1", "homework_minutes": "10-15"},
    3: {"key_stage": "KS2", "homework_minutes": "20-30"},
    4: {"key_stage": "KS2", "homework_minutes": "20-30"},
    5: {"key_stage": "KS2", "homework_minutes": "30"},
    6: {"key_stage": "KS2", "homework_minutes": "30"},
}


def check_year_english_exists(year_group: int) -> bool:
    """检查指定年级是否已有英语作业"""
    store = get_homework_rag_store()
    results = store.search(query="english", k=1, filters={"year_group": year_group, "subject": "English"})
    return len(results) > 0


def generate_year_homework(year_group: int, count: int = 100) -> list:
    """为指定年级生成指定数量的英语作业"""
    topics = ENGLISH_TOPICS_BY_YEAR.get(year_group, [])
    if not topics:
        print(f"警告：未找到 Year {year_group} 的英语主题")
        return []

    config = YEAR_CONFIG.get(year_group, {"key_stage": "KS2", "homework_minutes": "20-30"})
    batch_data = []

    for i in range(1, count + 1):
        topic = topics[(i - 1) % len(topics)]
        content = generate_english_homework(year_group, topic, i)

        doc_id = f"hw_english_y{year_group}_{i:03d}"
        metadata = {
            "year_group": year_group,
            "subject": "English",
            "homework_minutes": config["homework_minutes"],
            "key_stage": config["key_stage"],
            "topic": topic,
            "student_id": None,
        }

        batch_data.append({
            "content": content,
            "metadata": metadata,
            "doc_id": doc_id,
        })

        if i % 10 == 0:
            print(f"  已生成 {i}/{count} 份作业")

    return batch_data


def main():
    """主函数：检查各年级英语作业，缺失则生成"""
    print("检查各年级English作业是否存在...\n")

    store = get_homework_rag_store()
    years_to_generate = []

    for year in range(1, 7):
        exists = check_year_english_exists(year)
        status = "已有" if exists else "缺失"
        print(f"  Year {year}: {status}")
        if not exists:
            years_to_generate.append(year)

    if not years_to_generate:
        print("\n所有年级English作业已存在，无需生成。")
        return

    print(f"\n需要生成的年级: {', '.join(f'Year {y}' for y in years_to_generate)}")

    for year in years_to_generate:
        print(f"\n开始生成 Year {year} English作业...")
        batch_data = generate_year_homework(year, count=100)

        if batch_data:
            store.add_batch_homework(batch_data)
            print(f"成功添加 {len(batch_data)} 份 Year {year} English作业到 RAG 存储")

    # 显示统计信息
    stats = store.get_stats()
    print(f"\nRAG 存储统计:")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  按主题分布: {stats['by_subject']}")
    print(f"  按年级分布: {stats['by_year_group']}")


if __name__ == "__main__":
    main()
