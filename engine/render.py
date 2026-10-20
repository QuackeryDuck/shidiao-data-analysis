"""把研究需求、变量体系、样本方案、模型推荐与质控方案渲染为 Markdown 数据需求文档。"""

from __future__ import annotations

import datetime as _dt
from collections import OrderedDict

from .brief import Construct, Hypothesis, ResearchBrief, ValidationIssue
from .channels import ChannelPlan
from .knowledge import MODEL_QUESTION_MAP, Model, Recommendation, label_for_type
from .quality import QcPlan
from .sample import ModelRequirement, SampleResult
from .utils import fmt_num, fmt_pct, md_table, unique_keep_order
from .variables import VariableAnalysis, VariableRow

ROLE_CN = {
    "dependent": "因变量",
    "independent": "自变量",
    "mediator": "中介变量",
    "moderator": "调节变量",
    "control": "控制变量",
    "screening": "筛选变量",
    "exploratory": "探索性变量",
}

ROLE_PURPOSE = {
    "dependent": "研究的核心结果，所有假设与模型最终都指向它",
    "independent": "解释结果差异的主要前因，用于检验影响方向与强度",
    "mediator": "解释自变量如何作用于因变量的中间机制",
    "moderator": "界定核心关系在不同情境/群体下的边界条件",
    "control": "排除个体与背景差异的干扰，提高模型解释的可靠性",
    "screening": "保证样本符合研究总体与伦理要求",
    "exploratory": "用于描述性分析或后续探索，不进入核心假设检验",
}

MEASUREMENT_MODELS = {"likert", "cronbach", "kmo_bartlett", "pca_factor"}
TEXT_MODELS = {"word_frequency", "tfidf", "snownlp", "lda", "web_crawler"}
CAUSAL_MODELS = {"linear_regression", "logistic_regression", "anova", "chi_square", "sem", "random_forest", "elastic_net", "lightgbm"}
MODEL_RQ_TYPES = {
    "linear_regression": {"driver", "mediation", "moderation"},
    "logistic_regression": {"driver", "binary_outcome"},
    "anova": {"group_difference", "driver"},
    "chi_square": {"group_difference", "association"},
    "sem": {"driver", "mediation", "moderation", "latent"},
    "random_forest": {"prediction", "driver"},
    "elastic_net": {"driver", "prediction"},
    "lightgbm": {"prediction", "driver"},
}

ASSUMPTION_TEST = [
    (["代表性"], "样本结构与总体结构对比（性别/年级/地区/渠道）", "配额完成率≥90%，关键结构差异可解释", "补样、加权或明确外推边界"),
    (["变量定义", "编码口径", "编码清晰"], "数据字典与问卷逐题核对", "字段名、取值、缺失编码一致", "修订数据字典并回溯清洗"),
    (["题项同向", "反向题"], "项目—总分相关、反向题重编码检查", "同维度题项相关为正，反向题已转换", "重新编码或删除题项"),
    (["多题项", "同一构念"], "探索性因子分析 / 维度相关矩阵", "同一维度载荷>0.5，无明显交叉载荷", "删题或重新划分维度"),
    (["参数取值", "设计效应", "有效率", "预调研", "经验支持"], "逐项核对文献、预调研或同类调查依据", "每个参数均有可追溯来源", "补充依据或改用保守取值"),
    (["观测相互独立", "观测独立", "误差独立"], "研究设计与数据结构核查（横截面个体独立；时间序列用 Durbin-Watson）", "抽样与作答过程互不影响；时间序列 DW≈2", "检查收集过程；时间序列改用 HAC/稳健标准误"),
    (["正态"], "Shapiro-Wilk / Kolmogorov-Smirnov；偏度与峰度", "p>0.05 或偏度绝对值<2、峰度绝对值<7", "改用非参数检验或 Bootstrap"),
    (["方差齐"], "Levene 检验", "p>0.05", "改用 Welch ANOVA 或非参数检验"),
    (["共线性", "VIF"], "VIF / 容忍度", "VIF<5（宽松<10）", "删除或合并变量、主成分/岭回归"),
    (["期望频数"], "列联表期望频数", "各格≥5", "合并类别或 Fisher 精确检验"),
    (["KMO"], "KMO 检验", "KMO>0.7", "增加题项/样本或放弃因子分析"),
    (["Bartlett", "巴特利特"], "Bartlett 球形检验", "p<0.05", "检查题项相关结构"),
    (["线性"], "散点图、残差—拟合值图", "无明显非线性模式", "变量变换或非线性模型"),
    (["同方差"], "残差图 / Breusch-Pagan 检验", "p>0.05", "稳健标准误或加权最小二乘"),
    (["完全分离"], "交叉表与参数估计检查", "无空单元格或极大标准误", "合并类别、惩罚似然"),
    (["事件"], "每自变量事件数（EPV）", "EPV≥10", "减少自变量或扩大样本"),
    (["K 值", "聚类"], "肘部法则、轮廓系数", "轮廓系数>0.5 且群规模合理", "调整 K 或改用层次聚类"),
    (["载荷"], "旋转后因子载荷", "载荷>0.5 且无明显交叉载荷", "删除题项或重新设定维度"),
    (["一致性", "CR"], "AHP 一致性检验", "CR<0.1", "重新构造判断矩阵"),
    (["拟合"], "χ²/df、CFI、TLI、RMSEA、SRMR", "χ²/df<3；CFI/TLI>0.9；RMSEA<0.08；SRMR<0.08", "修正模型（须有理论依据）"),
    (["训练", "测试"], "训练/测试集划分", "70/30 或 80/20；固定随机种子", "重新划分或交叉验证"),
    (["随机种子"], "随机种子与版本记录", "结果可复现", "固定种子并保存脚本"),
    (["缺失值"], "缺失率统计、缺失机制与插补前后对比", "关键变量缺失率<5%；插补后结论方向不变", "删除、插补或做敏感性分析"),
    (["至少 3 个题项", "题项数不少于 5", "题项数"], "题项数与维度设计核对", "每维度≥3 题；总量表题项数符合模型要求", "补题、合并维度或改用单题指标"),
    (["题项间存在正向相关"], "相关矩阵与项目—总分相关", "同维度题项 r>0.3 且方向一致", "删题或重新设计量表"),
    (["样本来自目标总体"], "甄别题通过率与样本结构核对", "甄别题通过率≥95%，结构可解释", "补样或加权"),
    (["分词", "停用词"], "抽样检查分词结果与停用词表", "专业词、品牌名切分正确；停用词无过度删除", "补充自定义词典与停用词表"),
    (["去重", "去广告", "无效文本"], "规则去重 + 人工抽查", "重复/广告文本清除率≥95%，抽样复核一致", "调整规则并重新清洗"),
    (["分类互斥且穷尽"], "编码表审查与频数检查", "每个样本恰好落入一个类别，无未定义值", "补充类别或重新编码"),
    (["阈值设定合理"], "人工标注样本与情感得分对比", "与人工判断一致率≥80%", "调整阈值或改用监督模型"),
    (["结果仅表征区分度"], "解释口径审查", "不把 TF-IDF 权重解释为重要性或因果", "在报告中限定解释范围"),
    (["比较组样本量"], "比较组样本量与结构核对", "每组≥30，组间样本比不超过 2:1", "补样、合并组或改用加权"),
    (["人工抽样复核", "人工编码"], "分层抽样人工标注并计算一致率", "一致率≥85%，Kappa≥0.7", "扩大人工标注或调整模型阈值"),
    (["每个待估参数"], "待估参数数与有效样本比值核对", "每个参数对应≥10 个样本", "简化模型或补样"),
    (["样本量宜", "样本量≥", "题项数的 5", "每自变量事件"], "有效样本与模型参数/题项数核对", "达到模型最低样本与 EPV/题项比要求", "补样、减少参数或降级模型"),
    (["测量模型"], "Cronbach's α、KMO/Bartlett、验证性因子分析", "α≥0.7；KMO>0.7；CFA 拟合可接受", "删题、合并维度或改用总分"),
    (["理论模型"], "文献依据与路径图审查", "每条路径有理论或文献支持", "删去无依据路径，改为探索性分析"),
    (["分类变量编码", "多选题", "行列维度"], "数据字典、响应集定义与列联表规模检查", "编码互斥穷尽；响应集正确；维度≤5×5", "重新编码、合并类别或拆分表"),
    (["语料", "文本"], "语料规模与人工复核", "有效语料≥100 条（LDA 建议≥500）；复核一致率≥85%", "扩大语料或改用人工编码"),
]

