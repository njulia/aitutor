#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
11+ English 52-Week Year-Round Plan Generator
============================================

Generates a comprehensive 52-Week Year-Round English study roadmap formulated for
Henrietta Barnett, Tiffin, CSSE, and St Olave's English entrance papers.

Saves the generated plan to:
  - 11_Plus_English_52_Week_Plan.json
  - 11_Plus_English_52_Week_Plan.md

Also registers them in the RAG vector store for student queries.
"""

import sys
import os
import json
import math
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from src.elevenplus_rag import get_elevenplus_rag_store
except ImportError:
    get_elevenplus_rag_store = None

# Define the 52-Week English Curriculum
CURRICULUM = [
  {
    "termId": 1,
    "termName": "Term 1: Spelling, Word Patterns & Phonics Mastery",
    "focus": "Mastering core spelling rules, prefixes, suffixes, homophones, and double-consonant combinations.",
    "weeks": [
      {
        "weekNum": 1,
        "topic": "Spelling",
        "focus": "Vowel Patterns and Double Letters",
        "objectives": [
          "Identify and spell words with complex vowel digraphs (e.g., 'ae', 'oe', 'ie' vs 'ei').",
          "Master common double-letter traps in nouns and adjectives.",
          "Recognize visual patterns of correctly spelled words."
        ]
      },
      {
        "weekNum": 2,
        "topic": "Spelling",
        "focus": "Plural Rules and Exceptions",
        "objectives": [
          "Understand rules for adding -s, -es, -ies, and -ves to singular nouns.",
          "Learn irregular plural forms (e.g., criteria, phenomena, larvae).",
          "Apply correct spelling to plural possessives."
        ]
      },
      {
        "weekNum": 3,
        "topic": "Spelling",
        "focus": "Prefixes and Root Words",
        "objectives": [
          "Understand how common prefixes (un-, dis-, mis-, re-, pre-) modify root meanings.",
          "Avoid spelling mistakes when prefixes meet matching letters (e.g., dis- + satisfy = dissatisfy).",
          "Identify Greek and Latin root origins."
        ]
      },
      {
        "weekNum": 4,
        "topic": "Spelling",
        "focus": "Suffixes and Word Endings",
        "objectives": [
          "Learn when to drop 'e', double the consonant, or change 'y' to 'i' before adding suffixes.",
          "Differentiate between -able and -ible endings.",
          "Identify the grammatical role of suffix endings (-ly, -ment, -ness)."
        ]
      },
      {
        "weekNum": 5,
        "topic": "Spelling",
        "focus": "Silent Letters and Homophones",
        "objectives": [
          "Locate silent letters in standard vocabulary (e.g., knife, doubt, autumn, subtle).",
          "Differentiate between homophones (their/there/they're, practice/practise, advice/advise).",
          "Use context clues to select the correct homophone spelling."
        ]
      },
      {
        "weekNum": 6,
        "topic": "Spelling",
        "focus": "High-Frequency Spelling List (Part 1)",
        "objectives": [
          "Memorize spelling for first 15 words of the 11+ High-Frequency curriculum.",
          "Break down words into syllables for easier recall (e.g., ac-com-mo-date).",
          "Practice daily quick spelling drills."
        ]
      },
      {
        "weekNum": 7,
        "topic": "Spelling",
        "focus": "High-Frequency Spelling List (Part 2)",
        "objectives": [
          "Memorize spelling for second 15 words of the 11+ High-Frequency curriculum.",
          "Utilize visual mnemonics for tricky syllables (e.g., 'a rat' in 'separate').",
          "Test spelling accuracy under a 30-second time constraint."
        ]
      },
      {
        "weekNum": 8,
        "topic": "Spelling",
        "focus": "Words from Other Languages (Loan Words)",
        "objectives": [
          "Recognize and spell common French, Latin, and German loan words (e.g., bouquet, entrepreneur, curriculum).",
          "Understand phonetic differences in borrowed vocabulary.",
          "Master spelling patterns for foreign suffixes."
        ]
      },
      {
        "weekNum": 9,
        "topic": "Spelling",
        "focus": "Compound Words and Hyphenation",
        "objectives": [
          "Identify when to write compound words as one word, two words, or with a hyphen.",
          "Learn rules for hyphenating compound adjectives (e.g., well-known author).",
          "Master spelling for composite nouns."
        ]
      },
      {
        "weekNum": 10,
        "topic": "Spelling",
        "focus": "Difficult Double Consonant Pairings",
        "objectives": [
          "Practice spelling words with multiple double consonants (e.g., embarrassment, questionnaire).",
          "Analyze consonant structures under syllables.",
          "Recognize patterns of double 'r', 's', 'l', and 'n'."
        ]
      },
      {
        "weekNum": 11,
        "topic": "Spelling",
        "focus": "Confusion Words (e.g., Affect vs. Effect)",
        "objectives": [
          "Learn the distinct meanings and grammatical roles of easily confused pairs (affect/effect, stationary/stationery).",
          "Apply vocabulary guidelines to complete sentence gaps.",
          "Establish rules of thumb for daily differentiation."
        ]
      },
      {
        "weekNum": 12,
        "topic": "Spelling",
        "focus": "Spelling Under Time Pressure",
        "objectives": [
          "Complete rapid-fire spelling multiple-choice worksheets.",
          "Identify spelling errors in lengthy paragraphs of text.",
          "Review common traps in selective grammar school papers."
        ]
      },
      {
        "weekNum": 13,
        "topic": "Spelling",
        "focus": "Term 1 Spelling Mastery Review & Test",
        "objectives": [
          "Synthesize Term 1 spelling rules, plurals, prefixes, and silent letters.",
          "Complete a mixed 10-question GL-style spelling test.",
          "Eradicate repeat mistakes on active spelling sheets."
        ]
      }
    ]
  },
  {
    "termId": 2,
    "termName": "Term 2: Grammar Foundations & Sentence Structure",
    "focus": "Developing grammatical accuracy, mastering parts of speech, clause properties, and tenses.",
    "weeks": [
      {
        "weekNum": 14,
        "topic": "Grammar",
        "focus": "Parts of Speech: Nouns & Pronouns",
        "objectives": [
          "Differentiate between proper, common, concrete, abstract, and collective nouns.",
          "Master personal, possessive, relative, reflexive, and demonstrative pronouns.",
          "Avoid pronoun-noun agreement errors."
        ]
      },
      {
        "weekNum": 15,
        "topic": "Grammar",
        "focus": "Parts of Speech: Verbs & Tenses",
        "objectives": [
          "Identify action, linking, and helping (auxiliary) verbs.",
          "Conjugate verbs across simple past/present/future and perfect tenses.",
          "Master irregular verb forms (e.g., lie vs lay, rise vs raise)."
        ]
      },
      {
        "weekNum": 16,
        "topic": "Grammar",
        "focus": "Parts of Speech: Adjectives & Adverbs",
        "objectives": [
          "Use adjectives to modify nouns and adverbs to modify verbs, adjectives, or other adverbs.",
          "Understand comparative and superlative forms.",
          "Avoid confusing adjectives with adverbs (e.g., good vs well)."
        ]
      },
      {
        "weekNum": 17,
        "topic": "Grammar",
        "focus": "Parts of Speech: Prepositions & Conjunctions",
        "objectives": [
          "Identify prepositions of time, place, and direction.",
          "Use coordinating (FANBOYS) and subordinating conjunctions to connect clauses.",
          "Differentiate between prepositions and conjunctions."
        ]
      },
      {
        "weekNum": 18,
        "topic": "Grammar",
        "focus": "Subject-Verb Agreement (Singular vs. Plural)",
        "objectives": [
          "Match singular subjects with singular verbs and plural subjects with plural verbs.",
          "Resolve agreement with compound subjects joined by 'and', 'or', or 'nor'.",
          "Handle collective nouns and parenthetical insertions."
        ]
      },
      {
        "weekNum": 19,
        "topic": "Grammar",
        "focus": "Pronoun Agreement & Ambiguity",
        "objectives": [
          "Ensure pronouns agree in number and gender with their antecedents.",
          "Identify and correct vague or ambiguous pronoun references.",
          "Master subject vs object pronouns (e.g., he/him, who/whom)."
        ]
      },
      {
        "weekNum": 20,
        "topic": "Grammar",
        "focus": "Sentence Types (Simple, Compound, Complex)",
        "objectives": [
          "Recognize simple sentences containing a single independent clause.",
          "Form compound sentences using coordinating conjunctions or semicolons.",
          "Analyze complex sentences containing independent and subordinate clauses."
        ]
      },
      {
        "weekNum": 21,
        "topic": "Grammar",
        "focus": "Clauses and Phrases (Relative & Subordinate)",
        "objectives": [
          "Distinguish clearly between clauses (containing a subject-verb pair) and phrases.",
          "Identify relative clauses starting with relative pronouns (who, which, that).",
          "Deconstruct complex sentence syntax."
        ]
      },
      {
        "weekNum": 22,
        "topic": "Grammar",
        "focus": "Active vs. Passive Voice",
        "objectives": [
          "Identify whether a sentence is in active voice (subject performs action) or passive voice.",
          "Convert sentences from active to passive and vice versa.",
          "Understand the stylistic purpose of each voice in academic writing."
        ]
      },
      {
        "weekNum": 23,
        "topic": "Grammar",
        "focus": "Direct vs. Indirect Speech",
        "objectives": [
          "Identify direct quote speech and indirect reported speech.",
          "Convert speech styles, noting changes in verb tenses and pronouns.",
          "Master punctuation associated with dialogue."
        ]
      },
      {
        "weekNum": 24,
        "topic": "Grammar",
        "focus": "Common Grammatical Traps & Double Negatives",
        "objectives": [
          "Spot and eliminate double negatives in sentence structures.",
          "Correct dangling or misplaced modifiers.",
          "Master correct comparative structures (e.g., more faster -> faster)."
        ]
      },
      {
        "weekNum": 25,
        "topic": "Grammar",
        "focus": "Sentence Combining and Cohesion",
        "objectives": [
          "Combine multiple short sentences into a cohesive compound-complex sentence.",
          "Utilize transition words to establish flow and contrast.",
          "Master logical sequence structures."
        ]
      },
      {
        "weekNum": 26,
        "topic": "Grammar",
        "focus": "Term 2 Grammar Mastery Review & Test",
        "objectives": [
          "Synthesize nouns, verbs, tenses, subject-verb agreement, and clause types.",
          "Complete a mixed 10-question grammar paper.",
          "Analyze syntactic errors under exam time constraints."
        ]
      }
    ]
  },
  {
    "termId": 3,
    "termName": "Term 3: Capitalisation, Punctuation & Cloze Mastery",
    "focus": "Refining punctuation mechanics, complex mark usage, and contextual vocabulary selection.",
    "weeks": [
      {
        "weekNum": 27,
        "topic": "Capital Letters and Punctuation",
        "focus": "Capital Letters & Proper Nouns",
        "objectives": [
          "Capitalise sentences, direct speech, proper nouns, titles, and abbreviations.",
          "Avoid unnecessary capitalisation of common terms.",
          "Correct capitalization in complex headings."
        ]
      },
      {
        "weekNum": 28,
        "topic": "Capital Letters and Punctuation",
        "focus": "Full Stops, Question Marks & Exclamation Marks",
        "objectives": [
          "Apply terminal punctuation appropriately based on sentence intent.",
          "Avoid run-on sentences by separating complete thoughts.",
          "Master correct punctuation after abbreviations."
        ]
      },
      {
        "weekNum": 29,
        "topic": "Capital Letters and Punctuation",
        "focus": "Commas in Lists and Clauses",
        "objectives": [
          "Use commas to separate items in lists (including the serial/Oxford comma).",
          "Isolate introductory clauses, parenthetical remarks, and appositives.",
          "Avoid comma splices when joining independent clauses."
        ]
      },
      {
        "weekNum": 30,
        "topic": "Capital Letters and Punctuation",
        "focus": "Apostrophes for Contraction & Possession",
        "objectives": [
          "Apply apostrophes of contraction (e.g., can't, wouldn't, it's).",
          "Master singular and plural possessive rules (e.g., cat's milk vs cats' milk).",
          "Differentiate possessive pronouns (its, whose) from contractions."
        ]
      },
      {
        "weekNum": 31,
        "topic": "Capital Letters and Punctuation",
        "focus": "Speech Marks and Dialogue Punctuation",
        "objectives": [
          "Enclose direct spoken words inside double speech marks.",
          "Place punctuation marks (commas, full stops, question marks) inside speech marks.",
          "Start a new line for a new speaker."
        ]
      },
      {
        "weekNum": 32,
        "topic": "Capital Letters and Punctuation",
        "focus": "Colons and Semicolons",
        "objectives": [
          "Use colons to introduce lists, explanations, or direct quotes.",
          "Apply semicolons to join closely related independent clauses without conjunctions.",
          "Organize complex, comma-heavy lists using semicolons."
        ]
      },
      {
        "weekNum": 33,
        "topic": "Capital Letters and Punctuation",
        "focus": "Parenthesis: Brackets, Dashes & Commas",
        "objectives": [
          "Enclose extra, non-essential information inside brackets or parenthetical dashes.",
          "Understand how brackets, dashes, and commas create different stylistic emphasis.",
          "Maintain grammatical flow when parenthetical parts are removed."
        ]
      },
      {
        "weekNum": 34,
        "topic": "Vocabulary: Word Choice (Cloze)",
        "focus": "Cloze: Nouns and Verbs in Context",
        "objectives": [
          "Analyze surrounding words to determine the correct noun or verb category.",
          "Understand lexical collocations (words that frequently go together).",
          "Identify and discard contextually invalid options."
        ]
      },
      {
        "weekNum": 35,
        "topic": "Vocabulary: Word Choice (Cloze)",
        "focus": "Cloze: Adjectives and Adverbs in Context",
        "objectives": [
          "Evaluate descriptive passages to select the most appropriate tone modifiers.",
          "Recognize shades of meaning and positive vs negative contexts.",
          "Master high-tier descriptive adjectives."
        ]
      },
      {
        "weekNum": 36,
        "topic": "Vocabulary: Word Choice (Cloze)",
        "focus": "Cloze: Prepositions and Transition Words",
        "objectives": [
          "Fill sentence gaps with prepositions and transitional adverbs (therefore, however, although).",
          "Identify causal, contrast, and sequential relationships.",
          "Master sentence cohesive devices."
        ]
      },
      {
        "weekNum": 37,
        "topic": "Vocabulary: Synonyms and Antonyms",
        "focus": "Synonyms and Antonyms in Sentences",
        "objectives": [
          "Identify synonyms and antonyms for underlined words in written sentences.",
          "Evaluate vocabulary choices based on contextual nuance.",
          "Utilize process of elimination to discard unrelated choices."
        ]
      },
      {
        "weekNum": 38,
        "topic": "Vocabulary: Synonyms and Antonyms",
        "focus": "Context Clues and Tone Matching",
        "objectives": [
          "Deduce meanings of unfamiliar vocabulary using surrounding context clues.",
          "Match vocabulary tones (academic, informal, archaic) to the text.",
          "Master general 11+ vocabulary lists."
        ]
      },
      {
        "weekNum": 39,
        "topic": "Capital Letters and Punctuation",
        "focus": "Term 3 Punctuation & Cloze Mastery Review & Test",
        "objectives": [
          "Synthesize colons, semicolons, brackets, speech punctuation, and word cloze.",
          "Complete a mixed punctuation and vocabulary-cloze test.",
          "Analyze pacing: complete each item in under 40 seconds."
        ]
      }
    ]
  },
  {
    "termId": 4,
    "termName": "Term 4: Literary Comprehension, Inference & Exam Success",
    "focus": "Synthesizing all modules to excel in reading comprehension, inference, and exam time management.",
    "weeks": [
      {
        "weekNum": 40,
        "topic": "Reading Comprehension",
        "focus": "Reading Comprehension: Literal Fact Retrieval",
        "objectives": [
          "Locate specific facts directly stated in the text.",
          "Learn to scan for key terms, dates, and names.",
          "Avoid overthinking by sticking strictly to what is written."
        ]
      },
      {
        "weekNum": 41,
        "topic": "Reading Comprehension",
        "focus": "Reading Comprehension: Locating Evidence",
        "objectives": [
          "Identify the line numbers or paragraph details that prove an answer.",
          "Understand how to cross-reference multiple parts of a text.",
          "Track narrative sequence steps."
        ]
      },
      {
        "weekNum": 42,
        "topic": "Reading Comprehension",
        "focus": "Reading Comprehension: Word Meaning in Context",
        "objectives": [
          "Deduce what a word means based on how it is used in a specific sentence.",
          "Identify synonyms for literary terms inside comprehension texts.",
          "Differentiate between literal and figurative language (metaphor, simile)."
        ]
      },
      {
        "weekNum": 43,
        "topic": "Reading Comprehension",
        "focus": "Reading Comprehension: Simple Inference",
        "objectives": [
          "Read between the lines to deduce facts not explicitly stated.",
          "Identify character motivations and implied actions.",
          "Draw logical conclusions backed by subtle textual clues."
        ]
      },
      {
        "weekNum": 44,
        "topic": "Reading Comprehension",
        "focus": "Reading Comprehension: Character Feelings and Motives",
        "objectives": [
          "Interpret a character's emotional state from their dialogue, actions, and body language.",
          "Trace emotional changes throughout a story path.",
          "Contrast different characters' reactions."
        ]
      },
      {
        "weekNum": 45,
        "topic": "Reading Comprehension",
        "focus": "Reading Comprehension: Author's Tone and Intention",
        "objectives": [
          "Identify the author's purpose (to persuade, inform, entertain, describe).",
          "Deconstruct the tone of a passage (humorous, suspenseful, nostalgic).",
          "Analyze word choices that evoke specific feelings."
        ]
      },
      {
        "weekNum": 46,
        "topic": "Reading Comprehension",
        "focus": "Reading Comprehension: Text Layout & Formatting Clues",
        "objectives": [
          "Interpret non-fiction features (subheadings, bullet points, captions).",
          "Understand the purpose of italics, bolding, and quotation marks.",
          "Deconstruct informational texts."
        ]
      },
      {
        "weekNum": 47,
        "topic": "Reading Comprehension",
        "focus": "Exam Technique: Multiple-Choice Elimination (MCQ)",
        "objectives": [
          "Master the elimination strategy for 5-option English questions.",
          "Identify and discard common distractor traps (half-truths, extreme statements).",
          "Build absolute accuracy when choices feel similar."
        ]
      },
      {
        "weekNum": 48,
        "topic": "Reading Comprehension",
        "focus": "Exam Technique: Skimming and Scanning",
        "objectives": [
          "Practice high-speed skimming to get the 'gist' of a long passage in under 2 minutes.",
          "Scan targeted areas of text to locate specific information under strict timing.",
          "Minimize eye regression and stay focused."
        ]
      },
      {
        "weekNum": 49,
        "topic": "Reading Comprehension",
        "focus": "Exam Technique: Time Management",
        "objectives": [
          "Pace yourself during a standard 45-minute English paper.",
          "Learn when to skip a difficult question and come back to it.",
          "Double-check answers systematically in final minutes."
        ]
      },
      {
        "weekNum": 50,
        "topic": "Reading Comprehension",
        "focus": "Mixed English Drill - Speed and Accuracy",
        "objectives": [
          "Solve 10 mixed questions (Spelling, Grammar, Punctuation, Comprehension) under 8-minute time pressure.",
          "Maintain composure and logic under stress.",
          "Review step-by-step solutions instantly."
        ]
      },
      {
        "weekNum": 51,
        "topic": "Reading Comprehension",
        "focus": "Final Full-Syllabus English Mock Exam",
        "objectives": [
          "Complete a comprehensive, 20-question randomized mock English paper.",
          "Review comprehensive explanations for all sections.",
          "Identify final polish areas for selective school entrance."
        ]
      },
      {
        "weekNum": 52,
        "topic": "Reading Comprehension",
        "focus": "Ultimate Strategy, Anxiety Management & Prep",
        "objectives": [
          "Review elite exam guidelines and Coach Pip's checklist for selective schools.",
          "Establish a low-stress, confidence-building final warm-up routine.",
          "Visualize exam success with clarity and positive focus."
        ]
      }
    ]
  }
]

def get_questions_for_week(week_num: int) -> list:
    """Generate 3 homework questions for the specified week."""
    seed = week_num
    
    def rand_num(min_val, max_val, offset=0):
        # Deterministic pseudo-random sine hash
        x = math.sin(seed * 43758.5453 + offset) * 10000
        r = x - math.floor(x)
        return int(min_val + math.floor(r * (max_val - min_val + 1)))

    questions = []

    if week_num == 1:
        questions.append({
            "id": 1,
            "questionText": "Which of the following words is spelled correctly?",
            "options": ["neccessary", "necesary", "necessary", "neccesary", "necessery"],
            "correctLetter": "C",
            "correctValue": "necessary",
            "explanation": "The correct spelling is 'necessary'. A common mistake is doubling the 'c' or using a single 's'. Think of it as having 1 Collar (C) and 2 Sleeves (S) to dress properly.",
            "tip": "Use the mnemonic: 1 Collar, 2 Sleeves!"
        })
        questions.append({
            "id": 2,
            "questionText": "Which of the following words is spelled INCORRECTLY?",
            "options": ["separate", "embarrass", "definitely", "rhythm", "occassion"],
            "correctLetter": "E",
            "correctValue": "occassion",
            "explanation": "'occassion' is spelled incorrectly. The correct spelling is 'occasion' (double 'c', single 's').",
            "tip": "Remember: Two Cups of Coffee (CC) on one special occaSion!"
        })
        questions.append({
            "id": 3,
            "questionText": "Identify the correctly spelled word to complete: 'She was extremely ________ about the results.'",
            "options": ["conshious", "conscience", "conscious", "concious", "consciouss"],
            "correctLetter": "C",
            "correctValue": "conscious",
            "explanation": "The correct spelling is 'conscious' (meaning awake and aware). It has a 'sc' combination in the middle.",
            "tip": "Pronounce the 'sc' in your head to remember its spelling!"
        })
    elif week_num == 14:
        questions.append({
            "id": 1,
            "questionText": "Identify the word class of the capitalized word in: 'The boy looked at the OLD castle.'",
            "options": ["Noun", "Verb", "Adjective", "Adverb", "Pronoun"],
            "correctLetter": "C",
            "correctValue": "Adjective",
            "explanation": "The capitalized word 'OLD' describes the noun 'castle'. Words that describe nouns are adjectives.",
            "tip": "Always look at what the word is doing in the sentence: if it describes a noun, it's an adjective!"
        })
        questions.append({
            "id": 2,
            "questionText": "Which of the following pronouns is a relative pronoun?",
            "options": ["he", "who", "himself", "this", "mine"],
            "correctLetter": "B",
            "correctValue": "who",
            "explanation": "'who' is a relative pronoun used to connect clauses and refer back to a person.",
            "tip": "Relative pronouns connect a clause to a noun or pronoun (e.g., who, which, that)."
        })
        questions.append({
            "id": 3,
            "questionText": "Which of the following nouns is an abstract noun?",
            "options": ["table", "happiness", "water", "London", "team"],
            "correctLetter": "B",
            "correctValue": "happiness",
            "explanation": "'happiness' is an abstract noun because it represents a state, quality, or idea that cannot be touched or seen physically.",
            "tip": "If you can't touch, see, hear, smell, or taste it, it's an abstract noun!"
        })
    elif week_num == 27:
        questions.append({
            "id": 1,
            "questionText": "Which of the following is correctly capitalised?",
            "options": [
                "we visited the Eiffel tower in Paris.",
                "We visited the eiffel tower in paris.",
                "We visited the Eiffel Tower in Paris.",
                "We visited the Eiffel Tower in paris.",
                "we visited the eiffel tower in Paris."
            ],
            "correctLetter": "C",
            "correctValue": "We visited the Eiffel Tower in Paris.",
            "explanation": "Both 'Eiffel Tower' (a specific monument) and 'Paris' (a specific city) are proper nouns and must be capitalised. The sentence must also start with a capital 'We'.",
            "tip": "Names of specific landmarks, cities, and countries are proper nouns and must be capitalised!"
        })
        questions.append({
            "id": 2,
            "questionText": "Identify the correct punctuation mark needed to separate two closely related independent clauses without a conjunction: 'The sun was shining ____ the birds were singing.'",
            "options": ["Comma", "Semicolon", "Colon", "Dash", "Hyphen"],
            "correctLetter": "B",
            "correctValue": "Semicolon",
            "explanation": "A semicolon (';') is used to link two independent clauses that are closely related in thought, without using a conjunction.",
            "tip": "Use a semicolon to connect two complete sentences when they are closely linked in meaning."
        })
        questions.append({
            "id": 3,
            "questionText": "Which of the following is correctly punctuated for direct speech?",
            "options": [
                "\"I'm ready,\" said James.",
                "\"I'm ready\" said James.",
                "\"I'm ready\", said James.",
                "I'm ready said James.",
                "\"I'm ready.\" Said James."
            ],
            "correctLetter": "A",
            "correctValue": "\"I'm ready,\" said James.",
            "explanation": "In direct speech, a comma must separate the spoken words from the reporting verb, and it must go inside the closing speech marks. 'said' should not be capitalised.",
            "tip": "Commas and full stops go INSIDE closing speech marks!"
        })
    else:
        # Find week metadata from the CURRICULUM
        current_week = None
        for term in CURRICULUM:
            for week in term["weeks"]:
                if week["weekNum"] == week_num:
                    current_week = week
                    break
            if current_week:
                break
        
        focus = current_week["focus"] if current_week else "General English Practice"
        
        questions.append({
            "id": 1,
            "questionText": f"An 11+ test checks your understanding of [{focus}]. Select the best choice: Which word is most nearly the SAME in meaning as 'diligent'?",
            "options": ["lazy", "careful", "hard-working", "intelligent", "stubborn"],
            "correctLetter": "C",
            "correctValue": "hard-working",
            "explanation": "'diligent' means showing steady, earnest, and energetic effort in a task; therefore, 'hard-working' is the closest synonym.",
            "tip": "Diligent describes someone who puts in careful, consistent effort!"
        })
        questions.append({
            "id": 2,
            "questionText": f"To master [{focus}], identify the word that is spelled INCORRECTLY in the following selection:",
            "options": ["necessary", "parliament", "separate", "receive", "definately"],
            "correctLetter": "E",
            "correctValue": "definately",
            "explanation": "'definately' is incorrect. The correct spelling is 'definitely' (from the root 'finite', which has 'i's and no 'a').",
            "tip": "Remember there is a 'finite' inside 'definitely'!"
        })
        questions.append({
            "id": 3,
            "questionText": f"Regarding [{focus}], choose the correct verb form: 'Neither of the girls ________ completed the project.'",
            "options": ["has", "have", "were", "are", "having"],
            "correctLetter": "A",
            "correctValue": "has",
            "explanation": "The pronoun 'Neither' is singular and requires a singular verb. 'has' is singular, while 'have', 'were', and 'are' are plural.",
            "tip": "Pronouns like 'each', 'either', and 'neither' are always grammatically singular!"
        })

    return questions

def generate_markdown_plan() -> str:
    """Generate the full Markdown plan for 11+ English."""
    md = [
        "# Eleven Plus (11+) English Study Plan",
        "## The 52-Week Year-Round Curriculum & Homework Sets",
        "**Coach Pip's Selective Grammar School Entrance Training Core**",
        "*Prepared for the GL Assessment, CEM, and Super-Selective Stage Two Exams*",
        "",
        "---",
        "",
        "## STUDY PLAN OVERVIEW",
        "Preparing for highly competitive UK selective schools (like Henrietta Barnett, Tiffin, CSSE, and St Olave's) requires a systematic, spaced approach. This 52-week plan covers the complete 11+ English syllabus, divided into four strategic terms:",
        "1. **Term 1 (Weeks 1-13)**: Spelling, Word Patterns & Phonics Mastery",
        "2. **Term 2 (Weeks 14-26)**: Grammar Foundations & Sentence Structure",
        "3. **Term 3 (Weeks 27-39)**: Capitalisation, Punctuation & Cloze Mastery",
        "4. **Term 4 (Weeks 40-52)**: Literary Comprehension, Inference & Exam Success",
        "",
        "Each week contains core focus objectives and a **Homework Set of 3 Selective-School Style questions** with answer keys, worked explanations, and coaching advice.",
        "",
        "---",
        ""
    ]

    for term in CURRICULUM:
        md.append(f"# {term['termName']}")
        md.append(f"**Term Focus:** {term['focus']}\n")
        
        for week in term["weeks"]:
            md.append(f"## Week {week['weekNum']}: {week['focus']}")
            md.append(f"* **Syllabus Area:** {week['topic']}")
            md.append(f"* **Learning Objectives:**")
            for obj in week["objectives"]:
                md.append(f"  - {obj}")
            md.append("")
            
            md.append(f"### 📝 Homework Set {week['weekNum']}\n")
            questions = get_questions_for_week(week["weekNum"])
            for q in questions:
                md.append(f"#### Q{q['id']}. {q['questionText']}")
                md.append("**Options:**")
                for idx, opt in enumerate(q["options"]):
                    letter = ["A", "B", "C", "D", "E"][idx]
                    md.append(f"   {letter}) {opt}")
                md.append("")
                md.append(f"**Correct Answer:** Option **{q['correctLetter']}** ({q['correctValue']})\n")
                md.append(f"**Worked Step-by-Step Explanation:**\n{q['explanation']}\n")
                md.append(f"**Coach Pip's Elite School Tip:** *{q['tip']}*\n")
                md.append("---")
            md.append("")
            
    md.append("\n### 🎉 End of 52-Week Year-Round Curriculum")
    md.append("*Congratulations on working through this plan! Regular practice, reading widely, and careful analysis of punctuation are the keys to securing a high-accuracy selective school score.*")
    return "\n".join(md)

def main():
    print("==========================================================")
    print("      11+ English 52-Week Year-Round Plan Generator       ")
    print("==========================================================\n")

    # Format data for JSON output
    full_plan_data = []
    for term in CURRICULUM:
        term_data = {
            "termId": term["termId"],
            "termName": term["termName"],
            "focus": term["focus"],
            "weeks": []
        }
        for week in term["weeks"]:
            term_data["weeks"].append({
                "weekNum": week["weekNum"],
                "topic": week["topic"],
                "focus": week["focus"],
                "objectives": week["objectives"],
                "homeworkSet": get_questions_for_week(week["weekNum"])
            })
        full_plan_data.append(term_data)

    # Save to JSON
    json_path = "11_Plus_English_52_Week_Plan.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_plan_data, f, indent=2, ensure_ascii=False)
    print(f"[Success] Saved 52-Week Plan JSON to: {json_path}")

    # Save to Markdown
    md_path = "11_Plus_English_52_Week_Plan.md"
    markdown_content = generate_markdown_plan()
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    print(f"[Success] Saved 52-Week Plan Markdown to: {md_path}")

    # Register in RAG vector store
    if get_elevenplus_rag_store:
        try:
            print("\nRegistering 52-Week Year-Round sets with the RAG Store...")
            store = get_elevenplus_rag_store()
            
            # Format into batch homework objects for RAG ingestion
            batch_data = []
            for term in full_plan_data:
                for week in term["weeks"]:
                    # Create readable content string
                    content_str = (
                        f"11+ English 52-Week Plan - Term {term['termId']} - Week {week['weekNum']}\n"
                        f"Topic Focus: {week['focus']}\n"
                        f"Syllabus: {week['topic']}\n"
                        f"Objectives:\n" + "\n".join([f"- {o}" for o in week['objectives']]) + "\n\n"
                    )
                    
                    for idx, q in enumerate(week["homeworkSet"], 1):
                        content_str += (
                            f"Homework Question {idx}:\n"
                            f"{q['questionText']}\n"
                            f"Options: {', '.join(q['options'])}\n"
                            f"Correct Answer: {q['correctLetter']} ({q['correctValue']})\n"
                            f"Explanation: {q['explanation']}\n"
                            f"Coaching Strategy: {q['tip']}\n\n"
                        )
                    
                    metadata = {
                        "year_group": 6,
                        "subject": "English",
                        "key_stage": "11+",
                        "topic": week["topic"],
                        "week_num": week["weekNum"],
                        "term_id": term["termId"],
                        "exam_style": "GL & Selective School Style",
                        "created_at": datetime.now().isoformat()
                    }
                    
                    batch_data.append({
                        "content": content_str,
                        "metadata": metadata,
                        "doc_id": f"elevenplus_english_year_round_week_{week['weekNum']:02d}"
                    })
            
            store.add_batch_homework(batch_data)
            print("Successfully loaded 52 weekly plan entries into the RAG Store.")
        except Exception as e:
            print(f"RAG Integration skipped or failed: {e}")
    else:
        print("\nNote: RAG Store is not available in standalone execution. Local files generated successfully.")

if __name__ == "__main__":
    main()
