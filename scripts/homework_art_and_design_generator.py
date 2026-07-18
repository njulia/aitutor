#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate objective Art and Design homework for England Years 1-6, progressing from KS1 materials and visual elements to KS2 sketchbooks, technique, artists, architects, designers and evaluation.

The public generation and review contract is unchanged: each worksheet contains
10 numbered four-option questions and returns a positional list of 10 exact
answers for storage in ``correct_answers`` by ``src/homework_rag.py``.
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

ART_AND_DESIGN_TOPICS_BY_YEAR = {1: ['Lines and shapes', 'Primary colours', 'Texture and collage', 'Drawing painting and sculpture'],
 2: ['Pattern and printing', 'Warm and cool colours', 'Form and space', 'Artists and comparison'],
 3: ['Sketchbooks and observation', 'Tone and shading', 'Colour and mood', 'Clay and sculpture'],
 4: ['Composition', 'Perspective and depth', 'Textiles and pattern', 'Artists architects and designers'],
 5: ['Portrait and proportion', 'Mixed media', 'Printmaking', 'Evaluate and refine'],
 6: ['Visual elements and meaning',
     'Three-dimensional design',
     'Art movements and artists',
     'Curating and presentation']}

YEAR_CONFIG = {
    1: {"key_stage": "KS1" if True else "Optional enrichment", "homework_minutes": "10-15" if True else "5-10"},
    2: {"key_stage": "KS1" if True else "Optional enrichment", "homework_minutes": "10-15" if True else "5-10"},
    3: {"key_stage": "KS2", "homework_minutes": "15-20" if True else "10-15"},
    4: {"key_stage": "KS2", "homework_minutes": "15-20"},
    5: {"key_stage": "KS2", "homework_minutes": "20-25"},
    6: {"key_stage": "KS2", "homework_minutes": "20-25"},
}

