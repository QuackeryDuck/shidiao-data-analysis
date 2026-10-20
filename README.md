# 市场调查数据需求生成项目（正大杯 · 本科生版）

从一份结构化的研究简介（research brief）出发，自动生成市场调查项目中**数据分析部分的数据需求文档**：变量体系、样本与抽样参数、模型与方法、研究假设、调查渠道、质量控制措施。

项目面向全国大学生市场调查与分析大赛（正大杯）等本科市场调查场景，强调三件事：

1. **方法可解释**：每一个模型推荐都给出适用理由、样本门槛、前提检验与备选方案，而不是堆模型名称。
2. **结果可复现**：Python 标准库实现的确定性引擎，同一输入得到同一输出；生成后仍可人工改写。
3. **过程可交接**：输入格式、输出结构、质量清单和 skill 工作流都有文档，团队成员可以独立接手。

---

## 1. 快速开始

环境要求：Python 3.10+（Windows 推荐使用 `py` 启动器）。无需安装第三方依赖。

```powershell
# 1. 从模板创建输入文件
py -m engine.cli init

# 2. 编辑 doc/input/research_brief.md，填写项目信息、研究问题与核心构念
# 3. 校验输入并查看引擎识别结果
py -m engine.cli validate

# 4. 生成数据需求文档
py -m engine.cli generate

# 输出：doc/output/data_requirement.md
```

直接运行示例：

```powershell
py -m engine.cli generate `
  --input doc/input/example_research_brief.md `
  --output doc/output/example_data_requirement.md
```

> Windows 上请使用 `py`，不要使用可能指向 WindowsApps 占位程序的 `python`/`python3`。若命令无输出且退出码为 0，通常就是调用了占位程序。

常用参数：

```powershell
py -m engine.cli generate -i doc/input/research_brief.md -o doc/output/data_requirement.md --json
py -m engine.cli sample --confidence 0.95 --error 0.05 --population 300000 --deff 1.2 --rate 0.85
py -m engine.cli models --level 进阶 --search 回归
py -m engine.cli --version
```

---

## 2. 文件架构

```text
shidiao-data-analysis/
├── README.md                     # 本文件：项目说明、架构、使用方式
├── engine/                       # 数据需求生成引擎（Python 标准库）
│   ├── __init__.py               # 版本号
│   ├── __main__.py               # 支持 py -m engine
│   ├── cli.py                    # 命令行入口：generate / validate / sample / models / init
│   ├── brief.py                  # 输入解析：Markdown frontmatter + 章节，或 JSON
│   ├── variables.py              # 变量识别、角色判定、题项与问卷结构
│   ├── hypotheses.py             # 假设生成与变量/方法/理论绑定
│   ├── sample.py                 # 样本量、有限总体修正、设计效应、分层配额
│   ├── knowledge.py              # 35 个模型的知识库、问题类型推断、推荐打分
│   ├── channels.py               # 调查渠道组合与配额分配
│   ├── quality.py                # 六阶段质量控制框架
│   ├── render.py                 # Markdown 文档渲染（全部章节与附录）
│   ├── data/                     # 结构化知识库（JSON）
│   │   ├── models.json           # 35 个模型：适用问题、样本门槛、前提、备选
│   │   ├── channels.json         # 渠道库：覆盖、成本、速度、风险、合规
│   │   ├── qc.json               # 质控规则、无效问卷判定、验收标准
│   │   └── construct_keywords.json # 构念关键词、理论映射、情感方向词
│   └── tests/                    # 单元测试与端到端冒烟测试
│       ├── __init__.py
│       ├── test_sample.py        # 样本量公式、FPC、设计效应、边界
│       ├── test_brief.py         # Markdown/JSON 解析、别名、校验
│       ├── test_knowledge.py     # 问题类型、模型推荐、样本门槛
│       └── test_pipeline.py      # 示例输入 → 完整 Markdown
├── SKILL/
│   └── data-requirement/         # 数据需求生成 skill
│       ├── SKILL.md              # 触发条件、工作流、质量门槛
│       ├── references/
│       │   ├── input_format.md   # 输入字段、别名、构念表、排错
│       │   ├── output_spec.md    # 输出章节、格式、六项核心产出
│       │   ├── model_selection_guide.md  # 35 个模型的适用条件与备选
│       │   └── quality_checklist.md      # 交付前逐项检查
│       ├── scripts/
│       │   └── run_engine.py     # 跨目录定位项目根并调用引擎
│       ├── assets/
│       │   └── research_brief.template.md
│       └── evals/
│           └── evals.json        # 真实场景测试提示
├── doc/
│   ├── input/                    # 输入文档
│   │   ├── README.md             # 输入格式说明
│   │   ├── research_brief.template.md
│   │   └── example_research_brief.md
│   ├── output/                   # 输出文档（Markdown）
│   │   ├── README.md             # 输出结构与使用说明
│   │   └── example_data_requirement.md
│   └── learning/                 # 学习资料
│       └── 正大杯市场调查模型方法学习手册.docx
├── data/                         # 原始数据、清洗后数据（不入库）
│   └── README.md
└── report/                       # 图表、表格与最终报告素材
    └── README.md
```

