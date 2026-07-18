#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate curriculum-aligned, objectively markable Science homework.

The public generation and review flow is unchanged: each worksheet is stored in
``src.homework_rag`` with the same metadata and a positional answer list.
Questions use multiple choice so knowledge and working-scientifically skills can
be marked reliably without judging drawings or unrestricted explanations.

Curriculum basis: DfE Science programmes of study for Years 1-6 in England.
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

HOMEWORK_COUNT = {1: 100, 2: 200, 3: 300, 4: 400, 5: 500, 6: 600}

SCIENCE_TOPICS_BY_YEAR = {
    1: ["Plants", "Animals including humans", "Everyday materials", "Seasonal changes", "Working scientifically"],
    2: ["Living things and their habitats", "Plants", "Animals including humans", "Uses of everyday materials", "Working scientifically"],
    3: ["Plants", "Animals including humans", "Rocks", "Light", "Forces and magnets", "Working scientifically"],
    4: ["Living things and their habitats", "Animals including humans", "States of matter", "Sound", "Electricity", "Working scientifically"],
    5: ["Living things and their habitats", "Animals including humans", "Properties and changes of materials", "Earth and space", "Forces", "Working scientifically"],
    6: ["Living things and their habitats", "Animals including humans", "Evolution and inheritance", "Light", "Electricity", "Working scientifically"],
}

# Accept names from the older generator when another tool calls the function directly.
TOPIC_ALIASES = {
    "Animals and their habitats": "Animals including humans",
    "Plants and growth": "Plants",
    "Human body and senses": "Animals including humans",
    "Weather and seasons": "Seasonal changes",
    "Light and dark": "Seasonal changes",
    "Floating and sinking": "Everyday materials",
    "Sound and hearing": "Animals including humans",
    "Plants - growth and care": "Plants",
    "Human growth and development": "Animals including humans",
    "Habitats and food chains": "Living things and their habitats",
    "Living things": "Living things and their habitats",
    "Materials around us": "Uses of everyday materials",
    "Plants and photosynthesis": "Plants",
    "Animals - diet and teeth": "Animals including humans",
    "Rocks and soil": "Rocks",
    "Light and shadows": "Light",
    "States of matter": "States of matter",
    "Electrical circuits (simple)": "Electricity",
    "Sound and vibrations": "Sound",
    "The digestive system": "Animals including humans",
    "States of matter and changes": "States of matter",
    "Rocks and soils": "States of matter",
    "Electricity and circuits": "Electricity",
    "Light and vision": "Light",
    "The water cycle": "States of matter",
    "Life cycles of plants and animals": "Living things and their habitats",
    "Properties and changes of materials": "Properties and changes of materials",
    "Earth and space": "Earth and space",
    "Forces and motion": "Forces",
    "Gravity and weight": "Forces",
    "Levers and pulleys": "Forces",
    "Evolution and inheritance": "Evolution and inheritance",
    "Respiration and gas exchange": "Animals including humans",
    "Circulatory system and health": "Animals including humans",
    "The nervous system and reactions": "Animals including humans",
    "Classification of living things": "Living things and their habitats",
    "Electricity and circuits (advanced)": "Electricity",
    "Light - reflection and refraction": "Light",
    "Evolution and natural selection": "Evolution and inheritance",
    "Forces - pressure and moments": "Electricity",
    "Properties of materials (advanced)": "Electricity",
}

YEAR_CONFIG = {
    1: {"key_stage": "KS1", "homework_minutes": "10-15"},
    2: {"key_stage": "KS1", "homework_minutes": "10-20"},
    3: {"key_stage": "KS2", "homework_minutes": "15-20"},
    4: {"key_stage": "KS2", "homework_minutes": "20-25"},
    5: {"key_stage": "KS2", "homework_minutes": "20-30"},
    6: {"key_stage": "KS2", "homework_minutes": "25-30"},
}


def _repeat(items, rng, index):
    questions=[]
    for i in range(10):
        stem,answer,wrong=items[(i+index)%len(items)]
        questions.append(make_mcq(stem,answer,wrong,rng))
    return questions


