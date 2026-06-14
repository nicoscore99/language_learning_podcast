#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from generate_segmented_lesson_mp3_langtags import parse_tts_script
from standardize_lessons import reflection_pause, render_segments, response_pause


COURSE_FOLDERS = {
    "B1": Path("B1_English_TTS_Lesson_Scripts"),
    "B2": Path("B2_English_TTS_Lesson_Scripts"),
}

SECTION_TITLES = [
    "第一部分，课程介绍。",
    "第二部分，复习。",
    "第三部分，新词介绍。",
    "第四部分，新词练习。",
    "第五部分，情境句子练习。",
    "第六部分，课程总结。",
]

EXPRESSION_PATTERNS = {
    "hurt": "to hurt",
    "dizzy": "to feel dizzy",
    "swollen": "to be swollen",
    "recover": "to recover from something",
    "rest": "to rest",
    "avoid": "to avoid something",
    "improve": "to improve something",
    "hire": "to hire someone",
    "repair": "to repair something",
    "transfer": "to transfer something",
    "confirm": "to confirm something",
    "explain": "to explain something",
    "cancel": "to cancel something",
    "miss": "to miss something",
    "afford": "to afford something",
    "boil": "to boil something",
    "fry": "to fry something",
    "slice": "to slice something",
    "memorize": "to memorize something",
    "review": "to review something",
    "invite": "to invite someone",
    "accept": "to accept something",
    "refuse": "to refuse something",
    "arrange": "to arrange something",
    "suggest": "to suggest something",
    "worried": "to be worried about something",
    "excited": "to be excited about something",
    "annoyed": "to be annoyed about something",
    "surprised": "to be surprised by something",
    "embarrassed": "to be embarrassed about something",
    "proud": "to be proud of something",
    "argue": "to argue about something",
    "apologize": "to apologize for something",
    "forgive": "to forgive someone",
    "trust": "to trust someone",
    "support": "to support someone or something",
    "promise": "to promise something",
    "convincing": "to be convincing",
    "reasonable": "to be reasonable",
    "biased": "to be biased against someone or something",
    "justify": "to justify something",
    "conclude": "to conclude that something is true",
    "challenge": "to challenge something",
    "disagree": "to disagree with someone",
    "acknowledge": "to acknowledge something",
    "persuade": "to persuade someone",
    "controversial": "to be controversial",
    "subscribe": "to subscribe to something",
    "influence": "to influence someone or something",
    "moderate": "to moderate something",
    "recycle": "to recycle something",
    "renewable": "to be renewable",
    "sustainable": "to be sustainable",
    "negotiate": "to negotiate with someone",
    "significant": "to be significant",
    "cope": "to cope with something",
    "greedy": "to be greedy",
}

LEGACY_EXPRESSION_PATTERNS = {
    "to claim that something is true": "claim",
    "to compromise with someone": "compromise",
}

