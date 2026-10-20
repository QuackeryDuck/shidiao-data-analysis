"""模型知识库、研究问题类型识别与方法推荐。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .brief import ResearchBrief, ResearchQuestion
from .sample import ModelRequirement, model_requirement
from .utils import norm_key, unique_keep_order

DATA_DIR = Path(__file__).resolve().parent / "data"


# ---------------------------------------------------------------------------
# 研究问题类型
# ---------------------------------------------------------------------------

QUESTION_TYPES: dict[str, dict] = {
    "descriptive": {
        "label": "现状与结构描述",
        "keywords": ["现状", "水平", "分布", "结构", "特征", "基本", "描绘", "了解", "概况", "占比"],
    },
    "group_difference": {
        "label": "群体差异比较",
        "keywords": ["差异", "比较", "不同", "组间", "群体", "性别", "年龄", "学历", "收入", "地区"],
    },
    "association": {
        "label": "变量关联",
        "keywords": ["关系", "相关", "关联", "共现", "交叉", "联系", "有关"],
    },
    "driver": {
        "label": "影响因素",
        "keywords": ["影响", "因素", "驱动", "决定", "作用", "机制", "解释", "成因", "为什么"],
    },
    "binary_outcome": {
        "label": "二分类结果",
        "keywords": ["概率", "可能性", "转化", "会不会", "是否购买", "是否愿意", "是否选择", "是否使用", "是否参与", "是否推荐"],
    },
    "segmentation": {
        "label": "市场细分与画像",
        "keywords": ["细分", "分群", "类型", "画像", "人群", "类别", "聚类"],
    },
    "evaluation": {
        "label": "评价与满意度",
        "keywords": ["满意度", "服务质量", "评价", "体验", "态度", "感受", "打分", "评分"],
    },
    "priority": {
        "label": "改进优先级",
        "keywords": ["优先级", "改进", "重要度", "资源", "排序", "薄弱"],
    },
    "mediation": {
        "label": "中介机制",
        "keywords": ["中介", "机制", "路径", "通过", "传导"],
    },
    "moderation": {
        "label": "调节效应",
        "keywords": ["调节", "情境", "条件下", "缓冲", "交互"],
    },
    "prediction": {
        "label": "预测与分类",
        "keywords": ["预测", "分类", "识别", "准确率", "模型", "机器学习"],
    },
    "text": {
        "label": "文本与舆情",
        "keywords": ["评论", "文本", "舆情", "关键词", "主题", "情感", "内容", "语料", "词频"],
    },
    "macro": {
        "label": "宏观与行业环境",
        "keywords": ["宏观", "行业", "政策", "趋势", "市场容量", "市场规模", "PEST"],
    },
    "strategy": {
        "label": "策略建议",
        "keywords": ["策略", "定位", "营销", "建议", "组合", "推广", "对策"],
    },
    "weighting": {
        "label": "指标赋权与综合评价",
        "keywords": ["权重", "指标体系", "赋权", "综合评价", "评分", "指数"],
    },
    "sampling": {
        "label": "抽样与代表性",
        "keywords": ["抽样", "代表性", "样本量", "样本结构", "配额"],
    },
    "reliability": {
        "label": "信度",
        "keywords": ["信度", "一致性", "可靠性"],
    },
    "validity": {
        "label": "效度与结构",
        "keywords": ["效度", "因子", "维度", "结构", "量表"],
    },
    "latent": {
        "label": "潜变量与路径",
        "keywords": ["潜变量", "构念", "量表", "结构方程", "路径"],
    },
}


def infer_question_types(text: str) -> list[str]:
    """从一段研究问题/目标中识别可能的研究类型。"""
    text = (text or "").strip()
    if not text:
        return []
    hits: list[str] = []
    for key, info in QUESTION_TYPES.items():
        for kw in info["keywords"]:
            if kw.startswith("在.*"):
                import re

                if re.search(kw, text):
                    hits.append(key)
                    break
            elif kw in text:
                hits.append(key)
                break
    # 补充：出现“影响”时，若同时出现“是否”，同时保留 driver 与 binary
    return unique_keep_order(hits)


def label_for_type(key: str) -> str:
    return QUESTION_TYPES.get(key, {}).get("label", key)


# ---------------------------------------------------------------------------
# 模型
# ---------------------------------------------------------------------------


@dataclass
class Model:
    id: str
    name: str
    en: str
    level: str
    chapter: int
    category: str
    purposes: list[str]
    question_types: list[str]
    dep_type: list[str]
    indep_type: list[str]
    min_sample: int | None
    assumptions: list[str]
    inputs: str
    outputs: str
    report: str
    pitfalls: str
    software: list[str]
    formula: str
    undergrad_fit: int
    tags: list[str]
    fallback: str

    @property
    def is_advanced(self) -> bool:
        return self.level == "高阶"


def load_models() -> dict[str, Model]:
    path = DATA_DIR / "models.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, Model] = {}
    for item in data.get("models", []):
        m = Model(
            id=item["id"],
            name=item["name"],
            en=item.get("en", ""),
            level=item.get("level", "进阶"),
            chapter=int(item.get("chapter", 2)),
            category=item.get("category", ""),
            purposes=item.get("purposes", []),
            question_types=item.get("question_types", []),
            dep_type=item.get("dep_type", []),
            indep_type=item.get("indep_type", []),
            min_sample=item.get("min_sample"),
            assumptions=item.get("assumptions", []),
            inputs=item.get("inputs", ""),
            outputs=item.get("outputs", ""),
            report=item.get("report", ""),
            pitfalls=item.get("pitfalls", ""),
            software=item.get("software", []),
            formula=item.get("formula", ""),
            undergrad_fit=int(item.get("undergrad_fit", 3)),
            tags=item.get("tags", []),
            fallback=item.get("fallback", ""),
        )
        out[m.id] = m
    return out


# 模型 -> 可回答的问题类型（内部键）
MODEL_QUESTION_MAP: dict[str, list[str]] = {
    "descriptive": ["descriptive", "group_difference"],
    "likert": ["descriptive", "evaluation", "latent", "attitude"],
    "cronbach": ["reliability", "validity"],
    "baidu_index": ["macro", "descriptive", "sampling"],
    "word_frequency": ["text", "descriptive"],
    "aisas": ["strategy", "evaluation", "binary_outcome"],
    "sheth_newman_gross": ["driver", "evaluation", "latent"],
    "pest": ["macro", "strategy"],
    "swot": ["strategy", "macro"],
    "stp": ["segmentation", "strategy"],
    "four_p": ["strategy"],
    "sample_size": ["sampling", "descriptive"],
    "chi_square": ["association", "group_difference", "sampling"],
    "crosstab": ["association", "group_difference", "descriptive", "segmentation"],
    "anova": ["group_difference", "driver"],
    "kmo_bartlett": ["validity", "latent", "reliability"],
    "cluster": ["segmentation"],
    "linear_regression": ["driver", "prediction", "association", "mediation", "moderation"],
    "logistic_regression": ["driver", "binary_outcome", "prediction"],
    "servperf": ["evaluation", "priority"],
    "ipa": ["priority", "evaluation"],
    "web_crawler": ["text", "sampling"],
    "snownlp": ["text", "evaluation"],
    "tfidf": ["text", "segmentation"],
    "association_rules": ["association", "segmentation"],
    "random_forest": ["prediction", "driver", "segmentation"],
    "multistage_pps": ["sampling"],
    "pca_factor": ["validity", "latent", "segmentation", "weighting"],
    "ahp": ["weighting", "priority", "evaluation"],
    "fuzzy_evaluation": ["weighting", "evaluation", "priority"],
    "sem": ["mediation", "moderation", "latent", "driver", "evaluation"],
    "lda": ["text", "segmentation"],
    "elastic_net": ["driver", "prediction", "latent"],
    "lightgbm": ["prediction", "driver", "segmentation"],
    "bayesian_network": ["prediction", "driver", "latent"],
}

TYPE_REASON = {
    "descriptive": "用于刻画样本结构与核心变量的水平、分布",
    "group_difference": "用于检验不同群体在结果变量上的差异",
    "association": "用于检验分类变量之间的关联强度",
    "driver": "用于识别影响结果变量的关键因素及其相对作用",
    "binary_outcome": "用于分析二分类结果的发生概率与影响因素",
    "segmentation": "用于将受访者划分为可解释、可运营的细分群体",
    "evaluation": "用于测量满意度、服务质量或体验的维度表现",
    "priority": "用于确定资源投放与改进的优先顺序",
    "mediation": "用于检验变量之间的作用机制与中介路径",
    "moderation": "用于检验情境变量对核心关系的调节作用",
    "prediction": "用于预测结果并排序特征贡献",
    "text": "用于从评论、舆情或开放题中提取主题与情感",
    "macro": "用于补充行业、政策与宏观环境证据",
    "strategy": "用于把数据分析结论转化为可执行的策略",
    "weighting": "用于构建指标权重与综合评价体系",
    "sampling": "用于论证样本量、抽样方法与代表性",
    "reliability": "用于评价量表内部一致性",
    "validity": "用于检验量表结构与测量效度",
    "latent": "用于处理潜变量、测量误差与路径关系",
}


@dataclass
class Recommendation:
    core: list[Model] = field(default_factory=list)
    optional: list[Model] = field(default_factory=list)
    per_rq: dict[str, list[str]] = field(default_factory=dict)
    rationales: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    advanced_count: int = 0


def _name_matches(preferred: str, model: Model) -> bool:
    p = norm_key(preferred)
    if not p:
        return False
    return p in norm_key(model.name) or p in norm_key(model.en) or norm_key(model.id) in p


def _score_model(
    model: Model,
    matched_types: set[str],
    brief: ResearchBrief,
    n_effective: int,
    dv_types: set[str],
    preferred: list[str],
    apply_context: bool = True,
) -> float:
    score = 0.0
    model_types = set(MODEL_QUESTION_MAP.get(model.id, []))
    overlap = matched_types & model_types
    score += min(8.0, 4.0 * len(overlap))

    if model.level == "基础":
        score += 1.0
    elif model.level == "高阶":
        score -= 1.0
        # 高阶方法只在问题确实需要时保留
        if overlap and any(t in {"mediation", "moderation", "latent", "weighting", "text"} for t in overlap):
            score += 2.0
    if model.undergrad_fit <= 2 and not overlap:
        score -= 2.0

    if apply_context and any(_name_matches(p, model) for p in preferred):
        score += 6.0

    # 因变量类型匹配
    if dv_types:
        if any(t in model.dep_type for t in dv_types):
            score += 2.0
        elif model.dep_type and "none" not in model.dep_type:
            if any(t in {"continuous", "ordinal"} for t in dv_types) and "continuous" in model.dep_type:
                score += 1.0
            elif "binary" in dv_types and "binary" not in model.dep_type and model.id in {
                "linear_regression",
                "anova",
                "elastic_net",
            }:
                score -= 3.0

    # 数据类型与调查方式的全局匹配；逐题打分时关闭，避免所有 RQ 都推荐同一组方法
    if apply_context:
        if brief.has_text_data() and model.id in {"word_frequency", "snownlp", "tfidf", "lda", "web_crawler"}:
            score += 2.0
        if brief.has_secondary_data() and model.id in {"pest", "swot", "baidu_index"}:
            score += 1.5
        if brief.has_primary_survey() and model.id in {"sample_size", "descriptive"}:
            score += 3.0
    if model.id in {"pest", "swot", "four_p"} and matched_types and not (matched_types & {"macro", "strategy"}):
        score -= 2.0

    # 样本量不足时降权
    if model.min_sample is not None and n_effective and n_effective < model.min_sample:
        score -= 5.0
    return score


def recommend_models(
    brief: ResearchBrief,
    rq_types: dict[str, list[str]],
    n_effective: int,
    dv_types: set[str] | None = None,
    construct_count: int = 0,
    item_count: int = 0,
) -> Recommendation:
    """基于研究问题类型、样本量与变量结构推荐模型组合。"""
    models = load_models()
    dv_types = dv_types or set()
    preferred = brief.preferred_methods
    all_types: set[str] = set()
    for types in rq_types.values():
        all_types.update(types)

    # 每个研究问题单独打分
    per_rq_scores: dict[str, list[tuple[float, str]]] = {}
    for qid, types in rq_types.items():
        tset = set(types)
        scored = []
        for m in models.values():
            s = _score_model(m, tset, brief, n_effective, dv_types, preferred, apply_context=False)
            if s > 0:
                scored.append((s, m.id))
        scored.sort(key=lambda x: (-x[0], x[1]))
        per_rq_scores[qid] = scored

    # 全局得分：所有问题类型合并
    global_scores: dict[str, float] = {}
    for m in models.values():
        global_scores[m.id] = _score_model(m, all_types, brief, n_effective, dv_types, preferred)

    rec = Recommendation()
    chosen: list[str] = []

    def add(model_id: str, reason: str | None = None):
        if model_id in chosen or model_id not in models:
            return
        chosen.append(model_id)
        if reason:
            rec.rationales[model_id] = reason

    # --- 必备方法 -------------------------------------------------------
    if brief.has_primary_survey():
        add("sample_size", "问卷调查研究必须交代样本量与抽样依据，用于论证样本代表性。")
        add("descriptive", "所有实证分析的第一步，用于呈现样本结构与核心变量分布。")

    has_likert = any("李克特" in c.scale or "量表" in c.scale for c in brief.constructs)
    if has_likert or construct_count >= 2:
        add("likert", "核心构念采用量表测量，需要说明计分方式与维度合成规则。")
        add("cronbach", "多题项量表需报告内部一致性信度，作为后续分析的质量前提。")
    if has_likert and (construct_count >= 2 or item_count >= 8):
        add("kmo_bartlett", "多题项量表需检验结构效度与因子分析适用性。")

    # --- 按问题类型选择 -------------------------------------------------
    if "group_difference" in all_types:
        if "continuous" in dv_types or not dv_types:
            add("anova", TYPE_REASON["group_difference"] + "，连续因变量优先用方差分析。")
        add("crosstab", "用于呈现不同群体在分类结果上的分布差异，并可配合卡方检验。")
        add("chi_square", "用于检验群体分布差异是否具有统计显著性。")

    if "association" in all_types:
        add("crosstab", TYPE_REASON["association"] + "，列联表是最直观的呈现方式。")
        add("chi_square", "用于检验分类变量关联的统计显著性。")

    if "driver" in all_types:
        if "binary" in dv_types:
            add("logistic_regression", TYPE_REASON["binary_outcome"] + "，因变量为二分类，采用 Logistic 回归。")
        else:
            add("linear_regression", TYPE_REASON["driver"] + "，连续因变量优先用多元线性回归。")
        add("anova", "用于先检验不同群体在结果变量上的差异，为回归变量筛选提供依据。")

    if "binary_outcome" in all_types:
        add("logistic_regression", "因变量为二分类（如是否购买、是否愿意），Logistic 回归可直接解释发生比。")
        add("crosstab", "用于初步呈现二分类结果在不同群体中的分布。")

    if "segmentation" in all_types:
        add("cluster", TYPE_REASON["segmentation"] + "，K-Means/K-Modes 是常用的分群方法。")
        add("stp", "在聚类分群后完成目标市场选择与定位，使分群结果可落地。")

    if "evaluation" in all_types:
        add("servperf", "用于从有形性、可靠性、响应性、保证性、移情性五维度测量服务质量与体验。")
        add("ipa", "用于把重要度与满意度结合，识别优先改进项。")

    if "priority" in all_types:
        add("ipa", TYPE_REASON["priority"] + "，四象限图便于直接沟通。")

    if "mediation" in all_types:
        if n_effective >= 200:
            add("sem", "研究问题涉及中介机制，SEM 可同时处理潜变量测量误差与路径关系。")
        else:
            add("linear_regression", "样本量不足以支撑 SEM，改用回归 + Bootstrap 中介检验作为降级方案。")
            rec.warnings.append("样本量低于 200，不建议使用 SEM；已改为回归 + Bootstrap 中介检验。")

    if "moderation" in all_types:
        add("linear_regression", "通过中心化后构造交互项检验调节效应，是本科生可操作的稳妥方案。")
        if n_effective >= 200:
            rec.warnings.append("若理论模型较复杂，可将 SEM 作为调节效应的进阶备选。")

    if "text" in all_types or brief.has_text_data():
        add("word_frequency", "文本分析的第一步，用于了解语料主题分布与高频词。")
        add("tfidf", "用于识别不同品牌/群体/文档的差异化关键词。")
        add("snownlp", "用于判断评论情感倾向，需配合人工抽样复核。")
        if n_effective >= 500 or brief.has_text_data():
            # 文本样本量用条数衡量，这里仅作为可选建议
            rec.optional.append(models["lda"]) if "lda" not in chosen else None

    if "macro" in all_types:
        add("pest", "用于补充政策、经济、社会、技术四维宏观环境证据。")
        add("baidu_index", "用于提供网络关注度与区域市场潜力的客观佐证。")

    if "strategy" in all_types:
        add("swot", "用于整合内外部条件并导出 SO/ST/WO/WT 交叉策略。")
        add("stp", "用于明确目标市场与差异化定位。")
        add("four_p", "用于把研究结论转译为产品、价格、渠道、促销建议。")

    if "weighting" in all_types:
        add("ahp", "用于构建指标权重体系，需报告判断矩阵与一致性比率。")
        add("fuzzy_evaluation", "用于把多指标评价合成为综合得分与等级。")

    if "prediction" in all_types:
        add("random_forest", "用于预测与特征重要性排序，适合中小规模数据。")
        if n_effective >= 500:
            rec.optional.append(models["lightgbm"])
            rec.optional.append(models["elastic_net"])
        else:
            rec.warnings.append("样本量低于 500，不建议使用 LightGBM 等高阶模型，随机森林或回归更稳妥。")

    if "sampling" in all_types and not brief.has_primary_survey():
        add("multistage_pps", "用于说明多阶段/PPS 抽样设计、设计效应与样本量分解。")

    # --- 记录每个 RQ 的 top 模型（仅用于“问题—方法”对应表） -------------
    # 不在这里扩充核心模型集合，否则每个 RQ 的局部高分模型会不断叠加，
    # 使核心方法清单膨胀。全局方法族已在上面的问题类型分支中确定。
    for qid, scored in per_rq_scores.items():
        rec.per_rq[qid] = [mid for s, mid in scored[:3] if s >= 4]

    # --- 组织核心/可选 ---------------------------------------------------
    core = [models[mid] for mid in chosen]
    # 排序：基础 -> 进阶 -> 高阶，保持组内加入顺序
    order = {"基础": 0, "进阶": 1, "高阶": 2}
    core.sort(key=lambda m: order.get(m.level, 1))

    optional_ids = []
    for m in rec.optional:
        if m.id not in chosen and m.id not in optional_ids:
            optional_ids.append(m.id)
    # 全局高分但未入选的模型作为可选
    ranked = sorted(global_scores.items(), key=lambda x: -x[1])
    for mid, s in ranked:
        if mid not in chosen and mid not in optional_ids and s >= 3:
            optional_ids.append(mid)
    # 高阶模型最多保留 3 个在核心
    advanced_core = [m for m in core if m.level == "高阶"]
    if len(advanced_core) > 3:
        keep = set(m.id for m in advanced_core[:3])
        for m in advanced_core[3:]:
            optional_ids.append(m.id)
        core = [m for m in core if m.level != "高阶" or m.id in keep]

    rec.core = core
    core_ids = {m.id for m in core}
    for qid, ids in rec.per_rq.items():
        rec.per_rq[qid] = [mid for mid in ids if mid in core_ids]
    rec.optional = [models[mid] for mid in optional_ids if mid in models][:8]
    rec.advanced_count = sum(1 for m in core if m.level == "高阶")

    # 样本量校验
    if n_effective:
        for m in core:
            if m.min_sample and n_effective < m.min_sample:
                rec.warnings.append(
                    f"当前有效样本 {n_effective} 份低于「{m.name}」的建议下限 {m.min_sample} 份，需扩大样本或改用降级方案。"
                )

    if not rec.rationales:
        rec.rationales["descriptive"] = "用于建立对样本与核心变量的基本认识。"
    return rec


def _reason_for_model(model: Model, all_types: set[str]) -> str:
    model_types = set(MODEL_QUESTION_MAP.get(model.id, []))
    overlap = model_types & all_types
    if overlap:
        reasons = [TYPE_REASON[t] for t in sorted(overlap) if t in TYPE_REASON]
        if reasons:
            return reasons[0] + "。"
    return "与当前研究问题或数据结构相匹配。"


def requirements_for_models(
    models: Iterable[Model],
    n_effective: int,
    n_predictors: int,
    n_items: int,
    n_groups: int,
) -> list[ModelRequirement]:
    reqs = []
    for m in models:
        req = model_requirement(
            m.id,
            m.name,
            n_predictors=n_predictors,
            n_items=n_items,
            n_groups=n_groups,
        )
        if req.min_sample is not None:
            req.satisfied = n_effective >= req.min_sample
            req.gap = max(0, req.min_sample - n_effective)
            req.note = "满足" if req.satisfied else f"缺口 {req.gap} 份"
        else:
            req.satisfied = None
            req.note = "不适用"
        reqs.append(req)
    return reqs
