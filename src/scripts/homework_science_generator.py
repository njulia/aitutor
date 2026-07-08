#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
检查各年级Science作业是否存在，缺失则生成 500 份作业并添加到 RAG 存储
支持 Year 1-6 所有年级

Curriculum alignment note (Years 1-6)
--------------------------------------
Science topics below have been checked against the statutory National Curriculum
in England: Science programmes of study (DfE, 2013, updated 2021) -
https://www.gov.uk/government/publications/national-curriculum-in-england-science-programmes-of-study

The science curriculum is organised into three disciplines:
1. Biology (Living things and their habitats)
2. Chemistry (Materials and their properties, States of matter)
3. Physics (Physical processes, Energy, Forces, Light, Sound)

Each year group covers a combination of these areas with increasing complexity.
All questions are original and curriculum-aligned, using only free public sources
(no proprietary textbooks or assessments reproduced).

Year 1: Animals, plants, everyday materials, seasonal changes, light and dark
Year 2: Animals, plants, growth, materials, uses of everyday materials
Year 3: Plants, animals, rocks, states of matter, forces and magnets, light
Year 4: Living things and habitats, the digestive system, states of matter,
        rocks, sound, electricity
Year 5: Life cycles, properties of materials, Earth and space, forces,
        evolution and inheritance
Year 6: Circulatory and nervous systems, properties of materials, light,
        electricity, evolution, forces