QUESTION_BANKS = {1: {'Drawing painting and sculpture': [('Which material is commonly used for drawing?', 'charcoal', ['flour', 'string only', 'water']),
                                        ('Which tool is commonly used to apply paint?', 'brush', ['ruler', 'stapler', 'compass']),
                                        ('Which artwork is three-dimensional?', 'sculpture', ['pencil line', 'flat print', 'photograph']),
                                        ('Which material can be modelled by pressing and shaping it?',
                                         'clay',
                                         ['glass sheet', 'watercolour paper', 'chalk dust only']),
                                        ('What does three-dimensional mean?',
                                         'having height, width and depth',
                                         ['having only length and width', 'using three colours', 'being made in three minutes'])],
     'Lines and shapes': [('Which word describes a line that bends smoothly?', 'curved', ['straight', 'dotted', 'zigzag']),
                          ('Which shape has three straight sides?', 'triangle', ['circle', 'square', 'oval']),
                          ('What is the outside edge of a shape called?', 'outline', ['texture', 'tone', 'pattern']),
                          ('Which shape has no corners?', 'circle', ['rectangle', 'triangle', 'square']),
                          ('Which tool is most suitable for making a light sketch line?', 'pencil', ['glue stick', 'paint pot', 'clay tool'])],
     'Primary colours': [('Which set contains the three traditional primary paint colours?',
                          'red, yellow and blue',
                          ['red, green and blue', 'orange, green and purple', 'black, white and grey']),
                         ('Which colour is made by mixing red and yellow paint?', 'orange', ['green', 'purple', 'brown']),
                         ('Which colour is made by mixing blue and yellow paint?', 'green', ['orange', 'purple', 'pink']),
                         ('Which colour is made by mixing red and blue paint?', 'purple', ['green', 'orange', 'yellow']),
                         ('What is usually made by adding white to a colour?', 'a tint', ['a pattern', 'a texture', 'an outline'])],
     'Texture and collage': [('What does texture describe in art?',
                              'how a surface feels or looks as if it feels',
                              ['how loud a colour is', 'how old a picture is', 'how much it costs']),
                             ('What is a collage?',
                              'an artwork made by sticking pieces together',
                              ['a picture made only with one pencil line', 'a clay pot', 'a photograph of a building']),
                             ('Which word best describes sandpaper?', 'rough', ['smooth', 'shiny', 'transparent']),
                             ('Which material could be used in a fabric collage?', 'felt', ['water', 'air', 'sunlight']),
                             ('What does overlap mean?',
                              'one shape covers part of another',
                              ['two shapes never touch', 'a colour becomes lighter', 'a line becomes shorter'])]},
 2: {'Artists and comparison': [('Who painted The Starry Night?', 'Vincent van Gogh', ['Barbara Hepworth', 'William Morris', 'LS Lowry']),
                                ('Which artist is famous for The Great Wave off Kanagawa?',
                                 'Katsushika Hokusai',
                                 ['Vincent van Gogh', 'Yayoi Kusama', 'Alma Thomas']),
                                ('What does compare mean when discussing artworks?',
                                 'notice similarities and differences',
                                 ['copy one artwork exactly', 'choose the most expensive work', 'count only the colours']),
                                ('Which sentence describes a similarity?',
                                 'Both pictures use curved lines.',
                                 ['One picture is large and the other is small.',
                                  'The first is paint but the second is clay.',
                                  'Only one picture has people.']),
                                ('Which sentence describes a difference?',
                                 'One artwork is a sculpture and the other is a painting.',
                                 ['Both use blue.', 'Both show trees.', 'Both were made on paper.'])],
     'Form and space': [('Which word describes a solid three-dimensional shape in art?', 'form', ['line', 'tone', 'pattern']),
                        ('Which object has a cube form?', 'a dice', ['a coin face', 'a paper triangle', 'a painted line']),
                        ('What is negative space?',
                         'the empty area around or between shapes',
                         ['a dark paint only', 'a broken sculpture', 'a mistake that cannot be changed']),
                        ('Which change makes a paper sculpture stand more steadily?',
                         'making its base wider',
                         ['making its base narrower', 'removing every fold', 'placing all weight at the top']),
                        ('Which material is suitable for building a light model form?',
                         'card',
                         ['watercolour wash', 'graphite dust', 'liquid glue alone'])],
     'Pattern and printing': [('What is a pattern?', 'a design that repeats', ['a single random mark', 'a colour with white added', 'a sculpture']),
                              ('Which object can be used to make a simple repeated print?',
                               'a sponge shape',
                               ['a cup of water', 'a blank sheet only', 'a torch']),
                              ('What should happen before making the next print in a repeating pattern?',
                               'place the shape in the planned next position',
                               ['change every colour and shape randomly', 'tear the paper', 'wash away the first print']),
                              ('Which sequence is an alternating pattern?',
                               'circle, square, circle, square',
                               ['circle, circle, circle, circle', 'circle, square, triangle, star', 'square, triangle, triangle, circle']),
                              ('What is a printing block used for?',
                               'transferring an inked shape to a surface',
                               ['mixing clay', 'cutting fabric', 'measuring a frame'])],
     'Warm and cool colours': [('Which colour is usually described as warm?', 'red', ['blue', 'turquoise', 'violet']),
                               ('Which colour is usually described as cool?', 'blue', ['orange', 'red', 'yellow']),
                               ('Which group contains only warm colours?',
                                'red, orange and yellow',
                                ['blue, green and violet', 'black, white and grey', 'blue, orange and green']),
                               ('Which group contains mainly cool colours?',
                                'blue, green and violet',
                                ['red, orange and yellow', 'red, green and brown', 'yellow, pink and orange']),
                               ('Which choice would best suggest a cold winter scene?',
                                'cool blues and pale greens',
                                ['bright oranges and reds', 'only warm yellows', 'brown cardboard without colour'])]},
 3: {'Clay and sculpture': [('What does score and slip help do in clay work?',
                             'join two clay pieces',
                             ['make paint dry', 'cut fabric', 'measure a line']),
                            ('Which action changes a lump of clay by hand?', 'pinching', ['printing', 'photographing', 'weaving']),
                            ('What is an armature?',
                             'a supporting framework inside a sculpture',
                             ['a paint colour', 'a flat paper pattern', 'a type of glue brush']),
                            ('Why should a clay wall not be extremely thick?',
                             'it may dry unevenly and crack',
                             ['it will become transparent', 'it will turn into paper', 'it will always float']),
                            ('Which tool can make a repeated texture in clay?',
                             'a patterned stamp',
                             ['a torch', 'a calculator', 'a glass of water only'])],
     'Colour and mood': [('Which word describes the feeling suggested by an artwork?', 'mood', ['scale', 'frame', 'medium']),
                         ('Which colour choice often suggests energy or warmth?',
                          'bright red and orange',
                          ['pale blue and grey', 'only black pencil outlines', 'transparent glue']),
                         ('Which colour choice often suggests calm?',
                          'soft blue and green',
                          ['bright red and orange', 'neon red and black only', 'muddy brown only']),
                         ('What is a complementary colour pair?',
                          'colours opposite each other on a colour wheel',
                          ['two identical colours', 'a colour and white', 'three primary colours']),
                         ('Which pair is commonly shown as complementary?',
                          'blue and orange',
                          ['blue and green', 'red and orange', 'yellow and orange'])],
     'Sketchbooks and observation': [('What is a sketchbook mainly used for?',
                                      'recording observations and developing ideas',
                                      ['storing wet clay', 'mixing paint', 'displaying only finished work']),
                                     ('What is observational drawing?',
                                      'drawing carefully from something you can see',
                                      ['drawing with closed eyes', 'copying a word', 'making a random pattern']),
                                     ('Which note is useful beside a sketch?',
                                      'try a darker tone here',
                                      ['this page must never change', 'do not look at the object', 'all materials feel the same']),
                                     ('Why might an artist revisit a sketch?',
                                      'to improve or develop the idea',
                                      ['to erase every record of thinking', 'to avoid experimenting', 'to make the book heavier']),
                                     ('Which tool can help compare the size of parts while drawing?',
                                      "a pencil held at arm's length",
                                      ['a glue stick', 'a paint tray', 'a stapler'])],
     'Tone and shading': [('What does tone mean in drawing?',
                           'how light or dark something is',
                           ['how rough it feels', 'how loud it sounds', 'how old it is']),
                          ('How can a pencil area be made darker?',
                           'press harder or add more layers',
                           ['use less graphite and leave more white', 'rub it with water', 'cut the paper']),
                          ('Which technique uses many close parallel lines for shading?', 'hatching', ['collage', 'printing', 'weaving']),
                          ('Which technique crosses sets of lines to build darker tone?', 'cross-hatching', ['stamping', 'folding', 'washing']),
                          ('Where is a cast shadow usually found?',
                           'on the surface beside the object away from the light',
                           ['inside the light source', 'only at the top edge', 'nowhere near the object'])]},
 4: {'Artists architects and designers': [('Which person designs buildings?', 'architect', ['composer', 'geologist', 'chemist']),
                                          ('Barbara Hepworth is best known for which kind of work?', 'sculpture', ['novels', 'symphonies', 'maps']),
                                          ('William Morris is strongly associated with...',
                                           'decorative repeating patterns',
                                           ['space photography', 'Roman roads', 'digital animation only']),
                                          ('Which artist is known for paintings of industrial northern English scenes with many small figures?',
                                           'LS Lowry',
                                           ['Claude Monet', 'Frida Kahlo', 'Pablo Picasso']),
                                          ('Why study artists, architects and designers?',
                                           'to learn how ideas, materials and cultures shape creative work',
                                           ['to copy every work exactly',
                                            'to decide that only one style is correct',
                                            'to avoid making original choices'])],
     'Composition': [('What is composition in an artwork?',
                      'the arrangement of visual elements',
                      ['the price of the materials', "the artist's age", 'the drying time']),
                     ('What is the focal point?',
                      'the area that attracts attention first',
                      ['the back of the frame', 'the lightest tool', 'the empty paint pot']),
                     ('Which placement can make a composition feel balanced?',
                      'spreading visual weight thoughtfully',
                      ['putting every object in one corner', 'removing all contrast', 'using only one tiny mark']),
                     ('What is the foreground?',
                      'the part that appears closest to the viewer',
                      ['the part farthest away', 'the frame only', 'the title']),
                     ('What is the background?',
                      'the part behind the main subject',
                      ['the closest object only', 'the paintbrush', 'the paper edge'])],
     'Perspective and depth': [('What does perspective help an artist show?',
                                'depth on a flat surface',
                                ['the texture of clay only', 'the cost of paint', 'the age of paper']),
                               ('In simple perspective, objects farther away usually appear...',
                                'smaller',
                                ['larger', 'brighter than everything', 'three-dimensional in real space']),
                               ('What is a horizon line?',
                                'the apparent line where land or sea meets the sky',
                                ['the outline of every object', 'a line around a frame', 'a repeated pattern']),
                               ('What is a vanishing point?',
                                'a point where receding parallel lines seem to meet',
                                ['the darkest colour', 'the centre of a sculpture', 'a printing tool']),
                               ('Which method can also suggest depth?',
                                'overlapping shapes',
                                ['keeping every object the same size and position', 'removing the background', 'using only vertical lines'])],
     'Textiles and pattern': [('What is a textile?',
                               'a material made from fibres or fabric',
                               ['a stone sculpture', 'a glass window', 'a pencil line']),
                              ('What does weaving do?', 'interlaces threads over and under', ['melts clay', 'mixes paint', 'cuts wood']),
                              ('What is embroidery?',
                               'decorating fabric with stitches',
                               ['printing with a potato', 'drawing with charcoal', 'building with card']),
                              ('Which pattern has mirror balance?',
                               'a symmetrical pattern',
                               ['a random scribble', 'an unfinished wash', 'a single dot']),
                              ('Why is a repeated motif useful in textile design?',
                               'it creates a planned pattern',
                               ['it removes all colour', 'it makes fabric waterproof automatically', 'it changes cloth into metal'])]},
 5: {'Evaluate and refine': [('What does evaluate mean in art?',
                              'judge what works and what could improve',
                              ['throw away all experiments', 'copy another work', 'count the materials only']),
                             ('Which comment is specific and useful?',
                              'The darker background makes the yellow shape stand out.',
                              ['It is nice.', 'I like it because I do.', 'Everything is perfect.']),
                             ('What does refine mean?',
                              'make thoughtful improvements',
                              ['start again without looking', 'remove every detail', 'use more materials without a reason']),
                             ('Why compare finished work with an original intention?',
                              'to check whether choices communicate the idea',
                              ['to prove ideas never change', 'to avoid reflection', 'to count brushstrokes']),
                             ('Which evidence best shows artistic development?',
                              'sketches, trials, notes and the final work',
                              ['only the clean table', 'only unused materials', "the artist's name"])],
     'Mixed media': [('What is mixed-media art?',
                      'art combining more than one material or process',
                      ['art made only with pencil', 'art using one colour', 'art displayed outdoors only']),
                     ('Which is a mixed-media combination?',
                      'paint, printed paper and thread',
                      ['only one graphite pencil', 'only blue paint', 'only one clay tool']),
                     ('Why test materials before using them in final work?',
                      'to see how they behave together',
                      ['to guarantee no changes are needed', 'to remove every texture', 'to avoid planning']),
                     ('Which adhesive is usually suitable for lightweight paper collage?',
                      'PVA glue or glue stick',
                      ['cooking oil', 'water only', 'dry sand']),
                     ('What should an artist consider when layering transparent material?',
                      'lower layers may still be visible',
                      ['all layers become metal', 'colour disappears completely', 'the paper always tears'])],
     'Portrait and proportion': [('What is a portrait?',
                                  'an artwork representing a person',
                                  ['a map of a place', 'a sculpture of only a building', 'a repeated textile pattern']),
                                 ('What does proportion describe?',
                                  'the size relationship between parts',
                                  ['the roughness of a surface', 'the brightness of a colour', 'the age of an artist']),
                                 ('In a front-facing human face, the eyes are usually about...',
                                  'halfway down the head',
                                  ['at the very top of the head', 'below the chin', 'outside the face']),
                                 ('What is a self-portrait?',
                                  "an artist's image of themself",
                                  ['a picture of a landscape', 'a copy of a map', 'a design for a chair']),
                                 ('Which action best improves observed proportion?',
                                  'compare parts before adding detail',
                                  ['guess every size without looking', 'make every feature identical', 'avoid using guidelines'])],
     'Printmaking': [('What is a print edition?',
                      'a set of prints made from the same printing surface',
                      ['one sketchbook page', 'a group of sculptures', 'a paint palette']),
                     ('In relief printing, which areas usually receive ink?',
                      'the raised areas',
                      ['the cut-away areas only', 'the back of the paper', 'the table']),
                     ('What is registration in multi-colour printing?',
                      'aligning each printed layer',
                      ['washing the roller', 'cutting the paper randomly', 'making the ink transparent']),
                     ('Which tool spreads ink evenly on a printing block?', 'roller', ['compass', 'needle', 'ruler']),
                     ('Why should lettering be reversed on a relief block?',
                      'the print flips the image',
                      ['ink changes the alphabet', 'paper becomes transparent', 'letters cannot be printed'])]},
 6: {'Art movements and artists': [('Which movement often used fragmented shapes and several viewpoints?',
                                    'Cubism',
                                    ['Impressionism', 'Pop Art', 'Minimalism']),
                                   ('Which movement is linked with visible brushwork and changing light in outdoor scenes?',
                                    'Impressionism',
                                    ['Cubism', 'Surrealism', 'Op Art']),
                                   ('Yayoi Kusama is widely associated with repeated...', 'dots', ['Roman numerals', 'maps', 'musical notes']),
                                   ('Alma Thomas is known for abstract paintings using...',
                                    'rhythmic blocks of colour',
                                    ['only black-and-white photographs', 'marble statues only', 'architectural plans']),
                                   ('Why can an artist be influenced by a movement without copying it?',
                                    'they can adapt ideas in an original way',
                                    ['all movement artists make identical work', 'influence means tracing', 'movements forbid experimentation'])],
     'Curating and presentation': [('What does a curator do?',
                                    'selects and organises works for an exhibition',
                                    ['mixes every paint colour', 'repairs roads', 'writes computer code only']),
                                   ('What is an exhibition label used for?',
                                    'giving clear information about an artwork',
                                    ['hiding the title', 'covering the artwork', 'measuring the frame']),
                                   ('Which information usually belongs on a basic artwork label?',
                                    'artist, title, date and materials',
                                    ["artist's password", "visitor's home address", 'shop receipt only']),
                                   ('Why consider the order of works in a display?',
                                    'the sequence can guide comparison and meaning',
                                    ['order never affects viewing', 'largest work must always be first', 'all works should overlap']),
                                   ('Which lighting choice best protects delicate work on paper?',
                                    'avoiding excessive strong light',
                                    ['placing it in direct sunlight', 'using heat lamps', 'leaving it outdoors in rain'])],
     'Three-dimensional design': [('What is structural balance in sculpture?',
                                   'weight arranged so the work remains stable',
                                   ['using equal amounts of every colour', 'making every part flat', 'placing the work in a frame']),
                                  ('Which join is useful for card construction?',
                                   'tabs and slots',
                                   ['wet paint only', 'a pencil outline', 'shading']),
                                  ('Why might a sculptor make a maquette?',
                                   'to test a small model before a larger work',
                                   ['to mix printing ink', 'to write an artist biography', 'to sharpen pencils']),
                                  ('What is subtractive sculpture?',
                                   'making form by removing material',
                                   ['building by adding pieces', 'painting a flat image', 'printing repeated motifs']),
                                  ('What is additive sculpture?',
                                   'building form by adding and joining material',
                                   ['carving away stone only', 'drawing with charcoal', 'photographing a model'])],
     'Visual elements and meaning': [('Which list contains visual elements used to analyse art?',
                                      'line, colour, tone, texture, shape, form and space',
                                      ['price, age, weight and postcode', 'sound, smell and temperature only', 'title, frame and ticket only']),
                                     ('How can strong contrast affect an image?',
                                      'it can make areas stand out',
                                      ['it always removes the focal point', 'it makes every tone identical', 'it turns paint into clay']),
                                     ('What can repeated diagonal lines suggest?',
                                      'movement or energy',
                                      ['complete stillness only', 'a smooth texture only', 'no direction']),
                                     ('How can scale change meaning?',
                                      'making one subject very large can show importance',
                                      ['scale only changes paper cost', 'small objects always look close', 'scale cannot affect emphasis']),
                                     ('Which statement is an interpretation?',
                                      'The dark tones and empty space create a lonely mood.',
                                      ['The canvas is 40 centimetres wide.', 'The artist used blue paint.', 'There are three circles.'])]}}


