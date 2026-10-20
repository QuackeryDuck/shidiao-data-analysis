"""调查渠道推荐：根据目标人群、区域、预算、周期与数据来源匹配渠道组合。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .brief import ResearchBrief
from .utils import largest_remainder, norm_key

DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass
class Channel:
    id: str
    name: str
    type: str
    coverage: str
    cost_level: str
    speed: str
    best_for: list[str]
    pros: str
    risks: str
    qc: str
    compliance: str
    region_scope: str
    score: float = 0.0


@dataclass
class ChannelPlan:
    primary: list[Channel] = field(default_factory=list)
    secondary: list[Channel] = field(default_factory=list)
    supplementary: list[Channel] = field(default_factory=list)
    backup: list[Channel] = field(default_factory=list)
    secondary_data: list[Channel] = field(default_factory=list)
    allocation: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def survey_channels(self) -> list[Channel]:
        return self.primary + self.secondary + self.supplementary + self.backup


def load_channels() -> list[Channel]:
    data = json.loads((DATA_DIR / "channels.json").read_text(encoding="utf-8"))
    out = []
    for item in data.get("channels", []):
        out.append(
            Channel(
                id=item["id"],
                name=item["name"],
                type=item.get("type", ""),
                coverage=item.get("coverage", ""),
                cost_level=item.get("cost_level", "中"),
                speed=item.get("speed", "中"),
                best_for=item.get("best_for", []),
                pros=item.get("pros", ""),
                risks=item.get("risks", ""),
                qc=item.get("qc", ""),
                compliance=item.get("compliance", ""),
                region_scope=item.get("region_scope", "全国"),
            )
        )
    return out


def _score(ch: Channel, brief: ResearchBrief) -> float:
    blob = brief.text_blob()
    pop = brief.target_population + " " + brief.region
    score = 0.0

    # 调查方式匹配
    mode = brief.survey_mode or ""
    if "线上" in mode and ch.type in {"线上", "线上+线下"}:
        score += 3
    if "线下" in mode and ch.type in {"线下", "线上+线下"}:
        score += 3
    if "混合" in mode and ch.type in {"线上", "线下", "线上+线下"}:
        score += 1.5
    if "定性" in mode and ch.type == "定性":
        score += 4

    # 目标人群关键词
    hits = sum(1 for k in ch.best_for if k and k in pop)
    score += min(6, hits * 2)

    # 数据来源匹配
    if brief.has_text_data() and ch.id in {"ecommerce_comments", "weibo", "xiaohongshu", "douyin"}:
        score += 4
    if brief.has_secondary_data() and "二手" in ch.type:
        score += 5
    if any(k in blob for k in ["B2B", "企业", "采购", "管理者"]) and ch.id == "b2b_email":
        score += 6
    if any(k in blob for k in ["访谈", "焦点小组", "探索性"]) and ch.id == "interview_focus":
        score += 5

    # 人群专项
    if any(k in pop for k in ["学生", "大学生", "研究生", "高校"]):
        if ch.id == "campus":
            score += 6
        elif ch.id in {"wechat", "wenjuanxing"}:
            score += 3
        elif ch.id in {"xiaohongshu", "douyin"}:
            score += 1.5
    if any(k in pop for k in ["老年", "中老年", "社区", "居民"]):
        if ch.id in {"community", "offline_intercept"}:
            score += 5
    if any(k in pop for k in ["白领", "职场", "企业职员"]):
        if ch.id in {"wechat", "xiaohongshu", "offline_intercept"}:
            score += 2

    # 区域
    if brief.region and brief.region not in {"全国", "待确认", ""}:
        if ch.region_scope.startswith("本地"):
            score += 2
    else:
        if ch.region_scope == "全国":
            score += 1

    # 预算与周期
    if brief.budget_cny is not None:
        if brief.budget_cny < 5000 and ch.cost_level == "低":
            score += 2
        elif brief.budget_cny > 20000 and ch.cost_level in {"中", "高"}:
            score += 1
    if brief.timeline_weeks is not None and brief.timeline_weeks <= 4:
        if ch.speed == "快":
            score += 2
        elif ch.speed == "慢":
            score -= 1

    # 二手渠道仅在确实需要时作为主渠道
    if "二手" in ch.type and not brief.has_secondary_data():
        score -= 4
    if "二手" in ch.type:
        score -= 1  # 二手渠道一般不承担问卷样本量
    return score


def recommend(brief: ResearchBrief, n_plan: int) -> ChannelPlan:
    channels = load_channels()
    for ch in channels:
        ch.score = _score(ch, brief)

    survey = [c for c in channels if "二手" not in c.type]
    secondary = sorted([c for c in channels if "二手" in c.type], key=lambda c: -c.score)
    survey.sort(key=lambda c: (-c.score, c.name))

    # 过滤明显不匹配的渠道
    positive = [c for c in survey if c.score > 0]
    if len(positive) < 4:
        positive = survey[:6]
    # 去重并保证线上/线下兼顾
    chosen = positive[:8]

    plan = ChannelPlan()
    plan.primary = chosen[:2]
    plan.secondary = chosen[2:4]
    plan.supplementary = chosen[4:6]
    plan.backup = chosen[6:8]
    plan.secondary_data = [c for c in secondary if c.score > 0][:4]

    # 分配问卷样本量
    tiers = [
        ("主要渠道", plan.primary, 0.50),
        ("次要渠道", plan.secondary, 0.30),
        ("补充渠道", plan.supplementary, 0.15),
        ("备用渠道", plan.backup, 0.05),
    ]
    rows = []
    for tier_name, tier_channels, tier_share in tiers:
        if not tier_channels:
            continue
        weights = [max(c.score, 0.5) for c in tier_channels]
        total = sum(weights)
        if total <= 0:
            weights = [1.0 for _ in tier_channels]
            total = len(weights)
        alloc = largest_remainder(int(round(n_plan * tier_share)), weights)
        for ch, share, n in zip(tier_channels, [w / total for w in weights], alloc):
            rows.append(
                {
                    "tier": tier_name,
                    "channel": ch,
                    "share": tier_share * share,
                    "sample": n,
                }
            )
    plan.allocation = rows

    if not plan.primary:
        plan.warnings.append("未能匹配到合适的线上/线下渠道，请补充目标人群与调查方式后重试。")
    if not any(c.type == "线上" for c in plan.survey_channels):
        plan.warnings.append("渠道组合缺少线上渠道，可能影响样本覆盖速度与成本。")
    if brief.has_secondary_data() and not plan.secondary_data:
        plan.warnings.append("研究涉及二手数据，但未匹配到二手资料渠道，请手动补充行业报告来源。")
    if any(c.type == "线下" for c in plan.primary) and brief.timeline_weeks and brief.timeline_weeks <= 3:
        plan.warnings.append("线下渠道执行周期通常长于 3 周，当前时间安排可能偏紧。")

    return plan
