# Lesson Production Standard

This is the sole authoritative specification for lesson generation, TTS formatting, pedagogy, caching, and validation in this repository.

The detailed six-section structure applies to Mandarin-to-English B1 and B2 lessons. German A1 lessons use English teacher prompts and German learner answers while following the same block-format, language-tag, pause, caching, and quality principles where applicable.

## Objective

Create original, production-ready audio lesson scripts for Mandarin-speaking adults learning English. Lessons should support active recall, spoken repetition, and natural real-life communication.

Do not copy proprietary language-course scripts.

## Course Inputs

Each curriculum row provides:

```text
Level | Lesson | Topic | Word 1 | Word 2 | Word 3 | Word 4 | Word 5 | Word 6
```

Each lesson must preserve its supplied level, topic, six target expressions, order, and curriculum progression.

Teacher language: Mandarin Chinese.

Target language: neutral international English.

Use English appropriate for the specified CEFR level.

## Lesson Structure

Every lesson must use these six spoken Mandarin section transitions as separate blocks:

1. `第一部分，课程介绍。`
2. `第二部分，复习。`
3. `第三部分，新词介绍。`
4. `第四部分，新词练习。`
5. `第五部分，情境句子练习。`
6. `第六部分，课程总结。`

### 1. Course Introduction

- Welcome the learner.
- State the lesson number, CEFR level, and topic.
- Explain that the learner should answer in English and repeat model answers aloud.
- Introduce the six target expressions separately, with a `1.0s` break between them. This is only a quick preview, not active practice.

```xml
<break time="1.0s" />

<lang code="en" />
claim.
```

### 2. Review

- From lesson 2 onward, review recent expressions and sentences.
- Occasionally revisit older material.
- Keep prompts short and answers natural.
- Do not combine unrelated vocabulary merely for repetition.
- Make sure the sentences are realistic sentences used in every-day life that convey the meaning of the words practiced.

### 3. New Expression Introduction

For each target expression:

- Introduce the expression and its Mandarin meaning.
- Ask the learner to repeat it.
- Prompt the Mandarin meaning and ask for the English expression.
- Present one natural example sentence.
- Ask the learner to repeat the example sentence.
- In this section, you should always introduce verbs and adjectives with their collocations (see section "Pedagogical Rules")

Generic example sentences are acceptable here. They must still be natural and useful.

### 4. New Expression Practice

- Recall all six expressions in a mixed order.
- Revisit several complete example sentences.
- Prefer active recall and spoken production.

### 5. Scenario Sentence Practice

- Choose one believable real-life scenario for the entire section.
- Make the scenario feel personal when possible. Use named characters, familiar topics, or recognizable locations.
- Introduce the scenario setting clearly in Mandarin before the first scenario sentence.
- Build a coherent sequence of four to six natural sentences.
- Keep people, setting, and events consistent from sentence to sentence.
- Use target expressions only where they naturally belong.
- Outside vocabulary is encouraged when appropriate for the CEFR level.
- Never force more than two target expressions into one sentence.
- Prioritize naturalness and scenario coherence over vocabulary coverage.
- First, let the learner hear and repeat each English sentence.
- Then reproduce the scenario sentence by sentence: give each sentence in Mandarin, allow time for translation, and provide the correct English answer.

### 6. Course Conclusion

- Review the six target expressions.
- End with a short, reusable Mandarin closing.

## Pedagogical Rules

- When asking the learner to translate an expression into English, always play the correct English expression twice after the response pause.
- Whenever introducing or practicing a single verb or adjective, use an abstract pattern with its normal collocation or complementation. Examples:

    make --> to make something
    look after  --> to look after something or someone
    build   --> to build something

- When introducing adjectives, always introduce the abstract adjective pattern and its normal complementation.

    afraid  --> to be afraid of somthing or someone
    interested  --> to be interested in someting or someone

- When introducing or practicing a single noun, use it with `the`. This helps the learner recognize that it is a noun. Use natural articles normally inside complete sentences.

    conclusion --> the conclusion

## Reusable Blocks And Caching

The TTS pipeline uses exact-text caching. Identical spoken text only reuses cached audio when text, punctuation, capitalization, language code, voice, model, and settings are identical.

Therefore:

- Keep recurring instructions exactly identical across lessons.
- Put recurring instructions in their own spoken blocks.
- Do not join reusable instructions to lesson-specific text.
- Cache and reuse only complete spoken blocks. Never split sentences into words or fragments for audio reuse, and never stitch cached word fragments into sentences.
- Use consistent punctuation and language tags.
- Reuse prompts such as:
  - `请听例句。`
  - `请重复这个英语句子。`
  - `请回忆并说出这个英语句子。`
  - `现在打乱顺序，练习今天的新表达。`
