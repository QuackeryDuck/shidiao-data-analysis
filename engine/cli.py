"""数据需求引擎命令行入口。

常用命令::

    py -m engine.cli generate --input doc/input/research_brief.md
    py -m engine.cli validate --input doc/input/research_brief.md
    py -m engine.cli sample --input doc/input/research_brief.md
    py -m engine.cli models
    py -m engine.cli init
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .brief import ResearchBrief, load_brief
from .channels import recommend as recommend_channels
from .hypotheses import generate as generate_hypotheses
from .knowledge import infer_question_types, load_models, recommend_models, requirements_for_models
from .quality import build as build_qc
from .render import render
from .sample import ModelRequirement, allocate_strata, calculate, format_sample_summary, sensitivity_table
from .utils import fmt_num, fmt_pct, write_text
from .variables import analyze

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "doc" / "input" / "research_brief.md"
DEFAULT_OUTPUT = ROOT / "doc" / "output" / "data_requirement.md"
TEMPLATE = ROOT / "doc" / "input" / "research_brief.template.md"


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    cwd_candidate = Path.cwd() / p
    if cwd_candidate.exists():
        return cwd_candidate
    return (ROOT / p).resolve()


def _brief_from_args(args) -> tuple[ResearchBrief, Path]:
    path = _resolve(args.input)
    if not path.exists():
        raise SystemExit(
            f"输入文件不存在：{path}\n"
            f"请先运行 `py -m engine.cli init` 生成模板，或通过 --input 指定文件。"
        )
    return load_brief(path), path


def _infer_types(brief: ResearchBrief) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for q in brief.research_questions:
        out[q.qid] = q.types or infer_question_types(q.text)
    return out


def _print_issues(title: str, issues) -> None:
    print(f"\n{title}（{len(issues)} 项）")
    if not issues:
        print("  - 无")
        return
    for item in issues:
        print(f"  - [{item.level}] {item.field}: {item.message}")


def _pipeline(brief: ResearchBrief):
    rq_types = _infer_types(brief)
    analysis = analyze(brief)
    # 让逐题推荐与第 5.3 节使用同一套问题类型判断，避免出现“综合”或错配模型。
    for item in analysis.rq_map:
        item["types"] = rq_types.get(item["qid"], [])
    sample = calculate(
        confidence=brief.confidence_level,
        margin_error=brief.margin_error,
        proportion=brief.expected_proportion,
        population_size=brief.population_size,
        design_effect=brief.design_effect,
        response_rate=brief.response_rate,
    )
    strata = allocate_strata(brief.strata, sample.n_effective) if brief.strata else []
    core_constructs = [c for c in analysis.constructs if c.role not in {"control", "screening"}]
    rec = recommend_models(
        brief,
        rq_types,
        sample.n_effective,
        dv_types=analysis.dv_types,
        construct_count=len(core_constructs),
        item_count=analysis.item_count,
    )
    requirements: list[ModelRequirement] = requirements_for_models(
        rec.core,
        sample.n_effective,
        n_predictors=max(1, analysis.predictor_count),
        n_items=max(3, analysis.item_count),
        n_groups=max(2, analysis.group_count),
    )
    channel_plan = recommend_channels(brief, sample.n_plan)
    qc_plan = build_qc(brief, channel_plan)
    hypotheses, exploratory = generate_hypotheses(brief, analysis, rec)
    return {
        "rq_types": rq_types,
        "analysis": analysis,
        "sample": sample,
        "strata": strata,
        "rec": rec,
        "requirements": requirements,
        "channel_plan": channel_plan,
        "qc_plan": qc_plan,
        "hypotheses": hypotheses,
        "exploratory": exploratory,
    }


def cmd_generate(args) -> int:
    brief, path = _brief_from_args(args)
    issues = brief.validate()
    data = _pipeline(brief)
    output = _resolve(args.output) if args.output else DEFAULT_OUTPUT
    doc = render(
        brief,
        data["analysis"],
        data["rec"],
        data["sample"],
        data["strata"],
        data["requirements"],
        data["channel_plan"],
        data["qc_plan"],
        data["hypotheses"],
        data["exploratory"],
        issues,
        data["rq_types"],
    )

    if args.stdout:
        print(doc)
    else:
        write_text(output, doc)
        print(f"已生成数据需求文档：{output}")
        print(f"输入文件：{path}")
        print(f"文档行数：{len(doc.splitlines())}；字符数：{len(doc)}")

    sample = data["sample"]
    rec = data["rec"]
    analysis = data["analysis"]
    print("\n生成摘要")
    print(f"  - 研究问题：{len(brief.research_questions)} 个；假设：{len(data['hypotheses'])} 条")
    print(f"  - 变量：{len(analysis.constructs)} 个（核心构念 {len([c for c in analysis.constructs if c.role not in {'control', 'screening'}])} 个）")
    print(f"  - 样本：有效 {fmt_num(sample.n_effective)} 份；计划发放 {fmt_num(sample.n_plan)} 份")
    print(f"  - 核心模型（{len(rec.core)}）：{'、'.join(m.name for m in rec.core)}")
    if rec.optional:
        print(f"  - 可选模型（{len(rec.optional)}）：{'、'.join(m.name for m in rec.optional)}")
    print(f"  - 渠道：{'、'.join(c.name for c in data['channel_plan'].primary + data['channel_plan'].secondary) or '待确认'}")
    _print_issues("待确认事项", issues)

    warnings = analysis.warnings + rec.warnings + data["channel_plan"].warnings + data["qc_plan"].warnings
    if warnings:
        print(f"\n引擎提示（{len(warnings)} 项）")
        for w in warnings:
            print(f"  - {w}")

    if args.json:
        summary = {
            "input": str(path),
            "output": str(output),
            "project": brief.project_name,
            "research_questions": len(brief.research_questions),
            "hypotheses": len(data["hypotheses"]),
            "variables": len(analysis.constructs),
            "sample": sample.as_dict(),
            "core_models": [m.id for m in rec.core],
            "optional_models": [m.id for m in rec.optional],
            "issues": [i.__dict__ for i in issues],
        }
        print("\nJSON_SUMMARY")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def cmd_validate(args) -> int:
    brief, path = _brief_from_args(args)
    issues = brief.validate()
    print(f"输入文件：{path}")
    print(f"项目名称：{brief.project_name}")
    print(f"研究类型：{brief.research_type}")
    print(f"目标总体：{brief.target_population}")
    print(f"研究问题：{len(brief.research_questions)} 个")
    for q in brief.research_questions:
        types = q.types or infer_question_types(q.text)
        print(f"  - {q.qid}: {q.text}  [{'、'.join(types) or '未识别'}]")
    print(f"构念：{len(brief.constructs)} 个")
    print(f"数据来源：{'、'.join(brief.data_sources)}")
    _print_issues("校验结果", issues)
    fatal = [i for i in issues if i.level == "error"]
    return 1 if fatal else 0


def cmd_sample(args) -> int:
    brief = None
    if args.input:
        brief, _ = _brief_from_args(args)
    confidence = args.confidence if args.confidence is not None else (brief.confidence_level if brief else 0.95)
    margin = args.error if args.error is not None else (brief.margin_error if brief else 0.05)
    proportion = args.proportion if args.proportion is not None else (brief.expected_proportion if brief else 0.5)
    population = args.population if args.population is not None else (brief.population_size if brief else None)
    deff = args.deff if args.deff is not None else (brief.design_effect if brief else 1.2)
    rate = args.rate if args.rate is not None else (brief.response_rate if brief else 0.9)

    result = calculate(confidence, margin, proportion, population, deff, rate)
    print(format_sample_summary(result))
    print(f"基础样本量 n0 = {fmt_num(result.n_base)}（向上取整 {fmt_num(result.n_base_rounded)}）")
    if result.n_fpc is not None:
        print(f"有限总体修正后 n0' = {fmt_num(result.n_fpc)}")
    print(f"所需有效样本 n_eff = {fmt_num(result.n_effective)}；计划发放 n_plan = {fmt_num(result.n_plan)}")
    print("\n敏感性分析")
    rows = sensitivity_table([0.90, 0.95, 0.99], [0.03, 0.04, 0.05], proportion, population, deff, rate)
    print(f"{'置信水平':<10}{'允许误差':<12}{'z':<8}{'n_base':<10}{'n_eff':<10}{'n_plan':<10}")
    for r in rows:
        print(
            f"{fmt_pct(r['confidence'], 0):<10}"
            f"{'±' + fmt_pct(r['margin_error'], 1):<12}"
            f"{r['z']:<8.3f}"
            f"{fmt_num(r['n_base']):<10}"
            f"{fmt_num(r['n_effective']):<10}"
            f"{fmt_num(r['n_plan']):<10}"
        )
    if args.json:
        print("\nJSON_SUMMARY")
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
    return 0


def cmd_models(args) -> int:
    models = load_models()
    rows = list(models.values())
    if args.level:
        rows = [m for m in rows if m.level == args.level]
    if args.search:
        needle = args.search.lower()
        rows = [m for m in rows if needle in f"{m.name} {m.en} {m.id} {m.category}".lower()]
    rows.sort(key=lambda m: (m.chapter, m.id))
    print(f"模型知识库：{len(rows)} / {len(models)} 个")
    print(f"{'ID':<22}{'名称':<18}{'难度':<6}{'最低样本':<10}{'类别'}")
    for m in rows:
        print(f"{m.id:<22}{m.name:<18}{m.level:<6}{str(m.min_sample or '—'):<10}{m.category}")
    if args.json:
        print("\nJSON_SUMMARY")
        print(json.dumps([m.__dict__ for m in rows], ensure_ascii=False, indent=2))
    return 0


def cmd_init(args) -> int:
    target = _resolve(args.output) if args.output else DEFAULT_INPUT
    if target.exists() and not args.force:
        print(f"文件已存在：{target}\n如需覆盖，请加 --force。")
        return 1
    if not TEMPLATE.exists():
        print(f"模板不存在：{TEMPLATE}")
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    write_text(target, TEMPLATE.read_text(encoding="utf-8"))
    print(f"已创建输入文件：{target}")
    print("请填写 frontmatter 与各章节后运行：py -m engine.cli generate")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="py -m engine.cli",
        description="市场调查数据需求生成引擎（标准库实现）",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="生成 Markdown 数据需求文档")
    p_gen.add_argument("--input", "-i", default=str(DEFAULT_INPUT), help="输入文件（.md 或 .json）")
    p_gen.add_argument("--output", "-o", default=str(DEFAULT_OUTPUT), help="输出 Markdown 路径")
    p_gen.add_argument("--stdout", action="store_true", help="输出到终端而不写文件")
    p_gen.add_argument("--json", action="store_true", help="额外输出 JSON 摘要")
    p_gen.set_defaults(func=cmd_generate)

    p_val = sub.add_parser("validate", help="校验输入文件并查看识别结果")
    p_val.add_argument("--input", "-i", default=str(DEFAULT_INPUT))
    p_val.set_defaults(func=cmd_validate)

    p_sample = sub.add_parser("sample", help="单独计算样本量")
    p_sample.add_argument("--input", "-i", default=None, help="可选：从输入文件读取参数")
    p_sample.add_argument("--confidence", type=float, default=None, help="置信水平，如 0.95")
    p_sample.add_argument("--error", type=float, default=None, help="允许误差，如 0.05")
    p_sample.add_argument("--proportion", type=float, default=None, help="预估比例，默认 0.5")
    p_sample.add_argument("--population", type=int, default=None, help="总体规模")
    p_sample.add_argument("--deff", type=float, default=None, help="设计效应，默认 1.2")
    p_sample.add_argument("--rate", type=float, default=None, help="预计有效率，默认 0.9")
    p_sample.add_argument("--json", action="store_true")
    p_sample.set_defaults(func=cmd_sample)

    p_models = sub.add_parser("models", help="列出模型知识库")
    p_models.add_argument("--level", choices=["基础", "进阶", "高阶"], default=None)
    p_models.add_argument("--search", default=None, help="按名称/ID/类别搜索")
    p_models.add_argument("--json", action="store_true")
    p_models.set_defaults(func=cmd_models)

    p_init = sub.add_parser("init", help="从模板创建输入文件")
    p_init.add_argument("--output", "-o", default=str(DEFAULT_INPUT))
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except BrokenPipeError:
        return 0
    except SystemExit:
        raise
    except Exception as exc:  # 给 CLI 用户一个可读的错误，而不是整段 traceback
        print(f"执行失败：{exc.__class__.__name__}: {exc}", file=sys.stderr)
        if str(exc):
            print("可使用 --help 查看用法；若问题持续，请检查输入文件格式。", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
