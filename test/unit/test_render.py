#!/usr/bin/env python3
"""测试 homework.html 模板渲染"""
import sys
sys.path.insert(0, '../src')

from ai_tutor import display_homeworks

# 测试数据
test_sections = [
    {
        'subject': 'Spanish',
        'homework': '''# Spanish Homework: Los Colores

**Hello Ana!** Today we are going to learn some beautiful Spanish words about colors.

**Time needed:** 10-15 minutes

---

### Your Tasks

**1. Watch and Listen (5 minutes)**
Go to **BBC Bitesize** and find a short video about Spanish colors.

**2. Draw a Colourful Picture (5-7 minutes)**
Draw a simple picture and color it using these 4 Spanish words:
- **Rojo** (Red)
- **Azul** (Blue)
- **Amarillo** (Yellow)
- **Verde** (Green)

**3. Speak Like a Pro (2 minutes)**
Stand up and point to things around your house!
'''
    },
    {
        'subject': 'Chinese',
        'homework': '''# Chinese Adventure: Greetings & Numbers

**Year Group:** 2 (KS1)  
**Time Needed:** 10-15 Minutes

Hello Ana! Today we are going to explore the Chinese language.

### Task 1: Match the Meaning (5 Minutes)

| Chinese Character | Pinyin (How to say it) | English Meaning |
| :---: | :---: | :---: |
| **你好** | *Nǐ hǎo* | **Hello** |
| **一** | *Yī* | **One** |
| **二** | *Èr* | **Two** |
| **三** | *Sān* | **Three** |
| **再见** | *Zài jiàn* | **Goodbye** |

### Task 2: Speak and Count (5 Minutes)

Stand up and use your fingers to count in Chinese!
1. Hold up **one** finger and say *"Yī"*.
2. Hold up **two** fingers and say *"Èr"*.
3. Hold up **three** fingers and say *"Sān"*.
'''
    }
]

result = display_homeworks(test_sections)
print("HTML 生成成功！")
print(f"输出文件: data/output.html")

# 检查是否包含 markdown 内容
if 'Spanish Homework' in result and 'Chinese Adventure' in result:
    print("内容检查: 通过")
else:
    print("内容检查: 失败 - 内容可能未正确嵌入")