REFERENCES = {
    "descriptive": "NIST/SEMATECH. e-Handbook of Statistical Methods: Measures of Location and Scale.",
    "likert": "Likert, R. A technique for the measurement of attitudes. Archives of Psychology, 1932.",
    "cronbach": "Cronbach, L. J. Coefficient alpha and the internal structure of tests. Psychometrika, 1951.",
    "sample_size": "Cochran, W. G. Sampling Techniques (3rd ed.). Wiley, 1977.",
    "chi_square": "OpenStax. Introductory Statistics: The Chi-Square Distribution, 2023.",
    "crosstab": "Penn State STAT 504: Analysis of Discrete Data.",
    "anova": "OpenStax. Introductory Statistics: F Distribution and One-Way ANOVA, 2023.",
    "kmo_bartlett": "Kaiser, H. F. An index of factorial simplicity. Psychometrika, 1974.",
    "cluster": "MacQueen, J. Some methods for classification and analysis of multivariate observations, 1967.",
    "linear_regression": "NIST/SEMATECH. e-Handbook of Statistical Methods: Multiple Linear Regression.",
    "logistic_regression": "Penn State STAT 504: Analysis of Discrete Data.",
    "servperf": "Cronin, J. J., Taylor, S. A. Measuring service quality: a reexamination and extension. Journal of Marketing, 1992.",
    "ipa": "Martilla, J. A., James, J. C. Importance-performance analysis. Journal of Marketing, 1977.",
    "web_crawler": "Python Software Foundation. urllib.request; Selenium Documentation.",
    "snownlp": "Pang, B., Lee, L., Vaithyanathan, S. Thumbs up? Sentiment classification using machine learning techniques, 2002.",
    "tfidf": "Salton, G., Buckley, C. Term-weighting approaches in automatic text retrieval. IPM, 1988.",
    "association_rules": "Agrawal, R., Srikant, R. Fast algorithms for mining association rules, 1994.",
    "random_forest": "Breiman, L. Random forests. Machine Learning, 2001.",
    "multistage_pps": "Penn State STAT 506: Sampling Theory and Methods.",
    "pca_factor": "Hair, J. F., et al. Multivariate Data Analysis (8th ed.). Cengage, 2019.",
    "ahp": "Saaty, T. L. How to make a decision: the analytic hierarchy process. EJOR, 1990.",
    "fuzzy_evaluation": "Zadeh, L. A. Fuzzy sets. Information and Control, 1965.",
    "sem": "Fornell, C., Larcker, D. F. Evaluating structural equation models with unobservable variables and measurement error. JMR, 1981.",
    "lda": "Blei, D. M., Ng, A. Y., Jordan, M. I. Latent Dirichlet allocation. JMLR, 2003.",
    "elastic_net": "Friedman, J., Hastie, T., Tibshirani, R. Regularization paths for generalized linear models via coordinate descent. JSS, 2010.",
    "lightgbm": "Ke, G., et al. LightGBM: a highly efficient gradient boosting decision tree. NeurIPS, 2017.",
    "bayesian_network": "Pearl, J. Probabilistic Reasoning in Intelligent Systems. Morgan Kaufmann, 1988.",
    "pest": "Kotler, P., Keller, K. L. Marketing Management (15th ed.). Pearson, 2016.",
    "swot": "Weihrich, H. The TOWS matrix—a tool for situational analysis. Long Range Planning, 1982.",
    "stp": "Wedel, M., Kamakura, W. A. Market Segmentation (2nd ed.). Springer, 2000.",
    "four_p": "OpenStax. Principles of Marketing, 2023.",
    "aisas": "Kotler, P., Keller, K. L. Marketing Management (15th ed.). Pearson, 2016.",
    "sheth_newman_gross": "Sheth, J. N., Newman, B. I., Gross, B. L. Why we buy what we buy. JBR, 1991.",
    "baidu_index": "百度在线网络技术(北京)有限公司. 百度指数.",
    "word_frequency": "Manning, C. D., Raghavan, P., Schütze, H. Introduction to Information Retrieval. CUP, 2008.",
}


def _heading(text: str, level: int = 2) -> str:
    return f"{'#' * level} {text}"


def _para(text: str) -> str:
    return (text or "").strip()


def _bullets(items) -> str:
    return "\n".join(f"- {i}" for i in items if str(i).strip())


def _model_rqs(model: Model, analysis: VariableAnalysis) -> list[str]:
    """只返回该方法真正服务的研究问题，而不是所有共享一个宽泛标签的问题。"""
    out = []
    for item in analysis.rq_map:
        types = set(item.get("types", []))
        if model.id in TEXT_MODELS:
            if "text" in types:
                out.append(item["qid"])
        elif model.id in MEASUREMENT_MODELS:
            continue
        elif model.id in {"sample_size", "multistage_pps"}:
            continue
        elif model.id == "descriptive":
            if types & {"descriptive", "group_difference"}:
                out.append(item["qid"])
        elif model.id in MODEL_RQ_TYPES:
            if types & MODEL_RQ_TYPES[model.id]:
                out.append(item["qid"])
        elif model.id in CAUSAL_MODELS:
            if types & {"driver", "group_difference", "association", "mediation", "moderation", "binary_outcome", "evaluation"}:
                out.append(item["qid"])
        elif types & set(MODEL_QUESTION_MAP.get(model.id, [])):
            out.append(item["qid"])
    return unique_keep_order(out)


def _model_vars(model: Model, analysis: VariableAnalysis, rec: Recommendation) -> list[str]:
    if model.id in {"sample_size", "multistage_pps"}:
        return []
    if model.id in {"word_frequency", "tfidf", "snownlp", "lda", "web_crawler"}:
        return ["公开评论文本 / 开放题"]
    if model.id in {"likert", "cronbach", "kmo_bartlett", "pca_factor"}:
        return [c.name for c in analysis.constructs if "李克特" in c.scale or "量表" in c.scale]
    if model.id == "descriptive":
        return [c.name for c in analysis.constructs if c.role not in {"control", "screening"}]
    rqs = _model_rqs(model, analysis)
    names = []
    for item in analysis.rq_map:
        if item["qid"] in rqs:
            names.extend(item.get("iv", []) + item.get("dv", []) + item.get("mediator", []))
            if model.id == "sem":
                names.extend(item.get("moderator", []))
    if not names:
        names = analysis.names_by_role("dependent")[:1] + analysis.names_by_role("independent")[:3]
    return unique_keep_order(names)[: 8 if model.id == "sem" else 6]


def _hypothesis_rows(hypotheses: list[Hypothesis]) -> list[list[str]]:
    rows = []
    for h in hypotheses:
        rows.append(
            [
                h.hid,
                h.text,
                {
                    "difference": "差异",
                    "association": "相关",
                    "impact": "影响",
                    "mediation": "中介",
                    "moderation": "调节",
                    "descriptive": "描述",
                }.get(h.kind, h.kind),
                h.rq_id or "—",
                "、".join(h.iv) or "—",
                "、".join(h.dv) or "—",
                "、".join(h.mediator) or "—",
                h.direction,
                h.method,
            ]
        )
    return rows


def _concept_framework(analysis: VariableAnalysis) -> str:
    core_names = {c.name for c in analysis.constructs if c.role not in {"control", "screening"}}
    ids: dict[str, str] = {}
    nodes: list[str] = []

    def node(name: str) -> str:
        if name not in ids:
            ids[name] = f"V{len(ids) + 1}"
            nodes.append(f'  {ids[name]}["{name}"]')
        return ids[name]

    edges: list[str] = []
    seen: set[tuple[str, str, str]] = set()

    def edge(a: str, b: str, style: str = "-->") -> None:
        if a not in core_names or b not in core_names:
            return
        key = (a, b, style)
        if key in seen:
            return
        seen.add(key)
        edges.append(f"  {node(a)} {style} {node(b)}")

    for item in analysis.rq_map:
        types = set(item.get("types", []))
        dvs = [x for x in item.get("dv", []) if x in core_names]
        ivs = [x for x in item.get("iv", []) if x in core_names]
        meds = [x for x in item.get("mediator", []) if x in core_names]
        mods = [x for x in item.get("moderator", []) if x in core_names]
        # 纯群体差异问题画“分组比较”虚线，避免把分组变量误读为因果前因。
        if "group_difference" in types and not (types & {"driver", "mediation", "moderation"}):
            for dv in dvs:
                for iv in ivs:
                    edge(iv, dv, "-. 分组比较 .->")
            continue
        main_ivs = [x for x in ivs if x not in mods]
        for dv in dvs:
            for iv in main_ivs:
                edge(iv, dv)
            for med in meds:
                for iv in main_ivs:
                    edge(iv, med)
                edge(med, dv)
            for mod in mods:
                if main_ivs:
                    edge(mod, main_ivs[0], "-.->")
                elif not ivs:
                    edge(mod, dv, "-.->")

    # 保证所有核心构念都有节点，即使某个 RQ 没有形成边
    for name in core_names:
        node(name)

    lines = ["```mermaid", "flowchart LR"]
    lines.extend(edges)
    lines.extend(nodes)
    lines.append("```")
    return "\n".join(lines)


def _assumption_test(assumption: str) -> tuple[str, str, str]:
    for keys, test, threshold, action in ASSUMPTION_TEST:
        if any(k in assumption for k in keys):
            return test, threshold, action
    return "结合研究设计逐项说明", "按方法教材与数据分布判断", "在报告中说明局限"


def _model_detail(index: int, m: Model, rec: Recommendation, analysis: VariableAnalysis) -> str:
    rationale = rec.rationales.get(m.id, "与当前研究问题、变量类型或数据结构相匹配。")
    rqs = _model_rqs(m, analysis)
    vars_ = _model_vars(m, analysis, rec)
    out = [
        f"#### 5.4.{index} {m.name}（{m.level}｜{m.category}）",
        "",
        f"**在本题中的定位**：{rationale}",
        "",
    ]
    if rqs:
        out.append(f"**对应研究问题**：{'、'.join(rqs)}")
    elif m.id in {"sample_size", "multistage_pps"}:
        out.append("**对应研究问题**：覆盖全卷抽样与样本量论证（不绑定单一 RQ）")
    if vars_:
        out.append(f"**涉及变量**：{'、'.join(vars_)}")
    out.extend(
        [
            "",
            "**核心公式**：",
            "",
            "```text",
            m.formula,
            "```",
            "",
            "**适用条件**：",
            "",
            _bullets(m.assumptions),
            "",
            f"**所需数据**：{m.inputs}",
            "",
            f"**主要输出**：{m.outputs}",
            "",
            f"**报告口径**：{m.report}",
            "",
            f"**常见错误**：{m.pitfalls}",
            "",
        ]
    )
    if m.fallback:
        out.append(f"**备选/降级方案**：{m.fallback}")
    else:
        out.append("**备选/降级方案**：无；若前提不满足，需在报告中说明并改用更稳健的替代方法。")
    out.append("")
    return "\n".join(out)


def _model_assumption_rows(core: list[Model]) -> list[list[str]]:
    rows = []
    for m in core:
        for a in m.assumptions:
            test, threshold, action = _assumption_test(a)
            rows.append([m.name, a, test, threshold, action])
    return rows


