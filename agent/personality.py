"""
OCEAN personality model — converts five dimension scores (0–100) to Chinese descriptive text.

Dimensions:
  O — Openness to experience (开放性)
  C — Conscientiousness     (尽责性)
  E — Extraversion          (外向性)
  A — Agreeableness         (宜人性)
  N — Neuroticism           (神经质)
"""

from __future__ import annotations


def _level(score: float) -> int:
    """Map a 0–100 score to a level index 0–4 (very low → very high)."""
    if score <= 20:
        return 0
    if score <= 40:
        return 1
    if score <= 60:
        return 2
    if score <= 80:
        return 3
    return 4


_O_DESCRIPTIONS = [
    "务实保守，倾向于熟悉的常规，对新鲜事物持谨慎态度",
    "偏向传统，不太热衷于新奇体验，更喜欢已知和可预期的事物",
    "在传统与创新之间保持平衡，偶尔会对新事物感到好奇",
    "思维开放，乐于接受新想法，有较强的创造力和好奇心",
    "极具创造力和想象力，对新事物充满好奇，思维天马行空",
]

_C_DESCRIPTIONS = [
    "行事随意，缺乏计划性，容易被当下冲动左右",
    "做事较为随性，缺乏条理，有时容易拖延",
    "责任心适中，能完成日常任务，但有时会较为松散",
    "有较强的责任心和自律性，做事认真有条理",
    "极为自律，做事井井有条，目标明确，追求完美",
]

_E_DESCRIPTIONS = [
    "性格内向，独自一人时精力最充沛，社交场合令其感到疲倦",
    "偏向内敛，享受独处时光，在社交场合相对保守",
    "在社交与独处之间保持平衡，能适应不同场合",
    "性格外向开朗，享受与人交往，在社交活动中精力充沛",
    "极为外向活泼，热衷社交，充满活力，喜欢成为人群焦点",
]

_A_DESCRIPTIONS = [
    "以自我为中心，对他人抱有一定怀疑，容易与人产生摩擦",
    "较为直接甚至强势，不太在意他人感受，竞争意识较强",
    "能与人合作，但也会在需要时坚持自己的立场",
    "待人友善，富有同情心，善于协调人际关系",
    "极为善良温和，乐于助人，对他人充满同理心，善于合作",
]

_N_DESCRIPTIONS = [
    "情绪非常稳定，冷静自持，极少受压力或负面情绪影响",
    "情绪较为稳定，不容易被负面情绪左右",
    "情绪状态适中，偶尔会有压力，但通常能自我调节",
    "情绪较为敏感，容易受外界影响，有时感到焦虑或不安",
    "情绪波动较为剧烈，容易焦虑紧张，在压力下情绪容易起伏",
]


def ocean_to_description(o: float, c: float, e: float, a: float, n: float) -> str:
    """
    Convert OCEAN dimension scores (each 0–100) to a Chinese personality description.

    Args:
        o: Openness to experience
        c: Conscientiousness
        e: Extraversion
        a: Agreeableness
        n: Neuroticism

    Returns:
        A natural-language personality description string.
    """
    o_desc = _O_DESCRIPTIONS[_level(o)]
    c_desc = _C_DESCRIPTIONS[_level(c)]
    e_desc = _E_DESCRIPTIONS[_level(e)]
    a_desc = _A_DESCRIPTIONS[_level(a)]
    n_desc = _N_DESCRIPTIONS[_level(n)]

    return (
        f"在开放性方面，{o_desc}。"
        f"在尽责性方面，{c_desc}。"
        f"在外向性方面，{e_desc}。"
        f"在宜人性方面，{a_desc}。"
        f"在情绪稳定性方面，{n_desc}。"
    )
