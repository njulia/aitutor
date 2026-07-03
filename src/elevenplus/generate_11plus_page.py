#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_11plus_page.py

Generates a static, SEO-optimised landing page for 11+ preparation content.

Why a separate static page instead of the Gradio app:
Gradio serves the whole tool from one client-rendered URL, so a tab inside it
can never be independently indexed by Google. This script produces a real,
crawlable HTML page with actual body content targeting "11 plus" search
terms, which then links through to the interactive Gradio tool
(e.g. mounted at /app?tab=eleven_plus).

Content is kept as structured Python data (PAGE, SECTIONS, FAQS) rather than
hardcoded HTML strings, so the same render_page() function can be reused to
generate the other landing pages (KS1, KS2, "check my homework", etc.) just
by swapping in different data.

Usage:
    python generate_11plus_page.py
    -> writes 11-plus-practice.html to the output directory
"""

import json
import os

# ---------------------------------------------------------------------------
# 1. CONFIG — update these once you have a real domain / final tool URL
# ---------------------------------------------------------------------------

SITE_NAME = "Homework Magic"
SITE_URL = "https://your-domain.example"          # TODO: replace with real domain
PAGE_PATH = "/11-plus-practice"                     # final URL path for this page
TOOL_URL = "/app?tab=eleven_plus_tab"               # where the Gradio tool lives
project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(project_dir, "static")
OUTPUT_FILENAME = "11-plus-practice.html"

BRAND_BLUE = "#4285F4"
BRAND_GREEN = "#34A853"
BRAND_TEXT = "#222222"

# ---------------------------------------------------------------------------
# 2. PAGE-LEVEL METADATA (title, meta description, OG/Twitter tags)
# ---------------------------------------------------------------------------

PAGE = {
    "title": "Free 11 Plus (11+) Practice Questions & Preparation | Homework Magic",
    "meta_description": (
        "Free 11 plus practice questions and a personalised AI-generated 11+ "
        "study plan covering Maths, English, Verbal Reasoning and Non-Verbal "
        "Reasoning — plus instant marking with friendly feedback."
    ),
    "keywords": (
        "11 plus, 11+, eleven plus practice papers, 11 plus preparation, "
        "GL Assessment practice, CEM 11 plus, grammar school entrance exam, "
        "verbal reasoning practice, non-verbal reasoning practice"
    ),
    "h1": "Free 11 Plus Practice & Preparation",
    "intro": (
        "Homework Magic generates personalised 11+ practice questions across "
        "Maths, English, Verbal Reasoning and Non-Verbal Reasoning, then marks "
        "your child's answers instantly with clear, encouraging feedback — so "
        "you can see exactly where to focus revision next."
    ),
}

# ---------------------------------------------------------------------------
# 3. BODY CONTENT — real, original copy (this is what actually earns rankings)
# ---------------------------------------------------------------------------

SECTIONS = [
    {
        "heading": "What is the 11 Plus exam?",
        "paragraphs": [
            "The 11 plus (11+) is an entrance exam used by grammar schools and "
            "some independent schools across England and Northern Ireland to "
            "select pupils moving from Year 6 into Year 7. Most children sit "
            "the exam in the September or October of Year 6, meaning "
            "preparation typically needs to start in Year 4 or Year 5.",
            "Exactly what's tested, and how, varies by region and by the "
            "organisation that sets the exam for that area, which is why a "
            "good preparation plan needs to be matched to the right exam "
            "board and format rather than treated as one generic test.",
        ],
    },
    {
        "heading": "Which exam boards are used for 11+?",
        "paragraphs": [
            "Two organisations set most 11+ papers in England: GL Assessment "
            "and CEM (now run under Durham University's Centre for Evaluation "
            "and Monitoring, though many areas have moved to GL-style papers "
            "in recent years). Some areas, and many independent schools, use "
            "their own bespoke papers instead, and the Independent Schools "
            "Examinations Board (ISEB) Common Pre-Test is widely used for "
            "independent school entry.",
            "It's worth checking directly with your target school(s) or local "
            "authority which board and format they currently use before "
            "settling on a preparation approach, since question styles differ "
            "meaningfully between boards — particularly for verbal and "
            "non-verbal reasoning.",
        ],
    },
    {
        "heading": "What subjects does the 11+ cover?",
        "paragraphs": [],
        "list": [
            ("Mathematics", "Arithmetic, fractions, ratio, geometry and "
             "problem-solving at a Year 5/6 standard, often under timed "
             "conditions."),
            ("English", "Comprehension, grammar, punctuation, vocabulary and "
             "sometimes creative or continuous writing."),
            ("Verbal Reasoning", "Word- and logic-based puzzles: codes, "
             "sequences, analogies, and word relationships."),
            ("Non-Verbal Reasoning", "Pattern, shape and spatial reasoning "
             "questions that don't rely on reading ability."),
        ],
    },
    {
        "heading": "How Homework Magic helps with 11+ preparation",
        "paragraphs": [
            "Rather than working through generic, one-size-fits-all practice "
            "papers, Homework Magic builds a short profile of your child — "
            "year group, current strengths, and areas they find harder — and "
            "generates practice questions pitched at the right level across "
            "all four 11+ subject areas.",
            "Once your child has answered, Homework Magic reviews the work "
            "and gives specific, encouraging feedback: what they got right, "
            "where the mistake happened, and what to try next — the same way "
            "a tutor would talk through a paper with them, rather than just "
            "marking it right or wrong.",
        ],
    },
    {
        "heading": "Tips for parents preparing a child for the 11+",
        "paragraphs": [],
        "list": [
            ("Start early, keep it short", "15–30 minutes a day over many "
             "months tends to work better than long weekend cramming "
             "sessions, especially for maintaining a child's confidence and "
             "motivation."),
            ("Practise under timed conditions", "Real 11+ exams are strictly "
             "timed, so building some familiarity with working at pace "
             "matters as much as knowing the content."),
            ("Mix all four subject areas", "Verbal and non-verbal reasoning "
             "are unfamiliar question styles for most children — don't let "
             "Maths and English preparation crowd them out."),
            ("Watch for exam fatigue", "Regularly review how your child "
             "feels about the process, not just their scores — motivation "
             "matters over a multi-month preparation period."),
        ],
    },
]

FAQS = [
    {
        "q": "When should my child start preparing for the 11 plus?",
        "a": (
            "Most families begin focused 11+ preparation in Year 4 or early "
            "Year 5, giving 12–18 months of steady, low-pressure practice "
            "before exams typically held in Year 6."),
    },
    {
        "q": "Is the 11+ the same everywhere in England?",
        "a": (
            "No. Format, exam board (commonly GL Assessment or CEM-style) "
            "and subjects tested vary by local authority and by individual "
            "school, so it's important to confirm the specific format used "
            "by your target schools."),
    },
    {
        "q": "Does Homework Magic replace 11+ tuition?",
        "a": (
            "Homework Magic is designed as a daily practice and feedback "
            "tool to complement whatever preparation approach a family is "
            "using — whether that's self-study, a tutor, or a prep course — "
            "rather than a replacement for expert exam-specific guidance."),
    },
]

CTA_TEXT = "Generate a Free 11+ Practice Set"

# ---------------------------------------------------------------------------
# 4. RENDERING — turns the structured content above into HTML
# ---------------------------------------------------------------------------

def render_json_ld():
    """FAQPage + BreadcrumbList structured data for rich snippets."""
    faq_entities = [
        {
            "@type": "Question",
            "name": item["q"],
            "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
        }
        for item in FAQS
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
                    {"@type": "ListItem", "position": 2, "name": "11 Plus Practice",
                     "item": SITE_URL + PAGE_PATH},
                ],
            },
        ],
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


def render_faqs():
    html = ["<h2>Frequently Asked Questions</h2>"]
    for item in FAQS:
        html.append(
            f'<h3>{item["q"]}</h3>\n<p>{item["a"]}</p>'
        )
    return "\n".join(html)


def render_page():
    canonical = SITE_URL + PAGE_PATH
    sections_html = "\n".join(render_section(s) for s in SECTIONS)
    faqs_html = render_faqs()
    json_ld = render_json_ld()

    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{PAGE["title"]}</title>
<meta name="description" content="{PAGE["meta_description"]}">
<meta name="keywords" content="{PAGE["keywords"]}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{canonical}">

<meta property="og:type" content="article">
<meta property="og:title" content="{PAGE["title"]}">
<meta property="og:description" content="{PAGE["meta_description"]}">
<meta property="og:url" content="{canonical}">
<meta property="og:site_name" content="{SITE_NAME}">
<meta property="og:locale" content="en_GB">

<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{PAGE["title"]}">
<meta name="twitter:description" content="{PAGE["meta_description"]}">

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
</style>
</head>
<body>

<nav class="breadcrumb" aria-label="Breadcrumb">
  <a href="/">Home</a> &raquo; 11 Plus Practice
</nav>

<h1>{PAGE["h1"]}</h1>
<p class="intro">{PAGE["intro"]}</p>

<a class="cta" href="{TOOL_URL}">{CTA_TEXT}</a>

{sections_html}

{faqs_html}

<p><a class="cta" href="{TOOL_URL}">{CTA_TEXT}</a></p>

</body>
</html>
"""


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILENAME)
    html = render_page()
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {len(html):,} characters to {output_path}")


if __name__ == "__main__":
    main()