def _working_scientifically(year, topic, index):
    rng=stable_random("Science",year,topic,index)
    if year<=2:
        items=[
            ("Which tool is best for looking closely at a leaf?","hand lens",["ruler","timer","thermometer"]),
            ("Which is a simple scientific question?","Which paper towel absorbs the most water?",["Why is everything interesting?","What is the best thing ever?","Can all questions have no answer?"]),
            ("To compare two toy cars fairly, what should stay the same?","the ramp height",["the car used","the distance measured","the result"]),
            ("Which action records data?","writing the number of seeds that grew",["guessing without looking","changing every condition","forgetting the result"]),
            ("Which is a useful way to group objects?","by their observable properties",["by a secret rule nobody knows","randomly each time","without looking at them"]),
        ]
    elif year<=4:
        items=[
            ("What is a fair test?","a test where only the chosen variable is changed",["a test with no measurements","a test where everything changes","a test with a preferred result"]),
            ("Which variable should be measured in a plant-growth test?","plant height",["the researcher's name","the colour of the notebook","the day of the week only"]),
            ("Which table heading includes a unit correctly?","Temperature (°C)",["Temperature hot","Results maybe","Number nice"]),
            ("What should a conclusion use?","the collected evidence",["a guess made before the test","an unrelated fact","the answer a friend wanted"]),
            ("Why repeat a measurement?","to improve reliability",["to guarantee a chosen result","to avoid recording data","to change the question"]),
        ]
    else:
        items=[
            ("Which change makes an investigation more reliable?","repeat measurements and calculate a representative result",["remove results that disagree","change several variables at once","use no measuring equipment"]),
            ("Which graph is usually best for continuous data over time?","line graph",["pictogram only","unordered word list","Venn diagram"]),
            ("What is an anomalous result?","a result that does not fit the overall pattern",["the first result collected","the largest unit","a result copied twice"]),
            ("Which statement is a scientific conclusion?","The data supports the idea that warmer water dissolved the sugar faster.",["Warm water is always best because I like it.","The answer must be true with no data.","Sugar is interesting."]),
            ("Why identify control variables?","to keep other relevant conditions the same",["to make every test different","to avoid measuring the outcome","to hide the method"]),
        ]
    return _repeat(items,rng,index)


def _year1(topic,index):
    rng=stable_random("Science",1,topic,index)
    if topic=="Plants":items=[("Which part of a flowering plant usually absorbs water from the soil?","roots",["flower","fruit","leaf"]),("Which plant is an evergreen tree?","pine",["oak","daisy","sunflower"]),("Which part holds a plant upright?","stem",["petal","seed","root hair only"]),("Which is a common garden plant?","rose",["polar bear","granite","plastic"]),("What do seeds grow into?","new plants",["rocks","metal","clouds"])]
    elif topic=="Animals including humans":items=[("Which animal is a mammal?","dog",["salmon","frog","sparrow"]),("Which body part is used for hearing?","ears",["eyes","nose","tongue"]),("Which animal is a fish?","salmon",["cat","eagle","frog"]),("What do humans use to smell?","nose",["skin","ears","feet"]),("Which animal is a bird?","robin",["lizard","trout","rabbit"])]
    elif topic=="Everyday materials":items=[("Which object is usually made from glass?","window",["wool jumper","wooden spoon","rubber band"]),("Which material is waterproof?","plastic",["paper towel","cotton wool","cardboard"]),("Which material is magnetic?","iron",["wood","glass","cotton"]),("Which word describes rubber?","flexible",["transparent","brittle like glass","absorbent like paper"]),("Which object is commonly made from wood?","table",["drinking glass","metal coin","wool sock"])]
    elif topic=="Seasonal changes":items=[("Which season usually follows spring in the UK?","summer",["winter","autumn","spring"]),("In which season are UK days usually shortest?","winter",["summer","spring","autumn"]),("Which weather is common in winter?","cold temperatures",["the longest daylight hours","hot tropical heat every day","no clouds ever"]),("What happens to daylight from winter towards summer?","it generally increases",["it disappears","it always stays identical","it becomes night all day"]),("Which season usually comes after summer?","autumn",["spring","winter","summer"])]
    elif topic=="Working scientifically":return render_homework("Science",1,topic,index,_working_scientifically(1,topic,index))
    else:raise ValueError(f"Unknown Year 1 Science topic: {topic}")
    return render_homework("Science",1,topic,index,_repeat(items,rng,index))