SCENARIOS: dict[tuple[str, int], tuple[str, list[str]]] = {
    ("B1", 1): ("情境：你在家里感觉不舒服，正在向朋友说明情况。", [
        "My back hurts, and I feel dizzy when I stand up.",
        "I also have a cough and a small rash on my arm.",
        "My ankle is swollen because of an old injury.",
        "I think I should rest and call a doctor.",
    ]),
    ("B1", 2): ("情境：你去诊所看医生。", [
        "I have an appointment at the clinic this afternoon.",
        "The doctor will give me a check-up and discuss my treatment.",
        "I may need a prescription for the medicine.",
        "If I do not improve, I will see a specialist.",
    ]),
    ("B1", 3): ("情境：医生给你一些康复建议。", [
        "The doctor said I need more rest to recover.",
        "A healthy diet and light exercise should help.",
        "I should avoid heavy exercise for a few days.",
        "I already feel better, so the advice seems to be working.",
    ]),
    ("B1", 4): ("情境：你和同事正在计划一个工作项目。", [
        "My colleague and I have a meeting about the new project.",
        "We checked the schedule and agreed on a deadline.",
        "I will write the report, and she will review it.",
        "We plan to finish everything by Friday.",
    ]),
    ("B1", 5): ("情境：你正在申请一份新工作。", [
        "I sent my application for a sales position yesterday.",
        "During the interview, I will describe my experience in sales.",
        "The company wants to hire someone next month.",
        "I hope my qualifications make me right for the position.",
    ]),
    ("B1", 6): ("情境：你和经理正在解决工作中的问题。", [
        "My manager sent a request about a problem with the report.",
        "I asked her to explain the issue and confirm the deadline.",
        "She gave me useful feedback on my first solution.",
        "We agreed on a better solution together.",
    ]),
    ("B1", 7): ("情境：你正在准备一次国外旅行。", [
        "Our destination is a quiet town near the sea.",
        "I made a reservation and checked the accommodation.",
        "My passport and itinerary are in my carry-on bag.",
        "I hope my other luggage is not too heavy.",
    ]),
    ("B1", 8): ("情境：你的火车旅行出现了问题。", [
        "Our train has a delay, so we may arrive late.",
        "I am checking the platform for my connection.",
        "The company may cancel the service because of the weather.",
        "If that happens, I will ask for a refund.",
    ]),
    ("B1", 9): ("情境：你正在考虑租一套公寓。", [
        "The landlord showed me a bright apartment near the station.",
        "The rent is fair, but the deposit is quite high.",
        "I asked the previous tenant about the neighborhood.",
        "I will read the contract carefully before signing it.",
    ]),
    ("B1", 10): ("情境：你给房东打电话报告家里的问题。", [
        "There is a leak under the sink, and the heating is not working.",
        "The electricity is fine, but there is too much noise at night.",
        "The landlord promised to arrange a repair tomorrow.",
        "I like the neighborhood, so I hope the problems are fixed soon.",
    ]),
    ("B1", 11): ("情境：你正在制定每月预算。", [
        "My income is stable, but my expenses increased this month.",
        "I made a budget so I can protect my savings.",
        "I cannot afford a new laptop at the moment.",
        "I will wait until the shop offers a discount.",
    ]),
    ("B1", 12): ("情境：你正在检查一笔银行付款。", [
        "I made a transfer from my account this morning.",
        "The bank charged a small fee for the payment.",
        "I kept the receipt and checked my balance.",
        "Everything looks correct now.",
    ]),
    ("B1", 13): ("情境：你和朋友在餐厅吃晚饭。", [
        "The waiter brought the menu and explained today's specials.",
        "I ordered soup as a starter and fish as my main course.",
        "My friend chose a dessert after the meal.",
        "The service was excellent, so we left a tip.",
    ]),
    ("B1", 14): ("情境：你正在和朋友一起做晚饭。", [
        "We found a simple recipe and bought fresh ingredients.",
        "I sliced the vegetables while my friend boiled the rice.",
        "Then we fried a small portion of vegetables.",
        "The meal was easy to prepare and tasted great.",
    ]),
    ("B1", 15): ("情境：你正在谈论一门职业课程。", [
        "I am taking a course in digital marketing.",
        "The subject is useful, but each assignment takes several hours.",
        "I received a good grade on my last exam.",
        "The final certification may help me find a better job.",
    ]),
    ("B1", 16): ("情境：你和同学讨论学习方法。", [
        "My goal is to speak English more confidently.",
        "I practice every day and review new words each evening.",
        "I try to memorize useful phrases instead of single words.",
        "When I make a mistake, I learn from it and continue.",
    ]),
    ("B1", 17): ("情境：你在课堂上参加讨论。", [
        "I asked a question about today's topic.",
        "The teacher gave a clear answer and a helpful example.",
        "Then she asked me to explain my opinion.",
        "The discussion helped everyone understand the topic better.",
    ]),
    ("B1", 18): ("情境：你正在计划和朋友一起吃晚饭。", [
        "I invited several friends to dinner on Saturday.",
        "Two friends accepted, but one had to refuse.",
        "We arranged a time and chose a quiet restaurant.",
        "I will suggest another date if someone needs to cancel.",
    ]),
    ("B1", 19): ("情境：你在工作会议后谈论自己的感受。", [
        "I was worried before the meeting, but now I feel proud.",
        "My manager surprised me with very positive feedback.",
        "I felt embarrassed about one small mistake.",
        "I am excited to work on the next project.",
    ]),
    ("B1", 20): ("情境：两位朋友正在解决一次争吵。", [
        "Maya and Leo argued because Leo broke a promise.",
        "Leo apologized and asked Maya to forgive him.",
        "Maya said that trust takes time to rebuild.",
        "They promised to listen and support each other.",
    ]),
    ("B2", 1): ("情境：两位同事正在讨论一篇有争议的新闻报道。", [
        "Nina claims that the report presents a reasonable argument.",
        "Omar thinks the writer's perspective is biased.",
        "They examine the assumptions behind the report.",
        "In the end, neither finds the evidence completely convincing.",
    ]),
    ("B2", 2): ("情境：两位朋友正在讨论哪支足球队最强。", [
        "Peter argues that Spain has the best football team.",
        "Emily asks him to provide evidence for his argument.",
        "Peter uses recent results to justify his opinion.",
        "Emily offers a counterargument about Spain's recent losses.",
        "They conclude that both teams have strong qualities.",
    ]),
    ("B2", 3): ("情境：两个邻居正在讨论一项有争议的社区计划。", [
        "Lena disagrees with the controversial plan to remove the park.",
        "Mark challenges her argument but acknowledges her concerns.",
        "Lena uses local survey results to persuade him.",
        "They finally reach a compromise that protects half the park.",
    ]),
    ("B2", 4): ("情境：同事们正在选择新的办公软件。", [
        "The team is testing new software on several devices.",
        "Its best feature is a shared project platform.",
        "The latest update fixed several serious problems.",
        "They will check compatibility before buying the software.",
    ]),
    ("B2", 5): ("情境：一家公司正在处理网络安全问题。", [
        "A data breach exposed several customer accounts.",
        "The company immediately removed public access to the system.",
        "It introduced stronger passwords and improved encryption.",
        "The director promised to make customer privacy a priority.",
    ]),
    ("B2", 6): ("情境：朋友们正在讨论社交媒体推荐。", [
        "Mia receives a notification whenever the platform recommends new content.",
        "The algorithm uses her viewing history to choose those recommendations.",
        "She worries that repeated content may influence her opinions.",
        "She still subscribes, but wants the platform to moderate harmful posts.",
    ]),
    ("B2", 7): ("情境：居民正在讨论当地河流的问题。", [
        "Factory emissions have increased pollution near the river.",
        "Residents found signs of water contamination last week.",
        "Deforestation has also caused water shortages during summer.",
        "The council wants factories to reduce emissions and waste.",
    ]),
    ("B2", 8): ("情境：市议会正在设计一项环保计划。", [
        "The council wants every household to recycle more waste.",
        "New regulation will support renewable energy projects.",
        "Businesses will receive an incentive to use sustainable materials.",
        "The plan also includes water and forest conservation.",
    ]),
    ("B2", 9): ("情境：一个沿海小镇正在准备应对气候变化。", [
        "The town recently experienced a drought followed by a flood.",
        "The town's climate adaptation plan protects homes near the coast.",
        "It also protects biodiversity in the surrounding wetlands.",
        "Local leaders hope the plan will strengthen community resilience.",
    ]),
    ("B2", 10): ("情境：一位员工正在和导师讨论晋升。", [
        "Sara tells her mentor that she hopes to earn a promotion.",
        "Her recent performance shows strong leadership.",
        "Her mentor praises her expertise in project management.",
        "He advises her to gain more experience leading larger teams.",
    ]),
    ("B2", 11): ("情境：两家公司正在商谈一项商业提案。", [
        "The companies meet to negotiate a new proposal.",
        "Price is one priority, but product quality is equally important.",
        "Both sides discuss the risks and benefits.",
        "They accept a trade-off between a lower price and slower delivery.",
    ]),
    ("B2", 12): ("情境：一家小公司正在计划进入新市场。", [
        "The company sees growing demand in a new market.",
        "Its main competitor already offers a similar product.",
        "The team develops a strategy based on quality and service.",
        "They believe the investment will produce a profit within two years.",
    ]),
    ("B2", 13): ("情境：居民正在参加地方选举会议。", [
        "Each candidate explains their policy to local citizens.",
        "One representative focuses on housing and public transport.",
        "Another promises to protect workers' rights.",
        "The election gives citizens a chance to influence public decisions.",
    ]),
    ("B2", 14): ("情境：一个社区组织正在开展社会改革活动。", [
        "The campaign calls for changes to the welfare system.",
        "Organizers say reform could reduce inequality.",
        "They want better support for every minority community.",
        "Their goal is a fairer system based on justice.",
    ]),
    ("B2", 15): ("情境：研究人员正在计划一项语言学习研究。", [
        "The research team develops a clear hypothesis about daily practice.",
        "They design an experiment with a large sample of learners.",
        "Each participant completes a weekly survey.",
        "The researchers will compare the data after three months.",
    ]),
    ("B2", 16): ("情境：同事们正在讨论一份研究报告。", [
        "The analysis shows a significant increase in customer satisfaction.",
        "However, one variable may have influenced the trend.",
        "The team needs more evidence before changing its strategy.",
        "The current results are promising, but they are not final proof.",
    ]),
    ("B2", 17): ("情境：一名学生正在向导师谈论公开演讲。", [
        "Public speaking causes Daniel a great deal of anxiety.",
        "His mentor says practice can build confidence and motivation.",
        "She also explains how stress can affect self-esteem.",
        "Together, they develop a plan to help Daniel cope.",
    ]),
    ("B2", 18): ("情境：同事们正在讨论一位新团队成员。", [
        "Jon's calm personality gives him a positive attitude at work.",
        "He has a habit of listening carefully before speaking.",
        "His empathy helps colleagues feel understood.",
        "His resilience helps the team recover after difficult projects.",
    ]),
    ("B2", 19): ("情境：当地组织正在帮助新到来的难民家庭。", [
        "The family crossed the border after escaping a violent conflict.",
        "Local services provide housing, language classes, and security advice.",
        "Volunteers explain that successful integration takes time.",
        "They discuss the wider challenges of migration with local residents.",
    ]),
    ("B2", 20): ("情境：国际组织正在应对一场严重危机。", [
        "The crisis has increased poverty and limited access to clean water.",
        "International cooperation brings emergency aid to affected communities.",
        "Clean water is the most urgent resource.",
        "Long-term development will require education, healthcare, and stable jobs.",
    ]),
}

