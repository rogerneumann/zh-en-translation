#!/usr/bin/env python3
"""
Generate and evaluate alternative translations to improve quality.
Uses Claude to produce multiple translation options and rank them.
"""

import anthropic

client = anthropic.Anthropic()

# Chinese text to analyze
chinese_original = "NADCC氯片 200ppm 150ppm 100ppm浓度狗骨头浸泡测试已完成 实验室今天提供给@杨中宝"

# Current app translation (for comparison)
current_app_translation = "NADCC chlorine tablets 200 ppm 150 ppm 100 ppm dog bone immersion test completed."

prompt = f"""You are an expert translator specializing in scientific/technical Chinese-English translation.

ORIGINAL CHINESE TEXT:
{chinese_original}

CURRENT APP TRANSLATION (for reference):
{current_app_translation}

ANALYSIS TASK:
1. **Identify missing information**: What key details from the Chinese are missing in the current translation?
2. **Parse the Chinese structure**: Break down the Chinese phrase grammatically to show what each component means
3. **Generate 5 alternative translations**: Create 5 different English versions that capture the meaning accurately
   - Each should use different approaches (formal/informal, different sentence structures, etc.)
   - Number them 1-5 with different translation strategies
4. **Evaluate each alternative**:
   - Completeness (does it capture all information?)
   - Clarity (is it clear in English?)
   - Technical accuracy (are terms appropriate?)
   - Readability (does it flow naturally?)
5. **Recommend the best**: Which translation best captures the original without losing details?
6. **Explain why**: What makes your recommended translation superior?

Focus on:
- The "实验室今天提供给@杨中宝" clause (often missing in literal translations)
- Proper way to express concentrations (200/150/100 ppm)
- How to handle technical term "狗骨头" (dog-bone)
- Translating the recipient name @杨中宝
- Maintaining scientific accuracy

Be specific about what information the current app is losing and why it matters."""

response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=3000,
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

# Print results
print("=" * 80)
print("TRANSLATION ALTERNATIVES & ANALYSIS")
print("=" * 80)
print()

for block in response.content:
    if block.type == "text":
        print(block.text)
    elif block.type == "thinking":
        print("\n[Claude's Detailed Reasoning]")
        print("-" * 40)
        print(block.thinking)
        print("-" * 40)
        print()

print("\n" + "=" * 80)
print("TOKEN USAGE")
print("=" * 80)
print(f"Input tokens: {response.usage.input_tokens}")
print(f"Output tokens: {response.usage.output_tokens}")
