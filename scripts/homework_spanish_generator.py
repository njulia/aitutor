#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate age-appropriate Spanish homework for England Years 1-6.

Languages are statutory in England only at KS2 (Years 3-6).  Year 1-2 sets are
therefore labelled optional enrichment and build listening/phonics/vocabulary
foundations.  KS2 sets focus on practical communication, familiar topics,
phonology, vocabulary and basic grammar as required by the languages programme
of study.  The RAG and review format is unchanged.
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

SPANISH_TOPICS_BY_YEAR = {
    1: ["Greetings", "Numbers 1-10", "Colours", "Animals", "Classroom words"],
    2: ["Numbers 1-20", "Body parts", "Family", "Weather", "School objects"],
    3: ["Spanish sounds and greetings", "Numbers and dates", "Family and descriptions", "Classroom language", "Likes and dislikes", "Simple sentences"],
    4: ["Daily routine", "Telling the time", "Food and drink", "Town and directions", "Adjective agreement", "Present tense basics"],
    5: ["Common present-tense verbs", "Opinions and reasons", "School and leisure", "Travel and transport", "Short reading", "Sentence building"],
    6: ["Present and near future", "Past and future time phrases", "Opinions with justification", "Reading comprehension", "Spanish-speaking world", "Transition to secondary Spanish"],
}

TOPIC_ALIASES = {
    "Greetings and Introductions": "Greetings",
    "Family Members": "Family",
    "Food and Drink": "Classroom words",
    "Days of the Week": "Numbers 1-10",
    "Simple Commands": "Classroom words",
    "Body Parts": "Body parts",
    "Clothes": "Body parts",
    "Months and Seasons": "Weather",
    "Feelings and Emotions": "Family",
    "Hobbies and Sports": "School objects",
    "School Objects": "School objects",
    "Numbers 1-100": "Numbers and dates",
    "Telling Time": "Numbers and dates",
    "Daily Routine": "Simple sentences",
    "My House": "Family and descriptions",
    "Town and Places": "Simple sentences",
    "Likes and Dislikes": "Likes and dislikes",
    "Describing People": "Family and descriptions",
    "Simple Conversations": "Spanish sounds and greetings",
    "Numbers and Prices": "Telling the time",
    "Ordering Food": "Food and drink",
    "Holidays and Travel": "Town and directions",
    "Past Tense Introduction": "Present tense basics",
    "Giving Directions": "Town and directions",
    "Shopping": "Food and drink",
    "My Bedroom": "Adjective agreement",
    "Weather Forecasts": "Daily routine",
    "Present Tense Verbs": "Common present-tense verbs",
    "Future Plans": "Travel and transport",
    "Comparing Cultures": "Short reading",
    "Writing Emails": "Sentence building",
    "Restaurant Dialogues": "Opinions and reasons",
    "Transport": "Travel and transport",
    "Health and Illness": "School and leisure",
    "Environmental Topics": "Short reading",
    "Past Tense (Preterite)": "Past and future time phrases",
    "Opinions and Justifications": "Opinions with justification",
    "Formal and Informal Register": "Transition to secondary Spanish",
    "Reading Comprehension": "Reading comprehension",
    "Creative Writing in Spanish": "Present and near future",
    "Spanish-speaking Countries": "Spanish-speaking world",
    "Festivals and Traditions": "Spanish-speaking world",
    "Transition to Secondary Spanish": "Transition to secondary Spanish",
}

YEAR_CONFIG = {
    1: {"key_stage": "Optional enrichment", "homework_minutes": "5-10"},
    2: {"key_stage": "Optional enrichment", "homework_minutes": "5-10"},
    3: {"key_stage": "KS2", "homework_minutes": "10-15"},
    4: {"key_stage": "KS2", "homework_minutes": "15-20"},
    5: {"key_stage": "KS2", "homework_minutes": "15-20"},
    6: {"key_stage": "KS2", "homework_minutes": "20-25"},
}


def _repeat(items, rng, index):
    q=[]
    for i in range(10):
        stem,ans,wrong=items[(i+index)%len(items)]
        q.append(make_mcq(stem,ans,wrong,rng))
    return q


