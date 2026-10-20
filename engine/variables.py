"""变量体系推断：构念角色、测量层级、题项编码与变量字典。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .brief import Construct, ResearchBrief
from .utils import clean_inline, norm_key, unique_keep_order

DATA_DIR = Path(__file__).resolve().parent / "data"

STOPWORDS = {
    "消费者", "受访者", "用户", "顾客", "居民", "人群", "群体", "研究", "分析", "调查",
    "影响", "关系", "差异", "比较", "是否", "存在", "显著", "因素", "主要", "哪些",
    "如何", "程度", "情况", "现状", "以及", "并且", "对于", "关于", "进行", "可以",
    "我们", "他们", "本文", "项目", "市场", "问题", "目标", "内容", "方面", "角度",
    "作用", "机制", "路径", "条件下", "背景", "意义", "价值", "策略", "建议",
}

ROLE_ORDER = ["dependent", "independent", "mediator", "moderator", "control", "screening", "exploratory"]
ROLE_CN = {
    "dependent": "因变量",
    "independent": "自变量",
    "mediator": "中介变量",
    "moderator": "调节变量",
    "control": "控制变量",
    "screening": "筛选变量",
    "exploratory": "探索性变量",
}


@dataclass
class VariableRow:
    code: str
    name: str
    role: str
    role_cn: str
    definition: str
    measure: str
    items: int
    scale: str
    values: str
    source: str
    rq: str = ""
    hypothesis: str = ""
    note: str = ""


@dataclass
class QuestionnaireItem:
    code: str
    construct: str
    question: str
    measure: str
    reverse: bool = False
    attention: bool = False


@dataclass
class VariableAnalysis:
    constructs: list[Construct] = field(default_factory=list)
    rows: list[VariableRow] = field(default_factory=list)
    dictionary: list[VariableRow] = field(default_factory=list)
    questionnaire: list[QuestionnaireItem] = field(default_factory=list)
    rq_map: list[dict] = field(default_factory=list)
    dv_types: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)
    item_count: int = 0
    predictor_count: int = 0
    group_count: int = 3

    def by_role(self, role: str) -> list[Construct]:
        return [c for c in self.constructs if c.role == role]

    def names_by_role(self, role: str) -> list[str]:
        return [c.name for c in self.constructs if c.role == role]

    @property
    def dependent(self) -> list[Construct]:
        return self.by_role("dependent")

    @property
    def independent(self) -> list[Construct]:
        return self.by_role("independent")

    @property
    def mediators(self) -> list[Construct]:
        return self.by_role("mediator")

    @property
    def moderators(self) -> list[Construct]:
        return self.by_role("moderator")

    @property
    def controls(self) -> list[Construct]:
        return self.by_role("control")

    @property
    def screening(self) -> list[Construct]:
        return self.by_role("screening")


def _load_keywords() -> dict:
    return json.loads((DATA_DIR / "construct_keywords.json").read_text(encoding="utf-8"))


def infer_role(name: str, definition: str = "", rq_texts: list[str] | None = None) -> str:
    """根据名称、定义与研究问题推断变量角色。"""
    text = f"{name} {definition}".strip()
    kw = _load_keywords()["roles"]
    rq_texts = rq_texts or []

    # 明确的角色词优先
    if any(k in text for k in ["因变量", "结果变量", "被解释变量"]):
        return "dependent"
    if any(k in text for k in ["中介"]):
        return "mediator"
    if any(k in text for k in ["调节"]):
        return "moderator"
    if any(k in text for k in ["控制变量", "控制"]):
        return "control"
    if any(k in text for k in ["甄别", "筛选"]):
        return "screening"

    # 研究问题中的关系位置
    for rq in rq_texts:
        if name not in rq:
            continue
        # “X 通过 M 影响 Y”
        m = re.search(r"(.+?)通过(.+?)影响(.+?)(?:[。；;]|$)", rq)
        if m and name in m.group(2):
            return "mediator"
        # “X 在 M 调节下影响 Y”
        if "调节" in rq and name in rq:
            if re.search(rf"{re.escape(name)}.{{0,12}}调节|调节.{{0,12}}{re.escape(name)}", rq):
                return "moderator"
        # “X 对 Y 的影响”
        m = re.search(r"(.+?)对(.+?)的?(?:影响|作用)", rq)
        if m:
            iv_part, dv_part = m.group(1), m.group(2)
            if name in dv_part:
                return "dependent"
            if name in iv_part:
                return "independent"
        # “不同 X 在 Y 上的差异”
        m = re.search(r"不同(.+?)在(.+?)上", rq)
        if m:
            if name in m.group(2):
                return "dependent"
            if name in m.group(1):
                return "independent"

    # 关键词兜底：因变量词优先
    if any(k in name for k in kw["dependent"]):
        return "dependent"
    if any(k in name for k in kw["mediator"]):
        return "mediator"
    if any(k in name for k in kw["moderator"]):
        return "moderator"
    if any(k in name for k in kw["control"]):
        return "control"
    if any(k in name for k in kw["screening"]):
        return "screening"
    if any(k in name for k in kw["independent"]):
        return "independent"
    return "independent"


def _clean_name(text: str) -> str:
    s = clean_inline(text)
    s = re.sub(r"^(?:不同|各|该|本|其|消费者|受访者|用户|顾客|居民)+", "", s)
    s = re.sub(r"(?:消费者|受访者|用户|顾客|居民)$", "", s)
    s = s.strip("的 了 在 对 与 和 及 ")
    s = re.sub(r"^(?:影响因素|主要因素)$", "", s)
    return s.strip()


def _valid_name(s: str) -> bool:
    if not s or len(s) < 2 or len(s) > 16:
        return False
    if s in STOPWORDS:
        return False
    if not re.search(r"[一-鿿A-Za-z]", s):
        return False
    return True


def _extract_phrases(text: str) -> list[str]:
    """从研究问题中抽取候选构念短语。"""
    text = clean_inline(text)
    candidates: list[str] = []

    # 结构化关系模式
    patterns = [
        r"(.+?)对(.+?)的?(?:影响|作用)",
        r"(.+?)与(.+?)的?(?:关系|关联)",
        r"不同(.+?)在(.+?)上",
        r"(.+?)通过(.+?)影响(.+?)(?:[。；;]|$)",
        r"(.+?)在(.+?)的?调节下",
        r"(.+?)是否影响(.+?)(?:[。；;]|$)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            for g in m.groups():
                if g:
                    candidates.append(g)

    # 按连接词切分
    parts = re.split(r"[，,。；;、：:（）()\s]+|以及对|以及|并且|同时|从而|进而|对于|关于", text)
    for p in parts:
        p = re.sub(r"^(?:研究|分析|探讨|了解|调查|识别|检验|比较)+", "", p)
        candidates.append(p)

    out = []
    for c in candidates:
        c = _clean_name(c)
        # 再去掉动词性前缀
        c = re.sub(r"^(?:研究|分析|探讨|了解|调查|识别|检验|比较|评价|测量)+", "", c)
        c = _clean_name(c)
        if _valid_name(c):
            out.append(c)
    return unique_keep_order(out)


def extract_constructs(brief: ResearchBrief) -> list[Construct]:
    """当输入未提供构念时，从研究问题与目标中推断。"""
    constructs: list[Construct] = []
    seen: set[str] = set()
    rq_texts = [q.text for q in brief.research_questions]
    for q in brief.research_questions:
        for phrase in _extract_phrases(q.text):
            key = norm_key(phrase)
            if key in seen:
                continue
            seen.add(key)
            role = infer_role(phrase, "", rq_texts)
            constructs.append(Construct(name=phrase, role=role, inferred=True, definition=f"由研究问题「{q.text}」推断，待确认。"))
    # 如果仍为空，用目标文本
    if not constructs:
        for obj in brief.objectives:
            for phrase in _extract_phrases(obj):
                key = norm_key(phrase)
                if key in seen:
                    continue
                seen.add(key)
                constructs.append(
                    Construct(name=phrase, role=infer_role(phrase, "", rq_texts), inferred=True, definition=f"由研究目标「{obj}」推断，待确认。")
                )
    return constructs


def _infer_measure(c: Construct) -> str:
    text = f"{c.name} {c.definition} {c.scale} {c.measure}".strip()
    if c.measure:
        return c.measure
    if "文本" in text or "开放题" in text:
        return "文本"
    if "多选" in text or "多重响应" in text:
        return "多重响应"
    if "李克特" in text or "量表" in text:
        return "定序（按连续处理）"
    if any(k in text for k in ["性别", "职业", "地区", "类别", "是否", "渠道", "类型"]):
        return "定类"
    if any(k in text for k in ["年龄", "收入", "学历", "年级", "频率", "次数", "生活费"]):
        return "定序"
    if any(k in text for k in ["金额", "时长", "距离", "数量", "得分"]):
        return "连续"
    return "定序（按连续处理）"


def _infer_values(c: Construct, measure: str) -> str:
    if "文本" in measure:
        return "开放文本，编码后分析"
    if "多重响应" in measure:
        return "0/1 多选编码，1=选中，0=未选中"
    if "定类" in measure:
        if "性别" in c.name:
            return "1=男，2=女，3=其他/不愿透露"
        if "是否" in c.name:
            return "1=是，0=否"
        return "按选项编码（1,2,3…），需在问卷中列出全部选项"
    if "定序" in measure:
        if "李克特" in c.scale or "量表" in c.scale:
            return "1—5 或 1—7，数值越大表示越同意/越满意；反向题需转换"
        return "按等级编码，需注明组距与方向"
    return "连续数值，注明单位与小数位"


def _assign_codes(constructs: list[Construct]) -> dict[str, str]:
    counters = {r: 0 for r in ROLE_ORDER}
    codes: dict[str, str] = {}
    prefixes = {
        "dependent": "DV",
        "independent": "IV",
        "mediator": "MED",
        "moderator": "MOD",
        "control": "CV",
        "screening": "SC",
        "exploratory": "EX",
    }
    for c in constructs:
        role = c.role if c.role in counters else "independent"
        counters[role] += 1
        codes[norm_key(c.name)] = f"{prefixes[role]}{counters[role]}"
    return codes


def _default_controls(brief: ResearchBrief) -> list[Construct]:
    data = _load_keywords()
    defaults = data.get("default_controls", [])
    blob = brief.target_population + brief.region
    is_student = any(k in blob for k in ["学生", "大学生", "研究生", "高校", "校园"])
    controls: list[Construct] = []
    for item in defaults:
        name = item["name"]
        if is_student and name == "学历":
            name = "年级"
            levels = "大一/大二/大三/大四/研究生及以上"
        elif is_student and name == "月可支配收入":
            name = "月生活费"
            levels = "1000 元以下/1000—2000/2000—3000/3000—5000/5000 元以上"
        else:
            levels = item.get("levels", "")
        if is_student and name == "职业":
            continue
        controls.append(
            Construct(
                name=name,
                definition=f"人口统计特征，用于控制个体差异。取值：{levels}",
                role="control",
                items=1,
                scale="单选",
                measure=item.get("measure", "定类"),
                source="一手问卷",
            )
        )
    # 学生样本补充专业
    if is_student and not any("专业" in c.name for c in controls):
        controls.insert(2, Construct(name="专业", definition="受访者所学专业类别", role="control", items=1, scale="单选", measure="定类"))
    # 渠道来源作为控制/质控变量
    controls.append(
        Construct(
            name="问卷来源渠道",
            definition="受访者完成问卷的渠道（微信/校园社群/问卷星/线下拦截等）",
            role="control",
            items=1,
            scale="单选",
            measure="定类",
            source="系统记录",
        )
    )
    return controls


def _screening_vars(brief: ResearchBrief) -> list[Construct]:
    out = [
        Construct(
            name="知情同意",
            definition="受访者是否阅读并同意参与研究",
            role="screening",
            items=1,
            scale="单选（是/否）",
            measure="定类",
        ),
        Construct(
            name="目标人群甄别",
            definition=f"是否属于目标总体：{brief.target_population}",
            role="screening",
            items=1,
            scale="单选（是/否）",
            measure="定类",
        ),
    ]
    if brief.region and brief.region not in {"全国", "待确认", ""}:
        out.append(
            Construct(
                name="地区甄别",
                definition=f"当前常住/活动地是否位于研究区域：{brief.region}",
                role="screening",
                items=1,
                scale="单选（是/否）",
                measure="定类",
            )
        )
    return out


def _ensure_dependent(brief: ResearchBrief, constructs: list[Construct]) -> list[Construct]:
    if any(c.role == "dependent" for c in constructs):
        return constructs
    blob = brief.text_blob()
    candidates = [
        ("购买意愿", "购买"),
        ("使用意愿", "使用"),
        ("参与意愿", "参与"),
        ("总体满意度", "满意"),
        ("推荐意愿", "推荐"),
        ("支付意愿", "支付"),
    ]
    name = "综合满意度"
    for candidate, key in candidates:
        if key in blob:
            name = candidate
            break
    constructs.append(
        Construct(
            name=name,
            definition="研究的核心结果变量；由输入信息推断，需结合研究目标确认。",
            role="dependent",
            items=4,
            scale="5 级李克特",
            measure="定序（按连续处理）",
            inferred=True,
        )
    )
    return constructs


def _match_constructs_in_text(text: str, constructs: list[Construct]) -> list[Construct]:
    """按名称长度降序匹配文本中出现的构念。"""
    hits = []
    for c in sorted(constructs, key=lambda x: len(x.name), reverse=True):
        # 控制变量在“不同 X 在 Y 上”的差异问题中可能正是分组变量，
        # 因此保留控制变量，仅排除甄别题。
        if c.role == "screening":
            continue
        if c.name and c.name in text:
            hits.append(c)
    return hits


def _rq_variable_map(brief: ResearchBrief, constructs: list[Construct]) -> list[dict]:
    out = []
    for q in brief.research_questions:
        hits = _match_constructs_in_text(q.text, constructs)
        iv, dv, med, mod = [], [], [], []
        # 通过构念名称与研究问题中的关键词分配
        for c in hits:
            if c.role == "dependent":
                dv.append(c.name)
            elif c.role == "independent":
                iv.append(c.name)
            elif c.role == "mediator":
                med.append(c.name)
            elif c.role == "moderator":
                mod.append(c.name)
        # 依据关系模式修正
        m = re.search(r"(.+?)对(.+?)的?(?:影响|作用)", q.text)
        if m:
            for c in hits:
                if c.name in m.group(2) and c.name not in dv:
                    dv.append(c.name)
                elif c.name in m.group(1) and c.name not in iv:
                    iv.append(c.name)
        m = re.search(r"不同(.+?)在(.+?)上", q.text)
        if m:
            for c in hits:
                if c.name in m.group(2) and c.name not in dv:
                    dv.append(c.name)
                elif c.name in m.group(1) and c.name not in iv:
                    iv.append(c.name)
        # 只有关系型问题才补默认自变量；否则会把无关的 IV 强行挂到描述性问题上。
        relation_cues = ["影响", "关系", "相关", "差异", "作用", "中介", "调节", "因素", "比较"]
        if not iv and any(cue in q.text for cue in relation_cues):
            iv = [c.name for c in constructs if c.role == "independent"][:3]
        if not dv:
            outcome_cues = ["频率", "意愿", "满意度", "消费", "购买", "使用", "参与", "评价", "支出", "客单价"]
            text_cues = ["评论", "文本", "舆情", "情感", "提及", "词频", "主题", "语料"]
            is_text_question = any(cue in q.text for cue in text_cues)
            if not is_text_question and any(cue in q.text for cue in outcome_cues):
                dv = [c.name for c in constructs if c.role == "dependent"][:1]

        # 同一问题内按“控制变量 → 自变量 → 调节变量”排序，读起来更符合分组差异问题的表达。
        role_priority = {"control": 0, "independent": 1, "mediator": 2, "moderator": 3, "dependent": 4}
        construct_order = {c.name: i for i, c in enumerate(constructs)}

        def _ordered(names: list[str]) -> list[str]:
            role_of = {c.name: c.role for c in constructs}
            return sorted(
                unique_keep_order(names),
                key=lambda n: (role_priority.get(role_of.get(n, ""), 9), construct_order.get(n, 99)),
            )

        out.append(
            {
                "qid": q.qid,
                "text": q.text,
                "types": q.types,
                "iv": _ordered(iv),
                "dv": _ordered(dv),
                "mediator": _ordered(med),
                "moderator": _ordered(mod),
                "matched": [c.name for c in hits],
            }
        )
    return out


def _build_questionnaire(constructs: list[Construct]) -> list[QuestionnaireItem]:
    items: list[QuestionnaireItem] = []
    qno = 1
    q_order = {
        "screening": 0,
        "dependent": 1,
        "independent": 2,
        "mediator": 3,
        "moderator": 4,
        "exploratory": 5,
        "control": 6,
    }
    ordered = sorted(constructs, key=lambda c: q_order.get(c.role, 99))
    for c in ordered:
        n = max(1, c.items)
        for i in range(1, n + 1):
            is_reverse = False
            if i == n and n >= 4 and ("李克特" in c.scale or "量表" in c.scale):
                is_reverse = True
            items.append(
                QuestionnaireItem(
                    code=f"Q{qno}",
                    construct=c.name,
                    question=f"{c.name}相关题项 {i}",
                    measure=c.measure or ("定序" if "量表" in c.scale else "定类"),
                    reverse=is_reverse,
                )
            )
            qno += 1
    # 注意力检测题
    items.append(
        QuestionnaireItem(
            code=f"Q{qno}",
            construct="注意力检测",
            question="请在本题选择“比较同意”（用于检测是否认真作答）",
            measure="定序",
            attention=True,
        )
    )
    return items


def analyze(brief: ResearchBrief) -> VariableAnalysis:
    constructs = [Construct(**{**c.__dict__}) for c in brief.constructs]
    rq_texts = [q.text for q in brief.research_questions]

    if not constructs:
        constructs = extract_constructs(brief)

    # 补齐角色
    for c in constructs:
        if not c.role:
            c.role = infer_role(c.name, c.definition, rq_texts)
    # 补齐测量层级、题项数、量表
    for c in constructs:
        if not c.measure:
            c.measure = _infer_measure(c)
        if not c.scale:
            c.scale = "5 级李克特"
        if c.role in {"control", "screening"}:
            c.items = max(1, c.items)
        else:
            c.items = max(1, c.items)
    constructs = _ensure_dependent(brief, constructs)

    # 去掉重名
    seen: set[str] = set()
    deduped = []
    for c in constructs:
        key = norm_key(c.name)
        if key and key not in seen:
            seen.add(key)
            deduped.append(c)
    constructs = deduped

    # 补充控制与筛选变量
    existing = {norm_key(c.name) for c in constructs}
    for c in _screening_vars(brief):
        if norm_key(c.name) not in existing:
            constructs.append(c)
            existing.add(norm_key(c.name))
    for c in _default_controls(brief):
        if norm_key(c.name) not in existing:
            constructs.append(c)
            existing.add(norm_key(c.name))

    codes = _assign_codes(constructs)
    rq_map = _rq_variable_map(brief, constructs)
    rq_by_name: dict[str, list[str]] = {}
    for item in rq_map:
        for name in item["iv"] + item["dv"] + item["mediator"] + item["moderator"]:
            bucket = rq_by_name.setdefault(norm_key(name), [])
            if item["qid"] not in bucket:
                bucket.append(item["qid"])

    rows: list[VariableRow] = []
    for c in constructs:
        code = codes.get(norm_key(c.name), "VAR")
        rows.append(
            VariableRow(
                code=code,
                name=c.name,
                role=c.role,
                role_cn=ROLE_CN.get(c.role, c.role),
                definition=c.definition or f"测量受访者在「{c.name}」上的水平",
                measure=c.measure,
                items=c.items,
                scale=c.scale,
                values=_infer_values(c, c.measure),
                source=c.source,
                rq="、".join(rq_by_name.get(norm_key(c.name), [])),
                note="由研究问题推断，需人工确认" if c.inferred else c.notes,
            )
        )
    dictionary = sorted(rows, key=lambda r: (ROLE_ORDER.index(r.role) if r.role in ROLE_ORDER else 99, r.code))

    questionnaire = _build_questionnaire(constructs)
    dv_types: set[str] = set()
    for c in constructs:
        if c.role == "dependent":
            m = c.measure
            if "连续" in m:
                dv_types.add("continuous")
            elif "二分类" in m or ("定类" in m and ("是否" in c.name or "意愿" in c.name)):
                dv_types.add("binary")
            elif "文本" in m:
                dv_types.add("text")
            else:
                dv_types.add("continuous")
    predictor_count = max(1, len([c for c in constructs if c.role in {"independent", "mediator", "moderator"}]) + len([c for c in constructs if c.role == "control"]))
    item_count = sum(c.items for c in constructs if c.role not in {"screening", "control"})
    groups = 3
    for c in constructs:
        if c.role == "control" and any(k in c.name for k in ["年龄", "收入", "学历", "年级"]):
            groups = max(groups, 4)
            break

    warnings = []
    if any(c.inferred for c in constructs):
        warnings.append("部分变量由研究问题自动推断，正式使用前需结合理论与问卷逐项确认。")
    if not any(c.role == "dependent" and not c.inferred for c in constructs):
        warnings.append("因变量为推断结果，建议在输入文档中明确写出核心结果变量。")
    if sum(1 for c in constructs if c.role == "independent") < 2:
        warnings.append("自变量数量较少，回归类模型的解释力可能有限。")

    return VariableAnalysis(
        constructs=constructs,
        rows=rows,
        dictionary=dictionary,
        questionnaire=questionnaire,
        rq_map=rq_map,
        dv_types=dv_types,
        warnings=warnings,
        item_count=item_count,
        predictor_count=predictor_count,
        group_count=groups,
    )
