#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件读取工具模块

提供图片 OCR、文本文件读取、PDF 读取等功能。
已移除 LangChain 依赖，使用轻量级 LLMClient 进行视觉识别。
"""

import os
import base64
import logging

from src.llm_client import LLMClient, VISION_MODEL

logger = logging.getLogger(__name__)


def extract_text_from_image(image_path: str) -> str:
    """从图片中提取文本（使用多模态 LLM）"""
    try:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        # 使用 LLMClient 的视觉接口
        llm = LLMClient(model=VISION_MODEL, temperature=0)
        result = llm.vision_complete(
            prompt="Please extract all the text content from this image. This is a student's homework. Only return the text you see, do not add any commentary.",
            image_base64=image_data,
        )
        return result
    except Exception as e:
        logger.error("Failed to extract text from image: %s", e)
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
            logger.error("Failed to read text file: %s", e)
            return ""
    except Exception as e:
        logger.error("Failed to read text file: %s", e)
        return ""


def read_image_file(image_path: str) -> str:
    """从图片文件中提取文本（使用多模态 LLM）"""
    try:
        return extract_text_from_image(image_path)
    except Exception as e:
        logger.error("Failed to read image file: %s", e)
        return ""


def read_docx_file(docx_path: str) -> str:
    """从 docx 文件中提取文本内容"""
    try:
        from docx import Document
    except ImportError:
        logger.error("python-docx not installed. Please run: pip install python-docx")
        return ""
    try:
        doc = Document(docx_path)
        text_parts = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(text_parts) if text_parts else ""
    except Exception as e:
        logger.error("Failed to read docx file: %s", e)
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
        logger.error("Failed to read PDF file: %s", e)
        return ""