SCENARIO_MANDARIN: dict[tuple[str, int], list[str]] = {
    ("B1", 1): ["我的背很痛，站起来时会感到头晕。", "我还咳嗽，手臂上有一小块皮疹。", "我的脚踝因为旧伤而肿了。", "我觉得应该休息并给医生打电话。"],
    ("B1", 2): ["我今天下午在诊所有预约。", "医生会给我做检查并讨论治疗方案。", "我可能需要一张买药的处方。", "如果没有好转，我会去看专科医生。"],
    ("B1", 3): ["医生说我需要多休息才能康复。", "健康饮食和轻度运动应该会有帮助。", "这几天我应该避免剧烈运动。", "我已经感觉好多了，所以这些建议似乎有效。"],
    ("B1", 4): ["我和同事要开会讨论新项目。", "我们查看了日程并商定了截止日期。", "我会写报告，她会进行审核。", "我们计划在星期五之前完成所有工作。"],
    ("B1", 5): ["我昨天提交了一份销售职位的申请。", "面试时，我会介绍自己的销售经验。", "公司想在下个月招聘一个人。", "我希望自己的资历适合这个职位。"],
    ("B1", 6): ["经理发来了一项关于报告问题的请求。", "我请她解释情况并确认截止日期。", "她对我的第一个解决方案提出了有用的反馈。", "我们一起商定了一个更好的解决方案。"],
    ("B1", 7): ["我们的目的地是海边的一座安静小镇。", "我已经预订并确认了住宿。", "我的护照和行程表都在随身包里。", "我希望其他行李不会太重。"],
    ("B1", 8): ["我们的火车晚点了，所以可能会迟到。", "我正在查看转车的站台。", "公司可能因为天气原因取消这趟车。", "如果发生这种情况，我会要求退款。"],
    ("B1", 9): ["房东带我看了一套车站附近的明亮公寓。", "租金合理，但押金相当高。", "我向上一位租客询问了这个社区的情况。", "签字之前，我会仔细阅读合同。"],
    ("B1", 10): ["水槽下面漏水，暖气也坏了。", "电没有问题，但晚上噪音太大。", "房东答应明天安排维修。", "我喜欢这个社区，所以希望这些问题能尽快解决。"],
    ("B1", 11): ["我的收入稳定，但这个月的支出增加了。", "我制定了预算，以便保留存款。", "目前我买不起新笔记本电脑。", "我会等商店打折以后再买。"],
    ("B1", 12): ["我今天早上从账户里转了一笔钱。", "银行对这笔付款收取了一小笔手续费。", "我保留了收据并检查了余额。", "现在一切看起来都正确。"],
    ("B1", 13): ["服务员拿来菜单，并介绍了今天的特色菜。", "我点了汤作为前菜，主菜点了鱼。", "我的朋友饭后选了一份甜点。", "服务非常好，所以我们留下了小费。"],
    ("B1", 14): ["我们找到了一份简单的食谱，并买了新鲜食材。", "我切蔬菜时，朋友煮了米饭。", "然后我们炒了一小份蔬菜。", "这顿饭做起来简单，味道也很好。"],
    ("B1", 15): ["我正在学习一门数字营销课程。", "这个科目很有用，但每项作业都要花几个小时。", "我上次考试取得了好成绩。", "最终证书可能帮助我找到更好的工作。"],
    ("B1", 16): ["我的目标是更自信地说英语。", "我每天练习，并在晚上复习新词。", "我努力记住实用短语，而不是单个单词。", "犯错时，我会从中学习并继续前进。"],
    ("B1", 17): ["我问了一个关于今天主题的问题。", "老师给出了清楚的答案和一个有帮助的例子。", "然后她请我解释自己的观点。", "这次讨论帮助大家更好地理解了这个主题。"],
    ("B1", 18): ["我邀请了几位朋友星期六一起吃晚饭。", "两位朋友接受了邀请，但有一位不得不拒绝。", "我们安排了时间，并选择了一家安静的餐厅。", "如果有人需要取消，我会建议另一个日期。"],
    ("B1", 19): ["开会前我很担心，但现在感到很自豪。", "经理给我的积极反馈让我很惊讶。", "我因为一个小错误感到尴尬。", "我很期待参与下一个项目。"],
    ("B1", 20): ["玛雅和利奥因为利奥没有遵守承诺而争吵。", "利奥道了歉，并请玛雅原谅他。", "玛雅说，重建信任需要时间。", "他们承诺会倾听并支持彼此。"],
    ("B2", 1): ["妮娜声称这篇报道提出了合理的论点。", "奥马尔认为作者的观点带有偏见。", "他们分析了报道背后的假设。", "最后，两人都认为证据并不完全有说服力。"],
    ("B2", 2): ["彼得认为西班牙拥有最好的足球队。", "艾米丽请他为自己的论点提供证据。", "彼得用最近的比赛结果来证明自己的观点。", "艾米丽提出了关于西班牙近期失利的反驳观点。", "他们得出结论，两支球队都有各自的优势。"],
    ("B2", 3): ["莉娜不同意拆除公园这一有争议的计划。", "马克质疑她的论点，但也承认她的担忧。", "莉娜用当地调查结果来说服他。", "最后，他们达成了保留一半公园的妥协方案。"],
    ("B2", 4): ["团队正在几台设备上测试新软件。", "它最好的功能是共享项目平台。", "最新更新修复了几个严重问题。", "购买软件之前，他们会检查兼容性。"],
    ("B2", 5): ["一次数据泄露暴露了几个客户账户。", "公司立即取消了系统的公共访问权限。", "公司采用了更强的密码并改进了加密。", "主管承诺优先保护客户隐私。"],
    ("B2", 6): ["平台每次推荐新内容时，米娅都会收到通知。", "算法根据她的观看记录选择这些推荐内容。", "她担心重复的内容可能影响自己的观点。", "她仍然订阅这个平台，但希望平台更严格地审核有害内容。"],
    ("B2", 7): ["工厂排放增加了河流附近的污染。", "居民上周发现了水污染的迹象。", "森林砍伐也造成了夏季缺水。", "市议会希望工厂减少排放和废物。"],
    ("B2", 8): ["市议会希望每个家庭回收更多废物。", "新规定将支持可再生能源项目。", "使用可持续材料的企业将获得奖励。", "该计划还包括水资源和森林保护。"],
    ("B2", 9): ["小镇最近先经历了干旱，随后又发生了洪水。", "小镇的气候适应计划保护沿海住宅。", "该计划也保护周围湿地的生物多样性。", "当地领导人希望该计划能够增强社区韧性。"],
    ("B2", 10): ["萨拉告诉导师，她希望获得晋升。", "她最近的表现展现了出色的领导能力。", "导师称赞了她在项目管理方面的专业知识。", "他建议她积累领导更大团队的经验。"],
    ("B2", 11): ["两家公司会面，商谈一项新提案。", "价格是一项重点，但产品质量同样重要。", "双方讨论了风险和益处。", "他们接受了低价与较慢交付之间的权衡。"],
    ("B2", 12): ["公司发现一个新市场的需求正在增长。", "其主要竞争对手已经提供类似产品。", "团队制定了注重质量和服务的策略。", "他们认为这项投资将在两年内带来利润。"],
    ("B2", 13): ["每位候选人都向当地公民解释自己的政策。", "一位代表重点关注住房和公共交通。", "另一位承诺保护工人的权利。", "选举让公民有机会影响公共决策。"],
    ("B2", 14): ["这项运动呼吁改变福利制度。", "组织者表示，改革可以减少不平等。", "他们希望每个少数群体都能得到更好的支持。", "他们的目标是建立一个以正义为基础的更公平制度。"],
    ("B2", 15): ["研究团队提出了一个关于每日练习的明确假设。", "他们设计了一项包含大量学习者样本的实验。", "每位参与者每周完成一次调查。", "研究人员将在三个月后比较数据。"],
    ("B2", 16): ["分析显示，客户满意度显著提高。", "然而，一个变量可能影响了这一趋势。", "团队需要更多证据才能改变策略。", "目前的结果很有希望，但还不能作为最终证明。"],
    ("B2", 17): ["公开演讲让丹尼尔感到非常焦虑。", "导师说，练习可以增强自信和动力。", "她还解释了压力如何影响自尊。", "他们一起制定了帮助丹尼尔应对压力的计划。"],
    ("B2", 18): ["乔恩冷静的性格让他在工作中保持积极态度。", "他习惯在说话前认真倾听。", "他的同理心让同事感到被理解。", "他的韧性帮助团队从困难项目中恢复过来。"],
    ("B2", 19): ["这个家庭在逃离暴力冲突后越过了边境。", "当地服务机构提供住房、语言课程和安全建议。", "志愿者解释说，成功融入需要时间。", "他们与当地居民讨论了移民带来的更广泛挑战。"],
    ("B2", 20): ["这场危机加剧了贫困，并限制了人们获得清洁饮用水。", "国际合作为受影响的社区带来了紧急援助。", "清洁饮用水是最紧急的资源。", "长期发展需要教育、医疗和稳定的工作。"],
}


