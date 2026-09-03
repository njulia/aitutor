"""Additional original questions and formats for the 11+ mock catalogue.

The questions in this module were written for Homework Magic.  The public
sources are format and curriculum references only; no source questions or
commercial practice-paper content is reproduced.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable


def _question(
    question_id: str,
    subject: str,
    topic: str,
    prompt: str,
    options: Iterable[tuple[str, str]],
    answer: str,
    explanation: str,
    *,
    context: str = "",
) -> Dict[str, Any]:
    """Build a question without depending on the main catalogue module."""
    option_rows = [{"label": label, "text": text} for label, text in options]
    labels = {row["label"] for row in option_rows}
    if answer not in labels:
        raise ValueError(f"{question_id} has an answer outside its options")
    if len(labels) != len(option_rows) or len(option_rows) < 2:
        raise ValueError(f"{question_id} has invalid options")
    return {
        "id": question_id,
        "subject": subject,
        "topic": topic,
        "prompt": prompt,
        "context": context,
        "options": option_rows,
        "answer": answer,
        "explanation": explanation,
    }


ADDITIONAL_PUBLIC_SOURCES: Dict[str, Dict[str, str]] = {
    "top100-alevel-2025": {
        "title": "Top School Guide: 2025 Top 100 A-Level Schools",
        "url": "https://www.topschoolguide.com/uk/league-tables/all-schools/top-100-schools-for-a-levels/",
    },
    "nlcs-11plus-2027": {
        "title": "North London Collegiate School: 11+ sample papers",
        "url": "https://www.nlcs.org.uk/admissions/joining-the-senior-school/",
    },
    "clsg-11plus-2027": {
        "title": "City of London School for Girls: 11+ familiarisation and sample papers",
        "url": "https://clsg.org.uk/admissions/faqs/",
    },
    "highgate-11plus-2027": {
        "title": "Highgate School: 11+ sample test papers",
        "url": "https://www.highgateschool.org.uk/senior-school/admissions-11/",
    },
    "kehs-11plus-2027": {
        "title": "King Edward VI High School for Girls: 11+ specimen material",
        "url": "https://kehs.org.uk/admissions/entrance-exams/",
    },
    "wimbledon-high-11plus-2027": {
        "title": "Wimbledon High School: 11+ assessment information",
        "url": "https://www.wimbledonhigh.gdst.net/admissions/senior-admissions/",
    },
    "putney-high-11plus-2027": {
        "title": "Putney High School: 11+ assessment information",
        "url": "https://www.putneyhigh.gdst.net/admissions/senior-admissions/",
    },
    "brighton-11plus-2027": {
        "title": "Brighton College: 11+ assessment information",
        "url": "https://www.brightoncollege.org.uk/file/101/1750083672/1750083672-2026-overseas-timeline.pdf",
    },
    "habs-11plus-2027": {
        "title": "Haberdashers' Schools: 11+ admissions policy",
        "url": "https://www.habsgirls.org.uk/wp-content/uploads/2024/06/Admissions-Policy-.pdf",
    },
    "kent-test-2027": {
        "title": "Kent County Council: prepare for the Kent Test",
        "url": (
            "https://www.kent.gov.uk/education-and-children/schools/"
            "school-places/kent-test/prepare-for-the-kent-test"
        ),
    },
    "bucks-transfer-2027": {
        "title": "Buckinghamshire Council: Secondary Transfer Testing process",
        "url": (
            "https://www.buckinghamshire.gov.uk/schools-libraries-and-parks/"
            "school-admissions-and-appeals/guides-and-policies/guide-to-grammar-"
            "schools-and-the-secondary-school-transfer-test-11-plus/secondary-"
            "transfer-testing-process/"
        ),
    },
    "sutton-set-2027": {
        "title": "Greenshaw High School: Selective Eligibility Test for 2027 entry",
        "url": "https://www.greenshaw.co.uk/content/?contentid=45&pid=34",
    },
    "west-midlands-2027": {
        "title": "West Midlands Grammar Schools: the entrance test",
        "url": "https://westmidlandsgrammarschools.co.uk/the-entrance-test",
    },
    "csse-2027": {
        "title": "Consortium of Selective Schools in Essex: 2027 examination",
        "url": "https://csse.org.uk/",
    },
    "essex-grammar-2027": {
        "title": "Essex County Council: grammar school places and 2027 entry",
        "url": "https://www.essex.gov.uk/schools-and-learning/schools/admissions/grammar-school-places",
    },
    "lrgs-2027": {
        "title": "Lancaster Royal Grammar School: 2027 entrance tests",
        "url": "https://www.lrgs.org.uk/join-the-school/admissions",
    },
    "bexley-selection-2027": {
        "title": "London Borough of Bexley: 2027 Selection Test format",
        "url": (
            "https://www.bexley.gov.uk/services/schools-and-education/"
            "selection-tests/about-test"
        ),
    },
    "wirral-assessment-2027": {
        "title": "Wirral Council: 2027 grammar-school assessment",
        "url": (
            "https://www.wirral.gov.uk/schools-and-learning/school-admissions/"
            "step-by-step/apply-secondary-school-place/assessment-grammar"
        ),
    },
    "gloucestershire-test-2027": {
        "title": "Gloucestershire: 2027 grammar-school admission test format",
        "url": "https://www.gloucestershire.gov.uk/media/oexblecu/denmar-1.pdf",
    },
    "slough-consortium-2027": {
        "title": "Slough Consortium: 2027 shared 11+ examination",
        "url": "https://www.herschel.slough.sch.uk/year-7-admissions-2027/",
    },
    "medway-test-2027": {
        "title": "Medway Council: Medway Test papers and timings",
        "url": (
            "https://www.medway.gov.uk/info/200137/schools_and_learning/"
            "1049/medway_test_11"
        ),
    },
    "wilsons-second-stage-2027": {
        "title": "Wilson's School: 2027 Second Stage Entrance Examination FAQs",
        "url": "https://www.wilsons.school/admissions-faqs/",
    },
    "tiffin-girls-2027": {
        "title": "The Tiffin Girls' School: Year 7 admissions for 2027 entry",
        "url": "https://www.tiffingirls.org/admissions/year-7/",
    },
    "st-olaves-2027": {
        "title": "St Olave's Grammar School: public admissions information",
        "url": "https://www.saintolaves.net/",
    },
    "st-olaves-public-sample": {
        "title": "Public archive of St Olave's school-issued Stage One sample format",
        "url": (
            "https://athenatuition.co.uk/wp-content/uploads/2019/06/"
            "St-Olaves-Grammar-School-11-Stage-1-Entrance-Test-Sample.pdf"
        ),
    },
    "henrietta-barnett-2027": {
        "title": "The Henrietta Barnett School: 2027 entrance-test information",
        "url": "https://www.hbschool.org.uk/admissions/",
    },
    "altrincham-girls-2027": {
        "title": "Altrincham Grammar School for Girls: 2027 entrance-test information",
        "url": "https://aggs.bright-futures.co.uk/admissions/september-2027-entry/",
    },
    "reading-fsce-2027": {
        "title": "Reading School: 2027 FSCE entrance-test familiarisation information",
        "url": "https://www.reading-school.co.uk/admissions/year-7-entry",
    },
    "cchs-fsce-2027": {
        "title": "Chelmsford County High School for Girls: 2027 FSCE entrance test",
        "url": (
            "https://www.cchs.co.uk/admissions/"
            "admission-to-year-7-september-2027/"
        ),
    },
    "newstead-wood-2027": {
        "title": "Newstead Wood School: Year 7 admissions and selection test",
        "url": "https://www.newsteadwood.co.uk/admissions/year-7-admissions/about-the-selection-test",
    },
    "gl-11plus-free-materials": {
        "title": "GL Assessment: free 11+ familiarisation materials",
        "url": "https://11plus.gl-assessment.co.uk/pages/free-materials",
    },
}


_GLASSHOUSE_PASSAGE = (
    "Before the village woke, Priya slipped into the community glasshouse. A loose "
    "roof pane rattled in the wind, and rows of seedlings bowed over dry trays. She "
    "had meant only to collect a trowel, yet dark clouds were banking above the hill. "
    "Priya filled the watering can and worked along every row. By the time Mr Okoro "
    "arrived, rain tapped the glass and the leaves had lifted. ‘You read the weather "
    "better than I did,’ he said. Priya smiled but kept coiling the hose."
)

_WOODLAND_PASSAGE = (
    "Leo had mapped every turn of the woodland trail, yet the fallen oak was not on "
    "his sketch. It lay across the path, its roots raised like a wall. The race marker "
    "pointed straight ahead, and behind him shoes struck the gravel. Leo could scramble "
    "over the trunk, but his teammate Hana had an injured wrist. He spotted a narrow "
    "deer track looping through the ferns. It would cost a minute, perhaps two. Leo "
    "called to Hana and turned onto the track. They emerged beyond the oak just as the "
    "checkpoint bell sounded."
)

_CAUSEWAY_PASSAGE = (
    "At low tide, Amara followed Grandad across the stone causeway to the old "
    "lighthouse. They had promised to repaint its faded door before the weekend "
    "visitors arrived. Halfway across, Amara noticed the shallow pools between the "
    "stones beginning to join. ‘The tide is early,’ she said. Grandad studied his "
    "watch, then the darkening sky. Without arguing, he placed the paint tin in her "
    "rucksack and turned back. They reached the harbour just as the final stones "
    "vanished beneath silver water. The door could wait; the tide would not."
)

_MUSEUM_PASSAGE = (
    "Elena volunteered at the town museum, cataloguing boxes from a theatre that had "
    "closed decades ago. In one box she found a printed programme covered with "
    "pencilled notes: names were crossed out, timings altered and arrows squeezed into "
    "the margins. She almost filed it with the other programmes, but the initials on "
    "the cover matched those of a celebrated director. Instead of rubbing away the "
    "marks, Elena photographed every page and called the curator. The notes had turned "
    "an ordinary souvenir into a rare record of a rehearsal."
)

_PLANETARIUM_PASSAGE = (
    "At the school planetarium, Sami was trusted to run the projector for the "
    "evening show. Minutes before the families entered, one constellation flickered "
    "and vanished. The manual said to restart the whole system, but that would erase "
    "the carefully timed sequence. Sami noticed a loose cable beneath the console. "
    "He switched off only that section, pressed the connector firmly into place and "
    "tested it. Orion returned, sharp and bright. When the doors opened, Sami stood "
    "quietly at the back while the audience gasped at the stars above them."
)

_ORCHARD_PASSAGE = (
    "The wind rose while Asha and Tom were checking the community orchard. A young "
    "pear tree leaned so far that its roots lifted at one side. Tom ran to fetch rope, "
    "but Asha chose a wide strip of old cloth instead. Together they eased the trunk "
    "upright, braced it with two stakes and tied the cloth loosely. ‘Room to move, but "
    "not enough to fall,’ Asha said. Overnight, rain drummed on the shed roof. In the "
    "morning the tree still stood, and none of its bark had been rubbed raw."
)


ADDITIONAL_QUESTIONS = [
    # Mathematics
    _question(
        "m17", "Maths", "Fractions", "Work out 2 3/4 + 1 5/8.",
        (("A", "3 7/8"), ("B", "4 1/8"), ("C", "4 3/8"), ("D", "4 5/8")), "C",
        "2 3/4 is 2 6/8. Adding 1 5/8 gives 3 11/8, which is 4 3/8.",
    ),
    _question(
        "m18", "Maths", "Percentages",
        "A coat costs £80 and is reduced by 15%. What is the sale price?",
        (("A", "£64"), ("B", "£66"), ("C", "£68"), ("D", "£72")), "C",
        "15% of £80 is £12, so the sale price is £80 − £12 = £68.",
    ),
    _question(
        "m19", "Maths", "Ratio",
        "£84 is shared in the ratio 3:4. What is the larger share?",
        (("A", "£36"), ("B", "£42"), ("C", "£48"), ("D", "£56")), "C",
        "There are 7 equal parts, so each part is £12. The larger share is 4 × £12 = £48.",
    ),
    _question(
        "m20", "Maths", "Speed and time",
        "A cyclist travels 18 km at an average speed of 12 km per hour. How long does the journey take?",
        (("A", "1 hour 12 minutes"), ("B", "1 hour 20 minutes"),
         ("C", "1 hour 30 minutes"), ("D", "1 hour 48 minutes")), "C",
        "Time = distance ÷ speed = 18 ÷ 12 = 1.5 hours, which is 1 hour 30 minutes.",
    ),
    _question(
        "m21", "Maths", "Perimeter",
        "A rectangular garden is 18 m long and 11 m wide. What is its perimeter?",
        (("A", "29 m"), ("B", "47 m"), ("C", "58 m"), ("D", "198 m")), "C",
        "Perimeter is 2 × (18 + 11) = 2 × 29 = 58 m.",
    ),
    _question(
        "m22", "Maths", "Averages",
        "The mean of five numbers is 24. Four of the numbers are 17, 22, 25 and 27. What is the fifth number?",
        (("A", "24"), ("B", "27"), ("C", "29"), ("D", "31")), "C",
        "The five numbers total 5 × 24 = 120. The four shown total 91, so the missing number is 29.",
    ),
    _question(
        "m23", "Maths", "Algebra", "Solve 3(x + 4) = 33.",
        (("A", "5"), ("B", "7"), ("C", "9"), ("D", "15")), "B",
        "Divide by 3 to get x + 4 = 11, then subtract 4. Therefore x = 7.",
    ),
    _question(
        "m24", "Maths", "Measures", "Work out 2.35 kg + 680 g. Give the answer in kilograms.",
        (("A", "2.418 kg"), ("B", "2.93 kg"), ("C", "3.03 kg"), ("D", "3.75 kg")), "C",
        "680 g is 0.68 kg. Therefore 2.35 + 0.68 = 3.03 kg.",
    ),
    _question(
        "m25", "Maths", "Fractions", "Work out 7/8 − 5/12.",
        (("A", "1/3"), ("B", "5/24"), ("C", "11/24"), ("D", "1/2")), "C",
        "Using twenty-fourths, 7/8 = 21/24 and 5/12 = 10/24. The difference is 11/24.",
    ),
    _question(
        "m26", "Maths", "Percentages", "35% of a number is 84. What is the number?",
        (("A", "196"), ("B", "210"), ("C", "224"), ("D", "240")), "D",
        "If 35% is 84, then 5% is 12. Twenty lots of 5% make 100%, so the number is 240.",
    ),
    _question(
        "m27", "Maths", "Money",
        "Four adult tickets cost £7.50 each and three child tickets cost £4.25 each. What is the total cost?",
        (("A", "£39.25"), ("B", "£41.75"), ("C", "£42.75"), ("D", "£45.25")), "C",
        "The adult tickets cost £30 and the child tickets cost £12.75. The total is £42.75.",
    ),
    _question(
        "m28", "Maths", "Area", "A triangle has a base of 14 cm and a perpendicular height of 9 cm. What is its area?",
        (("A", "23 cm²"), ("B", "46 cm²"), ("C", "63 cm²"), ("D", "126 cm²")), "C",
        "Triangle area = base × height ÷ 2, so 14 × 9 ÷ 2 = 63 cm².",
    ),
    _question(
        "m29", "Maths", "Sequences", "What is the next number? 2, 6, 12, 20, 30, …",
        (("A", "36"), ("B", "40"), ("C", "42"), ("D", "44")), "C",
        "The gaps are 4, 6, 8 and 10. The next gap is 12, so 30 + 12 = 42.",
    ),
    _question(
        "m30", "Maths", "Volume", "A cuboid measures 8 cm by 5 cm by 4 cm. What is its volume?",
        (("A", "17 cm³"), ("B", "40 cm³"), ("C", "80 cm³"), ("D", "160 cm³")), "D",
        "Volume = 8 × 5 × 4 = 160 cm³.",
    ),
    _question(
        "m31", "Maths", "Probability",
        "A bag contains 6 red and 4 blue counters. One red counter is removed. What is the probability that the next counter is blue?",
        (("A", "2/5"), ("B", "4/9"), ("C", "1/2"), ("D", "5/9")), "B",
        "After one red counter is removed, 4 of the 9 remaining counters are blue, so the probability is 4/9.",
    ),
    _question(
        "m32", "Maths", "Time", "A film starts at 14:35 and ends at 16:22. How long does it last?",
        (("A", "1 hour 37 minutes"), ("B", "1 hour 47 minutes"),
         ("C", "2 hours 13 minutes"), ("D", "2 hours 47 minutes")), "B",
        "From 14:35 to 15:35 is one hour, then to 16:22 is another 47 minutes.",
    ),

    # English
    _question(
        "e17", "English", "Comprehension",
        "Why did Priya change what she planned to do in the glasshouse?",
        (("A", "The seedlings were dry and needed water."), ("B", "Mr Okoro asked her to clean the roof."),
         ("C", "She had lost the trowel."), ("D", "The rain had flooded every tray.")), "A",
        "Priya notices the bowed seedlings and dry trays, so she waters them instead of only collecting the trowel.",
        context=_GLASSHOUSE_PASSAGE,
    ),
    _question(
        "e18", "English", "Comprehension vocabulary",
        "In the passage, what does banking most nearly mean?",
        (("A", "disappearing"), ("B", "gathering into a mass"), ("C", "shining brightly"), ("D", "moving underground")), "B",
        "The dark clouds are gathering or piling up above the hill.",
        context=_GLASSHOUSE_PASSAGE,
    ),
    _question(
        "e19", "English", "Inference", "What can we infer about Priya?",
        (("A", "She avoids unexpected work."), ("B", "She is observant and helpful."),
         ("C", "She is frightened of rain."), ("D", "She wants Mr Okoro to leave.")), "B",
        "Priya spots what the plants need, acts without being asked and quietly finishes the job.",
        context=_GLASSHOUSE_PASSAGE,
    ),
    _question(
        "e20", "English", "Writer's choices",
        "What does the phrase the leaves had lifted suggest?",
        (("A", "The wind had blown the plants away."), ("B", "The plants had recovered after being watered."),
         ("C", "Mr Okoro had moved the trays."), ("D", "The roof pane had been repaired.")), "B",
        "The seedlings were bowed at first; their lifted leaves show that the water helped them recover.",
        context=_GLASSHOUSE_PASSAGE,
    ),
    _question(
        "e21", "English", "Vocabulary", "Which word is closest in meaning to concise?",
        (("A", "brief"), ("B", "confusing"), ("C", "ancient"), ("D", "noisy")), "A",
        "Concise means giving information clearly in only a few words, so brief is closest.",
    ),
    _question(
        "e22", "English", "Vocabulary", "Which word is the opposite of expand?",
        (("A", "stretch"), ("B", "increase"), ("C", "contract"), ("D", "explain")), "C",
        "To expand is to become larger; to contract is to become smaller.",
    ),
    _question(
        "e23", "English", "Punctuation", "Which sentence is punctuated correctly?",
        (("A", "Sam who lives in York, is visiting on Friday."),
         ("B", "Sam, who lives in York is visiting on Friday."),
         ("C", "Sam, who lives in York, is visiting on Friday."),
         ("D", "Sam who lives in York is visiting, on Friday.")), "C",
        "The relative clause adds extra information and needs a comma before and after it.",
    ),
    _question(
        "e24", "English", "Spelling", "Which spelling is correct?",
        (("A", "acommodate"), ("B", "accommodate"), ("C", "accomodate"), ("D", "accommadate")), "B",
        "Accommodate is spelt with two c letters and two m letters.",
    ),
    _question(
        "e25", "English", "Verb forms", "Choose the sentence with the correct verb forms.",
        (("A", "If I knew about the rain, I would have bring a coat."),
         ("B", "If I had known about the rain, I would have brought a coat."),
         ("C", "If I have knew about the rain, I brought a coat."),
         ("D", "If I had know about the rain, I would bringed a coat.")), "B",
        "Had known and would have brought correctly describe an unreal situation in the past.",
    ),
    _question(
        "e26", "English", "Apostrophes",
        "Which sentence correctly shows that the coats belong to several children?",
        (("A", "The childrens coats were hanging up."), ("B", "The childrens' coats were hanging up."),
         ("C", "The children's coats were hanging up."), ("D", "The childrens's coats were hanging up.")), "C",
        "Children is an irregular plural, so possession is shown by adding apostrophe-s: children's.",
    ),
    _question(
        "e27", "English", "Word classes",
        "Which word is the adverb in this sentence? The audience waited patiently beside the closed doors.",
        (("A", "audience"), ("B", "waited"), ("C", "patiently"), ("D", "closed")), "C",
        "Patiently describes how the audience waited, so it is an adverb.",
    ),
    _question(
        "e28", "English", "Formal language",
        "Choose the most formal word: The committee will ___ the proposal tomorrow.",
        (("A", "look at"), ("B", "check out"), ("C", "evaluate"), ("D", "have a peek at")), "C",
        "Evaluate is the most formal choice and means to assess something carefully.",
    ),
    _question(
        "e29", "English", "Comprehension", "Why did Leo choose the deer track?",
        (("A", "He wanted to avoid the checkpoint."), ("B", "It was the route shown on his map."),
         ("C", "It was safer for Hana's injured wrist."), ("D", "He could hear deer nearby.")), "C",
        "Climbing the trunk would be risky for Hana, so Leo chooses the safer route around it.",
        context=_WOODLAND_PASSAGE,
    ),
    _question(
        "e30", "English", "Comprehension vocabulary",
        "What does it would cost a minute mean in the passage?",
        (("A", "Leo would have to pay money."), ("B", "The route would take extra time."),
         ("C", "The checkpoint would close."), ("D", "Hana would lose her map.")), "B",
        "Cost is used figuratively to mean that the safer route would take additional time.",
        context=_WOODLAND_PASSAGE,
    ),
    _question(
        "e31", "English", "Inference", "What does Leo's decision show?",
        (("A", "He values his teammate's safety more than taking the fastest route."),
         ("B", "He has forgotten the purpose of the race."),
         ("C", "He does not trust any race markers."),
         ("D", "He wants the other runners to overtake him.")), "A",
        "Leo accepts a small delay so that Hana can continue safely.",
        context=_WOODLAND_PASSAGE,
    ),
    _question(
        "e32", "English", "Writer's choices",
        "Why does the writer say that shoes struck the gravel behind Leo?",
        (("A", "To explain how the oak fell"), ("B", "To show that other runners are approaching"),
         ("C", "To suggest that Hana has gone home"), ("D", "To describe the sound of the bell")), "B",
        "The approaching footsteps add urgency because competitors are close behind.",
        context=_WOODLAND_PASSAGE,
    ),

    # Verbal reasoning
    _question(
        "v17", "Verbal Reasoning", "Letter codes",
        "In a code, every letter moves two places forward in the alphabet. How is LAMP written?",
        (("A", "NCOR"), ("B", "NCPR"), ("C", "MBNQ"), ("D", "JYKN")), "A",
        "L→N, A→C, M→O and P→R, so LAMP becomes NCOR.",
    ),
    _question(
        "v18", "Verbal Reasoning", "Letter sequences", "What comes next? AB, DE, GH, JK, …",
        (("A", "LM"), ("B", "MN"), ("C", "NO"), ("D", "NP")), "B",
        "Each pair starts three letters after the previous pair: A, D, G, J, then M. The pair is MN.",
    ),
    _question(
        "v19", "Verbal Reasoning", "Analogies", "Bark is to dog as neigh is to …",
        (("A", "horse"), ("B", "sheep"), ("C", "owl"), ("D", "frog")), "A",
        "A dog barks and a horse neighs.",
    ),
    _question(
        "v20", "Verbal Reasoning", "Odd one out", "Which word is the odd one out?",
        (("A", "granite"), ("B", "marble"), ("C", "limestone"), ("D", "copper")), "D",
        "Granite, marble and limestone are rocks. Copper is a metal.",
    ),
    _question(
        "v21", "Verbal Reasoning", "Word links",
        "Which word can go after RAIN and before TIE to make two new words?",
        (("A", "bow"), ("B", "coat"), ("C", "drop"), ("D", "storm")), "A",
        "RAIN + BOW makes rainbow, and BOW + TIE makes bow tie.",
    ),
    _question(
        "v22", "Verbal Reasoning", "Alphabet values",
        "Using A=1, B=2, C=3 and so on, what is the value of MATH?",
        (("A", "38"), ("B", "40"), ("C", "42"), ("D", "44")), "C",
        "M=13, A=1, T=20 and H=8. Their total is 42.",
    ),
    _question(
        "v23", "Verbal Reasoning", "Anagrams", "Which word is an anagram of STREAM?",
        (("A", "MASTER"), ("B", "MUSTER"), ("C", "MARKET"), ("D", "STORM")), "A",
        "MASTER uses exactly the same six letters as STREAM.",
    ),
    _question(
        "v24", "Verbal Reasoning", "Number sequences", "What is the next number? 5, 9, 17, 33, 65, …",
        (("A", "97"), ("B", "127"), ("C", "129"), ("D", "130")), "C",
        "Each number is doubled and then 1 is subtracted. 65 × 2 − 1 = 129.",
    ),
    _question(
        "v25", "Verbal Reasoning", "Letter relationships",
        "DG becomes IL by moving each letter five places forward. What does FM become?",
        (("A", "JQ"), ("B", "KR"), ("C", "LS"), ("D", "MR")), "B",
        "F moves to K and M moves to R, so FM becomes KR.",
    ),
    _question(
        "v26", "Verbal Reasoning", "Word relationships", "Which pair has a different relationship?",
        (("A", "huge : enormous"), ("B", "silent : quiet"),
         ("C", "tiny : minute"), ("D", "ancient : modern")), "D",
        "The first three pairs have similar meanings. Ancient and modern are opposites.",
    ),
    _question(
        "v27", "Verbal Reasoning", "Logic",
        "All kestrels are birds. No birds are mammals. Which statement must be true?",
        (("A", "All mammals are kestrels."), ("B", "Some kestrels are mammals."),
         ("C", "No kestrels are mammals."), ("D", "No mammals can fly.")), "C",
        "Every kestrel is a bird, and no bird is a mammal, so no kestrel can be a mammal.",
    ),
    _question(
        "v28", "Verbal Reasoning", "Missing letters",
        "The same two letters complete both words: C __ T and P __ K. Which letters are they?",
        (("A", "AR"), ("B", "OA"), ("C", "OR"), ("D", "IN")), "A",
        "AR makes C + AR + T = CART and P + AR + K = PARK.",
    ),
    _question(
        "v29", "Verbal Reasoning", "Word links",
        "Which word can go after HOME and before SHOP to make two new words?",
        (("A", "book"), ("B", "pet"), ("C", "work"), ("D", "toy")), "C",
        "HOME + WORK makes homework, and WORK + SHOP makes workshop.",
    ),
    _question(
        "v30", "Verbal Reasoning", "Alphabetical order",
        "If these words are put in alphabetical order, which comes third? glacier, glimpse, globe, glow",
        (("A", "glacier"), ("B", "glimpse"), ("C", "globe"), ("D", "glow")), "C",
        "The order is glacier, glimpse, globe, glow, so globe is third.",
    ),
    _question(
        "v31", "Verbal Reasoning", "Letter codes",
        "In a mirror-alphabet code A becomes Z, B becomes Y, and so on. How is CAT written?",
        (("A", "XZG"), ("B", "XZH"), ("C", "WZG"), ("D", "XZU")), "A",
        "C becomes X, A becomes Z and T becomes G, giving XZG.",
    ),
    _question(
        "v32", "Verbal Reasoning", "Analogies", "Bee is to hive as ant is to …",
        (("A", "swarm"), ("B", "nest"), ("C", "web"), ("D", "kennel")), "B",
        "A hive is a home made by bees; a nest is a home made by ants.",
    ),

    # Non-verbal and spatial reasoning
    _question(
        "n17", "Non-Verbal Reasoning", "Rotation", "An arrow turns 90° clockwise each time: →, ↓, ←, …",
        (("A", "↑"), ("B", "↗"), ("C", "→"), ("D", "↙")), "A",
        "One more quarter-turn clockwise from left makes the arrow point up.",
    ),
    _question(
        "n18", "Non-Verbal Reasoning", "Position sequences", "What comes next? ●○○, ○●○, ○○●, …",
        (("A", "●○○"), ("B", "○●○"), ("C", "○○●"), ("D", "●●○")), "A",
        "The filled circle moves one place to the right and returns to the first place after the third step.",
    ),
    _question(
        "n19", "Non-Verbal Reasoning", "Shape properties",
        "The shapes have 4 sides, then 6 sides, then 8 sides. How many sides should the next shape have?",
        (("A", "9"), ("B", "10"), ("C", "11"), ("D", "12")), "B",
        "The number of sides increases by two each time: 4, 6, 8, 10.",
    ),
    _question(
        "n20", "Non-Verbal Reasoning", "Matrices",
        "Complete the 2×2 pattern. Top row: ○ becomes ●. Bottom row: □ becomes ?",
        (("A", "□"), ("B", "■"), ("C", "◇"), ("D", "◆")), "B",
        "Across each row the same shape changes from hollow to filled, so □ becomes ■.",
    ),
    _question(
        "n21", "Non-Verbal Reasoning", "Reflection", "A vertical mirror reflection changes ↗ into which arrow?",
        (("A", "↖"), ("B", "↘"), ("C", "↗"), ("D", "↙")), "A",
        "A vertical mirror reverses left and right, so up-right becomes up-left.",
    ),
    _question(
        "n22", "Non-Verbal Reasoning", "Repeating groups", "What comes next? ▲, ▲▲, ■, ■■, ●, …",
        (("A", "▲▲"), ("B", "■■"), ("C", "●●"), ("D", "●●●")), "C",
        "Each shape appears once and then twice, so the single circle is followed by two circles.",
    ),
    _question(
        "n23", "Non-Verbal Reasoning", "Two-rule patterns", "What comes next? □↑, ○→, □↓, ○←, …",
        (("A", "□↑"), ("B", "○↑"), ("C", "□→"), ("D", "○↓")), "A",
        "The outer shape alternates square and circle while the arrow turns 90° clockwise. Next is □↑.",
    ),
    _question(
        "n24", "Non-Verbal Reasoning", "Symmetry", "Which shape has no line of symmetry?",
        (("A", "a square"), ("B", "a circle"), ("C", "an isosceles triangle"), ("D", "a scalene triangle")), "D",
        "A scalene triangle has no equal sides and no line of symmetry.",
    ),
    _question(
        "n25", "Non-Verbal Reasoning", "Cubes",
        "On a cube, A is opposite D, B is opposite E, and C is opposite F. Which face is opposite B?",
        (("A", "A"), ("B", "C"), ("C", "D"), ("D", "E")), "D",
        "The information states that B and E are opposite faces.",
    ),
    _question(
        "n26", "Non-Verbal Reasoning", "Rotation", "An arrow turns 45° clockwise each time: ↖, ↑, ↗, →, …",
        (("A", "↘"), ("B", "↓"), ("C", "↙"), ("D", "←")), "A",
        "A 45° clockwise turn from right points down-right: ↘.",
    ),
    _question(
        "n27", "Non-Verbal Reasoning", "Matrices",
        "Across each row, one shape is added. Top row: ▲▲ then ▲▲▲. Bottom row: ●●● then ?",
        (("A", "●●"), ("B", "●●●"), ("C", "●●●●"), ("D", "●●●●●")), "C",
        "The rule adds one matching shape, so three circles become four circles.",
    ),
    _question(
        "n28", "Non-Verbal Reasoning", "Two-rule patterns", "What comes next? □, ■■, □□□, …",
        (("A", "□□□□"), ("B", "■■■"), ("C", "■■■■"), ("D", "□□□□□")), "C",
        "The number rises by one while hollow and filled shading alternate. The next group is four filled squares.",
    ),
    _question(
        "n29", "Non-Verbal Reasoning", "Transformations",
        "The rule changes ○△ into ●▲. Using the same rule, what does □◇ become?",
        (("A", "□◇"), ("B", "■◇"), ("C", "□◆"), ("D", "■◆")), "D",
        "The rule fills every hollow shape without changing its type, so □◇ becomes ■◆.",
    ),
    _question(
        "n30", "Non-Verbal Reasoning", "Position changes",
        "A dot alternates between the top-left and bottom-right corners. It is top-left, bottom-right, top-left, … Where is it next?",
        (("A", "top-right"), ("B", "bottom-left"), ("C", "bottom-right"), ("D", "centre")), "C",
        "The two positions alternate, so bottom-right follows top-left.",
    ),
    _question(
        "n31", "Non-Verbal Reasoning", "Spatial reasoning",
        "A square sheet is folded exactly in half, then folded exactly in half again. How many layers are there?",
        (("A", "2"), ("B", "3"), ("C", "4"), ("D", "8")), "C",
        "The first fold makes two layers and the second fold doubles them to four.",
    ),
    _question(
        "n32", "Non-Verbal Reasoning", "Rotation",
        "A flag points right with its pole on the left. After a 180° turn, what will it look like?",
        (("A", "It points right with the pole on the left."),
         ("B", "It points left with the pole on the right."),
         ("C", "It points up with the pole below."),
         ("D", "It points down with the pole above.")), "B",
        "A half-turn reverses both direction and position, so the flag points left and the pole is on the right.",
    ),
]

ADDITIONAL_QUESTIONS.extend([
    # Mathematics: third original expansion set
    _question(
        "m33", "Maths", "Rounding",
        "Round 487,650 to the nearest 10,000.",
        (("A", "480,000"), ("B", "487,000"), ("C", "490,000"), ("D", "500,000")), "C",
        "The thousands digit is 7, so 487,650 rounds up to 490,000.",
    ),
    _question(
        "m34", "Maths", "Fractions", "What is 5/6 of 72?",
        (("A", "48"), ("B", "54"), ("C", "60"), ("D", "66")), "C",
        "One sixth of 72 is 12, so five sixths is 5 × 12 = 60.",
    ),
    _question(
        "m35", "Maths", "Proportion",
        "A recipe uses 250 g of flour for 10 biscuits. How much flour is needed for 18 biscuits?",
        (("A", "400 g"), ("B", "425 g"), ("C", "450 g"), ("D", "500 g")), "C",
        "Each biscuit uses 25 g of flour. For 18 biscuits, 18 × 25 = 450 g.",
    ),
    _question(
        "m36", "Maths", "Percentages",
        "A club has 160 members. Membership increases by 12.5%. How many members are there now?",
        (("A", "172"), ("B", "176"), ("C", "180"), ("D", "182")), "C",
        "12.5% is one eighth. One eighth of 160 is 20, so the new total is 180.",
    ),
    _question(
        "m37", "Maths", "Division",
        "A warehouse packs 1,275 pencils into boxes of 24. How many complete boxes can it fill?",
        (("A", "51"), ("B", "52"), ("C", "53"), ("D", "54")), "C",
        "24 × 53 = 1,272, leaving 3 pencils. Therefore 53 complete boxes can be filled.",
    ),
    _question(
        "m38", "Maths", "Angles",
        "Three angles in a quadrilateral are 95°, 88° and 102°. What is the fourth angle?",
        (("A", "65°"), ("B", "75°"), ("C", "85°"), ("D", "105°")), "B",
        "Angles in a quadrilateral total 360°. The known angles total 285°, leaving 75°.",
    ),
    _question(
        "m39", "Maths", "Coordinates",
        "A point at (3, 7) moves 4 units right and 2 units down. What are its new coordinates?",
        (("A", "(5, 11)"), ("B", "(7, 5)"), ("C", "(7, 9)"), ("D", "(1, 11)")), "B",
        "Moving right adds 4 to x and moving down subtracts 2 from y, giving (7, 5).",
    ),
    _question(
        "m40", "Maths", "Data handling",
        "What is the range of these temperatures? 42°C, 55°C, 38°C, 61°C, 47°C",
        (("A", "19°C"), ("B", "21°C"), ("C", "23°C"), ("D", "25°C")), "C",
        "The range is the highest value minus the lowest: 61 − 38 = 23°C.",
    ),
    _question(
        "m41", "Maths", "Mixed numbers", "Work out 2 1/4 × 4.",
        (("A", "8"), ("B", "8 1/4"), ("C", "9"), ("D", "9 1/4")), "C",
        "Four lots of 2 make 8, and four lots of one quarter make 1. The total is 9.",
    ),
    _question(
        "m42", "Maths", "Ratio",
        "The ratio of boys to girls in a choir is 5:7. There are 35 girls. How many children are in the choir?",
        (("A", "50"), ("B", "55"), ("C", "60"), ("D", "70")), "C",
        "Seven parts equal 35, so one part is 5. Boys = 25 and the total is 25 + 35 = 60.",
    ),
    _question(
        "m43", "Maths", "Measures",
        "3.6 litres of juice is shared equally between 8 bottles. How much goes in each bottle?",
        (("A", "400 ml"), ("B", "425 ml"), ("C", "450 ml"), ("D", "480 ml")), "C",
        "3.6 litres is 3,600 ml. Dividing by 8 gives 450 ml per bottle.",
    ),
    _question(
        "m44", "Maths", "Area",
        "A 15 cm by 9 cm rectangle has a 5 cm by 5 cm square cut from one corner. What area remains?",
        (("A", "90 cm²"), ("B", "100 cm²"), ("C", "110 cm²"), ("D", "130 cm²")), "C",
        "The rectangle has area 135 cm² and the square has area 25 cm². 135 − 25 = 110 cm².",
    ),
    _question(
        "m45", "Maths", "Factors", "What is the highest common factor of 24 and 36?",
        (("A", "6"), ("B", "8"), ("C", "12"), ("D", "18")), "C",
        "The common factors include 1, 2, 3, 4, 6 and 12. The greatest is 12.",
    ),
    _question(
        "m46", "Maths", "Algebra", "Solve 5n − 8 = 47.",
        (("A", "9"), ("B", "10"), ("C", "11"), ("D", "13")), "C",
        "Add 8 to get 5n = 55, then divide by 5. Therefore n = 11.",
    ),
    _question(
        "m47", "Maths", "Scale",
        "A plan uses a scale of 1:200. A wall measures 6.5 cm on the plan. What is its real length?",
        (("A", "1.3 m"), ("B", "6.5 m"), ("C", "13 m"), ("D", "130 m")), "C",
        "6.5 × 200 = 1,300 cm, which is 13 m.",
    ),
    _question(
        "m48", "Maths", "Probability",
        "A fair spinner has eight equal sections numbered 1 to 8. What is the probability of landing on a multiple of 3?",
        (("A", "1/8"), ("B", "1/4"), ("C", "3/8"), ("D", "1/2")), "B",
        "The multiples of 3 are 3 and 6, so 2 of 8 outcomes work. 2/8 simplifies to 1/4.",
    ),

    # English: third original expansion set
    _question(
        "e33", "English", "Comprehension", "Why did Amara and Grandad turn back?",
        (("A", "They had forgotten the paintbrushes."), ("B", "The rising tide was covering the causeway."),
         ("C", "The lighthouse door had already been painted."), ("D", "Weekend visitors had arrived early.")), "B",
        "The joining pools show that the tide is rising and the route will soon be underwater.",
        context=_CAUSEWAY_PASSAGE,
    ),
    _question(
        "e34", "English", "Comprehension vocabulary",
        "What does the shallow pools beginning to join suggest?",
        (("A", "The stones are becoming drier."), ("B", "Water is spreading across the causeway."),
         ("C", "The harbour is being repaired."), ("D", "Visitors are crossing the stones.")), "B",
        "Separate pools connecting is a sign that more water is covering the causeway.",
        context=_CAUSEWAY_PASSAGE,
    ),
    _question(
        "e35", "English", "Inference", "What can we infer about Amara?",
        (("A", "She is alert to changes around her."), ("B", "She dislikes helping Grandad."),
         ("C", "She has never seen the sea."), ("D", "She wants to miss the weekend visitors.")), "A",
        "Amara notices the water joining and correctly realises that the tide is arriving early.",
        context=_CAUSEWAY_PASSAGE,
    ),
    _question(
        "e36", "English", "Writer's choices",
        "What is the effect of the final sentence: The door could wait; the tide would not?",
        (("A", "It shows that finishing the paintwork matters most."),
         ("B", "It contrasts a delayable job with an urgent danger."),
         ("C", "It proves the lighthouse door is broken."),
         ("D", "It suggests the tide has stopped moving.")), "B",
        "Painting can be postponed, but the tide keeps rising, so returning safely is urgent.",
        context=_CAUSEWAY_PASSAGE,
    ),
    _question(
        "e37", "English", "Vocabulary", "Which meaning is closest to ambiguous?",
        (("A", "open to more than one meaning"), ("B", "extremely cheerful"),
         ("C", "easy to measure"), ("D", "written in order")), "A",
        "Ambiguous describes something that can be understood in more than one way.",
    ),
    _question(
        "e38", "English", "Vocabulary", "Which word is the opposite of deteriorate?",
        (("A", "decline"), ("B", "improve"), ("C", "weaken"), ("D", "worsen")), "B",
        "Deteriorate means become worse; improve means become better.",
    ),
    _question(
        "e39", "English", "Punctuation", "Which sentence uses a colon correctly?",
        (("A", "Bring: a torch, a map and a whistle."),
         ("B", "Bring three items: a torch, a map and a whistle."),
         ("C", "Bring three: items a torch, a map and a whistle."),
         ("D", "Bring three items a torch: a map and a whistle.")), "B",
        "A colon can introduce a list after a complete clause: Bring three items.",
    ),
    _question(
        "e40", "English", "Spelling", "Which spelling is correct?",
        (("A", "priviledge"), ("B", "privelege"), ("C", "privilege"), ("D", "privillage")), "C",
        "Privilege is spelt p-r-i-v-i-l-e-g-e.",
    ),
    _question(
        "e41", "English", "Grammar", "Choose the sentence with correct subject–verb agreement.",
        (("A", "Neither of the routes are suitable."), ("B", "Neither of the routes is suitable."),
         ("C", "Neither of the routes be suitable."), ("D", "Neither of the routes were suitable now.")), "B",
        "Neither is singular here, so it takes the singular verb is.",
    ),
    _question(
        "e42", "English", "Apostrophes", "Which phrase means the picnic belonging to one family?",
        (("A", "the familys picnic"), ("B", "the family's picnic"),
         ("C", "the families picnic"), ("D", "the families' picnic")), "B",
        "For one family, add apostrophe-s: the family's picnic.",
    ),
    _question(
        "e43", "English", "Active and passive voice", "Which sentence is written in the passive voice?",
        (("A", "The captain lifted the trophy."), ("B", "The crowd cheered the captain."),
         ("C", "The trophy was presented by the mayor."), ("D", "The mayor smiled proudly.")), "C",
        "Was presented is passive because the trophy receives the action.",
    ),
    _question(
        "e44", "English", "Cohesion",
        "Choose the best linking word: The path was steep. ___, the group reached the summit before noon.",
        (("A", "For example"), ("B", "Meanwhile"), ("C", "Nevertheless"), ("D", "Similarly")), "C",
        "Nevertheless shows contrast: the climb was difficult, but the group still arrived early.",
    ),
    _question(
        "e45", "English", "Comprehension", "Why did Elena decide not to rub out the pencilled notes?",
        (("A", "She did not have an eraser."), ("B", "The marks might be historically important."),
         ("C", "The programme belonged to the curator."), ("D", "The theatre was reopening that day.")), "B",
        "The initials and working notes suggest a connection to a celebrated director and a real rehearsal.",
        context=_MUSEUM_PASSAGE,
    ),
    _question(
        "e46", "English", "Inference",
        "What do the crossed-out names, altered timings and arrows most likely show?",
        (("A", "The programme was damaged in storage."), ("B", "Someone used it while planning or rehearsing."),
         ("C", "Visitors drew on it recently."), ("D", "The printing company made many mistakes.")), "B",
        "The practical changes look like working notes made while organising a rehearsal.",
        context=_MUSEUM_PASSAGE,
    ),
    _question(
        "e47", "English", "Character inference", "Which description best fits Elena?",
        (("A", "Careless and impatient"), ("B", "Curious and careful"),
         ("C", "Secretive and dishonest"), ("D", "Noisy and distracted")), "B",
        "She notices the initials, preserves the marks, records every page and asks an expert.",
        context=_MUSEUM_PASSAGE,
    ),
    _question(
        "e48", "English", "Writer's choices",
        "Why does the writer contrast an ordinary souvenir with a rare record?",
        (("A", "To show that the programme became more expensive to print"),
         ("B", "To show how the notes changed the programme's significance"),
         ("C", "To suggest that all museum objects are ordinary"),
         ("D", "To explain why the theatre closed")), "B",
        "The handwritten evidence gives an otherwise common programme special historical value.",
        context=_MUSEUM_PASSAGE,
    ),

    # Verbal reasoning: third original expansion set
    _question(
        "v33", "Verbal Reasoning", "Letter codes",
        "In a code, every letter moves two places backwards in the alphabet. How is MOON written?",
        (("A", "KMML"), ("B", "KNNL"), ("C", "LNNM"), ("D", "OQQP")), "A",
        "M→K, O→M, O→M and N→L, so MOON becomes KMML.",
    ),
    _question(
        "v34", "Verbal Reasoning", "Letter sequences", "What comes next? ZA, XC, VE, TG, …",
        (("A", "RH"), ("B", "RI"), ("C", "SI"), ("D", "RJ")), "B",
        "The first letter moves back two places and the second moves forward two, giving RI.",
    ),
    _question(
        "v35", "Verbal Reasoning", "Analogies", "Chapter is to book as scene is to …",
        (("A", "actor"), ("B", "play"), ("C", "stage"), ("D", "costume")), "B",
        "A chapter is a section of a book, and a scene is a section of a play.",
    ),
    _question(
        "v36", "Verbal Reasoning", "Odd one out", "Which word is the odd one out?",
        (("A", "sprint"), ("B", "jog"), ("C", "stroll"), ("D", "stationary")), "D",
        "Sprint, jog and stroll are ways of moving. Stationary means not moving.",
    ),
    _question(
        "v37", "Verbal Reasoning", "Word links",
        "Which word can go after STAR and before BOWL to make two new words?",
        (("A", "dust"), ("B", "fish"), ("C", "light"), ("D", "shine")), "B",
        "STAR + FISH makes starfish, and FISH + BOWL makes fishbowl.",
    ),
    _question(
        "v38", "Verbal Reasoning", "Alphabet values",
        "Using A=1, B=2, C=3 and so on, what is the value of CODE?",
        (("A", "25"), ("B", "26"), ("C", "27"), ("D", "29")), "C",
        "C=3, O=15, D=4 and E=5. Their total is 27.",
    ),
    _question(
        "v39", "Verbal Reasoning", "Anagrams", "Which word is an anagram of CHEATER?",
        (("A", "TEACHER"), ("B", "REACHED"), ("C", "CREATED"), ("D", "CHEAPER")), "A",
        "TEACHER uses exactly the same seven letters as CHEATER.",
    ),
    _question(
        "v40", "Verbal Reasoning", "Number sequences", "What is the next number? 2, 5, 11, 23, 47, …",
        (("A", "71"), ("B", "93"), ("C", "95"), ("D", "96")), "C",
        "Each number is doubled and then 1 is added. 47 × 2 + 1 = 95.",
    ),
    _question(
        "v41", "Verbal Reasoning", "Letter relationships",
        "AZ becomes CX by moving the first letter two places forward and the second two places back. What does DW become?",
        (("A", "ET"), ("B", "FU"), ("C", "FV"), ("D", "GT")), "B",
        "D moves forward to F and W moves back to U, so DW becomes FU.",
    ),
    _question(
        "v42", "Verbal Reasoning", "Word relationships", "Which pair has a different relationship?",
        (("A", "hammer : hit"), ("B", "scissors : cut"),
         ("C", "pen : write"), ("D", "meal : eat")), "D",
        "The first word in the first three pairs is a tool used for the action. A meal is something acted upon.",
    ),
    _question(
        "v43", "Verbal Reasoning", "Logic",
        "Some nims are red. All red things are round. Which statement must be true?",
        (("A", "All nims are round."), ("B", "Some nims are round."),
         ("C", "No round things are nims."), ("D", "All round things are red.")), "B",
        "The nims that are red must also be round, so at least some nims are round.",
    ),
    _question(
        "v44", "Verbal Reasoning", "Missing letters",
        "The same two letters complete both words: F __ M and ST __ M. Which letters are they?",
        (("A", "AR"), ("B", "EA"), ("C", "IR"), ("D", "OR")), "D",
        "OR makes F + OR + M = FORM and ST + OR + M = STORM.",
    ),
    _question(
        "v45", "Verbal Reasoning", "Word links",
        "Which word can go after HEAD and before UP to make two new words?",
        (("A", "line"), ("B", "room"), ("C", "start"), ("D", "way")), "A",
        "HEAD + LINE makes headline, and LINE + UP makes lineup.",
    ),
    _question(
        "v46", "Verbal Reasoning", "Alphabetical order",
        "If these words are put in alphabetical order, which comes third? trace, track, trade, train",
        (("A", "trace"), ("B", "track"), ("C", "trade"), ("D", "train")), "C",
        "The order is trace, track, trade, train, so trade is third.",
    ),
    _question(
        "v47", "Verbal Reasoning", "Letter codes",
        "In a mirror-alphabet code A becomes Z, B becomes Y, and so on. How is DOG written?",
        (("A", "VKS"), ("B", "WLT"), ("C", "XMU"), ("D", "WMT")), "B",
        "D becomes W, O becomes L and G becomes T, giving WLT.",
    ),
    _question(
        "v48", "Verbal Reasoning", "Analogies", "Thermometer is to temperature as clock is to …",
        (("A", "distance"), ("B", "speed"), ("C", "time"), ("D", "weight")), "C",
        "A thermometer measures temperature, and a clock measures time.",
    ),

    # Non-verbal and spatial reasoning: third original expansion set
    _question(
        "n33", "Non-Verbal Reasoning", "Rotation", "An arrow turns 90° clockwise each time: ↓, ←, ↑, …",
        (("A", "↘"), ("B", "→"), ("C", "↓"), ("D", "↖")), "B",
        "One more quarter-turn clockwise from up makes the arrow point right.",
    ),
    _question(
        "n34", "Non-Verbal Reasoning", "Position sequences", "What comes next? ●○○○, ○●○○, ○○●○, ○○○●, …",
        (("A", "●○○○"), ("B", "○●○○"), ("C", "○○●○"), ("D", "●●○○")), "A",
        "The filled circle moves one place right and returns to the first position after four steps.",
    ),
    _question(
        "n35", "Non-Verbal Reasoning", "Shape properties",
        "The shapes have 10 sides, then 8 sides, then 6 sides. Which shape comes next?",
        (("A", "triangle"), ("B", "square"), ("C", "pentagon"), ("D", "octagon")), "B",
        "The number of sides falls by two: 10, 8, 6, then 4. A square has four sides.",
    ),
    _question(
        "n36", "Non-Verbal Reasoning", "Matrices",
        "Across each row, the arrow turns 90° clockwise. Top row: ↑ becomes →. Bottom row: ← becomes ?",
        (("A", "↑"), ("B", "→"), ("C", "↓"), ("D", "←")), "A",
        "A 90° clockwise turn changes a left arrow into an up arrow.",
    ),
    _question(
        "n37", "Non-Verbal Reasoning", "Reflection", "A horizontal mirror reflection changes ↗ into which arrow?",
        (("A", "↖"), ("B", "↘"), ("C", "↗"), ("D", "↙")), "B",
        "A horizontal mirror reverses up and down, so up-right becomes down-right.",
    ),
    _question(
        "n38", "Non-Verbal Reasoning", "Repeating groups", "What comes next? ◆, ◆◆, ▲, ▲▲, □, …",
        (("A", "□□"), ("B", "□□□"), ("C", "◆◆"), ("D", "▲▲")), "A",
        "Each shape appears once and then twice, so the single square is followed by two squares.",
    ),
    _question(
        "n39", "Non-Verbal Reasoning", "Two-rule patterns", "What comes next? ●↑, ○→, ●↓, ○←, …",
        (("A", "●↑"), ("B", "○↑"), ("C", "●→"), ("D", "○↓")), "A",
        "Filled and hollow circles alternate while the arrow turns clockwise. Next is ●↑.",
    ),
    _question(
        "n40", "Non-Verbal Reasoning", "Symmetry", "Which shape has no line of symmetry?",
        (("A", "a regular pentagon"), ("B", "a square"),
         ("C", "an equilateral triangle"), ("D", "a scalene triangle")), "D",
        "A scalene triangle has unequal sides and no line of symmetry.",
    ),
    _question(
        "n41", "Non-Verbal Reasoning", "Cubes",
        "On a cube, G is opposite J, H is opposite K, and I is opposite L. Which face is opposite K?",
        (("A", "G"), ("B", "H"), ("C", "I"), ("D", "L")), "B",
        "The information states that H and K are opposite faces.",
    ),
    _question(
        "n42", "Non-Verbal Reasoning", "Rotation", "An arrow turns 45° clockwise each time: ↓, ↙, ←, ↖, …",
        (("A", "↑"), ("B", "↗"), ("C", "→"), ("D", "↘")), "A",
        "One more 45° clockwise turn from up-left makes the arrow point up.",
    ),
    _question(
        "n43", "Non-Verbal Reasoning", "Matrices",
        "Across each row, two shapes are added. Top row: ● then ●●●. Bottom row: ■■ then ?",
        (("A", "■■"), ("B", "■■■"), ("C", "■■■■"), ("D", "■■■■■")), "C",
        "The rule adds two matching shapes, so two squares become four squares.",
    ),
    _question(
        "n44", "Non-Verbal Reasoning", "Two-rule patterns", "What comes next? ○, ■■, ○○○, ■■■■, …",
        (("A", "○○○○"), ("B", "○○○○○"), ("C", "■■■■■"), ("D", "■■■■■■")), "B",
        "The count rises by one while circles and squares alternate. Next are five hollow circles.",
    ),
    _question(
        "n45", "Non-Verbal Reasoning", "Transformations",
        "The rule changes ○↑ into ●→. Using the same rule, what does □← become?",
        (("A", "□↑"), ("B", "■↑"), ("C", "■↓"), ("D", "□→")), "B",
        "The shape becomes filled and the arrow turns 90° clockwise, so □← becomes ■↑.",
    ),
    _question(
        "n46", "Non-Verbal Reasoning", "Position changes",
        "A dot moves around the corners: top-left, bottom-left, bottom-right, top-right, … Where is it next?",
        (("A", "top-left"), ("B", "bottom-left"), ("C", "bottom-right"), ("D", "centre")), "A",
        "The dot has completed a circuit of the four corners, so it returns to top-left.",
    ),
    _question(
        "n47", "Non-Verbal Reasoning", "Spatial reasoning",
        "A rectangular sheet is folded exactly in half three times. How many layers are there?",
        (("A", "4"), ("B", "6"), ("C", "8"), ("D", "12")), "C",
        "Each fold doubles the layers: 1 becomes 2, then 4, then 8.",
    ),
    _question(
        "n48", "Non-Verbal Reasoning", "Rotation",
        "A dot is on the top edge of a square. The square turns 90° clockwise. Where is the dot now?",
        (("A", "top edge"), ("B", "right edge"), ("C", "bottom edge"), ("D", "left edge")), "B",
        "A quarter-turn clockwise moves the top edge to the right edge.",
    ),

    # Mathematics: fourth original expansion set
    _question(
        "m49", "Maths", "Fractions and measures",
        "A jug holds 2.4 litres when full. It is 3/4 full. How much water is in the jug?",
        (("A", "0.6 litres"), ("B", "1.6 litres"),
         ("C", "1.8 litres"), ("D", "2.1 litres")), "C",
        "One quarter of 2.4 litres is 0.6 litres, so three quarters is 3 × 0.6 = 1.8 litres.",
    ),
    _question(
        "m50", "Maths", "Percentages",
        "A library has 240 new books. 35% are non-fiction. How many are non-fiction?",
        (("A", "72"), ("B", "84"), ("C", "96"), ("D", "108")), "B",
        "10% of 240 is 24 and 5% is 12. Therefore 35% is 72 + 12 = 84.",
    ),
    _question(
        "m51", "Maths", "Ratio",
        "Red and blue counters are in the ratio 5:3. There are 64 counters altogether. How many are red?",
        (("A", "24"), ("B", "32"), ("C", "40"), ("D", "48")), "C",
        "There are 8 equal parts, so each part is 64 ÷ 8 = 8. Red has 5 parts: 5 × 8 = 40.",
    ),
    _question(
        "m52", "Maths", "Area",
        "A 15 cm by 8 cm rectangle has a 4 cm by 4 cm square cut from one corner. What area remains?",
        (("A", "88 cm²"), ("B", "104 cm²"),
         ("C", "112 cm²"), ("D", "116 cm²")), "B",
        "The rectangle's area is 15 × 8 = 120 cm². The cut-out is 4 × 4 = 16 cm², leaving 104 cm².",
    ),
    _question(
        "m53", "Maths", "Averages",
        "The mean of six numbers is 18. Five numbers are 15, 17, 19, 20 and 21. What is the sixth number?",
        (("A", "16"), ("B", "17"), ("C", "18"), ("D", "20")), "A",
        "All six numbers total 6 × 18 = 108. The five shown total 92, so the missing number is 16.",
    ),
    _question(
        "m54", "Maths", "Time",
        "A train leaves at 09:47 and the journey lasts 2 hours 38 minutes. When does it arrive?",
        (("A", "12:15"), ("B", "12:25"), ("C", "12:35"), ("D", "13:25")), "B",
        "Two hours after 09:47 is 11:47. Adding 38 minutes gives 12:25.",
    ),
    _question(
        "m55", "Maths", "Mixed numbers", "Work out 2 2/3 − 1 5/6.",
        (("A", "1/2"), ("B", "2/3"), ("C", "5/6"), ("D", "1 1/6")), "C",
        "In sixths, 2 2/3 is 2 4/6. Regrouping gives 1 10/6; subtracting 1 5/6 leaves 5/6.",
    ),
    _question(
        "m56", "Maths", "Volume",
        "A cuboid is 7 cm long, 6 cm wide and 5 cm high. What is its volume?",
        (("A", "18 cm³"), ("B", "42 cm³"),
         ("C", "180 cm³"), ("D", "210 cm³")), "D",
        "Volume = length × width × height, so 7 × 6 × 5 = 210 cm³.",
    ),
    _question(
        "m57", "Maths", "Algebra", "Solve n ÷ 4 + 7 = 15.",
        (("A", "8"), ("B", "22"), ("C", "30"), ("D", "32")), "D",
        "Subtract 7 to get n ÷ 4 = 8. Multiplying by 4 gives n = 32.",
    ),
    _question(
        "m58", "Maths", "Percentages",
        "A bicycle helmet costs £60. Its price increases by 20%. What is the new price?",
        (("A", "£68"), ("B", "£70"), ("C", "£80"), ("D", "£72")), "D",
        "20% of £60 is £12. Adding the increase gives £60 + £12 = £72.",
    ),
    _question(
        "m59", "Maths", "Angles",
        "Three angles in a quadrilateral are 95°, 85° and 110°. What is the fourth angle?",
        (("A", "60°"), ("B", "70°"), ("C", "80°"), ("D", "90°")), "B",
        "Angles in a quadrilateral total 360°. The three angles total 290°, so the fourth is 70°.",
    ),
    _question(
        "m60", "Maths", "Scale",
        "On a map, 1 cm represents 5 km. Two towns are 7.4 cm apart on the map. What is the real distance?",
        (("A", "12.4 km"), ("B", "35 km"), ("C", "42 km"), ("D", "37 km")), "D",
        "Each centimetre represents 5 km, so 7.4 × 5 = 37 km.",
    ),
    _question(
        "m61", "Maths", "Probability",
        "A bag contains 3 red, 5 blue and 2 green counters. What is the probability of choosing a counter that is not blue?",
        (("A", "1/5"), ("B", "3/10"), ("C", "1/2"), ("D", "7/10")), "C",
        "There are 10 counters. Five are not blue, so the probability is 5/10 = 1/2.",
    ),
    _question(
        "m62", "Maths", "Multiples", "What is the lowest common multiple of 8 and 12?",
        (("A", "16"), ("B", "20"), ("C", "48"), ("D", "24")), "D",
        "The first number in both lists of multiples is 24: 8 × 3 = 24 and 12 × 2 = 24.",
    ),
    _question(
        "m63", "Maths", "Perimeter",
        "A rectangle is 12.5 m long and 7.25 m wide. What is its perimeter?",
        (("A", "19.75 m"), ("B", "32.25 m"),
         ("C", "39.5 m"), ("D", "90.625 m")), "C",
        "Perimeter is 2 × (12.5 + 7.25) = 2 × 19.75 = 39.5 m.",
    ),
    _question(
        "m64", "Maths", "Data handling", "What is the median of 4, 7, 7, 9, 12, 15 and 18?",
        (("A", "7"), ("B", "8"), ("C", "12"), ("D", "9")), "D",
        "There are seven ordered values, so the fourth value is the median. The fourth value is 9.",
    ),

    # English: fourth original expansion set
    _question(
        "e49", "English", "Comprehension",
        "Why did Sami avoid restarting the whole projector system?",
        (("A", "It would make the room too bright."),
         ("B", "The manual was missing."),
         ("C", "The audience had already gone home."),
         ("D", "It would erase the timed sequence.")), "D",
        "The passage says that restarting the whole system would erase the carefully timed sequence.",
        context=_PLANETARIUM_PASSAGE,
    ),
    _question(
        "e50", "English", "Comprehension vocabulary",
        "What does flickered mean in the passage?",
        (("A", "grew much larger"), ("B", "made a loud noise"),
         ("C", "shone unsteadily"), ("D", "changed colour permanently")), "C",
        "A light that flickers shines unevenly or goes on and off quickly.",
        context=_PLANETARIUM_PASSAGE,
    ),
    _question(
        "e51", "English", "Inference", "What does Sami's response to the fault suggest?",
        (("A", "He dislikes looking at stars."),
         ("B", "He wants somebody else to run the show."),
         ("C", "He has forgotten when the families arrive."),
         ("D", "He is calm and practical.")), "D",
        "Sami checks the likely cause and fixes only the faulty section instead of panicking.",
        context=_PLANETARIUM_PASSAGE,
    ),
    _question(
        "e52", "English", "Writer's choices",
        "Why does the writer describe Orion as sharp and bright?",
        (("A", "To explain why the cable came loose"),
         ("B", "To suggest that the show was too long"),
         ("C", "To show that the projector repair worked"),
         ("D", "To prove that Orion is the largest constellation")), "C",
        "The clear, bright image confirms that Sami restored the missing constellation.",
        context=_PLANETARIUM_PASSAGE,
    ),
    _question(
        "e53", "English", "Vocabulary", "Which meaning is closest to meticulous?",
        (("A", "quick but careless"), ("B", "noisy and excited"),
         ("C", "ordinary and familiar"), ("D", "very careful and exact")), "D",
        "Someone who is meticulous pays very careful attention to details.",
    ),
    _question(
        "e54", "English", "Punctuation", "Which sentence uses a semicolon correctly?",
        (("A", "The hall; was full and warm."),
         ("B", "We brought; coats, hats and scarves."),
         ("C", "After the show; we walked home."),
         ("D", "The hall was full; every seat was taken.")), "D",
        "A semicolon can join two closely related main clauses: both halves of option A can stand alone.",
    ),
    _question(
        "e55", "English", "Spelling", "Which spelling is correct?",
        (("A", "neccessary"), ("B", "necesary"),
         ("C", "necessary"), ("D", "nessessary")), "C",
        "Necessary is spelt n-e-c-e-s-s-a-r-y.",
    ),
    _question(
        "e56", "English", "Modal verbs",
        "Which sentence uses a modal verb to show that something is possible?",
        (("A", "We visited the observatory yesterday."),
         ("B", "We are inside the observatory."),
         ("C", "We visit the observatory each term."),
         ("D", "We might visit the observatory tomorrow.")), "D",
        "Might is a modal verb that shows possibility.",
    ),
    _question(
        "e57", "English", "Comprehension",
        "Why did Asha choose a wide strip of cloth instead of rope?",
        (("A", "She wanted the pear tree to lie on the ground."),
         ("B", "The cloth would stop the rain completely."),
         ("C", "Tom had hidden every piece of rope."),
         ("D", "The cloth would support the tree without rubbing its bark raw.")), "D",
        "The loose, wide cloth supports the trunk while protecting its bark from damage.",
        context=_ORCHARD_PASSAGE,
    ),
    _question(
        "e58", "English", "Comprehension vocabulary",
        "What does braced mean in the passage?",
        (("A", "painted carefully"), ("B", "supported firmly"),
         ("C", "cut into pieces"), ("D", "watered deeply")), "B",
        "The stakes brace the tree by holding and supporting it firmly.",
        context=_ORCHARD_PASSAGE,
    ),
    _question(
        "e59", "English", "Inference", "What can we infer about Asha?",
        (("A", "She understands that a young tree needs support and room to move."),
         ("B", "She wants to remove every tree from the orchard."),
         ("C", "She is frightened of working with Tom."),
         ("D", "She believes tight rope can never damage bark.")), "A",
        "Asha supports the tree gently and deliberately leaves enough space for movement.",
        context=_ORCHARD_PASSAGE,
    ),
    _question(
        "e60", "English", "Writer's choices",
        "What effect does the phrase rain drummed on the shed roof create?",
        (("A", "It makes the rain seem strong and noisy."),
         ("B", "It shows that musicians were inside the shed."),
         ("C", "It proves that the roof was made of cloth."),
         ("D", "It makes the night seem completely silent.")), "A",
        "Drummed compares the sound of rain to repeated beats, making it feel loud and forceful.",
        context=_ORCHARD_PASSAGE,
    ),
    _question(
        "e61", "English", "Vocabulary", "Which meaning is closest to scarce?",
        (("A", "brightly coloured"), ("B", "in short supply"),
         ("C", "easy to replace"), ("D", "carefully hidden")), "B",
        "Something scarce is limited or difficult to find because there is not much of it.",
    ),
    _question(
        "e62", "English", "Apostrophes",
        "Which sentence shows that the bags belong to several players?",
        (("A", "The player's bags were beside the bench."),
         ("B", "The players bags were beside the bench."),
         ("C", "The players' bags were beside the bench."),
         ("D", "The players's bags were beside the bench.")), "C",
        "For a regular plural noun ending in s, the possessive apostrophe comes after the s: players'.",
    ),
    _question(
        "e63", "English", "Direct speech", "Which sentence is punctuated correctly?",
        (("A", "‘We should leave now,’ said Ravi."),
         ("B", "‘We should leave now’ said Ravi."),
         ("C", "‘We should leave now, said Ravi.’"),
         ("D", "We should leave now,’ said Ravi.")), "A",
        "The spoken words have opening and closing quotation marks, and the reporting clause follows a comma.",
    ),
    _question(
        "e64", "English", "Relative clauses", "Which sentence contains a relative clause?",
        (("A", "Ava rang the red bicycle bell."),
         ("B", "The bicycle that has a red bell belongs to Ava."),
         ("C", "Ava's bicycle bell rang loudly."),
         ("D", "Ring the bicycle bell, Ava.")), "B",
        "That has a red bell is a relative clause giving more information about the bicycle.",
    ),

    # Verbal reasoning: fourth original expansion set
    _question(
        "v49", "Verbal Reasoning", "Letter codes",
        "In a code, every letter moves one place forward in the alphabet. How is LION written?",
        (("A", "MJPO"), ("B", "MIPO"), ("C", "KHMN"), ("D", "NKQP")), "A",
        "L→M, I→J, O→P and N→O, so LION becomes MJPO.",
    ),
    _question(
        "v50", "Verbal Reasoning", "Letter sequences", "What comes next? AZ, BY, CX, DW, …",
        (("A", "EU"), ("B", "EV"), ("C", "FV"), ("D", "EW")), "B",
        "The first letters move forwards A, B, C, D, E while the second move backwards Z, Y, X, W, V.",
    ),
    _question(
        "v51", "Verbal Reasoning", "Analogies", "Gosling is to goose as calf is to …",
        (("A", "cow"), ("B", "duck"), ("C", "goat"), ("D", "sheep")), "A",
        "A gosling is a young goose, and a calf is a young cow.",
    ),
    _question(
        "v52", "Verbal Reasoning", "Odd one out", "Which word is the odd one out?",
        (("A", "triangle"), ("B", "square"), ("C", "pentagon"), ("D", "sphere")), "D",
        "Triangle, square and pentagon are flat shapes. A sphere is a three-dimensional solid.",
    ),
    _question(
        "v53", "Verbal Reasoning", "Word links",
        "Which word can go after NOTE and before MARK to make two new words?",
        (("A", "book"), ("B", "paper"), ("C", "pad"), ("D", "card")), "A",
        "NOTE + BOOK makes notebook, and BOOK + MARK makes bookmark.",
    ),
    _question(
        "v54", "Verbal Reasoning", "Alphabet values",
        "Using A=1, B=2, C=3 and so on, what is the value of BRAVE?",
        (("A", "43"), ("B", "46"), ("C", "48"), ("D", "50")), "C",
        "B=2, R=18, A=1, V=22 and E=5. Their total is 48.",
    ),
    _question(
        "v55", "Verbal Reasoning", "Anagrams", "Which word is an anagram of SILENT?",
        (("A", "LISTEN"), ("B", "LITTLE"), ("C", "LINES"), ("D", "STILL")), "A",
        "LISTEN uses exactly the same six letters as SILENT.",
    ),
    _question(
        "v56", "Verbal Reasoning", "Number sequences", "What is the next number? 4, 10, 22, 46, …",
        (("A", "70"), ("B", "82"), ("C", "92"), ("D", "94")), "D",
        "Each number is doubled and then 2 is added. 46 × 2 + 2 = 94.",
    ),
    _question(
        "v57", "Verbal Reasoning", "Letter relationships",
        "BF becomes EI by moving each letter three places forward. What does HQ become?",
        (("A", "JS"), ("B", "KT"), ("C", "KU"), ("D", "LT")), "B",
        "H moves to K and Q moves to T, so HQ becomes KT.",
    ),
    _question(
        "v58", "Verbal Reasoning", "Word relationships", "Which pair has a different relationship?",
        (("A", "kitten : cat"), ("B", "calf : cow"),
         ("C", "foal : horse"), ("D", "cub : den")), "D",
        "The first three pairs link a young animal to its adult form. A den is a home, not an adult animal.",
    ),
    _question(
        "v59", "Verbal Reasoning", "Logic",
        "All daxes are blue. Every blue thing is cold. No cold thing is soft. Which statement must be true?",
        (("A", "All soft things are daxes."), ("B", "Some daxes are soft."),
         ("C", "No daxes are soft."), ("D", "Every cold thing is a dax.")), "C",
        "Every dax is blue and therefore cold. Because no cold thing is soft, no dax can be soft.",
    ),
    _question(
        "v60", "Verbal Reasoning", "Missing letters",
        "The same two letters complete both words: B __ D and H __ D. Which letters are they?",
        (("A", "AN"), ("B", "EN"), ("C", "OL"), ("D", "UR")), "A",
        "AN makes B + AN + D = BAND and H + AN + D = HAND.",
    ),
    _question(
        "v61", "Verbal Reasoning", "Word links",
        "Which word can go after FOOT and before ROOM to make two new words?",
        (("A", "step"), ("B", "ball"), ("C", "rest"), ("D", "print")), "B",
        "FOOT + BALL makes football, and BALL + ROOM makes ballroom.",
    ),
    _question(
        "v62", "Verbal Reasoning", "Alphabetical order",
        "If these words are put in alphabetical order, which comes third? place, plain, planet, plaque",
        (("A", "place"), ("B", "plain"), ("C", "planet"), ("D", "plaque")), "C",
        "The order is place, plain, planet, plaque, so planet is third.",
    ),
    _question(
        "v63", "Verbal Reasoning", "Letter codes",
        "In a mirror-alphabet code A becomes Z, B becomes Y, and so on. How is FISH written?",
        (("A", "TRHS"), ("B", "UQIT"), ("C", "URHS"), ("D", "VSHR")), "C",
        "F becomes U, I becomes R, S becomes H and H becomes S, giving URHS.",
    ),
    _question(
        "v64", "Verbal Reasoning", "Analogies", "Author is to novel as composer is to …",
        (("A", "symphony"), ("B", "gallery"), ("C", "sculpture"), ("D", "camera")), "A",
        "An author creates a novel, and a composer creates a symphony.",
    ),

    # Non-verbal and spatial reasoning: fourth original expansion set
    _question(
        "n49", "Non-Verbal Reasoning", "Rotation", "An arrow turns 90° clockwise each time: ↑, →, ↓, …",
        (("A", "←"), ("B", "↖"), ("C", "↑"), ("D", "↘")), "A",
        "One more quarter-turn clockwise from down makes the arrow point left.",
    ),
    _question(
        "n50", "Non-Verbal Reasoning", "Position sequences",
        "The filled circle moves two places to the right each time: ●○○○○, ○○●○○, ○○○○●, ○●○○○, … What comes next?",
        (("A", "●○○○○"), ("B", "○○●○○"),
         ("C", "○○○●○"), ("D", "○○○○●")), "C",
        "The positions are first, third, fifth, second and then fourth, so ○○○●○ comes next.",
    ),
    _question(
        "n51", "Non-Verbal Reasoning", "Shape properties",
        "The shapes have 3 sides, then 5 sides, then 7 sides. How many sides should the next shape have?",
        (("A", "8"), ("B", "9"), ("C", "10"), ("D", "11")), "B",
        "The number of sides increases by two each time: 3, 5, 7, 9.",
    ),
    _question(
        "n52", "Non-Verbal Reasoning", "Matrices",
        "Across each row, two shapes exchange positions and become filled. Top row: ○□ becomes ■●. Bottom row: △◇ becomes ?",
        (("A", "▲◆"), ("B", "◆▲"), ("C", "◇△"), ("D", "■●")), "B",
        "The diamond moves first and the triangle second, and both become filled: ◆▲.",
    ),
    _question(
        "n53", "Non-Verbal Reasoning", "Reflection",
        "A horizontal mirror reflection changes ↘ into which arrow?",
        (("A", "↗"), ("B", "↖"), ("C", "↘"), ("D", "↙")), "A",
        "A horizontal mirror reverses up and down but keeps left and right, so down-right becomes up-right.",
    ),
    _question(
        "n54", "Non-Verbal Reasoning", "Repeating groups", "What comes next? ○, ○○○, ■, ■■■, ▲, …",
        (("A", "▲▲"), ("B", "▲▲▲"), ("C", "■■■"), ("D", "○○○")), "B",
        "Each shape appears once and then three times, so the single triangle is followed by three triangles.",
    ),
    _question(
        "n55", "Non-Verbal Reasoning", "Two-rule patterns", "What comes next? △↑, □→, △↓, □←, …",
        (("A", "△↑"), ("B", "□↑"), ("C", "△→"), ("D", "□↓")), "A",
        "The shapes alternate while the arrow turns 90° clockwise, returning to △↑.",
    ),
    _question(
        "n56", "Non-Verbal Reasoning", "Symmetry", "Which shape has exactly two lines of symmetry?",
        (("A", "a square"), ("B", "a non-square rectangle"),
         ("C", "an equilateral triangle"), ("D", "a circle")), "B",
        "A non-square rectangle has one horizontal and one vertical line of symmetry.",
    ),
    _question(
        "n57", "Non-Verbal Reasoning", "Cubes",
        "On a cube, M is opposite P, N is opposite Q, and O is opposite R. Which face is opposite O?",
        (("A", "M"), ("B", "N"), ("C", "P"), ("D", "R")), "D",
        "The information states that O and R are opposite faces.",
    ),
    _question(
        "n58", "Non-Verbal Reasoning", "Rotation",
        "An arrow turns 45° anticlockwise each time: →, ↗, ↑, ↖, …",
        (("A", "←"), ("B", "↙"), ("C", "↓"), ("D", "↘")), "A",
        "One more 45° anticlockwise turn from up-left makes the arrow point left.",
    ),
    _question(
        "n59", "Non-Verbal Reasoning", "Matrices",
        "Across each row, two matching shapes are added. Top row: ▲ becomes ▲▲▲. Bottom row: ●●●● becomes ?",
        (("A", "●●●●●"), ("B", "●●●●●●"),
         ("C", "▲▲▲▲▲▲"), ("D", "●●")), "B",
        "The rule adds two matching shapes, so four circles become six circles.",
    ),
    _question(
        "n60", "Non-Verbal Reasoning", "Two-rule patterns", "What comes next? ●, □□, ●●●, □□□□, …",
        (("A", "●●●●"), ("B", "●●●●●"),
         ("C", "□□□□□"), ("D", "□□□□□□")), "B",
        "The count rises by one while filled circles and hollow squares alternate. Next are five filled circles.",
    ),
    _question(
        "n61", "Non-Verbal Reasoning", "Transformations",
        "The rule changes ○↑ into ●↓. Using the same rule, what does □← become?",
        (("A", "■→"), ("B", "□→"), ("C", "■↑"), ("D", "□↓")), "A",
        "The shape becomes filled and the arrow turns 180°, so □← becomes ■→.",
    ),
    _question(
        "n62", "Non-Verbal Reasoning", "Position changes",
        "A dot moves clockwise around the middle of each edge: top, right, bottom, left, … Where is it next?",
        (("A", "top"), ("B", "right"), ("C", "bottom"), ("D", "centre")), "A",
        "The dot has completed a circuit of the four edges, so it returns to the top.",
    ),
    _question(
        "n63", "Non-Verbal Reasoning", "Spatial reasoning",
        "A sheet is folded exactly in half four times. How many layers are there?",
        (("A", "8"), ("B", "12"), ("C", "16"), ("D", "20")), "C",
        "Each fold doubles the layers: 1, 2, 4, 8, then 16.",
    ),
    _question(
        "n64", "Non-Verbal Reasoning", "Rotation",
        "An arrow points up. It turns 270° clockwise. Which way does it point?",
        (("A", "right"), ("B", "down"), ("C", "left"), ("D", "up")), "C",
        "A 270° clockwise turn is the same as a 90° anticlockwise turn, so up becomes left.",
    ),
])


SCHOOL_TARGET_QUESTIONS = [
    _question(
        "fsce01", "Art & Design", "Shading",
        "Which drawing technique is most useful for making a round apple look three-dimensional?",
        (("A", "Drawing a square border"), ("B", "Changing gradually from light to dark"),
         ("C", "Writing the colour names"), ("D", "Using only straight lines")), "B",
        "Gradual light and dark shading shows where light falls and helps a flat drawing look solid.",
    ),
    _question(
        "fsce02", "Art & Design", "Colour mixing",
        "Which colour is made by mixing blue and yellow paint?",
        (("A", "Orange"), ("B", "Purple"), ("C", "Green"), ("D", "Brown")), "C",
        "Blue and yellow are primary colours that mix to make green.",
    ),
    _question(
        "fsce03", "Computing", "Algorithms",
        "What is the computing name for a clear sequence of steps used to complete a task?",
        (("A", "An algorithm"), ("B", "A password"), ("C", "A pixel"), ("D", "A folder")), "A",
        "An algorithm is an ordered set of instructions for solving a problem or completing a task.",
    ),
    _question(
        "fsce04", "Computing", "Repetition",
        "A sprite must move forward and turn right four times to draw a square. Which coding tool is most helpful?",
        (("A", "A sound block"), ("B", "A variable called name"),
         ("C", "A stop button"), ("D", "A repeat loop")), "D",
        "A repeat loop runs the same move-and-turn instructions four times without rewriting them.",
    ),
    _question(
        "fsce05", "Design & Technology", "Prototypes",
        "Why might a designer build a simple cardboard model before making the final product?",
        (("A", "To make the final product heavier"), ("B", "To avoid measuring anything"),
         ("C", "To test and improve the idea"), ("D", "To hide the design")), "C",
        "A prototype lets a designer test how an idea works and improve it before making the final version.",
    ),
    _question(
        "fsce06", "Design & Technology", "Structures",
        "Which shape is often added to a bridge frame because it helps the frame stay rigid?",
        (("A", "Oval"), ("B", "Triangle"), ("C", "Spiral"), ("D", "Semicircle")), "B",
        "Triangles keep their shape when forces push or pull on a frame, so they add strength.",
    ),
    _question(
        "fsce07", "English", "Writing for an audience",
        "Which feature would best help Year 2 pupils follow instructions for planting a seed?",
        (("A", "Short numbered steps"), ("B", "A long mystery opening"),
         ("C", "Several difficult quotations"), ("D", "A surprise ending")), "A",
        "Short numbered steps put the actions in a clear order for younger readers.",
    ),
    _question(
        "fsce08", "English", "Inference",
        "Nia checked the dark clouds, zipped her coat and tucked the picnic blanket back into the cupboard. What is she most likely thinking?",
        (("A", "The cupboard is too full"), ("B", "The blanket is brand new"),
         ("C", "The coat is too warm"), ("D", "Rain may spoil the picnic")), "D",
        "The dark clouds, coat and stored blanket suggest that Nia expects rain and may cancel the picnic.",
    ),
    _question(
        "fsce09", "Geography", "Map scale",
        "On a map, 1 cm represents 2 km. Two villages are 3.5 cm apart on the map. How far apart are they?",
        (("A", "5 km"), ("B", "6 km"), ("C", "7 km"), ("D", "8 km")), "C",
        "Each centimetre represents 2 km, so 3.5 × 2 = 7 km.",
    ),
    _question(
        "fsce10", "Geography", "Water cycle",
        "Which process changes liquid water at the sea surface into water vapour in the air?",
        (("A", "Freezing"), ("B", "Evaporation"), ("C", "Precipitation"), ("D", "Collection")), "B",
        "Evaporation happens when liquid water gains heat energy and becomes water vapour.",
    ),
    _question(
        "fsce11", "History", "Historical sources",
        "Which item is a primary source for learning about a nurse's work during the First World War?",
        (("A", "Her diary written in 1916"), ("B", "A modern novel set in 1916"),
         ("C", "A website summary written this year"), ("D", "A new costume made for a play")), "A",
        "A diary written by the nurse at the time is direct evidence from the period being studied.",
    ),
    _question(
        "fsce12", "History", "Chronology",
        "Which event happened earliest?",
        (("A", "The Norman Conquest in 1066"), ("B", "The Great Fire of London in 1666"),
         ("C", "The first Moon landing in 1969"), ("D", "The Roman invasion of Britain in AD 43")), "D",
        "AD 43 comes before 1066, 1666 and 1969, so the Roman invasion is the earliest event.",
    ),
    _question(
        "fsce13", "Languages", "Using context",
        "A sign says 'biblioteca' beside a picture of shelves full of books. What place does the word most likely mean?",
        (("A", "Swimming pool"), ("B", "Train station"), ("C", "Library"), ("D", "Bakery")), "C",
        "The book shelves give a strong context clue that 'biblioteca' means library.",
    ),
    _question(
        "fsce14", "Languages", "Reading strategies",
        "When you meet one unknown word in a short passage in another language, what should you try first?",
        (("A", "Ignore every other word"), ("B", "Use nearby words, pictures and familiar patterns"),
         ("C", "Change the word into a number"), ("D", "Read only the final letter")), "B",
        "Context, pictures and familiar word patterns can help you infer an unknown word's meaning.",
    ),
    _question(
        "fsce15", "Maths", "Fractions",
        "A club has 64 badges. Three eighths are blue. How many badges are blue?",
        (("A", "8"), ("B", "16"), ("C", "21"), ("D", "24")), "D",
        "One eighth of 64 is 8, so three eighths is 3 × 8 = 24.",
    ),
    _question(
        "fsce16", "Maths", "Perimeter",
        "A rectangular garden is 12 m long and 7 m wide. What is its perimeter?",
        (("A", "38 m"), ("B", "19 m"), ("C", "48 m"), ("D", "84 m")), "A",
        "Perimeter = 12 + 7 + 12 + 7 = 38 m.",
    ),
    _question(
        "fsce17", "Music", "Dynamics",
        "Which musical feature tells a performer whether to play loudly or quietly?",
        (("A", "Pitch"), ("B", "Dynamics"), ("C", "Tempo"), ("D", "Pulse")), "B",
        "Dynamics describe how loud or quiet music should be played.",
    ),
    _question(
        "fsce18", "Music", "Pitch",
        "A piccolo usually makes a higher sound than a tuba. Which property is being compared?",
        (("A", "Duration"), ("B", "Volume"), ("C", "Pitch"), ("D", "Rhythm")), "C",
        "Pitch describes how high or low a sound is.",
    ),
    _question(
        "fsce19", "Physical Education", "Warm-ups",
        "Why is a gentle warm-up useful before vigorous exercise?",
        (("A", "It removes the need to drink water"), ("B", "It makes every game shorter"),
         ("C", "It guarantees that a team wins"), ("D", "It gradually prepares muscles and the heart")), "D",
        "A warm-up gradually raises the heart rate and prepares muscles and joints for harder movement.",
    ),
    _question(
        "fsce20", "Physical Education", "Teamwork",
        "In a passing game, what is the best way for a player without the ball to help the team?",
        (("A", "Move into a clear space"), ("B", "Stand behind an opponent"),
         ("C", "Leave the playing area"), ("D", "Keep both eyes closed")), "A",
        "Moving into space gives the player with the ball a safe passing option.",
    ),
    _question(
        "fsce21", "Science", "Electricity",
        "A bulb, cell and wires are connected, but the switch is open. Why does the bulb stay off?",
        (("A", "The bulb has too much light"), ("B", "The wires are magnetic"),
         ("C", "The circuit is incomplete"), ("D", "The cell has become a motor")), "C",
        "An open switch breaks the circuit, so electric current cannot flow through the bulb.",
    ),
    _question(
        "fsce22", "Science", "Light and shadows",
        "Why is a person's outdoor shadow often shorter around midday than early in the morning?",
        (("A", "The person becomes shorter"), ("B", "The Sun is higher in the sky"),
         ("C", "The ground stops reflecting light"), ("D", "The Earth stops turning")), "B",
        "When the Sun is higher, its light reaches the ground at a steeper angle and makes shorter shadows.",
    ),
]

ADDITIONAL_QUESTIONS.extend(SCHOOL_TARGET_QUESTIONS)


ADDITIONAL_EXAMS: Dict[str, Dict[str, Any]] = {
    "newstead-wood-11plus-1": {
        "id": "newstead-wood-11plus-1",
        "category": "school_target",
        "title": "Newstead Wood School 11+ Target Mock",
        "description": "Original Verbal and Non-Verbal Reasoning practice aligned with Newstead Wood School's publicly published Year 7 selection-test format.",
        "school": "Newstead Wood School",
        "stage": "Year 7 Selection Test",
        "duration_minutes": 90,
        "is_free": False,
        "question_ids": tuple([f"v{i:02d}" for i in range(33, 57)] + [f"n{i:02d}" for i in range(33, 57)]),
        "source_ids": ("dfe-primary", "newstead-wood-2027", "gl-11plus-free-materials"),
        "format_note": "Two-part multiple-choice practice: 45 minutes of Verbal Reasoning followed by 45 minutes of Non-Verbal Reasoning. Newstead Wood states that its selection test assesses only Verbal and Non-Verbal Reasoning; this is an original independent practice simulation, not an official school paper.",
        "last_verified": "2026-09-02",
    },
    "nlcs-11plus-1": {
        "id": "nlcs-11plus-1",
        "category": "school_target",
        "title": "North London Collegiate School 11+ Target Mock",
        "description": "Original English and Maths practice aligned with NLCS's publicly published 11+ sample-paper scope.",
        "school": "North London Collegiate School",
        "stage": "11+ Year 7 entrance exam",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple([f"e{i:02d}" for i in range(17, 29)] + [f"m{i:02d}" for i in range(17, 29)]),
        "source_ids": ("top100-alevel-2025", "nlcs-11plus-2027"),
        "format_note": "Shortened English and Maths practice. NLCS publishes Maths and English sample papers; this is an original practice mock, not an official paper.",
        "last_verified": "2026-08-11",
    },
    "clsg-11plus-1": {
        "id": "clsg-11plus-1",
        "category": "school_target",
        "title": "City of London School for Girls 11+ Target Mock",
        "description": "Original English, Maths and reasoning practice based on CLSG's publicly described CEM familiarisation and sample-paper material.",
        "school": "City of London School for Girls",
        "stage": "11+ entrance assessment",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple([f"e{i:02d}" for i in range(25, 33)] + [f"m{i:02d}" for i in range(25, 33)] + [f"v{i:02d}" for i in range(25, 29)] + [f"n{i:02d}" for i in range(25, 29)]),
        "source_ids": ("top100-alevel-2025", "clsg-11plus-2027"),
        "format_note": "Shortened practice combining English, Maths and reasoning. CLSG publishes CEM familiarisation plus Maths and English sample papers; this mock is original.",
        "last_verified": "2026-08-11",
    },
    "highgate-11plus-1": {
        "id": "highgate-11plus-1",
        "category": "school_target",
        "title": "Highgate School 11+ Target Mock",
        "description": "Original English and Mathematics practice aligned with Highgate's published 11+ sample tests.",
        "school": "Highgate School",
        "stage": "11+ entrance exams",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple([f"e{i:02d}" for i in range(49, 61)] + [f"m{i:02d}" for i in range(49, 61)]),
        "source_ids": ("top100-alevel-2025", "highgate-11plus-2027"),
        "format_note": "Shortened English and Maths practice. Highgate publicly provides English and Maths sample papers; this mock uses original questions.",
        "last_verified": "2026-08-11",
    },
    "kehs-11plus-1": {
        "id": "kehs-11plus-1",
        "category": "school_target",
        "title": "King Edward VI High School for Girls 11+ Target Mock",
        "description": "Original English and Maths practice aligned with KEHS's publicly available specimen material.",
        "school": "King Edward VI High School for Girls",
        "stage": "11+ entrance exam",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple([f"e{i:02d}" for i in range(31, 43)] + [f"m{i:02d}" for i in range(31, 43)]),
        "source_ids": ("top100-alevel-2025", "kehs-11plus-2027"),
        "format_note": "Shortened English and Maths practice. KEHS publishes English poetry/prose and Maths specimen material; this mock is original.",
        "last_verified": "2026-08-11",
    },
    "wimbledon-high-11plus-1": {
        "id": "wimbledon-high-11plus-1",
        "category": "school_target",
        "title": "Wimbledon High School 11+ Target Mock",
        "description": "Original Verbal and Non-Verbal Reasoning practice aligned with Wimbledon High's published first-stage assessment scope.",
        "school": "Wimbledon High School",
        "stage": "11+ First Stage",
        "duration_minutes": 40,
        "is_free": False,
        "question_ids": tuple([f"v{i:02d}" for i in range(33, 45)] + [f"n{i:02d}" for i in range(33, 45)]),
        "source_ids": ("top100-alevel-2025", "wimbledon-high-11plus-2027"),
        "format_note": "Shortened original VR and NVR practice. Wimbledon High publicly states that its first stage tests Verbal and Non-Verbal Reasoning; the creative second stage is not scored here.",
        "last_verified": "2026-08-11",
    },
    "putney-high-11plus-1": {
        "id": "putney-high-11plus-1",
        "category": "school_target",
        "title": "Putney High School 11+ Target Mock",
        "description": "Original Maths and English practice aligned with Putney High's publicly described first-stage digital assessment.",
        "school": "Putney High School",
        "stage": "11+ First Stage",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple([f"e{i:02d}" for i in range(53, 65)] + [f"m{i:02d}" for i in range(53, 65)]),
        "source_ids": ("top100-alevel-2025", "putney-high-11plus-2027"),
        "format_note": "Shortened original Maths and English practice. Putney High publicly describes a first-stage digital assessment in Maths and English; the creative Athena Assessment is not scored here.",
        "last_verified": "2026-08-11",
    },
    "brighton-college-11plus-1": {
        "id": "brighton-college-11plus-1",
        "category": "school_target",
        "title": "Brighton College 11+ Target Mock",
        "description": "Original English and Mathematics practice aligned with Brighton College's publicly stated 11+ assessment subjects.",
        "school": "Brighton College",
        "stage": "11+ Year 7 assessment",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple([f"e{i:02d}" for i in range(7, 19)] + [f"m{i:02d}" for i in range(7, 19)]),
        "source_ids": ("top100-alevel-2025", "brighton-11plus-2027"),
        "format_note": "Shortened English and Maths practice. Brighton College publicly states that 11+ candidates sit assessments in English and Mathematics; this mock is original.",
        "last_verified": "2026-08-11",
    },
    "habs-boys-11plus-1": {
        "id": "habs-boys-11plus-1",
        "category": "school_target",
        "title": "Haberdashers' Boys' School 11+ Target Mock",
        "description": "Original reasoning, English and Maths practice aligned with the publicly published Habs 11+ assessment scope.",
        "school": "Haberdashers' Boys' School",
        "stage": "11+ entrance examination",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple([f"e{i:02d}" for i in range(19, 27)] + [f"m{i:02d}" for i in range(19, 27)] + [f"v{i:02d}" for i in range(25, 29)] + [f"n{i:02d}" for i in range(25, 29)]),
        "source_ids": ("top100-alevel-2025", "habs-11plus-2027"),
        "format_note": "Shortened original practice covering verbal/non-verbal reasoning, puzzles/problem solving, English and Maths. The official exam also includes creative writing, which is not auto-scored here.",
        "last_verified": "2026-08-11",
    },
    "habs-girls-11plus-1": {
        "id": "habs-girls-11plus-1",
        "category": "school_target",
        "title": "Haberdashers' Girls' School 11+ Target Mock",
        "description": "Original reasoning, English and Maths practice aligned with the publicly published Habs 11+ assessment scope.",
        "school": "Haberdashers' Girls' School",
        "stage": "11+ entrance examination",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple([f"e{i:02d}" for i in range(31, 39)] + [f"m{i:02d}" for i in range(31, 39)] + [f"v{i:02d}" for i in range(33, 37)] + [f"n{i:02d}" for i in range(33, 37)]),
        "source_ids": ("top100-alevel-2025", "habs-11plus-2027"),
        "format_note": "Shortened original practice covering verbal/non-verbal reasoning, puzzles/problem solving, English and Maths. The official exam also includes creative writing, which is not auto-scored here.",
        "last_verified": "2026-08-11",
    },
    "common-full-3": {
        "id": "common-full-3",
        "category": "common",
        "title": "Common Four-Subject Mock C",
        "description": "A fresh timed paper with 32 original questions across all four core 11+ subjects.",
        "school": None,
        "stage": "Full practice",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(17, 25)]
            + [f"e{i:02d}" for i in range(17, 25)]
            + [f"v{i:02d}" for i in range(17, 25)]
            + [f"n{i:02d}" for i in range(17, 25)]
        ),
        "source_ids": ("dfe-primary", "common-four-subject"),
        "format_note": "Four multiple-choice sections in one timed sitting.",
        "last_verified": "2026-08-06",
    },
    "common-full-4": {
        "id": "common-full-4",
        "category": "common",
        "title": "Common Four-Subject Mock D",
        "description": "A fourth full practice paper with a completely different set of original questions.",
        "school": None,
        "stage": "Full practice",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(25, 33)]
            + [f"e{i:02d}" for i in range(25, 33)]
            + [f"v{i:02d}" for i in range(25, 33)]
            + [f"n{i:02d}" for i in range(25, 33)]
        ),
        "source_ids": ("dfe-primary", "common-four-subject"),
        "format_note": "Four multiple-choice sections in one timed sitting.",
        "last_verified": "2026-08-06",
    },
    "buckinghamshire-transfer-1": {
        "id": "buckinghamshire-transfer-1",
        "category": "school_target",
        "title": "Buckinghamshire Transfer Test Target Mock",
        "description": "Original verbal, mathematical and non-verbal practice balanced to the council's published weighting.",
        "school": "Buckinghamshire grammar schools",
        "stage": "Secondary Transfer Test",
        "duration_minutes": 50,
        "is_free": False,
        "question_ids": tuple(
            [f"e{i:02d}" for i in range(17, 25)]
            + [f"v{i:02d}" for i in range(25, 33)]
            + [f"m{i:02d}" for i in range(17, 25)]
            + [f"n{i:02d}" for i in range(25, 33)]
        ),
        "source_ids": ("dfe-primary", "bucks-transfer-2027"),
        "format_note": "Condensed 50:25:25 verbal, maths and non-verbal mix; the official test has two papers.",
        "last_verified": "2026-08-06",
    },
    "kent-test-1": {
        "id": "kent-test-1",
        "category": "school_target",
        "title": "Kent Test Target Mock",
        "description": "Original English, Maths, Verbal and Non-Verbal Reasoning practice for the published Kent Test scope.",
        "school": "Kent grammar schools",
        "stage": "Kent Test",
        "duration_minutes": 50,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(25, 33)]
            + [f"e{i:02d}" for i in range(25, 33)]
            + [f"v{i:02d}" for i in range(17, 25)]
            + [f"n{i:02d}" for i in range(17, 25)]
        ),
        "source_ids": ("dfe-primary", "kent-test-2027"),
        "format_note": "Condensed multiple-choice practice; the official writing exercise is not included.",
        "last_verified": "2026-08-06",
    },
    "sutton-set-1": {
        "id": "sutton-set-1",
        "category": "school_target",
        "title": "Sutton SET Target Mock",
        "description": "Original English and Maths multiple-choice practice for the shared Selective Eligibility Test.",
        "school": "Sutton selective schools",
        "stage": "Selective Eligibility Test",
        "duration_minutes": 40,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(19, 31)]
            + [f"e{i:02d}" for i in range(19, 31)]
        ),
        "source_ids": ("dfe-primary", "sutton-set-2027"),
        "format_note": "Shortened English and Maths multiple-choice practice; the official SET uses separate papers.",
        "last_verified": "2026-08-06",
    },
    "common-full-5": {
        "id": "common-full-5",
        "category": "common",
        "title": "Common Four-Subject Mock E",
        "description": "A fifth full paper with 32 new questions across the four common 11+ subjects.",
        "school": None,
        "stage": "Full practice",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(33, 41)]
            + [f"e{i:02d}" for i in range(33, 41)]
            + [f"v{i:02d}" for i in range(33, 41)]
            + [f"n{i:02d}" for i in range(33, 41)]
        ),
        "source_ids": ("dfe-primary", "common-four-subject"),
        "format_note": "Four multiple-choice sections in one timed sitting.",
        "last_verified": "2026-08-06",
    },
    "common-full-6": {
        "id": "common-full-6",
        "category": "common",
        "title": "Common Four-Subject Mock F",
        "description": "A sixth full paper with another completely different set of original questions.",
        "school": None,
        "stage": "Full practice",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(41, 49)]
            + [f"e{i:02d}" for i in range(41, 49)]
            + [f"v{i:02d}" for i in range(41, 49)]
            + [f"n{i:02d}" for i in range(41, 49)]
        ),
        "source_ids": ("dfe-primary", "common-four-subject"),
        "format_note": "Four multiple-choice sections in one timed sitting.",
        "last_verified": "2026-08-06",
    },
    "common-full-7": {
        "id": "common-full-7",
        "category": "common",
        "title": "Common Four-Subject Mock G",
        "description": "A seventh full paper with 32 new questions across the four common 11+ subjects.",
        "school": None,
        "stage": "Full practice",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(49, 57)]
            + [f"e{i:02d}" for i in range(49, 57)]
            + [f"v{i:02d}" for i in range(49, 57)]
            + [f"n{i:02d}" for i in range(49, 57)]
        ),
        "source_ids": ("dfe-primary", "common-four-subject"),
        "format_note": "Four multiple-choice sections in one timed sitting.",
        "last_verified": "2026-08-09",
    },
    "common-full-8": {
        "id": "common-full-8",
        "category": "common",
        "title": "Common Four-Subject Mock H",
        "description": "An eighth full paper with another completely different set of original questions.",
        "school": None,
        "stage": "Full practice",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(57, 65)]
            + [f"e{i:02d}" for i in range(57, 65)]
            + [f"v{i:02d}" for i in range(57, 65)]
            + [f"n{i:02d}" for i in range(57, 65)]
        ),
        "source_ids": ("dfe-primary", "common-four-subject"),
        "format_note": "Four multiple-choice sections in one timed sitting.",
        "last_verified": "2026-08-09",
    },
    "west-midlands-grammar-1": {
        "id": "west-midlands-grammar-1",
        "category": "school_target",
        "title": "West Midlands Grammar Schools Target Mock",
        "description": "Original English, verbal, mathematical and spatial practice balanced to the partnership's published weighting.",
        "school": "West Midlands Grammar Schools partnership",
        "stage": "Entrance Test",
        "duration_minutes": 50,
        "is_free": False,
        "question_ids": tuple(
            [f"e{i:02d}" for i in range(33, 41)]
            + [f"v{i:02d}" for i in range(41, 49)]
            + [f"m{i:02d}" for i in range(33, 41)]
            + [f"n{i:02d}" for i in range(41, 49)]
        ),
        "source_ids": ("dfe-primary", "west-midlands-2027"),
        "format_note": "Condensed 50:25:25 verbal, maths and non-verbal/spatial mix; the official test has two papers.",
        "last_verified": "2026-08-06",
    },
    "essex-csse-11plus-2": {
        "id": "essex-csse-11plus-2",
        "category": "school_target",
        "title": "Essex 11+ Mock Exam — CSSE Practice 2",
        "description": "Original Essex 11 plus mock exam practice in the CSSE English and Mathematics format, with a fresh question mix for repeat practice.",
        "school": "Consortium of Selective Schools in Essex",
        "stage": "CSSE 11+ Examination",
        "duration_minutes": 50,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(49, 61)]
            + [f"e{i:02d}" for i in range(37, 49)]
        ),
        "source_ids": ("dfe-primary", "csse-2027", "essex-grammar-2027"),
        "format_note": "Original English and Mathematics practice shaped around the current CSSE two-paper format; the official CSSE examination uses separate 60-minute English and Mathematics tests.",
        "last_verified": "2026-08-20",
    },
    "essex-csse-11plus-3": {
        "id": "essex-csse-11plus-3",
        "category": "school_target",
        "title": "Essex 11+ Mock Exam — CSSE Practice 3",
        "description": "Another original 11 plus mock exam for Essex CSSE preparation, focusing on English reading and writing skills plus non-calculator Mathematics.",
        "school": "Consortium of Selective Schools in Essex",
        "stage": "CSSE 11+ Examination",
        "duration_minutes": 50,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(53, 65)]
            + [f"e{i:02d}" for i in range(41, 53)]
        ),
        "source_ids": ("dfe-primary", "csse-2027", "essex-grammar-2027"),
        "format_note": "Original English and Mathematics practice based on the published CSSE scope. It is an independent simulation, not an official CSSE paper.",
        "last_verified": "2026-08-20",
    },
    "colchester-essex-11plus-1": {
        "id": "colchester-essex-11plus-1",
        "category": "school_target",
        "title": "Colchester Essex 11+ Mock Exam — CSSE Target",
        "description": "Original 11 plus mock exam practice for families targeting Colchester Royal Grammar School or Colchester County High School for Girls through the CSSE test.",
        "school": "Colchester Royal Grammar School / Colchester County High School for Girls",
        "stage": "CSSE 11+ Examination",
        "duration_minutes": 50,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(37, 49)]
            + [f"e{i:02d}" for i in range(53, 65)]
        ),
        "source_ids": ("dfe-primary", "csse-2027", "essex-grammar-2027"),
        "format_note": "Colchester-targeted independent practice using the shared CSSE English and Mathematics entrance-test format. It is not an official school paper.",
        "last_verified": "2026-08-20",
    },
    "southend-westcliff-essex-11plus-1": {
        "id": "southend-westcliff-essex-11plus-1",
        "category": "school_target",
        "title": "Southend & Westcliff Essex 11+ Mock Exam — CSSE Target",
        "description": "Original 11 plus mock exam practice for Southend and Westcliff selective schools using the common CSSE English and Mathematics format.",
        "school": "Southend and Westcliff CSSE schools",
        "stage": "CSSE 11+ Examination",
        "duration_minutes": 50,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(41, 53)]
            + [f"e{i:02d}" for i in range(49, 61)]
        ),
        "source_ids": ("dfe-primary", "csse-2027", "essex-grammar-2027"),
        "format_note": "Southend and Westcliff-targeted independent practice based on the shared CSSE English and Mathematics format used by member schools.",
        "last_verified": "2026-08-20",
    },
    "chelmsford-essex-11plus-2": {
        "id": "chelmsford-essex-11plus-2",
        "category": "school_target",
        "title": "Chelmsford Essex 11+ Mock Exam — CCHS FSCE Practice 2",
        "description": "Original Chelmsford County High School for Girls 11 plus mock exam practice, extending the existing CCHS FSCE target mock with another question mix.",
        "school": "Chelmsford County High School for Girls",
        "stage": "FSCE Entrance Test familiarisation",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple(
            [f"fsce{i:02d}" for i in range(2, 8)]
            + [f"fsce{i:02d}" for i in range(9, 15)]
            + [f"fsce{i:02d}" for i in range(16, 23)]
            + ["e55", "e56", "e61", "e62"]
            + ["m54", "m56", "m59", "m61"]
        ),
        "source_ids": ("dfe-primary", "cchs-fsce-2027", "essex-grammar-2027"),
        "format_note": "Independent CCHS/FSCE practice using publicly described mixed-subject familiarisation material; the official assessment may use other answer formats and creative work.",
        "last_verified": "2026-08-20",
    },
    "csse-essex-1": {
        "id": "csse-essex-1",
        "category": "school_target",
        "title": "Essex 11+ Mock Exam — CSSE Practice 1",
        "description": "Original English and Mathematics practice for the Consortium of Selective Schools in Essex scope.",
        "school": "CSSE selective schools in Essex",
        "stage": "CSSE 11+ Examination",
        "duration_minutes": 50,
        "is_free": False,
        "question_ids": tuple(
            [f"m{i:02d}" for i in range(35, 47)]
            + [f"e{i:02d}" for i in range(35, 47)]
        ),
        "source_ids": ("dfe-primary", "csse-2027"),
        "format_note": "Shortened English and Maths practice; the official examination uses two separate 60-minute tests.",
        "last_verified": "2026-08-06",
    },
    "lancaster-royal-grammar-1": {
        "id": "lancaster-royal-grammar-1",
        "category": "school_target",
        "title": "Lancaster Royal Grammar Target Mock",
        "description": "Original English, Mathematics and Verbal Reasoning practice with no Non-Verbal Reasoning section.",
        "school": "Lancaster Royal Grammar School",
        "stage": "11+ Entrance Tests",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple(
            [f"e{i:02d}" for i in range(41, 49)]
            + [f"m{i:02d}" for i in range(33, 41)]
            + [f"v{i:02d}" for i in range(33, 41)]
        ),
        "source_ids": ("dfe-primary", "lrgs-2027"),
        "format_note": "Shortened three-subject practice; the school states that its test does not use Non-Verbal Reasoning.",
        "last_verified": "2026-08-06",
    },
    "bexley-selection-1": {
        "id": "bexley-selection-1",
        "category": "school_target",
        "title": "Bexley Selection Test Target Mock",
        "description": "Original verbal, English comprehension, numerical and non-verbal practice balanced to Bexley's published weighting.",
        "school": "Bexley grammar schools",
        "stage": "Bexley Selection Test",
        "duration_minutes": 50,
        "is_free": False,
        "question_ids": tuple(
            [f"e{i:02d}" for i in range(17, 25)]
            + [f"v{i:02d}" for i in range(1, 9)]
            + [f"m{i:02d}" for i in range(41, 49)]
            + [f"n{i:02d}" for i in range(9, 17)]
        ),
        "source_ids": ("dfe-primary", "bexley-selection-2027"),
        "format_note": "Condensed 50:25:25 verbal, numerical and non-verbal mix; the official test uses two approximately 50-minute booklets.",
        "last_verified": "2026-08-09",
    },
    "wirral-assessment-1": {
        "id": "wirral-assessment-1",
        "category": "school_target",
        "title": "Wirral Grammar Assessment Target Mock",
        "description": "Original Verbal Reasoning, Mathematics and Non-Verbal Reasoning practice for the shared Wirral assessment.",
        "school": "Wirral non-Catholic grammar schools",
        "stage": "Grammar School Assessment",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple(
            [f"v{i:02d}" for i in range(25, 33)]
            + [f"m{i:02d}" for i in range(9, 17)]
            + [f"n{i:02d}" for i in range(41, 49)]
        ),
        "source_ids": ("dfe-primary", "wirral-assessment-2027"),
        "format_note": "Shortened three-subject practice; the official Wirral assessment has two papers taken on the same day.",
        "last_verified": "2026-08-09",
    },
    "gloucestershire-grammar-1": {
        "id": "gloucestershire-grammar-1",
        "category": "school_target",
        "title": "Gloucestershire Grammar Schools Target Mock",
        "description": "Original verbal ability, numerical reasoning and non-verbal reasoning practice for the shared county test scope.",
        "school": "Gloucestershire grammar schools",
        "stage": "Grammar School Entrance Test",
        "duration_minutes": 50,
        "is_free": False,
        "question_ids": tuple(
            [f"e{i:02d}" for i in range(33, 39)]
            + [f"v{i:02d}" for i in range(9, 15)]
            + [f"m{i:02d}" for i in range(19, 31)]
            + [f"n{i:02d}" for i in range(1, 13)]
        ),
        "source_ids": ("dfe-primary", "gloucestershire-test-2027"),
        "format_note": "Condensed three-skill multiple-choice practice; the published Gloucestershire format uses two papers.",
        "last_verified": "2026-08-09",
    },
    "slough-consortium-1": {
        "id": "slough-consortium-1",
        "category": "school_target",
        "title": "Slough Consortium 11+ Target Mock",
        "description": "Original English, Mathematics, Verbal and Non-Verbal Reasoning practice for the consortium's shared scope.",
        "school": "Slough Consortium of Grammar Schools",
        "stage": "Consortium 11+ Examination",
        "duration_minutes": 50,
        "is_free": False,
        "question_ids": tuple(
            [f"e{i:02d}" for i in range(1, 9)]
            + [f"v{i:02d}" for i in range(41, 49)]
            + [f"m{i:02d}" for i in range(17, 25)]
            + [f"n{i:02d}" for i in range(25, 33)]
        ),
        "source_ids": ("dfe-primary", "slough-consortium-2027"),
        "format_note": "Shortened four-subject practice; the official consortium examination uses two longer papers.",
        "last_verified": "2026-08-09",
    },
    "medway-test-1": {
        "id": "medway-test-1",
        "category": "school_target",
        "title": "Medway Test Target Mock",
        "description": "Original English, Mathematics, Verbal and Spatial/Non-Verbal Reasoning practice reflecting Medway's published paper mix.",
        "school": "Medway grammar schools",
        "stage": "Medway Test",
        "duration_minutes": 50,
        "is_free": False,
        "question_ids": tuple(
            [f"e{i:02d}" for i in range(37, 49)]
            + [f"m{i:02d}" for i in range(25, 37)]
            + [f"v{i:02d}" for i in range(33, 36)]
            + [f"n{i:02d}" for i in range(33, 36)]
        ),
        "source_ids": ("dfe-primary", "medway-test-2027"),
        "format_note": "Condensed 2:2:1 English, Maths and Reasoning mix; the official Medway Test uses three separately timed papers.",
        "last_verified": "2026-08-09",
    },
    "wilsons-second-stage-1": {
        "id": "wilsons-second-stage-1",
        "category": "school_target",
        "title": "Wilson's Second Stage Skills Mock",
        "description": "Original English and Mathematics practice for the subjects in Wilson's shared Second Stage examination.",
        "school": "Wilson's School",
        "stage": "Second Stage skills practice",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": (
            "e35", "e37", "e59", "e60", "e63", "e41",
            "e45", "e58", "e50", "e52", "e49", "e51",
            "m53", "m50", "m52", "m54", "m49", "m51",
            "m55", "m61", "m56", "m57", "m58", "m60",
        ),
        "source_ids": ("dfe-primary", "wilsons-second-stage-2027"),
        "format_note": "Shortened multiple-choice skills check; the official Second Stage has separate written English and Maths papers and is not multiple choice.",
        "last_verified": "2026-08-09",
    },
    "tiffin-girls-stage-one-1": {
        "id": "tiffin-girls-stage-one-1",
        "category": "school_target",
        "title": "Tiffin Girls' Stage One Target Mock",
        "description": "Original English and Mathematics questions for The Tiffin Girls' School Stage One subject scope.",
        "school": "The Tiffin Girls' School",
        "stage": "Stage One",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": (
            "e07", "e10", "e12", "e17", "e21", "e01",
            "e03", "e05", "e02", "e04", "e53", "e54",
            "m53", "m38", "m39", "m48", "m33", "m34",
            "m40", "m41", "m06", "m10", "m62", "m64",
        ),
        "source_ids": ("dfe-primary", "tiffin-girls-2027"),
        "format_note": "Shortened English and Maths practice; the official Stage One questions are computer-marked and Stage Two uses written papers.",
        "last_verified": "2026-08-09",
    },
    "st-olaves-stage-one-1": {
        "id": "st-olaves-stage-one-1",
        "category": "school_target",
        "title": "St Olave's Stage One Target Mock",
        "description": "Original English, Mathematics, Verbal and Non-Verbal Reasoning questions for the published Stage One scope.",
        "school": "St Olave's Grammar School",
        "stage": "Stage One",
        "duration_minutes": 40,
        "is_free": False,
        "question_ids": (
            "e31", "e35", "e33", "e34", "e40", "e49",
            "m07", "m08", "m11", "m12", "m06", "m10",
            "v33", "v39", "v35", "v38", "v40", "v36",
            "n34", "n36", "n33", "n43", "n40", "n57",
        ),
        "source_ids": (
            "dfe-primary",
            "st-olaves-2027",
            "st-olaves-public-sample",
        ),
        "format_note": "Shortened four-section multiple-choice practice based on the public Stage One format; it is not an official school paper.",
        "last_verified": "2026-08-09",
    },
    "henrietta-barnett-first-round-1": {
        "id": "henrietta-barnett-first-round-1",
        "category": "school_target",
        "title": "Henrietta Barnett First Round Target Mock",
        "description": "Original English, Verbal and Non-Verbal Reasoning practice for the school's published First Round scope.",
        "school": "The Henrietta Barnett School",
        "stage": "First Round",
        "duration_minutes": 40,
        "is_free": False,
        "question_ids": (
            "e17", "e21", "e18", "e19", "e22", "e23", "e53", "e54",
            "v17", "v19", "v18", "v25", "v22", "v24", "v27", "v20",
            "n17", "n18", "n19", "n20", "n22", "n24", "n25", "n29",
        ),
        "source_ids": ("dfe-primary", "henrietta-barnett-2027"),
        "format_note": "Shortened First Round practice only; the official Second Round separately tests written English and Mathematics.",
        "last_verified": "2026-08-09",
    },
    "altrincham-girls-1": {
        "id": "altrincham-girls-1",
        "category": "school_target",
        "title": "Altrincham Girls Entrance Target Mock",
        "description": "Original Mathematics, Verbal and Non-Verbal Reasoning practice for the Trafford consortium scope used by AGGS.",
        "school": "Altrincham Grammar School for Girls",
        "stage": "Trafford GL Consortium Entrance Exam",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": (
            "m53", "m31", "m32", "m33", "m34", "m26", "m30", "m56",
            "v45", "v49", "v41", "v43", "v46", "v48", "v54", "v44",
            "n42", "n46", "n49", "n41", "n44", "n43", "n40", "n57",
        ),
        "source_ids": ("dfe-primary", "altrincham-girls-2027"),
        "format_note": "Shortened three-skill practice; the official Trafford consortium entrance exam has two papers of approximately one hour each.",
        "last_verified": "2026-08-09",
    },
    "reading-fsce-1": {
        "id": "reading-fsce-1",
        "category": "school_target",
        "title": "Reading School FSCE Target Mock",
        "description": "Original cross-curricular questions applying Year 5 knowledge across the public FSCE subject range.",
        "school": "Reading School",
        "stage": "FSCE Entrance Test familiarisation",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple(f"fsce{i:02d}" for i in range(1, 23)),
        "source_ids": ("dfe-primary", "reading-fsce-2027"),
        "format_note": "Shortened multiple-choice cross-curricular practice; the official FSCE test can also use short written answers and a creative response, which are not marked here.",
        "last_verified": "2026-08-09",
    },
    "cchs-fsce-1": {
        "id": "cchs-fsce-1",
        "category": "school_target",
        "title": "CCHS FSCE Target Mock",
        "description": "Original cross-curricular, English and Mathematics practice for Chelmsford County High School for Girls' public FSCE scope.",
        "school": "Chelmsford County High School for Girls",
        "stage": "FSCE Entrance Test familiarisation",
        "duration_minutes": 45,
        "is_free": False,
        "question_ids": tuple(
            [f"fsce{i:02d}" for i in range(1, 7)]
            + [f"fsce{i:02d}" for i in range(9, 15)]
            + [f"fsce{i:02d}" for i in range(17, 23)]
            + ["e59", "e60", "e58", "e57"]
            + ["m53", "m55", "m58", "m60"]
        ),
        "source_ids": ("dfe-primary", "cchs-fsce-2027"),
        "format_note": "Shortened multiple-choice cross-curricular practice; the official FSCE test may use other answer formats and creative work that this mock does not score.",
        "last_verified": "2026-08-09",
    },
}