---

## 3. 输入：research brief

输入支持 Markdown 与 JSON。推荐 Markdown，因为团队成员可以直接阅读和批注。

- 文件位置：`doc/input/research_brief.md`（默认）或 `--input` 指定。
- 结构：YAML frontmatter（简单键值）+ 固定中文章节。
- 最小可用输入：`project_name` + `## 研究问题`。
- 完整输入还会包含：研究背景、研究目标、核心构念表、分析方法倾向、约束条件、分层配额、补充说明。

```markdown
---
project_name: 大学生现制咖啡消费行为研究
target_population: 武汉市高校在校大学生
data_sources: [一手问卷, 公开文本/评论]
confidence_level: 0.95
margin_error: 0.05
population_size: 300000
design_effect: 1.2
response_rate: 0.85
---

## 研究问题

1. RQ1：大学生咖啡消费频率与客单价呈现怎样的特征？
2. RQ2：不同年级学生的消费频率是否存在显著差异？
3. RQ3：产品品质与价格感知对购买意愿有何影响？
```

完整字段、章节别名和构念表格式见 [doc/input/README.md](doc/input/README.md)，可直接复制 [research_brief.template.md](doc/input/research_brief.template.md)。

---

## 4. 输出：数据需求文档

默认输出 `doc/output/data_requirement.md`，UTF-8 Markdown。文档固定包含：

| 章节 | 内容 | 对应需求 |
| --- | --- | --- |
| 0 文档摘要 | 一页看清研究设计、样本、核心方法 | 交接 |
| 1 研究概述 | 背景、问题、目标、范围、概念框架、数据需求总览 | 研究设计 |
| 2 研究假设 | 假设体系、检验口径、探索性问题 | **假设** |
| 3 变量确定 | 变量角色、操作化、变量字典、量表、问卷结构、变量—模型映射 | **变量确定** |
| 4 样本与抽样 | 总体、抽样方法、样本量、敏感性、配额、模型样本校验、采集规模 | **样本参数** |
| 5 模型与方法 | 选择逻辑、路线图、RQ—变量—模型对应、核心模型详解、前提检验、备选、软件模块 | **模型方法（重点）** |
| 6 调查渠道 | 渠道组合、执行表、二手数据、渠道质控、节奏、合规 | **调查渠道** |
| 7 质量控制 | 六阶段质控、清洗规则、伦理、清单、验收标准 | **质控措施** |
| 8 数据交付 | 数据集结构、编码、缺失值、版本、交付清单 | 数据交接 |
| 9 进度与风险 | 周计划、分工、风险应对 | 项目管理 |
| 10 待确认事项 | 引擎默认值与需人工确认的假设 | 风险披露 |
| 附录 A–C | 模型速查、参考文献、术语表 | 答辩准备 |

输出示例：[doc/output/example_data_requirement.md](doc/output/example_data_requirement.md)。结构与写作要求见 [doc/output/README.md](doc/output/README.md)。

---

## 5. 引擎做了什么

```text
输入 brief
  → 解析与校验（brief.py）
  → 识别研究问题类型（knowledge.infer_question_types）
  → 推断变量角色与测量层级（variables.py）
  → 计算样本量与分层配额（sample.py）
  → 推荐核心/可选模型并校验样本门槛（knowledge.py）
  → 生成假设并绑定检验方法（hypotheses.py）
  → 推荐渠道组合（channels.py）
  → 生成六阶段质控方案（quality.py）
  → 渲染 Markdown（render.py）
```

关键设计：