def _year2(topic,index):
    rng=stable_random("Science",2,topic,index)
    if topic=="Living things and their habitats":items=[("Which is alive?","oak tree",["stone","plastic cup","metal spoon"]),("What is a habitat?","the place where an organism lives",["a type of food only","a weather chart","a measuring tool"]),("Which habitat suits a frog?","pond",["dry cupboard","hot oven","concrete wall"]),("Which is a simple food chain?","grass → rabbit → fox",["fox → grass → rabbit","rabbit → fox → grass","grass → fox → sunlight"]),("Why do habitats matter?","They provide organisms with things needed to survive.",["They make every animal identical.","They stop all weather.","They are only for plants."])]
    elif topic=="Plants":items=[("What does a seed need to germinate?","water and suitable warmth",["bright paint","salt only","a metal box"]),("Which condition helps most green plants grow well?","light",["complete darkness forever","no water","freezing every day"]),("What can a bulb grow into?","a mature plant",["a stone","an animal","a metal tool"]),("Which part may contain seeds?","fruit",["root only","soil","watering can"]),("What happens when a healthy plant grows?","It increases in size and develops.",["It becomes a rock.","It stops needing any resources.","It changes into an animal."])]
    elif topic=="Animals including humans":items=[("Which sequence shows human growth correctly?","baby → child → adult",["adult → baby → child","child → adult → baby","baby → adult → child"]),("What do animals need to survive?","water, food and air",["plastic, glass and metal","only toys","paint and glue"]),("Which habit supports good health?","regular exercise",["never sleeping","eating only sweets","never drinking water"]),("Why do humans eat food?","for energy and nutrients",["to stop breathing","to become metal","to avoid all movement"]),("Which animal gives birth to live young?","cat",["chicken","frog","butterfly"])]
    elif topic=="Uses of everyday materials":items=[("Why is glass useful for windows?","It is transparent.",["It is always soft.","It absorbs lots of water.","It is magnetic."]),("Why is rubber useful for wellington boots?","It is waterproof and flexible.",["It dissolves in rain.","It is transparent and brittle.","It is made of paper."]),("Which material is best for a saucepan?","metal",["paper","cotton wool","cardboard"]),("Which change can be reversed?","bending a flexible wire",["burning paper","cooking an egg","baking clay"]),("Why is wood often used for furniture?","It is strong and can be shaped.",["It is always liquid.","It is completely transparent.","It melts at room temperature."])]
    elif topic=="Working scientifically":return render_homework("Science",2,topic,index,_working_scientifically(2,topic,index))
    else:raise ValueError(f"Unknown Year 2 Science topic: {topic}")
    return render_homework("Science",2,topic,index,_repeat(items,rng,index))


def _year3(topic,index):
    rng=stable_random("Science",3,topic,index)
    if topic=="Plants":items=[("Which part transports water from roots to leaves?","stem",["petal","fruit","seed coat"]),("What is pollination?","transfer of pollen from anther to stigma",["water moving into roots","seeds turning into rocks","leaves losing all colour"]),("Which is needed for healthy plant growth?","light",["plastic","metal","complete lack of water"]),("What is the role of roots?","anchor the plant and absorb water and minerals",["make sound","catch animals","produce metal"]),("What happens after fertilisation in a flower?","seeds can form",["the plant becomes a mammal","all roots disappear","the flower turns to stone"])]
    elif topic=="Animals including humans":items=[("Which nutrient is mainly needed for growth and repair?","protein",["fibre only","water only","vitamin C only"]),("Which type of teeth cuts food?","incisors",["molars","canines only","wisdom teeth only"]),("What is the function of a skeleton?","support, protection and movement",["make sunlight","digest food directly","pump electricity"]),("Which joint allows the arm to bend?","elbow",["skull","rib","tooth"]),("Why do muscles work in pairs?","one contracts while the other relaxes to move a bone",["both disappear","they make bones liquid","they stop all movement"])]
    elif topic=="Rocks":items=[("Which rock forms when magma or lava cools?","igneous rock",["sedimentary rock","metamorphic rock only from shells","soil"]),("What are fossils?","preserved remains or traces of past living things",["new plastic objects","clouds trapped in stone","living animals inside every rock"]),("Which process helps form soil?","weathering of rock mixed with organic matter",["painting stones","freezing metal","melting glass only"]),("Which rock is often permeable?","sandstone",["polished granite","glass","metal"]),("Metamorphic rock forms when existing rock is changed by what?","heat and pressure",["moonlight only","paint and glue","cold air only"])]
    elif topic=="Light":items=[("Why can we see most objects?","Light reflects from them into our eyes.",["Objects always make their own light.","Sound enters our eyes.","Shadows shine."]),("Which is a light source?","Sun",["Moon","mirror","book"]),("How is a shadow formed?","An opaque object blocks light.",["Sound bends around an object.","A transparent object creates electricity.","Darkness reflects from a mirror."]),("What happens to a shadow when an object moves closer to a light source?","It usually becomes larger.",["It always disappears.","It becomes a sound.","It changes into glass."]),("Why is looking directly at the Sun unsafe?","It can damage the eyes.",["It freezes the eyes.","It removes all shadows.","It changes eye colour immediately."])]
    elif topic=="Forces and magnets":items=[("Which force slows a sliding object?","friction",["magnetism only","light","sound"]),("Which material is attracted to a magnet?","iron",["wood","plastic","glass"]),("What happens when two north poles are brought together?","They repel.",["They attract.","They melt.","They become non-magnetic immediately."]),("Which surface usually creates most friction?","rough carpet",["smooth ice","polished tile","oiled metal"]),("A force can do what?","change an object's speed, direction or shape",["turn matter into time","remove all mass","stop gravity everywhere"])]
    elif topic=="Working scientifically":return render_homework("Science",3,topic,index,_working_scientifically(3,topic,index))
    else:raise ValueError(f"Unknown Year 3 Science topic: {topic}")
    return render_homework("Science",3,topic,index,_repeat(items,rng,index))


