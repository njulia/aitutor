#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LangGraph 智能体工作流模块

包含 Hybrid Agent 的状态定义、节点函数、工作流创建和运行逻辑。
"""

import json
import logging
from typing import Dict, List, Any, Literal, TypedDict, Optional, Annotated
from datetime import datetime

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from src.models import tools
from src.prompts import (
    ASSESSMENT_PROMPT, DATA_COLLECTION_PROMPT, ANALYSIS_PROMPT,
    RECOMMENDATION_PROMPT, REACTIVE_SYSTEM_PROMPT,
)

# AGICTO API Key
LLM_MODEL = "qwen3.5-plus"

logger = logging.getLogger(__name__)

# LangSmith 配置
LANGSMITH_ENABLED = False
LANGSMITH_PROJECT = "english-tutor-hybrid-agent"


def init_llm():
    """初始化 LLM 实例"""
    import os

    agicto_api_key = os.getenv("AGICTO_API_KEY")
    if not agicto_api_key:
        logger.error("Error: AGICTO_API_KEY environment variable not found")
        logger.error("Please set the environment variable: export AGICTO_API_KEY='your-api-key'")
        exit(1)

    # 检查是否启用 LangSmith
    global LANGSMITH_ENABLED, LANGSMITH_PROJECT
    LANGSMITH_ENABLED = os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"
    LANGSMITH_PROJECT = os.getenv("LANGCHAIN_PROJECT", "english-tutor-hybrid-agent")

    llm = ChatOpenAI(
        model=LLM_MODEL,
        openai_api_key=agicto_api_key,
        openai_api_base="https://api.agicto.cn/v1/",
        temperature=0.7,
    )

    llm_with_tools = llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    return llm, llm_with_tools, tool_node


# Define state type
class EnglishTutorState(TypedDict):
    """English tutor agent state"""
    # Input
    user_query: str
    student_profile: Optional[Dict[str, Any]]

    # Processing state
    query_type: Optional[Literal["vocabulary", "grammar", "reading", "writing", "conversation", "study_plan"]]
    processing_mode: Optional[Literal["reactive", "deliberative"]]
    learning_data: Optional[Dict[str, Any]]
    analysis_results: Optional[Dict[str, Any]]

    # Message history (for tool calling)
    messages: Annotated[List[BaseMessage], add_messages]

    # Output
    final_response: Optional[str]

    # Control flow
    current_phase: Optional[str]
    error: Optional[str]


# Phase 1: Context Assessment - Determine query type and processing mode
def assess_query(state: EnglishTutorState, llm) -> Dict[str, Any]:
    logger.debug("[DEBUG] Entering node: assess_query")

    prompt = ChatPromptTemplate.from_template(ASSESSMENT_PROMPT)
    chain = prompt | llm | JsonOutputParser()
    result = chain.invoke({"user_query": state["user_query"]})

    logger.debug(f"[DEBUG] LLM assessment output: {result}")

    processing_mode = result.get("processing_mode", "reactive")
    if processing_mode not in ["reactive", "deliberative"]:
        processing_mode = "reactive"

    query_type = result.get("query_type", "vocabulary")
    if query_type not in ["vocabulary", "grammar", "reading", "writing", "conversation", "study_plan"]:
        query_type = "vocabulary"

    logger.debug(f"[DEBUG] Branch decision: processing_mode={processing_mode}, query_type={query_type}")

    return {
        "query_type": query_type,
        "processing_mode": processing_mode,
    }


# Reactive processing - Initialize messages and invoke LLM with tools
def reactive_agent(state: EnglishTutorState, llm_with_tools) -> Dict[str, Any]:
    logger.debug("[DEBUG] Entering node: reactive_agent")

    student_info = json.dumps(state.get("student_profile", {}), ensure_ascii=False, indent=2)

    system_prompt = REACTIVE_SYSTEM_PROMPT.format(student_info=student_info)

    messages = state.get("messages", [])
    if not messages:
        messages = [HumanMessage(content=f"{system_prompt}\n\nStudent Question: {state['user_query']}")]

    response = llm_with_tools.invoke(messages)
    logger.debug(f"[DEBUG] LLM response: {response}")

    return {"messages": [response]}


# Determine whether to continue calling tools
def should_continue_tools(state: EnglishTutorState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return "end"

    last_message = messages[-1]

    # Check for tool calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.debug(f"[DEBUG] Tool call detected: {last_message.tool_calls}")
        return "tools"

    return "end"


# Extract final response from messages
def extract_reactive_response(state: EnglishTutorState) -> Dict[str, Any]:
    logger.debug("[DEBUG] Entering node: extract_reactive_response")

    messages = state.get("messages", [])

    # Find the last AI message as the final response
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return {"final_response": msg.content}

    return {"final_response": "Unable to generate response"}


# Data collection - Gather learning information needed for personalized tutoring
def collect_data(state: EnglishTutorState, llm) -> Dict[str, Any]:
    logger.debug("[DEBUG] Entering node: collect_data")

    prompt = ChatPromptTemplate.from_template(DATA_COLLECTION_PROMPT)
    chain = prompt | llm | JsonOutputParser()

    result = chain.invoke({
        "user_query": state["user_query"],
        "student_profile": json.dumps(state.get("student_profile", {}), ensure_ascii=False, indent=2)
    })

    return {
        "learning_data": result.get("collected_data", {}),
        "current_phase": "analyze"
    }


# In-depth analysis - Analyze student's learning situation
def analyze_data(state: EnglishTutorState, llm) -> Dict[str, Any]:
    logger.debug("[DEBUG] Entering node: analyze_data")

    prompt = ChatPromptTemplate.from_template(ANALYSIS_PROMPT)
    chain = prompt | llm | JsonOutputParser()

    result = chain.invoke({
        "user_query": state["user_query"],
        "student_profile": json.dumps(state.get("student_profile", {}), ensure_ascii=False, indent=2),
        "learning_data": json.dumps(state.get("learning_data", {}), ensure_ascii=False, indent=2)
    })

    return {
        "analysis_results": result,
        "current_phase": "recommend"
    }


# Generate recommendations - Provide tutoring response based on analysis
def generate_recommendations(state: EnglishTutorState, llm) -> Dict[str, Any]:
    logger.debug("[DEBUG] Entering node: generate_recommendations")

    prompt = ChatPromptTemplate.from_template(RECOMMENDATION_PROMPT)
    chain = prompt | llm | StrOutputParser()

    result = chain.invoke({
        "user_query": state["user_query"],
        "student_profile": json.dumps(state.get("student_profile", {}), ensure_ascii=False, indent=2),
        "analysis_results": json.dumps(state.get("analysis_results", {}), ensure_ascii=False, indent=2)
    })

    return {
        "final_response": result,
        "current_phase": "respond"
    }


# Create agent workflow
def create_english_tutor_workflow(llm, llm_with_tools, tool_node) -> StateGraph:
    """Create English tutor hybrid agent workflow"""

    workflow = StateGraph(EnglishTutorState)

    # Add nodes (using lambda to pass llm instances)
    workflow.add_node("assess", lambda state: assess_query(state, llm))
    workflow.add_node("reactive_agent", lambda state: reactive_agent(state, llm_with_tools))
    workflow.add_node("tools", tool_node)
    workflow.add_node("extract_response", extract_reactive_response)
    workflow.add_node("collect_data", lambda state: collect_data(state, llm))
    workflow.add_node("analyze", lambda state: analyze_data(state, llm))
    workflow.add_node("recommend", lambda state: generate_recommendations(state, llm))

    # Set entry point
    workflow.set_entry_point("assess")

    # Branch routing after assessment
    workflow.add_conditional_edges(
        "assess",
        lambda x: "reactive_agent" if x.get("processing_mode") == "reactive" else "collect_data",
        {
            "reactive_agent": "reactive_agent",
            "collect_data": "collect_data"
        }
    )

    # Tool calling loop for reactive agent
    workflow.add_conditional_edges(
        "reactive_agent",
        should_continue_tools,
        {
            "tools": "tools",
            "end": "extract_response"
        }
    )

    # Return to agent after tool execution
    workflow.add_edge("tools", "reactive_agent")

    # End after extracting response
    workflow.add_edge("extract_response", END)

    # Deliberative mode flow
    workflow.add_edge("collect_data", "analyze")
    workflow.add_edge("analyze", "recommend")
    workflow.add_edge("recommend", END)

    return workflow.compile()


# Run the agent
def run_english_tutor(user_query: str, student_id: str = "student1", student_profiles: Dict = None) -> Dict[str, Any]:
    """Run the English tutor agent and return results"""

    from src.models import SAMPLE_STUDENT_PROFILES

    llm, llm_with_tools, tool_node = init_llm()
    agent = create_english_tutor_workflow(llm, llm_with_tools, tool_node)

    profiles = student_profiles or SAMPLE_STUDENT_PROFILES
    student_profile = profiles.get(student_id, profiles["student1"])

    initial_state = {
        "user_query": user_query,
        "student_profile": student_profile,
        "query_type": None,
        "processing_mode": None,
        "learning_data": None,
        "analysis_results": None,
        "messages": [],
        "final_response": None,
        "current_phase": "assess",
        "error": None
    }

    logger.info("LangGraph Mermaid Flowchart:")
    logger.info(agent.get_graph().draw_mermaid())

    # 准备 LangSmith 配置（如果启用）
    config = {}
    if LANGSMITH_ENABLED:
        logger.info(f"✓ LangSmith is enabled")
        logger.info(f"  Project: {LANGSMITH_PROJECT}")
        logger.info(f"  View Tracking: https://smith.langchain.com\n")

        config = RunnableConfig(
            tags=[
                "english-tutor",
                "hybrid-agent",
                f"student-{student_id}",
                student_profile.get("english_level", "unknown")
            ],
            metadata={
                "student_id": student_id,
                "year_group": student_profile.get("year_group", "unknown"),
                "age": student_profile.get("age", "unknown"),
                "english_level": student_profile.get("english_level", "unknown"),
                "user_query": user_query[:100],
                "timestamp": datetime.now().isoformat()
            },
            run_name=f"english-tutor-{student_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
    else:
        logger.info("ℹ LangSmith is disabled\n")

    # 运行智能体
    if config:
        result = agent.invoke(initial_state, config=config)
    else:
        result = agent.invoke(initial_state)
    return result