def _year1(topic,index):
    rng=stable_random("Spanish",1,topic,index)
    if topic=="Greetings":items=[("What does 'hola' mean?","hello",["goodbye","please","thank you"]),("Which Spanish word means 'goodbye'?","adiós",["hola","gracias","sí"]),("What does 'buenos días' mean?","good morning",["good night","goodbye","see you tomorrow"]),("Which phrase means 'my name is...' ?","me llamo...",["¿cómo estás?","hasta luego","por favor"]),("What does 'gracias' mean?","thank you",["hello","sorry","no"])]
    elif topic=="Numbers 1-10":items=[("What number is 'uno'?","1",["2","3","10"]),("How do you say 5 in Spanish?","cinco",["cuatro","seis","diez"]),("What number is 'ocho'?","8",["6","7","9"]),("How do you say 10 in Spanish?","diez",["dos","tres","nueve"]),("Which sequence is correct?","uno, dos, tres",["uno, tres, dos","dos, uno, cuatro","tres, uno, dos"])]
    elif topic=="Colours":items=[("What colour is 'rojo'?","red",["blue","green","yellow"]),("How do you say blue in Spanish?","azul",["verde","rojo","negro"]),("What colour is 'verde'?","green",["orange","white","pink"]),("How do you say yellow in Spanish?","amarillo",["morado","blanco","gris"]),("What colour is 'negro'?","black",["white","brown","purple"])]
    elif topic=="Animals":items=[("What animal is 'gato'?","cat",["dog","fish","bird"]),("How do you say dog in Spanish?","perro",["pájaro","pez","conejo"]),("What animal is 'pez'?","fish",["horse","rabbit","cow"]),("How do you say bird in Spanish?","pájaro",["gato","cerdo","caballo"]),("What animal is 'conejo'?","rabbit",["cow","pig","cat"])]
    elif topic=="Classroom words":items=[("What does 'libro' mean?","book",["pencil","chair","door"]),("How do you say pencil in Spanish?","lápiz",["mesa","libro","silla"]),("What does 'escucha' mean?","listen",["write","run","sleep"]),("Which word means table?","mesa",["puerta","ventana","mochila"]),("What does 'mira' mean?","look",["sit","eat","close"])]
    else:raise ValueError(f"Unknown Year 1 Spanish topic: {topic}")
    return render_homework("Spanish",1,topic,index,_repeat(items,rng,index),note="Optional language enrichment for Year 1.")


def _year2(topic,index):
    rng=stable_random("Spanish",2,topic,index)
    if topic=="Numbers 1-20":items=[("What number is 'doce'?","12",["11","13","20"]),("How do you say 15 in Spanish?","quince",["catorce","dieciséis","cinco"]),("What number is 'dieciocho'?","18",["16","17","19"]),("How do you say 20 in Spanish?","veinte",["nueve","diez","diecinueve"]),("Which comes after 'trece'?","catorce",["doce","quince","once"])]
    elif topic=="Body parts":items=[("What does 'cabeza' mean?","head",["hand","foot","arm"]),("How do you say hand in Spanish?","mano",["pie","ojo","boca"]),("What does 'ojos' mean?","eyes",["ears","legs","teeth"]),("How do you say nose in Spanish?","nariz",["oreja","brazo","pelo"]),("What does 'boca' mean?","mouth",["head","finger","knee"])]
    elif topic=="Family":items=[("What does 'madre' mean?","mother",["father","sister","brother"]),("How do you say father in Spanish?","padre",["abuela","hermana","tía"]),("What does 'hermano' mean?","brother",["sister","grandfather","cousin"]),("How do you say grandmother in Spanish?","abuela",["abuelo","madre","prima"]),("What does 'familia' mean?","family",["school","house","friend"])]
    elif topic=="Weather":items=[("What does 'hace sol' mean?","it is sunny",["it is raining","it is cold","it is windy"]),("How do you say 'it is raining'?","llueve",["nieva","hace calor","hace sol"]),("What does 'hace frío' mean?","it is cold",["it is hot","it is sunny","it is cloudy"]),("How do you say 'it is windy'?","hace viento",["hace buen tiempo","llueve","nieva"]),("What does 'nieva' mean?","it is snowing",["it is raining","it is hot","it is foggy"])]
    elif topic=="School objects":items=[("What does 'mochila' mean?","school bag",["book","chair","window"]),("How do you say ruler in Spanish?","regla",["goma","bolígrafo","cuaderno"]),("What does 'cuaderno' mean?","exercise book",["pencil case","desk","board"]),("How do you say rubber in Spanish?","goma",["tijeras","mesa","puerta"]),("What does 'bolígrafo' mean?","pen",["pencil","ruler","book"])]
    else:raise ValueError(f"Unknown Year 2 Spanish topic: {topic}")
    return render_homework("Spanish",2,topic,index,_repeat(items,rng,index),note="Optional language enrichment for Year 2.")


