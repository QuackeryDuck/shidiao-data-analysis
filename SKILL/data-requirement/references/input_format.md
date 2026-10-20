# 输入格式（research brief）

引擎接受 Markdown（推荐）与 JSON。编码 UTF-8。默认路径 `doc/input/research_brief.md`。

## 1. Markdown 结构

```markdown
---
project_name: 项目名称
target_population: 目标总体
data_sources: [一手问卷, 公开文本/评论]
confidence_level: 0.95
margin_error: 0.05
population_size: 300000
design_effect: 1.2
response_rate: 0.85
---

<!-- 注释会被忽略 -->

## 研究背景
...

## 研究问题
1. RQ1：...
2. RQ2：...

## 核心构念
| 构念 | 角色 | 操作化定义 | 题项数 | 量表 | 测量层级 | 数据来源 | 维度 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 购买意愿 | 因变量 | ... | 4 | 5 级李克特 | 连续 | 一手问卷 |  |  |
```

规则：

- frontmatter 在第一行 `---` 与下一个 `---` 之间；只支持单行键值与行内列表，不支持 YAML 嵌套/多行字符串。
- 正文按 `##` 标题切分，顺序不限；标题做归一化（忽略空格、标点、大小写）。
- `<!-- ... -->` 注释忽略。
- 没有“研究问题”时，用“研究目标”替代；两者都没有会校验失败。

## 2. 字段

| 字段 | 类型 | 默认 / 说明 |
| --- | --- | --- |
| `project_name` | 字符串 | 必填，文档标题 |
| `project_slug` | 字符串 | 可选，英文短名 |
| `competition` | 字符串 | 默认“正大杯全国大学生市场调查与分析大赛” |
| `research_type` | 字符串 | 默认“市场调查” |
| `industry` | 字符串 | 行业 |
| `region` | 字符串 | 研究区域 |
| `target_population` | 字符串 | 目标总体；缺失会警告 |
| `survey_unit` | 字符串 | 默认“个人” |
| `data_sources` | 列表 | 如 `[一手问卷, 公开文本/评论, 二手行业数据]` |
| `survey_mode` | 字符串 | 默认“线上为主” |
| `confidence_level` | 数值 | 默认 0.95 |
| `margin_error` | 数值 | 默认 0.05；>0.10 警告 |
| `expected_proportion` | 数值 | 默认 0.5（最保守） |
| `population_size` | 整数 | 留空按无限总体 |
| `design_effect` | 数值 | 默认 1.2；简单随机为 1.0 |
| `response_rate` | 数值 | 默认 0.9；<0.5 警告 |
| `budget_cny` | 整数 | 影响渠道推荐 |
| `timeline_weeks` | 整数 | 影响排期与渠道 |
| `team_size` | 整数 | 影响分工建议 |

## 3. 章节别名

| 内部字段 | 可识别标题 |
| --- | --- |
| background | 研究背景、项目背景、背景、研究缘起、Background |
| research_questions | 研究问题、核心问题、研究议题、待回答的问题、Research Questions、RQs |
| objectives | 研究目标、研究目的、研究任务、Objectives、Goals |
| constructs | 调查内容、核心构念、研究变量、变量设计、构念、变量、Constructs、Variables |
| existing_hypotheses | 研究假设、已有假设、假设、Hypotheses |
| constraints | 约束条件、研究约束、条件限制、限制条件、Constraints |
| preferred_methods | 分析方法倾向、拟用方法、方法偏好、分析方法、Preferred Methods、Methods |
| notes | 补充说明、其他说明、备注、Notes |
| strata | 分层、配额、分层配额、抽样分层、Strata、Quotas |
| basic | 基本信息、项目信息、研究概况、Basic Info |

“基本信息”章节可用 `键：值` 补充 frontmatter（不覆盖已有值）。

## 4. 研究问题写法

```markdown
## 研究问题

1. RQ1：武汉市大学生的咖啡消费频率与客单价呈现怎样的特征？
2. RQ2：不同年级学生的消费频率是否存在显著差异？
3. RQ3：产品品质、价格感知对购买意愿有何影响？
4. RQ4：品牌信任是否在产品品质与购买意愿之间起中介作用？
5. RQ5：月生活费是否调节价格感知对购买意愿的影响？
6. RQ6：大学生对主要咖啡品牌的提及频率与情感倾向如何？
```

