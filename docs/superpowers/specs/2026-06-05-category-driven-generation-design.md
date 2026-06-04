# TK-ERP V2 — 分类驱动的 AI 产品生成系统 设计文档

> 日期：2026-06-05 | 状态：已确认 | 替代 V1 设计

---

## 1. 项目概述

### 1.1 核心变化

| V1 (旧) | V2 (新) |
|---------|---------|
| 基于原始印花图片生成 | 基于提示词分类生成 |
| img2img + 抠图 + 合成 | txt2img 一步出图 |
| 每个印花=一个产品 | 选分类+数量=批量产品 |
| 管理原始印花库 | 管理分类提示词库 |
| rembg 抠图不可靠 | 无需抠图 |

### 1.2 核心流程

```
上传模板 → 豆包分析版型 → 手动输入面料 → 存入模板库
上传图集 → 豆包分类 → 生成分类.md → 存入分类库
生成产品 → 选分类 + 选模板 + 数量 → txt2img → T恤实物图
```

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────┐
│              Bootstrap 5 + htmx 运营面板              │
├─────────────────────────────────────────────────────┤
│                                                     │
│  模板管理 ──→ 分类管理 ──→ 产品生成 ──→ 产品库/导出    │
│                                                     │
├─────────────────────────────────────────────────────┤
│  AI 引擎                                            │
│  ├── 豆包 Vision (分析图集/模板)                      │
│  ├── DeepSeek (生成商品标题)                          │
│  └── ComfyUI txt2img (生成产品图)                    │
├─────────────────────────────────────────────────────┤
│  数据存储: SQLite + 本地文件系统                       │
└─────────────────────────────────────────────────────┘
```

---

## 3. 数据模型

### 3.1 TShirtTemplate（修改）

| 字段 | 类型 | 说明 |
|------|------|------|
| name | CharField | 模板名称 |
| image | ImageField | T恤底图 |
| color | CharField | 颜色 |
| prompt_body | TextField | 豆包分析的版型提示词 |
| fabric | CharField | 手动输入的面料描述 |
| fit_style | CharField | 版型 (Oversized/Regular/Slim) |
| is_active | BooleanField | 启用状态 |

### 3.2 PrintCategory（新建）

| 字段 | 类型 | 说明 |
|------|------|------|
| name | CharField | 分类名 (如 Horror Graphic) |
| slug | CharField | 文件标识 (horror-graphic) |
| prompt_file | CharField | .md 文件路径 |
| keywords | TextField | 匹配关键词 (逗号分隔) |
| print_prompt | TextField | 核心印花提示词 |
| extra_prompt | TextField | 额外提示词 (可选) |
| is_active | BooleanField | 启用状态 |
| created_at | DateTimeField | 创建时间 |

### 3.3 Product（简化）

移除：`pattern FK`, `print_image`, `ProductSKU`

| 字段 | 类型 | 说明 |
|------|------|------|
| country | FK→Country | 目标国家 |
| category | FK→PrintCategory | 印花分类 |
| template | FK→TShirtTemplate | 主模板 |
| title | CharField | 商品标题 |
| description | TextField | 商品描述 |
| size_info | CharField | 尺码 |
| status | CharField | pending/processing/completed/failed |
| mockup_image | ImageField | 生成的效果图 |
| seed | IntegerField | 生成种子 |
| background | CharField | 使用的背景 |
| created_at | DateTimeField | 创建时间 |

### 3.4 ProductSKU（新建）

| 字段 | 类型 | 说明 |
|------|------|------|
| product | FK→Product | 所属产品 |
| template | FK→TShirtTemplate | 此SKU的模板(不同颜色) |
| mockup_image | ImageField | SKU效果图 |

---

## 4. 分类 .md 文件结构

```markdown
# [分类名]

## 匹配关键词
keyword1, keyword2, keyword3, ...

## 印花 Prompt
[核心印花描述，用于 txt2img]

## 完整生成 Prompt
{template_prompt}, {fabric}

[印花: {print_prompt}]

{background}, soft indoor lighting, commercial apparel photography,
front view, center composition, 85mm lens, ultra realistic, 8k

## 负面 Prompt
low quality, blurry, anime, cartoon, childish, cute style, ...
```

生成时 `{template_prompt}` `{fabric}` `{print_prompt}` `{background}` 动态替换。

---

## 5. 分类管理流程

### 首次上传图集
```
上传图集(10-50张) → 豆包分析 → 建议分类列表 → 自动创建分类.md + 入库
用户可在界面编辑分类的: 名称、关键词、印花提示词
```

### 后续上传
```
新图集 → 豆包分析 → 匹配已有分类(通过关键词) → 更新现有分类 or 建议新建
```

### 分类手动管理
- 创建/编辑/删除分类
- 编辑 .md 文件内容
- 手动调整匹配关键词
- 优化印花 prompt

---

## 6. 产品生成流程

```
用户: 选分类 + 选模板(多选=多SKU) + 数量
        ↓
系统: 拼装 prompt = template_prompt + fabric + print_prompt + random_bg + base_spec
        ↓
ComfyUI: txt2img × 数量 (每张不同seed, 不同背景)
        ↓
结果: Product × 数量, 每个Product有N个SKU效果图(N=模板数量)
```

**同产品多SKU规则:** 同seed、同背景、同印花，只改模板颜色prompt。

**背景随机选择池:** `office chair, bookshelf background, minimalist interior, wood furniture, coffee shop, light gray background, cream white background, modern room`

---

## 7. Prompt 拼装公式

```
{template.prompt_body}, {template.fabric}

[印花: {category.print_prompt}]

{random_background}, soft indoor lighting, commercial apparel photography,
front view, center composition, 85mm lens, ultra realistic, 8k
```

负面 prompt 统一从分类 .md 读取。

---

## 8. 界面结构

```
├── 🏠 工作台
├── 🏢 店铺管理 (国家+店铺 CRUD)
├── 👥 用户管理
├── 👕 模板管理 (上传/编辑/删除，含 prompt 和面料字段)
├── 📂 分类管理 (创建/编辑/删除/查看 .md 内容)
├── ✨ 创建产品 (选分类+模板+数量 → 生成)
├── 📦 产品库 (列表/编辑/删除/导出)
└── ⚙️ 设置 (ComfyUI 模型选择)
```

---

## 9. 删除的内容

- Pattern 模型及相关管理页面
- 批量导入印花功能
- rembg 抠图逻辑
- img2img 工作流
- 印花贴模板合成逻辑
- ProductSKU 旧模型
- 印花变体策略

## 10. 后续扩展

- 生成时可手动微调 prompt
- 支持批量修改分类提示词
- 生成历史回溯
