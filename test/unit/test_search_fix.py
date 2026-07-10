#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试 HomeworkRAGStore.search() 方法的修复
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from src.homework_rag import get_homework_rag_store

def test_search_fix():
    """测试修复后的 search() 方法"""
    print("测试 HomeworkRAGStore.search() 方法修复...")
    
    try:
        # 获取 RAG store
        store = get_homework_rag_store()
        print("✓ 成功获取 HomeworkRAGStore 实例")
        
        # 测试搜索（即使集合为空也应该能工作）
        results = store.search(query="test", k=1)
        print(f"✓ 搜索成功完成，返回 {len(results)} 个结果")
        
        # 测试带过滤条件的搜索
        results = store.search(
            query="math", 
            k=1, 
            filters={"subject": "Maths", "year_group": 3}
        )
        print(f"✓ 带过滤条件的搜索成功完成，返回 {len(results)} 个结果")
        
        print("\n✅ 所有测试通过！search() 方法修复成功")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_search_fix()
    sys.exit(0 if success else 1)