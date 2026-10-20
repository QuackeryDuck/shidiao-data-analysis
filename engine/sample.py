"""样本量测算、分层配额与模型样本要求校验。"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .utils import clamp, fmt_num, fmt_pct, largest_remainder

Z_TABLE = {
    0.80: 1.282,
    0.85: 1.440,
    0.90: 1.645,
    0.95: 1.960,
    0.98: 2.326,
    0.99: 2.576,
}


def z_value(confidence: float) -> float:
    """取最接近的常用置信水平对应的 z 值。"""
    if confidence in Z_TABLE:
        return Z_TABLE[confidence]
    # 线性近似：常用区间内足够
    keys = sorted(Z_TABLE)
    if confidence <= keys[0]:
        return Z_TABLE[keys[0]]
    if confidence >= keys[-1]:
        return Z_TABLE[keys[-1]]
    for a, b in zip(keys, keys[1:]):
        if a <= confidence <= b:
            ratio = (confidence - a) / (b - a)
            return Z_TABLE[a] + ratio * (Z_TABLE[b] - Z_TABLE[a])
    return 1.96


@dataclass
class SampleResult:
    confidence: float
    margin_error: float
    proportion: float
    population_size: int | None
    design_effect: float
    response_rate: float
    z: float
    n_base: float
    n_base_rounded: int
    n_fpc: float | None
    n_effective: int
    n_plan: int
    expected_valid: int
    fpc_applied: bool

    def as_dict(self) -> dict:
        return {
            "confidence": self.confidence,
            "margin_error": self.margin_error,
            "proportion": self.proportion,
            "population_size": self.population_size,
            "design_effect": self.design_effect,
            "response_rate": self.response_rate,
            "z": self.z,
            "n_base": self.n_base,
            "n_base_rounded": self.n_base_rounded,
            "n_fpc": self.n_fpc,
            "n_effective": self.n_effective,
            "n_plan": self.n_plan,
            "expected_valid": self.expected_valid,
            "fpc_applied": self.fpc_applied,
        }


def calculate(
    confidence: float = 0.95,
    margin_error: float = 0.05,
    proportion: float = 0.5,
    population_size: int | None = None,
    design_effect: float = 1.0,
    response_rate: float = 1.0,
) -> SampleResult:
    """按简单随机抽样公式测算样本量，并考虑有限总体修正、设计效应与有效率。"""
    confidence = clamp(confidence, 0.5, 0.999)
    margin_error = clamp(margin_error, 0.001, 0.5)
    proportion = clamp(proportion, 0.01, 0.99)
    design_effect = max(design_effect, 1.0)
    response_rate = clamp(response_rate, 0.05, 1.0)
    z = z_value(confidence)

    n_base = (z ** 2) * proportion * (1 - proportion) / (margin_error ** 2)
    n_base_rounded = int(math.ceil(n_base))

    n_fpc: float | None = None
    fpc_applied = False
    if population_size and population_size > 0:
        n_fpc = n_base / (1 + (n_base - 1) / population_size)
        fpc_applied = True
        n_effective = int(math.ceil(n_fpc * design_effect))
    else:
        n_effective = int(math.ceil(n_base * design_effect))

    n_plan = int(math.ceil(n_effective / response_rate))
    expected_valid = int(math.floor(n_plan * response_rate))
    return SampleResult(
        confidence=confidence,
        margin_error=margin_error,
        proportion=proportion,
        population_size=population_size,
        design_effect=design_effect,
        response_rate=response_rate,
        z=z,
        n_base=n_base,
        n_base_rounded=n_base_rounded,
        n_fpc=n_fpc,
        n_effective=n_effective,
        n_plan=n_plan,
        expected_valid=expected_valid,
        fpc_applied=fpc_applied,
    )


def sensitivity_table(
    confidence_list: list[float],
    margin_list: list[float],
    proportion: float,
    population_size: int | None,
    design_effect: float,
    response_rate: float,
) -> list[dict]:
    rows = []
    for conf in confidence_list:
        for margin in margin_list:
            r = calculate(conf, margin, proportion, population_size, design_effect, response_rate)
            rows.append(
                {
                    "confidence": conf,
                    "margin_error": margin,
                    "z": r.z,
                    "n_base": r.n_base_rounded,
                    "n_effective": r.n_effective,
                    "n_plan": r.n_plan,
                }
            )
    return rows


def allocate_strata(strata, n_effective: int) -> list[dict]:
    """按比例/总体规模/等分把有效样本分配到各层。"""
    if not strata:
        return []
    weights: list[float] = []
    for s in strata:
        if s.proportion and s.proportion > 0:
            weights.append(s.proportion)
        elif s.population and s.population > 0:
            weights.append(float(s.population))
        else:
            weights.append(0.0)
    if sum(weights) <= 0:
        weights = [1.0 for _ in strata]
    total_w = sum(weights)
    weights = [w / total_w for w in weights]
    alloc = largest_remainder(n_effective, weights)
    out = []
    for s, w, n in zip(strata, weights, alloc):
        out.append(
            {
                "name": s.name,
                "weight": w,
                "sample": n,
                "population": s.population,
            }
        )
    return out


@dataclass
class ModelRequirement:
    model_id: str
    model_name: str
    min_sample: int | None
    basis: str
    satisfied: bool | None = None
    gap: int = 0
    note: str = ""
    dynamic: bool = False


def model_requirement(
    model_id: str,
    model_name: str,
    n_predictors: int = 5,
    n_items: int = 20,
    n_groups: int = 3,
    n_categories: int = 4,
) -> ModelRequirement:
    """根据模型类型与研究设计估算最低样本要求。"""
    p = max(1, n_predictors)
    items = max(3, n_items)
    groups = max(2, n_groups)
    cats = max(2, n_categories)

    table = {
        "descriptive": (30, "描述性统计的经验下限", False),
        "likert": (30, "量表分析的经验下限", False),
        "cronbach": (30, "题项数较少时的最低样本", False),
        "baidu_index": (None, "二手指数数据，无问卷样本量要求", False),
        "word_frequency": (100, "文本探索性分析的经验下限", False),
        "aisas": (100, "阶段人数估计的最低样本", False),
        "sheth_newman_gross": (100, "五维量表分析的最低样本", False),
        "pest": (None, "定性框架，无样本量要求", False),
        "swot": (None, "定性框架，无样本量要求", False),
        "stp": (200, "细分与定位分析的经验下限", False),
        "four_p": (None, "策略框架，无样本量要求", False),
        "sample_size": (None, "抽样设计工具本身不设样本下限", False),
        "chi_square": (max(100, 5 * cats * 2), "期望频数≥5 的近似要求", False),
        "crosstab": (100, "列联表分析的经验下限", False),
        "anova": (max(100, 30 * groups), "每组约 30 例的经验要求", False),
        "kmo_bartlett": (max(100, 5 * items), "题项数的 5 倍", True),
        "cluster": (200, "聚类分析的经验下限", False),
        "linear_regression": (max(50, 10 * (p + 1)), "每个自变量 10 例以上", True),
        "logistic_regression": (max(100, 20 * p), "每个自变量约 10 个事件（按 50% 事件率折算）", True),
        "servperf": (200, "五维量表分析的经验下限", False),
        "ipa": (100, "IPA 分析的经验下限", False),
        "web_crawler": (None, "文本数据获取，无问卷样本量要求", False),
        "snownlp": (100, "文本情感分析的经验下限", False),
        "tfidf": (100, "文本对比分析的经验下限", False),
        "association_rules": (200, "关联规则挖掘的经验下限", False),
        "random_forest": (300, "机器学习建模的经验下限", False),
        "multistage_pps": (None, "抽样设计工具本身不设样本下限", False),
        "pca_factor": (max(200, 5 * items), "题项数的 5—10 倍", True),
        "ahp": (None, "专家判断，无问卷样本量要求", False),
        "fuzzy_evaluation": (100, "模糊综合评价的经验下限", False),
        "sem": (200, "SEM 的经验下限", False),
        "lda": (500, "主题模型对语料规模的要求", False),
        "elastic_net": (max(200, 20 * p), "高维回归的经验下限", True),
        "lightgbm": (500, "梯度提升的经验下限", False),
        "bayesian_network": (300, "概率图模型的经验下限", False),
    }
    min_n, basis, dynamic = table.get(model_id, (None, "未登记", False))
    return ModelRequirement(
        model_id=model_id,
        model_name=model_name,
        min_sample=min_n,
        basis=basis,
        dynamic=dynamic,
    )


def check_requirements(requirements: list[ModelRequirement], n_effective: int) -> list[ModelRequirement]:
    for r in requirements:
        if r.min_sample is None:
            r.satisfied = None
            r.gap = 0
            r.note = "不适用"
        else:
            r.satisfied = n_effective >= r.min_sample
            r.gap = max(0, r.min_sample - n_effective)
            if r.satisfied:
                r.note = "满足"
            else:
                r.note = f"缺口 {fmt_num(r.gap)} 份"
    return requirements


def format_sample_summary(r: SampleResult) -> str:
    return (
        f"在 {fmt_pct(r.confidence, 0)} 置信水平、允许误差 ±{fmt_pct(r.margin_error, 1)}、"
        f"预估比例 {r.proportion:.2f} 下，基础样本量为 {fmt_num(r.n_base_rounded)} 份；"
        f"考虑设计效应 {r.design_effect:.2f} 与有效率 {fmt_pct(r.response_rate, 0)} 后，"
        f"需有效样本 {fmt_num(r.n_effective)} 份，计划发放 {fmt_num(r.n_plan)} 份。"
    )
