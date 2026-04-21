#!/usr/bin/env python3
"""
Analyze translation quality and suggest improvements.
"""

import anthropic
import json

client = anthropic.Anthropic()

# The translations to analyze
chinese_original = "NADCC氯片 200ppm 150ppm 100ppm浓度狗骨头浸泡测试已完成 实验室今天提供给@杨中宝"

translations = {
    "current_app": "NADCC chlorine tablets 200 ppm 150 ppm 100 ppm dog bone immersion test completed.",
    "option_2": "The dog-bone soaking tests using NADCC chlorine tablets at concentrations of 200 ppm, 150 ppm, and 100ppm have been completed. The laboratory will provide them today.@杨中宝",
    "option_3": 'The "dog-bone" immersion tests for the NADCC chlorine tablets—at concentrations of 200 ppm, 150 ppm, and 100 ppm—have been completed. The laboratory provided the results to @YangZhongbao today.'
}

prompt = f"""Analyze these Chinese-to-English translations and evaluate their quality.

ORIGINAL CHINESE:
{chinese_original}

TRANSLATIONS TO EVALUATE:
1. Current App: {translations['current_app']}
2. Option 2: {translations['option_2']}
3. Option 3: {translations['option_3']}

Please provide a detailed analysis:

1. **Completeness Analysis**: Which translation captures the most information from the original?
2. **Clarity Comparison**: How well does each translation express the scientific/technical content?
3. **Why Option 3 is Better**: Specifically analyze what makes Option 3 superior to the current app output
4. **Key Differences**: What are the critical differences that improve readability and accuracy?
5. **Improvement Strategy**: What specific changes would we need to make to the current app's output to approach Option 3's quality?
6. **Translation Principles**: What translation techniques does Option 3 use that the app output doesn't?

For each point, be specific about:
- How the Chinese structure (compound nouns, grammatical relationships) maps to English
- Why certain phrasing choices are better
- How punctuation and organization affect clarity
- What context is implicit in Chinese but needs to be explicit in English

Focus on actionable insights we can use to improve our translation pipeline."""

response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=2000,
    thinking={
        "type": "adaptive"
    },
    output_config={
        "effort": "high"
    },
    messages=[
        {
            "role": "user",
            "content": prompt
        }
    ]
)

# Print the analysis
print("=" * 80)
print("TRANSLATION QUALITY ANALYSIS")
print("=" * 80)
print()

for block in response.content:
    if block.type == "text":
        print(block.text)
    elif block.type == "thinking":
        print("\n[Model Reasoning]")
        print(block.thinking)
        print()

print("\n" + "=" * 80)
print("USAGE SUMMARY")
print("=" * 80)
print(f"Input tokens: {response.usage.input_tokens}")
print(f"Output tokens: {response.usage.output_tokens}")
if hasattr(response.usage, 'cache_read_input_tokens'):
    print(f"Cache read tokens: {response.usage.cache_read_input_tokens}")
if hasattr(response.usage, 'cache_creation_input_tokens'):
    print(f"Cache creation tokens: {response.usage.cache_creation_input_tokens}")