- Do not make scenario sentences generic merely to increase cache hits.

## English Quality

- Every English sentence must sound natural in a real spoken situation.
- No English sentence may exceed 20 words.
- Use each target expression with the correct meaning and part of speech.
- Use articles and verb forms naturally.
- Avoid translated-sounding generic templates.
- Avoid sentences that merely discuss how to use a vocabulary word.
- Avoid slang, childish examples, and unnecessarily complex idioms.
- Naturalness takes priority over repetition.

## TTS File Format

Lesson files must contain only:

- spoken Mandarin teacher blocks;
- spoken English model-answer blocks;
- language tags;
- break tags.

Use a language tag before every spoken block:

```xml
<lang code="zh" />
请重复这个英语句子。

<break time="5.5s" />

<lang code="en" />
The meeting starts at ten.
```

Allowed tags:

```xml
<lang code="zh" />
<lang code="en" />
<lang code="auto" />
<break time="3.5s" />
```

Use `auto` only for deliberately mixed-language blocks. Keep pure Mandarin and English blocks separate whenever possible.

Do not include speaker labels, Markdown headings, bullet points, production notes, filenames, or unsupported SSML inside lesson files.

## Pause Rules

Response pauses before an expected English answer:

- One word: `3.5s`
- Two to five words: `4.5s`
- Six to ten words: `5.5s`
- Eleven to sixteen words: `6.5s`
- Seventeen to twenty words: `7.5s`

Reflection pauses after English model answers:

- One word: `2.0s`
- Two to eight words: `2.5s`
- Nine to sixteen words: `3.0s`
- Seventeen to twenty words: `4.0s`

No individual break may exceed `10.0s`.

## Canonical Lesson Template

Use this as the structural reference for every B1 and B2 lesson. Text inside `{braces}` is a placeholder and must be replaced. Do not leave placeholders in production lesson files.

### Section 1: Course Introduction

Introduce the six expressions as six separate English blocks. Use the appropriate isolated teaching form:

- noun: `the conclusion`
- verb: `to justify something`
- adjective: `to be interested in something`

```xml
<lang code="zh" />
第一部分，课程介绍。

<lang code="zh" />
欢迎回来。今天是第{lesson number}课，级别是{level}。

<lang code="zh" />
今天的主题是{topic in Mandarin}。

<lang code="zh" />
你会听到中文提示，并用英语回答。听到英语示范后，请大声重复。

<lang code="zh" />
今天的六个新英语表达是。

<lang code="en" />
{isolated expression 1}.

<break time="1.0s" />

<lang code="en" />
{isolated expression 2}.

<break time="1.0s" />

<lang code="en" />
{isolated expression 3}.

<break time="1.0s" />

<lang code="en" />
{isolated expression 4}.

<break time="1.0s" />

<lang code="en" />
{isolated expression 5}.

<break time="1.0s" />

<lang code="en" />
{isolated expression 6}.
```

### Section 2: Review

When asking for an isolated expression, play the correct answer twice. Keep both answers as identical complete English blocks.

```xml
<lang code="zh" />
第二部分，复习。

<lang code="zh" />
先复习上一课的几个表达。听中文，说英语。

<lang code="zh" />
请说英语：{Mandarin meaning}.

<break time="{response pause}s" />

<lang code="en" />
{isolated expression}.

<break time="{reflection pause}s" />

<lang code="en" />
{isolated expression}.

<break time="{reflection pause}s" />

<lang code="zh" />
现在复习上一课的两个句子。

<lang code="zh" />
请回忆并说出上一课的这个句子。

<break time="{response pause}s" />

<lang code="en" />
{natural previous-lesson sentence}.

<break time="{reflection pause}s" />
```

For lesson 1, replace the review content with:

```xml
<lang code="zh" />
第二部分，复习。

<lang code="zh" />
这是第一课。我们直接开始学习新内容。
```

### Section 3: New Expression Introduction

Repeat this structure for all six target expressions.

```xml
<lang code="zh" />
第三部分，新词介绍。

<lang code="zh" />
今天的第1个表达是。

<lang code="en" />
{isolated expression}.

<lang code="zh" />
意思是：{Mandarin meaning}。请跟读。

<lang code="en" />
{isolated expression}.

<break time="{reflection pause}s" />

<lang code="zh" />
请说英语：{Mandarin meaning}。

<break time="{response pause}s" />

<lang code="en" />
{isolated expression}.

<break time="{reflection pause}s" />

<lang code="en" />
{isolated expression}.

<break time="{reflection pause}s" />

<lang code="zh" />
请听例句。

<lang code="en" />
{natural example sentence}.

<break time="{reflection pause}s" />

<lang code="zh" />
请重复这个英语句子。

<break time="{response pause}s" />

<lang code="en" />
{natural example sentence}.

<break time="{reflection pause}s" />
```

