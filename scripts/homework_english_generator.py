#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate AI-markable English homework for England Years 1-6.

The generator keeps the existing worksheet/RAG/review interface.  Open-ended
composition prompts have been replaced with closed questions about phonics,
spelling, vocabulary, grammar, punctuation, text structure and comprehension.
This lets the existing answer-key reviewer decide right or wrong consistently.

Curriculum basis: DfE English programmes of study for key stages 1 and 2,
including reading, writing, spelling, vocabulary, grammar and punctuation.
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

HOMEWORK_COUNT = {1: 960, 2: 1120, 3: 1500, 4: 1980, 5: 2400, 6: 2640}

ENGLISH_TOPICS_BY_YEAR = {
    1: ["Phonics and Letter Sounds", "Sight Words", "Simple Sentence Writing", "Reading Comprehension (Simple)", "Capital Letters and Full Stops", "Rhyming Words", "Story Sequencing", "Describing Pictures"],
    2: ["Spelling Patterns", "Punctuation (Full Stops, Capital Letters, Question Marks)", "Sentence Structure", "Reading Comprehension (Short Texts)", "Creative Writing (Simple Stories)", "Word Classes (Nouns, Verbs, Adjectives)", "Prefixes and Suffixes", "Writing Instructions"],
    3: ["Grammar (Tenses)", "Paragraph Writing", "Reading Comprehension", "Spelling Rules", "Creative Writing", "Punctuation (Commas, Speech Marks)", "Word Classes (Adverbs, Prepositions)", "Editing and Proofreading"],
    4: ["Advanced Grammar", "Formal and Informal Writing", "Reading Inference", "Creative Writing (Descriptions)", "Report Writing", "Punctuation (Colons, Semi-colons)", "Figurative Language", "Sentence Variety"],
    5: ["Complex Sentences", "Persuasive Writing", "Reading Analysis", "Creative Writing (Narratives)", "Newspaper Reports", "Grammar (Modal Verbs, Passive Voice)", "Vocabulary Development", "Essay Structure"],
    6: ["Advanced Writing Techniques", "Analytical Writing", "Reading Comprehension (Complex Texts)", "Creative Writing (Advanced)", "Debate and Argument", "SATs Writing Preparation", "Literary Devices", "Editing for Impact"],
}

YEAR_CONFIG = {
    1: {"key_stage": "KS1", "homework_minutes": "10-15"},
    2: {"key_stage": "KS1", "homework_minutes": "10-20"},
    3: {"key_stage": "KS2", "homework_minutes": "15-20"},
    4: {"key_stage": "KS2", "homework_minutes": "20-25"},
    5: {"key_stage": "KS2", "homework_minutes": "20-30"},
    6: {"key_stage": "KS2", "homework_minutes": "25-30"},
}


def _phonics(year, topic, index):
    rng=stable_random("English",year,topic,index);q=[]
    sets=[
        ("Which word begins with the /sh/ sound?","ship",["chip","tip","map"]),
        ("Which word contains the /ch/ sound?","chair",["share","fair","star"]),
        ("Which word has the long /ai/ sound?","rain",["ran","ring","run"]),
        ("Which word has the long /ee/ sound?","green",["grin","grain","grow"]),
        ("Which word ends with the /ng/ sound?","king",["kick","kit","kid"]),
        ("Which word has two syllables?","rabbit",["cat","dog","fish"]),
        ("Which word has the same first sound as moon?","map",["sun","top","fish"]),
        ("Which word has the same final sound as duck?","book",["bed","bus","bag"]),
        ("Which word is split correctly into sounds?","f-i-sh",["fi-shh","fish-e","f-ish-e"]),
        ("Which word contains the grapheme 'oa'?","boat",["boot","bat","bit"]),
    ]
    for stem,ans,wrong in sets:q.append(make_mcq(stem,ans,wrong,rng))
    return q