def _year4(topic,index):
    rng=stable_random("Science",4,topic,index)
    if topic=="Living things and their habitats":items=[("What is a classification key used for?","identifying organisms from their features",["measuring temperature","making electricity","changing habitats"]),("Which group has a backbone?","vertebrates",["invertebrates","fungi only","plants only"]),("Which environmental change may reduce a habitat's biodiversity?","pollution",["protecting nesting sites","planting native flowers","creating a pond"]),("Which is an invertebrate?","snail",["frog","bird","fish"]),("Why group living things?","to organise and identify them using shared features",["to make them identical","to stop them growing","to remove their habitats"])]
    elif topic=="Animals including humans":items=[("Where does digestion begin?","mouth",["large intestine","leg","lung"]),("What is the function of the stomach?","mix food with digestive juices",["pump blood","produce sound","absorb light"]),("Which teeth grind food?","molars",["incisors","canines","milk teeth as a group"]),("Which sequence is a food chain?","grass → grasshopper → frog",["frog → grass → grasshopper","grasshopper → frog → grass","Sun → frog → grass"]),("What is the role of the small intestine?","absorb digested nutrients",["chew food","pump blood","make bones move"])]
    elif topic=="States of matter":items=[("Which state has a fixed shape and volume?","solid",["liquid","gas","vapour only"]),("What is melting?","solid changing to liquid",["gas changing to liquid","liquid changing to gas","liquid changing to solid"]),("What is condensation?","gas changing to liquid",["solid changing to liquid","liquid changing to gas","solid changing to gas only"]),("Which change happens during evaporation?","liquid changes to gas",["gas changes to liquid","solid changes to liquid","gas changes to solid"]),("What drives the water cycle?","energy from the Sun",["magnetism","sound","electric current only"])]
    elif topic=="Sound":items=[("How is sound produced?","by vibrating objects",["by shadows","by magnets only","by still air with no vibration"]),("What happens to pitch when vibrations become faster?","pitch becomes higher",["pitch becomes lower","sound becomes light","volume always becomes zero"]),("What usually makes a sound louder?","larger vibrations",["smaller vibrations","no vibration","a darker colour"]),("Through which medium can sound travel?","solids, liquids and gases",["a vacuum only","light only","nothing at all"]),("Which part of the ear vibrates when sound arrives?","eardrum",["tooth","elbow","retina"])]
    elif topic=="Electricity":items=[("What is needed for a bulb to light?","a complete circuit",["an open circuit","a disconnected cell","a plastic loop with no cell"]),("Which material is an electrical conductor?","copper",["rubber","wood","plastic"]),("What does a switch do?","opens or closes a circuit",["creates matter","changes sound into food","removes the cell"]),("If another cell is added correctly in series, what usually happens to a bulb?","It becomes brighter.",["It always goes out.","It becomes colder only.","It turns into a motor."]),("Which component provides electrical energy in a simple circuit?","cell",["wire only","switch only","bulb only"])]
    elif topic=="Working scientifically":return render_homework("Science",4,topic,index,_working_scientifically(4,topic,index))
    else:raise ValueError(f"Unknown Year 4 Science topic: {topic}")
    return render_homework("Science",4,topic,index,_repeat(items,rng,index))