def speech(text: str, language: str) -> dict[str, Any]:
    return {"type": "speech", "text": text, "language_code": language}


def silence(seconds: float) -> dict[str, Any]:
    return {"type": "silence", "seconds": seconds}


def model_answer(blocks: list[dict[str, Any]], text: str, *, prompt: str | None = None) -> None:
    if prompt:
        blocks.append(speech(prompt, "zh"))
        blocks.append(silence(response_pause(text)))
    blocks.append(speech(text, "en"))
    blocks.append(silence(reflection_pause(text)))


def expression_pattern(word: str) -> str:
    return EXPRESSION_PATTERNS.get(word, f"the {word}")


def expression_word(text: str) -> str:
    normalized = text.strip().rstrip(".")
    if normalized in LEGACY_EXPRESSION_PATTERNS:
        return LEGACY_EXPRESSION_PATTERNS[normalized]
    if normalized.startswith("the ") and normalized.removeprefix("the ") in LEGACY_EXPRESSION_PATTERNS:
        return LEGACY_EXPRESSION_PATTERNS[normalized.removeprefix("the ")]
    matched = next(
        (word for word, pattern in EXPRESSION_PATTERNS.items() if pattern == normalized),
        None,
    )
    if matched:
        return matched
    return normalized.removeprefix("the ")


