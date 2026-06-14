#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from generate_lesson_mp3 import parse_tts_script
from standardize_lessons import render_segments


B2_PRACTICE = {
    1: [
        "From my perspective, the claim is reasonable, but the evidence is not completely convincing.",
        "We should question that assumption before accepting the claim.",
        "Biased reporting can shape how people understand an issue.",
        "I think the main claim needs stronger evidence.",
        "Can you explain your perspective in more detail?",
        "Yes. I am concerned that the underlying assumption may be wrong.",
        "That sounds reasonable, but I would like more evidence.",
        "From my perspective, the claim deserves consideration. However, its assumptions may be biased. More evidence would make it convincing.",
    ],
    2: [
        "The evidence supports the argument, but it does not justify the conclusion.",
        "We should consider the counterargument before reaching a conclusion.",
        "Strong evidence can support an argument and justify its conclusion.",
        "The evidence supports the main claim.",
        "I think the argument needs more evidence.",
        "Can you explain how the evidence supports your argument?",
        "Yes. The evidence supports my argument, but I also considered the counterargument.",
        "That argument sounds plausible, but how can you justify it?",
        "The argument is clear, but it needs stronger evidence. A fair response should address the counterargument before reaching a conclusion.",
    ],
    3: [
        "I disagree with the proposal, but I acknowledge the need for compromise.",
        "We should acknowledge both sides before challenging the proposal.",
        "A respectful compromise can resolve a controversial disagreement.",
        "This controversial issue requires a compromise.",
        "I think we should challenge that argument respectfully.",
        "Can you explain why you disagree?",
        "Yes. I acknowledge the goal, but the evidence does not persuade me.",
        "That compromise sounds fair, but both sides must accept it.",
        "This issue is controversial, so disagreement is expected. We should acknowledge both sides and seek a compromise that can persuade them.",
    ],
    4: [
        "The software update added a useful feature, but it caused compatibility problems.",
        "We should check the platform's compatibility before installing the software.",
        "A software update can improve a device or create new compatibility issues.",
        "This device needs a software update.",
        "I think compatibility is the main concern.",
        "Can you explain which software feature you need?",
        "Yes. The platform works well, but this device may not be compatible.",
        "That update sounds useful, but will it work on my device?",
        "The update adds a useful feature to the platform. However, we should check the software's compatibility with older devices.",
    ],
    5: [
        "The account offers easy access, but its privacy settings need improvement.",
        "We should strengthen encryption before allowing wider access.",
        "A data breach can expose private accounts and damage trust.",
        "Protecting account privacy is the main priority.",
        "I think the account needs stronger encryption.",
        "Can you explain who has access to the account?",
        "Yes. Encryption protects the account if a password is stolen.",
        "That account sounds useful, but is my personal data secure?",
        "This account is convenient, but privacy matters more. Strong encryption and limited access can reduce the risk of a data breach.",
    ],
    6: [
        "The algorithm influences which content appears in each notification.",
        "We should moderate the content before recommending it to subscribers.",
        "Algorithms can influence users by repeatedly promoting similar content.",
        "The algorithm has the greatest influence on what users see.",
        "I think the platform should moderate harmful content.",
        "Can you explain how the algorithm selects content?",
        "Yes. It uses your activity to choose content and notifications.",
        "That recommendation sounds useful, but how did the algorithm choose it?",
        "The algorithm recommends content based on user activity. Platforms should explain this influence and moderate harmful material responsibly.",
    ],
    7: [
        "Pollution and deforestation can cause water shortages and contamination.",
        "We should reduce emissions and waste to prevent further pollution.",
        "Water contamination can turn a shortage into a public health crisis.",
        "Reducing pollution is the most urgent priority.",
        "I think factories must reduce their emissions.",
        "Can you explain how these emissions affect local communities?",
        "Yes. They increase pollution and may contaminate the water supply.",
        "That shortage sounds serious, but what caused it?",
        "Pollution, emissions, and deforestation damage ecosystems. They can also cause water shortages, contamination, and serious health problems.",
    ],
    8: [
        "Regulation and financial incentives can encourage sustainable recycling.",
        "We should invest in renewable energy and water conservation.",
        "Conservation protects resources, while recycling reduces waste.",
        "Sustainable development should be our main goal.",
        "I think stronger regulation would encourage recycling.",
        "Can you explain why renewable energy needs incentives?",
        "Yes. Incentives can make sustainable technology more affordable.",
        "That incentive sounds promising, but how much will it cost?",
        "A sustainable policy should support renewable energy, recycling, and conservation. Clear regulation and practical incentives can encourage lasting change.",
    ],
    9: [
        "Climate adaptation can protect biodiversity and strengthen community resilience.",
        "We should prepare for droughts and floods before they become disasters.",
        "Community resilience helps people adapt after a flood or drought.",
        "Climate adaptation is the most urgent priority.",
        "I think the drought threatens local biodiversity.",
        "Can you explain how the drought affected the region?",
        "Yes. It reduced the water supply and damaged local biodiversity.",
        "That adaptation plan sounds useful, but will it prevent future damage?",
        "Climate change increases the risk of droughts and floods. Adaptation can protect biodiversity and strengthen community resilience.",
    ],
    10: [
        "Her ambition and expertise make her a strong candidate for promotion.",
        "We should assess her performance and leadership before deciding on the promotion.",
        "A good mentor can develop leadership skills and share valuable expertise.",
        "Her leadership experience is her greatest strength.",
        "I think her performance deserves recognition.",
        "Can you explain why she deserves a promotion?",
        "Yes. Her performance improved, and she demonstrated strong leadership.",
        "That promotion sounds deserved, but is she ready to lead the team?",
        "Her ambition is supported by strong performance and relevant expertise. A mentor can help her develop the leadership skills she needs.",
    ],
    11: [
        "We must negotiate a trade-off between the proposal's risks and benefits.",
        "We should clarify our priorities before negotiating the proposal.",
        "Every proposal involves a trade-off between risk and benefit.",
        "Reducing risk is our main priority.",
        "I think the proposal offers a clear benefit.",
        "Can you explain the main risk in the proposal?",
        "Yes. The proposal offers benefits, but the trade-off may be too costly.",
        "That benefit sounds valuable, but what are the risks?",
        "Before we negotiate, we should identify our priorities. Then we can compare each benefit, risk, and possible trade-off.",
    ],
    12: [
        "Our strategy could increase profit and help us compete in a growing market.",
        "We should study market demand before making the investment.",
        "A strong competitor can force a company to improve its strategy.",
        "Market demand is the most important factor.",
        "I think the investment could increase profit.",
        "Can you explain why demand is increasing?",
        "Yes. Demand is growing because customers want a cheaper service.",
        "That competitor sounds strong, but our strategy may still succeed.",
        "Market demand is growing, so the investment could be profitable. However, our strategy must distinguish us from our main competitor.",
    ],
    13: [
        "Citizens elect representatives to protect their rights and influence government policy.",
        "We should review the policy before the next election.",
        "An elected representative should defend citizens' rights.",
        "Protecting citizens' rights is the main priority.",
        "I think the government should revise this policy.",
        "Can you explain how the government developed this policy?",
        "Yes. The government consulted citizens and their representatives.",
        "That representative sounds experienced, but what policies do they support?",
        "Citizens expect the government to protect their rights. During an election, each representative should clearly explain their policies.",
    ],
    14: [
        "The reform could reduce inequality and improve welfare for minority communities.",
        "We should consider justice and welfare before approving the reform.",
        "A public campaign can build support for social reform.",
        "Reducing inequality should be the main goal.",
        "I think the reform would improve access to welfare.",
        "Can you explain how the reform promotes justice?",
        "Yes. It protects minority groups and reduces inequality.",
        "That reform sounds promising, but how will it affect minority communities?",
        "The campaign calls for reform to reduce inequality. It also argues that justice requires fair welfare support for minority communities.",
    ],
    15: [
        "The research uses survey data from a representative sample.",
        "We should test the hypothesis with a larger experiment.",
        "Reliable data depends on a well-designed survey and a representative sample.",
        "The quality of the research is the main concern.",
        "I think the sample is too small.",
        "Can you explain how the experiment tested the hypothesis?",
        "Yes. The researchers collected survey data from two groups.",
        "That survey sounds useful, but is the sample representative?",
        "The research begins with a clear hypothesis. A controlled experiment, representative sample, and reliable survey data can test it.",
    ],
    16: [
        "The analysis found a significant trend, but one variable remains unclear.",
        "We should examine the evidence before treating the trend as proof.",
        "A significant result is evidence, but it is not always proof.",
        "The analysis of the evidence is the main concern.",
        "I think one variable may explain the trend.",
        "Can you explain what evidence supports this trend?",
        "Yes. The analysis found a significant change in one variable.",
        "That result sounds significant, but is it strong enough to prove the claim?",
        "The analysis identified a significant trend. However, one variable remains unclear, so the evidence does not yet provide definitive proof.",
    ],
    17: [
        "Confidence and self-esteem can help people cope with anxiety and stress.",
        "We should reduce stress before expecting confidence to improve.",
        "Strong motivation can help people cope with anxiety.",
        "Reducing anxiety is the most urgent goal.",
        "I think stress is affecting her confidence.",
        "Can you explain what improved your confidence?",
        "Yes. Regular practice reduced my anxiety and improved my self-esteem.",
        "That could improve self-esteem, but everyone responds differently.",
        "Anxiety and stress can damage confidence and self-esteem. Clear goals and steady motivation can help people cope more effectively.",
    ],
    18: [
        "A positive attitude and empathy can strengthen personal resilience.",
        "We should understand the habit before judging it as greedy.",
        "Empathy and resilience can shape a person's attitude.",
        "Her positive attitude is her greatest strength.",
        "I think that habit reflects his personality.",
        "Can you explain why you consider that decision greedy?",
        "Yes. It benefits one person while ignoring everyone else's needs.",
        "That response shows resilience, but the experience was still difficult.",
        "Attitude, habits, and personality influence how people respond to others. Empathy builds trust, while resilience helps people recover.",
    ],
    19: [
        "Successful integration requires security, cooperation, and support for refugees.",
        "We should protect the border without preventing refugee integration.",
        "Conflict and insecurity often force refugees to cross a border.",
        "Supporting refugee integration is the main priority.",
        "I think the conflict created serious security concerns.",
        "Can you explain why the refugee crossed the border?",
        "Yes. The conflict threatened the refugee's safety.",
        "That security plan sounds practical, but will it protect refugees?",
        "Conflict often drives migration and forces refugees across borders. Effective integration requires both public security and respect for human rights.",
    ],
    20: [
        "International cooperation can direct aid and resources toward sustainable development.",
        "We should coordinate aid before the crisis becomes worse.",
        "A crisis can deepen poverty and slow economic development.",
        "Reducing poverty should be the main priority.",
        "I think clean water is the most important resource.",
        "Can you explain how the aid supports development?",
        "Yes. The aid provides essential resources during the crisis.",
        "That resource is essential, but how will communities access it?",
        "Poverty often becomes worse during a crisis. International aid and cooperation can provide essential resources and support long-term development.",
    ],
}