def _ks2_bank(year,topic):
    banks={
      "Spanish sounds and greetings":[("Which Spanish word has the letter 'j' pronounced like a strong English 'h'?","jugo",["gato","mesa","luna"]),("What is a suitable reply to '¿Cómo te llamas?'","Me llamo Ana.",["Tengo diez años.","Vivo en Londres.","Me gusta el tenis."]),("What does '¿Cómo estás?' mean?","How are you?",["What is your name?","How old are you?","Where do you live?"]),("Which phrase means 'See you later'?","Hasta luego",["Buenos días","Por favor","Lo siento"]),("Which reply matches 'Buenos días'?","Buenos días",["Buenas noches only","Adiós only","No entiendo"])] ,
      "Numbers and dates":[("What number is 'cuarenta y dos'?","42",["24","32","52"]),("How do you say 67 in Spanish?","sesenta y siete",["setenta y seis","sesenta y seis","cincuenta y siete"]),("What does 'lunes' mean?","Monday",["Tuesday","month","morning"]),("Which month is 'enero'?","January",["June","August","October"]),("How do you say 'the third of May'?","el tres de mayo",["el mayo de tres","tres mayo el","el tercero mayo"])] ,
      "Family and descriptions":[("What does 'mi hermana' mean?","my sister",["my brother","my mother","my friend"]),("Choose the correct translation of 'He is tall'.","Es alto.",["Es alta.","Está alto.","Tiene alto."]),("Choose the correct translation of 'She is friendly'.","Es simpática.",["Es simpático.","Tiene simpática.","Está simpatía."]),("What does 'tiene el pelo negro' mean?","he or she has black hair",["he or she has blue eyes","he or she is short","he or she wears black"]),("Which adjective agrees with 'una chica'?","inteligente",["alto","pequeños","simpáticos"])] ,
      "Classroom language":[("What does 'abre el libro' mean?","open the book",["close the door","write the date","listen carefully"]),("How do you say 'write'?","escribe",["lee","escucha","mira"]),("What does 'levanta la mano' mean?","raise your hand",["sit down","open the window","read aloud"]),("Which phrase asks for repetition?","Repite, por favor.",["Cierra la puerta.","Tengo un lápiz.","Es lunes."]),("What does 'no entiendo' mean?","I do not understand",["I do not have a pen","I am not tired","I do not like it"])] ,
      "Likes and dislikes":[("What does 'me gusta el fútbol' mean?","I like football",["I play football every day","I dislike football","Football is difficult"]),("How do you say 'I do not like cheese'?","No me gusta el queso.",["Me gusta el queso.","No tengo queso.","El queso no gusta."]),("Which phrase gives a reason?","porque es divertido",["y también","pero no","muy bien"]),("What does 'me encantan los animales' mean?","I love animals",["I have animals","I see animals","I avoid animals"]),("Choose the correct sentence for 'I like books because they are interesting'.","Me gustan los libros porque son interesantes.",["Me gusta los libros porque es interesante.","Me gustan el libro porque son interesante.","Los libros me no gusta."])] ,
      "Simple sentences":[("Which sentence means 'I live in London'?","Vivo en Londres.",["Voy a Londres.","Me llamo Londres.","Tengo Londres."]),("Choose the correct word order.","Tengo un perro pequeño.",["Un tengo pequeño perro.","Perro pequeño un tengo.","Tengo pequeño un perro."]),("What does 'Tengo diez años' mean?","I am ten years old",["I have ten books","I live for ten years","I am in Year 10"]),("Which sentence means 'The house is big'?","La casa es grande.",["El casa es grande.","La casa son grande.","Casa la grande es."]),("Which conjunction means 'and'?","y",["pero","porque","también"])] ,
      "Daily routine":[("What does 'me levanto a las siete' mean?","I get up at seven",["I go to bed at seven","I eat at seven","I leave school at seven"]),("How do you say 'I have breakfast'?","desayuno",["ceno","duermo","estudio"]),("What does 'voy al colegio' mean?","I go to school",["I leave school","I like school","I build a school"]),("Which phrase means 'in the morning'?","por la mañana",["por la noche","por la tarde","mañana only as tomorrow"]),("How do you say 'I go to bed'?","me acuesto",["me visto","me ducho","me levanto"])] ,
      "Telling the time":[("What does 'son las tres' mean?","it is three o'clock",["it is half past three","it is one o'clock","it is thirteen o'clock"]),("How do you say half past five?","son las cinco y media",["son las cinco menos media","es la cinco y media","son cinco y cuarto"]),("What does 'es la una' mean?","it is one o'clock",["it is eleven o'clock","it is two o'clock","it is half past one"]),("How do you say quarter past eight?","son las ocho y cuarto",["son las ocho menos cuarto","son las ocho y media","es la ocho"]),("What does 'son las diez menos cuarto' mean?","it is quarter to ten",["it is quarter past ten","it is half past ten","it is ten o'clock"])] ,
      "Food and drink":[("What does 'quiero una manzana' mean?","I want an apple",["I have an apple","I like apples","I buy bread"]),("How do you say water?","agua",["leche","zumo","pan"]),("What does 'Tengo hambre' mean?","I am hungry",["I am thirsty","I am tired","I am cold"]),("Which phrase is polite when ordering?","Quisiera una pizza, por favor.",["Dame pizza.","Pizza ahora.","No pizza tú."]),("What does 'la cuenta' mean in a restaurant?","the bill",["the menu","the table","the kitchen"])] ,
      "Town and directions":[("What does 'la biblioteca' mean?","the library",["the station","the shop","the swimming pool"]),("How do you say 'turn left'?","gira a la izquierda",["gira a la derecha","sigue todo recto","cruza la plaza"]),("What does 'sigue todo recto' mean?","go straight on",["stop here","turn right","go back"]),("Which phrase asks where the station is?","¿Dónde está la estación?",["¿Qué hora es la estación?","¿Cómo es la estación?","¿Quién tiene la estación?"]),("What does 'al lado de' mean?","next to",["opposite","behind","far from"])] ,
      "Adjective agreement":[("Choose the correct phrase for 'a red house'.","una casa roja",["una casa rojo","un casa roja","una roja casa always"]),("Choose the correct phrase for 'two small dogs'.","dos perros pequeños",["dos perros pequeño","dos perras pequeños for male dogs","dos pequeños perro"]),("What is the feminine form of 'alto'?","alta",["altos","altas","alte"]),("Which adjective agrees with 'los libros'?","interesantes",["interesante singular","interesanta","interesantos"]),("Choose the correct phrase for 'the white shirt'.","la camisa blanca",["la camisa blanco","el camisa blanca","la blanca camiso"])] ,
      "Present tense basics":[("What does 'hablo' mean?","I speak",["you speak","he speaks","we speak"]),("Choose the correct form: 'She eats'.","Ella come.",["Ella como.","Ella comes.","Ella comer."]),("What does 'vivimos' mean?","we live",["I live","they live","you live singular"]),("Choose the correct form: 'They study'.","Ellos estudian.",["Ellos estudia.","Ellos estudiar.","Ellos estudio."]),("Which infinitive means 'to play'?","jugar",["juego","juega","jugamos"])] ,
      "Common present-tense verbs":[("Choose the correct form: 'I go'.","voy",["va","vamos","ir"]),("What does 'hace' mean in 'Hace los deberes'?","he or she does",["I do","we do","they do"]),("Choose the correct form: 'We have'.","tenemos",["tengo","tienen","tener"]),("What does 'puedo' mean?","I can",["I want","I must","I know"]),("Choose the correct sentence for 'They play tennis'.","Juegan al tenis.",["Juega al tenis.","Jugamos al tenis.","Jugar al tenis."])] ,
      "Opinions and reasons":[("What does 'Pienso que es útil' mean?","I think it is useful",["I know it is easy","I do not like it","It is always useful"]),("Which phrase means 'because it is exciting'?","porque es emocionante",["pero es emocionante","también emocionante","emocionante porque only"]),("How do you say 'In my opinion'?","En mi opinión",["En mi casa","Por la mañana","A veces"]),("What does 'prefiero' mean?","I prefer",["I promise","I practise","I prepare"]),("Choose the best justified opinion.","Me gusta la ciencia porque es interesante.",["Me gusta la ciencia.","La ciencia porque.","Interesante ciencia me."])] ,
      "School and leisure":[("What does 'mi asignatura favorita' mean?","my favourite subject",["my school bag","my classroom","my timetable"]),("How do you say 'I play basketball'?","Juego al baloncesto.",["Toco el baloncesto.","Hago el baloncesto.","Voy baloncesto."]),("What does 'los fines de semana' mean?","at weekends",["on Mondays","in summer","after school only"]),("Which sentence means 'I read books in my free time'?","Leo libros en mi tiempo libre.",["Escribo libros en clase.","Tengo tiempo y libros.","Los libros leen mi tiempo."]),("How do you say 'homework'?","los deberes",["el recreo","el comedor","el uniforme"])] ,
      "Travel and transport":[("What does 'voy en tren' mean?","I go by train",["I drive a train","I like trains","I wait at home"]),("How do you say 'airport'?","aeropuerto",["puerto","estación","carretera"]),("What does 'un billete de ida y vuelta' mean?","a return ticket",["a single ticket","a bus stop","a passport"]),("Which phrase means 'next summer'?","el verano que viene",["el verano pasado","este invierno","ayer"]),("How do you say 'We are going to visit Madrid'?","Vamos a visitar Madrid.",["Visitamos Madrid ayer.","Madrid nos visita.","Vamos Madrid visitar a."])] ,
      "Short reading":[("Read: 'Lucía vive en Sevilla y va al colegio en autobús.' Where does Lucía live?","Seville",["Madrid","London","Barcelona"]),("Read: 'Los sábados juego al tenis con mi hermano.' When does the speaker play tennis?","on Saturdays",["on Sundays","every morning","on Mondays"]),("Read: 'Mi perro es pequeño, blanco y muy simpático.' What colour is the dog?","white",["black","brown","grey"]),("Read: 'Prefiero las manzanas porque son sanas.' Why are apples preferred?","because they are healthy",["because they are expensive","because they are blue","because they are hot"]),("Read: 'Mañana vamos a viajar en avión.' How will they travel?","by plane",["by train","by bus","on foot"])] ,
      "Sentence building":[("Choose the correct sentence order.","Normalmente juego al fútbol después del colegio.",["Juego normalmente después colegio al fútbol del.","Al fútbol colegio normalmente del juego.","Después juego normalmente del colegio fútbol al."]),("Which connector means 'but'?","pero",["porque","y","también"]),("Complete: 'Me gusta leer ___ es relajante.'","porque",["pero","y","o"]),("Which phrase adds another idea?","también",["nunca","ayer","sin"]),("Choose the correct negative sentence.","No juego al tenis.",["Juego no al tenis.","No al tenis juego no.","Juego al no tenis."])] ,
      "Present and near future":[("What does 'voy a estudiar' mean?","I am going to study",["I studied","I study every day","I do not study"]),("Choose the correct near-future form: 'We are going to travel'.","Vamos a viajar.",["Viajamos ayer.","Ir viajar nosotros.","Vamos viajar a."]),("What does 'va a llover' mean?","it is going to rain",["it rained","it rains every day","it is sunny"]),("Which sentence is present tense?","Juego al fútbol los martes.",["Voy a jugar mañana.","Jugué ayer.","Jugar fútbol."]),("Which time phrase matches the near future?","mañana",["ayer","el año pasado","antes"])] ,
      "Past and future time phrases":[("What does 'ayer' mean?","yesterday",["tomorrow","today","next week"]),("Which phrase means 'last weekend'?","el fin de semana pasado",["el fin de semana que viene","este fin de semana","cada fin de semana"]),("What does 'la semana que viene' mean?","next week",["last week","this morning","yesterday"]),("Which sentence refers to the past?","Ayer visité un museo.",["Mañana voy a visitar un museo.","Visito museos los sábados.","Voy a un museo ahora."]),("Which sentence refers to the future?","El sábado vamos a jugar.",["El sábado pasado jugamos.","Jugamos cada sábado.","Ayer jugamos."])] ,
      "Opinions with justification":[("Which sentence gives an opinion and reason?","Creo que el uniforme es útil porque es práctico.",["El uniforme es azul.","Llevo uniforme.","Uniforme práctico porque."]),("What does 'sin embargo' mean?","however",["therefore","also","because"]),("Which phrase introduces a contrasting view?","Por otro lado",["Por ejemplo","En primer lugar","Finalmente"]),("What does 'estoy de acuerdo' mean?","I agree",["I disagree","I am tired","I understand"]),("How do you say 'I disagree because it is expensive'?","No estoy de acuerdo porque es caro.",["Estoy de acuerdo y es barato.","No acuerdo caro.","Es caro pero acuerdo."])] ,
      "Reading comprehension":[("Read: 'Aunque llovía, Marta fue al parque porque quería correr.' Why did Marta go to the park?","because she wanted to run",["because it was sunny","because she lost a book","because she wanted to swim"]),("Read: 'Pablo ahorra dinero para comprar una bicicleta nueva.' What is Pablo saving for?","a new bicycle",["a computer","a holiday","a football"]),("Read: 'El tren salió tarde, por eso llegamos a las nueve.' Why did they arrive at nine?","the train left late",["they missed the bus","the station closed","they walked slowly"]),("Read: 'Ana prefiere vivir en el campo porque es tranquilo.' Where does Ana prefer to live?","in the countryside",["in a city centre","near an airport","at school"]),("Read: 'Después de cenar, terminé mis deberes y vi una película.' What happened first?","the speaker had dinner",["the speaker watched a film","the speaker finished homework","the speaker went to school"])] ,
      "Spanish-speaking world":[("Which country has Spanish as an official language?","Mexico",["Brazil","Portugal","Italy"]),("What is the capital of Spain?","Madrid",["Barcelona","Seville","Valencia"]),("Which continent contains Argentina?","South America",["Europe","Africa","Asia"]),("Which language is mainly spoken in Brazil?","Portuguese",["Spanish","French","Italian"]),("Why is the Spanish-speaking world diverse?","It includes many countries with different histories and cultures.",["Every country is identical.","Only Spain has Spanish speakers.","Spanish is spoken on one island only."])] ,
      "Transition to secondary Spanish":[("Which strategy helps understand an unfamiliar text?","look for cognates and use context",["translate every word without context","ignore familiar words","guess from one letter only"]),("What is an infinitive?","the basic verb form, such as hablar",["a plural noun","a time phrase","a punctuation mark"]),("Which dictionary entry should be used for 'hablo'?","hablar",["habló","hablando","hablas only"]),("Which response is appropriately formal?","Buenos días, señor. ¿Cómo está?",["Hola tío, ¿qué tal?","¡Eh, tú!","Qué pasa, colega."]),("Which habit supports language progress?","short, regular practice of sounds, words and sentences",["memorising once and never reviewing","avoiding listening","using only English pronunciation"])] ,
    }
    return banks[topic]