- **问题类型驱动模型**：先把研究问题归为描述、组间差异、关联、影响、中介、调节、二分类结果、评价、文本、分群等类型，再按类型匹配模型。
- **逐题推荐 + 全局组合**：每个 RQ 得到自己的候选模型；全局再按本科生适配度、数据来源、样本量、方法偏好组装核心与可选模型。
- **样本门槛校验**：模型要求的最低有效样本、每个自变量所需样本、分组样本等会与测算结果比较，不满足时给出降级或补样建议。
- **模型特定匹配**：回归、方差分析、卡方、SEM 只绑定真正适配的 RQ，避免“所有因果模型都对应所有问题”。
- **确定性输出**：不调用外部 API，不依赖网络；相同输入稳定复现。

模型知识库覆盖 35 个方法，按基础 / 进阶 / 高阶分层，来源为 `doc/learning/正大杯市场调查模型方法学习手册.docx` 的整理。查看：

```powershell
py -m engine.cli models
py -m engine.cli models --level 基础
```

---

## 6. 使用 skill

`SKILL/data-requirement/` 是给 Claude 使用的工作流封装。触发后，它会：

1. 定位项目根目录（当前目录向上查找，或读取 `DATA_REQUIREMENT_PROJECT_ROOT`）。
2. 读取并校验输入，缺关键信息时先列出待确认项。
3. 调用 `engine` 生成基线文档。
4. 按质量清单复核并补写引擎不擅长的部分（理论依据、行业语境、学校/团队约束）。
5. 报告输出路径、关键假设和仍需人工确认的事项。

skill 不会替代人工判断：它负责把“该考虑什么”铺全，最终变量取舍、模型选择与结论解释仍由研究团队负责。

```powershell
# 可直接运行 skill 附带的入口脚本
py SKILL/data-requirement/scripts/run_engine.py --input doc/input/research_brief.md
```

详见 [SKILL/data-requirement/SKILL.md](SKILL/data-requirement/SKILL.md)。

---

## 7. 测试

```powershell
py -m unittest discover -s engine/tests -v
```

测试覆盖样本量公式与边界、输入解析、问题类型识别、模型推荐门槛，以及从示例输入到 Markdown 输出的端到端流程。

---

## 8. 扩展指南

| 想改什么 | 改哪里 |
| --- | --- |
| 增加模型或调整模型适用条件 | `engine/data/models.json`，必要时同步 `engine/knowledge.py` 的问题类型映射 |
| 增加调查渠道 | `engine/data/channels.json` |
| 调整质控规则/验收标准 | `engine/data/qc.json` |
| 增加构念关键词或理论映射 | `engine/data/construct_keywords.json` |
| 修改文档章节或表格 | `engine/render.py` |
| 增加输入字段/章节别名 | `engine/brief.py` |
| 修改 skill 行为 | `SKILL/data-requirement/SKILL.md` 与 `references/` |

修改知识库后建议重新生成示例并运行测试，确认没有破坏现有输出。

---

## 9. 边界与注意事项

- 引擎给出的是**研究设计基线**，不是统计结果；所有数字（样本量、配额、门槛）都依赖输入假设。
- 自动识别的变量角色和问题类型需要人工复核，尤其是含多重含义的中文表述。
- 模型推荐偏向本科竞赛可执行性，不追求方法前沿；高阶模型会同时给出降级方案。
- 样本量公式默认简单随机抽样，复杂设计通过设计效应近似；严格概率抽样需在文档中单独说明。
- 公开文本数据必须遵守平台条款、著作权与个人信息保护要求，不采集身份信息。
- 生成文档中的参考文献为方法学通用条目，正式参赛前应按学校格式核对并补充文献。

---

## 10. 常见问题

**Q：`py -m engine.cli generate` 提示输入文件不存在？**
先运行 `py -m engine.cli init`，或使用 `--input` 指向已有文件。

**Q：可以只用研究问题、不填构念表吗？**
可以。引擎会从研究问题中推断变量，并在第 10 章标注需复核。正式提交前建议补全构念表。

**Q：生成的核心模型太多怎么办？**
在输入文件的“分析方法倾向”中列出团队真正会用 methods，或在生成后按第 5.1 节的选择逻辑删减。核心模型建议控制在 6–12 个（纯问卷通常 6–10 个，含文本/多源数据可适当增加），确保每个都有对应 RQ 和变量。

**Q：输出能直接作为参赛文档提交吗？**
不能直接提交。它是数据需求与方案文档，需要结合文献综述、问卷定稿、实际数据和指导教师意见改写。

**Q：为什么不用 pandas / statsmodels？**
本项目只负责“需求设计与方案生成”，不执行统计分析。标准库实现保证任何队员的电脑都能运行，不依赖环境配置。
