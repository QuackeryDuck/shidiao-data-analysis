"""端到端测试：示例输入 → 数据需求 Markdown。"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from engine import cli

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "doc" / "input" / "example_research_brief.md"


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.tmp.name) / "data_requirement.md"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.main(
                [
                    "generate",
                    "--input",
                    str(EXAMPLE),
                    "--output",
                    str(cls.output),
                ]
            )
        cls.stdout = buf.getvalue()
        assert code == 0, cls.stdout
        cls.doc = cls.output.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_output_exists_and_large(self):
        self.assertTrue(self.output.is_file())
        self.assertGreater(len(self.doc), 30000)
        self.assertIn("# 《大学生现制咖啡消费行为与品牌选择研究》数据需求文档", self.doc)

    def test_six_required_sections(self):
        required = [
            "## 2. 研究假设",
            "## 3. 变量确定",
            "## 4. 样本与抽样设计",
            "## 5. 模型与方法确定（重点）",
            "## 6. 调查渠道",
            "## 7. 质量控制措施",
        ]
        for heading in required:
            self.assertIn(heading, self.doc)

    def test_supporting_sections(self):
        for heading in ["## 0. 文档摘要", "## 8. 数据交付要求", "## 9. 进度、分工与风险", "## 10. 待确认事项与假设清单"]:
            self.assertIn(heading, self.doc)
        self.assertIn("附录 A", self.doc)
        self.assertIn("附录 B", self.doc)
        self.assertIn("附录 C", self.doc)

    def test_sample_numbers_consistent(self):
        self.assertIn("461", self.doc)
        self.assertIn("543", self.doc)
        self.assertIn("有限总体修正", self.doc)
        self.assertIn("设计效应", self.doc)

    def test_model_rq_mapping_is_specific(self):
        def section(model_id: str) -> str:
            start = self.doc.index(f"#### {model_id}")
            nxt = self.doc.find("\n#### ", start + 5)
            nxt = nxt if nxt != -1 else self.doc.find("\n### ", start + 5)
            return self.doc[start:nxt]

        linear = section("5.4.10")
        sem = section("5.4.13")
        for block, name in [(linear, "线性回归"), (sem, "SEM")]:
            rq_line = next(line for line in block.splitlines() if "对应研究问题" in line)
            self.assertNotIn("RQ2", rq_line, f"{name} 不应绑定纯组间差异问题")
            self.assertIn("RQ3", rq_line)

    def test_hypotheses_and_variables_present(self):
        self.assertIn("假设体系", self.doc)
        self.assertIn("变量字典", self.doc)
        self.assertIn("变量与模型对应关系", self.doc)
        self.assertIn("品牌信任", self.doc)
        self.assertIn("月生活费", self.doc)

    def test_channels_and_qc(self):
        self.assertIn("渠道组合策略", self.doc)
        self.assertIn("质量控制措施", self.doc)
        self.assertIn("无效问卷", self.doc)
        self.assertIn("验收标准", self.doc)

    def test_summary_printed(self):
        self.assertIn("已生成数据需求文档", self.stdout)
        self.assertIn("核心模型", self.stdout)
        self.assertIn("计划发放", self.stdout)


if __name__ == "__main__":
    unittest.main()
