"""研究需求输入解析：支持 Markdown（frontmatter + 章节）与 JSON。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .utils import (
    as_float,
    as_int,
    clean_inline,
    normalize_confidence,
    normalize_error,
    normalize_rate,
    read_text,
    split_inline_list,
    strip_bullet,
)


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass
class Construct:
    name: str
    definition: str = ""
    role: str = ""  # dependent / independent / mediator / moderator / control / screening
    items: int = 4
    scale: str = "5 级李克特"
    measure: str = ""  # 定类 / 定序 / 连续 / 文本 / 多重响应
    source: str = "一手问卷"
    dimensions: list[str] = field(default_factory=list)
    notes: str = ""
    inferred: bool = False

    def role_cn(self) -> str:
        return {
            "dependent": "因变量",
            "independent": "自变量",
            "mediator": "中介变量",
            "moderator": "调节变量",
            "control": "控制变量",
            "screening": "筛选变量",
            "exploratory": "探索性变量",
        }.get(self.role, self.role or "待定")


@dataclass
class ResearchQuestion:
    qid: str
    text: str
    types: list[str] = field(default_factory=list)
    source: str = "input"


@dataclass
class Hypothesis:
    hid: str
    text: str
    kind: str = "影响关系"
    rq_id: str = ""
    iv: list[str] = field(default_factory=list)
    dv: list[str] = field(default_factory=list)
    mediator: list[str] = field(default_factory=list)
    moderator: list[str] = field(default_factory=list)
    direction: str = "显著"
    method: str = ""
    theory: str = ""
    source: str = "generated"


@dataclass
class Strata:
    name: str
    proportion: float | None = None
    population: int | None = None


@dataclass
class ValidationIssue:
    level: str
    field: str
    message: str


@dataclass
class ResearchBrief:
    project_name: str = ""
    project_slug: str = ""
    competition: str = "正大杯全国大学生市场调查与分析大赛"
    research_type: str = "市场调查"
    industry: str = "待确认"
    region: str = "待确认"
    target_population: str = "待确认"
    survey_unit: str = "个人"
    data_sources: list[str] = field(default_factory=list)
    survey_mode: str = "线上为主"
    confidence_level: float = 0.95
    margin_error: float = 0.05
    expected_proportion: float = 0.5
    population_size: int | None = None
    design_effect: float = 1.2
    response_rate: float = 0.9
    budget_cny: float | None = None
    timeline_weeks: int | None = None
    team_size: int | None = None
    background: str = ""
    research_questions: list[ResearchQuestion] = field(default_factory=list)
    objectives: list[str] = field(default_factory=list)
    constructs: list[Construct] = field(default_factory=list)
    existing_hypotheses: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    preferred_methods: list[str] = field(default_factory=list)
    notes: str = ""
    strata: list[Strata] = field(default_factory=list)
    source_path: str = ""
    raw_text: str = ""

    # -- 派生信息 ---------------------------------------------------------
    def text_blob(self) -> str:
        parts = [
            self.project_name,
            self.research_type,
            self.industry,
            self.region,
            self.target_population,
            self.background,
            " ".join(q.text for q in self.research_questions),
            " ".join(self.objectives),
            " ".join(c.name + c.definition for c in self.constructs),
            " ".join(self.constraints),
            " ".join(self.preferred_methods),
            self.notes,
        ]
        return "\n".join(p for p in parts if p)

    def has_primary_survey(self) -> bool:
        if any("二手" in s for s in self.data_sources):
            return any(("问卷" in s or "一手" in s) for s in self.data_sources) or not self.data_sources
        return not self.data_sources or any(("问卷" in s or "一手" in s or "访谈" in s) for s in self.data_sources)

    def has_text_data(self) -> bool:
        blob = self.text_blob()
        return any(k in blob for k in ["文本", "评论", "舆情", "爬虫", "内容分析"]) or any(
            "文本" in s for s in self.data_sources
        )

    def has_secondary_data(self) -> bool:
        blob = self.text_blob()
        return any(k in blob for k in ["二手", "行业报告", "统计年鉴", "百度指数", "宏观"]) or any(
            "二手" in s for s in self.data_sources
        )

    def default_strata(self) -> list[Strata]:
        if self.strata:
            return self.strata
        return []

    def validate(self) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not self.project_name or self.project_name.strip() in {"待确认", "请填写项目名称"}:
            issues.append(ValidationIssue("error", "project_name", "缺少项目名称，无法生成文档标题。"))
        if not self.research_questions and not self.objectives:
            issues.append(
                ValidationIssue(
                    "error",
                    "research_questions",
                    "缺少研究问题与研究目标，无法确定变量、假设与模型。",
                )
            )
        if not self.target_population or self.target_population == "待确认":
            issues.append(
                ValidationIssue("warning", "target_population", "未填写目标总体，抽样与渠道建议将按一般消费者处理。")
            )
        if not self.constructs:
            issues.append(
                ValidationIssue(
                    "warning",
                    "constructs",
                    "未填写核心构念，引擎将从研究问题中推断变量，需人工复核。",
                )
            )
        if not self.data_sources:
            issues.append(
                ValidationIssue("warning", "data_sources", "未填写数据来源，默认按一手问卷为主处理。")
            )
        if self.margin_error > 0.1:
            issues.append(ValidationIssue("warning", "margin_error", "允许误差大于 10%，样本量可能偏小。"))
        if self.response_rate < 0.5:
            issues.append(ValidationIssue("warning", "response_rate", "预计有效率低于 50%，请核实依据。"))
        return issues


# ---------------------------------------------------------------------------
# 解析器
# ---------------------------------------------------------------------------

SECTION_ALIASES = {
    "background": ["研究背景", "项目背景", "背景", "研究缘起", "background"],
    "research_questions": ["研究问题", "核心问题", "研究议题", "待回答的问题", "researchquestions", "rqs"],
    "objectives": ["研究目标", "研究目的", "研究任务", "objectives", "goals"],
    "constructs": ["调查内容", "核心构念", "研究变量", "变量设计", "构念", "变量", "constructs", "variables"],
    "existing_hypotheses": ["研究假设", "已有假设", "假设", "hypotheses"],
    "constraints": ["约束条件", "研究约束", "条件限制", "限制条件", "constraints"],
    "preferred_methods": ["分析方法倾向", "拟用方法", "方法偏好", "分析方法", "preferredmethods", "methods"],
    "notes": ["补充说明", "其他说明", "备注", "notes"],
    "strata": ["分层", "配额", "分层配额", "抽样分层", "strata", "quotas"],
    "basic": ["基本信息", "项目信息", "研究概况", "basicinfo"],
}

def _norm_heading(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"[\s\-_/（）()【】\[\]：:．.]+", "", text)
    return text


ALIAS_TO_KEY = {}
for key, aliases in SECTION_ALIASES.items():
    for alias in aliases:
        ALIAS_TO_KEY[_norm_heading(alias)] = key


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.startswith("[") and value.endswith("]"):
        return split_inline_list(value)
    low = value.lower()
    if low in {"true", "yes", "是"}:
        return True
    if low in {"false", "no", "否"}:
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """解析简单的 YAML frontmatter（仅支持标量、行内列表与引号）。"""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() in {"---", "..."}:
            end = i
            break
    if end is None:
        return {}, text
    meta: dict[str, Any] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if not key:
            continue
        meta[key] = _parse_scalar(value)
    return meta, "\n".join(lines[end + 1 :])


def _split_sections(body: str) -> list[tuple[str, str]]:
    """按 Markdown 标题切分章节，返回 (标题, 内容)。"""
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if m:
            if current_title or current_lines:
                sections.append((current_title, current_lines))
            current_title = m.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_title or current_lines:
        sections.append((current_title, current_lines))
    return [(title, "\n".join(lines).strip()) for title, lines in sections]


def _parse_list_section(content: str) -> list[str]:
    """把章节内容解析为条目列表，支持项目符号、编号、表格首列。"""
    content = (content or "").strip()
    if not content:
        return []
    items: list[str] = []
    # Markdown 表格：优先取第一列（去掉表头与分隔行）
    table_lines = [ln for ln in content.splitlines() if ln.strip().startswith("|")]
    if len(table_lines) >= 2:
        rows = []
        for ln in table_lines:
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if cells and re.fullmatch(r":?-{2,}:?", cells[0].replace(" ", "")):
                continue
            rows.append(cells)
        if rows:
            # 第一行若像表头则跳过
            first = rows[0]
            if any(h in first[0] for h in ["序号", "编号", "问题", "目标", "构念", "变量", "假设", "分层", "渠道"]):
                rows = rows[1:]
            for row in rows:
                if row and row[0]:
                    items.append(" | ".join(row))
            if items:
                return items
    for ln in content.splitlines():
        raw = ln.strip()
        if not raw:
            continue
        if re.match(r"^(?:[-*+•·]|\d+[.、)）]|[（(]\d+[）)]|\[[ xX]\])", raw):
            item = strip_bullet(raw)
            if item:
                items.append(item)
        elif items:
            # 续行合并到上一条
            items[-1] = items[-1] + " " + clean_inline(raw)
    if not items:
        # 没有列表符号时按行处理
        for ln in content.splitlines():
            s = clean_inline(ln)
            if s and not s.startswith("#"):
                items.append(s)
    return items


def _parse_constructs(content: str) -> list[Construct]:
    """解析构念/变量章节，支持表格与“名称：定义”两种写法。"""
    content = (content or "").strip()
    if not content:
        return []
    constructs: list[Construct] = []
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]

    # 表格解析
    table_lines = [ln for ln in lines if ln.startswith("|")]
    if len(table_lines) >= 2:
        header = [c.strip() for c in table_lines[0].strip("|").split("|")]
        col = _construct_columns(header)
        for ln in table_lines[1:]:
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if not cells or re.fullmatch(r":?-{2,}:?", cells[0].replace(" ", "")):
                continue
            name = _cell(cells, col.get("name"))
            if not name or name in {"构念", "变量", "名称", "变量名称"}:
                continue
            constructs.append(
                Construct(
                    name=name,
                    definition=_cell(cells, col.get("definition")),
                    role=_role_from_text(_cell(cells, col.get("role"))),
                    items=as_int(_cell(cells, col.get("items")), 4) or 4,
                    scale=_cell(cells, col.get("scale")) or "5 级李克特",
                    measure=_cell(cells, col.get("measure")),
                    source=_cell(cells, col.get("source")) or "一手问卷",
                    dimensions=split_inline_list(_cell(cells, col.get("dimensions"))),
                    notes=_cell(cells, col.get("notes")),
                )
            )
        if constructs:
            return constructs

    # 列表解析
    for raw in lines:
        if raw.startswith("|"):
            continue
        item = strip_bullet(raw)
        if not item:
            continue
        if "|" in item:
            parts = [p.strip() for p in item.split("|")]
            name = parts[0]
            role = _role_from_text(parts[1]) if len(parts) > 1 else ""
            definition = parts[2] if len(parts) > 2 else ""
            items_n = as_int(parts[3], 4) if len(parts) > 3 else 4
            scale = parts[4] if len(parts) > 4 else "5 级李克特"
            constructs.append(
                Construct(
                    name=name,
                    definition=definition,
                    role=role,
                    items=items_n or 4,
                    scale=scale,
                )
            )
        elif "：" in item:
            name, _, definition = item.partition("：")
            constructs.append(Construct(name=clean_inline(name), definition=clean_inline(definition)))
        elif ":" in item:
            name, _, definition = item.partition(":")
            constructs.append(Construct(name=clean_inline(name), definition=clean_inline(definition)))
        else:
            constructs.append(Construct(name=item))
    return [c for c in constructs if c.name]


def _construct_columns(header: list[str]) -> dict[str, int]:
    col: dict[str, int] = {}
    for i, h in enumerate(header):
        hh = _norm_heading(h)
        if any(k in hh for k in ["构念", "变量", "名称", "name"]):
            col.setdefault("name", i)
        if any(k in hh for k in ["角色", "类型", "role", "type"]):
            col.setdefault("role", i)
        if any(k in hh for k in ["定义", "操作化", "说明", "definition"]):
            col.setdefault("definition", i)
        if any(k in hh for k in ["题项", "题目", "items", "题量"]):
            col.setdefault("items", i)
        if any(k in hh for k in ["量表", "scale", "测量"]):
            col.setdefault("scale", i)
        if any(k in hh for k in ["测量层级", "数据类型", "measure"]):
            col.setdefault("measure", i)
        if any(k in hh for k in ["来源", "source"]):
            col.setdefault("source", i)
        if any(k in hh for k in ["维度", "dimension"]):
            col.setdefault("dimensions", i)
        if any(k in hh for k in ["备注", "notes"]):
            col.setdefault("notes", i)
    return col


def _cell(cells: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(cells):
        return ""
    return cells[idx].strip()


def _role_from_text(text: str) -> str:
    t = (text or "").strip().lower()
    if not t:
        return ""
    if any(k in t for k in ["因变量", "dependent", "dv", "结果变量", "被解释"]):
        return "dependent"
    if any(k in t for k in ["中介", "mediator", "med"]):
        return "mediator"
    if any(k in t for k in ["调节", "moderator", "mod"]):
        return "moderator"
    if any(k in t for k in ["控制", "control", "cv"]):
        return "control"
    if any(k in t for k in ["筛选", "甄别", "screening"]):
        return "screening"
    if any(k in t for k in ["自变量", "independent", "iv", "解释变量", "前因"]):
        return "independent"
    if any(k in t for k in ["探索", "exploratory"]):
        return "exploratory"
    return ""


def _parse_strata(content: str) -> list[Strata]:
    content = (content or "").strip()
    if not content:
        return []
    out: list[Strata] = []
    for raw in content.splitlines():
        item = strip_bullet(raw)
        if not item or item.startswith("|"):
            continue
        # 名称：比例 / 名称 | 比例 / 名称 比例%
        m = re.match(r"(.+?)[：:|]\s*([\d.]+)\s*([%％人]?)$", item)
        if m:
            name = clean_inline(m.group(1))
            val = as_float(m.group(2), 0.0) or 0.0
            unit = m.group(3)
            has_pct = unit in {"%", "％"} or "%" in item or "％" in item
            has_count = unit == "人" or val > 100
            if has_count:
                # “120人”或大于 100 的数值视为该层人数/总体规模
                out.append(Strata(name=name, population=int(round(val))))
            else:
                # “25%”“25”“0.25”都表示比例
                proportion = val / 100 if (has_pct or val > 1) else val
                out.append(Strata(name=name, proportion=min(max(proportion, 0), 1)))
        else:
            out.append(Strata(name=item))
    return out


def _assign_ids(items: list[str], prefix: str) -> list[str]:
    out = []
    for i, item in enumerate(items, 1):
        item = re.sub(r"^(?:RQ|R|Q|H|目标|问题)\s*\d+\s*[：:.、-]\s*", "", item, flags=re.I)
        item = re.sub(r"^\d+\s*[：:.、)）]\s*", "", item)
        item = clean_inline(item)
        if item:
            out.append(item)
    return out


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [clean_inline(str(v)) for v in value if str(v).strip()]
    if isinstance(value, str):
        return split_inline_list(value) if any(sep in value for sep in ",，、;；|") else [value.strip()] if value.strip() else []
    return [str(value)]


# ---------------------------------------------------------------------------
# 对外入口
# ---------------------------------------------------------------------------


def load_brief(path: str | Path) -> ResearchBrief:
    p = Path(path)
    text = read_text(p)
    if p.suffix.lower() == ".json":
        return _from_json(json.loads(text), str(p), text)
    meta, body = parse_frontmatter(text)
    # 章节内的 HTML 注释只是填写说明，不能进入列表/表格解析
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    sections = _split_sections(body)

    b = ResearchBrief(source_path=str(p), raw_text=text)
    _apply_meta(b, meta)

    sec_map: dict[str, str] = {}
    for title, content in sections:
        key = ALIAS_TO_KEY.get(_norm_heading(title))
        if key and content:
            sec_map[key] = content
        elif not b.project_name and title and not content:
            b.project_name = title

    if "basic" in sec_map:
        # 基本信息章节里的“键：值”行
        for ln in sec_map["basic"].splitlines():
            item = strip_bullet(ln)
            if "：" in item:
                k, _, v = item.partition("：")
            elif ":" in item:
                k, _, v = item.partition(":")
            else:
                continue
            _apply_meta(b, {k.strip(): _parse_scalar(v)}, overwrite=False)

    if "background" in sec_map:
        b.background = sec_map["background"]
    if "notes" in sec_map:
        b.notes = sec_map["notes"]
    if "research_questions" in sec_map:
        b.research_questions = _to_rqs(_parse_list_section(sec_map["research_questions"]))
    if "objectives" in sec_map:
        b.objectives = _assign_ids(_parse_list_section(sec_map["objectives"]), "O")
    if "constructs" in sec_map:
        b.constructs = _parse_constructs(sec_map["constructs"])
    if "existing_hypotheses" in sec_map:
        b.existing_hypotheses = _assign_ids(_parse_list_section(sec_map["existing_hypotheses"]), "H")
    if "constraints" in sec_map:
        b.constraints = _assign_ids(_parse_list_section(sec_map["constraints"]), "C")
    if "preferred_methods" in sec_map:
        b.preferred_methods = _assign_ids(_parse_list_section(sec_map["preferred_methods"]), "M")
    if "strata" in sec_map:
        b.strata = _parse_strata(sec_map["strata"])

    # 若没有研究问题，用研究目标替代
    if not b.research_questions and b.objectives:
        b.research_questions = [ResearchQuestion(qid=f"RQ{i}", text=t, source="objectives") for i, t in enumerate(b.objectives, 1)]
    if not b.objectives and b.research_questions:
        b.objectives = [q.text for q in b.research_questions]

    _postprocess(b)
    return b


def _to_rqs(items: list[str]) -> list[ResearchQuestion]:
    out = []
    for i, item in enumerate(items, 1):
        text = re.sub(r"^(?:RQ|R|Q)\s*\d+\s*[：:.、-]\s*", "", item, flags=re.I)
        text = re.sub(r"^\d+\s*[：:.、)）]\s*", "", text)
        text = clean_inline(text)
        if text:
            out.append(ResearchQuestion(qid=f"RQ{i}", text=text))
    return out


def _apply_meta(b: ResearchBrief, meta: dict[str, Any], overwrite: bool = True) -> None:
    def setv(attr: str, value: Any, transform=None):
        if value is None or value == "":
            return
        if not overwrite and getattr(b, attr):
            return
        if transform:
            value = transform(value)
        setattr(b, attr, value)

    setv("project_name", meta.get("project_name") or meta.get("项目名称") or meta.get("title"))
    setv("project_slug", meta.get("project_slug") or meta.get("slug"))
    setv("competition", meta.get("competition") or meta.get("竞赛名称"))
    setv("research_type", meta.get("research_type") or meta.get("研究类型"))
    setv("industry", meta.get("industry") or meta.get("行业"))
    setv("region", meta.get("region") or meta.get("地区") or meta.get("区域"))
    setv("target_population", meta.get("target_population") or meta.get("目标总体") or meta.get("研究对象"))
    setv("survey_unit", meta.get("survey_unit") or meta.get("调查单位"))
    setv("data_sources", meta.get("data_sources") or meta.get("数据来源"), _coerce_list)
    setv("survey_mode", meta.get("survey_mode") or meta.get("调查方式"))
    setv("confidence_level", meta.get("confidence_level") or meta.get("置信水平"), normalize_confidence)
    setv("margin_error", meta.get("margin_error") or meta.get("允许误差"), normalize_error)
    setv("expected_proportion", meta.get("expected_proportion") or meta.get("预估比例"), lambda v: min(max(as_float(v, 0.5) or 0.5, 0.01), 0.99))
    setv("population_size", meta.get("population_size") or meta.get("总体规模"), lambda v: as_int(v))
    setv("design_effect", meta.get("design_effect") or meta.get("设计效应"), lambda v: max(as_float(v, 1.2) or 1.2, 1.0))
    setv("response_rate", meta.get("response_rate") or meta.get("预计有效率"), normalize_rate)
    setv("budget_cny", meta.get("budget_cny") or meta.get("预算"), lambda v: as_float(v))
    setv("timeline_weeks", meta.get("timeline_weeks") or meta.get("周期"), lambda v: as_int(v))
    setv("team_size", meta.get("team_size") or meta.get("团队人数"), lambda v: as_int(v))
    setv("background", meta.get("background") or meta.get("研究背景"))
    setv("notes", meta.get("notes") or meta.get("补充说明"))
    setv("research_questions", meta.get("research_questions"), lambda v: _to_rqs(_coerce_list(v)))
    setv("objectives", meta.get("objectives"), lambda v: _assign_ids(_coerce_list(v), "O"))
    setv("existing_hypotheses", meta.get("hypotheses") or meta.get("existing_hypotheses"), lambda v: _assign_ids(_coerce_list(v), "H"))
    setv("constraints", meta.get("constraints"), lambda v: _assign_ids(_coerce_list(v), "C"))
    setv("preferred_methods", meta.get("preferred_methods") or meta.get("methods"), lambda v: _assign_ids(_coerce_list(v), "M"))


def _postprocess(b: ResearchBrief) -> None:
    if not b.project_name:
        if b.source_path:
            stem = Path(b.source_path).stem
            b.project_name = stem.replace("_", " ").replace("-", " ").strip() or "市场调查项目"
    if not b.project_slug:
        b.project_slug = re.sub(r"[^\w一-鿿-]+", "-", b.project_name).strip("-") or "data-requirement"
    if not b.data_sources:
        inferred = []
        blob = b.text_blob()
        if b.has_primary_survey() or any(k in blob for k in ["问卷", "调查", "访谈"]):
            inferred.append("一手问卷")
        if any(k in blob for k in ["二手", "行业报告", "统计年鉴", "百度指数", "宏观"]):
            inferred.append("二手行业数据")
        if any(k in blob for k in ["评论", "文本", "舆情", "爬虫"]):
            inferred.append("公开文本/评论")
        b.data_sources = inferred or ["一手问卷"]
    if not b.survey_mode:
        b.survey_mode = "线上为主" if any("问卷" in s for s in b.data_sources) else "混合"
    if not b.target_population:
        b.target_population = "待确认"


def _from_json(data: dict[str, Any], path: str, raw: str) -> ResearchBrief:
    b = ResearchBrief(source_path=path, raw_text=raw)
    _apply_meta(b, data)
    # 结构化字段
    if isinstance(data.get("constructs"), list):
        for item in data["constructs"]:
            if isinstance(item, dict):
                b.constructs.append(
                    Construct(
                        name=str(item.get("name", "")).strip(),
                        definition=str(item.get("definition", "")).strip(),
                        role=_role_from_text(str(item.get("role", ""))),
                        items=as_int(item.get("items"), 4) or 4,
                        scale=str(item.get("scale", "5 级李克特")),
                        measure=str(item.get("measure", "")),
                        source=str(item.get("source", "一手问卷")),
                        dimensions=[str(x) for x in item.get("dimensions", [])],
                        notes=str(item.get("notes", "")),
                    )
                )
    if isinstance(data.get("strata"), list):
        for item in data["strata"]:
            if isinstance(item, dict) and item.get("name"):
                b.strata.append(
                    Strata(
                        name=str(item["name"]),
                        proportion=as_float(item.get("proportion")),
                        population=as_int(item.get("population")),
                    )
                )
    if not b.research_questions and b.objectives:
        b.research_questions = [ResearchQuestion(qid=f"RQ{i}", text=t, source="objectives") for i, t in enumerate(b.objectives, 1)]
    _postprocess(b)
    return b