### Section 4: New Expression Practice

Recall all six isolated expressions in mixed order, with every answer played twice. Then recall three natural example sentences.

```xml
<lang code="zh" />
第四部分，新词练习。

<lang code="zh" />
现在打乱顺序，练习今天的新表达。

<lang code="zh" />
请说英语：{Mandarin meaning}.

<break time="{response pause}s" />

<lang code="en" />
{isolated expression}.

<break time="{reflection pause}s" />

<lang code="en" />
{isolated expression}.

<break time="{reflection pause}s" />

<lang code="zh" />
现在练习三个完整句子。

<lang code="zh" />
请回忆并说出这个英语句子。

<break time="{response pause}s" />

<lang code="en" />
{natural example sentence}.

<break time="{reflection pause}s" />
```

### Section 5: Scenario Sentence Practice

Use one clear, personal scenario. Introduce its setting in Mandarin.

The first round is listen-and-repeat:

- The initial Mandarin instruction introduces the first sentence.
- Before each later new sentence, use `请重复这个英语句子。`
- Play the new English sentence.
- Leave a response pause for the learner to repeat it.
- Replay the same complete English sentence without another Mandarin prompt.

```xml
<lang code="zh" />
第五部分，情境句子练习。

<lang code="zh" />
情境：{clear personal scenario setting in Mandarin}。

<lang code="zh" />
先听每个英语句子，然后在停顿时大声重复。

<lang code="en" />
{scenario sentence 1}.

<break time="{response pause}s" />

<lang code="en" />
{scenario sentence 1}.

<break time="{reflection pause}s" />

<lang code="zh" />
请重复这个英语句子。

<lang code="en" />
{scenario sentence 2}.

<break time="{response pause}s" />

<lang code="en" />
{scenario sentence 2}.

<break time="{reflection pause}s" />
```

Continue the same pattern for all four to six scenario sentences.

The second round is Mandarin-to-English translation. Do not play the answer twice in this round.

```xml
<lang code="zh" />
现在根据中文提示，把这个情境中的句子翻译成英语。

<lang code="zh" />
{natural Mandarin meaning of scenario sentence 1}.

<break time="{response pause}s" />

<lang code="en" />
{scenario sentence 1}.

<break time="{reflection pause}s" />

<lang code="zh" />
{natural Mandarin meaning of scenario sentence 2}.

<break time="{response pause}s" />

<lang code="en" />
{scenario sentence 2}.

<break time="{reflection pause}s" />
```

### Section 6: Course Conclusion

Review all six isolated expressions. Each correct expression is played twice.

```xml
<lang code="zh" />
第六部分，课程总结。

<lang code="zh" />
最后，再复习今天的六个新表达。

<lang code="zh" />
请说英语：{Mandarin meaning}.

<break time="{response pause}s" />

<lang code="en" />
{isolated expression}.

<break time="{reflection pause}s" />

<lang code="en" />
{isolated expression}.

<break time="{reflection pause}s" />

<lang code="zh" />
很好。今天的练习到这里结束。请继续保持每天开口练习的习惯。
```

## Validation Requirements

Before delivery:

- verify all six sections appear exactly once and in order;
- verify all six target expressions remain present;
- verify Mandarin blocks use `zh` and English blocks use `en`;
- verify every English sentence is 20 words or fewer;
- verify no unsupported tags or metadata leak into speech;
- verify recurring prompts are exact reusable blocks;
- verify the final scenario is coherent and natural;
- verify the first scenario round uses English sentence, response pause, identical English sentence, reflection pause;
- verify `请重复这个英语句子。` appears before each new scenario sentence after the first;
- verify the second scenario round uses Mandarin prompt, response pause, one English answer, reflection pause;
- run strict lesson validation and a TTS dry run.

## Repository Commands

Rebuild the English B1 and B2 lessons:

```powershell
python curriculum\tools\rebuild_english_lessons.py
```

Apply shared formatting and pause standardization:

```powershell
python curriculum\tools\standardize_lessons.py
```

Validate every production lesson:

```powershell
python curriculum\tools\validate_lessons.py curriculum\courses\A1_German_TTS_Lesson_Scripts curriculum\courses\B1_English_TTS_Lesson_Scripts curriculum\courses\B2_English_TTS_Lesson_Scripts --strict
```

Refresh stored validation summaries:

```powershell
python curriculum\tools\refresh_validation_summaries.py
```