def _rq_models(item: dict, analysis: VariableAnalysis, rec: Recommendation) -> list[Model]:
    """在与 RQ 类型匹配的基础上，再用该 RQ 的实际变量过滤掉不相关方法。"""
    core_by_id = {m.id: m for m in rec.core}
    ids = [mid for mid in rec.per_rq.get(item["qid"], []) if mid in core_by_id]
    models = [core_by_id[mid] for mid in ids]
    var_names = item.get("iv", []) + item.get("dv", []) + item.get("mediator", []) + item.get("moderator", [])
    constructs = [c for c in analysis.constructs if c.name in var_names]
    has_likert = any("李克特" in c.scale or "量表" in c.scale for c in constructs)
    has_text = "text" in item.get("types", []) or any("文本" in c.measure for c in constructs)
    has_iv = bool(item.get("iv"))
    filtered = []
    for m in models:
        if m.id in MEASUREMENT_MODELS and not has_likert:
            continue
        if m.id in TEXT_MODELS and not has_text:
            continue
        if m.id in CAUSAL_MODELS and not has_iv:
            continue
        # 组间比较类方法只服务差异/关联问题，避免被“影响因素”问题顺手带出
        if m.id in {"anova", "chi_square", "crosstab"} and not (
            set(item.get("types", [])) & {"group_difference", "association"}
        ):
            continue
        filtered.append(m)
    return filtered or models[:2]


def _model_choice_rows(analysis: VariableAnalysis, rec: Recommendation) -> list[list[str]]:
    rows = []
    for item in analysis.rq_map:
        types = [label_for_type(t) for t in item.get("types", [])]
        rq_models = _rq_models(item, analysis, rec)
        if not rq_models:
            rq_models = rec.core[:3]
        names = "、".join(m.name for m in rq_models[:4])
        fallback = "；".join(m.fallback for m in rq_models[:2] if m.fallback) or "按前提检验结果调整"
        rows.append(
            [
                item["qid"],
                item["text"],
                "、".join(types) or "综合",
                "、".join(item.get("iv", [])) or "—",
                "、".join(item.get("dv", [])) or "—",
                names,
                fallback,
            ]
        )
    return rows


def _variable_model_rows(analysis: VariableAnalysis, rec: Recommendation) -> list[list[str]]:
    rows = []
    core_by_id = {m.id: m for m in rec.core}
    for c in analysis.constructs:
        if c.role == "control":
            rows.append([c.name, ROLE_CN.get(c.role, c.role), "作为控制变量进入回归/Logistic 模型"])
            continue
        if c.role == "screening":
            rows.append([c.name, ROLE_CN.get(c.role, c.role), "样本甄别与质控"])
            continue
        names: list[str] = []
        for item in analysis.rq_map:
            vars_ = item.get("iv", []) + item.get("dv", []) + item.get("mediator", []) + item.get("moderator", [])
            if c.name in vars_:
                names.extend(m.name for m in _rq_models(item, analysis, rec) if m.id not in {"sample_size", "multistage_pps"})
        names = unique_keep_order(names)
        if not names:
            if c.role == "dependent":
                names = [m.name for m in rec.core if any(k in m.name for k in ["描述", "方差", "回归", "SEM", "结构方程"])]
            elif c.role == "independent":
                names = [m.name for m in rec.core if any(k in m.name for k in ["回归", "方差", "卡方", "交叉", "SEM", "结构方程"])]
            elif c.role == "mediator":
                names = [m.name for m in rec.core if any(k in m.name for k in ["SEM", "结构方程", "回归"])]
            elif c.role == "moderator":
                names = [m.name for m in rec.core if any(k in m.name for k in ["回归", "SEM", "结构方程"])]
        rows.append([c.name, ROLE_CN.get(c.role, c.role), "、".join(names[:5]) or "描述统计"])
    return rows


def _progress_plan(weeks: int | None) -> list[list[str]]:
    weeks = max(4, weeks or 6)
    phases = [
        (0.15, "选题、文献与问卷设计", "研究框架、问卷初稿、变量字典"),
        (0.15, "预调研与问卷修订", "预调研报告、正式问卷"),
        (0.35, "正式调研与配额监控", "原始数据、回收日报"),
        (0.10, "数据清洗与质量核查", "清洗后数据集、清洗日志"),
        (0.15, "统计分析与建模", "分析结果、图表、模型输出"),
        (0.10, "报告撰写与答辩准备", "数据需求终稿、分析报告"),
    ]
    total = sum(p[0] for p in phases)
    raw = [weeks * p[0] / total for p in phases]
    base = [max(1, int(round(x))) for x in raw]
    # 调整到总周数
    while sum(base) > weeks:
        i = base.index(max(base))
        base[i] -= 1
    while sum(base) < weeks:
        i = base.index(min(base))
        base[i] += 1
    rows = []
    start = 1
    for (share, task, output), n in zip(phases, base):
        end = start + n - 1
        span = f"第 {start} 周" if n == 1 else f"第 {start}—{end} 周"
        rows.append([span, task, output])
        start = end + 1
    return rows


