#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
检查各年级Spanish作业是否存在，缺失则生成 100 份作业并添加到 RAG 存储
支持 Year 1-6 所有年级
"""
import sys
import os
import random

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from homework_rag import get_homework_rag_store


# 各年级西班牙语主题（英国小学课程）
SPANISH_TOPICS_BY_YEAR = {
    1: [
        "Greetings and Introductions",
        "Numbers 1-10",
        "Colours",
        "Animals",
        "Family Members",
        "Food and Drink",
        "Days of the Week",
        "Simple Commands",
    ],
    2: [
        "Numbers 1-20",
        "Body Parts",
        "Clothes",
        "Weather",
        "Months and Seasons",
        "Feelings and Emotions",
        "Hobbies and Sports",
        "School Objects",
    ],
    3: [
        "Numbers 1-100",
        "Telling Time",
        "Daily Routine",
        "My House",
        "Town and Places",
        "Likes and Dislikes",
        "Describing People",
        "Simple Conversations",
    ],
    4: [
        "Numbers and Prices",
        "Ordering Food",
        "Holidays and Travel",
        "Past Tense Introduction",
        "Giving Directions",
        "Shopping",
        "My Bedroom",
        "Weather Forecasts",
    ],
    5: [
        "Present Tense Verbs",
        "Future Plans",
        "Comparing Cultures",
        "Writing Emails",
        "Restaurant Dialogues",
        "Transport",
        "Health and Illness",
        "Environmental Topics",
    ],
    6: [
        "Past Tense (Preterite)",
        "Opinions and Justifications",
        "Formal and Informal Register",
        "Reading Comprehension",
        "Creative Writing in Spanish",
        "Spanish-speaking Countries",
        "Festivals and Traditions",
        "Transition to Secondary Spanish",
    ],
}


def generate_spanish_homework(year_group: int, topic: str, index: int) -> str:
    """根据年级、主题生成西班牙语作业"""

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
    """Year 1 西班牙语作业（5-6 岁）"""
    if topic == "Greetings and Introductions":
        questions = [
            "1. Learn: Hola = Hello",
            "2. Learn: Adios = Goodbye",
            "3. Learn: Buenos dias = Good morning",
            "4. Learn: Buenas tardes = Good afternoon",
            "5. Learn: Como te llamas? = What is your name?",
            "6. Learn: Me llamo... = My name is...",
            "7. Practise saying 'Hola' to 3 people",
            "8. Write your name in Spanish: Me llamo ___",
            "9. Match: Hola - Hello, Adios - Goodbye",
            "10. Draw a speech bubble and write 'Hola!'",
        ]
    elif topic == "Numbers 1-10":
        questions = [
            "Learn the numbers 1-10 in Spanish:",
            "1 = uno, 2 = dos, 3 = tres, 4 = cuatro, 5 = cinco",
            "6 = seis, 7 = siete, 8 = ocho, 9 = nueve, 10 = diez",
            "",
            "1. Write the number for 'tres'",
            "2. Write the Spanish for '5'",
            "3. Count from 1 to 10 in Spanish",
            "4. What number is 'siete'?",
            "5. Write 'ocho' in numbers",
            "6. Match: uno-1, dos-2, tres-3",
            "7. Write the numbers 1-5 in Spanish",
            "8. Write the numbers 6-10 in Spanish",
            "9. How do you say '4' in Spanish?",
            "10. How do you say '9' in Spanish?",
        ]
    elif topic == "Colours":
        questions = [
            "Learn the colours in Spanish:",
            "red = rojo, blue = azul, green = verde, yellow = amarillo",
            "black = negro, white = blanco, pink = rosa, orange = naranja",
            "",
            "1. What colour is 'rojo'?",
            "2. Write 'blue' in Spanish",
            "3. What colour is 'verde'?",
            "4. Write 'yellow' in Spanish",
            "5. Colour a circle rojo",
            "6. Colour a square azul",
            "7. Match: negro-black, blanco-white",
            "8. What colour is the sky? Write in Spanish",
            "9. What colour is grass? Write in Spanish",
            "10. Name 3 colours in Spanish",
        ]
    elif topic == "Animals":
        questions = [
            "Learn the animals in Spanish:",
            "cat = gato, dog = perro, fish = pez, bird = pajaro",
            "rabbit = conejo, horse = caballo, cow = vaca, pig = cerdo",
            "",
            "1. What is 'gato' in English?",
            "2. Write 'dog' in Spanish",
            "3. What is 'pez' in English?",
            "4. Write 'bird' in Spanish",
            "5. Match: gato-cat, perro-dog",
            "6. Draw a gato and label it",
            "7. Draw a perro and label it",
            "8. Which animal is 'vaca'?",
            "9. Name 3 animals in Spanish",
            "10. What is your favourite animal? Write in Spanish",
        ]
    elif topic == "Family Members":
        questions = [
            "Learn family members in Spanish:",
            "mother = madre, father = padre, sister = hermana, brother = hermano",
            "grandmother = abuela, grandfather = abuelo",
            "",
            "1. What is 'madre' in English?",
            "2. Write 'father' in Spanish",
            "3. What is 'hermana' in English?",
            "4. Write 'brother' in Spanish",
            "5. Match: madre-mother, padre-father",
            "6. Draw your family and label in Spanish",
            "7. What is 'abuela' in English?",
            "8. Write 'grandfather' in Spanish",
            "9. How do you say 'sister' in Spanish?",
            "10. How do you say 'brother' in Spanish?",
        ]
    elif topic == "Food and Drink":
        questions = [
            "Learn food and drink in Spanish:",
            "apple = manzana, bread = pan, milk = leche, water = agua",
            "banana = platano, cheese = queso, egg = huevo, rice = arroz",
            "",
            "1. What is 'manzana' in English?",
            "2. Write 'bread' in Spanish",
            "3. What is 'leche' in English?",
            "4. Write 'water' in Spanish",
            "5. Match: agua-water, leche-milk",
            "6. Draw your favourite food and label in Spanish",
            "7. What is 'queso' in English?",
            "8. Write 'apple' in Spanish",
            "9. Say 'I like apples' in Spanish: Me gustan las manzanas",
            "10. Name 3 foods in Spanish",
        ]
    elif topic == "Days of the Week":
        questions = [
            "Learn the days of the week in Spanish:",
            "Monday = lunes, Tuesday = martes, Wednesday = miercoles",
            "Thursday = jueves, Friday = viernes, Saturday = sabado, Sunday = domingo",
            "",
            "1. What is 'lunes' in English?",
            "2. Write 'Friday' in Spanish",
            "3. What day is 'miercoles'?",
            "4. Write 'Sunday' in Spanish",
            "5. Match: lunes-Monday, viernes-Friday",
            "6. Write all 7 days in Spanish",
            "7. What day comes after 'martes'?",
            "8. What day comes before 'sabado'?",
            "9. What is your favourite day? Write in Spanish",
            "10. Practise saying the days in order",
        ]
    elif topic == "Simple Commands":
        questions = [
            "Learn commands in Spanish:",
            "Sit down = Sientate, Stand up = Levantate, Listen = Escucha",
            "Look = Mira, Be quiet = Callate, Come here = Ven aqui",
            "",
            "1. What does 'Sientate' mean?",
            "2. Write 'Stand up' in Spanish",
            "3. What does 'Escucha' mean?",
            "4. Write 'Look' in Spanish",
            "5. Match: Mira-Look, Escucha-Listen",
            "6. What does 'Callate' mean?",
            "7. Write 'Come here' in Spanish",
            "8. Practise the commands with a partner",
            "9. Draw someone saying 'Sientate'",
            "10. Write 3 commands you learned",
        ]
    else:
        questions = [f"{i+1}. Year 1 Spanish practice question {i+1}" for i in range(10)]

    return f"Spanish Homework - Year 1 - {topic} (Set {index:03d})\n\n" + "\n".join(questions)


def _generate_year2_homework(topic: str, index: int) -> str:
    """Year 2 西班牙语作业（6-7 岁）"""
    if topic == "Numbers 1-20":
        questions = [
            "Learn numbers 11-20 in Spanish:",
            "11 = once, 12 = doce, 13 = trece, 14 = catorce, 15 = quince",
            "16 = dieciseis, 17 = diecisiete, 18 = dieciocho, 19 = diecinueve, 20 = veinte",
            "",
            "1. Write '15' in Spanish",
            "2. What number is 'doce'?",
            "3. Write '18' in Spanish",
            "4. What number is 'veinte'?",
            "5. Count from 10 to 20 in Spanish",
            "6. Match: once-11, doce-12, trece-13",
            "7. Write numbers 1-10 in Spanish",
            "8. Write numbers 11-20 in Spanish",
            "9. What is 10 + 5 in Spanish?",
            "10. What is 20 - 3 in Spanish?",
        ]
    elif topic == "Body Parts":
        questions = [
            "Learn body parts in Spanish:",
            "head = cabeza, hand = mano, foot = pie, eye = ojo",
            "nose = nariz, mouth = boca, ear = oreja, arm = brazo",
            "",
            "1. What is 'cabeza' in English?",
            "2. Write 'hand' in Spanish",
            "3. What is 'ojo' in English?",
            "4. Write 'nose' in Spanish",
            "5. Match: boca-mouth, nariz-nose",
            "6. Draw a person and label 5 body parts in Spanish",
            "7. What is 'pie' in English?",
            "8. Write 'ear' in Spanish",
            "9. Touch your 'cabeza'!",
            "10. Name 5 body parts in Spanish",
        ]
    elif topic == "Clothes":
        questions = [
            "Learn clothes in Spanish:",
            "shirt = camiseta, trousers = pantalones, shoes = zapatos, dress = vestido",
            "jacket = chaqueta, hat = sombrero, socks = calcetines, coat = abrigo",
            "",
            "1. What is 'camiseta' in English?",
            "2. Write 'shoes' in Spanish",
            "3. What is 'vestido' in English?",
            "4. Write 'hat' in Spanish",
            "5. Match: pantalones-trousers, zapatos-shoes",
            "6. What are you wearing today? Label in Spanish",
            "7. Draw and label 3 clothes items",
            "8. What is 'abrigo' in English?",
            "9. Write 'jacket' in Spanish",
            "10. Name 4 clothes in Spanish",
        ]
    elif topic == "Weather":
        questions = [
            "Learn weather words in Spanish:",
            "sunny = soleado, rainy = lluvioso, cloudy = nublado, windy = ventoso",
            "snowy = nevado, hot = calor, cold = frio, stormy = tormentoso",
            "",
            "1. What is 'soleado' in English?",
            "2. Write 'rainy' in Spanish",
            "3. What is 'frio' in English?",
            "4. Write 'hot' in Spanish",
            "5. Match: nublado-cloudy, ventoso-windy",
            "6. What is the weather today? Write in Spanish",
            "7. Draw a sunny day and write 'soleado'",
            "8. Draw a rainy day and write 'lluvioso'",
            "9. What is 'nevado' in English?",
            "10. Name 3 weather words in Spanish",
        ]
    elif topic == "Months and Seasons":
        questions = [
            "Learn months and seasons in Spanish:",
            "Spring = primavera, Summer = verano, Autumn = otono, Winter = invierno",
            "January = enero, February = febrero, March = marzo",
            "",
            "1. What is 'primavera' in English?",
            "2. Write 'summer' in Spanish",
            "3. What is 'invierno' in English?",
            "4. Write 'autumn' in Spanish",
            "5. Match: verano-summer, otono-autumn",
            "6. Write the 4 seasons in Spanish",
            "7. What month is your birthday? Write in Spanish",
            "8. Write 'enero' in English",
            "9. What season is it now? Write in Spanish",
            "10. Name 3 months in Spanish",
        ]
    elif topic == "Feelings and Emotions":
        questions = [
            "Learn feelings in Spanish:",
            "happy = feliz, sad = triste, angry = enfadado, tired = cansado",
            "hungry = hambriento, scared = asustado, excited = emocionado, bored = aburrido",
            "",
            "1. What is 'feliz' in English?",
            "2. Write 'sad' in Spanish",
            "3. What is 'cansado' in English?",
            "4. Write 'angry' in Spanish",
            "5. Match: triste-sad, enfadado-angry",
            "6. How are you today? Write in Spanish: Estoy ___",
            "7. Draw a happy face and write 'feliz'",
            "8. Draw a sad face and write 'triste'",
            "9. What is 'emocionado' in English?",
            "10. Name 4 feelings in Spanish",
        ]
    elif topic == "Hobbies and Sports":
        questions = [
            "Learn hobbies and sports in Spanish:",
            "football = futbol, swimming = natacion, reading = lectura, dancing = baile",
            "painting = pintura, cycling = ciclismo, running = correr, singing = cantar",
            "",
            "1. What is 'futbol' in English?",
            "2. Write 'swimming' in Spanish",
            "3. What is 'lectura' in English?",
            "4. Write 'dancing' in Spanish",
            "5. Match: natacion-swimming, baile-dancing",
            "6. What is your hobby? Write: Me gusta ___",
            "7. Draw your favourite sport and label in Spanish",
            "8. What is 'cantar' in English?",
            "9. Write 'running' in Spanish",
            "10. Name 3 hobbies in Spanish",
        ]
    elif topic == "School Objects":
        questions = [
            "Learn school objects in Spanish:",
            "book = libro, pen = boligrafo, pencil = lapiz, ruler = regla",
            "rubber = goma, bag = mochila, desk = pupitre, computer = ordenador",
            "",
            "1. What is 'libro' in English?",
            "2. Write 'pen' in Spanish",
            "3. What is 'lapiz' in English?",
            "4. Write 'ruler' in Spanish",
            "5. Match: boligrafo-pen, goma-rubber",
            "6. What is in your bag? List 3 items in Spanish",
            "7. Draw a classroom and label 5 objects",
            "8. What is 'mochila' in English?",
            "9. Write 'desk' in Spanish",
            "10. Name 5 school objects in Spanish",
        ]
    else:
        questions = [f"{i+1}. Year 2 Spanish practice question {i+1}" for i in range(10)]

    return f"Spanish Homework - Year 2 - {topic} (Set {index:03d})\n\n" + "\n".join(questions)


def _generate_year3_homework(topic: str, index: int) -> str:
    """Year 3 西班牙语作业（7-8 岁）"""
    if topic == "Numbers 1-100":
        questions = [
            "Learn tens in Spanish:",
            "10 = diez, 20 = veinte, 30 = treinta, 40 = cuarenta, 50 = cincuenta",
            "60 = sesenta, 70 = setenta, 80 = ochenta, 90 = noventa, 100 = cien",
            "",
            "1. Write '30' in Spanish",
            "2. What number is 'cincuenta'?",
            "3. Write '70' in Spanish",
            "4. What number is 'ochenta'?",
            "5. Count by tens: diez, veinte, ___",
            "6. Write '45' in Spanish (cuarenta y cinco)",
            "7. Write '82' in Spanish",
            "8. What is 'sesenta y tres' in numbers?",
            "9. What is 20 + 30 in Spanish?",
            "10. What is 100 - 50 in Spanish?",
        ]
    elif topic == "Telling Time":
        questions = [
            "Learn to tell time in Spanish:",
            "What time is it? = Que hora es?",
            "It is... = Son las...",
            "1:00 = Es la una, 2:00 = Son las dos",
            "half past = y media, quarter past = y cuarto",
            "",
            "1. How do you ask the time in Spanish?",
            "2. Write 'It is 3 o'clock' in Spanish",
            "3. What time is 'Son las cinco'?",
            "4. Write 'half past 4' in Spanish",
            "5. What time is 'Son las dos y media'?",
            "6. Draw a clock showing 3:00 and write in Spanish",
            "7. Draw a clock showing 6:30 and write in Spanish",
            "8. What is 'y cuarto' in English?",
            "9. Write 'quarter past 7' in Spanish",
            "10. Practise telling 3 times in Spanish",
        ]
    elif topic == "Daily Routine":
        questions = [
            "Learn daily routine phrases in Spanish:",
            "I wake up = Me despierto, I get up = Me levanto",
            "I have breakfast = Desayuno, I go to school = Voy al colegio",
            "I have lunch = Almuerzo, I go to bed = Me acuesto",
            "",
            "1. What is 'Me despierto' in English?",
            "2. Write 'I get up' in Spanish",
            "3. What is 'Desayuno' in English?",
            "4. Write 'I go to school' in Spanish",
            "5. Match: Me levanto-I get up, Almuerzo-I have lunch",
            "6. Write your morning routine in Spanish (3 sentences)",
            "7. What time do you 'desayuno'?",
            "8. Write 'Me acuesto' in English",
            "9. Order: Me despierto, Voy al colegio, Me levanto",
            "10. Name 4 daily routine phrases in Spanish",
        ]
    elif topic == "My House":
        questions = [
            "Learn rooms and items in Spanish:",
            "kitchen = cocina, bedroom = dormitorio, bathroom = bano, living room = salon",
            "garden = jardin, door = puerta, window = ventana, table = mesa",
            "",
            "1. What is 'cocina' in English?",
            "2. Write 'bedroom' in Spanish",
            "3. What is 'bano' in English?",
            "4. Write 'garden' in Spanish",
            "5. Match: salon-living room, jardin-garden",
            "6. Draw your house and label 4 rooms in Spanish",
            "7. What is 'puerta' in English?",
            "8. Write 'window' in Spanish",
            "9. Describe your bedroom in 2 sentences (Spanish)",
            "10. Name 5 house items in Spanish",
        ]
    elif topic == "Town and Places":
        questions = [
            "Learn places in town in Spanish:",
            "school = colegio, park = parque, shop = tienda, hospital = hospital",
            "library = biblioteca, cinema = cine, restaurant = restaurante, church = iglesia",
            "",
            "1. What is 'colegio' in English?",
            "2. Write 'park' in Spanish",
            "3. What is 'tienda' in English?",
            "4. Write 'library' in Spanish",
            "5. Match: hospital-hospital, cine-cinema",
            "6. Draw a map of your town and label 4 places in Spanish",
            "7. What is 'biblioteca' in English?",
            "8. Write 'restaurant' in Spanish",
            "9. Where do you go on weekends? Write in Spanish",
            "10. Name 6 places in town in Spanish",
        ]
    elif topic == "Likes and Dislikes":
        questions = [
            "Learn to express likes and dislikes in Spanish:",
            "I like = Me gusta, I don't like = No me gusta",
            "I love = Me encanta, I hate = Odio",
            "Do you like? = Te gusta?",
            "",
            "1. How do you say 'I like' in Spanish?",
            "2. Write 'I don't like' in Spanish",
            "3. Translate: Me gusta el futbol",
            "4. Write 'I love music' in Spanish",
            "5. Translate: No me gusta la lluvia",
            "6. Write 3 things you like in Spanish",
            "7. Write 2 things you don't like in Spanish",
            "8. Ask a friend 'Te gusta?' about 3 things",
            "9. What is 'Me encanta' in English?",
            "10. Write a dialogue about likes (4 lines)",
        ]
    elif topic == "Describing People":
        questions = [
            "Learn to describe people in Spanish:",
            "tall = alto, short = bajo, fat = gordo, thin = delgado",
            "blonde = rubio, brunette = moreno, kind = amable, funny = gracioso",
            "",
            "1. What is 'alto' in English?",
            "2. Write 'short' in Spanish",
            "3. What is 'rubio' in English?",
            "4. Write 'funny' in Spanish",
            "5. Match: gordo-fat, delgado-thin",
            "6. Describe your friend in 3 sentences (Spanish)",
            "7. What is 'amable' in English?",
            "8. Write 'brunette' in Spanish",
            "9. Describe yourself in Spanish (2 sentences)",
            "10. Name 5 describing words in Spanish",
        ]
    elif topic == "Simple Conversations":
        questions = [
            "Learn useful conversation phrases:",
            "Please = Por favor, Thank you = Gracias, Sorry = Lo siento",
            "Excuse me = Perdon, Yes = Si, No = No",
            "I don't understand = No entiendo, Can you repeat? = Puedes repetir?",
            "",
            "1. How do you say 'please' in Spanish?",
            "2. Write 'thank you' in Spanish",
            "3. What is 'Lo siento' in English?",
            "4. Write 'I don't understand' in Spanish",
            "5. Match: Gracias-Thank you, Si-Yes",
            "6. Write a short dialogue (6 lines) using these phrases",
            "7. What is 'Perdon' in English?",
            "8. Write 'Can you repeat?' in Spanish",
            "9. Practise ordering food in Spanish",
            "10. Write 5 conversation phrases you learned",
        ]
    else:
        questions = [f"{i+1}. Year 3 Spanish practice question {i+1}" for i in range(10)]

    return f"Spanish Homework - Year 3 - {topic} (Set {index:03d})\n\n" + "\n".join(questions)


def _generate_year4_homework(topic: str, index: int) -> str:
    """Year 4 西班牙语作业（8-9 岁）"""
    if topic == "Numbers and Prices":
        questions = [
            "Learn to talk about prices in Spanish:",
            "How much is it? = Cuanto cuesta?",
            "It costs... = Cuesta...",
            "euros = euros, cents = centimos",
            "",
            "1. How do you ask the price in Spanish?",
            "2. Write 'It costs 5 euros' in Spanish",
            "3. Translate: Cuanto cuesta el libro?",
            "4. Write 'It costs 12 euros' in Spanish",
            "5. Match: Cuanto cuesta?-How much?, Cuesta-It costs",
            "6. Write prices for 3 items in Spanish",
            "7. Role-play: Ask the price of 2 items",
            "8. What is 'centimos' in English?",
            "9. Write a shopping list with prices (5 items)",
            "10. Translate: El pan cuesta dos euros",
        ]
    elif topic == "Ordering Food":
        questions = [
            "Learn to order food in Spanish:",
            "I would like... = Me gustaria..., Can I have...? = Puedo tener...?",
            "The bill, please = La cuenta, por favor",
            "breakfast = desayuno, lunch = almuerzo, dinner = cena",
            "",
            "1. How do you say 'I would like' in Spanish?",
            "2. Write 'Can I have water?' in Spanish",
            "3. What is 'La cuenta' in English?",
            "4. Write 'breakfast' in Spanish",
            "5. Match: almuerzo-lunch, cena-dinner",
            "6. Write a restaurant dialogue (8 lines)",
            "7. Order 3 foods you like in Spanish",
            "8. What is 'Me gustaria' in English?",
            "9. Write 'The bill, please' in Spanish",
            "10. Name 5 foods in Spanish you could order",
        ]
    elif topic == "Holidays and Travel":
        questions = [
            "Learn holiday vocabulary in Spanish:",
            "beach = playa, hotel = hotel, suitcase = maleta, passport = pasaporte",
            "plane = avion, train = tren, ticket = billete, map = mapa",
            "",
            "1. What is 'playa' in English?",
            "2. Write 'suitcase' in Spanish",
            "3. What is 'avion' in English?",
            "4. Write 'ticket' in Spanish",
            "5. Match: tren-train, mapa-map",
            "6. Where do you go on holiday? Write in Spanish",
            "7. Pack your suitcase: list 5 items in Spanish",
            "8. What is 'pasaporte' in English?",
            "9. Write 'I go by plane' in Spanish: Voy en avion",
            "10. Describe your dream holiday in Spanish (3 sentences)",
        ]
    elif topic == "Past Tense Introduction":
        questions = [
            "Learn simple past tense in Spanish:",
            "I went = Fui, I ate = Comi, I played = Juge",
            "I saw = Vi, I had = Tuve, I was = Estuve",
            "",
            "1. What is 'Fui' in English?",
            "2. Write 'I ate' in Spanish",
            "3. What is 'Vi' in English?",
            "4. Write 'I had' in Spanish",
            "5. Match: Comi-I ate, Tuve-I had",
            "6. Write 3 things you did yesterday (Spanish)",
            "7. Translate: Fui al parque ayer",
            "8. What is 'Juge' in English?",
            "9. Write 'I was at school' in Spanish",
            "10. Write a short diary entry (4 sentences) about yesterday",
        ]
    elif topic == "Giving Directions":
        questions = [
            "Learn directions in Spanish:",
            "left = izquierda, right = derecha, straight on = todo recto",
            "next to = al lado de, opposite = enfrente de, between = entre",
            "Where is...? = Donde esta...?",
            "",
            "1. What is 'izquierda' in English?",
            "2. Write 'right' in Spanish",
            "3. What is 'todo recto' in English?",
            "4. Write 'next to' in Spanish",
            "5. Match: derecha-right, enfrente de-opposite",
            "6. Give directions from school to the park (Spanish)",
            "7. Draw a simple map and write directions in Spanish",
            "8. What is 'Donde esta...?' in English?",
            "9. Write 'between' in Spanish",
            "10. Ask for directions to the cinema (Spanish dialogue)",
        ]
    elif topic == "Shopping":
        questions = [
            "Learn shopping vocabulary in Spanish:",
            "shop = tienda, buy = comprar, expensive = caro, cheap = barato",
            "I'm looking for... = Busco..., Do you have...? = Tiene...?",
            "size = talla, colour = color, I'll take it = Me lo llevo",
            "",
            "1. What is 'tienda' in English?",
            "2. Write 'buy' in Spanish",
            "3. What is 'caro' in English?",
            "4. Write 'cheap' in Spanish",
            "5. Match: comprar-buy, barato-cheap",
            "6. Write 'I'm looking for a shirt' in Spanish",
            "7. Role-play: Buy something in a shop (6 lines)",
            "8. What is 'talla' in English?",
            "9. Write 'I'll take it' in Spanish",
            "10. Write a shopping dialogue in Spanish",
        ]
    elif topic == "My Bedroom":
        questions = [
            "Learn bedroom vocabulary in Spanish:",
            "bed = cama, wardrobe = armario, desk = escritorio, lamp = lampara",
            "shelf = estante, computer = ordenador, posters = posters, carpet = alfombra",
            "In my bedroom... = En mi dormitorio...",
            "",
            "1. What is 'cama' in English?",
            "2. Write 'wardrobe' in Spanish",
            "3. What is 'lampara' in English?",
            "4. Write 'desk' in Spanish",
            "5. Match: armario-wardrobe, ordenador-computer",
            "6. Describe your bedroom in Spanish (5 sentences)",
            "7. Draw your bedroom and label 6 items in Spanish",
            "8. What is 'estante' in English?",
            "9. Write 'In my bedroom there is...' in Spanish",
            "10. Name 8 bedroom items in Spanish",
        ]
    elif topic == "Weather Forecasts":
        questions = [
            "Learn to talk about weather forecasts in Spanish:",
            "The weather forecast = El pronostico del tiempo",
            "Today it will be... = Hoy va a estar...",
            "Tomorrow = Manana, This week = Esta semana",
            "temperature = temperatura, degrees = grados",
            "",
            "1. What is 'El pronostico del tiempo' in English?",
            "2. Write 'Tomorrow' in Spanish",
            "3. Write 'Today it will be sunny' in Spanish",
            "4. What is 'temperatura' in English?",
            "5. Match: manana-tomorrow, grados-degrees",
            "6. Write a weather forecast for tomorrow (Spanish)",
            "7. What is the temperature today? Write in Spanish",
            "8. Write 'This week it will rain' in Spanish",
            "9. Draw weather symbols and label in Spanish",
            "10. Present a weather forecast (5 sentences, Spanish)",
        ]
    else:
        questions = [f"{i+1}. Year 4 Spanish practice question {i+1}" for i in range(10)]

    return f"Spanish Homework - Year 4 - {topic} (Set {index:03d})\n\n" + "\n".join(questions)


def _generate_year5_homework(topic: str, index: int) -> str:
    """Year 5 西班牙语作业（9-10 岁）"""
    if topic == "Present Tense Verbs":
        questions = [
            "Learn present tense verb endings in Spanish:",
            "hablar (to speak): yo hablo, tu hablas, el/ella habla, nosotros hablamos",
            "comer (to eat): yo como, tu comes, el/ella come, nosotros comemos",
            "vivir (to live): yo vivo, tu vives, el/ella vive, nosotros vivimos",
            "",
            "1. Conjugate 'hablar' for 'yo'",
            "2. Conjugate 'comer' for 'tu'",
            "3. Conjugate 'vivir' for 'el/ella'",
            "4. Write 'I speak Spanish' in Spanish",
            "5. Write 'We eat lunch' in Spanish",
            "6. Translate: Ellos viven en Londres",
            "7. Conjugate 'hablar' for 'nosotros'",
            "8. Write 3 sentences using present tense verbs",
            "9. What is the 'yo' ending for -ar verbs?",
            "10. What is the 'tu' ending for -er verbs?",
        ]
    elif topic == "Future Plans":
        questions = [
            "Learn to talk about future plans in Spanish:",
            "I am going to... = Voy a...",
            "Next week = La semana que viene, Tomorrow = Manana",
            "This weekend = Este fin de semana, Next year = El ano que viene",
            "",
            "1. How do you say 'I am going to' in Spanish?",
            "2. Write 'I am going to study' in Spanish",
            "3. What is 'La semana que viene' in English?",
            "4. Write 'This weekend' in Spanish",
            "5. Match: manana-tomorrow, El ano que viene-next year",
            "6. Write 3 future plans in Spanish",
            "7. Translate: Voy a visitar a mi abuela",
            "8. What will you do tomorrow? Write in Spanish",
            "9. Write 'Next year I am going to...' in Spanish",
            "10. Write about your weekend plans (5 sentences, Spanish)",
        ]
    elif topic == "Comparing Cultures":
        questions = [
            "Learn about Spanish-speaking cultures:",
            "Spain = Espana, Mexico = Mexico, Argentina = Argentina",
            "Language = idioma/ lengua, Culture = cultura",
            "Tradition = tradicion, Festival = festival",
            "",
            "1. Name 3 Spanish-speaking countries",
            "2. What is 'Espana' in English?",
            "3. Write 'culture' in Spanish",
            "4. Name a Spanish festival",
            "5. Compare school life in UK and Spain (3 points)",
            "6. What food is popular in Mexico?",
            "7. Write 'tradition' in Spanish",
            "8. What time do Spanish people eat lunch?",
            "9. Name 2 differences between UK and Spanish culture",
            "10. Write 3 facts about a Spanish-speaking country",
        ]
    elif topic == "Writing Emails":
        questions = [
            "Learn to write emails in Spanish:",
            "Dear... = Querido/Estimado..., Best wishes = Saludos cordiales",
            "I am writing to... = Te escribo para..., How are you? = Como estas?",
            "I hope you are well = Espero que estes bien",
            "",
            "1. How do you start an informal email in Spanish?",
            "2. Write 'Best wishes' in Spanish",
            "3. How do you say 'How are you?' in Spanish?",
            "4. Write 'I am writing to tell you...' in Spanish",
            "5. Match: Querido-Dear, Saludos cordiales-Best wishes",
            "6. Write an email to a Spanish friend (8-10 sentences)",
            "7. What is 'Espero que estes bien' in English?",
            "8. Write an email about your school (Spanish)",
            "9. List 5 useful email phrases in Spanish",
            "10. Reply to a friend's email (6 sentences, Spanish)",
        ]
    elif topic == "Restaurant Dialogues":
        questions = [
            "Learn restaurant dialogue phrases:",
            "A table for... = Una mesa para..., Can I see the menu? = Puedo ver la carta?",
            "I would like... = Quisiera..., For starters... = De primero...",
            "For main... = De segundo..., For dessert... = De postre...",
            "",
            "1. How do you ask for a table in Spanish?",
            "2. Write 'Can I see the menu?' in Spanish",
            "3. What is 'De primero' in English?",
            "4. Write 'For dessert' in Spanish",
            "5. Match: Una mesa para-A table for, Quisiera-I would like",
            "6. Write a full restaurant dialogue (10-12 lines)",
            "7. Order a 3-course meal in Spanish",
            "8. What is 'la carta' in English?",
            "9. Ask for the bill in Spanish",
            "10. Role-play: waiter and customer dialogue",
        ]
    elif topic == "Transport":
        questions = [
            "Learn transport vocabulary in Spanish:",
            "bus = autobus, car = coche, bicycle = bicicleta, train = tren",
            "plane = avion, boat = barco, underground = metro, taxi = taxi",
            "I go by... = Voy en..., How do you get to...? = Como llegas a...?",
            "",
            "1. What is 'autobus' in English?",
            "2. Write 'bicycle' in Spanish",
            "3. What is 'metro' in English?",
            "4. Write 'boat' in Spanish",
            "5. Match: coche-car, avion-plane",
            "6. How do you get to school? Write in Spanish",
            "7. Translate: Voy en autobus al colegio",
            "8. What is 'barco' in English?",
            "9. Write 'How do you get to...?' in Spanish",
            "10. Compare 3 types of transport in Spanish",
        ]
    elif topic == "Health and Illness":
        questions = [
            "Learn health vocabulary in Spanish:",
            "I feel ill = Me siento mal, I have a headache = Tengo dolor de cabeza",
            "I have a cold = Tengo un resfriado, I need a doctor = Necesito un medico",
            "pharmacy = farmacia, medicine = medicina, appointment = cita",
            "",
            "1. How do you say 'I feel ill' in Spanish?",
            "2. Write 'I have a headache' in Spanish",
            "3. What is 'farmacia' in English?",
            "4. Write 'medicine' in Spanish",
            "5. Match: resfriado-cold, medico-doctor",
            "6. Translate: Tengo dolor de estomago",
            "7. What do you say at the pharmacy? (Spanish)",
            "8. Write 'I need a doctor' in Spanish",
            "9. What is 'cita' in English?",
            "10. Write a dialogue at the doctor's (8 lines)",
        ]
    elif topic == "Environmental Topics":
        questions = [
            "Learn environmental vocabulary in Spanish:",
            "environment = medio ambiente, pollution = contaminacion",
            "recycle = reciclar, protect = proteger, nature = naturaleza",
            "tree = arbol, river = rio, ocean = oceano, animal = animal",
            "",
            "1. What is 'medio ambiente' in English?",
            "2. Write 'recycle' in Spanish",
            "3. What is 'contaminacion' in English?",
            "4. Write 'protect' in Spanish",
            "5. Match: naturaleza-nature, arbol-tree",
            "6. How can you help the environment? (Spanish, 3 points)",
            "7. Translate: Debemos proteger la naturaleza",
            "8. Write 'pollution' in Spanish",
            "9. Name 3 environmental problems in Spanish",
            "10. Write about protecting nature (5 sentences, Spanish)",
        ]
    else:
        questions = [f"{i+1}. Year 5 Spanish practice question {i+1}" for i in range(10)]

    return f"Spanish Homework - Year 5 - {topic} (Set {index:03d})\n\n" + "\n".join(questions)


def _generate_year6_homework(topic: str, index: int) -> str:
    """Year 6 西班牙语作业（10-11 岁）"""
    if topic == "Past Tense (Preterite)":
        questions = [
            "Learn the preterite (past tense) in Spanish:",
            "hablar: yo hable, tu hablaste, el hablo, nosotros hablamos",
            "comer: yo comi, tu comiste, el comio, nosotros comimos",
            "vivir: yo vivi, tu viviste, el vivio, nosotros vivimos",
            "",
            "1. Conjugate 'hablar' in preterite for 'yo'",
            "2. Conjugate 'comer' in preterite for 'el'",
            "3. Conjugate 'vivir' in preterite for 'nosotros'",
            "4. Write 'I spoke yesterday' in Spanish",
            "5. Write 'We ate pizza' in Spanish",
            "6. Translate: Ellos vivieron en Madrid",
            "7. Write 5 things you did last weekend (Spanish)",
            "8. What is the preterite ending for -ar verbs (yo)?",
            "9. What is the preterite ending for -er verbs (tu)?",
            "10. Write a short story in past tense (6 sentences)",
        ]
    elif topic == "Opinions and Justifications":
        questions = [
            "Learn to give opinions in Spanish:",
            "I think that... = Creo que..., In my opinion = En mi opinion",
            "because = porque, therefore = por lo tanto",
            "I agree = Estoy de acuerdo, I disagree = No estoy de acuerdo",
            "",
            "1. How do you say 'I think that' in Spanish?",
            "2. Write 'In my opinion' in Spanish",
            "3. What is 'porque' in English?",
            "4. Write 'I agree' in Spanish",
            "5. Match: Estoy de acuerdo-I agree, No estoy de acuerdo-I disagree",
            "6. Give your opinion on school uniforms (Spanish, 4 sentences)",
            "7. Translate: Creo que es importante estudiar idiomas",
            "8. Write 'therefore' in Spanish",
            "9. Give 3 opinions about learning Spanish (with reasons)",
            "10. Write a paragraph justifying your favourite subject (Spanish)",
        ]
    elif topic == "Formal and Informal Register":
        questions = [
            "Learn formal vs informal Spanish:",
            "Informal: tu (you), Formal: usted (you)",
            "Informal: Como estas? Formal: Como esta usted?",
            "Informal: Gracias, Formal: Muchas gracias",
            "",
            "1. What is the formal word for 'tu'?",
            "2. Write 'How are you?' formally in Spanish",
            "3. When would you use 'usted'?",
            "4. Write an informal greeting in Spanish",
            "5. Write a formal greeting in Spanish",
            "6. Convert to formal: 'Tu eres mi amigo'",
            "7. Convert to informal: 'Usted es muy amable'",
            "8. Write a formal email opening (Spanish)",
            "9. Write an informal text to a friend (Spanish)",
            "10. List 3 differences between formal and informal Spanish",
        ]
    elif topic == "Reading Comprehension":
        questions = [
            "Read and answer in Spanish:",
            "'Maria vive en Barcelona con su familia. Ella tiene doce anos y va al colegio todos los dias. Su asignatura favorita es matematicas porque le gusta resolver problemas. Los fines de semana, Maria va al parque con sus amigos o lee libros en casa.'",
            "",
            "1. Donde vive Maria?",
            "2. Cuantos anos tiene Maria?",
            "3. Que asignatura le gusta?",
            "4. Por que le gusta matematicas?",
            "5. Que hace los fines de semana?",
            "6. Con quien vive Maria?",
            "7. Va Maria al colegio todos los dias?",
            "8. Lee Maria libros?",
            "9. Escribe 3 hechos sobre Maria (en espanol)",
            "10. Te gustaria ser amigo de Maria? Por que?",
        ]
    elif topic == "Creative Writing in Spanish":
        questions = [
            "Write a story in Spanish (10-15 sentences):",
            "",
            "Title: 'Un dia en la playa' (A day at the beach)",
            "",
            "Include:",
            "1. Where and when the story happens",
            "2. Who is in the story",
            "3. What happens (beginning, middle, end)",
            "4. Use past tense verbs",
            "5. Use describing words (adjectives)",
            "6. Use connectors (y, pero, porque, entonces)",
            "7. Include dialogue",
            "8. A surprise or funny moment",
            "",
            "Write in full sentences. Check spelling and grammar.",
        ]
    elif topic == "Spanish-speaking Countries":
        questions = [
            "Learn about Spanish-speaking countries:",
            "Spain (Espana), Mexico (Mexico), Argentina (Argentina)",
            "Colombia (Colombia), Peru (Peru), Chile (Chile)",
            "Capital cities: Madrid, Ciudad de Mexico, Buenos Aires",
            "",
            "1. Name 6 Spanish-speaking countries",
            "2. What is the capital of Spain?",
            "3. What is the capital of Mexico?",
            "4. Write 'Argentina' in Spanish",
            "5. Match: Madrid-Espana, Buenos Aires-Argentina",
            "6. Which country is famous for tacos?",
            "7. What language do they speak in Peru?",
            "8. Write about one country (5 facts, Spanish)",
            "9. What is the largest Spanish-speaking country?",
            "10. Compare Spain and Mexico (3 differences)",
        ]
    elif topic == "Festivals and Traditions":
        questions = [
            "Learn about Spanish festivals:",
            "La Tomatina = tomato throwing festival",
            "Dia de los Muertos = Day of the Dead (Mexico)",
            "Semana Santa = Holy Week",
            "Las Fallas = fireworks festival in Valencia",
            "",
            "1. What is La Tomatina?",
            "2. Write 'Day of the Dead' in Spanish",
            "3. When is Semana Santa?",
            "4. What happens at Las Fallas?",
            "5. Match: La Tomatina-tomatoes, Dia de los Muertos-Dead",
            "6. Which festival would you like to attend? Why? (Spanish)",
            "7. Compare a Spanish festival with a UK celebration",
            "8. Draw a festival scene and label in Spanish",
            "9. Write about your favourite festival (6 sentences, Spanish)",
            "10. What food is eaten at Spanish festivals?",
        ]
    elif topic == "Transition to Secondary Spanish":
        questions = [
            "Prepare for secondary school Spanish:",
            "Review: greetings, numbers, colours, animals, family",
            "Review: present tense, past tense, future plans",
            "Review: opinions, descriptions, dialogues",
            "",
            "1. Write a self-introduction in Spanish (5 sentences)",
            "2. Count 1-20 in Spanish",
            "3. Name 10 animals in Spanish",
            "4. Describe your family in Spanish (4 sentences)",
            "5. Write what you did yesterday (Spanish, 4 sentences)",
            "6. Write your plans for next year (Spanish, 4 sentences)",
            "7. Give your opinion about learning Spanish (Spanish)",
            "8. Translate 5 sentences from English to Spanish",
            "9. Write a dialogue: meeting someone new (Spanish)",
            "10. Set 3 goals for Spanish at secondary school",
        ]
    else:
        questions = [f"{i+1}. Year 6 Spanish practice question {i+1}" for i in range(10)]

    return f"Spanish Homework - Year 6 - {topic} (Set {index:03d})\n\n" + "\n".join(questions)


# 各年级 Key Stage 和作业时间设置
YEAR_CONFIG = {
    1: {"key_stage": "KS1", "homework_minutes": "10-15"},
    2: {"key_stage": "KS1", "homework_minutes": "10-15"},
    3: {"key_stage": "KS2", "homework_minutes": "20-30"},
    4: {"key_stage": "KS2", "homework_minutes": "20-30"},
    5: {"key_stage": "KS2", "homework_minutes": "30"},
    6: {"key_stage": "KS2", "homework_minutes": "30"},
}


def check_year_spanish_exists(year_group: int) -> bool:
    """检查指定年级是否已有西班牙语作业"""
    store = get_homework_rag_store()
    results = store.search(query="spanish", k=1, filters={"year_group": year_group, "subject": "Spanish"})
    return len(results) > 0


def generate_year_homework(year_group: int, count: int = 100) -> list:
    """为指定年级生成指定数量的西班牙语作业"""
    topics = SPANISH_TOPICS_BY_YEAR.get(year_group, [])
    if not topics:
        print(f"警告：未找到 Year {year_group} 的西班牙语主题")
        return []

    config = YEAR_CONFIG.get(year_group, {"key_stage": "KS2", "homework_minutes": "20-30"})
    batch_data = []

    for i in range(1, count + 1):
        topic = topics[(i - 1) % len(topics)]
        content = generate_spanish_homework(year_group, topic, i)

        doc_id = f"hw_spanish_y{year_group}_{i:03d}"
        metadata = {
            "year_group": year_group,
            "subject": "Spanish",
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
    """主函数：检查各年级西班牙语作业，缺失则生成"""
    print("检查各年级Spanish作业是否存在...\n")

    store = get_homework_rag_store()
    years_to_generate = []

    for year in range(1, 7):
        exists = check_year_spanish_exists(year)
        status = "已有" if exists else "缺失"
        print(f"  Year {year}: {status}")
        if not exists:
            years_to_generate.append(year)

    if not years_to_generate:
        print("\n所有年级Spanish作业已存在，无需生成。")
        return

    print(f"\n需要生成的年级: {', '.join(f'Year {y}' for y in years_to_generate)}")

    for year in years_to_generate:
        print(f"\n开始生成 Year {year} Spanish作业...")
        batch_data = generate_year_homework(year, count=100)

        if batch_data:
            store.add_batch_homework(batch_data)
            print(f"成功添加 {len(batch_data)} 份 Year {year} Spanish作业到 RAG 存储")

    # 显示统计信息
    stats = store.get_stats()
    print(f"\nRAG 存储统计:")
    print(f"  总文档数: {stats['total_documents']}")
    print(f"  按主题分布: {stats['by_subject']}")
    print(f"  按年级分布: {stats['by_year_group']}")


if __name__ == "__main__":
    main()