def _ks2(year,topic,index):
    rng=stable_random("Spanish",year,topic,index)
    return render_homework("Spanish",year,topic,index,_repeat(_ks2_bank(year,topic),rng,index))


def generate_spanish_homework(year_group:int,topic:str,index:int)->tuple[str,list[str]]:
    canonical=TOPIC_ALIASES.get(topic,topic)
    if year_group==1:return _year1(canonical,index)
    if year_group==2:return _year2(canonical,index)
    if year_group in {3,4,5,6}:return _ks2(year_group,canonical,index)
    raise ValueError("year_group must be between 1 and 6")


def generate_year_homework(year_group:int,count:int=300)->list:
    topics=SPANISH_TOPICS_BY_YEAR.get(year_group,[]);config=YEAR_CONFIG.get(year_group)
    if not topics or not config:return []
    batch=[]
    for i in range(1,count+1):
        topic=topics[(i-1)%len(topics)];content,answers=generate_spanish_homework(year_group,topic,i)
        batch.append(build_batch_item(content=content,answers=answers,year_group=year_group,subject="Spanish",topic=topic,homework_minutes=config["homework_minutes"],key_stage=config["key_stage"],doc_id=f"spanish_y{year_group}_{i:04d}"))
        if i%100==0:print(f"  Generated {i}/{count}")
    return batch


def main():
    store=get_homework_rag_store();print(f"RAG target: {store.store.database_target}")
    for year in range(1,7):
        expected=HOMEWORK_COUNT[year];existing=count_year_homework(store,year,"Spanish")
        if existing>=expected:
            print(f"Year {year}: complete ({existing}/{expected})");continue
        data=generate_year_homework(year,expected);added=add_homework_in_batches(store,data)
        print(f"Year {year}: added {added}; target {len(data)}")
    get_rag_stats(store)


if __name__=="__main__":main()