B2_BAD_PATTERNS = [
    re.compile(r"From my perspective, the .+ is .+ but not completely .+\."),
    re.compile(r"We should discuss the .+ before we make a final decision about the .+\."),
    re.compile(r"This situation shows why .+ can change the way people understand the issue\."),
    re.compile(r"I can connect .+ with .+ because both ideas affect the final decision\."),
    re.compile(r"I think the most important point is the .+\."),
    re.compile(r"Can you explain your .+ in a little more detail\?"),
    re.compile(r"Yes\. My main reason is that the .+ affects the result\."),
    re.compile(r"That sounds .+, but I still need more information\."),
    re.compile(r"From my perspective, this topic needs careful discussion\..+", re.DOTALL),
]

B1_DIRECT_REPLACEMENTS = {
    "I avoid heavy food because I want my health to improve.": (
        "I avoid heavy meals because I want my health to improve."
    ),
    "There is a delay in my itinerary.": (
        "My itinerary has changed because of a delay."
    ),
    "The apartment needs a repair.": (
        "The apartment needs some repairs."
    ),
    "For the main course and dessert, we left a small tip.": (
        "After the main course and dessert, we left a small tip."
    ),
    "This certification is useful for my favorite subject.": (
        "This certification will help me teach my favorite subject."
    ),
}


