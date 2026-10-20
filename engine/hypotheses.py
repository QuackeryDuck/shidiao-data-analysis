"""研究假设生成：从研究问题导出可检验假设，并绑定变量与模型。"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .brief import Hypothesis, ResearchBrief
from .knowledge import Recommendation, infer_question_types
from .utils import clean_inline, norm_key, unique_keep_order
from .variables import VariableAnalysis

DATA_DIR = Path(__file__).resolve().parent / "data"

KIND_CN = {
    "difference": "差异关系",
    "association": "相关关系",
    "impact": "影响关系",
    "mediation": "中介机制",
    "moderation": "调节效应",
    "descriptive": "描述性",
}


def _theory_for(text: str) -> tuple[str, str]:
    data = json.loads((DATA_DIR / "construct_keywords.json").read_text(encoding="utf-8"))
    for item in data.get("theory_map", []):
        if any(k in text for k in item["keywords"]):
            return item["theory"], item.get("note", "")
    return "消费者行为理论", "建议结合文献补充具体理论依据"


def _direction(iv_text: str) -> str:
    data = json.loads((DATA_DIR / "construct_keywords.json").read_text(encoding="utf-8"))
    pos = data.get("positive_keywords", [])
    neg = data.get("negative_keywords", [])
    if any(k in iv_text for k in neg):
        return "负向"
    if any(k in iv_text for k in pos):
        return "正向"
    return ""


def _infer_kind(text: str) -> str:
    if "中介" in text or "通过" in text:
        return "mediation"
    if "调节" in text:
        return "moderation"
    if "差异" in text or "比较" in text or "不同" in text:
        return "difference"
    if "关系" in text or "相关" in text or "关联" in text:
        return "association"
    if "影响" in text or "作用" in text or "因素" in text:
        return "impact"
    return "descriptive"


def _method_for(kind: str, dv_types: set[str], rec: Recommendation | None = None) -> str:
    if rec:
        core_ids = {m.id for m in rec.core}
        preference = {
            "difference": ["anova", "chi_square", "crosstab"],
            "association": ["chi_square", "crosstab"],
            "impact": ["logistic_regression", "linear_regression", "sem"],
            "mediation": ["sem", "linear_regression"],
            "moderation": ["linear_regression", "sem"],
            "descriptive": ["descriptive"],
        }.get(kind, [])
        names = [m.name for m in rec.core if m.id in preference and m.id in core_ids]
        if names:
            return " / ".join(names[:2])
    return {
        "difference": "方差分析（连续因变量）或卡方检验（分类因变量）",
        "association": "卡方检验 + 交叉分析",
        "impact": "二元 Logistic 回归" if "binary" in dv_types else "多元线性回归",
        "mediation": "Bootstrap 中介检验（或 SEM）",
        "moderation": "分层回归（交互项）",
        "descriptive": "描述性统计",
    }.get(kind, "描述性统计 + 推断统计")


def _find_vars(text: str, analysis: VariableAnalysis) -> dict[str, list[str]]:
    """在假设文本中匹配已有构念。"""
    iv, dv, med, mod = [], [], [], []
    for c in sorted(analysis.constructs, key=lambda x: len(x.name), reverse=True):
        if c.role in {"control", "screening"} or c.name not in text:
            continue
        if c.role == "dependent":
            dv.append(c.name)
        elif c.role == "independent":
            iv.append(c.name)
        elif c.role == "mediator":
            med.append(c.name)
        elif c.role == "moderator":
            mod.append(c.name)
    return {"iv": unique_keep_order(iv), "dv": unique_keep_order(dv), "mediator": unique_keep_order(med), "moderator": unique_keep_order(mod)}


def _pick_names(candidates: list[str], default: list[str], n: int = 1) -> list[str]:
    out = unique_keep_order(candidates)
    if not out:
        out = default[:n]
    return out[:n]


def _build_from_rq(
    rq_id: str,
    rq_text: str,
    analysis: VariableAnalysis,
    rec: Recommendation | None,
) -> tuple[Hypothesis | None, dict | None]:
    kind = _infer_kind(rq_text)
    rq_info = next((x for x in analysis.rq_map if x["qid"] == rq_id), None) or {}
    ivs = rq_info.get("iv", [])
    dvs = rq_info.get("dv", [])
    meds = rq_info.get("mediator", [])
    mods = rq_info.get("moderator", [])
    dv_types = analysis.dv_types

    if kind == "mediation" and not meds:
        # 尝试从“通过 X”中提取
        m = re.search(r"通过(.+?)影响", rq_text)
        if m:
            meds = [clean_inline(m.group(1))]
    if kind == "moderation" and not mods:
        m = re.search(r"(.+?)的?调节", rq_text)
        if m:
            mods = [clean_inline(m.group(1))]
    if not dvs:
        dvs = analysis.names_by_role("dependent")[:1]
    if not ivs:
        ivs = analysis.names_by_role("independent")[:2]

    if kind == "moderation":
        # 调节变量不应同时被当作自变量重复列出
        ivs = [x for x in ivs if x not in mods] or analysis.names_by_role("independent")[:1]

    iv_text = "、".join(ivs) if ivs else "核心影响因素"
    dv = dvs[0] if dvs else "核心结果变量"
    direction_word = _direction(" ".join(ivs)) if len(ivs) == 1 else ""
    theory, theory_note = _theory_for(rq_text)
    method = _method_for(kind, dv_types, rec)

    if kind == "difference":
        text = f"不同{iv_text}的受访者在{dv}上存在显著差异。"
        if not ivs:
            text = f"不同群体特征在{dv}上存在显著差异。"
        direction = "存在差异"
        mods = []
    elif kind == "association":
        other = ivs[1] if len(ivs) > 1 else "其他核心变量"
        text = f"{ivs[0] if ivs else '核心变量'}与{other}之间存在显著相关关系。"
        direction = "存在关联"
        mods = []
    elif kind == "mediation":
        med = meds[0] if meds else "中介变量"
        text = f"{med}在{iv_text}与{dv}之间起中介作用。"
        direction = "存在中介"
        mods = []
    elif kind == "moderation":
        mod = mods[0] if mods else "情境变量"
        text = f"{mod}调节{iv_text}对{dv}的影响。"
        direction = "存在调节"
        meds = []
    elif kind == "impact":
        if direction_word:
            text = f"{iv_text}对{dv}具有显著{direction_word}影响。"
            direction = direction_word
        else:
            text = f"{iv_text}对{dv}具有显著影响。"
            direction = "待逐项检验"
    else:
        return None, {
            "qid": rq_id,
            "text": rq_text,
            "reason": "该问题偏向现状描述或探索性分析，暂不转化为可检验假设。",
        }

    return (
        Hypothesis(
            hid="",
            text=text,
            kind=kind,
            rq_id=rq_id,
            iv=unique_keep_order(ivs),
            dv=unique_keep_order(dvs),
            mediator=unique_keep_order(meds),
            moderator=unique_keep_order(mods),
            direction=direction,
            method=method,
            theory=f"{theory}：{theory_note}" if theory_note else theory,
            source="generated",
        ),
        None,
    )


def generate(brief: ResearchBrief, analysis: VariableAnalysis, rec: Recommendation | None = None) -> tuple[list[Hypothesis], list[dict]]:
    hypotheses: list[Hypothesis] = []
    exploratory: list[dict] = []

    # 1. 保留用户已有假设
    for i, text in enumerate(brief.existing_hypotheses, 1):
        text = clean_inline(text)
        text = re.sub(r"^H\s*\d+\s*[：:.、-]\s*", "", text, flags=re.I)
        kind = _infer_kind(text)
        vars_ = _find_vars(text, analysis)
        if not vars_["dv"]:
            vars_["dv"] = analysis.names_by_role("dependent")[:1]
        if not vars_["iv"]:
            vars_["iv"] = analysis.names_by_role("independent")[:2]
        theory, theory_note = _theory_for(text)
        hypotheses.append(
            Hypothesis(
                hid=f"H{i}",
                text=text if text.endswith("。") else text + "。",
                kind=kind,
                rq_id="",
                iv=vars_["iv"],
                dv=vars_["dv"],
                mediator=vars_["mediator"],
                moderator=vars_["moderator"],
                direction=_direction(" ".join(vars_["iv"])),
                method=_method_for(kind, analysis.dv_types, rec),
                theory=f"{theory}：{theory_note}" if theory_note else theory,
                source="input",
            )
        )

    # 2. 从研究问题生成
    if not brief.existing_hypotheses:
        for q in brief.research_questions:
            h, ex = _build_from_rq(q.qid, q.text, analysis, rec)
            if h:
                hypotheses.append(h)
            if ex:
                exploratory.append(ex)

    # 3. 编号
    for i, h in enumerate(hypotheses, 1):
        h.hid = f"H{i}"

    # 4. 若没有生成任何假设，补充一条总体假设
    if not hypotheses and analysis.dependent:
        dv = analysis.dependent[0].name
        ivs = analysis.independent[:2]
        if ivs:
            hypotheses.append(
                Hypothesis(
                    hid="H1",
                    text=f"{ivs[0]}对{dv}具有显著影响。",
                    kind="impact",
                    iv=[ivs[0]],
                    dv=[dv],
                    direction=_direction(ivs[0]) or "显著",
                    method=_method_for("impact", analysis.dv_types, rec),
                    theory="消费者行为理论",
                    source="generated",
                )
            )
    return hypotheses, exploratory
