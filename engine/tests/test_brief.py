"""输入解析测试：模板、别名、构念表、分层与 JSON。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from engine.brief import load_brief

ROOT = Path(__file__).resolve().parents[2]


class MarkdownBriefTest(unittest.TestCase):
    def test_template_parses(self):
        b = load_brief(ROOT / "doc" / "input" / "research_brief.template.md")
        self.assertEqual(b.project_name, "请填写项目名称")
        self.assertEqual(len(b.research_questions), 3)
        self.assertEqual(len(b.constructs), 9)
        self.assertEqual(len(b.strata), 4)
        self.assertEqual(sum(s.proportion or 0 for s in b.strata), 1.0)

    def test_example_roles_and_data_sources(self):
        b = load_brief(ROOT / "doc" / "input" / "example_research_brief.md")
        self.assertEqual(len(b.research_questions), 6)
        roles = {c.name: c.role for c in b.constructs}
        self.assertEqual(roles["购买意愿"], "dependent")
        self.assertEqual(roles["品牌信任"], "mediator")
        self.assertEqual(roles["月生活费"], "moderator")
        self.assertEqual(roles["性别"], "control")
        self.assertIn("一手问卷", b.data_sources)
        self.assertTrue(b.has_text_data())
        self.assertTrue(b.has_primary_survey())

    def test_section_aliases_and_comments(self):
        text = """---
project_name: 别名测试
data_sources: [一手问卷]
---

<!-- 这段注释不能被当成章节 -->

## 研究目的

- 了解消费者态度
- 比较不同群体

## 变量

| 变量 | 角色 | 题项数 | 量表 |
| --- | --- | --- | --- |
| 满意度 | 因变量 | 3 | 5 级李克特 |
| 服务质量 | 自变量 | 4 | 5 级李克特 |
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "brief.md"
            p.write_text(text, encoding="utf-8")
            b = load_brief(p)
        self.assertEqual(b.project_name, "别名测试")
        self.assertEqual(len(b.research_questions), 2)  # 研究目标回退为研究问题
        self.assertEqual(len(b.constructs), 2)
        self.assertEqual(b.constructs[0].role, "dependent")

    def test_strata_supports_percent_and_count(self):
        text = """---
project_name: 分层测试
---

## 研究问题

1. RQ1：满意度如何？

## 分层配额

- 大一：120人
- 大二：80
- 大三：25%
"""
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "brief.md"
            p.write_text(text, encoding="utf-8")
            b = load_brief(p)
        self.assertEqual(b.strata[0].population, 120)
        self.assertAlmostEqual(b.strata[1].proportion or 0, 0.8)
        self.assertAlmostEqual(b.strata[2].proportion or 0, 0.25)

    def test_missing_project_name_is_error(self):
        text = "---\nproject_name: 待确认\n---\n\n## 研究问题\n1. RQ1：消费者满意度如何？\n"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "brief.md"
            p.write_text(text, encoding="utf-8")
            b = load_brief(p)
        issues = b.validate()
        self.assertTrue(any(i.level == "error" and i.field == "project_name" for i in issues))

    def test_no_questions_or_objectives_is_error(self):
        text = "---\nproject_name: 空研究\n---\n\n## 研究背景\n只有背景。\n"
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "brief.md"
            p.write_text(text, encoding="utf-8")
            b = load_brief(p)
        issues = b.validate()
        self.assertTrue(any(i.level == "error" and i.field == "research_questions" for i in issues))


class JsonBriefTest(unittest.TestCase):
    def test_json_roundtrip(self):
        data = {
            "project_name": "JSON 测试",
            "target_population": "本市消费者",
            "data_sources": ["一手问卷"],
            "research_questions": [
                {"qid": "RQ1", "text": "消费者满意度如何？"},
                {"qid": "RQ2", "text": "不同性别消费者的满意度是否存在差异？"},
            ],
            "constructs": [
                {"name": "满意度", "role": "dependent", "items": 4, "scale": "5 级李克特", "measure": "连续"},
                {"name": "服务质量", "role": "independent", "items": 5, "scale": "5 级李克特", "measure": "连续"},
                {"name": "性别", "role": "control", "items": 1, "scale": "单选", "measure": "定类"},
            ],
            "strata": [{"name": "男", "ratio": 0.5}, {"name": "女", "ratio": 0.5}],
            "preferred_methods": ["多元线性回归"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "brief.json"
            p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            b = load_brief(p)
        self.assertEqual(b.project_name, "JSON 测试")
        self.assertEqual(len(b.research_questions), 2)
        self.assertEqual(b.constructs[0].role, "dependent")
        self.assertEqual(len(b.strata), 2)
        self.assertEqual(b.preferred_methods, ["多元线性回归"])


if __name__ == "__main__":
    unittest.main()
