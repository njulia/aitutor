#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
简化的智能体工作流模块

已移除 LangGraph 依赖，使用纯 Python 实现轻量级路由。
保留原有的 reactive / deliberative 双模式逻辑，但不再依赖状态图。
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from src.llm_client import LLMClient, format_prompt, build_messages
from src.models import (
    SAMPLE_STUDENT_PROFILES, tools_schema, execute_tool,
)
from src.prompts import (
    ASSESSMENT_PROMPT, DATA_COLLECTION_PROMPT, ANALYSIS_PROMPT,
    RECOMMENDATION_PROMPT, REACTIVE_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


class SimpleAgentWorkflow:
    """简化的智能体工作流，替代 LangGraph 的状态图

    保留两种处理模式：
    - reactive: 快速响应，支持工具调用
    - deliberative: 多步分析（收集数据 -> 分析 -> 推荐）
    """

    def __init__(self, llm: LLMClient):
        self.llm = llm

    def run(self, user_query: str, student_profile: Dict[str, Any] = None) -> Dict[str, Any]:
        """运行智能体工作流

        Args:
            user_query: 学生的问题
            student_profile: 学生档案

        Returns:
            包含 final_response 的字典
        """
        if student_profile is None:
            student_profile = SAMPLE_STUDENT_PROFILES.get("student1", {})

        # 1. 评估查询类型和处理模式
        assessment = self._assess_query(user_query)
        processing_mode = assessment.get("processing_mode", "reactive")

        logger.debug("[Agent] assessment: mode=%s, type=%s",
                     processing_mode, assessment.get("query_type"))

        # 2. 根据模式路由
        if processing_mode == "reactive":
            final_response = self._reactive_process(user_query, student_profile)
        else:
            final_response = self._deliberative_process(user_query, student_profile)

        return {
            "final_response": final_response,
            "query_type": assessment.get("query_type"),
            "processing_mode": processing_mode,
        }

    def _assess_query(self, user_query: str) -> Dict[str, Any]:
        """评估查询类型和处理模式"""
        prompt_text = format_prompt(ASSESSMENT_PROMPT, user_query=user_query)
        messages = build_messages(prompt_text)
        try:
            result = self.llm.complete_json(messages, temperature=0.3)
        except Exception as e:
            logger.warning("[Agent] 评估失败，使用默认 reactive 模式: %s", e)
            result = {"query_type": "vocabulary", "processing_mode": "reactive"}

        # 校验字段
        if result.get("processing_mode") not in ("reactive", "deliberative"):
            result["processing_mode"] = "reactive"
        if result.get("query_type") not in (
            "vocabulary", "grammar", "reading", "writing", "conversation", "study_plan"
        ):
            result["query_type"] = "vocabulary"

        return result

    def _reactive_process(self, user_query: str, student_profile: Dict[str, Any]) -> str:
        """Reactive 模式：快速响应，支持工具调用循环"""
        student_info = json.dumps(student_profile, ensure_ascii=False, indent=2)
        system_prompt = format_prompt(REACTIVE_SYSTEM_PROMPT, student_info=student_info)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Student Question: {user_query}"},
        ]

        # 工具调用循环（最多 3 轮）
        for _ in range(3):
            response = self.llm.complete_with_tools(messages, tools_schema)

            # 检查是否有工具调用
            tool_calls = response.get("tool_calls")
            if not tool_calls:
                # 没有工具调用，返回最终文本
                return response.get("content", "Unable to generate response")

            # 将 AI 的工具调用消息加入历史
            messages.append(response)

            # 执行每个工具调用
            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    func_args = json.loads(tc["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    func_args = {}

                tool_result = execute_tool(func_name, func_args)

                # 将工具结果加入消息历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })

        # 超出循环次数，最后一次不带工具调用获取回复
        final = self.llm.complete(messages)
        return final or "Unable to generate response"

    def _deliberative_process(self, user_query: str, student_profile: Dict[str, Any]) -> str:
        """Deliberative 模式：多步分析（收集 -> 分析 -> 推荐）"""
        profile_str = json.dumps(student_profile, ensure_ascii=False, indent=2)

        # 步骤 1: 数据收集
        prompt_text = format_prompt(
            DATA_COLLECTION_PROMPT,
            user_query=user_query,
            student_profile=profile_str,
        )
        messages = build_messages(prompt_text)
        try:
            data_result = self.llm.complete_json(messages, temperature=0.3)
            learning_data = data_result.get("collected_data", {})
        except Exception as e:
            logger.warning("[Agent] 数据收集失败: %s", e)
            learning_data = {}

        # 步骤 2: 深度分析
        prompt_text = format_prompt(
            ANALYSIS_PROMPT,
            user_query=user_query,
            student_profile=profile_str,
            learning_data=json.dumps(learning_data, ensure_ascii=False, indent=2),
        )
        messages = build_messages(prompt_text)
        try:
            analysis_results = self.llm.complete_json(messages, temperature=0.3)
        except Exception as e:
            logger.warning("[Agent] 分析失败: %s", e)
            analysis_results = {}

        # 步骤 3: 生成推荐
        prompt_text = format_prompt(
            RECOMMENDATION_PROMPT,
            user_query=user_query,
            student_profile=profile_str,
            analysis_results=json.dumps(analysis_results, ensure_ascii=False, indent=2),
        )
        messages = build_messages(prompt_text)
        result = self.llm.complete(messages)

        return result or "Unable to generate response"


# ---- 模块级便捷接口（保持向后兼容） ----

def init_llm() -> LLMClient:
    """初始化 LLM 实例，返回 LLMClient

    保持与原 init_llm() 的调用兼容性。
    """
    return LLMClient()


def run_english_tutor(user_query: str, student_id: str = "student1", student_profiles: Dict = None) -> Dict[str, Any]:
    """运行 English tutor 智能体并返回结果

    Args:
        user_query: 学生的问题
        student_id: 学生 ID
        student_profiles: 学生档案字典

    Returns:
        包含 final_response 的字典
    """
    llm = init_llm()
    workflow = SimpleAgentWorkflow(llm)

    profiles = student_profiles or SAMPLE_STUDENT_PROFILES
    student_profile = profiles.get(student_id, profiles.get("student1", {}))

    logger.info("[Agent] Running tutor for student %s", student_id)
    return workflow.run(user_query, student_profile)