def expression_recall(
    blocks: list[dict[str, Any]],
    word: str,
    meaning: str,
) -> None:
    answer = expression_pattern(word) + "."
    blocks.append(speech(f"请说英语：{meaning}。", "zh"))
    blocks.append(silence(response_pause(answer)))
    model_answer(blocks, answer)
    model_answer(blocks, answer)


def extract_lesson(path: Path, source_text: str | None = None) -> dict[str, Any]:
    segments = parse_tts_script(
        source_text if source_text is not None else path.read_text(encoding="utf-8")
    )
    lesson = int(re.search(r"Lesson_(\d+)_", path.name).group(1))
    level = path.name[:2]
    english = [
        segment["text"].strip()
        for segment in segments
        if segment["type"] == "speech" and segment.get("language_code") == "en"
    ]
    target_list = next(
        (text.rstrip(".").split(", ") for text in english if text.count(",") == 5),
        None,
    )
    if target_list:
        targets = target_list
    else:
        preview_start = next(
            index
            for index, segment in enumerate(segments)
            if segment["type"] == "speech"
            and segment.get("language_code") == "zh"
            and segment["text"].strip() == "今天的六个新英语表达是。"
        )
        targets = [
            expression_word(segment["text"])
            for segment in segments[preview_start + 1 :]
            if segment["type"] == "speech" and segment.get("language_code") == "en"
        ][:6]

    mandarin_blocks = [
        segment["text"].strip()
        for segment in segments
        if segment["type"] == "speech" and segment.get("language_code") == "zh"
    ]
    topic_match = next(
        (
            match
            for text in mandarin_blocks
            if (match := re.search(r"今天的主题是(.+?)(?:，|。)", text))
        ),
        None,
    )
    if topic_match:
        topic = topic_match.group(1)
    else:
        topic_segment = next(
            segment["text"].strip()
            for segment in segments
            if segment["type"] == "speech"
            and segment.get("language_code") == "zh"
            and segment["text"].strip().startswith("主题是")
        )
        topic = topic_segment.removeprefix("主题是")

    meanings: dict[str, str] = {}
    examples: dict[str, str] = {}
    section_three_index = next(
        (
            index
            for index, segment in enumerate(segments)
            if segment["type"] == "speech"
            and segment["text"].strip() == SECTION_TITLES[2]
        ),
        None,
    )
    section_four_index = next(
        (
            index
            for index, segment in enumerate(segments)
            if segment["type"] == "speech"
            and segment["text"].strip() == SECTION_TITLES[3]
        ),
        None,
    )
    if section_three_index is not None and section_four_index is not None:
        introduction = segments[section_three_index:section_four_index]
        for position, word in enumerate(targets, start=1):
            marker_index = next(
                index
                for index, item in enumerate(introduction)
                if item["type"] == "speech"
                and item["text"].strip() == f"今天的第{position}个表达是。"
            )
            following = [
                item for item in introduction[marker_index + 1 :] if item["type"] == "speech"
            ]
            meaning_block = next(
                item["text"].strip()
                for item in following
                if item.get("language_code") == "zh" and item["text"].startswith("意思是：")
            )
            meanings[word] = meaning_block.removeprefix("意思是：").split("。")[0]
            example_marker = next(
                index
                for index, item in enumerate(following)
                if item.get("language_code") == "zh" and item["text"].strip() == "请听例句。"
            )
            examples[word] = next(
                item["text"].strip()
                for item in following[example_marker + 1 :]
                if item.get("language_code") == "en"
            )
    else:
        for index, segment in enumerate(segments):
            if segment["type"] != "speech" or segment.get("language_code") != "en":
                continue
            word = expression_word(segment["text"])
            if word not in targets:
                continue
            following = [item for item in segments[index + 1 :] if item["type"] == "speech"]
            if word not in meanings:
                meaning_block = next(
                    (
                        item["text"].strip()
                        for item in following
                        if item.get("language_code") == "zh" and "意思是" in item["text"]
                    ),
                    "",
                )
                if meaning_block:
                    meanings[word] = re.split(r"意思是[:：]?", meaning_block, maxsplit=1)[1].split("。")[0]
            if word not in examples:
                for offset, item in enumerate(following):
                    if item.get("language_code") == "zh" and (
                        "现在听一个例句" in item["text"] or item["text"].strip() == "例句。"
                    ):
                        examples[word] = next(
                            candidate["text"].strip()
                            for candidate in following[offset + 1 :]
                            if candidate.get("language_code") == "en"
                        )
                        break

    if set(targets) != set(meanings) or set(targets) != set(examples):
        raise ValueError(f"Could not extract curriculum data from {path}")
    return {"lesson": lesson, "level": level, "topic": topic, "targets": targets, "meanings": meanings, "examples": examples}


