"""问题类型识别、模型推荐与样本门槛测试。"""

from __future__ import annotations

import unittest

from engine.brief import Construct, ResearchBrief
from engine.knowledge import (
    infer_question_types,
    load_models,
    recommend_models,
    requirements_for_models,
)


def _brief(preferred=None) -> ResearchBrief:
    return ResearchBrief(
        project_name="测试项目",
        target_population="某市消费者",
        data_sources=["一手问卷"],
        constructs=[
            Construct(name="购买意愿", role="dependent", items=4, scale="5 级李克特", measure="连续"),
            Construct(name="产品品质", role="independent", items=5, scale="5 级李克特", measure="连续"),
            Construct(name="品牌信任", role="mediator", items=4, scale="5 级李克特", measure="连续"),
            Construct(name="月生活费", role="moderator", items=1, scale="单选", measure="定序"),
        ],
        preferred_methods=preferred or [],
    )


class QuestionTypeTest(unittest.TestCase):
    def test_group_difference(self):
        self.assertIn("group_difference", infer_question_types("不同年级学生的消费频率是否存在显著差异？"))

    def test_driver(self):
        self.assertIn("driver", infer_question_types("产品品质对购买意愿有何影响？"))

    def test_mediation(self):
        types = infer_question_types("品牌信任是否在产品品质与购买意愿之间起中介作用？")
        self.assertIn("mediation", types)

    def test_moderation(self):
        self.assertIn("moderation", infer_question_types("月生活费是否调节价格感知对购买意愿的影响？"))

    def test_text(self):
        self.assertIn("text", infer_question_types("大学生对品牌的提及频率与情感倾向如何？"))

    def test_binary_outcome(self):
        self.assertIn("binary_outcome", infer_question_types("消费者是否愿意再次购买？"))

    def test_empty(self):
        self.assertEqual(infer_question_types(""), [])


class ModelKnowledgeTest(unittest.TestCase):
    def test_all_models_loaded(self):
        models = load_models()
        self.assertEqual(len(models), 35)
        self.assertIn("sem", models)
        self.assertEqual(models["sem"].level, "高阶")

    def test_survey_baseline_models(self):
        brief = _brief()
        rec = recommend_models(brief, {"RQ1": ["descriptive"]}, n_effective=400, dv_types={"continuous"})
        ids = {m.id for m in rec.core}
        self.assertIn("sample_size", ids)
        self.assertIn("descriptive", ids)
        self.assertIn("likert", ids)
        self.assertIn("cronbach", ids)

    def test_driver_prefers_regression(self):
        brief = _brief(preferred=["多元线性回归"])
        rec = recommend_models(brief, {"RQ1": ["driver"]}, n_effective=400, dv_types={"continuous"})
        ids = {m.id for m in rec.core}
        self.assertIn("linear_regression", ids)
        self.assertNotIn("logistic_regression", ids)

    def test_mediation_uses_sem_only_with_enough_sample(self):
        brief = _brief()
        big = recommend_models(brief, {"RQ1": ["mediation"]}, n_effective=400, dv_types={"continuous"})
        small = recommend_models(brief, {"RQ1": ["mediation"]}, n_effective=120, dv_types={"continuous"})
        self.assertIn("sem", {m.id for m in big.core})
        self.assertNotIn("sem", {m.id for m in small.core})
        self.assertTrue(any("SEM" in w for w in small.warnings))

    def test_group_difference_does_not_force_regression(self):
        brief = _brief()
        rec = recommend_models(brief, {"RQ1": ["group_difference"]}, n_effective=300, dv_types={"continuous"})
        ids = {m.id for m in rec.core}
        self.assertIn("anova", ids)
        self.assertIn("chi_square", ids)
        self.assertNotIn("linear_regression", ids)

    def test_small_sample_warning(self):
        brief = _brief()
        rec = recommend_models(brief, {"RQ1": ["driver"]}, n_effective=60, dv_types={"continuous"})
        self.assertTrue(any("低于" in w for w in rec.warnings))

    def test_requirements_have_basis(self):
        models = load_models()
        reqs = requirements_for_models([models["linear_regression"], models["sem"]], 400, 5, 18, 4)
        self.assertEqual(len(reqs), 2)
        for r in reqs:
            self.assertTrue(r.model_name)
            self.assertTrue(r.basis)
            self.assertIsNotNone(r.satisfied)


if __name__ == "__main__":
    unittest.main()