def _year1(topic,index):
    rng=stable_random("English",1,topic,index);q=[]
    if topic=="Phonics and Letter Sounds":q=_phonics(1,topic,index)
    elif topic=="Sight Words":
        words=[("Which word completes the sentence: I ___ to school.","go",["no","so","do"]),("Which word completes: ___ is my book.","This",["These","Then","They"]),("Which is a common exception word?","said",["sayed","sed","sayd"]),("Which spelling is correct?","because",["becos","becaus","beccause"]),("Which word completes: We ___ happy.","are",["is","am","be"])]
        for i in range(10):stem,ans,wrong=words[(i+index)%len(words)];q.append(make_mcq(stem,ans,wrong,rng))
    elif topic=="Simple Sentence Writing":
        items=[("Which is a complete sentence?","The dog runs.",["The dog","Runs fast","Dog the runs"]),("Choose the sentence with words in the correct order.","Sam kicks the ball.",["Kicks Sam the ball.","The ball Sam kicks.","Sam the kicks ball."]),("Which word completes: The cat ___ on the mat.","sat",["blue","soft","mat"]),("Which sentence tells us something?","It is raining.",["Is it raining?","Stop raining!","Raining?"]),("Which sentence asks a question?","Where is my coat?",["My coat is blue.","Put on your coat.","What a warm coat!"])]
        for i in range(10):stem,ans,wrong=items[(i+index)%len(items)];q.append(make_mcq(stem,ans,wrong,rng))
    elif topic=="Reading Comprehension (Simple)":
        passages=[("Mia has a red kite. She flies it in the park.",[("What colour is Mia's kite?","red",["blue","green","yellow"]),("Where does Mia fly the kite?","in the park",["at school","in the kitchen","on a bus"])]),("Tom feeds his small brown rabbit a carrot.",[("What animal does Tom feed?","a rabbit",["a dog","a cat","a bird"]),("What food does it get?","a carrot",["an apple","some bread","a banana"])])]
        for i in range(10):
            passage,items=passages[(i//2+index)%len(passages)];stem,ans,wrong=items[i%2];q.append(make_mcq(f"Read: '{passage}' {stem}",ans,wrong,rng))
    elif topic=="Capital Letters and Full Stops":
        items=[("Which sentence is punctuated correctly?","Ben has a bike.",["ben has a bike.","Ben has a bike","ben has a bike"]),("Which word needs a capital letter in: 'we went to london.'?","London",["went","to","we"]),("Which mark belongs at the end of a telling sentence?","full stop",["question mark","comma","apostrophe"]),("Which sentence starts correctly?","The sun is hot.",["the sun is hot.","THE sun is hot.","tHe sun is hot."]),("Which name is written correctly?","Aisha",["aisha","AISha","aIsha"])]
        for i in range(10):stem,ans,wrong=items[(i+index)%len(items)];q.append(make_mcq(stem,ans,wrong,rng))
    elif topic=="Rhyming Words":
        pairs=[("cat","hat",["cup","dog","fish"]),("log","frog",["leg","sun","top"]),("light","night",["late","little","look"]),("play","day",["blue","boy","pen"]),("moon","spoon",["man","mouse","map"])]
        for i in range(10):word,ans,wrong=pairs[(i+index)%len(pairs)];q.append(make_mcq(f"Which word rhymes with '{word}'?",ans,wrong,rng))
    elif topic=="Story Sequencing":
        sequences=[("First, Ava put on her coat. Next, she opened the door. What happened next?","She went outside.",["She went to bed.","She ate breakfast yesterday.","She took off her shoes before dressing."]),("First, we mixed the flour. Next, we baked the cake. What happened last?","We ate the cake.",["We bought flour after eating it.","We planted the cake.","We put it back into an egg."]),("A seed was planted. It was watered. What happened next?","A shoot grew.",["The seed became a stone.","The plant turned into a shoe.","The water became dry."])]
        for i in range(10):stem,ans,wrong=sequences[(i+index)%len(sequences)];q.append(make_mcq(stem,ans,wrong,rng))
    elif topic=="Describing Pictures":
        scenes=[("Imagine a yellow duck swimming on a blue pond. Which sentence describes it best?","A yellow duck swims on a blue pond.",["A red car drives on a road.","A cat sleeps under a bed.","A tree grows in a desert."]),("Imagine two children building a tall sandcastle. Which sentence fits?","Two children build a tall sandcastle.",["One child reads a book.","Three birds fly away.","A dog eats its dinner."]),("Imagine a small black cat under a table. Which description is correct?","A small black cat is under the table.",["A large white dog is on the table.","A black cat is above the roof.","A small fish is in a tree."])]
        for i in range(10):stem,ans,wrong=scenes[(i+index)%len(scenes)];q.append(make_mcq(stem,ans,wrong,rng))
    else:raise ValueError(f"Unknown Year 1 English topic: {topic}")
    return render_homework("English",1,topic,index,q)


def _year2(topic,index):
    rng=stable_random("English",2,topic,index);q=[]
    if topic=="Spelling Patterns":
        items=[("Which spelling is correct?","knock",["nock","knok","knoch"]),("Which word ends with -tion?","station",["stasion","stashion","stacion"]),("Which word uses 'dge' after a short vowel?","badge",["bage","badje","baj"]),("Which spelling is correct?","beautiful",["beautifull","beutiful","beautyful"]),("Which word contains the /j/ sound written 'g'?","giant",["jam","chair","ship"]),("Which spelling is correct?","people",["peaple","peeple","pepole"])]
        for i in range(10):stem,ans,wrong=items[(i+index)%len(items)];q.append(make_mcq(stem,ans,wrong,rng))
    elif topic.startswith("Punctuation"):
        items=[("Which sentence needs a question mark?","Where is the bus?",["The bus is late.","Stop the bus!","The red bus."]),("Which sentence is correct?","On Monday, Sam went swimming.",["on monday, Sam went swimming.","On Monday Sam went swimming", "On monday, sam went swimming."]),("Which sentence uses an exclamation mark correctly?","What a huge wave!",["What a huge wave.","Where is the wave!","The wave is blue?"]),("Which sentence has a correct comma in a list?","I packed socks, shoes and a hat.",["I packed, socks shoes and a hat.","I packed socks shoes, and a hat.","I, packed socks shoes and a hat."])]
        for i in range(10):stem,ans,wrong=items[(i+index)%len(items)];q.append(make_mcq(stem,ans,wrong,rng))
    elif topic=="Sentence Structure":
        items=[("Choose the sentence joined correctly with 'and'.","I opened the box and found a toy.",["I opened and the box found a toy.","And I opened the box.","I opened the box found and a toy."]),("Which conjunction shows a reason?","because",["but","or","then"]),("Which sentence is in the present tense?","The birds sing.",["The birds sang.","The birds will sing.","The birds had sung."]),("Which sentence is a command?","Close the gate.",["The gate is closed.","Is the gate closed?","What a heavy gate!"]),("Which sentence is a statement?","The train is early.",["Is the train early?","Catch the train!","What a fast train!"])]
        for i in range(10):stem,ans,wrong=items[(i+index)%len(items)];q.append(make_mcq(stem,ans,wrong,rng))
    elif topic=="Reading Comprehension (Short Texts)":
        passage="On Saturday, Leo visited the library. He borrowed a book about space and read it on the bus home."
        items=[("When did Leo visit the library?","Saturday",["Monday","Friday","Sunday"]),("What was the book about?","space",["dinosaurs","football","cooking"]),("Where did Leo read the book?","on the bus",["in bed","at school","in the park"]),("Why did Leo go to the library?","to borrow a book",["to buy shoes","to play football","to cook dinner"]),("Which event happened last?","Leo read on the bus home.",["Leo visited the library.","Leo borrowed a book.","It became Saturday."])]
        for i in range(10):stem,ans,wrong=items[(i+index)%len(items)];q.append(make_mcq(f"Read: '{passage}' {stem}",ans,wrong,rng))
    elif topic=="Creative Writing (Simple Stories)":
        items=[("Which is the best opening for a story?","One windy morning, Zara found a tiny key.",["Keys are metal objects.","The end.","Zara key windy tiny."]),("Which sentence gives a clear setting?","Snow covered the quiet village.",["It was there.","Things happened.","Village snow quiet covered."]),("Which is the best ending?","At last, Ben returned the lost puppy to its owner.",["Once upon a time.","Puppies have four legs.","Ben puppy owner return maybe."]),("Which word best describes a storm?","fierce",["gentle","tiny","silent"]),("Which sentence shows a character's feeling?","Maya's hands shook as she opened the door.",["The door was brown.","Maya had hands.","The room had a floor."])]
        for i in range(10):stem,ans,wrong=items[(i+index)%len(items)];q.append(make_mcq(stem,ans,wrong,rng))
    elif topic=="Word Classes (Nouns, Verbs, Adjectives)":
        items=[("Which word is the noun in 'The fox jumps'?","fox",["the","jumps","quickly"]),("Which word is the verb in 'Birds sing loudly'?","sing",["birds","loudly","the"]),("Which word is the adjective in 'a shiny coin'?","shiny",["coin","a","rolled"]),("Which is a noun?","teacher",["teach","carefully","bright"]),("Which is a verb?","whisper",["whispering voice","quiet","softly"]),("Which is an adjective?","enormous",["elephant","stomp","outside"])]
        for i in range(10):stem,ans,wrong=items[(i+index)%len(items)];q.append(make_mcq(stem,ans,wrong,rng))
    elif topic=="Prefixes and Suffixes":
        items=[("Add un- to 'happy'. Which word is made?","unhappy",["happyun","unhappi","rehappy"]),("Add -ful to 'help'.","helpful",["helpness","unhelp","helping"]),("Which word means 'not kind'?","unkind",["kindful","rekind","kindly"]),("Add -less to 'care'.","careless",["careful","caring","uncare"]),("Which word has the suffix -ment?","enjoyment",["enjoyful","unenjoy","enjoying"])]
        for i in range(10):stem,ans,wrong=items[(i+index)%len(items)];q.append(make_mcq(stem,ans,wrong,rng))
    elif topic=="Writing Instructions":
        items=[("Which word is best to start the first instruction?","First",["Yesterday","Maybe","Sadly"]),("Which sentence is an instruction?","Mix the flour and water.",["The flour is white.","Did you mix it?","What a messy bowl!"]),("Which verb is an imperative?","Cut",["knife","careful","slowly"]),("What should come after 'First, wash the apple'?","Next, cut the apple carefully.",["Yesterday, apples grew.","The apple is red.","Finally, buy the apple first."]),("Which heading suits instructions?","How to Make a Paper Boat",["My Best Holiday","The Lost Dragon","Why Rain Falls"])]
        for i in range(10):stem,ans,wrong=items[(i+index)%len(items)];q.append(make_mcq(stem,ans,wrong,rng))
    else:raise ValueError(f"Unknown Year 2 English topic: {topic}")
    return render_homework("English",2,topic,index,q)


def _ks2_grammar(year,topic,index):
    rng=stable_random("English",year,topic,index);q=[]
    level_items={
        3:[("Which sentence is in the past tense?","The dog chased the ball.",["The dog chases the ball.","The dog will chase the ball.","The dog is chasing tomorrow."]),("Which word is a preposition?","under",["jump","bright","slowly"]),("Which word is an adverb?","carefully",["careful","care","carer"]),("Which sentence uses the present perfect?","I have finished my book.",["I finish my book.","I finished my book.","I will finish my book."]),("Which conjunction shows contrast?","although",["because","when","so"]),("Which sentence uses 'a' or 'an' correctly?","an orange",["a orange","an banana","a umbrella"])],
        4:[("Which sentence uses a fronted adverbial?","After lunch, we played outside.",["We played outside after lunch.","Lunch was outside.","We after played lunch."]),("Which word is a determiner in 'those bright stars'?","those",["bright","stars","shine"]),("Which sentence uses Standard English?","We were waiting.",["We was waiting.","We be waiting.","We is waiting."]),("Which sentence has a possessive pronoun?","The blue bag is mine.",["I carried the bag.","My bag is blue.","The bag has books."]),("Which word is a pronoun?","they",["children","quickly","yellow"]),("Which sentence uses the present perfect?","She has visited York.",["She visited York yesterday.","She visits York.","She will visit York."])],
        5:[("Which word is a modal verb?","might",["walk","quiet","garden"]),("Which sentence is passive?","The window was broken by the ball.",["The ball broke the window.","The window broke the ball.","The ball is round."]),("Which sentence contains a relative clause?","The cyclist, who wore a helmet, stopped.",["The cyclist stopped.","Wearing a helmet.","The cyclist and helmet stopped."]),("Which sentence uses a parenthesis correctly?","The museum (which opened in 1902) is nearby.",["The museum which (opened in 1902 is nearby.","The museum) opened in 1902 (is nearby.","The museum opened in 1902 is nearby)."]),("Which word shows possibility?","perhaps",["certainly","always","must"]),("Which sentence has an adverb of possibility?","The train will probably arrive soon.",["The train arrives.","The probable train.","The train is a vehicle."])],
        6:[("Which sentence is in the passive voice?","The trophy was lifted by the captain.",["The captain lifted the trophy.","The captain was proud.","The trophy shone."]),("Which sentence uses the subjunctive form?","If I were taller, I could reach it.",["If I was taller, I can reach it.","I am taller.","I were reaching it."]),("Which word is a synonym for 'reluctant'?","unwilling",["eager","noisy","ordinary"]),("Which sentence is the most formal?","I would be grateful if you could reply.",["Reply soon, please.","Can you get back to me?","Tell me now."]),("Which punctuation can mark a boundary between closely related main clauses?","semicolon",["apostrophe","hyphen","quotation mark"]),("Which sentence uses a colon to introduce a list?","Bring three items: a pen, a ruler and a notebook.",["Bring: three items a pen, a ruler and a notebook.","Bring three: items a pen, a ruler and a notebook.","Bring three items a pen: a ruler and a notebook."])],
    }
    items=level_items[year]
    for i in range(10):stem,ans,wrong=items[(i+index)%len(items)];q.append(make_mcq(stem,ans,wrong,rng))
    return q


def _reading(year,topic,index):
    rng=stable_random("English",year,topic,index)
    passages={
        3:"At dawn, Priya pulled on her boots and followed the muddy path. A trail of tiny paw prints led towards the shed, where a frightened hedgehog was trapped behind a bucket.",
        4:"The lighthouse beam swept across the restless sea. Although the storm had weakened, Arun kept watch because several fishing boats had not yet returned to the harbour.",
        5:"The council planned to close the old orchard, but local residents argued that it provided food and shelter for wildlife. They collected evidence, wrote letters and proposed a safer walking route through the trees.",
        6:"When the research team reached the glacier, they found that the marker placed five years earlier was now far from the ice edge. The change supported the measurements in their records, although one scientist warned that a longer set of data was needed before drawing a firm conclusion.",
    }
    p=passages[year]
    items={
        3:[("When did Priya follow the path?","at dawn",["at midnight","after lunch","at sunset"]),("What made the prints?","a hedgehog",["a fox","a dog","a bird"]),("Where was the animal trapped?","behind a bucket",["under a tree","inside the house","beside a pond"]),("Which word best describes the path?","muddy",["dry","icy","golden"]),("Why did Priya go to the shed?","She followed the paw prints.",["She wanted breakfast.","She lost her boots.","She heard music."])],
        4:[("What was the weather like?","stormy",["calm","sunny","snowy"]),("Why did Arun keep watch?","Some fishing boats had not returned.",["The lighthouse was closed.","He wanted to sleep.","The harbour was empty forever."]),("What does 'restless sea' suggest?","The water was rough and moving.",["The sea was asleep.","The water was frozen.","The sea was silent and still."]),("Which word is a conjunction showing contrast?","Although",["because","across","several"]),("Where were the boats expected to return?","the harbour",["the mountain","the station","the orchard"])],
        5:[("What did the council plan to close?","the old orchard",["the school","the harbour","the museum"]),("Why did residents value the orchard?","It provided food and shelter for wildlife.",["It was a car park.","It had a cinema.","It stopped all rain."]),("Which action showed residents were organised?","They collected evidence and wrote letters.",["They ignored the plan.","They cut down the trees.","They moved away."]),("What is the main purpose of the passage?","to explain a local disagreement and response",["to give baking instructions","to advertise a holiday","to describe a football match"]),("What does 'proposed' mean here?","suggested",["destroyed","forgot","measured"])],
        6:[("What had moved since the marker was placed?","the edge of the glacier",["the research station","the mountain","the marker itself"]),("What supported the team's records?","the change in the ice edge",["a newspaper story","a guess","a photograph of a boat"]),("Why did one scientist want more data?","to make the conclusion more reliable",["to delay lunch","to move the glacier","to hide the measurements"]),("What does 'firm conclusion' mean?","a confident judgement based on evidence",["a hard piece of ice","a quick guess","an unrelated opinion"]),("Which statement best summarises the passage?","Evidence showed glacier change, but more long-term data was advised.",["The team found no change.","The team stopped all research.","The glacier grew because of the marker."])],
    }
    q=[]
    for i in range(10):stem,ans,wrong=items[year][(i+index)%len(items[year])];q.append(make_mcq(f"Read: '{p}' {stem}",ans,wrong,rng))
    return q


def _writing_structure(year,topic,index):
    rng=stable_random("English",year,topic,index)
    items_by_year={
        3:[("Which topic sentence best starts a paragraph about bees?","Bees are important pollinators.",["I like yellow.","Yesterday was Tuesday.","The end."]),("Which sentence gives a reason?","Plants grow well because they receive enough light.",["Plants are green.","Do plants grow?","What bright plants!"]),("Which word best links events in time?","afterwards",["blue","under","perhaps"]),("Which sentence is most suitable for a story setting?","Mist curled between the dark trees.",["Trees are plants.","There were things.","I tree mist dark."]),("Which sentence belongs in instructions?","Next, fold the paper in half.",["The paper was lovely.","I once saw paper.","What a paper!"])],
        4:[("Which opening is suitable for a formal report?","This report explains the results of our traffic survey.",["You won't believe this!","Once upon a time...","Hi everyone!"]),("Which sentence is informal?","The match was loads of fun.",["The event was highly enjoyable.","The results were recorded accurately.","Visitors must enter quietly."]),("Which detail creates a precise description?","Rain tapped sharply against the glass roof.",["It was nice.","Stuff happened outside.","There was weather."]),("Which sentence is a clear conclusion?","Therefore, the evidence suggests that recycling increased.",["First, we asked a question.","Maybe something happened.","Recycling bin green."]),("Which heading suits a non-fiction report?","How Volcanoes Form",["The Magical Dragon","My Funniest Day","A Secret Wish"])],
        5:[("Which sentence gives a persuasive reason?","Schools should plant trees because they provide shade and habitats.",["Trees are green.","I saw a tree.","Plant maybe tree."]),("Which phrase addresses the reader directly?","Imagine how much cleaner our park could be.",["The park opened in 1998.","Parks contain grass.","A park was measured."]),("Which sentence uses evidence?","In our survey, 78% of pupils supported the change.",["Everyone definitely agrees.","I just know it is right.","Changes are changeable."]),("Which is the best newspaper headline?","Local Pupils Transform Neglected Garden",["A Garden", "Something Happened", "I Like Gardens"]),("Which sentence is an effective narrative hook?","The envelope on the doorstep carried no name, only a silver star.",["Envelopes are made of paper.","The story starts now.","There was an envelope and it was envelope-like."])],
        6:[("Which thesis sentence clearly states an argument?","School streets should restrict traffic at busy times because this improves safety and air quality.",["Traffic exists.","Some people have cars.","This paragraph is about things."]),("Which sentence evaluates evidence?","The survey is useful, although its small sample limits how widely we can apply the result.",["The survey has numbers.","All surveys are perfect.","The result is a result."]),("Which transition signals a counterargument?","However",["Furthermore","For example","Consequently"]),("Which sentence creates controlled suspense?","The footsteps stopped outside the locked door; then the handle began to turn.",["Someone walked.","Doors have handles.","It was scary and scary."]),("Which conclusion is most effective?","Taken together, the evidence supports a trial of the scheme, followed by a careful review.",["That is all.","I hope you liked it.","Schemes are interesting."])],
    }
    q=[];items=items_by_year[year]
    for i in range(10):stem,ans,wrong=items[(i+index)%len(items)];q.append(make_mcq(stem,ans,wrong,rng))
    return q


def _punctuation(year,topic,index):
    rng=stable_random("English",year,topic,index)
    items_by_year={
        3:[("Which sentence uses inverted commas correctly?",'"Stop!" shouted Ali.',["Stop! shouted Ali.",'"Stop! shouted" Ali.','Stop "shouted" Ali!']),("Which sentence uses a comma after a fronted adverbial?","Before sunrise, the hikers left.",["Before, sunrise the hikers left.","Before sunrise the, hikers left.","Before sunrise the hikers left,"]),("Which sentence uses an apostrophe for possession?","the girl's coat",["the girls coat","the girls' coat for one girl","the girl is coat"]),("Which sentence punctuates a list correctly?","We saw lions, tigers, bears and wolves.",["We saw, lions tigers bears and wolves.","We saw lions tigers, bears and wolves.","We, saw lions tigers bears and wolves."])],
        4:[("Which sentence uses a colon correctly?","You need three things: paper, glue and scissors.",["You need: three things paper, glue and scissors.","You need three: things paper, glue and scissors.","You need three things paper: glue and scissors."]),("Which sentence uses a semicolon correctly?","The rain stopped; the match began.",["The rain; stopped the match began.","The rain stopped the; match began.","The rain stopped; and because the match."]),("Which sentence uses an apostrophe for plural possession?","the players' boots",["the player's boots for many players","the players boots","the player is boots"]),("Which sentence uses a dash to add extra information?","The final runner—our team captain—crossed the line.",["The final—runner our team captain crossed the line.","The final runner our—team captain crossed the line.","The final runner crossed—the line our team captain."])],
        5:[("Which sentence uses brackets correctly?","The blue whale (the largest animal) can exceed 25 metres.",["The blue whale (the largest animal can exceed 25 metres.","The blue whale the largest animal) can exceed 25 metres.","The blue whale )the largest animal( can exceed 25 metres."]),("Which sentence uses a colon correctly?","She had one goal: to finish the race.",["She had: one goal to finish the race.","She had one: goal to finish the race.","She had one goal to: finish the race."]),("Which sentence uses commas for parenthesis?","Mr Khan, our new coach, arrived early.",["Mr Khan our, new coach arrived early.","Mr Khan our new coach, arrived early.","Mr, Khan our new coach arrived early."]),("Which sentence uses a hyphen to avoid ambiguity?","a man-eating shark",["a man eating-shark","a-man eating shark","a man eating shark when the shark is eating a man"] )],
        6:[("Which sentence uses a semicolon between related clauses?","The path was flooded; we chose another route.",["The path; was flooded we chose another route.","The path was flooded because; we chose another route.","The path was; flooded."]),("Which sentence uses a colon to introduce an explanation?","There was one problem: the bridge was closed.",["There was: one problem the bridge was closed.","There was one: problem the bridge was closed.","There was one problem the: bridge was closed."]),("Which sentence uses a dash for emphasis?","Only one person knew the code—the caretaker.",["Only—one person knew the code the caretaker.","Only one person—knew the code the caretaker.","Only one person knew—the code the caretaker."]),("Which sentence uses an ellipsis to show hesitation?",'"I thought I saw... something move," whispered Jo.',["I thought... I saw something move normally.","I thought I saw something move.","I... thought... every... word..."])],
    }
    q=[];items=items_by_year[year]
    for i in range(10):stem,ans,wrong=items[(i+index)%len(items)];q.append(make_mcq(stem,ans,wrong,rng))
    return q


def _vocabulary(year,topic,index):
    rng=stable_random("English",year,topic,index)
    levels={3:[("Which word is closest in meaning to 'enormous'?","huge",["tiny","quiet","ordinary"]),("Which word is the opposite of 'ancient'?","modern",["old","historic","broken"]),("What does 'reluctantly' mean?","unwillingly",["eagerly","loudly","quickly"]),("Which word is more precise than 'went' for moving quietly?","crept",["said","looked","stood"])],4:[("Which phrase is a simile?","as cold as ice",["the icy wind","the wind screamed","cold wind"]),("Which phrase is personification?","The leaves danced in the wind.",["The leaves were green.","The wind was strong.","Leaves fell quickly."]),("Which word best replaces 'nice' in a formal report?","beneficial",["cool","lovely","fun"]),("What does 'scarce' mean?","in short supply",["plentiful","brightly coloured","very noisy"])],5:[("Which word is a synonym for 'significant'?","important",["minor","hidden","ordinary"]),("Which word has the strongest meaning?","devastated",["sad","unhappy","disappointed"]),("Which phrase is metaphorical?","The classroom was a furnace.",["The classroom was warm.","The heater was on.","The classroom felt hot."]),("What does 'contrast' mean?","show differences",["repeat exactly","hide evidence","list dates"])],6:[("Which word is closest to 'ambiguous'?","unclear",["certain","brief","honest"]),("Which word is an antonym of 'deteriorate'?","improve",["decline","weaken","worsen"]),("What does 'corroborate' mean?","support with further evidence",["contradict without evidence","summarise briefly","remove all detail"]),("Which phrase is an example of irony?","The fire station burned down during fire-safety week.",["The fire station was red.","Firefighters used water.","The week lasted seven days."])]}
    q=[];items=levels[year]
    for i in range(10):stem,ans,wrong=items[(i+index)%len(items)];q.append(make_mcq(stem,ans,wrong,rng))
    return q


def _generate_ks2(year,topic,index):
    grammar_topics={3:{"Grammar (Tenses)","Word Classes (Adverbs, Prepositions)"},4:{"Advanced Grammar","Sentence Variety"},5:{"Complex Sentences","Grammar (Modal Verbs, Passive Voice)"},6:{"SATs Writing Preparation","Advanced Writing Techniques"}}
    reading_topics={3:{"Reading Comprehension"},4:{"Reading Inference"},5:{"Reading Analysis"},6:{"Reading Comprehension (Complex Texts)","Analytical Writing"}}
    punctuation_topics={3:{"Punctuation (Commas, Speech Marks)","Editing and Proofreading"},4:{"Punctuation (Colons, Semi-colons)"},5:{"Newspaper Reports"},6:{"Editing for Impact"}}
    vocabulary_topics={3:{"Spelling Rules"},4:{"Figurative Language"},5:{"Vocabulary Development"},6:{"Literary Devices"}}
    if topic in grammar_topics.get(year,set()):q=_ks2_grammar(year,topic,index)
    elif topic in reading_topics.get(year,set()):q=_reading(year,topic,index)
    elif topic in punctuation_topics.get(year,set()):q=_punctuation(year,topic,index)
    elif topic in vocabulary_topics.get(year,set()):q=_vocabulary(year,topic,index)
    else:q=_writing_structure(year,topic,index)
    return render_homework("English",year,topic,index,q)


def generate_english_homework(year_group:int,topic:str,index:int)->tuple[str,list[str]]:
    if year_group==1:return _year1(topic,index)
    if year_group==2:return _year2(topic,index)
    if year_group in {3,4,5,6}:return _generate_ks2(year_group,topic,index)
    raise ValueError("year_group must be between 1 and 6")


def generate_year_homework(year_group:int,count:int=500)->list:
    topics=ENGLISH_TOPICS_BY_YEAR.get(year_group,[]);config=YEAR_CONFIG.get(year_group)
    if not topics or not config:return []
    batch=[]
    for i in range(1,count+1):
        topic=topics[(i-1)%len(topics)];content,answers=generate_english_homework(year_group,topic,i)
        batch.append(build_batch_item(content=content,answers=answers,year_group=year_group,subject="English",topic=topic,homework_minutes=config["homework_minutes"],key_stage=config["key_stage"],doc_id=f"english_y{year_group}_{i:04d}"))
        if i%100==0:print(f"  Generated {i}/{count}")
    return batch


def main():
    store=get_homework_rag_store();print(f"RAG target: {store.store.database_target}")
    for year in range(1,7):
        expected=HOMEWORK_COUNT[year];existing=count_year_homework(store,year,"English")
        if existing>=expected:
            print(f"Year {year}: complete ({existing}/{expected})");continue
        data=generate_year_homework(year,expected);added=add_homework_in_batches(store,data)
        print(f"Year {year}: added {added}; target {len(data)}")
    get_rag_stats(store)


if __name__=="__main__":main()
