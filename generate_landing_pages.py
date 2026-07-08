#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_landing_pages.py

Generates static, SEO-optimised landing pages for the Homework Magic AI Tutor,
following the same pattern as generate_11plus_page.py.

Pages generated:
- index.html (Homepage)
- ks1-homework.html (KS1 - Year 1-2)
- ks2-homework.html (KS2 - Year 3-6)
- check-my-homework.html (Homework marking feature)
"""

import json
import os

# ---------------------------------------------------------------------------
# 1. CONFIG
# ---------------------------------------------------------------------------

SITE_NAME = "Homework Magic"
SITE_URL = "https://your-domain.example"
TOOL_URL = "/app"

project_dir = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(project_dir, "static")
os.makedirs(OUTPUT_DIR, exist_ok=True)

BRAND_BLUE = "#4285F4"
BRAND_GREEN = "#34A853"
BRAND_TEXT = "#222222"


# ---------------------------------------------------------------------------
# 2. COMMON RENDERING FUNCTIONS
# ---------------------------------------------------------------------------

def render_json_ld_faq(faqs, page_name, page_path):
    """FAQPage + BreadcrumbList structured data for rich snippets."""
    faq_entities = [
        {
            "@type": "Question",
            "name": item["q"],
            "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
        }
        for item in faqs
    ]

    data = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "FAQPage",
                "mainEntity": faq_entities,
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home",
                     "item": SITE_URL + "/"},
                    {"@type": "ListItem", "position": 2, "name": page_name,
                     "item": SITE_URL + page_path},
                ],
            },
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def render_json_ld_educational_app():
    """EducationalApplication structured data for the homepage."""
    data = {
        "@context": "https://schema.org",
        "@type": "EducationalApplication",
        "name": "Homework Magic",
        "description": "AI homework generator and marker for UK primary school students, covering KS1, KS2 and 11+ preparation, aligned to the National Curriculum.",
        "applicationCategory": "EducationalApplication",
        "operatingSystem": "Web",
        "audience": {
            "@type": "EducationalAudience",
            "educationalRole": "student",
            "audienceType": "UK primary school students (ages 5-11) and parents"
        },
        "inLanguage": "en-GB",
        "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "GBP"
        }
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def render_section(section):
    html = [f'<h2>{section["heading"]}</h2>']
    for para in section.get("paragraphs", []):
        html.append(f"<p>{para}</p>")
    if section.get("list"):
        html.append("<ul>")
        for term, desc in section["list"]:
            html.append(f"<li><strong>{term}:</strong> {desc}</li>")
        html.append("</ul>")
    return "\n".join(html)


def render_faqs(faqs):
    html = ["<h2>Frequently Asked Questions</h2>"]
    for item in faqs:
        html.append(
            f'<h3>{item["q"]}</h3>\n<p>{item["a"]}</p>'
        )
    return "\n".join(html)


def render_page(page_data, sections, faqs, cta_text, page_path, page_name, json_ld=None):
    canonical = SITE_URL + page_path
    sections_html = "\n".join(render_section(s) for s in sections)
    faqs_html = render_faqs(faqs)

    if json_ld is None:
        json_ld = render_json_ld_faq(faqs, page_name, page_path)

    breadcrumb_name = page_name
    if page_path == "/":
        breadcrumb_name = "Home"

    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_data["title"]}</title>
<meta name="description" content="{page_data["meta_description"]}">
<meta name="keywords" content="{page_data["keywords"]}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{canonical}">

<meta property="og:type" content="article">
<meta property="og:title" content="{page_data["title"]}">
<meta property="og:description" content="{page_data["meta_description"]}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:locale" content="en_GB">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{page_data["title"]}">
<meta name="twitter:description" content="{page_data["meta_description"]}">

<script type="application/ld+json">
{json_ld}
</script>

<style>
  body {{
    font-family: 'Google Sans', Arial, sans-serif;
    color: {BRAND_TEXT};
    max-width: 760px;
    margin: 0 auto;
    padding: 24px;
    line-height: 1.6;
  }}
  h1 {{ font-size: 2em; }}
  h2 {{ color: {BRAND_BLUE}; margin-top: 2em; }}
  h3 {{ margin-top: 1.4em; }}
  .intro {{ font-size: 1.15em; }}
  .cta {{
    display: inline-block;
    background: {BRAND_GREEN};
    color: #ffffff;
    font-weight: bold;
    padding: 14px 28px;
    border-radius: 30px;
    text-decoration: none;
    margin: 24px 0;
  }}
  nav.breadcrumb {{ font-size: 0.9em; color: #666; margin-bottom: 16px; }}
  nav.breadcrumb a {{ color: {BRAND_BLUE}; text-decoration: none; }}
  .nav-links {{ margin-top: 2em; padding-top: 2em; border-top: 1px solid #eee; }}
  .nav-links a {{ margin-right: 1em; color: {BRAND_BLUE}; }}
</style>
</head>
<body>

<nav class="breadcrumb" aria-label="Breadcrumb">
  <a href="/">Home</a>{" &raquo; " + breadcrumb_name if page_path != "/" else ""}
</nav>

<h1>{page_data["h1"]}</h1>
<p class="intro">{page_data["intro"]}</p>

<a class="cta" href="{TOOL_URL}">{cta_text}</a>

{sections_html}

{faqs_html}

<p><a class="cta" href="{TOOL_URL}">{cta_text}</a></p>

<div class="nav-links">
   <a href="/">Home</a>
  <a href="/ks1-homework">KS1</a>
  <a href="/ks2-homework">KS2</a>
  <a href="/elevenplus-practice">11+</a>
  <a href="/elevenplus/articles">11+ Articles</a>
  <a href="/progress">Progress</a>
  <a href="/check-my-homework">Mark Homework</a>
    <a href="/login">Login</a> <!-- Added Login link -->
  <a href="/register">Register</a> <!-- Added Register link -->
                <a href="#" id="logout-link" style="display:none;">Logout</a> <!-- Placeholder for Logout -->
</div>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# 3. HOMEPAGE (index.html)
# ---------------------------------------------------------------------------

HOME_PAGE = {
    "title": "Homework Magic — AI Homework Generator & Marker for UK Primary School",
    "meta_description": (
        "Homework Magic generates personalised KS1–KS2 and 11+ homework, then marks it instantly "
        "with encouraging, curriculum-aligned feedback for UK primary school students."
    ),
    "keywords": (
        "AI homework generator, UK primary school homework, KS1 homework, KS2 homework, "
        "11 plus practice, National Curriculum homework, homework marking AI, free homework generator"
    ),
    "h1": "Homework Magic — AI Homework for UK Primary Schools",
    "intro": (
        "Homework Magic generates personalised homework for UK primary school students (Year 1–6), "
        "aligned to the National Curriculum. Then it marks your child's work instantly with friendly, "
        "constructive feedback — like having a patient tutor available 24/7."
    ),
}

HOME_SECTIONS = [
    {
        "heading": "What Homework Magic does",
        "paragraphs": [
            "Homework Magic is an AI-powered tool that creates custom homework for your child based on "
            "their year group, strengths, and interests. It covers all National Curriculum subjects for "
            "KS1 and KS2, plus 11+ preparation.",
            "Best of all, it will mark your child's homework too — explaining what they did well, where "
            "they went wrong, and how to improve next time."
        ],
    },
    {
        "heading": "Subjects covered",
        "paragraphs": [],
        "list": [
            ("Mathematics", "Arithmetic, fractions, geometry, problem-solving and more for all year groups."),
            ("English", "Comprehension, grammar, punctuation, vocabulary, and creative writing."),
            ("Science", "Biology, chemistry, physics topics aligned to the National Curriculum."),
            ("History & Geography", "Key topics from the UK primary curriculum."),
            ("Languages", "Spanish, Latin, and Chinese practice available."),
            ("11+ Preparation", "Verbal Reasoning, Non-Verbal Reasoning, Maths and English practice."),
        ],
    },
    {
        "heading": "How it works",
        "paragraphs": [
            "1. Describe your child (or use our Quick Select to pick their year group).",
            "2. Choose which subjects you'd like homework for.",
            "3. Click 'Generate My Homework' — custom questions appear in seconds.",
            "4. When your child has finished, enter their answers and get instant feedback.",
        ],
    },
    {
        "heading": "Why parents love Homework Magic",
        "paragraphs": [
            "Homework Magic saves you time, ensures your child gets practice at the right level, and provides "
            "feedback that encourages learning rather than just giving a score. It's designed to be positive, "
            "supportive, and aligned to what's actually being taught in UK primary schools."
        ],
    },
]

HOME_FAQS = [
    {
        "q": "Is Homework Magic free to use?",
        "a": "Yes, Homework Magic is completely free for personal use with your own AI API key.",
    },
    {
        "q": "Does it follow the UK National Curriculum?",
        "a": "Yes, all homework generated is aligned to the UK National Curriculum for KS1 and KS2.",
    },
    {
        "q": "What year groups does it cover?",
        "a": "Homework Magic covers Year 1 through Year 6, plus 11+ preparation for Year 5 and 6 students.",
    },
    {
        "q": "Can it mark handwritten homework?",
        "a": "Yes! You can upload a photo of your child's handwritten work and the AI will review it.",
    },
]

HOME_CTA = "Start Generating Free Homework"


# ---------------------------------------------------------------------------
# 4. KS1 PAGE
# ---------------------------------------------------------------------------

KS1_PAGE = {
    "title": "Free KS1 Homework Generator — Year 1 & 2 | Homework Magic",
    "meta_description": (
        "Generate free, personalised KS1 homework (Year 1 & 2) aligned to the UK National Curriculum. "
        "Covers Maths, English, Science and more with instant AI marking."
    ),
    "keywords": (
        "KS1 homework, Year 1 homework, Year 2 homework, free KS1 worksheets, "
        "National Curriculum KS1, primary school homework, Year 1 maths, Year 2 English"
    ),
    "h1": "Free KS1 Homework — Year 1 & 2",
    "intro": (
        "Homework Magic generates custom KS1 homework for Year 1 and Year 2 students, perfectly matched "
        "to the UK National Curriculum. From counting and phonics to simple science, get personalised "
        "practice with instant, friendly marking."
    ),
}

KS1_SECTIONS = [
    {
        "heading": "What is KS1?",
        "paragraphs": [
            "Key Stage 1 (KS1) covers children in Year 1 and Year 2 (ages 5–7). It's a crucial stage where "
            "children build foundational skills in reading, writing, and mathematics that they'll build on "
            "throughout their school journey.",
            "Homework at KS1 should be fun, engaging, and not too long — usually around 15–30 minutes per day "
            "depending on the year group."
        ],
    },
    {
        "heading": "KS1 subjects covered",
        "paragraphs": [],
        "list": [
            ("KS1 Mathematics", "Number & place value, addition & subtraction, multiplication & division, fractions, measurement, geometry, statistics."),
            ("KS1 English", "Reading (phonics, comprehension), writing (spelling, grammar, punctuation, composition), speaking & listening."),
            ("KS1 Science", "Working scientifically, living things & their habitats, animals including humans, plants, everyday materials, seasonal changes."),
            ("KS1 History & Geography", "Simple topics that introduce children to the past and the world around them."),
        ],
    },
    {
        "heading": "How to support your child in KS1",
        "paragraphs": [
            "Keep homework sessions short and positive. Praise effort as much as correctness. Read together "
            "every day — even just 10 minutes makes a huge difference. Make maths part of everyday life by "
            "counting, measuring, and talking about numbers at home."
        ],
    },
]

KS1_FAQS = [
    {
        "q": "How much homework should a Year 1 child do?",
        "a": "The recommended amount for Year 1 is about 10–15 minutes per day, plus daily reading.",
    },
    {
        "q": "How much homework should a Year 2 child do?",
        "a": "Year 2 children typically do 15–30 minutes per day, plus daily reading practice.",
    },
    {
        "q": "Does Homework Magic include phonics practice?",
        "a": "Yes, KS1 English homework includes phonics, reading comprehension, and writing practice appropriate for Year 1 and 2.",
    },
]

KS1_CTA = "Generate Free KS1 Homework"


# ---------------------------------------------------------------------------
# 5. KS2 PAGE
# ---------------------------------------------------------------------------

KS2_PAGE = {
    "title": "Free KS2 Homework Generator — Year 3, 4, 5 & 6 | Homework Magic",
    "meta_description": (
        "Generate free, personalised KS2 homework (Year 3–6) aligned to the UK National Curriculum. "
        "Covers Maths, English, Science, 11+ preparation and more with instant AI marking."
    ),
    "keywords": (
        "KS2 homework, Year 3 homework, Year 4 homework, Year 5 homework, Year 6 homework, "
        "free KS2 worksheets, National Curriculum KS2, SATs preparation"
    ),
    "h1": "Free KS2 Homework — Year 3 to 6",
    "intro": (
        "Homework Magic generates custom KS2 homework for Year 3 to Year 6 students, aligned to the UK "
        "National Curriculum and perfect for SATs preparation. Get personalised practice in Maths, English, "
        "Science and more, with instant, encouraging feedback."
    ),
}

KS2_SECTIONS = [
    {
        "heading": "What is KS2?",
        "paragraphs": [
            "Key Stage 2 (KS2) covers children in Year 3 through Year 6 (ages 7–11). This is a period of "
            "increasing independence and deeper learning, culminating in SATs assessments at the end of Year 6.",
            "Homework at KS2 helps consolidate classroom learning, develops study skills, and prepares children "
            "for secondary school."
        ],
    },
    {
        "heading": "KS2 subjects covered",
        "paragraphs": [],
        "list": [
            ("KS2 Mathematics", "Number, calculation, fractions, decimals, percentages, ratio, algebra, geometry, measurement, statistics."),
            ("KS2 English", "Reading comprehension, writing (transcription, composition, vocabulary, grammar & punctuation), spoken language."),
            ("KS2 Science", "Working scientifically, biology, chemistry, physics topics in depth."),
            ("Foundation Subjects", "History, Geography, Design & Technology, Art & Design, Computing, Languages."),
            ("11+ Preparation", "For Year 5 and 6 students preparing for grammar school entrance exams."),
        ],
    },
    {
        "heading": "SATs preparation support",
        "paragraphs": [
            "Homework Magic can help your child prepare for KS2 SATs by generating practice questions at the "
            "right level, with detailed feedback that explains not just whether an answer is right or wrong, "
            "but why — helping your child really understand the concepts."
        ],
    },
]

KS2_FAQS = [
    {
        "q": "When do SATs happen?",
        "a": "KS2 SATs take place in May of Year 6, covering English reading, English grammar, punctuation & spelling, and mathematics.",
    },
    {
        "q": "How much homework should a KS2 child do?",
        "a": "Guidelines suggest 30 minutes per day in Year 3 & 4, building to 1 hour per day by Year 6, plus reading.",
    },
    {
        "q": "Can Homework Magic help with 11+ preparation?",
        "a": "Yes! We have a dedicated 11+ tab with practice for Verbal Reasoning, Non-Verbal Reasoning, Maths and English.",
    },
]

KS2_CTA = "Generate Free KS2 Homework"


# ---------------------------------------------------------------------------
# 6. Mark Homework PAGE
# ---------------------------------------------------------------------------

CHECK_PAGE = {
    "title": "Mark Homework — Instant AI Homework Marking | Homework Magic",
    "meta_description": (
        "Get instant AI marking for your child's homework. Upload handwritten work or type in answers, "
        "and receive friendly, detailed feedback aligned to the UK National Curriculum."
    ),
    "keywords": (
        "homework checker, AI homework marking, mark my homework, homework feedback, "
        "homework help, primary school homework review, mark maths homework"
    ),
    "h1": "Mark Homework — Instant AI Marking",
    "intro": (
        "Upload a photo of your child's handwritten homework or type in their answers, and Homework Magic "
        "will mark it instantly. You'll get detailed, encouraging feedback that explains what they did well, "
        "where mistakes happened, and how to improve."
    ),
}

CHECK_SECTIONS = [
    {
        "heading": "How the homework checker works",
        "paragraphs": [
            "1. Generate some homework with Homework Magic first (or use your own).",
            "2. Have your child complete the work on paper or type answers into the box.",
            "3. Upload a photo of their work, or paste in their answers.",
            "4. Click 'Submit for Review' and get instant, detailed feedback.",
        ],
    },
    {
        "heading": "What the feedback includes",
        "paragraphs": [],
        "list": [
            ("Encouragement", "Positive feedback on what your child did well."),
            ("Explanations", "Clear explanations of any mistakes, in language children understand."),
            ("Correct answers", "The right approach or answer shown clearly."),
            ("Next steps", "Suggestions for what to practice next."),
        ],
    },
    {
        "heading": "Supported formats",
        "paragraphs": [
            "You can upload photos (JPG, PNG, HEIC), PDF files, or simply type answers directly into the text box. "
            "Handwritten work works best when the photo is well-lit and the writing is clear."
        ],
    },
]

CHECK_FAQS = [
    {
        "q": "Can it mark handwritten work?",
        "a": "Yes! Just take a clear photo of your child's homework and upload it — the AI will read and review it.",
    },
    {
        "q": "What subjects can it mark?",
        "a": "All UK primary school subjects including Maths, English, Science, History, Geography, and more.",
    },
    {
        "q": "Does it replace a teacher?",
        "a": "No — Homework Magic is a supplementary tool to support home learning, not a replacement for school teaching.",
    },
]

CHECK_CTA = "Try the Homework Checker"


# ---------------------------------------------------------------------------
# 7. MAIN FUNCTION
# ---------------------------------------------------------------------------

def main():
    pages = [
        ("index.html", HOME_PAGE, HOME_SECTIONS, HOME_FAQS, HOME_CTA, "/", "Home", render_json_ld_educational_app()),
        ("ks1-homework.html", KS1_PAGE, KS1_SECTIONS, KS1_FAQS, KS1_CTA, "/ks1-homework", "KS1", None),
        ("ks2-homework.html", KS2_PAGE, KS2_SECTIONS, KS2_FAQS, KS2_CTA, "/ks2-homework", "KS2", None),
        ("check-my-homework.html", CHECK_PAGE, CHECK_SECTIONS, CHECK_FAQS, CHECK_CTA, "/check-my-homework", "Mark Homework", None),
    ]

    for filename, page_data, sections, faqs, cta_text, page_path, page_name, json_ld in pages:
        output_path = os.path.join(OUTPUT_DIR, filename)
        html = render_page(page_data, sections, faqs, cta_text, page_path, page_name, json_ld)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Wrote {len(html):,} characters to {output_path}")

    print(f"\nGenerated {len(pages)} landing pages in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