- 支持 `1.`、`-`、`*`；编号 `RQ1：` 可省略。
- 关键词决定问题类型：描述、差异/比较/不同、相关/关系、影响/因素、中介/通过、调节/交互、分群、评价/评分、文本/评论。
- 用 `validate` 检查识别结果；识别错误时改写问题措辞，而不是在文档里硬改模型。

## 5. 核心构念表

列名可用中文或英文；至少包含“构念”和“角色”。

| 列 | 取值 |
| --- | --- |
| 构念 | 变量名 |
| 角色 | 因变量、自变量、中介变量、调节变量、控制变量、筛选变量、探索性变量 |
| 操作化定义 | 测量内容与口径 |
| 题项数 | 整数 |
| 量表 | 5 级李克特、7 级李克特、单选、多选、填空、排序 |
| 测量层级 | 定类、定序、连续、文本、多重响应 |
| 数据来源 | 一手问卷、公开评论文本、二手行业数据等 |
| 维度 | 子维度，用 `/` 或 `、` 分隔 |
| 备注 | 特殊说明，如“同时作为分组变量” |

注意：

- 一个变量只设一个主角色。既是调节又用于分组，在备注中说明，不要重复建行。
- 李克特量表构念建议 ≥3 题；否则信度与 SEM 测量模型不稳定。
- 控制变量不是越多越好；只放理论上可能影响因变量、且与核心自变量相关的变量。
- 没有构念表时引擎会从研究问题推断，但角色可能错，必须在第 10 章标注并人工复核。

## 6. 分层配额

```markdown
## 分层配额

- 大一：25%
- 大二：25%
- 大三：25%
- 大四：25%
```

- 必须用列表，不要用表格。
- 支持比例 `25%` 或人数 `120人`；比例会归一化。
- 未填写时，文档按性别、年级/年龄、地区给建议配额。

## 7. 已有假设

```markdown
## 研究假设

- H1：产品品质对购买意愿具有显著正向影响。
- H2：品牌信任在产品品质与购买意愿之间起中介作用。
```

提供后引擎不再自动生成假设，只补变量、方法和理论绑定。不需要时删除整个章节。

## 8. JSON

```json
{
  "project_name": "大学生咖啡消费研究",
  "target_population": "武汉市高校在校大学生",
  "data_sources": ["一手问卷", "公开文本/评论"],
  "confidence_level": 0.95,
  "margin_error": 0.05,
  "population_size": 300000,
  "design_effect": 1.2,
  "response_rate": 0.85,
  "research_questions": [
    {"qid": "RQ1", "text": "大学生咖啡消费频率呈现怎样的特征？"},
    {"qid": "RQ2", "text": "不同年级学生的消费频率是否存在显著差异？"}
  ],
  "constructs": [
    {"name": "购买意愿", "role": "dependent", "items": 4, "scale": "5 级李克特", "measure": "连续"},
    {"name": "产品品质", "role": "independent", "items": 5, "scale": "5 级李克特", "measure": "连续"}
  ],
  "strata": [{"name": "大一", "ratio": 0.25}, {"name": "大二", "ratio": 0.25}],
  "preferred_methods": ["多元线性回归"],
  "constraints": ["预算 3000 元"]
}
```

- `research_questions` 可为字符串数组或 `{qid, text}` 数组。
- `role` 用英文：dependent / independent / mediator / moderator / control / screening / exploratory。
- `strata` 用 `ratio`（0–1）或 `count`。

## 9. 排错

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 输入文件不存在 | 未 init 或路径错 | `py -m engine.cli init` 或 `--input` |
| 研究问题类型识别错 | 措辞缺分析动词 | 改写问题；用 `validate` 验证 |
| 变量角色全为推断 | 未填构念表 | 补表并明确角色 |
| 配额未生效 | 用了表格 | 改成 `- 层名：25%` |
| 样本量异常 | 误差/有效率参数不合理 | 检查 `margin_error`、`response_rate` |
| 中文乱码 | 非 UTF-8 | 另存为 UTF-8 |
| YAML 报错 | 使用了嵌套/多行 | 改为单行键值与行内列表 |