def _quota_rows(analysis: VariableAnalysis, n_eff: int) -> list[list[str]]:
    rows = []
    for c in analysis.controls:
        if c.name in {"性别", "年龄", "学历", "年级", "月可支配收入", "月生活费", "地区", "所在地区"}:
            if c.name == "性别":
                cats = [("男", 0.5), ("女", 0.5)]
            elif c.name in {"年龄", "年级"}:
                cats = [("低年龄段/低年级", 0.25), ("中低年龄段/中低年级", 0.25), ("中高年龄段/高年级", 0.25), ("高年龄段/研究生及以上", 0.25)]
            elif c.name in {"学历", "月可支配收入", "月生活费"}:
                cats = [("低分组", 0.25), ("中低分组", 0.25), ("中高分组", 0.25), ("高分组", 0.25)]
            else:
                cats = [("核心区域", 0.6), ("外围区域", 0.4)]
            for cat, p in cats:
                rows.append([c.name, cat, f"{p:.0%}", fmt_num(max(30, int(round(n_eff * p))))])
    if not rows:
        rows = [
            ["性别", "男 / 女", "各 50%", fmt_num(max(30, n_eff // 2))],
            ["年龄", "按目标总体年龄结构分组", "以统计年鉴为准", "每组≥30"],
            ["地区", "按研究区域分层", "以目标总体分布为准", "每组≥30"],
        ]
    return rows


def _channel_rows(plan: ChannelPlan) -> list[list[str]]:
    rows = []
    for item in plan.allocation:
        ch = item["channel"]
        rows.append(
            [
                item["tier"],
                ch.name,
                ch.type,
                fmt_num(item["sample"]),
                f"{item['share']:.0%}",
                ch.coverage,
                ch.pros,
                ch.risks,
                ch.qc,
            ]
        )
    return rows


def _channel_qc_rows(plan: ChannelPlan) -> list[list[str]]:
    rows = []
    for ch in plan.survey_channels + plan.secondary_data:
        rows.append([ch.name, ch.risks, ch.qc, ch.compliance])
    return rows


def _qc_stage_rows(qc: QcPlan) -> list[list[str]]:
    rows = []
    for stage in qc.stages:
        measures = stage.get("measures", [])
        points = "；".join(m.get("point", "") for m in measures)
        rows.append([stage.get("stage", ""), stage.get("goal", ""), points, f"{len(measures)} 项"])
    if qc.extra_measures:
        rows.append(["专项质控", "针对本研究的调查方式/数据类型补充", "；".join(m.get("point", "") for m in qc.extra_measures), f"{len(qc.extra_measures)} 项"])
    return rows


def _qc_detail_rows(qc: QcPlan) -> list[list[str]]:
    rows = []
    for stage in qc.stages:
        for m in stage.get("measures", []):
            rows.append(
                [
                    stage.get("stage", ""),
                    m.get("point", ""),
                    m.get("measure", ""),
                    m.get("standard", ""),
                    m.get("record", ""),
                ]
            )
    for m in qc.extra_measures:
        rows.append(
            [
                m.get("stage", "专项"),
                m.get("point", ""),
                m.get("measure", ""),
                m.get("standard", ""),
                m.get("record", ""),
            ]
        )
    return rows


def _qc_checklist_rows(qc: QcPlan) -> list[list[str]]:
    owner_map = {
        "设计阶段": "问卷设计负责人",
        "抽样阶段": "项目负责人",
        "执行阶段": "数据采集负责人",
        "清洗阶段": "数据分析负责人",
        "分析阶段": "数据分析负责人",
        "交付阶段": "项目负责人",
        "合规": "全体成员",
        "专项": "对应模块负责人",
        "专项质控": "对应模块负责人",
    }
    timing_map = {
        "设计阶段": "正式调研前",
        "抽样阶段": "正式调研前",
        "执行阶段": "调研期间每日",
        "清洗阶段": "数据回收后 3 日内",
        "分析阶段": "分析开始前与结题前",
        "交付阶段": "交付前",
        "合规": "全流程",
        "专项": "对应阶段",
        "专项质控": "对应阶段",
    }
    rows = []
    for stage in qc.stages:
        for m in stage.get("measures", []):
            st = stage.get("stage", "")
            rows.append([st, m.get("point", ""), m.get("measure", ""), m.get("standard", ""), owner_map.get(st, "项目负责人"), timing_map.get(st, "对应阶段"), m.get("record", "")])
    for m in qc.extra_measures:
        st = m.get("stage", "专项")
        rows.append([st, m.get("point", ""), m.get("measure", ""), m.get("standard", ""), owner_map.get(st, "对应模块负责人"), timing_map.get(st, "对应阶段"), m.get("record", "")])
    return rows


def _data_overview_rows(brief: ResearchBrief, sample: SampleResult, analysis: VariableAnalysis) -> list[list[str]]:
    rows = []
    if brief.has_primary_survey():
        rows.append(
            [
                "一手问卷数据",
                "核心变量测量、假设检验、建模",
                "线上/线下问卷",
                f"计划发放 {fmt_num(sample.n_plan)} 份",
                "个体层面",
                "问卷星/渠道平台导出 Excel/CSV",
            ]
        )
    if brief.has_text_data():
        rows.append(
            [
                "公开文本/评论",
                "情感、主题、关键词、竞品对比",
                "平台公开评论、开放题",
                "有效文本≥100 条；LDA 建议≥500 条",
                "文本条目",
                "CSV（文本、时间、来源、评分等字段）",
            ]
        )
    if brief.has_secondary_data():
        rows.append(
            [
                "二手行业数据",
                "背景论证、市场容量、趋势与区域对比",
                "统计年鉴、行业报告、指数平台",
                "按研究需要",
                "行业/区域/年度",
                "来源清单 + 摘录表",
            ]
        )
    if any("访谈" in s or "定性" in s for s in brief.data_sources) or "访谈" in brief.text_blob():
        rows.append(
            [
                "定性资料",
                "探索动机、修正问卷、解释定量结果",
                "深度访谈/焦点小组",
                "8—12 人（或 3—5 组）",
                "个人/小组",
                "录音转写稿 + 编码表",
            ]
        )
    return rows


def _data_source_rows(brief: ResearchBrief, sample: SampleResult, plan: ChannelPlan) -> list[list[str]]:
    rows = []
    if brief.has_primary_survey():
        rows.append(
            [
                "一手问卷",
                "量表题、事实行为题、人口统计题",
                f"{fmt_num(sample.n_plan)} 份（目标有效 {fmt_num(sample.n_effective)} 份）",
                "、".join(c.name for c in (plan.primary + plan.secondary)[:3]) or "线上问卷平台",
                "调研期第 1—3 周",
            ]
        )
    for ch in plan.secondary_data[:4]:
        rows.append([ch.type, "、".join(ch.best_for[:4]) or ch.coverage, "按需", ch.name, "调研前 1—2 周"])
    has_text_source = any("文本" in c.type for c in plan.secondary_data)
    if brief.has_text_data() and not has_text_source:
        rows.append(["公开文本", "评论、帖子、开放题", "≥100 条（LDA≥500 条）", "电商/点评/社媒", "调研前 1—2 周"])
    return rows


def _risk_rows() -> list[list[str]]:
    return [
        ["样本量不足或有效回收率低", "中", "高", "提前预调研估算有效率；设置备用渠道；每日配额监控；必要时延长调研期"],
        ["渠道样本偏差", "高", "中", "多渠道组合；设置配额；报告样本结构并与总体对比；必要时加权"],
        ["问卷理解偏差", "中", "中", "认知访谈 + 预调研；修订歧义题项；保留开放题补充"],
        ["模型前提不满足", "中", "中", "分析前逐项检验；准备非参数/稳健方法作为降级方案"],
        ["多重比较导致假阳性", "中", "中", "预先设定核心假设；使用 Bonferroni/Tukey/FDR 校正"],
        ["数据合规与隐私风险", "低", "高", "知情同意、匿名化、最小化收集、加密存储、遵守平台协议"],
        ["进度延误", "中", "中", "倒排工期；关键路径前置；每周检查里程碑"],
        ["团队分工不清", "中", "中", "明确角色与交付物；使用共享文档与版本管理"],
    ]


def _assumption_rows(brief: ResearchBrief, sample: SampleResult) -> list[list[str]]:
    rows = [
        ["目标总体", brief.target_population, "输入文档"],
        ["调查单位", brief.survey_unit, "输入文档"],
        ["置信水平", fmt_pct(sample.confidence, 0), "输入文档/默认 95%"],
        ["允许误差", f"±{fmt_pct(sample.margin_error, 1)}", "输入文档/默认 5%"],
        ["预估比例", f"{sample.proportion:.2f}", "默认取 0.5（最保守）"],
        ["设计效应", f"{sample.design_effect:.2f}", "输入文档/默认 1.2"],
        ["预计有效率", fmt_pct(sample.response_rate, 0), "输入文档/默认 90%"],
        ["总体规模", fmt_num(sample.population_size) if sample.population_size else "未提供（未作有限总体修正）", "输入文档"],
        ["调查方式", brief.survey_mode, "输入文档/推断"],
        ["数据来源", "、".join(brief.data_sources), "输入文档/推断"],
    ]
    return rows


def _todo_rows(issues: list[ValidationIssue], warnings: list[str]) -> list[list[str]]:
    rows = []
    for issue in issues:
        rows.append([issue.level, issue.field, issue.message, "确认后补充到输入文档", "项目负责人"])
    for w in warnings:
        rows.append(["warning", "engine", w, "人工复核并在正式调研前确认", "项目负责人"])
    return rows


def _selected_models(rec: Recommendation) -> list[Model]:
    return rec.core + rec.optional


def render(
    brief: ResearchBrief,
    analysis: VariableAnalysis,
    rec: Recommendation,
    sample: SampleResult,
    strata_alloc: list[dict],
    requirements: list[ModelRequirement],
    plan: ChannelPlan,
    qc: QcPlan,
    hypotheses: list[Hypothesis],
    exploratory: list[dict],
    issues: list[ValidationIssue],
    rq_types: dict[str, list[str]],
) -> str:
    today = _dt.date.today().isoformat()
    lines: list[str] = []

    # 封面与文档信息 -----------------------------------------------------
    lines += [
        f"# 《{brief.project_name}》数据需求文档",
        "",
        f"> **项目名称**：{brief.project_name}  ",
        f"> **竞赛/课程**：{brief.competition}  ",
        f"> **研究类型**：{brief.research_type}  ",
        f"> **行业/区域**：{brief.industry}｜{brief.region}  ",
        f"> **目标总体**：{brief.target_population}  ",
        f"> **文档版本**：v1.0  ",
        f"> **生成日期**：{today}  ",
        f"> **生成方式**：data-requirement skill + 本地规则引擎  ",
        f"> **文档用途**：作为问卷设计、数据采集、清洗与统计建模的统一依据  ",
        "",
        "---",
        "",
        "## 0. 文档摘要",
        "",
        f"本文件面向《{brief.project_name}》的数据分析部分，回答“需要什么数据、如何取得、用什么方法分析”三个问题。"
        "文档中的变量、样本参数、模型方法与质控措施相互对应，可直接用于问卷定稿、调研执行和分析分工。",
        "",
    ]

    core_names = "、".join(m.name for m in rec.core)
    lines += [
        f"- **研究主题**：{brief.project_name}",
        f"- **核心研究问题**：{len(brief.research_questions)} 个，见 1.2；其中可转化为统计假设的 {len(hypotheses)} 条",
        f"- **变量体系**：{len(analysis.constructs)} 个变量（含控制与筛选变量），核心构念 {len([c for c in analysis.constructs if c.role not in {'control','screening'}])} 个",
        f"- **样本方案**：目标有效样本 **{fmt_num(sample.n_effective)}** 份，计划发放 **{fmt_num(sample.n_plan)}** 份",
        f"- **核心方法**：{core_names}",
        f"- **主要渠道**：{'、'.join(c.name for c in plan.primary + plan.secondary) or '待确认'}",
        f"- **质量控制**：覆盖设计、抽样、执行、清洗、分析、交付 6 个阶段，共 {sum(len(s.get('measures', [])) for s in qc.stages) + len(qc.extra_measures)} 项控制点",
        f"- **数据交付**：原始数据、清洗数据、变量字典、清洗日志、分析脚本",
        "",
    ]
    if issues:
        lines += [
            f"> ⚠️ 文档生成时发现 {len(issues)} 项待确认事项，已在第 10 章列出。正式调研前应逐项确认。",
            "",
        ]
    lines += ["---", ""]

    # 1. 研究概述 --------------------------------------------------------
    lines += [_heading("1. 研究概述"), ""]
    lines += [_heading("1.1 研究背景", 3), ""]
    lines += [_para(brief.background) or "（输入文档未提供研究背景，请在正式报告中补充行业背景、选题依据与研究意义。）", ""]

    lines += [_heading("1.2 研究问题", 3), ""]
    rq_rows = []
    for q in brief.research_questions:
        types = rq_types.get(q.qid, [])
        rq_rows.append([q.qid, q.text, "、".join(label_for_type(t) for t in types) or "综合", q.source])
    lines += [md_table(["编号", "研究问题", "问题类型", "来源"], rq_rows), ""]

    lines += [_heading("1.3 研究目标", 3), ""]
    lines += [_bullets(brief.objectives) or "- （未单独列出研究目标，以上述研究问题为准。）", ""]

    lines += [_heading("1.4 研究范围与调查单位", 3), ""]
    lines += [
        md_table(
            ["项目", "内容"],
            [
                ["目标总体", brief.target_population],
                ["调查单位", brief.survey_unit],
                ["研究区域", brief.region],
                ["所属行业", brief.industry],
                ["研究类型", brief.research_type],
                ["数据来源", "、".join(brief.data_sources)],
                ["调查方式", brief.survey_mode],
                ["约束条件", "；".join(c.rstrip("。；; ") for c in brief.constraints) or "未填写"],
            ],
        ),
        "",
    ]

    lines += [_heading("1.5 概念框架", 3), ""]
    lines += [
        "下图给出变量之间的核心关系。实线表示影响路径，虚线表示调节或分组比较；中介路径与具体系数将在第 5 章对应模型中检验。",
        "",
        _concept_framework(analysis),
        "",
    ]
    concept_rows = []
    for c in analysis.constructs:
        if c.role in {"dependent", "independent", "mediator", "moderator"}:
            concept_rows.append([c.name, ROLE_CN.get(c.role, c.role), c.definition or "—"])
    lines += [md_table(["构念", "角色", "操作化定义"], concept_rows), ""]

    lines += [_heading("1.6 数据需求总览", 3), ""]
    lines += [
        md_table(
            ["数据类型", "用途", "采集方式", "目标规模", "粒度", "交付格式"],
            _data_overview_rows(brief, sample, analysis),
        ),
        "",
    ]
    lines += ["---", ""]

    # 2. 研究假设 --------------------------------------------------------
    lines += [_heading("2. 研究假设"), ""]
    lines += [
        "假设是连接研究问题与统计模型的桥梁。以下假设均给出变量、预期方向与检验方法；"
        "正式报告中应同时报告原假设（H0）与备择假设（H1）的检验结果，而不能只挑选显著结果。",
        "",
    ]
    lines += [_heading("2.1 假设体系", 3), ""]
    if hypotheses:
        lines += [
            md_table(
                ["编号", "假设内容", "类型", "对应RQ", "自变量", "因变量", "中介/调节", "预期方向", "检验方法"],
                [
                    [
                        h.hid,
                        h.text,
                        {"difference": "差异", "association": "相关", "impact": "影响", "mediation": "中介", "moderation": "调节"}.get(h.kind, h.kind),
                        h.rq_id or "—",
                        "、".join(h.iv) or "—",
                        "、".join(h.dv) or "—",
                        "、".join((h.mediator if h.kind == "mediation" else []) + (h.moderator if h.kind == "moderation" else [])) or "—",
                        h.direction,
                        h.method,
                    ]
                    for h in hypotheses
                ],
            ),
            "",
        ]
    else:
        lines += ["当前输入未形成可检验假设；建议补充研究问题或在输入文档中直接给出假设。", ""]

    lines += [_heading("2.2 假设说明与检验口径", 3), ""]
    for h in hypotheses:
        lines += [
            f"**{h.hid}｜{h.text}**",
            "",
            f"- **理论依据**：{h.theory}",
            f"- **变量关系**：{'、'.join(h.iv) or '—'} → {'、'.join(h.dv) or '—'}"
            + (f"；中介：{'、'.join(h.mediator)}" if h.mediator else "")
            + (f"；调节：{'、'.join(h.moderator)}" if h.moderator else ""),
            f"- **检验方法**：{h.method}",
            f"- **判定标准**：p<0.05 视为统计显著；同时报告效应量（如 β、OR、η²、R²）与 95% 置信区间；"
            "若进行多组比较，需说明多重比较校正方法。",
            "- **结果表述**：显著时说明方向与强度；不显著时表述为“未发现显著证据”，不能直接认定为“没有影响”。",
            "",
        ]

    lines += [_heading("2.3 探索性问题", 3), ""]
    if exploratory:
        lines += [_bullets([f"{e['qid']}：{e['text']}（{e['reason']}）" for e in exploratory]), ""]
    else:
        lines += ["本研究问题均可转化为可检验假设；文本挖掘、聚类分群等探索性结果应在报告中单独标注为“探索性发现”。", ""]

    lines += ["---", ""]

    # 3. 变量确定 --------------------------------------------------------
    lines += [_heading("3. 变量确定"), ""]
    lines += [
        "变量设计遵循“理论驱动、单维可测、口径统一、可分析、可追溯”五项原则。"
        "每个变量都应能回答：测量什么、用什么题项、如何编码、进入哪个模型。",
        "",
    ]

    lines += [_heading("3.1 变量体系总览", 3), ""]
    role_rows = []
    for role in ["dependent", "independent", "mediator", "moderator", "control", "screening", "exploratory"]:
        cs = [c for c in analysis.constructs if c.role == role]
        if cs:
            role_rows.append([ROLE_CN.get(role, role), "、".join(c.name for c in cs), str(len(cs)), ROLE_PURPOSE.get(role, "")])
    lines += [md_table(["变量角色", "变量", "数量", "在模型中的作用"], role_rows), ""]

    lines += [_heading("3.2 因变量", 3), ""]
    dvs = analysis.dependent
    if dvs:
        lines += [
            md_table(
                ["变量", "操作化定义", "测量层级", "题项数", "量表", "数据来源"],
                [[c.name, c.definition or "—", c.measure, str(c.items), c.scale, c.source] for c in dvs],
            ),
            "",
            "因变量是全部假设的落点。若因变量为二分类（如“是否购买”），应使用 Logistic 回归；"
            "若为连续/近似连续变量（如满意度均值），使用线性回归或方差分析。",
            "",
        ]
    else:
        lines += ["当前未识别出因变量，请补充核心结果变量（如购买意愿、满意度、使用意愿）。", ""]

    lines += [_heading("3.3 自变量", 3), ""]
    ivs = analysis.independent
    if ivs:
        lines += [
            md_table(
                ["变量", "操作化定义", "测量层级", "题项数", "量表", "数据来源"],
                [[c.name, c.definition or "—", c.measure, str(c.items), c.scale, c.source] for c in ivs],
            ),
            "",
        ]
    else:
        lines += ["当前未识别出自变量，请补充核心影响因素。", ""]

    lines += [_heading("3.4 中介与调节变量", 3), ""]
    meds = analysis.mediators
    mods = analysis.moderators
    if meds or mods:
        rows = []
        for c in meds:
            rows.append([c.name, "中介变量", c.definition or "—", c.measure, str(c.items), c.scale])
        for c in mods:
            rows.append([c.name, "调节变量", c.definition or "—", c.measure, str(c.items), c.scale])
        lines += [md_table(["变量", "角色", "操作化定义", "测量层级", "题项数", "量表"], rows), ""]
        lines += [
            "中介变量用于回答“为什么/如何影响”，调节变量用于回答“在什么条件下影响更强/更弱”。"
            "若样本量不足 200，建议优先使用回归 + Bootstrap 中介检验，而非 SEM。",
            "",
        ]
    else:
        lines += [
            "当前研究问题未明确中介或调节变量。若后续引入，应满足：",
            "",
            "- **中介**：自变量 → 中介变量 → 因变量 的路径有理论依据；中介变量与因变量在概念上可区分。",
            "- **调节**：调节变量应为情境/群体/个体特征，且与自变量交互有理论依据；交互项需中心化处理。",
            "",
        ]

    lines += [_heading("3.5 控制变量", 3), ""]
    ctrls = analysis.controls
    if ctrls:
        lines += [
            md_table(
                ["变量", "操作化定义", "测量层级", "题项数", "说明"],
                [[c.name, c.definition or "—", c.measure, str(c.items), "进入回归/Logistic 作为控制变量"] for c in ctrls],
            ),
            "",
        ]
    else:
        lines += ["未设置控制变量；建议至少纳入性别、年龄、学历/年级、收入/生活费与地区。", ""]

    lines += [_heading("3.6 筛选与质控变量", 3), ""]
    scs = analysis.screening
    if scs:
        lines += [
            md_table(
                ["变量", "用途", "题项数", "处理规则"],
                [[c.name, c.definition or "—", str(c.items), "不通过则终止问卷或剔除样本"] for c in scs],
            ),
            "",
        ]
    lines += [
        "此外，数据集中应保留以下质控字段（不计入分析变量）：",
        "",
        "- `QC_DURATION`：全卷作答时长（秒）",
        "- `QC_IP` / `QC_DEVICE`：IP 与设备标识（脱敏后哈希存储）",
        "- `QC_SOURCE`：渠道来源参数",
        "- `QC_ATTENTION`：注意力检测题是否通过",
        "- `QC_FLAG`：人工复核标记",
        "",
    ]

    lines += [_heading("3.7 变量字典", 3), ""]
    lines += [
        "变量字典是数据采集、清洗与建模的共同语言。字段命名统一使用英文大写缩写 + 序号，"
        "中文名称仅用于报告呈现。",
        "",
        md_table(
            ["变量代码", "变量名称", "角色", "操作化定义", "测量层级", "题项数", "量表/取值", "数据来源", "对应RQ"],
            [
                [
                    r.code,
                    r.name,
                    r.role_cn,
                    r.definition,
                    r.measure,
                    str(r.items),
                    f"{r.scale}；{r.values}",
                    r.source,
                    r.rq or "—",
                ]
                for r in analysis.dictionary
            ],
        ),
        "",
    ]

    lines += [_heading("3.8 量表与题项设计", 3), ""]
    likert_constructs = [c for c in analysis.constructs if "李克特" in c.scale or "量表" in c.scale]
    if likert_constructs:
        lines += [
            md_table(
                ["构念", "题项数", "量表", "反向题", "题项设计要点"],
                [
                    [
                        c.name,
                        str(c.items),
                        c.scale,
                        "1 题（建议）" if c.items >= 4 else "—",
                        "围绕同一维度撰写；避免双重问题、诱导性表述与双重否定；至少 1 题反向表述",
                    ]
                    for c in likert_constructs
                ],
            ),
            "",
            "**计分规则**：正向题按 1—5 计分；反向题在分析前转换为 `x' = 6 − x`（5 级量表）。"
            "维度得分取题项均值；若题项缺失超过 30%，该样本该维度得分记为缺失。",
            "",
        ]
    else:
        lines += ["当前未识别出量表题项；若使用量表，请按 3—5 题/构念设计并设置反向题。", ""]

    lines += [_heading("3.9 问卷结构与题项编码", 3), ""]
    construct_by_name = {c.name: c for c in analysis.constructs}

    def _q_meta(name: str) -> tuple[str, str]:
        if "注意力" in name:
            return "质控题", "注意力检测"
        c = construct_by_name.get(name)
        if c is None:
            return "事实题", "变量测量"
        if c.role == "screening":
            return "甄别题", "样本甄别"
        if c.role == "control":
            return "人口统计题", "控制变量"
        if "李克特" in c.scale or "量表" in c.scale:
            return "量表题", "变量测量"
        return "事实题", "变量测量"

    # 按构念汇总题项范围
    q_rows = []
    current = None
    start = end = None
    for item in analysis.questionnaire:
        if item.construct != current:
            if current is not None:
                qtype, purpose = _q_meta(current)
                q_rows.append([current, f"{start}—{end}" if start != end else start, qtype, purpose])
            current = item.construct
            start = item.code
        end = item.code
    if current is not None:
        qtype, purpose = _q_meta(current)
        q_rows.append([current, f"{start}—{end}" if start != end else start, qtype, purpose])
    lines += [
        md_table(["问卷部分/构念", "题项编号", "题型", "用途"], q_rows),
        "",
        f"问卷总题项约 **{len(analysis.questionnaire)}** 题。建议将甄别题与知情同意置于最前，"
        "核心量表居中，人口统计与开放题置于最后，以减少中途退出。",
        "",
    ]

    lines += [_heading("3.10 变量与模型对应关系", 3), ""]
    lines += [
        md_table(
            ["变量", "角色", "主要进入的模型"],
            _variable_model_rows(analysis, rec),
        ),
        "",
    ]

    lines += ["---", ""]

    # 4. 样本与抽样 ------------------------------------------------------
    lines += [_heading("4. 样本与抽样设计"), ""]
    lines += [_heading("4.1 目标总体与抽样框", 3), ""]
    lines += [
        f"- **目标总体**：{brief.target_population}",
        f"- **调查单位**：{brief.survey_unit}",
        f"- **研究区域**：{brief.region}",
        f"- **抽样框**：{'以目标总体的名单、区域人口统计或平台用户库为抽样框；若无法获得完整名单，采用配额抽样并说明局限性。' if brief.region != '全国' else '以全国/区域人口统计或平台用户库为抽样框；若无完整名单，采用多阶段或配额抽样并说明局限性。'}",
        "",
    ]

    lines += [_heading("4.2 抽样方法", 3), ""]
    sampling_text = (
        "本研究以一手问卷调查为主，建议采用**线上便利抽样 + 关键配额控制**的组合："
        "通过问卷平台与社交渠道触达目标人群，同时按性别、年龄/年级、地区设置配额，降低渠道同质性带来的偏差。"
        "若总体名单可得，优先采用简单随机抽样或分层随机抽样；若需覆盖较大区域且无完整名单，可采用多阶段抽样，"
        "并在报告中说明各阶段抽样单位与设计效应。"
    )
    if not brief.has_primary_survey():
        sampling_text = "本研究以二手数据/文本数据为主，不涉及问卷抽样；如补充一手问卷，应按本节方法单独设计抽样方案。"
    lines += [sampling_text, ""]
    lines += [
        "**方法选择说明**：",
        "",
        "- 简单随机抽样：适用于有完整名单、总体规模适中的情形，样本量按 4.3 公式计算。",
        "- 分层随机抽样：按性别、年龄、地区等分层，可提高估计精度；需报告各层样本量与权重。",
        "- 多阶段/PPS 抽样：适用于总体大、无完整名单的实地调查；阶段数宜控制在 2—3 个。",
        "- 便利/配额抽样：本科生最常用，但外推能力有限；必须在报告中说明“样本代表性边界”。",
        "",
    ]

    lines += [_heading("4.3 样本量测算", 3), ""]
    lines += [
        "样本量按简单随机抽样公式测算，并考虑有限总体修正、设计效应与预计有效率：",
        "",
        "```text",
        "n0 = z² · P(1 − P) / d²",
        "n0' = n0 / [1 + (n0 − 1) / N]        （总体较小时）",
        "n_eff = n0' × deff",
        "n_plan = n_eff / r",
        "```",
        "",
        "式中：z 为置信水平对应的标准正态分位数；P 为预估比例；d 为允许误差；N 为总体规模；"
        "deff 为设计效应；r 为预计有效率；n_eff 为所需有效样本；n_plan 为计划发放量。",
        "",
        md_table(
            ["参数", "取值", "说明/依据"],
            [
                ["置信水平", f"{fmt_pct(sample.confidence, 0)}", f"对应 z = {sample.z:.3f}"],
                ["允许误差", f"±{fmt_pct(sample.margin_error, 1)}", "研究精度要求；越小所需样本越大"],
                ["预估比例 P", f"{sample.proportion:.2f}", "取 0.5 时方差最大，样本量最保守"],
                ["总体规模 N", fmt_num(sample.population_size) if sample.population_size else "未提供", "已用于有限总体修正" if sample.population_size else "未提供，按无限总体处理"],
                ["设计效应 deff", f"{sample.design_effect:.2f}", "分层/整群/多阶段抽样通常>1；便利抽样可按 1.0—1.5 估算"],
                ["预计有效率 r", fmt_pct(sample.response_rate, 0), "结合预调研或同类调查经验"],
            ],
        ),
        "",
        md_table(
            ["指标", "数值", "说明"],
            [
                ["基础样本量 n0", fmt_num(sample.n_base_rounded), "简单随机抽样、无设计效应"],
                ["有限总体修正后 n0'", fmt_num(sample.n_fpc) if sample.n_fpc else "未修正", f"总体规模 N={fmt_num(sample.population_size)}" if sample.population_size else "未提供总体规模"],
                ["所需有效样本 n_eff", fmt_num(sample.n_effective), "考虑设计效应后需要回收的有效问卷数"],
                ["计划发放量 n_plan", fmt_num(sample.n_plan), "按预计有效率折算，向上取整"],
                ["预计有效回收", fmt_num(sample.expected_valid), "计划发放量 × 有效率"],
            ],
        ),
        "",
        f"> **结论**：在 {fmt_pct(sample.confidence, 0)} 置信水平、允许误差 ±{fmt_pct(sample.margin_error, 1)} 下，"
        f"至少需要 **{fmt_num(sample.n_effective)}** 份有效问卷；按 {fmt_pct(sample.response_rate, 0)} 的有效率，"
        f"计划发放 **{fmt_num(sample.n_plan)}** 份。",
        "",
    ]

    lines += [_heading("4.4 敏感性分析", 3), ""]
    from .sample import sensitivity_table

    sens = sensitivity_table(
        [0.90, 0.95, 0.99],
        [0.03, 0.04, 0.05],
        sample.proportion,
        sample.population_size,
        sample.design_effect,
        sample.response_rate,
    )
    lines += [
        "下表展示不同置信水平与允许误差组合下的样本量变化，便于在精度、成本与周期之间权衡。",
        "",
        md_table(
            ["置信水平", "允许误差", "z 值", "基础样本量", "所需有效样本", "计划发放量"],
            [[fmt_pct(r["confidence"], 0), f"±{fmt_pct(r['margin_error'], 1)}", f"{r['z']:.3f}", fmt_num(r["n_base"]), fmt_num(r["n_effective"]), fmt_num(r["n_plan"])] for r in sens],
        ),
        "",
    ]

    lines += [_heading("4.5 分层与配额", 3), ""]
    if strata_alloc:
        lines += [
            "按输入的分层/配额方案分配有效样本：",
            "",
            md_table(
                ["分层", "权重", "目标有效样本", "总体规模"],
                [[r["name"], f"{r['weight']:.1%}", fmt_num(r["sample"]), fmt_num(r["population"]) if r["population"] else "—"] for r in strata_alloc],
            ),
            "",
        ]
    else:
        lines += [
            "输入未提供分层方案。建议至少按以下维度设置配额，具体比例以目标总体统计（如人口普查、统计年鉴）为准；"
            "若无法获得总体结构，采用接近均衡的配额并在报告中说明。",
            "",
            md_table(["配额维度", "类别", "建议比例", "最低样本"], _quota_rows(analysis, sample.n_effective)),
            "",
        ]

    lines += [_heading("4.6 样本量与模型要求校验", 3), ""]
    req_rows = []
    for r in requirements:
        req_rows.append(
            [
                r.model_name,
                fmt_num(r.min_sample) if r.min_sample else "不适用",
                fmt_num(sample.n_effective),
                "满足" if r.satisfied else ("不适用" if r.satisfied is None else "不满足"),
                r.basis,
            ]
        )
    lines += [
        "不同模型对样本量有不同要求。下表用于检查当前样本方案能否支撑第 5 章的方法组合；"
        "若不满足，应优先扩大样本，或改用表中“备选/降级方案”。",
        "",
        md_table(["模型", "建议最低样本", "当前有效样本", "是否满足", "依据"], req_rows),
        "",
    ]

    lines += [_heading("4.7 数据来源与采集规模", 3), ""]
    lines += [
        md_table(["数据类型", "内容", "目标规模", "采集渠道", "时间安排"], _data_source_rows(brief, sample, plan)),
        "",
    ]

    lines += ["---", ""]

    # 5. 模型与方法 ------------------------------------------------------
    lines += [_heading("5. 模型与方法确定（重点）"), ""]
    lines += [
        "模型选择遵循“问题—变量—前提—样本—解释”五步逻辑：先明确研究问题要回答什么，"
        "再判断变量类型与数据结构，随后检查模型前提与样本量，最后选择可解释、可复现、与本科生能力匹配的方法。"
        "本研究的总体原则是：**基础方法优先、进阶方法够用、高阶方法必须有明确问题支撑**。",
        "",
    ]

    lines += [_heading("5.1 方法选择逻辑", 3), ""]
    lines += [
        "1. **研究问题决定方法族**：描述现状用描述统计；比较群体用方差分析/卡方；解释影响因素用回归；"
        "分群用聚类；机制用中介检验；文本用词频/情感/主题模型。",
        "2. **变量类型决定具体模型**：因变量连续用线性回归，二分类用 Logistic 回归；"
        "自变量为分类变量时需设虚拟变量；多题项量表先做信效度检验。",
        "3. **前提条件决定能否使用**：正态性、方差齐性、共线性、期望频数、KMO、事件数等必须在分析前检验。",
        "4. **样本量决定模型上限**：样本不足时优先降级，而不是强行使用高阶模型。",
        "5. **解释成本决定最终选择**：能用一个简单模型说清楚的问题，不叠加复杂模型；"
        "每个模型都要能回答“它相对前一个模型增加了什么信息”。",
        "",
    ]

    lines += [_heading("5.2 方法路线图", 3), ""]
    route = [
        ("第 1 步", "数据清洗与编码", "剔除无效样本、处理缺失值与异常值、完成反向题转换与多选题编码", "清洗后数据集、清洗日志"),
        ("第 2 步", "描述统计与样本代表性", "样本结构、核心变量分布、渠道/地区对比", "描述统计表、样本结构图"),
        ("第 3 步", "信度与效度", "Cronbach's α、KMO/Bartlett、因子分析（如适用）", "信效度报告"),
        ("第 4 步", "假设检验", "卡方、方差分析、相关分析", "组间差异表、相关矩阵"),
        ("第 5 步", "核心模型", "线性回归/Logistic 回归/SEM/聚类等", "模型系数表、拟合指标"),
        ("第 6 步", "稳健性与补充分析", "替换变量、子样本、稳健标准误、文本/二手数据交叉验证", "稳健性附录"),
        ("第 7 步", "结论与策略转化", "STP、4P、IPA、SWOT 等框架", "策略建议"),
    ]
    lines += [
        md_table(["阶段", "任务", "主要工作", "交付物"], [list(r) for r in route]),
        "",
    ]

    lines += [_heading("5.3 研究问题—变量—模型对应", 3), ""]
    lines += [
        md_table(
            ["RQ", "研究问题", "问题类型", "自变量", "因变量", "推荐模型", "备选/降级"],
            _model_choice_rows(analysis, rec),
        ),
        "",
    ]

    lines += [_heading("5.4 核心模型详解", 3), ""]
    lines += [
        f"以下按“基础 → 进阶 → 高阶”顺序展开 **{len(rec.core)} 个核心模型**。"
        "每个模型均给出选择理由、公式、前提、输入输出、报告口径与常见错误，便于直接对照执行。",
        "",
    ]
    for i, m in enumerate(rec.core, 1):
        lines.append(_model_detail(i, m, rec, analysis))
    if rec.optional:
        lines += [
            _heading("5.4 补充：可选进阶模型", 4),
            "",
            "以下模型与本研究问题相关，但受样本量、理论复杂度或本科生可操作性限制，列为可选。"
            "只有在核心模型无法回答研究问题、且前提条件满足时，才建议纳入。",
            "",
            md_table(
                ["模型", "难度", "适用场景", "最低样本", "纳入建议"],
                [[m.name, m.level, "、".join(m.question_types[:3]), fmt_num(m.min_sample) if m.min_sample else "不适用", "作为稳健性/补充分析" if m.level != "高阶" else "谨慎使用，需有明确理论依据"] for m in rec.optional],
            ),
            "",
        ]

    lines += [_heading("5.5 模型前提检验清单", 3), ""]
    lines += [
        "下表把核心模型的前提条件转成可执行的检验动作。分析报告中应逐项交代检验结果，"
        "对不满足的前提说明处理方式，而不是直接忽略。",
        "",
        md_table(["模型", "前提条件", "检验方法", "判定标准", "不满足时的处理"], _model_assumption_rows(rec.core)),
        "",
    ]

    lines += [_heading("5.6 稳健性与备选方案", 3), ""]
    robust_rows = []
    for m in rec.core:
        robust_rows.append(
            [
                m.name,
                "替换变量口径/子样本/稳健标准误/更换估计方法后核心结论是否稳定",
                m.fallback or "报告局限，改用更保守的描述性结论",
            ]
        )
    lines += [
        md_table(["核心模型", "稳健性检验", "降级/备选方案"], robust_rows),
        "",
        "**稳健性检验的最低要求**：至少对核心假设做一次替代设定（如更换因变量口径、剔除异常值、"
        "分渠道/分群体重估），并报告核心系数方向与显著性是否改变。若改变，应在结论中明确说明边界条件。",
        "",
    ]

    lines += [_heading("5.7 软件与代码模块建议", 3), ""]
    lines += [
        md_table(
            ["任务", "推荐工具", "说明"],
            [
                ["数据清洗与变量生成", "Python(pandas) / Excel", "统一编码、反向题转换、缺失值标记"],
                ["描述统计与交叉表", "SPSS / Python(pandas, scipy)", "报告 N、均值、标准差、频数与百分比"],
                ["信度与效度", "SPSS / Python(pingouin, factor_analyzer)", "Cronbach's α、KMO、Bartlett、EFA"],
                ["回归与假设检验", "SPSS / Python(statsmodels, scipy)", "线性回归、Logistic、ANOVA、卡方"],
                ["结构方程/中介", "R(lavaan) / Python(semopy)", "样本≥200 时使用；报告完整拟合指标"],
                ["聚类与机器学习", "Python(scikit-learn)", "标准化、K 值选择、训练/测试划分"],
                ["文本分析", "Python(jieba, snownlp, scikit-learn, gensim)", "分词、情感、TF-IDF、LDA"],
                ["可视化", "Python(matplotlib/seaborn) / Excel", "统一配色与坐标轴标签；图表须可独立阅读"],
            ],
        ),
        "",
        "建议在项目 `engine/` 之外新建 `analysis/` 目录存放分析脚本，按“清洗—描述—检验—建模—可视化”拆分模块，"
        "所有随机过程固定种子，确保结果可复现。",
        "",
    ]

    lines += ["---", ""]

    # 6. 调查渠道 --------------------------------------------------------
    lines += [_heading("6. 调查渠道"), ""]
    lines += [_heading("6.1 渠道组合策略", 3), ""]
    lines += [
        f"根据目标总体「{brief.target_population}」、区域「{brief.region}」、调查方式「{brief.survey_mode}」"
        f"与预算/周期约束，建议采用“**主要渠道 + 次要渠道 + 补充渠道 + 备用渠道**”的组合，"
        "避免单一渠道造成的样本同质化。主要渠道承担约一半样本，次要渠道用于扩大覆盖，"
        "补充渠道用于触达特定群体，备用渠道用于应对回收不足。",
        "",
    ]
    lines += [_heading("6.2 问卷渠道执行表", 3), ""]
    if plan.allocation:
        lines += [
            md_table(
                ["层级", "渠道", "类型", "目标样本", "占比", "覆盖范围", "优势", "风险", "质控要点"],
                _channel_rows(plan),
            ),
            "",
        ]
    else:
        lines += ["当前未匹配到问卷渠道；若以二手数据为主，可跳过本节。", ""]

    lines += [_heading("6.3 二手数据与文本来源", 3), ""]
    if plan.secondary_data:
        lines += [
            md_table(
                ["渠道", "类型", "覆盖范围", "主要用途", "质控要点", "合规要求"],
                [[c.name, c.type, c.coverage, c.pros, c.qc, c.compliance] for c in plan.secondary_data],
            ),
            "",
        ]
    elif brief.has_secondary_data() or brief.has_text_data():
        lines += ["研究涉及二手/文本数据，但未匹配到具体来源；建议补充行业报告、统计年鉴、指数平台或公开评论平台。", ""]
    else:
        lines += ["本研究以一手问卷为主，暂不涉及二手数据；如需补充行业背景，可增加统计年鉴与行业报告。", ""]

    lines += [_heading("6.4 各渠道质控与合规要点", 3), ""]
    lines += [md_table(["渠道", "主要风险", "质控措施", "合规要求"], _channel_qc_rows(plan)), ""]

    lines += [_heading("6.5 投放节奏", 3), ""]
    weeks = max(4, brief.timeline_weeks or 6)
    lines += [
        f"按 {weeks} 周周期安排，建议将正式调研放在第 2—4 周，预留至少 1 周用于清洗与补样：",
        "",
        md_table(
            ["周次", "渠道动作", "目标", "监控指标"],
            [
                ["第 1 周", "问卷定稿、预调研（30—50 份）、渠道沟通", "完成问卷修订与渠道排期", "预调研信度、题项理解问题"],
                ["第 2 周", "主要渠道正式投放", "完成主要渠道目标的 50%", "回收量、配额完成率、答题时长"],
                ["第 3 周", "次要/补充渠道投放；配额调整", "累计完成 85%", "渠道占比、样本结构"],
                ["第 4 周", "补样与收尾；开始清洗", "完成 100% 并剔除无效样本", "有效回收率、关键变量缺失率"],
                [f"第 {min(weeks, 5)} 周", "数据清洗与质量核查", "形成清洗后数据集", "无效样本规则、回访一致率"],
                [f"第 {weeks} 周", "分析与报告撰写", "完成分析结果与初稿", "模型前提检验、稳健性"],
            ],
        ),
        "",
    ]

    lines += [_heading("6.6 合规要求", 3), ""]
    lines += [
        "- 问卷首页提供知情同意，说明研究目的、匿名性、数据用途与退出权。",
        "- 不收集与 research 无关的身份证号、精确住址、银行卡号等敏感信息。",
        "- 公开文本抓取遵守平台协议与 robots.txt，不抓取个人隐私；引用时匿名化。",
        "- 激励设置避免高额诱导，防止非目标人群涌入。",
        "- 数据仅用于本项目研究，不向第三方出售或共享。",
        "",
    ]

    lines += ["---", ""]

    # 7. 质量控制 --------------------------------------------------------
    lines += [_heading("7. 质量控制措施"), ""]
    lines += [_heading("7.1 质控体系总览", 3), ""]
    lines += [
        "质量控制贯穿“设计—抽样—执行—清洗—分析—交付”全流程。下表给出各阶段目标与控制点数量，"
        "详细措施见后续各节。",
        "",
        md_table(["阶段", "目标", "主要控制点", "数量"], _qc_stage_rows(qc)),
        "",
    ]

    lines += [_heading("7.2 设计与抽样阶段质控", 3), ""]
    design_rows = [r for r in _qc_detail_rows(qc) if r[0] in {"设计阶段", "抽样阶段"}]
    lines += [
        md_table(["阶段", "控制点", "具体措施", "判定标准", "记录/证据"], design_rows),
        "",
    ]

    lines += [_heading("7.3 执行阶段质控", 3), ""]
    exec_rows = [r for r in _qc_detail_rows(qc) if r[0] in {"执行阶段", "合规"}]
    lines += [
        md_table(["阶段", "控制点", "具体措施", "判定标准", "记录/证据"], exec_rows),
        "",
    ]

    lines += [_heading("7.4 数据清洗规则", 3), ""]
    lines += [
        "数据清洗规则必须在正式调研前确定，避免“看到结果后再决定删哪些样本”。"
        "所有剔除与修改都应留痕，并在报告中说明。",
        "",
        md_table(["规则", "判定标准", "处理动作"], [[r["rule"], r["criterion"], r["action"]] for r in qc.invalid_rules]),
        "",
        "**清洗流程**：",
        "",
        "1. 导入原始数据并锁定只读副本；",
        "2. 去除重复提交（IP/设备/账号）；",
        "3. 按规则标记无效样本，生成 `QC_FLAG` 与剔除原因；",
        "4. 处理缺失值（删除/插补），记录插补方法与比例；",
        "5. 反向题转换、维度得分合成、多选题展开；",
        "6. 异常值与逻辑一致性复核；",
        "7. 输出清洗后数据集、清洗日志与变量字典。",
        "",
    ]
    clean_rows = [r for r in _qc_detail_rows(qc) if r[0] in {"清洗阶段"}]
    lines += [md_table(["阶段", "控制点", "具体措施", "判定标准", "记录/证据"], clean_rows), ""]

    lines += [_heading("7.5 分析与交付阶段质控", 3), ""]
    analysis_rows = [r for r in _qc_detail_rows(qc) if r[0] in {"分析阶段", "交付阶段"}]
    lines += [md_table(["阶段", "控制点", "具体措施", "判定标准", "记录/证据"], analysis_rows), ""]

    lines += [_heading("7.6 伦理与数据安全", 3), ""]
    lines += [_bullets(qc.ethics), ""]

    lines += [_heading("7.7 质控清单", 3), ""]
    lines += [
        "下表可直接作为调研执行与结题检查的清单。建议指定每项的责任人与完成时间，并在项目例会上逐项确认。",
        "",
        md_table(["阶段", "控制点", "具体措施", "判定标准", "责任人", "时间", "记录"], _qc_checklist_rows(qc)),
        "",
    ]

    lines += [_heading("7.8 验收标准", 3), ""]
    lines += [
        md_table(["验收项", "目标值"], [[r["item"], r["target"]] for r in qc.acceptance]),
        "",
    ]

    lines += ["---", ""]

    # 8. 数据交付 --------------------------------------------------------
    lines += [_heading("8. 数据交付要求"), ""]
    lines += [_heading("8.1 数据集结构", 3), ""]
    lines += [
        md_table(
            ["文件/数据表", "内容", "格式", "规模", "说明"],
            [
                ["raw_questionnaire", "问卷平台导出的原始数据", "CSV/XLSX", f"约 {fmt_num(sample.n_plan)} 行", "只读保存，不直接修改"],
                ["clean_main", "清洗后的分析数据集", "CSV", f"约 {fmt_num(sample.n_effective)} 行", "一行一个样本，含变量代码与 QC 标记"],
                ["text_corpus", "公开评论文本（如适用）", "CSV", "≥100 条", "字段：id, source, time, text, rating"],
                ["secondary_data", "二手资料摘录（如适用）", "XLSX/CSV", "按需", "字段：来源、年份、指标、数值、口径"],
                ["variable_dictionary", "变量字典", "XLSX/MD", "全变量", "与第 3.7 节一致"],
                ["cleaning_log", "清洗日志", "MD/XLSX", "逐条记录", "剔除原因、缺失处理、异常值复核"],
                ["analysis_code", "分析脚本", "PY/IPYNB/R", "按模块", "固定随机种子，含运行说明"],
            ],
        ),
        "",
    ]

    lines += [_heading("8.2 字段与编码规范", 3), ""]
    lines += [
        "- 字段名：英文大写 + 下划线，角色前缀 `DV_`、`IV_`、`MED_`、`MOD_`、`CV_`、`SC_`、`QC_`。",
        "- 变量代码：与第 3.7 节变量字典一致，不在数据集中随意改名。",
        "- 量表题：1—5 或 1—7 整数；反向题已转换；维度得分为题项均值，保留 2 位小数。",
        "- 分类变量：使用整数编码，并在变量字典中列出码表；不得在同一列混用文字与数字。",
        "- 多选题：每个选项一列（0/1），另设 `MR_*_COUNT` 记录选择项数；不得用逗号拼接后直接分析。",
        "- 开放题：保留原文列 `OPEN_*_TEXT` 与编码列 `OPEN_*_CODE`，编码规则写入变量字典。",
        "- 日期/时间：统一 `YYYY-MM-DD` 与 `HH:MM:SS`；时长以秒为单位。",
        "",
    ]

    lines += [_heading("8.3 缺失值与异常值", 3), ""]
    lines += [
        md_table(
            ["情形", "编码/处理", "说明"],
            [
                ["未作答", "-99", "问卷未答或跳过"],
                ["不适用", "-98", "逻辑跳转导致的不适用"],
                ["拒绝回答", "-97", "受访者明确拒答"],
                ["不知道", "-96", "受访者无法判断"],
                ["异常值", "保留原值 + QC_FLAG", "不直接删除；复核后决定是否剔除或缩尾"],
                ["关键变量缺失>30%", "整样本剔除", "记录剔除原因"],
                ["量表维度缺失", "该维度得分记为缺失", "不应用 0 分代替"],
            ],
        ),
        "",
        "缺失值处理优先顺序：① 回溯问卷/原始记录补录；② 删除关键变量缺失样本；③ 对少量缺失采用中位数/均值插补；"
        "④ 对重要模型使用多重插补，并在报告中说明。不得用 0 或均值无条件填补所有缺失。",
        "",
    ]

    lines += [_heading("8.4 版本与可复现", 3), ""]
    lines += [
        "- 原始数据只读；清洗数据按 `clean_v1`、`clean_v2` 递增，保留每次变更说明。",
        "- 分析脚本与数据版本一一对应；脚本头部注明输入文件、输出文件、运行环境与随机种子。",
        "- 图表由脚本生成，不手工改数；图表标题、坐标轴、单位、样本量齐全。",
        "- 重要结果保存中间表（系数表、拟合指标、稳健性结果），便于复核。",
        "",
    ]

    lines += [_heading("8.5 交付清单", 3), ""]
    lines += [
        "- [ ] 原始数据（只读）",
        "- [ ] 清洗后数据集",
        "- [ ] 变量字典",
        "- [ ] 清洗日志与无效样本清单",
        "- [ ] 分析脚本与运行说明",
        "- [ ] 信效度报告、模型输出与稳健性附录",
        "- [ ] 数据来源与合规说明",
        "",
    ]

    lines += ["---", ""]

    # 9. 进度分工风险 ----------------------------------------------------
    lines += [_heading("9. 进度、分工与风险"), ""]
    lines += [_heading("9.1 进度计划", 3), ""]
    lines += [
        md_table(["时间", "任务", "交付物"], _progress_plan(brief.timeline_weeks)),
        "",
    ]

    lines += [_heading("9.2 分工建议", 3), ""]
    team = brief.team_size or 5
    roles = [
        ["项目负责人", "统筹进度、对外沟通、质量把关", "研究方案、进度表、最终报告"],
        ["问卷设计", "构念操作化、题项撰写、预调研", "问卷、变量字典、预调研报告"],
        ["数据采集", "渠道投放、配额监控、回访", "回收数据、渠道日报、回访记录"],
        ["数据分析", "清洗、统计检验、建模、可视化", "清洗数据、分析结果、代码"],
        ["报告撰写", "文献、结果呈现、策略建议、答辩", "报告初稿、PPT、答辩稿"],
    ]
    if team <= 3:
        roles = [
            ["项目负责人/分析", "统筹、问卷设计、数据分析", "方案、问卷、分析结果"],
            ["数据采集", "渠道投放、配额与回访", "回收数据、日报"],
            ["报告撰写", "文献、报告、答辩", "报告与 PPT"],
        ]
    lines += [
        md_table(["角色", "主要职责", "关键交付物"], roles),
        "",
        f"当前团队规模：{team} 人。建议每人至少负责一个可交付模块，并在进度表中标注交接节点。",
        "",
    ]

    lines += [_heading("9.3 风险与应对", 3), ""]
    lines += [
        md_table(["风险", "可能性", "影响", "应对措施"], _risk_rows()),
        "",
    ]

    lines += ["---", ""]

    # 10. 待确认 --------------------------------------------------------
    lines += [_heading("10. 待确认事项与假设清单"), ""]
    lines += [
        "以下事项由输入信息推断或采用默认值生成。正式调研前应由项目组逐项确认，"
        "确认结果回写到 `doc/input/research_brief.md` 后重新生成文档。",
        "",
    ]
    todo = _todo_rows(issues, analysis.warnings + rec.warnings + plan.warnings + qc.warnings)
    if todo:
        lines += [md_table(["级别", "来源/字段", "说明", "建议动作", "责任人"], todo), ""]
    else:
        lines += ["未发现需要特别确认的事项。", ""]

    lines += [_heading("10.1 生成时采用的默认值与假设", 3), ""]
    lines += [md_table(["项目", "取值", "来源/说明"], _assumption_rows(brief, sample)), ""]

    lines += ["---", ""]

    # 附录 ---------------------------------------------------------------
    lines += [_heading("附录 A. 本研究相关模型速查"), ""]
    lines += [
        md_table(
            ["模型", "难度", "核心用途", "输入数据", "主要输出", "关键前提"],
            [
                [m.name, m.level, "、".join(m.question_types[:2]), m.inputs, m.outputs, m.assumptions[0] if m.assumptions else "—"]
                for m in _selected_models(rec)
            ],
        ),
        "",
    ]

    lines += [_heading("附录 B. 参考文献"), ""]
    refs = []
    for m in rec.core + rec.optional:
        if m.id in REFERENCES and REFERENCES[m.id] not in refs:
            refs.append(REFERENCES[m.id])
    for i, ref in enumerate(refs, 1):
        lines.append(f"[{i}] {ref}")
    lines.append("")

    lines += [_heading("附录 C. 术语表"), ""]
    lines += [
        md_table(
            ["术语", "含义"],
            [
                ["构念（Construct）", "无法直接观测、需通过多个题项间接测量的抽象概念，如满意度、信任。"],
                ["操作化（Operationalization）", "把抽象构念转化为可观察、可计分的题项或指标的过程。"],
                ["李克特量表", "由一组同向陈述句与等级选项构成的测量工具，常用 5 级或 7 级计分。"],
                ["信度（Reliability）", "测量结果的稳定性与内部一致性，常用 Cronbach's α 评价。"],
                ["效度（Validity）", "测量工具是否真正测到了目标构念，常用 KMO/Bartlett 与因子分析检验结构效度。"],
                ["设计效应（deff）", "复杂抽样相对简单随机抽样的方差放大倍数，用于调整样本量。"],
                ["有效样本", "剔除无效问卷后真正进入分析的样本量。"],
                ["多重响应", "多选题的分析方式，每个选项作为 0/1 变量，分别报告响应百分比与个案百分比。"],
                ["VIF", "方差膨胀因子，用于诊断自变量间的多重共线性；一般要求<5。"],
                ["OR（Exp(B)）", "Logistic 回归的发生比，表示自变量每增加一个单位，事件发生几率相对参照组的倍数。"],
                ["SEM", "结构方程模型，可同时处理潜变量测量误差与变量间路径关系。"],
                ["IPA", "重要性—表现分析，用重要度与满意度四象限确定改进优先级。"],
                ["稳健性检验", "通过替换口径、子样本或估计方法，检验核心结论是否稳定。"],
            ],
        ),
        "",
    ]

    lines += [
        "---",
        "",
        f"*本文档由 data-requirement skill 与 `engine/` 规则引擎于 {today} 生成。"
        "文档中的变量、样本参数与方法建议需结合指导老师意见、预调研结果与正式数据复核后使用。*",
        "",
    ]

    return "\n".join(lines)
