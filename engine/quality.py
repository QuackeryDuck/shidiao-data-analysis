"""质量控制方案：按研究设计组装设计、执行、清洗、分析与交付质控措施。"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from .brief import ResearchBrief
from .channels import ChannelPlan

DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass
class QcPlan:
    stages: list[dict] = field(default_factory=list)
    invalid_rules: list[dict] = field(default_factory=list)
    acceptance: list[dict] = field(default_factory=list)
    ethics: list[str] = field(default_factory=list)
    extra_measures: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def build(brief: ResearchBrief, channel_plan: ChannelPlan | None = None) -> QcPlan:
    data = json.loads((DATA_DIR / "qc.json").read_text(encoding="utf-8"))
    plan = QcPlan(
        stages=deepcopy(data.get("stages", [])),
        invalid_rules=deepcopy(data.get("invalid_rules", [])),
        acceptance=deepcopy(data.get("acceptance", [])),
        ethics=list(data.get("ethics", [])),
    )

    extras: list[dict] = []
    if any("线上" in (c.type or "") for c in (channel_plan.survey_channels if channel_plan else [])):
        extras.append(
            {
                "stage": "执行阶段",
                "point": "线上样本防重复",
                "measure": "启用 IP、设备指纹、微信/账号去重；同设备多份问卷进入人工复核",
                "standard": "同一设备/账号最多计 1 份有效样本",
                "record": "平台去重日志",
            }
        )
        extras.append(
            {
                "stage": "执行阶段",
                "point": "线上配额与渠道平衡",
                "measure": "每日监控各渠道回收量与人群配额，单一渠道占比不超过 40%",
                "standard": "渠道结构与配额表偏差≤5 个百分点",
                "record": "每日回收报表",
            }
        )
    if any("线下" in (c.type or "") for c in (channel_plan.survey_channels if channel_plan else [])):
        extras.append(
            {
                "stage": "执行阶段",
                "point": "访问员一致性",
                "measure": "统一培训、话术与访问记录；督导随机跟访",
                "standard": "访问员间关键题项分布无系统性差异",
                "record": "培训记录、跟访表",
            }
        )
    if brief.has_text_data():
        extras.append(
            {
                "stage": "清洗阶段",
                "point": "文本语料清洗",
                "measure": "去重、去广告、去水军、统一编码；抽样人工复核",
                "standard": "有效文本率≥80%；人工复核一致率≥85%",
                "record": "语料清洗日志、复核表",
            }
        )
        extras.append(
            {
                "stage": "合规",
                "point": "文本抓取合规",
                "measure": "遵守平台协议与 robots.txt；不抓取个人身份信息；仅使用公开文本",
                "standard": "无个人信息字段；来源可追溯",
                "record": "来源清单与合规说明",
            }
        )
    if any("访谈" in s or "定性" in s for s in brief.data_sources) or "访谈" in brief.text_blob():
        extras.append(
            {
                "stage": "执行阶段",
                "point": "定性资料质控",
                "measure": "统一访谈提纲；录音经授权；双人独立编码",
                "standard": "编码一致率≥90%；关键主题可追溯至原始语句",
                "record": "访谈记录、编码表",
            }
        )

    plan.extra_measures = extras

    if not brief.target_population or brief.target_population == "待确认":
        plan.warnings.append("目标总体未明确，质控方案中的配额与甄别标准需在确定总体后补充。")
    if brief.expected_proportion == 0.5 and not brief.research_questions:
        plan.warnings.append("研究问题缺失，质量控制的构念—题项对应关系无法完整建立。")
    return plan