def _year5(topic,index):
    rng=stable_random("Science",5,topic,index)
    if topic=="Living things and their habitats":items=[("Which stage follows a caterpillar in a butterfly life cycle?","pupa",["egg","adult bird","seed"]),("Which process transfers pollen between flowers?","pollination",["germination","respiration","evaporation"]),("Which animal undergoes metamorphosis?","frog",["human","cat","horse"]),("What is asexual reproduction in plants?","one parent produces genetically similar offspring",["two animals produce seeds","a rock forms a plant","all offspring are unrelated"]),("Which scientist is known for work on animal behaviour?","Jane Goodall",["Isaac Newton only for gravity","Ada Lovelace only for computing","Florence Nightingale only for nursing"])]
    elif topic=="Animals including humans":items=[("Which stage usually follows childhood?","adolescence",["infancy","old age","embryo"]),("What happens during puberty?","The body develops towards adult maturity.",["The body becomes a different species.","Growth stops forever.","Bones turn to liquid."]),("Which statement about human development is correct?","Humans change in predictable broad stages.",["All humans develop at exactly the same rate.","Adults become babies again.","Development has no physical changes."]),("Which is a stage of the human life cycle?","infancy",["germination","pupa","spore only"]),("Why do scientists use growth data?","to identify patterns and variation",["to guarantee identical growth","to remove differences","to avoid measurements"])]
    elif topic=="Properties and changes of materials":items=[("Which material is usually a good thermal conductor?","metal",["wool","foam","wood"]),("Which method separates sand from water?","filtration",["melting","magnetism only","freezing both"]),("Which change is reversible?","dissolving salt then evaporating the water",["burning wood","rusting iron","baking a cake"]),("What happens in a chemical change?","new substances form",["only shape changes","mass disappears","all particles stop moving"]),("Which material property is useful for a raincoat?","water resistance",["solubility in water","high absorbency","brittleness"])]
    elif topic=="Earth and space":items=[("What causes day and night?","Earth rotating on its axis",["the Sun moving around Earth each day","the Moon blocking all light","clouds moving"]),("How long does Earth take to orbit the Sun?","about one year",["one day","one month","one hour"]),("Which body orbits Earth?","Moon",["Sun","Mars","Polaris"]),("Why does the Sun appear to move across the sky?","Earth rotates",["the Sun circles Earth daily","the Moon pushes it","wind moves it"]),("Which model is scientifically accepted?","Earth and other planets orbit the Sun",["all planets orbit Earth","the Sun orbits the Moon","Earth does not move"])]
    elif topic=="Forces":items=[("Which force pulls objects towards Earth?","gravity",["friction","magnetism only","upthrust only"]),("What does air resistance do to a falling object?","opposes its motion",["removes its mass","turns it into gas","always speeds it up"]),("Which simple machine can increase the effect of a force?","lever",["thermometer","beaker","mirror"]),("Why do parachutes have a large surface area?","to increase air resistance",["to remove gravity","to increase mass greatly","to stop all motion instantly"]),("What does a gear system change?","speed, force or direction of movement",["chemical identity","temperature only","amount of matter"])]
    elif topic=="Working scientifically":return render_homework("Science",5,topic,index,_working_scientifically(5,topic,index))
    else:raise ValueError(f"Unknown Year 5 Science topic: {topic}")
    return render_homework("Science",5,topic,index,_repeat(items,rng,index))