def target_words(segments: list[dict[str, Any]]) -> set[str]:
    for segment in segments:
        if segment["type"] != "speech" or segment.get("language_code") != "en":
            continue
        text = segment["text"].strip()
        if text.count(",") == 5:
            return {
                word.strip().rstrip(".").casefold()
                for word in text.split(",")
            }
    raise ValueError("Could not find target-word list")


def remove_forced_b1_combinations(segments: list[dict[str, Any]]) -> None:
    targets = target_words(segments)
    for segment in segments:
        if segment["type"] != "speech" or segment.get("language_code") != "en":
            continue
        if segment["text"].strip() in B1_DIRECT_REPLACEMENTS:
            segment["text"] = B1_DIRECT_REPLACEMENTS[segment["text"].strip()]
        sentences = re.split(r"(?<=[.!?])\s+", segment["text"].strip())
        if len(sentences) != 2:
            continue
        first_words = set(re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)?", sentences[0].casefold()))
        second_words = set(re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)?", sentences[1].casefold()))
        if not targets.intersection(first_words) and targets.intersection(second_words):
            segment["text"] = sentences[1]


def replace_b2_practice(segments: list[dict[str, Any]], lesson: int) -> None:
    replacements = iter(B2_PRACTICE[lesson])
    replaced = 0
    for segment in segments:
        if segment["type"] != "speech" or segment.get("language_code") != "en":
            continue
        text = segment["text"].strip()
        if any(pattern.fullmatch(text) for pattern in B2_BAD_PATTERNS):
            segment["text"] = next(replacements)
            replaced += 1
    expected = 8 if lesson == 1 else len(B2_BAD_PATTERNS)
    if replaced == 0:
        return
    if replaced != expected:
        raise ValueError(f"B2 lesson {lesson}: expected {expected} replacements, made {replaced}")


def process() -> None:
    changed: list[Path] = []
    for path in sorted(Path("B1_English_TTS_Lesson_Scripts").glob("B1_Lesson_*.txt")):
        original = path.read_text(encoding="utf-8")
        segments = parse_tts_script(original)
        remove_forced_b1_combinations(segments)
        updated = render_segments(segments)
        if updated != original.replace("\r\n", "\n"):
            path.write_text(updated, encoding="utf-8", newline="\n")
            changed.append(path)

    for path in sorted(Path("B2_English_TTS_Lesson_Scripts").glob("B2_Lesson_*.txt")):
        original = path.read_text(encoding="utf-8")
        segments = parse_tts_script(original)
        lesson = int(re.search(r"B2_Lesson_(\d+)_", path.name).group(1))
        replace_b2_practice(segments, lesson)
        updated = render_segments(segments)
        if updated != original.replace("\r\n", "\n"):
            path.write_text(updated, encoding="utf-8", newline="\n")
            changed.append(path)

    print(f"Naturalized lesson files: {len(changed)}")
    for path in changed:
        print(path)


if __name__ == "__main__":
    process()