def build_lesson(data: dict[str, Any], previous: dict[str, Any] | None) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    lesson, level, topic = data["lesson"], data["level"], data["topic"]
    targets, meanings, examples = data["targets"], data["meanings"], data["examples"]

    blocks += [
        speech(SECTION_TITLES[0], "zh"),
        speech(f"欢迎回来。今天是第{lesson}课，级别是{level}。", "zh"),
        speech(f"今天的主题是{topic}。", "zh"),
        speech("你会听到中文提示，并用英语回答。听到英语示范后，请大声重复。", "zh"),
        speech("今天的六个新英语表达是。", "zh"),
        speech(SECTION_TITLES[1], "zh"),
    ]
    preview_position = blocks.index(speech(SECTION_TITLES[1], "zh"))
    preview_blocks: list[dict[str, Any]] = []
    for index, word in enumerate(targets):
        preview_blocks.append(speech(expression_pattern(word) + ".", "en"))
        if index < len(targets) - 1:
            preview_blocks.append(silence(1.0))
    blocks[preview_position:preview_position] = preview_blocks

    if previous:
        blocks.append(speech("先复习上一课的几个表达。听中文，说英语。", "zh"))
        for word in previous["targets"][:4]:
            expression_recall(blocks, word, previous["meanings"][word])
        blocks.append(speech("现在复习上一课的两个句子。", "zh"))
        for word in previous["targets"][1:5:3]:
            model_answer(blocks, previous["examples"][word], prompt="请回忆并说出上一课的这个句子。")
    else:
        blocks.append(speech("这是第一课。我们直接开始学习新内容。", "zh"))

    blocks.append(speech(SECTION_TITLES[2], "zh"))
    for position, word in enumerate(targets, start=1):
        blocks.append(speech(f"今天的第{position}个表达是。", "zh"))
        blocks.append(speech(expression_pattern(word) + ".", "en"))
        blocks.append(speech(f"意思是：{meanings[word]}。请跟读。", "zh"))
        model_answer(blocks, expression_pattern(word) + ".")
        expression_recall(blocks, word, meanings[word])
        blocks.append(speech("请听例句。", "zh"))
        model_answer(blocks, examples[word])
        model_answer(blocks, examples[word], prompt="请重复这个英语句子。")

    blocks += [speech(SECTION_TITLES[3], "zh"), speech("现在打乱顺序，练习今天的新表达。", "zh")]
    for index in [3, 0, 5, 2, 4, 1]:
        word = targets[index]
        expression_recall(blocks, word, meanings[word])
    blocks.append(speech("现在练习三个完整句子。", "zh"))
    for index in [0, 3, 5]:
        model_answer(blocks, examples[targets[index]], prompt="请回忆并说出这个英语句子。")

    scenario_intro, scenario_sentences = SCENARIOS[(level, lesson)]
    scenario_mandarin = SCENARIO_MANDARIN[(level, lesson)]
    if len(scenario_sentences) != len(scenario_mandarin):
        raise ValueError(f"Scenario translation count mismatch for {level} lesson {lesson}")
    for sentence in scenario_sentences:
        used_targets = [
            word
            for word in targets
            if re.search(
                rf"(?<!\w){re.escape(word)}(?:s|ed|ing)?(?!\w)",
                sentence,
                flags=re.IGNORECASE,
            )
        ]
        if len(used_targets) > 2:
            raise ValueError(
                f"{level} lesson {lesson} scenario sentence uses more than two targets: "
                f"{used_targets}: {sentence}"
            )
    blocks += [
        speech(SECTION_TITLES[4], "zh"),
        speech(scenario_intro, "zh"),
        speech("先听每个英语句子，然后在停顿时大声重复。", "zh"),
    ]
    for index, sentence in enumerate(scenario_sentences):
        if index > 0:
            blocks.append(speech("请重复这个英语句子。", "zh"))
        blocks.append(speech(sentence, "en"))
        blocks.append(silence(response_pause(sentence)))
        blocks.append(speech(sentence, "en"))
        blocks.append(silence(reflection_pause(sentence)))
    blocks.append(speech("现在根据中文提示，把这个情境中的句子翻译成英语。", "zh"))
    for mandarin, sentence in zip(scenario_mandarin, scenario_sentences):
        model_answer(blocks, sentence, prompt=mandarin)

    blocks += [
        speech(SECTION_TITLES[5], "zh"),
        speech("最后，再复习今天的六个新表达。", "zh"),
    ]
    for word in targets:
        expression_recall(blocks, word, meanings[word])
    blocks.append(speech("很好。今天的练习到这里结束。请继续保持每天开口练习的习惯。", "zh"))
    return blocks


def main() -> None:
    changed: list[Path] = []
    for level, folder in COURSE_FOLDERS.items():
        paths = sorted(path for path in folder.glob(f"{level}_Lesson_*.txt") if "example" not in path.name)
        lessons = [extract_lesson(path) for path in paths]
        for path, data, previous in zip(paths, lessons, [None, *lessons[:-1]]):
            updated = render_segments(build_lesson(data, previous))
            if updated != path.read_text(encoding="utf-8").replace("\r\n", "\n"):
                path.write_text(updated, encoding="utf-8", newline="\n")
                changed.append(path)
    print(f"Rebuilt English lessons: {len(changed)}")
    for path in changed:
        print(path)


if __name__ == "__main__":
    main()