def _year6(topic,index):
    rng=stable_random("Science",6,topic,index)
    if topic=="Living things and their habitats":items=[("Which group contains organisms with feathers?","birds",["mammals","amphibians","fish"]),("What feature distinguishes vertebrates?","a backbone",["six legs","green leaves","no cells"]),("Who developed an early classification system still influential today?","Carl Linnaeus",["Charles Babbage","Michael Faraday only for electricity","Mary Anning only for fossils"]),("Which microorganism is used to make bread rise?","yeast",["virus","algae only","moss"]),("A classification key uses what?","observable characteristics",["random guesses","personal favourites","unmeasured opinions"])]
    elif topic=="Animals including humans":items=[("Which organ pumps blood around the body?","heart",["lungs","stomach","kidneys"]),("What is carried by red blood cells?","oxygen",["sound","light","bones"]),("Which blood vessel carries blood away from the heart?","artery",["vein","capillary only towards heart","airway"]),("How can regular exercise affect the heart?","It can strengthen the heart and improve fitness.",["It stops blood flow.","It removes the need for oxygen.","It turns muscle into bone."]),("What is the role of the lungs?","gas exchange",["digesting food","making urine","controlling bones directly"])]
    elif topic=="Evolution and inheritance":items=[("What is inheritance?","passing characteristics from parents to offspring",["learning a new skill","changing habitat daily","choosing all features"]),("What is an adaptation?","a feature that helps an organism survive and reproduce",["a temporary mood","a random object","a measurement error"]),("What evidence can fossils provide?","information about organisms from the past",["the exact future","proof that species never change","weather tomorrow"]),("Why can populations change over many generations?","Individuals with helpful variations may reproduce more successfully.",["Every individual chooses new genes.","All organisms become identical instantly.","Habitats never change."]),("Which is an example of variation?","different beak sizes in birds of one species",["all birds having cells","all mammals needing food","all plants being living things"])]
    elif topic=="Light":items=[("How does light usually travel?","in straight lines",["only in circles","as sound waves","through no medium and no direction"]),("Why can we see an object in a mirror?","Light reflects from the object to the mirror and into our eyes.",["The mirror creates the object.","Sound reflects into our eyes.","The object enters the mirror."]),("What happens to the angle of reflection?","It equals the angle of incidence.",["It is always zero.","It is always 90°.","It has no relationship."]),("Why does a periscope work?","mirrors reflect light along a new path",["magnets bend light","sound carries images","water creates electricity"]),("Why are shadows the same shape as blocking objects?","Light travels in straight lines.",["Sound copies shapes.","Air becomes solid.","The object emits darkness."])]
    elif topic=="Electricity":items=[("What happens to bulb brightness when more cells are added correctly in series?","It usually increases.",["It always decreases.","It becomes unrelated to voltage.","The bulb turns into a switch."]),("Which circuit symbol represents a cell?","one long and one short parallel line",["a circle with a cross","a zigzag only","two open dots only"]),("What does a variable resistor change?","current in the circuit",["the material's mass","the number of planets","the colour of light only"]),("Why will a bulb not light in an open circuit?","There is no complete path for current.",["The bulb has too much food.","The wires are always magnetic.","Electricity needs sunlight."]),("Which change would reduce current in a simple circuit?","adding resistance",["adding another cell in the same direction","shortening a resistance wire","closing an open switch"])]
    elif topic=="Working scientifically":return render_homework("Science",6,topic,index,_working_scientifically(6,topic,index))
    else:raise ValueError(f"Unknown Year 6 Science topic: {topic}")
    return render_homework("Science",6,topic,index,_repeat(items,rng,index))


def generate_science_homework(year_group:int,topic:str,index:int)->tuple[str,list[str]]:
    canonical=TOPIC_ALIASES.get(topic,topic)
    generators={1:_year1,2:_year2,3:_year3,4:_year4,5:_year5,6:_year6}
    if year_group not in generators:raise ValueError("year_group must be between 1 and 6")
    return generators[year_group](canonical,index)


def generate_year_homework(year_group:int,count:int=500)->list:
    topics=SCIENCE_TOPICS_BY_YEAR.get(year_group,[]);config=YEAR_CONFIG.get(year_group)
    if not topics or not config:return []
    batch=[]
    for i in range(1,count+1):
        topic=topics[(i-1)%len(topics)];content,answers=generate_science_homework(year_group,topic,i)
        batch.append(build_batch_item(content=content,answers=answers,year_group=year_group,subject="Science",topic=topic,homework_minutes=config["homework_minutes"],key_stage=config["key_stage"],doc_id=f"science_y{year_group}_{i:04d}"))
        if i%100==0:print(f"  Generated {i}/{count}")
    return batch


def main():
    store=get_homework_rag_store();print(f"RAG target: {store.store.database_target}")
    for year in range(1,7):
        expected=HOMEWORK_COUNT[year];existing=count_year_homework(store,year,"Science")
        if existing>=expected:
            print(f"Year {year}: complete ({existing}/{expected})");continue
        data=generate_year_homework(year,expected);added=add_homework_in_batches(store,data)
        print(f"Year {year}: added {added}; target {len(data)}")
    get_rag_stats(store)


if __name__=="__main__":main()
