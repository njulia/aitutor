#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件读取工具模块

提供图片 OCR、文本文件读取、PDF 读取等功能。
"""

import os
import base64
import logging

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

LLM_MODEL = "qwen3.5-plus"
AGICTO_API_KEY = os.getenv("AGICTO_API_KEY")

logger = logging.getLogger(__name__)


def extract_text_from_image(image_path: str) -> str:
    """从图片中提取文本（使用多模态 LLM）"""
    try:
        vision_llm = ChatOpenAI(
            model=LLM_MODEL,
            openai_api_key=AGICTO_API_KEY,
            openai_api_base="https://api.agicto.cn/v1/",
            temperature=0,
        )

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        message = HumanMessage(content=[
            {"type": "text",
             "text": "Please extract all the text content from this image. This is a student's homework. Only return the text you see, do not add any commentary."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}}
        ])

        response = vision_llm.invoke([message])
        return response.content
    except Exception as e:
        logger.error(f"Failed to extract text from image: {e}")
        return ""


def read_text_file(file_path: str) -> str:
    """读取文本文件内容"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='gbk') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read text file: {e}")
            return ""
    except Exception as e:
        logger.error(f"Failed to read text file: {e}")
        return ""


def read_image_file(image_path: str) -> str:
    """从图片文件中提取文本（使用多模态 LLM）"""
    try:
        return extract_text_from_image(image_path)
    except Exception as e:
        logger.error(f"Failed to read image file: {e}")
        return ""


def read_pdf_file(pdf_path: str) -> str:
    """从 PDF 文件中提取文本内容"""
    try:
        try:
            from pypdf import PdfReader
        except ImportError:
            from PyPDF2 import PdfReader

        reader = PdfReader(pdf_path)
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        return "\n\n".join(text_parts) if text_parts else ""
    except ImportError:
        logger.error("pypdf/PyPDF2 not installed. Please run: pip install pypdf")
        return ""
    except Exception as e:
        logger.error(f"Failed to read PDF file: {e}")
        return ""