"""

import sys
import os
import random
import json

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from homework_rag import get_homework_rag_store
except ImportError:
    # 备选路径（如果在其他位置）
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from src.homework_rag import get_homework_rag_store

os.environ["TOKENIZERS_PARALLELISM"] = "false"

HOMEWORK_COUNT = {1: 960, 2: 1120, 3: 1500, 4: 1980, 5: 2400, 6: 2640}

# 各年级Science主题（英国小学课程）
SCIENCE_TOPICS_BY_YEAR = {
    1: [
        "Animals and their habitats",
        "Plants and growth",
        "Human body and senses",
        "Everyday materials",
        "Seasonal changes",
        "Light and dark",
        "Floating and sinking",
        "Sound and hearing",
    ],
    2: [
        "Animals and their habitats",
        "Plants - growth and care",
        "Human growth and development",
        "Uses of everyday materials",
        "Weather and seasons",
        "Habitats and food chains",
        "Living things",
        "Materials around us",
    ],
    3: [
        "Plants and photosynthesis",
        "Animals - diet and teeth",
        "Rocks and soil",
        "Light and shadows",
        "Forces and magnets",
        "States of matter",
        "Electrical circuits (simple)",
        "Sound and vibrations",
    ],
    4: [
        "Living things and habitats",
        "The digestive system",
        "States of matter and changes",
        "Rocks and soils",
        "Sound",
        "Electricity and circuits",
        "Light and vision",
        "The water cycle",
    ],
    5: [
        "Life cycles of plants and animals",
        "Properties and changes of materials",
        "Earth and space",
        "Forces and motion",
        "Gravity and weight",
        "Levers and pulleys",
        "Evolution and inheritance",
        "Respiration and gas exchange",
    ],
    6: [
        "Circulatory system and health",
        "The nervous system and reactions",
        "Classification of living things",
        "Electricity and circuits (advanced)",
        "Light - reflection and refraction",
        "Evolution and natural selection",
        "Forces - pressure and moments",
        "Properties of materials (advanced)",
    ],
}


def generate_science_homework(year_group: int, topic: str, index: int) -> tuple:
    """根据年级、主题生成Science作业，返回 (content, correct_answers)"""

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


def _generate_year1_homework(topic: str, index: int) -> tuple:
    """Year 1 Science作业（5-6 岁），返回 (content, correct_answers)"""
    if topic == "Animals and their habitats":
        animals = ["cat", "dog", "bird", "fish", "squirrel", "rabbit", "hedgehog", "frog"]
        habitats = ["home", "garden", "tree", "pond", "burrow", "nest", "hedgerow", "water"]
        questions = [
            f"1. What habitat does a {random.choice(animals)} live in?",
            "2. Draw a picture of an animal and its home.",
            "3. Name 3 animals you can see in your garden.",
            "4. Where do birds live?",
            "5. Where do fish live?",
            "6. What animals can climb trees?",
            "7. Draw a picture of a hedgehog's home.",
            "8. Name a small animal.",
            "9. Name a big animal.",
            "10. Where do you live? Is it an animal habitat too?",
        ]
        answers = [
            "student's own answer (varies by animal)",
            "drawing (with animal and habitat)",
            "student's own answer (e.g., ants, beetles, birds, butterflies)",
            "in a nest/tree",
            "in a pond/water/river",
            "squirrels, birds, cats (student's own)",
            "drawing (underground burrow/nest)",
            "student's own answer (e.g., ant, bee, mouse)",
            "student's own answer (e.g., cow, elephant, horse)",
            "yes, many animals live in human habitats",
        ]
    elif topic == "Plants and growth":
        questions = [
            "1. What do plants need to grow? Name 2 things.",
            "2. What part of a plant is under the ground?",
            "3. What colour are most leaves?",
            "4. Draw a flower and label the parts you know.",
            "5. What helps a plant grow tall?",
            "6. Do all plants have flowers?",
            "7. Name 3 plants you can see near your home.",
            "8. What colour are most flowers?",
            "9. How do seeds travel?",
            "10. Draw the life cycle of a plant (seed to flower).",
        ]
        answers = [
            "water and sunlight (and soil)",
            "roots",
            "green",
            "drawing (with stem, leaves, flower, roots)",
            "sunlight, water, soil",
            "no (grass, ferns don't have flowers)",
            "student's own answer (e.g., grass, daisies, dandelions)",
            "student's own answer (e.g., yellow, pink, red, white)",
            "wind, water, animals carry them",
            "drawing (seed → roots → stem → leaves → flower)",
        ]
    elif topic == "Human body and senses":
        questions = [
            "1. Name 5 parts of your body.",
            "2. What do we use to see?",
            "3. What do we use to hear?",
            "4. What do we use to smell?",
            "5. What do we use to taste?",
            "6. What do we use to touch and feel?",
            "7. Draw a face and label the sense organs.",
            "8. Name a sweet taste.",
            "9. Name a sound you like to hear.",
            "10. Can you touch, see, and hear at the same time?",
        ]
        answers = [
            "student's own answer (e.g., head, arms, legs, hands, feet)",
            "eyes",
            "ears",
            "nose",
            "tongue",
            "skin/hands",
            "drawing (with eyes, ears, nose, tongue, skin labelled)",
            "student's own answer (e.g., chocolate, ice cream, honey)",
            "student's own answer (e.g., music, bird song, laughter)",
            "yes",
        ]
    elif topic == "Everyday materials":
        materials = ["wood", "plastic", "metal", "glass", "paper", "fabric", "rubber", "stone"]
        questions = [
            f"1. Is {random.choice(materials)} hard or soft?",
            "2. Name 3 things made of plastic.",
            "3. Name 3 things made of wood.",
            "4. Can you bend metal?",
            "5. What can we use glass for?",
            "6. Is paper waterproof? (yes or no)",
            "7. Name 2 materials that are strong.",
            "8. Name 2 materials that are flexible (bendy).",
            "9. What material are your shoes made of?",
            "10. Can you sort these materials: wood, plastic, metal, fabric? (say how)",
        ]
        answers = [
            "student's own answer (varies by material)",
            "student's own answer (e.g., bottles, toys, bags)",
            "student's own answer (e.g., table, chair, pencil)",
            "yes (some metals)",
            "windows, drinking glasses, jars",
            "no",
            "student's own answer (e.g., metal, wood, plastic, stone)",
            "student's own answer (e.g., rubber, fabric, paper)",
            "student's own answer (e.g., rubber, leather, plastic, canvas)",
            "by material type, by colour, by texture, etc.",
        ]
    elif topic == "Seasonal changes":
        questions = [
            "1. Name the 4 seasons.",
            "2. What season is it now?",
            "3. When is it cold? (spring, summer, autumn, winter)",
            "4. When do flowers grow?",
            "5. When do leaves fall from trees?",
            "6. When is the weather hot and sunny?",
            "7. In winter, what happens to plants?",
            "8. How do animals change in winter?",
            "9. Draw a tree in 2 different seasons.",
            "10. What clothes do we wear in winter?",
        ]
        answers = [
            "spring, summer, autumn, winter",
            "student's own answer (based on current month)",
            "winter (and autumn)",
            "spring (and summer)",
            "autumn",
            "summer",
            "many plants die, others rest and become dormant",
            "some sleep (hibernation), some grow winter coats",
            "drawing (e.g., green in summer, brown in winter)",
            "warm clothes: coat, hat, scarf, gloves, boots",
        ]
    elif topic == "Light and dark":
        questions = [
            "1. What gives us light during the day?",
            "2. What gives us light at night?",
            "3. Can you see in complete darkness?",
            "4. Name 3 things that give light.",
            "5. Name 3 things that are dark.",
            "6. What makes a shadow?",
            "7. Draw the sun and show light coming from it.",
            "8. When is it dark outside?",
            "9. Are shadows always the same size?",
            "10. Can light travel through glass?",
        ]
        answers = [
            "the sun",
            "the moon, stars, electric lights, candles",
            "no (you need some light)",
            "student's own answer (e.g., sun, lamp, fire, torch, candle)",
            "student's own answer (e.g., cave, night sky, inside a cupboard)",
            "when light is blocked by an object",
            "drawing (sun with rays of light)",
            "at night (after sunset)",
            "no (shadows change size as light position changes)",
            "yes",
        ]
    elif topic == "Floating and sinking":
        objects = ["ball", "apple", "feather", "stone", "wood", "coin", "cork", "sponge"]
        questions = [
            f"1. Does a {random.choice(objects)} float or sink in water?",
            "2. What floats on water?",
            "3. What sinks in water?",
            "4. Can a metal boat float?",
            "5. Why do heavy things sometimes float?",
            "6. Name 3 things that float.",
            "7. Name 3 things that sink.",
            "8. Is a beach ball heavy or light?",
            "9. Draw something floating on water.",
            "10. Can you change whether something floats or sinks?",
        ]
        answers = [
            "student's own answer (varies by object)",
            "student's own answer (e.g., wood, cork, leaves, boats)",
            "student's own answer (e.g., stones, coins, metals)",
            "yes (if it's shaped properly and not too heavy)",
            "because of their shape and what they're made of",
            "student's own answer (e.g., wood, cork, boat, apple)",
            "student's own answer (e.g., stone, coin, key)",
            "light",
            "drawing (e.g., toy boat, duck, log)",
            "yes (by changing the object or filling it with air)",
        ]
    elif topic == "Sound and hearing":
        questions = [
            "1. What do we use to hear sounds?",
            "2. Name 5 sounds you can hear.",
            "3. Can sound travel through water?",
            "4. Can sound travel through walls?",
            "5. What makes a sound?",
            "6. Is a whisper loud or quiet?",
            "7. Is a shout loud or quiet?",
            "8. What is your favourite sound?",
            "9. Draw something that makes a loud sound.",
            "10. How can you make a quiet sound become louder?",
        ]
        answers = [
            "ears",
            "student's own answer (e.g., music, birds, cars, voices, rain)",
            "yes",
            "yes (sound travels slower)",
            "vibrations (something moving)",
            "quiet",
            "loud",
            "student's own answer (e.g., music, birdsong, laughter)",
            "drawing (e.g., drum, bell, trumpet, siren)",
            "move closer to the sound, or make the vibrations bigger",
        ]
    else:
        questions = [f"{i + 1}. Year 1 Science practice question {i + 1}" for i in range(10)]
        answers = [f"answer {i + 1}" for i in range(10)]

    content = f"Science Homework - Year 1 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year2_homework(topic: str, index: int) -> tuple:
    """Year 2 Science作业（6-7 岁），返回 (content, correct_answers)"""
    if topic == "Animals and their habitats":
        questions = [
            "1. What is a habitat?",
            "2. Name 3 animals that live in water.",
            "3. Name 3 animals that live on land.",
            "4. Name 3 animals that can fly.",
            "5. What does a frog need to live?",
            "6. Where do squirrels live?",
            "7. What is a food chain? Draw one.",
            "8. In a food chain: plant → rabbit → fox. Which eats which?",
            "9. Why do some animals live in water?",
            "10. How are animals suited to their habitats?",
        ]
        answers = [
            "a place where an animal lives",
            "student's own answer (e.g., fish, frog, duck, whale)",
            "student's own answer (e.g., cat, dog, bird, squirrel)",
            "student's own answer (e.g., bird, butterfly, bat, bee)",
            "water, food, shelter",
            "in trees",
            "drawing (e.g., grass → caterpillar → bird → hawk)",
            "rabbit eats plant, fox eats rabbit",
            "they have gills to breathe, fins to swim, etc.",
            "they have adapted body parts (e.g., birds have wings, fish have fins)",
        ]
    elif topic == "Plants - growth and care":
        questions = [
            "1. What 3 things do plants need to grow?",
            "2. Why do plants need water?",
            "3. Why do plants need light?",
            "4. What does a plant need soil for?",
            "5. Name the parts of a plant.",
            "6. What do roots do?",
            "7. What do leaves do?",
            "8. How long does it take a seed to grow?",
            "9. How can we look after a plant?",
            "10. Can plants grow without soil? (yes or no - explain)",
        ]
        answers = [
            "water, sunlight, soil (nutrients)",
            "to carry nutrients and keep it firm",
            "for photosynthesis (to make food)",
            "to hold the plant and provide nutrients",
            "roots, stem, leaves, flowers, seeds",
            "absorb water and nutrients from soil",
            "make food using sunlight (photosynthesis)",
            "varies by plant (weeks to months)",
            "water regularly, give it sunlight, keep it warm",
            "yes, if they get nutrients (in hydroponic systems)",
        ]
    elif topic == "Human growth and development":
        questions = [
            "1. What stages of growth are there in humans?",
            "2. A human baby needs: (name 3 things)",
            "3. What do children need to grow?",
            "4. How do we grow taller?",
            "5. At what age do humans stop growing?",
            "6. How do babies move?",
            "7. How do toddlers move?",
            "8. What can teenagers do that babies cannot?",
            "9. Draw the life stages of a human.",
            "10. How long is human childhood?",
        ]
        answers = [
            "baby, toddler, child, teenager, adult, elderly",
            "food, water, warmth, love, care",
            "healthy food, exercise, sleep, care, education",
            "genetics, good diet, exercise",
            "around 18-25 years old",
            "crying, moving arms and legs",
            "walking, running, climbing",
            "talk, read, play, use technology, make decisions",
            "drawing (showing growth from baby to adult)",
            "roughly 18 years (to adulthood)",
        ]
    elif topic == "Uses of everyday materials":
        questions = [
            "1. What materials are books made from?",
            "2. What materials are shoes made from?",
            "3. What materials are windows made from?",
            "4. Why is plastic useful?",
            "5. Why is metal useful?",
            "6. Can wood be bent?",
            "7. Is rubber waterproof?",
            "8. Why do we use different materials for different things?",
            "9. Sort these: plastic, wood, metal, glass, fabric - where would you find each?",
            "10. Which materials can we recycle?",
        ]
        answers = [
            "paper (wood pulp)",
            "leather, rubber, plastic, canvas, etc.",
            "glass",
            "it's cheap, light, waterproof, can be shaped",
            "it's strong, can conduct electricity, can be shaped",
            "yes (some types)",
            "yes",
            "because different materials have different properties for different jobs",
            "plastic: bags; wood: tables; metal: cutlery; glass: jars; fabric: clothes",
            "plastic, metal, glass, paper, fabric (some types)",
        ]
    elif topic == "Weather and seasons":
        questions = [
            "1. What is weather?",
            "2. Name 4 types of weather.",
            "3. How do we measure temperature?",
            "4. What is rain?",
            "5. What is wind?",
            "6. When is the weather hottest?",
            "7. When is the weather coldest?",
            "8. How do animals prepare for winter?",
            "9. What clothes do we wear in different seasons?",
            "10. Record the weather for one week - what did you notice?",
        ]
        answers = [
            "conditions in the air (temperature, rain, wind, sun)",
            "student's own answer (rain, snow, sunny, windy, cloudy, hail)",
            "with a thermometer",
            "water falling from clouds",
            "moving air",
            "summer",
            "winter",
            "hibernate, migrate, grow thicker fur, store food",
            "summer: light clothes; winter: thick, warm clothes",
            "student's own observations (e.g., temperature changes, weather patterns)",
        ]
    elif topic == "Habitats and food chains":
        questions = [
            "1. What is a habitat?",
            "2. What is a food chain?",
            "3. Draw a simple food chain: plant → animal → predator",
            "4. What do herbivores eat?",
            "5. What do carnivores eat?",
            "6. What do omnivores eat?",
            "7. In this chain: grass → rabbit → fox, who is the predator?",
            "8. What would happen if all the plants died?",
            "9. Name 3 different habitats.",
            "10. How are animals in different habitats different?",
        ]
        answers = [
            "a place where an animal or plant lives",
            "the flow of food/energy: producer → consumer → predator",
            "drawing (arrows showing who eats what)",
            "plants only",
            "meat/animals only",
            "both plants and animals",
            "the fox",
            "the rabbits would starve, then the fox would starve",
            "student's own answer (e.g., forest, ocean, desert, pond)",
            "they are adapted to their environment (camouflage, diet, movement)",
        ]
    elif topic == "Living things":
        questions = [
            "1. What is a living thing?",
            "2. Name 5 living things.",
            "3. Name 5 non-living things.",
            "4. What do all living things need?",
            "5. Can plants move?",
            "6. Do plants breathe?",
            "7. How do plants reproduce?",
            "8. How do animals reproduce?",
            "9. Draw and label a plant and an animal.",
            "10. What is the difference between living and non-living?",
        ]
        answers = [
            "something that is alive and can grow, move, eat, and reproduce",
            "student's own answer (e.g., dog, tree, bird, flower, human)",
            "student's own answer (e.g., rock, table, car, water, sand)",
            "food, water, air, sunlight (or energy)",
            "yes, slowly (towards light, roots towards water)",
            "yes (through stomata on leaves)",
            "through seeds",
            "through mating/reproduction",
            "drawing (with labels: stem, leaves, roots, head, body, legs)",
            "living things grow, eat, move, feel, reproduce; non-living don't",
        ]
    elif topic == "Materials around us":
        questions = [
            "1. Name 5 different materials.",
            "2. Which materials are natural?",
            "3. Which materials are man-made?",
            "4. What properties does wood have?",
            "5. What properties does plastic have?",
            "6. Can you change the shape of paper?",
            "7. Can you change the shape of metal?",
            "8. What material is best for a raincoat? Why?",
            "9. Sort materials by: hard/soft, bendy/stiff",
            "10. How are materials changed to make things?",
        ]
        answers = [
            "student's own answer (e.g., wood, plastic, metal, glass, fabric, rubber)",
            "wood, stone, cotton, wool, leather, rubber",
            "plastic, glass, steel, nylon, paper",
            "hard, can be shaped by cutting/sanding, can rot, can burn",
            "waterproof, light, can be bent, doesn't rot, can be recycled",
            "yes (tear, fold, crumple)",
            "yes (bend, fold, hammer, melt)",
            "rubber or plastic (waterproof)",
            "student's own sorting (hard: stone, metal; soft: fabric, foam)",
            "by heating, cutting, folding, mixing, processing",
        ]
    else:
        questions = [f"{i + 1}. Year 2 Science practice question {i + 1}" for i in range(10)]
        answers = [f"answer {i + 1}" for i in range(10)]

    content = f"Science Homework - Year 2 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year3_homework(topic: str, index: int) -> tuple:
    """Year 3 Science作业（7-8 岁），返回 (content, correct_answers)"""
    if topic == "Plants and photosynthesis":
        questions = [
            "1. What is photosynthesis?",
            "2. What do plants need for photosynthesis?",
            "3. What do plants make during photosynthesis?",
            "4. What gas do plants release?",
            "5. Why are leaves green?",
            "6. What is chlorophyll?",
            "7. Where in a plant does photosynthesis happen?",
            "8. Do all plants have leaves?",
            "9. Can plants photosynthesise at night?",
            "10. How would a plant die if kept in darkness?",
        ]
        answers = [
            "the process where plants make their own food using light",
            "sunlight, water, carbon dioxide, and chlorophyll",
            "glucose (sugar) and oxygen",
            "oxygen",
            "because of chlorophyll (a green pigment)",
            "the green pigment in plants that captures light",
            "in the leaves (in chloroplasts)",
            "no (some have fronds, needles, or no obvious leaves)",
            "no (it needs light)",
            "without light, it can't photosynthesise, so it can't make food",
        ]
    elif topic == "Animals - diet and teeth":
        questions = [
            "1. What are herbivores?",
            "2. What are carnivores?",
            "3. What are omnivores?",
            "4. Name 3 herbivores.",
            "5. Name 3 carnivores.",
            "6. Name 3 omnivores.",
            "7. What do different teeth do?",
            "8. What are incisors for?",
            "9. What are molars for?",
            "10. How are animal teeth suited to their diet?",
        ]
        answers = [
            "animals that eat only plants",
            "animals that eat only meat",
            "animals that eat plants and meat",
            "student's own answer (e.g., cow, sheep, rabbit, deer)",
            "student's own answer (e.g., lion, shark, eagle, cat)",
            "student's own answer (e.g., human, pig, bear, dog)",
            "cutting (incisors), tearing (canines), grinding (molars)",
            "cutting and slicing food",
            "grinding and crushing food",
            "herbivores have flat molars for grinding; carnivores have sharp teeth for tearing",
        ]
    elif topic == "Rocks and soil":
        questions = [
            "1. What are the 3 main types of rock?",
            "2. What is igneous rock?",
            "3. What is sedimentary rock?",
            "4. What is metamorphic rock?",
            "5. What is soil made from?",
            "6. Why is soil important?",
            "7. What is a fossil?",
            "8. How do rocks change over time?",
            "9. Can rocks be broken down into soil?",
            "10. Why do different places have different soils?",
        ]
        answers = [
            "igneous, sedimentary, metamorphic",
            "rock formed from cooled lava (volcanic)",
            "rock formed from compressed sediment (layers)",
            "rock formed from other rock changed by heat/pressure",
            "broken rock, dead plants, dead animals, air, water",
            "plants grow in it, animals live in it, filters water, stores nutrients",
            "the preserved remains of a dead organism",
            "by weathering (wind, rain, ice), erosion, and heating/cooling cycles",
            "yes, over thousands of years",
            "based on local rock types, climate, and weathering patterns",
        ]
    elif topic == "Light and shadows":
        questions = [
            "1. What is light?",
            "2. Can light travel in straight lines?",
            "3. What is a shadow?",
            "4. What causes a shadow?",
            "5. Why do shadows change during the day?",
            "6. Are shadows always the same length?",
            "7. Does light travel through all materials?",
            "8. What materials are opaque?",
            "9. What materials are translucent?",
            "10. What materials are transparent?",
        ]
        answers = [
            "energy that travels in waves and allows us to see",
            "yes",
            "a dark area where light is blocked",
            "an object blocking light",
            "because the sun's position changes",
            "no (depends on light direction)",
            "no (blocked by opaque objects)",
            "wood, metal, stone (block all light)",
            "paper, frosted glass (let some light through)",
            "clear glass, air (let all light through)",
        ]
    elif topic == "Forces and magnets":
        questions = [
            "1. What is a force?",
            "2. Name 3 types of forces.",
            "3. What does a magnet attract?",
            "4. Do all metals stick to magnets?",
            "5. What is magnetism?",
            "6. What are magnetic poles?",
            "7. Do opposite poles attract or repel?",
            "8. Do same poles attract or repel?",
            "9. What is the Earth's magnetic field?",
            "10. What are non-contact forces?",
        ]
        answers = [
            "a push, pull, or twist that changes motion",
            "push, pull, friction, gravity, magnetism",
            "ferrous metals (iron, steel, nickel, cobalt)",
            "no (only ferrous metals)",
            "the force that attracts ferrous metals to magnets",
            "north and south ends of a magnet",
            "attract",
            "repel",
            "the magnetic field that surrounds Earth, used by compass needles",
            "forces that work without touching (gravity, magnetism)",
        ]
    elif topic == "States of matter":
        questions = [
            "1. What are the 3 states of matter?",
            "2. What is a solid?",
            "3. What is a liquid?",
            "4. What is a gas?",
            "5. Give an example of each state.",
            "6. Can solids change shape?",
            "7. Can liquids change shape?",
            "8. Can gases be contained?",
            "9. What is melting?",
            "10. What is evaporation?",
        ]
        answers = [
            "solid, liquid, gas",
            "has a fixed shape and volume (e.g., ice, rock, table)",
            "has a fixed volume but no fixed shape (e.g., water, milk)",
            "has no fixed shape or volume (e.g., air, steam)",
            "solid: ice/rock; liquid: water; gas: air/steam",
            "no (have fixed shape)",
            "yes (take the shape of their container)",
            "yes (if contained)",
            "when a solid becomes a liquid (ice → water)",
            "when a liquid becomes a gas (water → steam)",
        ]
    elif topic == "Electrical circuits (simple)":
        questions = [
            "1. What do you need to make a simple circuit?",
            "2. Does a circuit need to be closed or open?",
            "3. What is a switch?",
            "4. What does a battery do in a circuit?",
            "5. What is a conductor?",
            "6. What is an insulator?",
            "7. Will a circuit work if it has a gap?",
            "8. What happens when you open a switch?",
            "9. Draw a simple circuit with a bulb.",
            "10. Why don't we touch bare wires in circuits?",
        ]
        answers = [
            "a battery, wires, and a bulb (or other component)",
            "closed (to allow electricity to flow)",
            "a device that breaks the circuit on or off",
            "provides electrical energy",
            "a material that lets electricity flow (copper, steel)",
            "a material that stops electricity (rubber, plastic)",
            "no (electricity can't flow across gaps)",
            "the circuit breaks and the bulb turns off",
            "drawing (battery, wires, bulb in a loop)",
            "because electricity can cause injury",
        ]
    elif topic == "Sound and vibrations":
        questions = [
            "1. What makes sound?",
            "2. How does sound travel?",
            "3. Can sound travel through solids?",
            "4. Can sound travel through liquids?",
            "5. Can sound travel through gases?",
            "6. What is a vibration?",
            "7. What is pitch?",
            "8. What is volume?",
            "9. How do speakers make sound?",
            "10. Why do we hear differently at different distances?",
        ]
        answers = [
            "vibrations (something moving back and forth)",
            "as vibrations (waves) through materials",
            "yes",
            "yes",
            "yes",
            "a repeated, rapid movement back and forth",
            "how high or low a sound is",
            "how loud or quiet a sound is",
            "electricity makes a cone vibrate, which vibrates air",
            "sound waves spread out and get weaker the further they travel",
        ]
    else:
        questions = [f"{i + 1}. Year 3 Science practice question {i + 1}" for i in range(10)]
        answers = [f"answer {i + 1}" for i in range(10)]

    content = f"Science Homework - Year 3 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year4_homework(topic: str, index: int) -> tuple:
    """Year 4 Science作业（8-9 岁），返回 (content, correct_answers)"""
    if topic == "Living things and habitats":
        questions = [
            "1. Classify these: grasshopper, ant, beetle, spider, woodlouse - what are they?",
            "2. How many legs do insects have?",
            "3. What is an adaptation?",
            "4. Give examples of animal adaptations.",
            "5. How are desert plants adapted?",
            "6. How are arctic animals adapted?",
            "7. Draw a food web with at least 6 organisms.",
            "8. What happens if one organism is removed from a food chain?",
            "9. Name 3 endangered animals.",
            "10. What can we do to protect habitats?",
        ]
        answers = [
            "insects (and arachnids for spider)",
            "6 legs",
            "a feature that helps an organism survive in its environment",
            "camouflage, thick fur, sharp teeth, long roots, waxy leaves, etc.",
            "deep roots, small leaves, waxy coating to save water, ability to store water",
            "thick fur, white color for camouflage, layer of fat, small ears to keep warmth",
            "drawing (showing multiple food chains interconnected)",
            "the chain is broken and organisms above it may starve",
            "student's own answer (e.g., giant panda, rhino, polar bear, tiger)",
            "reduce pollution, protect forests, not litter, recycle, reduce habitat destruction",
        ]
    elif topic == "The digestive system":
        questions = [
            "1. What is digestion?",
            "2. Name the parts of the digestive system.",
            "3. What does the mouth do?",
            "4. What is the purpose of the stomach?",
            "5. What do the small intestines do?",
            "6. What do the large intestines do?",
            "7. How long does food take to digest?",
            "8. What is saliva?",
            "9. Why do we need to chew food?",
            "10. Draw and label the digestive system.",
        ]
        answers = [
            "the process of breaking down food into nutrients the body can use",
            "mouth, oesophagus, stomach, small intestine, large intestine, anus",
            "breaks down food (chewing) and starts digestion with saliva",
            "further breaks down food with acid and churning",
            "absorb nutrients into the bloodstream",
            "absorb water and prepare waste",
            "24-48 hours",
            "liquid that breaks down food chemically",
            "to break it down mechanically and increase surface area",
            "drawing (with all parts labelled)",
        ]
    elif topic == "States of matter and changes":
        questions = [
            "1. Define: solid, liquid, gas.",
            "2. What is melting?",
            "3. What is freezing?",
            "4. What is evaporation?",
            "5. What is condensation?",
            "6. What is the water cycle?",
            "7. At what temperature does water freeze?",
            "8. At what temperature does water boil?",
            "9. Can gases be turned into liquids?",
            "10. Draw the water cycle and label processes.",
        ]
        answers = [
            "solid: fixed shape/volume; liquid: fixed volume, no shape; gas: no fixed shape/volume",
            "solid → liquid (due to heating)",
            "liquid → solid (due to cooling)",
            "liquid → gas (at any temperature, faster when hot)",
            "gas → liquid (due to cooling)",
            "continuous cycle of water: evaporation → condensation → precipitation → collection",
            "0°C (32°F)",
            "100°C (212°F)",
            "yes (liquefaction)",
            "drawing (showing sun, water, evaporation, clouds, condensation, rain, collection)",
        ]
    elif topic == "Rocks and soils":
        questions = [
            "1. What are the 3 types of rock?",
            "2. How is igneous rock formed?",
            "3. How is sedimentary rock formed?",
            "4. How is metamorphic rock formed?",
            "5. What is the rock cycle?",
            "6. What is weathering?",
            "7. What is erosion?",
            "8. How do rocks become soil?",
            "9. What is a fossil?",
            "10. How do fossils form?",
        ]
        answers = [
            "igneous, sedimentary, metamorphic",
            "from cooled and solidified lava or magma",
            "from compressed and cemented layers of sediment",
            "from existing rock changed by heat and pressure",
            "igneous → weathering → sedimentary → heat/pressure → metamorphic → melting → igneous",
            "breaking down rock (by wind, water, ice, temperature changes)",
            "carrying away broken rock material",
            "through weathering and the actions of organisms",
            "preserved remains of dead organisms",
            "organisms die, get buried, minerals replace organic material over millions of years",
        ]
    elif topic == "Sound":
        questions = [
            "1. What is sound?",
            "2. What produces sound?",
            "3. How fast does sound travel?",
            "4. What is a sound wave?",
            "5. What is pitch?",
            "6. What is volume/loudness?",
            "7. What is the frequency of sound?",
            "8. Can sound be louder in different materials?",
            "9. What causes an echo?",
            "10. How do different animals hear sounds?",
        ]
        answers = [
            "vibrations that travel through a medium and are detected by ears",
            "vibrations of objects",
            "about 343 m/s in air (varies by medium)",
            "a pattern of vibrations traveling through a medium",
            "how high or low a sound is (determined by frequency)",
            "how intense a sound is (determined by amplitude)",
            "number of vibrations per second (measured in Hz)",
            "yes (faster in solids, slower in gases)",
            "sound reflects off hard surfaces and returns to source",
            "student's own answer (different ear structures, frequencies different animals hear)",
        ]
    elif topic == "Electricity and circuits":
        questions = [
            "1. What is electricity?",
            "2. What is a circuit?",
            "3. What is a complete circuit?",
            "4. What is a broken circuit?",
            "5. What is the difference between series and parallel circuits?",
            "6. Draw a series circuit and a parallel circuit.",
            "7. In series: if one bulb breaks, what happens?",
            "8. In parallel: if one bulb breaks, what happens?",
            "9. What is resistance?",
            "10. How do switches work?",
        ]
        answers = [
            "flow of electrons through a conductor",
            "path that electricity follows",
            "a closed path allowing electricity to flow and power components",
            "path with a break, preventing electricity from flowing",
            "series: single loop (all in one path); parallel: multiple paths",
            "drawing (series: all in one line; parallel: multiple branches)",
            "all bulbs turn off (circuit is broken)",
            "other bulbs stay on (electricity can still flow through other paths)",
            "opposition to the flow of electricity",
            "by breaking/completing a circuit to turn power on/off",
        ]
    elif topic == "Light and vision":
        questions = [
            "1. How do we see?",
            "2. What is light?",
            "3. What are the primary colours of light?",
            "4. What are the primary colours of pigment?",
            "5. How are rainbows formed?",
            "6. What is reflection?",
            "7. What is refraction?",
            "8. Can light be bent?",
            "9. How do mirrors work?",
            "10. How does the eye focus light?",
        ]
        answers = [
            "light enters the eye, is focused by lens, image on retina, signal to brain",
            "electromagnetic waves that can be seen",
            "red, green, blue (RGB)",
            "red, yellow, blue (RYB)",
            "white light refracts through water droplets, splitting into spectrum colours",
            "light bouncing off a surface",
            "light bending when passing between different materials",
            "yes, when passing from one material to another (refraction)",
            "reflect light to show images",
            "the lens changes shape to focus light on the retina",
        ]
    elif topic == "The water cycle":
        questions = [
            "1. What is the water cycle?",
            "2. What is evaporation?",
            "3. What is condensation?",
            "4. What is precipitation?",
            "5. What is collection?",
            "6. Where does water go when it evaporates?",
            "7. What drives the water cycle?",
            "8. How do clouds form?",
            "9. What happens to water that falls as rain?",
            "10. Draw and explain the water cycle.",
        ]
        answers = [
            "continuous cycle: evaporation → condensation → precipitation → collection → evaporation",
            "liquid water → gas (water vapour) due to heating",
            "gas (water vapour) → liquid water due to cooling",
            "water falling from clouds (rain, snow, sleet, hail)",
            "water gathering in seas, rivers, lakes, underground",
            "into the atmosphere as water vapour",
            "heat from the sun",
            "water vapour condenses when it cools in the atmosphere",
            "evaporates, infiltrates soil, runs into rivers/seas, or is absorbed by plants",
            "drawing (showing sun, earth, clouds, rain, rivers, ocean, and labels)",
        ]
    else:
        questions = [f"{i + 1}. Year 4 Science practice question {i + 1}" for i in range(10)]
        answers = [f"answer {i + 1}" for i in range(10)]

    content = f"Science Homework - Year 4 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year5_homework(topic: str, index: int) -> tuple:
    """Year 5 Science作业（9-10 岁），返回 (content, correct_answers)"""
    if topic == "Life cycles of plants and animals":
        questions = [
            "1. What is a life cycle?",
            "2. Describe the life cycle of a plant.",
            "3. Describe the life cycle of an insect (e.g., butterfly).",
            "4. What are the stages of butterfly metamorphosis?",
            "5. Describe the life cycle of a mammal (e.g., dog).",
            "6. What is reproduction?",
            "7. What is sexual reproduction?",
            "8. What is asexual reproduction?",
            "9. How do plants reproduce?",
            "10. Compare plant and animal life cycles.",
        ]
        answers = [
            "the series of changes an organism goes through from birth to death",
            "seed germination → growth → flowering → reproduction → seed dispersal → death",
            "egg → larva → pupa → adult",
            "egg, larva (caterpillar), pupa (chrysalis), adult butterfly",
            "birth → growth → reaching maturity → reproduction → old age → death",
            "the process of creating new organisms",
            "creation of offspring from two parents (involves genetic mixing)",
            "creation of offspring from one parent (no genetic mixing)",
            "sexually (through pollen and seeds) and asexually (vegetative reproduction)",
            "plants have longer life cycles; animals vary; plants can reproduce asexually",
        ]
    elif topic == "Properties and changes of materials":
        questions = [
            "1. What are material properties?",
            "2. List 10 material properties.",
            "3. What is a reversible change?",
            "4. What is an irreversible change?",
            "5. Give examples of reversible changes.",
            "6. Give examples of irreversible changes.",
            "7. What is combustion?",
            "8. What is dissolving?",
            "9. Can all materials dissolve?",
            "10. How do we separate mixtures?",
        ]
        answers = [
            "characteristics or features of materials (hardness, colour, texture, etc.)",
            "hardness, strength, flexibility, transparency, conductivity, magnetism, solubility, melting point, etc.",
            "a change that can be undone (e.g., freezing water, dissolving sugar)",
            "a change that cannot be undone (e.g., burning paper, cooking egg)",
            "melting, freezing, evaporation, condensation, dissolving, stretching",
            "burning, cooking, rusting, rotting, chemical reactions",
            "burning (combining with oxygen to release energy)",
            "a solid mixing with liquid to form a solution",
            "no (some are insoluble, e.g., sand in water)",
            "filtering (solids), evaporation (dissolved solids), chromatography (colours)",
        ]
    elif topic == "Earth and space":
        questions = [
            "1. What is the Earth?",
            "2. What is the Sun?",
            "3. What is the Moon?",
            "4. What causes day and night?",
            "5. What causes the seasons?",
            "6. What is a year?",
            "7. What is the solar system?",
            "8. How many planets are in our solar system?",
            "9. Name the planets in order from the Sun.",
            "10. What is gravity?",
        ]
        answers = [
            "our planet, a sphere orbiting the Sun",
            "a star at the center of the solar system",
            "Earth's natural satellite",
            "Earth's rotation on its axis",
            "Earth's tilt as it orbits the Sun",
            "time for Earth to orbit the Sun (365 days)",
            "the Sun and all objects orbiting it (8 planets, moons, asteroids, comets)",
            "8 planets",
            "Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune",
            "force of attraction between objects (keeps Earth orbiting Sun, holds us on Earth)",
        ]
    elif topic == "Forces and motion":
        questions = [
            "1. What is a force?",
            "2. What are the types of forces?",
            "3. What is friction?",
            "4. What is air resistance?",
            "5. What is water resistance?",
            "6. How do forces cause motion?",
            "7. How do forces slow motion?",
            "8. What is Newton's First Law of Motion?",
            "9. What is Newton's Second Law of Motion?",
            "10. What is Newton's Third Law of Motion?",
        ]
        answers = [
            "push or pull that causes change in motion",
            "contact (friction, air/water resistance) and non-contact (gravity, magnetism)",
            "force opposing motion between surfaces in contact",
            "force opposing motion through air",
            "force opposing motion through water",
            "unbalanced forces cause acceleration",
            "opposing forces slow or stop motion",
            "object at rest stays at rest, object in motion stays in motion unless acted upon",
            "force = mass × acceleration (F=ma)",
            "for every action, there is an equal and opposite reaction",
        ]
    elif topic == "Gravity and weight":
        questions = [
            "1. What is gravity?",
            "2. What is weight?",
            "3. What is mass?",
            "4. Are weight and mass the same?",
            "5. How do we measure weight?",
            "6. What causes weight?",
            "7. Does gravity work in space?",
            "8. Would you weigh less on the Moon? Why?",
            "9. What would happen if Earth had no gravity?",
            "10. How is gravity used in sports?",
        ]
        answers = [
            "force of attraction between objects (especially towards Earth)",
            "the force of gravity acting on an object (measured in Newtons)",
            "amount of matter in an object (measured in kg)",
            "no (mass is constant, weight varies with gravity)",
            "with a spring balance or weighing scale",
            "gravitational force of Earth pulling down",
            "yes (weaker further from Earth)",
            "yes (Moon's gravity is weaker than Earth's, about 1/6)",
            "atmosphere would escape, objects would float, life impossible",
            "gravity affects ball trajectories, water flow, athletic movements",
        ]
    elif topic == "Levers and pulleys":
        questions = [
            "1. What is a lever?",
            "2. What are the parts of a lever?",
            "3. How many classes of levers are there?",
            "4. Give examples of Class 1 levers.",
            "5. Give examples of Class 2 levers.",
            "6. Give examples of Class 3 levers.",
            "7. What is a pulley?",
            "8. How do pulleys help us?",
            "9. What is mechanical advantage?",
            "10. How are levers used in the body?",
        ]
        answers = [
            "a simple machine: a rigid bar that pivots on a fulcrum",
            "load, effort, fulcrum (pivot point)",
            "3 classes",
            "seesaw, crowbar, scissors, pliers",
            "wheelbarrow, nutcracker, bottle opener",
            "tweezers, fishing rod, human arm",
            "a simple machine: wheel with a rope/cable for lifting",
            "change direction of force, reduce effort needed, lift heavy objects",
            "how much easier a machine makes a task (effort × distance = load × distance)",
            "bones are levers, muscles apply effort, joints are fulcrums",
        ]
    elif topic == "Evolution and inheritance":
        questions = [
            "1. What is evolution?",
            "2. What is natural selection?",
            "3. What is adaptation?",
            "4. Give examples of adaptations.",
            "5. What is inheritance?",
            "6. How do characteristics pass to offspring?",
            "7. What is variation?",
            "8. What is mutation?",
            "9. How does evolution happen?",
            "10. Name scientists who studied evolution.",
        ]
        answers = [
            "gradual change of organisms over long periods",
            "process where organisms best suited to environment survive and reproduce",
            "feature that helps organism survive",
            "student's own (e.g., camouflage, thick fur, sharp teeth, strong legs)",
            "passing characteristics from parents to offspring",
            "through genes (DNA) passed from parents",
            "differences between individuals of the same species",
            "permanent change in genes",
            "variation + natural selection + time = evolution",
            "Charles Darwin, Jean-Baptiste Lamarck, Gregor Mendel",
        ]
    elif topic == "Respiration and gas exchange":
        questions = [
            "1. What is respiration?",
            "2. What happens during respiration?",
            "3. What gas do we need to survive?",
            "4. What gas do we breathe out?",
            "5. What is the respiratory system?",
            "6. What do lungs do?",
            "7. What is gas exchange?",
            "8. Where does gas exchange happen?",
            "9. What is aerobic respiration?",
            "10. What is anaerobic respiration?",
        ]
        answers = [
            "process of releasing energy from food using oxygen",
            "food + oxygen → energy + carbon dioxide + water",
            "oxygen",
            "carbon dioxide (and oxygen, nitrogen, argon)",
            "nose, trachea, bronchi, lungs, diaphragm",
            "absorb oxygen and release carbon dioxide",
            "oxygen enters blood, carbon dioxide leaves blood",
            "in the alveoli of the lungs",
            "respiration using oxygen (produces more energy)",
            "respiration without oxygen (produces less energy, causes lactic acid buildup)",
        ]
    else:
        questions = [f"{i + 1}. Year 5 Science practice question {i + 1}" for i in range(10)]
        answers = [f"answer {i + 1}" for i in range(10)]

    content = f"Science Homework - Year 5 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


def _generate_year6_homework(topic: str, index: int) -> tuple:
    """Year 6 Science作业（10-11 岁），返回 (content, correct_answers)"""
    if topic == "Circulatory system and health":
        questions = [
            "1. What is the circulatory system?",
            "2. What does the heart do?",
            "3. What is blood pressure?",
            "4. What is a heartbeat?",
            "5. What are arteries?",
            "6. What are veins?",
            "7. What are capillaries?",
            "8. What does blood transport?",
            "9. What factors affect heart health?",
            "10. How does exercise affect the heart?",
        ]
        answers = [
            "system transporting blood around the body (heart, blood vessels, blood)",
            "pumps blood around the body",
            "force blood exerts on vessel walls",
            "one complete cycle of heart contracting and relaxing",
            "vessels carrying blood away from heart (thick, elastic)",
            "vessels carrying blood back to heart (thin walls, valves)",
            "tiny vessels where gas/nutrient exchange happens",
            "oxygen, nutrients, hormones, antibodies, waste",
            "diet, exercise, stress, smoking, alcohol",
            "makes it stronger, increases efficiency, lowers resting heart rate",
        ]
    elif topic == "The nervous system and reactions":
        questions = [
            "1. What is the nervous system?",
            "2. What are the two parts of the nervous system?",
            "3. What does the brain do?",
            "4. What does the spinal cord do?",
            "5. What are reflexes?",
            "6. What is a reflex arc?",
            "7. Give examples of reflexes.",
            "8. How fast are reflex reactions?",
            "9. Why are reflexes important?",
            "10. How do we react to stimuli?",
        ]
        answers = [
            "system that controls body functions and reactions (brain, spinal cord, nerves)",
            "central nervous system (CNS) and peripheral nervous system (PNS)",
            "controls thoughts, emotions, memory, sensations, voluntary movement",
            "carries signals between brain and body",
            "automatic, rapid responses to stimuli (no thinking)",
            "stimulus → sensory neuron → spinal cord → motor neuron → response",
            "pulling hand away from hot object, closing eyes to bright light, pupil dilation",
            "very fast (milliseconds) - no brain involved",
            "protect body from danger before conscious thought",
            "stimulus → sensory receptors → nervous system → motor response",
        ]
    elif topic == "Classification of living things":
        questions = [
            "1. What is classification?",
            "2. What are the main groups of living things?",
            "3. What are vertebrates?",
            "4. What are invertebrates?",
            "5. Name the 5 classes of vertebrates.",
            "6. Give examples of each vertebrate class.",
            "7. What are invertebrates? Give examples.",
            "8. What is a kingdom?",
            "9. What is a phylum?",
            "10. Classify a human and an insect.",
        ]
        answers = [
            "sorting organisms into groups based on features",
            "animals, plants, fungi, bacteria (protists)",
            "animals with a backbone (mammals, birds, reptiles, amphibians, fish)",
            "animals without a backbone (insects, worms, jellyfish, molluscs, crustaceans)",
            "fish, amphibians, reptiles, birds, mammals",
            "fish: sharks; amphibians: frogs; reptiles: snakes; birds: eagles; mammals: dogs",
            "insects, worms, molluscs (snails), crustaceans (crabs), arachnids (spiders)",
            "broadest category of classification",
            "major group within a kingdom (e.g., Chordata)",
            "human: animal, chordata, mammal; insect: animal, arthropoda, insecta",
        ]
    elif topic == "Electricity and circuits (advanced)":
        questions = [
            "1. What is electrical current?",
            "2. What is voltage?",
            "3. What is resistance?",
            "4. What is Ohm's Law?",
            "5. What are conductors and insulators?",
            "6. What is the difference between AC and DC electricity?",
            "7. How are household circuits wired?",
            "8. What is a fuse?",
            "9. What is an electromagnet?",
            "10. How is electricity generated?",
        ]
        answers = [
            "flow of electrons through a circuit (measured in amps)",
            "electrical potential difference (measured in volts)",
            "opposition to current flow (measured in ohms)",
            "V = I × R (voltage = current × resistance)",
            "conductors: let electricity flow (copper, steel); insulators: don't (rubber, plastic)",
            "AC: alternating current (oscillates); DC: direct current (constant direction)",
            "parallel (allows independent on/off); household wiring is series/parallel combination",
            "safety device that breaks circuit if current too high",
            "coil of wire that becomes magnetic when current passes through",
            "generators (mechanical), solar cells (light), batteries (chemical)",
        ]
    elif topic == "Light - reflection and refraction":
        questions = [
            "1. What are the properties of light?",
            "2. What is the speed of light?",
            "3. What is reflection?",
            "4. What is the Law of Reflection?",
            "5. What is refraction?",
            "6. Why does light refract?",
            "7. What is a convex lens?",
            "8. What is a concave lens?",
            "9. How does a microscope work?",
            "10. How does a telescope work?",
        ]
        answers = [
            "travels in straight lines, reflects, refracts, can be absorbed/transmitted",
            "about 300,000 km/s (in vacuum)",
            "light bouncing off a surface",
            "angle of incidence = angle of reflection",
            "light bending when entering different material",
            "light travels at different speeds in different materials",
            "thicker in middle, focuses light (magnifies, real inverted images)",
            "thinner in middle, spreads light (magnifies, virtual upright images)",
            "uses two convex lenses to magnify small objects",
            "uses lenses to magnify distant objects (astronomical telescope)",
        ]
    elif topic == "Evolution and natural selection":
        questions = [
            "1. Define evolution.",
            "2. What is natural selection?",
            "3. What is survival of the fittest?",
            "4. How does adaptation lead to evolution?",
            "5. Give examples of evolved adaptations.",
            "6. What is a fossil record?",
            "7. What does fossil evidence show?",
            "8. How long does evolution take?",
            "9. What causes variation in a population?",
            "10. How are humans and apes related evolutionarily?",
        ]
        answers = [
            "gradual change of organisms over millions of years",
            "individuals best suited to environment survive and pass genes to offspring",
            "organisms best adapted to their environment are most likely to survive",
            "advantageous adaptations become more common in population over generations",
            "bird wings, fish fins, thick fur in cold climates, camouflage, poisonous frogs",
            "layers of rock containing fossils showing organism remains over time",
            "organisms change over time; extinction; gradual change; common ancestors",
            "millions of years (very slow process)",
            "mutations, sexual reproduction, gene mixing",
            "share common ancestor; humans are primates; share ~98-99% DNA with apes",
        ]
    elif topic == "Forces - pressure and moments":
        questions = [
            "1. What is pressure?",
            "2. What is the formula for pressure?",
            "3. How does area affect pressure?",
            "4. What is a moment?",
            "5. What is the formula for moment?",
            "6. What is equilibrium?",
            "7. What is a lever's mechanical advantage?",
            "8. Give examples of pressure in daily life.",
            "9. Give examples of moments in daily life.",
            "10. How do we calculate resultant forces?",
        ]
        answers = [
            "force per unit area (force/area)",
            "P = F/A (pressure = force ÷ area)",
            "smaller area = greater pressure for same force",
            "turning effect of a force about a pivot",
            "M = F × d (moment = force × perpendicular distance from pivot)",
            "when all forces and moments are balanced (no acceleration)",
            "relationship between effort, load, and lever design",
            "pressure in tyres, water pressure, atmospheric pressure, knife cutting",
            "seesaws, door hinges, spanners turning bolts, pedals on bike",
            "add forces in same direction, subtract in opposite directions",
        ]
    elif topic == "Properties of materials (advanced)":
        questions = [
            "1. What are thermal properties?",
            "2. What is thermal conductivity?",
            "3. What is specific heat capacity?",
            "4. What are electrical properties?",
            "5. What is electrical conductivity?",
            "6. What are optical properties?",
            "7. What is density?",
            "8. How is density calculated?",
            "9. What are magnetic properties?",
            "10. How are material properties used in design?",
        ]
        answers = [
            "how materials respond to heat (thermal conductivity, specific heat, melting point)",
            "how well material conducts heat (metals are good, insulators are poor)",
            "energy needed to raise temperature of 1kg by 1°C",
            "how materials respond to electricity (conductivity, resistance)",
            "how well material conducts electricity",
            "how materials interact with light (colour, transparency, reflection)",
            "mass per unit volume (kg/m³)",
            "D = m/v (density = mass ÷ volume)",
            "materials attracted to magnets (ferrous metals)",
            "choose materials based on properties needed (e.g., insulation material for warmth)",
        ]
    else:
        questions = [f"{i + 1}. Year 6 Science practice question {i + 1}" for i in range(10)]
        answers = [f"answer {i + 1}" for i in range(10)]

    content = f"Science Homework - Year 6 - {topic} (Set {index})\n\n" + "\n".join(questions)
    return content, answers


# 各年级 Key Stage 和作业时间设置
YEAR_CONFIG = {
    1: {"key_stage": "KS1", "homework_minutes": "10-15"},
    2: {"key_stage": "KS1", "homework_minutes": "10-15"},
    3: {"key_stage": "KS2", "homework_minutes": "20-30"},
    4: {"key_stage": "KS2", "homework_minutes": "20-30"},
    5: {"key_stage": "KS2", "homework_minutes": "30"},
    6: {"key_stage": "KS2", "homework_minutes": "30"},
}


def check_year_science_exists(year_group: int) -> bool:
    """检查指定年级是否已有Science作业"""
    store = get_homework_rag_store()
    results = store.search(query="science", k=1, filters={"year_group": year_group, "subject": "Science"})
    return len(results) > 0


def generate_year_homework(year_group: int, count: int = 500) -> list:
    """为指定年级生成指定数量的Science作业"""
    topics = SCIENCE_TOPICS_BY_YEAR.get(year_group, [])
    if not topics:
        print(f"警告：未找到 Year {year_group} 的Science主题")
        return []

    config = YEAR_CONFIG.get(year_group, {"key_stage": "KS2", "homework_minutes": "20-30"})
    batch_data = []

    for i in range(1, count + 1):
        topic = topics[(i - 1) % len(topics)]
        content, correct_answers = generate_science_homework(year_group, topic, i)
        if content is None or correct_answers is None:
            print(f"  Year {year_group}: Failed to generate question {i}, skipping...")
            continue

        metadata = {
            "year_group": year_group,
            "subject": "Science",
            "homework_minutes": config["homework_minutes"],
            "key_stage": config["key_stage"],
            "topic": topic,
            "student_id": None,
            "correct_answers": json.dumps(correct_answers),  # Convert list to JSON string for ChromaDB
        }

        doc_id = f"science_y{year_group}_{i:03d}"
        batch_data.append({
            "content": content,
            "metadata": metadata,
            "doc_id": doc_id,
        })

        if i % 10 == 0:
            print(f"  已生成 {i}/{count} 份作业")

    return batch_data


def main():
    """主函数：检查各年级Science作业，缺失则生成"""
    print("检查各年级Science作业是否存在...\n")

    store = get_homework_rag_store()
    years_to_generate = []

    for year in range(1, 7):
        exists = check_year_science_exists(year)
        status = "已有" if exists else "缺失"
        print(f"  Year {year}: {status}")
        if not exists:
            years_to_generate.append(year)

    if not years_to_generate:
        print("\n所有年级Science作业已存在，无需生成。")
        return

    print(f"\n需要生成的年级: {', '.join(f'Year {y}' for y in years_to_generate)}")

    for year in years_to_generate:
        print(f"\n开始生成 Year {year} Science作业...")
        batch_data = generate_year_homework(year, count=500)

        if batch_data:
            store.add_batch_homework(batch_data)
            print(f"成功添加 {len(batch_data)} 份 Year {year} Science作业到 RAG 存储")

    # 显示统计信息
    stats = store.get_stats()
    print(f"\nRAG 存储统计:")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  按主题分布: {stats['by_subject']}")
    print(f"  按年级分布: {stats['by_year_group']}")


if __name__ == "__main__":
    main()