def _repeat(items, rng, index):
    questions = []
    for offset in range(10):
        stem, answer, distractors = items[(offset + index) % len(items)]
        questions.append(make_mcq(stem, answer, distractors, rng))
    return questions


def generate_art_and_design_homework(
    year_group: int,
    topic: str,
    index: int,
) -> tuple[str, list[str]]:
    if year_group not in ART_AND_DESIGN_TOPICS_BY_YEAR:
        raise ValueError("year_group must be between 1 and 6")
    if topic not in ART_AND_DESIGN_TOPICS_BY_YEAR[year_group]:
        raise ValueError(f"Unknown Year {year_group} Art and Design topic: {topic}")

    items = QUESTION_BANKS[year_group][topic]
    rng = stable_random("Art and Design", year_group, topic, index)
    note = ""
    return render_homework(
        "Art and Design",
        year_group,
        topic,
        index,
        _repeat(items, rng, index),
        note=note,
    )


def generate_year_homework(year_group: int, count: int = 300) -> list:
    topics = ART_AND_DESIGN_TOPICS_BY_YEAR.get(year_group, [])
    config = YEAR_CONFIG.get(year_group)
    if not topics or not config:
        return []

    batch = []
    for index in range(1, count + 1):
        topic = topics[(index - 1) % len(topics)]
        content, answers = generate_art_and_design_homework(year_group, topic, index)
        batch.append(
            build_batch_item(
                content=content,
                answers=answers,
                year_group=year_group,
                subject="Art and Design",
                topic=topic,
                homework_minutes=config["homework_minutes"],
                key_stage=config["key_stage"],
                doc_id=f"art_and_design_y{year_group}_{index:04d}",
            )
        )
        if index % 100 == 0:
            print(f"  Generated {index}/{count}")
    return batch


def main():
    store = get_homework_rag_store()
    print(f"RAG target: {store.store.database_target}")
    for year_group in range(1, 7):
        expected = HOMEWORK_COUNT[year_group]
        existing = count_year_homework(store, year_group, "Art and Design")
        if existing >= expected:
            print(f"Year {year_group}: complete ({existing}/{expected})")
            continue
        homework = generate_year_homework(year_group, expected)
        added = add_homework_in_batches(store, homework)
        print(f"Year {year_group}: added {added}; target {len(homework)}")
    get_rag_stats(store)


if __name__ == "__main__":
    main()
