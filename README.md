# AI Tutor - Hybrid English Tutor

A hybrid agent AI tutoring system built with LangGraph, providing intelligent after-school tutoring for UK primary school students (Year 1–6).

## Architecture

Three-tier hybrid agent architecture:

1. **Bottom (Reactive)**: Instantly responds to student questions with rapid feedback
2. **Middle (Coordination)**: Evaluates question type and difficulty, dynamically selects processing mode
3. **Top (Deliberative)**: Performs learning analysis and creates personalized study plans

## Features

- Generates age-appropriate English homework based on UK Department for Education guidelines
- Automatic subject detection (Math, English, Science, History, Geography, etc.)
- Homework review and feedback
- Student learning analytics and personalized recommendations
- Built-in 《中文》(Zhongwen) textbook PDF resources (Volumes 1–12)

## Requirements

- Python 3.10+
- AGICTO API Key

## Quick Start

```bash
# Set API Key
export AGICTO_API_KEY="your-api-key"

# (Optional) Enable LangSmith tracing for debugging
export LANGCHAIN_TRACING_V2="true"
export LANGCHAIN_API_KEY="your-langsmith-key"

# Install dependencies
pip install langchain-openai langchain-core langgraph pydantic

# Run
python hybrid_english_tutor_langgraph.py
```

## Project Structure

```
ai_tutor/
├── hybrid_english_tutor_langgraph.py  # Main program: LangGraph hybrid agent
├── prompts.py                         # Prompt templates
├── gui_template.html                  # Frontend UI template
├── styles.css                         # Stylesheet
└── chinese/                           # 《中文》textbook PDF resources (Volumes 1–12)
```

## Subjects

Math, English, Science, History, Geography, Design and Technology, Art and Design, Computing, Latin, Spanish, Chinese
