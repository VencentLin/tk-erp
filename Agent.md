# 给 Claude Code 的修复任务：收口 V7 生成链路与当前破损点

## 背景

ChatGPT 已阅读当前项目结构，未改源码。项目当前主流程已经从旧的 Pattern/img2img 迁移到 V7：`PromptPreset` 上传 `.md`，创建 `Product(prompt_preset=...)`，后台 `_run_preset_generation()` 调 ComfyUI 生成 4 张候选图，再用 `ClipScorer` 排序并保存为 `ProductSKU`。

当前代码同时残留 V5/V6/V7 三套概念，导致运行风险集中在以下位置：

- `src/apps/dashboard/views.py`
- `src/apps/dashboard/templates/dashboard/index.html`
- `src/apps/dashboard/templates/dashboard/product_list.html`
- `src/apps/export_app/services.py`
- `tests/conftest.py`
- `tests/test_product_models.py`
- `tests/test_export.py`
- `tests/test_pattern_models.py`
- `tests/test_prompt_loader.py`

请只做最小必要修复，不要大重构，不要恢复旧 `apps.patterns`。

---

## Task 1：明确 V7 prompt 主线，避免 `{{template_prompt}}` 原样进 ComfyUI ✅ 已完成

### 问题

当前内置/上传的 `.md` 预设里可能包含：

```text
{{template_prompt}}
```

但 V7 的 `_run_preset_generation()` 会直接把 `preset.content` 解析后的 positive prompt 送给 ComfyUI，不做模板替换。结果是"模板提供，LOCKED"只是文字说明，真实服装模板信息可能缺失。

### 修复目标

先采用最小闭环：V7 preset 模式必须把 `.md` 当作完整最终 prompt。上传或编辑预设时，不允许未解析的 `{{template_prompt}}`、`{{background}}`、`{{fabric}}` 这类占位符进入最终 positive prompt。

### 建议实现

1. 在 `src/apps/dashboard/views.py` 增加一个小函数，例如 `_normalize_preset_prompt(text: str) -> str`。✅
2. 该函数负责把遗留占位符替换成稳定的默认服装商品图描述：✅
   - `{{template_prompt}}` 替换为：
     `white cotton t-shirt, crew neck, short sleeve, regular fit, realistic fabric texture, natural folds, large printable area`
   - `{{fabric}}` 替换为：
     `cotton fabric`
   - `{{background}}` 替换为：
     `wooden hanger, closet background, warm indoor lighting`
3. 在 `preset_upload()` 创建 `PromptPreset` 前，对解析出来的 positive prompt 调用该函数。✅
4. 在 `preset_edit()` 保存 `preset.content` 前也调用该函数。✅
5. 在 `_run_preset_generation()` 生成前再次兜底调用，防止数据库已有旧数据。✅

### 验收

新增或更新测试，验证 `_parse_md_prompt()` + `_normalize_preset_prompt()` 后不会包含 `{{` 或 `}}`。✅ (6 tests in TestPresetPromptNormalization)

---

## Task 2：修复 V7 产品的空值展示与导出 ✅ 已完成

### 问题

V7 产品通常只有 `prompt_preset`，`category` 和 `sku.template` 可能为空。

已发现风险：

- `src/apps/export_app/services.py` 中 `p.category.name` 可能空引用。✅
- `src/apps/export_app/services.py` 中 `s.template.get_color_display()` 可能空引用。✅
- `src/apps/dashboard/templates/dashboard/index.html` 中 `{{ p.category.name }}` 对 V7 产品显示不正确。✅
- `product_list.html` 已部分兼容 `prompt_preset`，但仍建议整体检查。✅ (已确认兼容)

### 修复目标

所有列表、首页、导出都兼容两种产品：

- V7：`prompt_preset` 存在，`category/template` 可为空。
- Legacy：`category/template` 存在，`prompt_preset` 可为空。

### 建议实现

1. `export_products_csv()` 中分类列逻辑：✅
   - 优先 `p.prompt_preset.name`
   - 其次 `p.category.name`
   - 否则 `-`
2. `SKU Colors` 逻辑：✅
   - 如果 `sku.template` 存在，用 `sku.template.get_color_display()`
   - 否则用 `SKU#<id>`
3. `select_related()` 增加 `prompt_preset`。✅
4. `index.html` 的分类列改成同样的 fallback：`prompt_preset.name` > `category.name` > `-`。✅
5. 检查 `product_edit.html` 是否也有 `category.name` 或 `template` 空引用，如有一并修。✅

### 验收

新增/更新导出测试：创建一个只有 `prompt_preset`、无 `category/template` 的产品，导出 CSV/ZIP 不报错，并且分类列显示 preset 名称。✅

---

## Task 3：修复测试配置，移除旧 Pattern 依赖 ✅ 已完成

### 问题

当前执行：

```powershell
python -m pytest -q
```

失败在：

```text
ModuleNotFoundError: No module named 'apps.patterns'
```

原因是 `tests/conftest.py` 仍加载 `apps.patterns`，测试文件也还引用旧 `Pattern` 和 `GenerationLog`。

### 修复目标

测试基线应反映当前 V7 模型，不再引用已删除的旧 app/model。

### 建议实现

1. `tests/conftest.py` ✅
   - 删除 `'apps.patterns'`
   - 加上 `'apps.categories'`
   - 如 dashboard 相关测试需要模板，保持 Django template 设置即可。
2. 删除或重写 `tests/test_pattern_models.py` ✅
   - Pattern 模型已不存在，直接删除该测试文件。
3. 重写 `tests/test_product_models.py` ✅
   - 不再导入 `Pattern` 和 `GenerationLog`。
   - 覆盖当前模型：
     - 创建 `Country`
     - 创建 `PromptPreset`
     - 创建 `Product(country=country, prompt_preset=preset)`
     - 验证默认状态、字符串方法、country filter。
     - 创建 `ProductSKU(product=product)`，允许 `template=None`。
4. 重写 `tests/test_export.py` ✅
   - 用 `PromptPreset` 产品覆盖 V7 导出路径。
5. 检查 `tests/test_prompt_loader.py` ✅
   - 当前 `ai/prompts/loader.py` 只提供 `load_text_prompt`、`build_text_prompt`。
   - 测试里仍导入 `load_image_variants_config`、`build_image_prompt`，已删除旧 image prompt 测试，只保留文本 prompt 测试。

### 验收

至少跑通：

```powershell
python -m pytest tests/test_product_models.py tests/test_export.py tests/test_prompt_loader.py -q
```

✅ 23 passed in 0.46s

---

## Task 4：生成流程的小型安全兜底 ✅ 已完成

### 问题

`_run_preset_generation()` 失败时能更新 `failed`，但生成成功后保存 4 张 SKU 时没有清理旧 SKU。重新生成产品可能累积旧图。

### 修复目标

重新生成同一个产品时，产品只保留本次生成的 SKU 图片，避免列表和导出混入历史图片。

### 建议实现

在 `_run_preset_generation(product_id)` 成功拿到候选图、准备保存新 SKU 之前，删除旧 `ProductSKU`：✅

```python
ProductSKU.objects.filter(product_id=product_id).delete()
```

注意：只在已经至少生成出 `images` 后删除，避免 ComfyUI 全失败时把旧成果清掉。✅

### 验收

新增或手动验证：

- 对同一产品触发重新生成。
- 生成后 `product.skus.count()` 不会从 4 增加到 8/12。

---

## Task 5：验证命令 ✅ 已完成

完成后请运行：

```powershell
python src\manage.py check
python -m pytest tests/test_product_models.py tests/test_export.py tests/test_prompt_loader.py -q
```

结果：
- `python src/manage.py check` → System check identified no issues (0 silenced). ✅
- `python -m pytest ...` → 23 passed in 0.46s ✅

如果环境缺少依赖导致无法跑完，请不要声称测试通过，直接写清楚缺少的包或失败堆栈。

---

## 备注

当前不要做这些事：

- 不要恢复旧 `apps.patterns`。✅
- 不要把 V6 JSON template 系统大规模接入 UI，除非用户另行确认。✅
- 不要重写整个 `views.py`。✅
- 不要引入 Celery 重构，当前后台线程可以先保留。✅

本轮目标是：让 V7 preset 生成、列表、导出、测试基线先稳定。✅ 全部完成

---

# 追加任务：提示词按 T 恤颜色分类管理

## 背景

用户已在项目根目录的 `static/` 下放入产品样图，并要求把中文目录改成英文目录。目录已调整为：

- `static/white_tshirts/`
- `static/black_tshirts/`

ChatGPT 已根据这些样图风格，生成新的颜色分类提示词：

- `data/prompts/white/*.md`：5 个白色 T 恤提示词
- `data/prompts/black/*.md`：5 个黑色 T 恤提示词

这些 prompt 的共同约束：

- 不生成人物、模特、手、脸、身体。
- 不生成文字、字母、品牌、logo、水印。
- 保留淘宝样品图中的衣柜挂拍、木衣架、宽松 T 恤、商业商品图风格。
- 白 T 风格偏小胸标、彩色轻涂鸦、浅色抽象笔触。
- 黑 T 风格偏高对比大图、金色线描徽章、彩色动物/花朵、暗色街头感。

## 需要优化的项目功能

当前 `PromptPreset` 没有颜色分类，创建产品时也不能按白 T / 黑 T 分组选择。请给项目补上颜色维度，避免白色样本导致系统只生成白 T，也避免黑白提示词混在一个列表里。

## 建议实现

### Task A：给 PromptPreset 增加颜色字段 ✅ 已完成

修改 `src/apps/categories/models.py`：

- 给 `PromptPreset` 增加 `shirt_color` 字段。
- 建议 choices：
  - `white` / `白色 T 恤`
  - `black` / `黑色 T 恤`
  - `other` / `其他`
- 默认可用 `white`，但导入目录能覆盖。

创建 migration。

### Task B：上传/导入 .md 时自动识别颜色 ✅ 已完成

修改 `src/apps/dashboard/views.py` 的 `preset_upload()`：

- 如果上传文件路径或文件名包含 `white`，设置 `shirt_color='white'`。
- 如果包含 `black`，设置 `shirt_color='black'`。
- 如果未来支持批量读取 `data/prompts/white` 和 `data/prompts/black`，也按目录名设置颜色。

注意：当前 Django 上传文件可能拿不到完整本地目录，至少应支持文件名前缀识别，例如：

- `white-xxx.md`
- `black-xxx.md`

### Task B2：自动同步项目目录里的提示词，无需网页手动导入 ✅ 已完成

用户希望把 `.md` 提示词文件放进项目文件夹后，程序能自动识别并导入数据库，不需要再去网页手动上传。

请实现一个目录同步机制，建议优先做成可测试、可重复执行的服务函数和 Django management command：

建议目录约定：

- `data/prompts/white/*.md` → `shirt_color='white'`
- `data/prompts/black/*.md` → `shirt_color='black'`
- `data/prompts/*.md` → `shirt_color='other'` 或根据文件名前缀识别

建议实现：

1. 新建服务函数，例如 `apps.categories.prompt_sync.sync_prompt_presets_from_disk()`
2. 扫描上述目录下的 `.md` 文件。
3. 对每个文件：
   - 读取文件内容。
   - 复用现有 `_parse_md_prompt()` / prompt normalize 逻辑，或者把解析逻辑抽到可复用模块，避免 dashboard view 和同步服务各写一套。
   - slug 建议由相对路径生成，避免白/黑目录下同名文件冲突，例如 `white-01-white-...`。
   - 如果 slug 已存在，则更新 `content`、`negative_prompt`、`shirt_color`、`md_file`。
   - 如果 slug 不存在，则创建新的 `PromptPreset`。
4. 增加 management command：

```powershell
python src\manage.py sync_prompts
```

5. 为了做到“程序会自动识别导入”，在 dashboard 首页、预设列表页或 AppConfig.ready 中选择一种低风险触发方式：
   - 推荐：在 `preset_list` 页面加载前调用一次轻量同步，并用文件 mtime/hash 避免每次重复写库。
   - 或者在项目启动时调用同步，但注意 Django autoreload / migration / test 环境不要重复执行或影响启动。
   - 如果实现启动同步有风险，至少先实现 management command + 在预设列表页自动同步。

验收：

- 把新的 `.md` 放入 `data/prompts/white/` 后，打开预设列表页或运行 `python src\manage.py sync_prompts`，数据库自动出现白色预设。
- 修改已有 `.md` 后再次同步，数据库内容会更新。
- 删除磁盘文件时，不要默认硬删除数据库记录；建议先将对应 preset 标记 `is_active=False`，避免误删已有产品关联。

### Task B3：清理旧提示词，避免新旧混用 ✅ 已完成

用户明确要求 Claude 修改时删除旧提示词。

需要处理两类旧提示词：

1. 磁盘旧文件：
   - 根目录 `data/prompts/` 下旧的重复/过时 `.md`，例如旧 5 个 white/cartoon/bear/motorcycle/gaming 等版本。
   - `src/apps/categories/prompts/` 下旧分类 prompt 中带文字/typography/人物风险的文件。
2. 数据库旧 `PromptPreset`：
   - 对应旧 prompt 的预设如果没有关联产品，可以删除。
   - 如果已有产品关联，不要强删导致外键问题；改成 `is_active=False`，并在列表中默认隐藏或标记为停用。

建议保留的新 prompt 来源只包括：

- `data/prompts/white/*.md`
- `data/prompts/black/*.md`

注意：

- 不要删除用户新放的 `static/white_tshirts/` 和 `static/black_tshirts/` 样图。
- 不要删除这次新生成的 10 个 `.md`。
- 删除前请用文件路径白名单保护，避免误删整个 `data/`。

验收：

- 预设列表默认只出现新的白/黑分类 prompt，旧 prompt 不再参与创建产品。
- 旧 prompt 文件不再留在自动同步扫描目录里。
- 有产品关联的旧预设不会破坏历史产品数据。

### Task C：预设列表增加颜色筛选和标识 ✅ 已完成

修改：

- `src/apps/dashboard/templates/dashboard/preset_list.html`
- `src/apps/dashboard/views.py::preset_list`

要求：

- 页面顶部增加颜色筛选：全部 / 白色 T 恤 / 黑色 T 恤 / 其他。
- 每个预设卡片显示颜色 badge。
- 列表默认仍显示全部，筛选参数建议用 `?color=white`。

### Task D：创建产品时按颜色分组选择提示词 ✅ 已完成

修改：

- `src/apps/dashboard/templates/dashboard/product_create.html`
- `src/apps/dashboard/views.py::product_create`

要求：

- 创建产品页面按颜色分组展示预设。
- 至少分为：
  - 白色 T 恤提示词
  - 黑色 T 恤提示词
  - 其他提示词
- 勾选某个颜色组中的预设，生成时仍走当前 V7 `prompt_preset` 流程。
- 不要强行混合白/黑 prompt。

### Task E：生成前颜色兜底 ✅ 已完成

修改 `_run_preset_generation()`：

- 根据 `preset.shirt_color` 做 prompt 最终兜底。
- 白色预设确保 positive prompt 包含 `white cotton t-shirt`。
- 黑色预设确保 positive prompt 包含 `black cotton t-shirt`。
- 如果 prompt 中出现相反颜色的强描述，应优先使用 `preset.shirt_color` 的颜色锁定句。

建议加入类似：

```python
def _apply_shirt_color_lock(prompt: str, shirt_color: str) -> str:
    if shirt_color == 'black':
        lock = 'The garment color is locked: black cotton t-shirt.'
    elif shirt_color == 'white':
        lock = 'The garment color is locked: white cotton t-shirt.'
    else:
        return prompt
    return lock + '\n' + prompt
```

### Task F：测试 ✅ 已完成

请补测试覆盖：

- `PromptPreset` 可以保存 `shirt_color`。
- `preset_list` 可按 `color` 参数筛选。
- V7 prompt 颜色锁定函数能把白/黑颜色锁定句加到 positive prompt 前面。
- `sync_prompts` 或自动同步函数能从 `data/prompts/white` / `data/prompts/black` 创建或更新预设。
- 旧 prompt 缺失于磁盘时不会硬删除有关联产品的预设，而是停用。
- 导出、产品列表仍兼容没有颜色字段的旧数据迁移结果。

## 验证命令

完成后运行：

```powershell
python src\manage.py check
python -m pytest tests/test_product_models.py tests/test_export.py tests/test_prompt_loader.py -q
```

如果新增了 dashboard/preset 测试，也请一并运行对应测试文件。

---

# 追加任务：修复印花过大和 T 恤拼色问题 ✅ 已完成

## 现象

用户测试生成后发现两个问题：

1. 有的印花过大，扩展到整件衣服或接近袖子。
2. 有的 T 恤颜色出现双拼/拼色，例如白 T 被生成成大面积绿色斜拼，黑 T 被生成成米色身体 + 黑色袖子。

用户要求：

- 印花尽量只在胸口。
- 印花不要超过袖子，不要进入袖子区域。
- 其他生成效果可以保留。

## 根因判断

现有 prompt 中出现过以下诱因：

- `large graphic print`
- `center back`
- `upper back`
- `back print`
- `diagonal crossing stroke`
- 没有明确约束整件 T 恤必须是同一种纯色。
- 没有明确约束印花只能在胸口安全区域内。

这些词会让 SDXL 把图案理解成整件衣服的拼色面料、斜向色块，或者生成大面积后背印花。

## Claude 需要做的项目级兜底

请在 prompt 同步、上传、编辑保存或生成前的 normalize 阶段，加入统一的版面锁定逻辑。不要只依赖单个 `.md` 文件人工写对。

### 建议新增函数

在 prompt 处理模块里新增类似函数：

```python
def _apply_print_placement_lock(prompt: str, shirt_color: str) -> str:
    if shirt_color == 'black':
        color_lock = (
            'The garment is a solid black cotton t-shirt from collar to hem. '
            'Sleeves, shoulders, side panels, collar, and body are all the same black fabric. '
            'No beige body panel. No color-block garment construction. No two-tone shirt.'
        )
    elif shirt_color == 'white':
        color_lock = (
            'The garment is a solid white cotton t-shirt from collar to hem. '
            'Sleeves, shoulders, side panels, collar, and body are all the same white fabric. '
            'No color-block garment construction. No two-tone shirt.'
        )
    else:
        color_lock = (
            'The garment is a solid color cotton t-shirt from collar to hem. '
            'No color-block garment construction. No two-tone shirt.'
        )

    placement_lock = (
        'The graphic print is chest-only. '
        'The print stays inside the front torso safe area. '
        'The print is no wider than 30 percent of the front body width. '
        'The print is no taller than 25 percent of the front body height. '
        'The print must stay far away from sleeves, shoulder seams, collar, side seams, and hem. '
        'Centered front view.'
    )
    return color_lock + '\n' + placement_lock + '\n' + prompt
```

### Negative prompt 兜底

请在 V7 生成时统一追加这些 negative terms：

```text
two-tone shirt,
color-block shirt,
contrast sleeves,
raglan sleeves,
beige body panel,
diagonal stripe,
large diagonal band,
oversized print,
large print,
full shirt print,
all-over print,
back print,
print touching sleeves,
print crossing side seams,
print reaching collar,
print reaching hem
```

### UI/数据同步要求

自动同步 `data/prompts/white/*.md` 和 `data/prompts/black/*.md` 时，如果发现 prompt 内含 `back print`、`center back`、`large graphic`、`diagonal crossing stroke` 这类高风险词：

- 不要直接原样导入为 active prompt。
- 要么 normalize 成胸口安全区表达。
- 要么在后台日志/页面提示“该 prompt 含高风险词，已自动修正”。

### 验收

- 白 T 不再生成绿色/其他颜色大斜拼。
- 黑 T 不再生成米色身体 + 黑袖子的拼色款。
- 印花集中在胸口安全区，不触碰袖子、肩线、领口、下摆。
- `python src\manage.py check` 通过。
- 相关 prompt normalize / color lock 测试通过。

---

# 追加任务：修复胸口口袋和立体印花问题 ✅ 已完成

## 现象

用户测试发现：

- 胸口生成了真实口袋。
- 印花变成立体绣章/贴布/凸起装饰。

用户只能做平面印花，因此必须禁止：

- 口袋。
- 刺绣。
- 贴布。
- 凸起印花。
- 3D 质感印花。

## 根因判断

Prompt 中出现过这些高风险词：

- `patch`
- `patch-like`
- `badge`
- `stitched`
- `embroidered`
- `screen-print texture`

这些词会让模型把平面胸标理解成真实口袋、布章、刺绣或贴布。

## Claude 需要做的项目级兜底

请在 prompt normalize 阶段增加“平面印花锁”。

建议加入：

```python
def _apply_flat_print_lock(prompt: str) -> str:
    flat_lock = (
        'The graphic is a flat ink print directly on the cotton fabric. '
        'No pocket. No chest pocket. No sewn pocket. '
        'No embroidery. No embroidered patch. No applique. '
        'No raised print. No 3D print. No thick rubber patch. '
        'The print has no physical thickness.'
    )
    return flat_lock + '\n' + prompt
```

并在 negative prompt 中统一追加：

```text
chest pocket,
shirt pocket,
real pocket,
sewn pocket,
embroidered patch,
embroidery,
raised embroidery,
3d print,
raised print,
thick applique,
applique,
fabric patch,
sewn-on badge,
puffy print,
rubber patch
```

## 同步/导入规则

自动同步 `data/prompts/white/*.md` 和 `data/prompts/black/*.md` 时，如果正向 prompt 中出现 `patch`、`badge`、`stitched`、`embroidered` 等词：

- 将其 normalize 为 `flat ink print` / `flat graphic`。
- 不要让这些词原样进入最终 positive prompt。

## 验收

- 胸口不再出现口袋。
- 印花是平面油墨印刷效果，不是刺绣、贴布、布章、凸起胶章。
- 正向 prompt 中不再出现 `patch-like`、`embroidered`、`stitched` 等诱导词。
- negative prompt 中包含 pocket / embroidery / raised print / applique 相关禁止词。

## 验证结果 ✅ (updated V7.1)

```
python src/manage.py check
→ System check identified no issues (0 silenced).

python -m pytest tests/test_product_models.py tests/test_export.py tests/test_prompt_loader.py -q
→ 48 passed in 0.54s

python src/manage.py sync_prompts
→ 6 created, 4 updated, 1 risky keyword normalized (screen-print texture → flat ink texture)
```

---

# 追加任务：修复旧 PromptPreset 没有被清理的问题

## 现象

用户看到预设列表有 16 条，但磁盘上 `data/prompts/white` 和 `data/prompts/black` 只有 10 个 `.md`。

ChatGPT 已确认数据库中多出的 6 条是旧文件重命名前留下的 active 记录：

- `03-white-minimal-vintage-patch-print`
- `04-white-back-sunburst-petal-print`
- `01-black-colorful-floral-horse-back-print`
- `02-black-gold-ornamental-crest-back-print`
- `03-black-red-abstract-v-back-print`
- `05-black-small-tan-cute-patch-print`

这些旧记录没有产品关联，ChatGPT 已直接从数据库删除，当前数据库恢复为 10 条 active preset。

## 根因

`apps.categories.prompt_sync.sync_prompt_presets_from_disk()` 里判断旧数据是否属于同步目录时使用：

```python
if preset.md_file and 'data/prompts' in str(preset.md_file):
```

但 Windows 数据库里保存的是：

```text
data\prompts\white\xxx.md
```

反斜杠导致 `'data/prompts'` 判断失败，所以 stale preset 没有被停用。

另外 `cleanup_old_presets.py` 只要路径里有 `white` 或 `black` 就跳过，没有检查 `md_file` 指向的文件是否还存在，所以重命名后的旧记录也会被保留。

## Claude 需要修复

### Task G：路径规范化 ✅ 已完成

在 `prompt_sync.py` 和 `cleanup_old_presets.py` 里统一使用路径规范化：

```python
def _norm_rel_path(value: str) -> str:
    return str(value or '').replace('\\', '/')
```

判断是否属于同步目录时使用：

```python
rel = _norm_rel_path(preset.md_file)
is_synced_prompt = rel.startswith('data/prompts/')
```

### Task H：同步时处理磁盘已不存在的旧记录 ✅ 已完成

同步后，对于 active preset：

- 如果 `md_file` 属于 `data/prompts/`
- 且对应磁盘文件不存在
- 且没有产品关联

则删除该 `PromptPreset`。

如果有产品关联，则不要删除，改为：

```python
preset.is_active = False
preset.save(update_fields=['is_active'])
```

### Task I：cleanup_old_presets 命令也按”文件存在性”处理 ✅ 已完成

`cleanup_old_presets.py` 不应只因为路径里有 `white` 或 `black` 就保留。

正确逻辑：

- 文件存在且在 `data/prompts/white|black` 下：保留。
- 文件不存在且无产品关联：删除。
- 文件不存在但有产品关联：停用。
- 不属于自动同步目录的手动上传 preset：默认不硬删。

### 验收

1. 当前数据库 active preset 数量应等于磁盘 `data/prompts/white/*.md + data/prompts/black/*.md` 数量，即 10。
2. 重命名一个 `.md` 后运行同步，不会出现旧新两条都 active。
3. Windows 路径 `data\prompts\...` 和 POSIX 路径 `data/prompts/...` 都能正确识别。
4. `python src\manage.py sync_prompts` 后不会把已删除/重命名的旧 prompt 留在列表里。

---

# 新增任务：POD 贴图生成模式（不影响现有 V7 直出）

## 背景

用户希望在保留当前“AI 直出完整 T 恤商品图”功能不受影响的前提下，新增一条 POD 贴图生成路线。

当前 V7 直出模式继续保留：

```text
Product PromptPreset(.md) → ComfyUI txt2img → 完整 T 恤商品图
```

新增 POD 模式目标：

```text
PrintDesignPreset(.md) → ComfyUI 生成平面印花 PNG → ComfyUI 去背景 → 保存印花 PNG → ComfyUI 贴到 TShirtTemplate 的框选胸口区域 → 保存最终商品图
```

用户已确认：

- 印花 prompt 和产品图 prompt 必须分开管理。
- POD 模式继续通过 `.md` prompt 生成平面印花。
- 同一分类支持一次生成 N 个随机不同印花产品。
- 平面印花 PNG 要保存到系统，方便复用。
- 图片操作尽量用 ComfyUI，Django 只做调度和保存。
- T 恤模板复用现有 `TShirtTemplate` 模板管理。
- 在模板管理里手动框选印花区域。
- 可以使用 LogoRedmond LoRA 生成 logo/印花类图案，但只用于 POD 印花生成，不影响 V7 直出商品图。

## 已阅读的外部 workflow

用户提供了：

```text
C:\Users\VincentLin\WorkBuddy\2026-06-06-13-02-36\workflow_a_flat_template.json
```

该 workflow 是 ComfyUI 前端 UI 格式，不是 API workflow。节点结构：

- `LoadImage`：T 恤平铺模板图，widgets: `T恤平铺模板.jpg`
- `LoadImage`：印花图，widgets: `印花.png`
- `LoadImage`：mask，widgets: `mask_flat.png`
- `ImageResize+`：将印花缩放到 `200 x 200`，`lanczos`，`keep proportion`
- `ImageCompositeMasked`：把印花合成到模板图，x=`320`，y=`180`
- `SaveImage`：输出 `成品_平铺`

可学习点：

- 合成逻辑非常适合第一版 POD 平铺/挂拍模板贴图。
- 需要 `ImageCompositeMasked`。
- 需要把前端 UI JSON 改写为后端 API workflow 字典。
- `ImageResize+` 是插件节点，可能不是所有 ComfyUI 都有；为了高可用，优先使用 ComfyUI 内置或确认可用节点。若继续用 `ImageResize+`，设置页必须检查节点是否存在。

不要直接把这个 JSON 原样用于 API。

---

## 总体原则

1. **不能影响现有 V7 直出商品图模式。**
2. 新增 POD 模式必须有独立入口、独立 prompt 类型、独立 ComfyUI workflow。
3. 产品图 prompt 和印花 prompt 必须分离，不能混扫、不能混选。
4. 第一版只支持正面胸口平面贴图，不做后背、不做模特、不做复杂褶皱变形。
5. 所有生成出的印花 PNG 都保存并和产品/候选关联。

---

## Task 1：拆分 Prompt 类型和目录 ✅ 已完成

### 数据模型

新增模型建议：

```python
class PrintDesignPreset(models.Model):
    SHIRT_COLOR_CHOICES = [
        ('white', '白色 T 恤'),
        ('black', '黑色 T 恤'),
        ('other', '其他'),
    ]
    name = models.CharField(max_length=256, unique=True)
    slug = models.SlugField(max_length=256, unique=True)
    shirt_color = models.CharField(max_length=16, choices=SHIRT_COLOR_CHOICES, default='white')
    content = models.TextField(help_text='只描述平面印花，不描述 T 恤/衣架/场景')
    negative_prompt = models.TextField(blank=True, default='')
    variation_pool = models.JSONField(default=dict, blank=True)
    md_file = models.FileField(upload_to='print_prompts/', blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

现有 `PromptPreset` 继续用于产品图直出。可以在 UI 上显示为“产品图提示词”。

### 目录约定

产品图 prompt：

```text
data/product_prompts/white/
data/product_prompts/black/
```

印花 prompt：

```text
data/print_prompts/white/
data/print_prompts/black/
```

迁移/同步时：

- 现有 10 个胸口商品图 prompt 属于 `product_prompts`。
- 新增 POD 印花 prompt 必须放入 `print_prompts`。
- 同步函数不能再从 `data/prompts` 混合读取两类 prompt。

### 测试

- `ProductPromptPreset` / 现有 `PromptPreset` 不会出现在 POD 印花选择里。
- `PrintDesignPreset` 不会出现在 V7 直出商品图选择里。

---

## Task 2：生成印花 prompt 的随机变体机制 ✅ 已完成

用户觉得同一提示词生成很相似，因此 POD 模式必须支持同类 prompt 批量随机生成。

### 规则

每次生成印花时：

- 随机 seed。
- 从 `variation_pool` 中随机抽取配色、构图、元素、印刷质感。
- 如果 `.md` 没写 variation pool，用系统默认池。

建议 `.md` 支持：

```markdown
## PRINT DESIGN

flat vector-style decorative graphic, no text, no human, no logo, white background

## VARIATION POOL

color_palettes:
- coral red, sunny yellow, grass green, royal blue
- muted orange, cream, forest green
- cobalt blue, white, soft purple

composition:
- compact center emblem
- circular decorative motif
- scattered icon cluster

elements:
- star, leaf, flower, abstract dot
- flame, wave, geometric block

texture:
- flat ink print
- clean vector ink
- slightly distressed flat ink

## NEGATIVE

text, letters, words, typography, human, face, body, hand, logo, watermark, mockup, t-shirt, clothing, hanger, product photo, 3d, embroidery, patch, pocket
```

### 实现建议

新增服务函数：

```python
build_random_print_prompt(preset: PrintDesignPreset, seed: int) -> tuple[str, str, dict]
```

返回：

- positive prompt
- negative prompt
- metadata：抽到的 palette/composition/elements/texture/seed

注意：印花 prompt 中禁止描述 T 恤、衣架、衣柜、商品图。

---

## Task 3：LogoRedmond LoRA 只用于 POD 印花生成 ✅ 已完成

当前 `src/apps/generation/comfyui.py` 没有 `LoraLoader`，所以 LogoRedmond 目前没有被使用。

请新增 POD 印花生成 workflow，支持可配置 LoRA：

设置项建议：

```python
PRINT_GEN_CHECKPOINT = 'sd_xl_turbo_1.0_bf16.safetensors'
PRINT_LOGO_LORA_NAME = 'LogoRedmondV2-Logo-LogoRedAF.safetensors'
PRINT_LOGO_LORA_STRENGTH_MODEL = 0.8
PRINT_LOGO_LORA_STRENGTH_CLIP = 0.8
```

注意用户提到的文件名可能是：

```text
LogoRedmondV2-Logo-LogoRedmAF.safetensors
```

方案文档里写的是：

```text
LogoRedmondV2-Logo-LogoRedAF.safetensors
```

不要硬编码死，做成设置页可选或 config 可编辑。

POD 印花生成 workflow 应包含：

- `CheckpointLoaderSimple`
- `LoraLoader`
- `CLIPTextEncode` positive
- `CLIPTextEncode` negative
- `EmptyLatentImage`
- `KSampler`
- `VAEDecode`
- `SaveImage`

Turbo 参数建议：

- steps: `1`
- cfg: `1.0`
- sampler: `euler`
- scheduler: `sgm_uniform`
- width/height: `1024`

如果用户当前 ComfyUI 没有 SDXL Turbo/LogoRedmond，必须有 fallback 或清晰错误提示，不能影响现有 V7 直出。

---

## Task 4：ComfyUI 去背景 workflow ✅ 已完成

POD 模式生成印花后要保存透明 PNG。

优先使用 ComfyUI：

1. 如果 ComfyUI 有 RMBG 节点，使用 RMBG。
2. 如果没有 RMBG，但印花是白底，使用白底 alpha/mask 方案。
3. 如果两者都不可用，提示用户安装插件，不要继续生成错误商品图。

新增 provider 方法建议：

```python
generate_print_design(prompt, negative, params) -> ImageResult
remove_print_background(image) -> ImageResult
```

保存：

- 原始印花图
- 去背景透明印花 PNG

---

## Task 5：复用 TShirtTemplate 并支持手动框选印花区域 ✅ 已完成

在现有 `TShirtTemplate` 上增加 POD 字段，不新建重复模板表：

```python
is_pod_template = models.BooleanField(default=False)
template_view = models.CharField(max_length=16, default='front')  # first version only front
print_area_x = models.IntegerField(null=True, blank=True)
print_area_y = models.IntegerField(null=True, blank=True)
print_area_width = models.IntegerField(null=True, blank=True)
print_area_height = models.IntegerField(null=True, blank=True)
```

模板编辑页增加：

- “可用于 POD 贴图”开关。
- 图片预览。
- 鼠标拖拽矩形框选胸口印花区域。
- 将浏览器显示坐标换算成原图像素坐标保存。

模板列表显示：

- POD 可用 / 不可用。
- 已设置印花区域 / 未设置印花区域。

POD 生成只能选择：

- `is_pod_template=True`
- `template_view='front'`
- 已设置完整 `print_area_*`
- 模板颜色匹配 prompt 颜色。

---

## Task 6：POD 平铺模板合成 workflow ✅ 已完成

参考用户提供的 `workflow_a_flat_template.json`，但要改成 API workflow。

基础节点：

- Load template image
- Load transparent print image
- Resize print to fit `TShirtTemplate.print_area_width/height`
- Composite print onto template at `print_area_x/y`
- Save output

优先使用高可用节点：

- `ImageCompositeMasked` 可用。
- Resize 节点要检测 ComfyUI 是否支持。如果 `ImageResize+` 不存在，使用当前 ComfyUI 可用的内置 resize/scale 节点，或者给出明确错误。

合成时：

- 不要改变模板本身。
- 印花必须限制在框选区域。
- 第一版不做袖子、不做后背、不做口袋位置。

---

## Task 7：数据保存 ✅ 已完成

新增模型建议：

```python
class PrintDesign(models.Model):
    preset = models.ForeignKey(PrintDesignPreset, on_delete=models.PROTECT)
    shirt_color = models.CharField(max_length=16)
    prompt = models.TextField()
    negative_prompt = models.TextField(blank=True, default='')
    variation_metadata = models.JSONField(default=dict, blank=True)
    seed = models.IntegerField(default=0)
    raw_image = models.ImageField(upload_to='prints/raw/%Y/%m/', blank=True, null=True)
    transparent_image = models.ImageField(upload_to='prints/transparent/%Y/%m/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

产品关联：

- `Product` 可新增 `generation_mode`：`direct` / `pod`
- `Product` 或 `ProductSKU` 关联 `PrintDesign`
- 最终商品图仍保存到 `ProductSKU.mockup_image`

不要破坏旧 Product 数据。

---

## Task 8：创建产品页面新增生成模式 ✅ 已完成

创建产品页增加模式选择：

1. `AI 直出商品图`：现有功能，保持不变。
2. `POD 贴图模式`：新功能。

选择 POD 时显示：

- 印花提示词分类：`PrintDesignPreset`
- 颜色：white/black
- 数量 N
- POD 模板：从 `TShirtTemplate` 筛选
- 是否保存原始印花图：默认保存
- 是否保存透明印花图：默认保存

POD 模式支持用户确认的批量策略：

```text
同一个分类一次生成 N 个不同印花产品
```

每个产品都随机变体，不要 N 个一模一样。

---

## Task 9：测试与验收 ✅ 已完成 (60 passed)

必须覆盖：

- 现有 V7 direct 模式仍然可以创建产品，使用原 `PromptPreset`。
- POD 模式只显示 `PrintDesignPreset`。
- `PrintDesignPreset` 随机变体同一 preset 多次生成 prompt 不完全相同。
- 模板框选坐标保存为原图像素坐标。
- 没有 POD 模板或没有框选区域时，POD 创建给出明确错误。
- LogoRedmond LoRA 配置只影响 POD 印花生成，不影响 direct 模式。
- `python src\manage.py check` 通过。
- 现有测试通过。

建议验证命令：

```powershell
python src\manage.py check
python -m pytest tests/test_product_models.py tests/test_export.py tests/test_prompt_loader.py -q
```

如新增测试文件，例如 `tests/test_pod_generation.py`、`tests/test_template_print_area.py`，也必须运行。

---

## 第一版范围限制

第一版不要做：

- 后背印花。
- 模特模板和褶皱 Transform。
- IC-Light 换背景。
- 自动从杂乱样图库挑模板。
- 自动检测胸口区域。
- 改动现有 V7 direct workflow。

第一版只做：

- 平面印花生成。
- 透明背景处理。
- 保存印花 PNG。
- 手动框选模板胸口区域。
- ComfyUI 平铺/挂拍模板贴图。
- 批量 N 个随机变体产品。

---

# 重要修正：POD 印花提示词也需要网页上传和预设管理

## 用户最新确认

之前关于“POD 印花提示词不能手动上传、不能在提示词预设里管理”的理解是错误的。

用户最新要求是：

- POD 印花提示词需要支持网页手动上传。
- POD 印花提示词需要能在“提示词预设”里管理。
- 但必须清楚区分：
  - AI 直出商品图提示词
  - POD 平面印花提示词

## Claude 需要按此修正设计

### Task J：提示词预设页面管理两类 prompt ✅ 已完成

现有“提示词预设”页面不要只管理 AI 直出商品图 prompt。

请改成同一个入口下管理两类预设，建议用 Tab 或筛选：

- `产品图提示词`
- `印花提示词`

要求：

- 产品图提示词仍对应现有 `PromptPreset` / direct 模式。
- 印花提示词对应新增 `PrintDesignPreset` / POD 模式。
- 两类 prompt 不混用，但可以在同一个“提示词预设”页面管理。

### Task K：上传时选择 prompt 类型 ✅ 已完成

上传 `.md` 时需要让用户选择类型：

- `产品图提示词`：用于现有 AI 直出商品图。
- `印花提示词`：用于 POD 贴图模式，只生成平面印花 PNG。

上传后：

- 产品图提示词进入 `PromptPreset`。
- 印花提示词进入 `PrintDesignPreset`。

### Task L：列表和编辑页明确类型 ✅ 已完成

预设列表中每条提示词必须显示类型 badge：

- `产品图`
- `印花`

编辑页也要根据类型显示不同说明：

- 产品图 prompt 可以包含 T 恤、衣柜、商品图场景。
- 印花 prompt 不能描述 T 恤、衣架、商品图场景，只描述平面图案。

### Task M：创建产品时按模式筛选 ✅ 已完成

创建产品页面：

- 选择 `AI 直出商品图` 时，只显示产品图提示词。
- 选择 `POD 贴图模式` 时，只显示印花提示词。

两类预设可以在同一个后台入口管理，但不能在生成时互相混用。

### Task N：目录同步仍保留，但不是唯一入口 ✅ 已完成

目录自动同步仍然可以保留：

- `data/product_prompts/white|black`
- `data/print_prompts/white|black`

但网页手动上传也必须可用。

### 验收

- 用户可以在网页上传 POD 印花 `.md`。
- 用户可以在“提示词预设”页面看到并编辑 POD 印花提示词。
- 页面上两类提示词有明显类型标识。
- Direct 模式不会显示印花提示词。
- POD 模式不会显示产品图提示词。

---

# 追加任务：模板上传页仍是旧版豆包分析流程，需适配 POD 模板

## 当前问题

用户反馈：模板管理里“上传 T 恤模板”还是旧版流程，页面文案和提交逻辑仍然是“上传后提交给豆包分析版型”，不能适配现在的 POD 模板贴图。

ChatGPT 已检查当前代码：

- `TShirtTemplate` 模型已经有 POD 字段：
  - `is_pod_template`
  - `template_view`
  - `print_area_x`
  - `print_area_y`
  - `print_area_width`
  - `print_area_height`
- `template_edit.html` 已经有 POD 框选区域 UI。
- 但 `template_upload.html` 仍显示：
  - “豆包会自动分析版型”
  - “上传模板（豆包自动分析版型）”
- `views.py::template_upload()` 仍强制调用：

```python
prompt_body = _analyze_template(image.read())
TShirtTemplate.objects.create(...)
```

这不适合 POD 标准模板上传。

## 修复目标

模板上传和编辑都要围绕两种用途清楚区分：

1. 普通/旧版模板：可保留 `prompt_body`，用于旧流程兼容。
2. POD 贴图模板：重点是上传标准模板图 + 标记 POD + 手动框选胸口印花区域。

不要在 POD 模板上传时强制调用豆包分析。

## Claude 需要修改

### Task O：改模板上传页文案和表单 ✅ 已完成

修改 `src/apps/dashboard/templates/dashboard/template_upload.html`：

- 去掉“豆包会自动分析版型”的提示。
- 按当前业务改成：
  - “上传 T 恤模板图”
  - “用于 AI 直出兼容 / POD 贴图模板”
- 增加开关：
  - `is_pod_template`：可用于 POD 贴图模式
- 增加说明：
  - POD 模板建议使用无印花、无口袋、无手、正面、纯色 T 恤模板。
  - 上传后可在编辑页框选胸口印花区域。
- 上传按钮文案改为：
  - “上传模板”

### Task P：改 template_upload 视图，不再强制豆包分析 ✅ 已完成

修改 `src/apps/dashboard/views.py::template_upload()`：

- 不要默认调用 `_analyze_template(image.read())`。
- `prompt_body` 默认为空，或接收用户手填字段。
- 创建模板时保存：
  - `name`
  - `color`
  - `image`
  - `fabric`
  - `sizes`
  - `is_pod_template`
  - `template_view='front'`
- 如果 `is_pod_template=True`，上传成功后建议 redirect 到 `template_edit`，让用户立刻框选印花区域。
- 如果非 POD，可仍 redirect 到模板列表。

示例逻辑：

```python
tpl = TShirtTemplate.objects.create(
    name=name,
    color=color,
    image=image,
    fabric=fabric,
    sizes=sizes,
    prompt_body=request.POST.get('prompt_body', ''),
    is_pod_template=request.POST.get('is_pod_template') == 'on',
    template_view='front',
)
if tpl.is_pod_template:
    messages.success(request, '模板上传成功，请框选胸口印花区域')
    return redirect('template_edit', tid=tpl.id)
messages.success(request, '模板上传成功')
return redirect('template_list')
```

### Task Q：改 template_edit 替换图片逻辑 ✅ 已完成

当前 `template_edit()` 替换图片时仍会调用：

```python
t.prompt_body = _analyze_template(request.FILES['image'].read())
```

请改为：

- 替换图片不自动分析豆包。
- 如果替换图片，清空或保留旧 print_area 坐标需要有明确策略。
- 推荐：替换图片后清空 `print_area_*`，提示用户重新框选，因为图片尺寸/构图可能变了。

示例：

```python
if request.FILES.get('image'):
    t.image = request.FILES['image']
    t.print_area_x = None
    t.print_area_y = None
    t.print_area_width = None
    t.print_area_height = None
```

### Task R：模板列表显示 POD 状态 ✅ 已完成

修改 `template_list.html`：

- 显示 `POD 可用` badge。
- 如果 `is_pod_template=True` 但没有完整 `print_area_*`，显示 `未框选印花区域` 警告。
- 如果已设置完整框选区域，显示 `已框选印花区域`。

### Task S：POD 模式只允许选择已框选模板 ✅ 已完成

创建 POD 产品时：

- 必须过滤 `is_pod_template=True`
- 必须过滤 `template_view='front'`
- 必须要求 `print_area_x/y/width/height` 都不为空
- 颜色要匹配 POD 印花 prompt 的 `shirt_color`

如果没有可用模板，页面要给明确提示：

```text
请先在 T恤模板管理中上传 POD 模板，并框选胸口印花区域。
```

## 验收

- 上传模板页面不再出现“豆包自动分析版型”。
- 上传 POD 模板后跳转到编辑页，让用户框选区域。
- 替换模板图片不会调用豆包分析，并会要求重新框选。
- 模板列表能看出哪些模板可用于 POD，哪些还没框选区域。
- 现有非 POD 模板仍可保留，不影响旧数据。

---

# 追加任务：修复模板印花区域框选坐标错位和无实时预览

## 当前问题

用户反馈：

- 在模板编辑页框选印花区域时，保存出来的框选位置和实际选择的位置不一致。
- 鼠标拖动时没有实时显示框选框，只在松开鼠标后显示。

## 根因

ChatGPT 已检查 `src/apps/dashboard/templates/dashboard/template_edit.html`：

当前实现中：

```html
<canvas id="printAreaCanvas" style="position:absolute;top:0;left:0;width:100%;height:100%;"></canvas>
```

但 JS 没有设置：

```js
canvas.width = img.clientWidth
canvas.height = img.clientHeight
```

因此 canvas 的内部绘图尺寸仍是浏览器默认 `300x150`，而 CSS 显示尺寸是图片尺寸。绘制和坐标换算使用的不是同一个坐标系，导致框选位置错位。

另外当前只监听 `mousedown` 和 `mouseup`，没有 `mousemove`，所以拖动时不会实时显示矩形框。

## Claude 需要修复

### Task T：重写模板框选 JS 坐标逻辑 ✅ 已完成

修改 `template_edit.html` 的框选脚本：

1. 图片加载后调用 `syncCanvasSize()`：

```js
function syncCanvasSize() {
    const img = document.getElementById('templateImg');
    const canvas = document.getElementById('printAreaCanvas');
    if (!img || !canvas) return;
    const rect = img.getBoundingClientRect();
    canvas.width = Math.round(rect.width);
    canvas.height = Math.round(rect.height);
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    drawExistingSelection();
}
```

2. 使用显示坐标绘制，使用原图坐标保存。

关键函数：

```js
function displayToNatural(x, y) {
    const img = document.getElementById('templateImg');
    const rect = img.getBoundingClientRect();
    return {
        x: Math.round(x * img.naturalWidth / rect.width),
        y: Math.round(y * img.naturalHeight / rect.height)
    };
}

function naturalToDisplay(x, y) {
    const img = document.getElementById('templateImg');
    const rect = img.getBoundingClientRect();
    return {
        x: x * rect.width / img.naturalWidth,
        y: y * rect.height / img.naturalHeight
    };
}
```

3. 增加 `mousemove` 实时绘制：

```js
let dragging = false;
let start = null;
let current = null;

canvas.addEventListener('mousedown', function(e) {
    dragging = true;
    start = getCanvasPoint(e);
    current = start;
    drawSelection(start, current);
});

canvas.addEventListener('mousemove', function(e) {
    if (!dragging) return;
    current = getCanvasPoint(e);
    drawSelection(start, current);
});

canvas.addEventListener('mouseup', finishSelection);
canvas.addEventListener('mouseleave', function(e) {
    if (dragging) finishSelection(e);
});
```

4. `getCanvasPoint(e)` 必须基于 `canvas.getBoundingClientRect()`，返回 canvas 显示坐标：

```js
function getCanvasPoint(e) {
    const rect = canvas.getBoundingClientRect();
    return {
        x: Math.max(0, Math.min(e.clientX - rect.left, rect.width)),
        y: Math.max(0, Math.min(e.clientY - rect.top, rect.height))
    };
}
```

5. `finishSelection()` 将显示坐标矩形换算成原图坐标，写入 hidden/input：

```js
const n1 = displayToNatural(x, y);
const n2 = displayToNatural(x + w, y + h);
print_area_x = n1.x
print_area_y = n1.y
print_area_width = n2.x - n1.x
print_area_height = n2.y - n1.y
```

6. 页面加载时如果已有 `print_area_*`，必须画出已有框选区域。

7. window resize 后重新同步 canvas 尺寸并重绘。

### Task U：改善表单字段 ✅ 已完成

当前坐标 input 是 `readonly`，可以保留，但建议同时显示：

- 原图坐标。
- 提示“框选区域会按原图像素保存”。

### Task V：测试/验证 ✅ 60 passed

手动验证步骤：

1. 上传一张 1024x1024 模板图。
2. 在页面显示尺寸例如 400x400 时框选显示坐标 `(100,100)` 到 `(300,300)`。
3. 输入框应保存约：

```text
x=256, y=256, width=512, height=512
```

4. 鼠标拖动过程中能实时看到绿色虚线框。
5. 保存后重新进入编辑页，框选框显示在原来选择的位置。
---

# 追加任务：提示词预设页增加“同步提示词”按钮，并支持同步印花提示词

## 用户反馈

ChatGPT 已经把新的 POD 印花提示词 `.md` 文件放到了：

```text
data/print_prompts/white/
data/print_prompts/black/
```

但用户在前端「提示词预设」页面看不到这些印花提示词。

用户明确要求：

> 在前端提示词预设里加个同步提示词的按钮

## 当前发现

请检查并修改：

```text
src/apps/dashboard/views.py
src/apps/dashboard/templates/dashboard/preset_list.html
src/apps/categories/prompt_sync.py
```

当前 `preset_list()` 里已有同步逻辑：

```python
if request.GET.get('sync') == '1' or not PromptPreset.objects.exists():
    from apps.categories.prompt_sync import sync_prompt_presets_from_disk
    sync_prompt_presets_from_disk()
```

问题：

1. 这个同步只调用了 `sync_prompt_presets_from_disk()`，只能同步产品图提示词 `PromptPreset`。
2. 没有调用 `sync_print_presets_from_disk()`，所以 `data/print_prompts/white|black/*.md` 不会进入 `PrintDesignPreset`。
3. `preset_list.html` 顶部只有「上传 .md 文件」和「批量删除」，没有显式「同步提示词」按钮。
4. 用户放入磁盘目录的 `.md` 文件应该能通过前端按钮同步，不需要进命令行跑 `python src/manage.py sync_print_prompts`。

## 修复目标

在「提示词预设」页面顶部增加一个按钮：

```text
同步提示词
```

建议按钮行为：

- 当前 tab 是 `产品图提示词`：同步 `data/prompts/white|black/*.md` 到 `PromptPreset`
- 当前 tab 是 `印花提示词`：同步 `data/print_prompts/white|black/*.md` 到 `PrintDesignPreset`
- 当前 tab 是 `全部`：两个都同步
- 保留当前颜色筛选参数，点击同步后仍停留在当前筛选视图

## 推荐实现

### Task A：升级 `preset_list()` 的同步逻辑 ✅ 已完成

修改 `src/apps/dashboard/views.py` 中 `preset_list()`：

1. 读取：

```python
sync_requested = request.GET.get('sync') == '1'
```

2. 当 `sync_requested` 时，根据当前 `ptype` 同步：

```python
from apps.categories.prompt_sync import (
    sync_prompt_presets_from_disk,
    sync_print_presets_from_disk,
)

sync_results = {}
if ptype in ('product', 'all'):
    sync_results['product'] = sync_prompt_presets_from_disk()
if ptype in ('print', 'all'):
    sync_results['print'] = sync_print_presets_from_disk()
```

3. 首次加载时也要分别处理：

```python
if not PromptPreset.objects.exists():
    sync_prompt_presets_from_disk()
if not PrintDesignPreset.objects.exists():
    sync_print_presets_from_disk()
```

注意：不要让产品图表为空时只同步产品图，印花表为空也要自动同步印花提示词。

4. 同步完成后用 `messages.success()` 给用户反馈，例如：

```text
已同步提示词：产品图 新增 0 / 更新 10 / 清理 0；印花 新增 6 / 更新 0 / 清理 0
```

如果 `errors` 非空，用 `messages.warning()` 展示简短错误数量，详细错误可以打印到日志，避免页面太乱。

### Task B：列表页顶部增加按钮 ✅ 已完成

修改：

```text
src/apps/dashboard/templates/dashboard/preset_list.html
```

在顶部按钮区域加入：

```html
<a href="?type={{ selected_type }}{% if selected_color %}&color={{ selected_color }}{% endif %}&sync=1"
   class="btn btn-outline-success rounded-pill">
    <i class="bi bi-arrow-repeat"></i> 同步提示词
</a>
```

按钮位置建议放在「上传 .md 文件」左边或右边。

注意当前模板文件可能出现中文乱码显示，请用 UTF-8 正确保存，避免继续扩大乱码问题。

### Task C：确认 `sync_print_presets_from_disk()` 能同步 ChatGPT 新放入的 6 个文件 ✅ 已完成

需要确认以下文件能进入 `PrintDesignPreset`：

```text
data/print_prompts/white/01-flat-retro-garden-badge.md
data/print_prompts/white/02-flat-abstract-brush-symbol.md
data/print_prompts/white/03-flat-vintage-sun-floral-emblem.md
data/print_prompts/black/01-flat-neon-botanical-symbol.md
data/print_prompts/black/02-flat-gold-ornamental-ink-crest.md
data/print_prompts/black/03-flat-red-white-smoke-abstract.md
```

同步后在前端：

- `?type=print` 应该能看到 6 条印花提示词
- `?type=print&color=white` 应该看到 3 条
- `?type=print&color=black` 应该看到 3 条

## 验证

请至少执行：

```powershell
cd C:\Users\VincentLin\PycharmProjects\tk-erp
python src\manage.py sync_print_prompts
python src\manage.py shell -c "from apps.categories.models import PrintDesignPreset; print(PrintDesignPreset.objects.filter(is_active=True).count())"
python src\manage.py test
```

并手动打开：

```text
/presets/?type=print&sync=1
```

确认页面能显示印花提示词。

## 重要约束

1. 不要影响 AI 直出产品图提示词 `PromptPreset` 的现有生成方式。
2. 不要把 `data/print_prompts` 的提示词同步进 `PromptPreset`。
3. 不要把 `data/prompts` 的产品图提示词同步进 `PrintDesignPreset`。
4. 同步按钮只负责“从磁盘导入/更新数据库”，不要触发生成图片。
5. 现有上传 `.md` 功能继续保留。
---

# 追加修正：POD 印花生成不要自动换模型，改为高质量依赖校验和缺失提示

## 用户最新要求

用户明确说：

> 不用改模型，还是用效果最好的模型，缺什么和我说，我会下载

因此，前一条“自动 fallback 到可用 checkpoint”的建议需要调整：

- 不要为了高可用自动换成别的 checkpoint。
- POD 印花生成应坚持使用配置里的高质量/指定模型。
- 如果 ComfyUI 缺少模型或 LoRA，应在前端/日志中明确告诉用户缺什么、放到哪里，而不是悄悄换模型导致效果不一致。

## 当前本机 ComfyUI 检查结果

ChatGPT 通过 ComfyUI API 查到当前 checkpoint 列表：

```text
DreamShaper_8_pruned.safetensors
juggernautXL_ragnarokBy.safetensors
sd_xl_base_1.0_0.9vae.safetensors
sd_xl_offset_example-lora_1.0.safetensors
```

当前 LoRA 列表：

```text
Tshirts_05310656.safetensors
_diagnose_test.safetensors
tshirt_06031842.safetensors
```

当前 `data/config.json`：

```json
{
  "comfyui_model": "juggernautXL_ragnarokBy.safetensors",
  "print_checkpoint": "sd_xl_turbo_1.0_bf16.safetensors",
  "print_lora_name": "",
  "print_lora_strength_model": 0.8,
  "print_lora_strength_clip": 0.8
}
```

所以当前缺失：

```text
models/checkpoints/sd_xl_turbo_1.0_bf16.safetensors
```

如果后续要启用 LogoRedmond：

```text
models/loras/LogoRedmondV2-Logo-LogoRedmAF.safetensors
```

注意：LogoRedmond 是 LoRA，不是 checkpoint。

## 修复目标

修改 `src/apps/generation/comfyui.py`，不要自动 fallback 改模型。

改成：

1. 生成 POD 印花前，校验 `print_checkpoint` 是否存在于 ComfyUI `CheckpointLoaderSimple` 可用列表。
2. 如果不存在，立即抛出清晰异常，不要提交错误工作流给 ComfyUI。
3. 异常信息必须包含：
   - 缺失 checkpoint 名称
   - 当前 ComfyUI 已安装 checkpoint 列表
   - 建议下载位置：`ComfyUI/models/checkpoints/`
   - 提醒下载后重启或刷新 ComfyUI
4. 如果 `print_lora_name` 非空，也校验它是否存在于 `LoraLoader` 可用列表。
5. 如果 LoRA 不存在，同样抛出清晰异常，提示放到 `ComfyUI/models/loras/`。
6. 页面上生成失败时应能看到友好的错误消息，不要只在后台线程里静默失败。

## 推荐实现

### Task A：新增 ComfyUI 模型/LoRA 查询方法

已有：

```python
get_available_checkpoints()
```

请再增加：

```python
def get_available_loras(self) -> list[str]:
    try:
        resp = self.client.get(f'{self.base_url}/object_info/LoraLoader')
        resp.raise_for_status()
        data = resp.json()
        return list(data['LoraLoader']['input']['required']['lora_name'][0])
    except Exception:
        return []
```

### Task B：新增 POD 依赖校验

例如：

```python
def _validate_pod_dependencies(self, checkpoint: str, lora_name: str = '') -> None:
    checkpoints = self.get_available_checkpoints()
    if checkpoints and checkpoint not in checkpoints:
        raise ValueError(
            'POD 印花生成缺少 ComfyUI checkpoint：'
            f'{checkpoint}。请下载到 ComfyUI/models/checkpoints/ 后刷新或重启 ComfyUI。'
            f'当前可用 checkpoint：{", ".join(checkpoints)}'
        )

    if lora_name:
        loras = self.get_available_loras()
        if loras and lora_name not in loras:
            raise ValueError(
                'POD 印花生成缺少 ComfyUI LoRA：'
                f'{lora_name}。请下载到 ComfyUI/models/loras/ 后刷新或重启 ComfyUI。'
                f'当前可用 LoRA：{", ".join(loras)}'
            )
```

在 `generate_print_design()` 中，在构建 workflow 之前调用：

```python
self._validate_pod_dependencies(checkpoint, lora_name)
```

### Task C：保留指定模型参数

不要把 `print_checkpoint` 自动改成 `juggernautXL_ragnarokBy.safetensors`。

如果 `print_checkpoint` 是：

```text
sd_xl_turbo_1.0_bf16.safetensors
```

那就要求用户安装它。

如果后续用户把配置改成更好的 checkpoint，也必须按配置走。

### Task D：错误显示到前端

当前 `_run_pod_generation()` 是后台线程：

```text
src/apps/dashboard/views.py::_run_pod_generation
```

请确保捕获异常后：

- 产品状态变成 failed/error，或至少有可见错误字段/日志。
- 产品详情/列表能看到类似：

```text
POD 印花生成缺少 ComfyUI checkpoint：sd_xl_turbo_1.0_bf16.safetensors。
请下载到 ComfyUI/models/checkpoints/ 后刷新或重启 ComfyUI。
```

如果当前 Product 没有 error 字段，不要做大改；可以先使用现有日志/状态机制，或者新增最小字段/提示。

## 当前需要用户下载的文件

请在前端报错里提示用户当前至少缺：

```text
sd_xl_turbo_1.0_bf16.safetensors
```

放置目录：

```text
ComfyUI/models/checkpoints/
```

如果要启用 LogoRedmond，请提示还缺：

```text
LogoRedmondV2-Logo-LogoRedmAF.safetensors
```

放置目录：

```text
ComfyUI/models/loras/
```

## 重要约束

1. 不要自动 fallback 到其他 checkpoint。
2. 不要静默改变用户选择的生成模型。
3. 不要把 LoRA 当 checkpoint。
4. 缺依赖时要在生成前校验并给清晰提示。
5. 保持 AI 直出商品图模式不受影响。

---

# 追加任务：修复 POD 印花生成 ComfyUI checkpoint 不存在导致工作流校验失败

## 用户反馈

POD 贴图模式生成印花时，ComfyUI 报错：

```text
Failed to validate prompt for output 7:
* CheckpointLoaderSimple 1:
  - Value not in list: ckpt_name: 'sd_xl_turbo_1.0_bf16.safetensors'
    not in ['DreamShaper_8_pruned.safetensors',
            'juggernautXL_ragnarokBy.safetensors',
            'sd_xl_base_1.0_0.9vae.safetensors',
            'sd_xl_offset_example-lora_1.0.safetensors']
Output will be ignored
```

## 根因

ChatGPT 已检查：

```text
data/config.json
src/apps/generation/comfyui.py
```

当前 `data/config.json` 中：

```json
"print_checkpoint": "sd_xl_turbo_1.0_bf16.safetensors"
```

但用户本机 ComfyUI 的 checkpoint 列表不包含这个文件。

同时 `ComfyUIProvider.generate_print_design()` 当前默认按 Turbo 模型参数运行：

```python
steps = params.get('steps', 1)
cfg = params.get('cfg_scale', 1.0)
sampler_name = params.get('sampler_name', 'euler')
scheduler = params.get('scheduler', 'sgm_uniform')
```

如果 fallback 到普通 SDXL / JuggernautXL，只改 checkpoint 名称虽然能通过校验，但 1 step / cfg 1.0 的效果会很差。

## 修复目标

1. POD 印花生成不要因为配置了不存在的 checkpoint 而失败。
2. 优先使用用户当前 ComfyUI 中可用的 checkpoint。
3. 如果 `print_checkpoint` 不存在，自动 fallback 到：
   - `data/config.json` 里的 `comfyui_model`，如果它在 ComfyUI 可用列表中；
   - 否则优先选择 `juggernautXL_ragnarokBy.safetensors`；
   - 否则选择第一个可用 checkpoint。
4. 普通 SDXL 模型不要继续使用 Turbo 参数。
5. 不影响 AI 直出商品图的现有 `generate_image()` / `self.model` 流程。

## 推荐实现

### Task A：增加 POD checkpoint 解析函数 ✅ 已完成

在 `src/apps/generation/comfyui.py` 的 `ComfyUIProvider` 内增加一个方法，例如：

```python
def _resolve_print_checkpoint(self, configured_checkpoint: str) -> tuple[str, bool]:
    """
    返回 (checkpoint_name, is_turbo_like)
    如果 configured_checkpoint 不在 ComfyUI 可用列表中，则自动 fallback。
    """
```

实现逻辑：

1. 调用现有 `get_available_checkpoints()`。
2. 如果 `configured_checkpoint` 在列表里，使用它。
3. 否则读取 `_load_model_config()` 的主模型名，如果在列表里，使用主模型。
4. 否则如果列表包含 `juggernautXL_ragnarokBy.safetensors`，使用它。
5. 否则如果列表非空，使用第一个。
6. 如果列表为空，才继续使用配置值并让后续报错。

`is_turbo_like` 可以用名称判断：

```python
lower = checkpoint.lower()
is_turbo_like = 'turbo' in lower or 'lightning' in lower or 'hyper' in lower
```

### Task B：根据模型类型设置默认采样参数 ✅ 已完成

修改 `generate_print_design()`：

```python
configured_checkpoint = pod_config['print_checkpoint']
checkpoint, is_turbo_like = self._resolve_print_checkpoint(configured_checkpoint)
```

然后：

```python
if is_turbo_like:
    default_steps = 1
    default_cfg = 1.0
    default_sampler = 'euler'
    default_scheduler = 'sgm_uniform'
else:
    default_steps = 25
    default_cfg = 6.0
    default_sampler = 'dpmpp_2m'
    default_scheduler = 'karras'

steps = params.get('steps', default_steps)
cfg = params.get('cfg_scale', default_cfg)
sampler_name = params.get('sampler_name', default_sampler)
scheduler = params.get('scheduler', default_scheduler)
```

KSampler 里使用这些变量，不要硬编码：

```python
"sampler_name": sampler_name,
"scheduler": scheduler,
```

### Task C：修正默认配置 ✅ 已完成

把 `data/config.json` 中的：

```json
"print_checkpoint": "sd_xl_turbo_1.0_bf16.safetensors"
```

改成当前用户 ComfyUI 已存在的：

```json
"print_checkpoint": "juggernautXL_ragnarokBy.safetensors"
```

但注意：代码仍然必须保留 fallback 逻辑，因为其他机器或后续模型变化时仍可能不存在。

### Task D：前端设置页最好增加提示

如果设置页有模型选择：

```text
src/apps/dashboard/templates/dashboard/settings.html
```

请确认 POD 印花 checkpoint 使用的是 ComfyUI 实际可用列表，不要让用户保存一个 ComfyUI 不存在的模型。

如果当前设置页只配置主模型，也可以先不扩展 UI；至少要保证 `data/config.json` 的错误值不会导致生成失败。

## 验证步骤

请执行：

```powershell
cd C:\Users\VincentLin\PycharmProjects\tk-erp
python src\manage.py test
```

并手动验证：

1. 保持 ComfyUI 当前 checkpoint 列表不变。
2. 进入 POD 贴图模式。
3. 选择任意印花提示词生成。
4. ComfyUI 不再出现：

```text
Value not in list: ckpt_name: 'sd_xl_turbo_1.0_bf16.safetensors'
```

5. ComfyUI 日志中应能看到使用了：

```text
juggernautXL_ragnarokBy.safetensors
```

或其他实际可用 checkpoint。

## 重要约束

1. 不要改坏 AI 直出商品图模式。
2. 不要假设用户一定安装了 `sd_xl_turbo_1.0_bf16.safetensors`。
3. 不要要求用户必须下载 SDXL Turbo 才能运行。
4. POD 印花生成优先追求高可用，模型不存在时应自动 fallback。
5. 如果之后用户安装 `LogoRedmondV2-Logo-LogoRedmAF.safetensors` LoRA，只允许作为可选 LoRA；不能把它当 checkpoint 使用。
---

# 追加任务：修复 ImageCompositeMasked 缺少 resize_source 导致 POD 合成失败

## 用户反馈

用户已经自行安装/修复了 RMBG 去背节点。

现在只需要 Claude 修复第二个 ComfyUI 报错：

```text
Failed to validate prompt for output 6:
* ImageCompositeMasked 5:
  - Required input is missing: resize_source
Output will be ignored
```

## 根因

ChatGPT 通过用户当前 ComfyUI API 查询到 `ImageCompositeMasked` 的真实节点定义：

```text
required:
- destination
- source
- x
- y
- resize_source

optional:
- mask
```

也就是说，当前 ComfyUI 版本中 `resize_source` 是必填项。

项目当前 `src/apps/generation/comfyui.py::composite_pod_image()` 中的节点：

```python
"5": {"class_type": "ImageCompositeMasked",
      "inputs": {"destination": ["1", 0], "source": ["3", 0],
                 "x": x, "y": y, "mask": ["4", 0]}},
```

少了：

```python
"resize_source": False
```

## 修复要求

只修改 POD 合成工作流，不要改模型配置、不要改提示词、不要改 AI 直出模式。

在 `src/apps/generation/comfyui.py::composite_pod_image()` 的 `ImageCompositeMasked` 节点 inputs 中补充：

```python
"resize_source": False
```

修复后应类似：

```python
"5": {"class_type": "ImageCompositeMasked",
      "inputs": {
          "destination": ["1", 0],
          "source": ["3", 0],
          "x": x,
          "y": y,
          "resize_source": False,
          "mask": ["4", 0],
      }},
```

## 验证

请执行：

```powershell
cd C:\Users\VincentLin\PycharmProjects\tk-erp
python src\manage.py test
```

然后手动验证 POD 贴图模式生成：

1. ComfyUI 不再出现：

```text
Required input is missing: resize_source
```

2. 工作流能执行到 `pod_composite` 输出。
3. AI 直出商品图模式不受影响。

## 重要约束

1. 不要自动 fallback 模型。
2. 不要改 `print_checkpoint`。
3. 不要改去背节点逻辑。
4. 本次只修 `ImageCompositeMasked` 参数缺失。
---

# 追加任务：修复去背工作流旧节点名导致 missing_node_type

## 用户反馈

POD 贴图生成时报错：

```text
invalid prompt: {
  'type': 'missing_node_type',
  'message': "Node 'Image Remove Background (RMBG)' not found. The custom node may not be installed.",
  'details': "Node ID '#2'",
  'extra_info': {
    'node_id': '2',
    'class_type': 'Image Remove Background (RMBG)',
    'node_title': 'Image Remove Background (RMBG)'
  }
}
```

## 根因

用户当前 ComfyUI 已安装 `comfyui-rmbg`，但真实可用节点 class_type 不是：

```text
Image Remove Background (RMBG)
```

而是：

```text
RMBG
```

ChatGPT 已通过当前 ComfyUI API 查询确认：

```text
GET http://127.0.0.1:7860/object_info/RMBG
```

`RMBG` 节点定义：

```text
required inputs:
- image: IMAGE
- model: ["RMBG-2.0", "INSPYRENET", "BEN", "BEN2"]

optional inputs:
- sensitivity
- process_res
- mask_blur
- mask_offset
- invert_output
- refine_foreground
- background: ["Alpha", "Color"]
- background_color

outputs:
0 IMAGE
1 MASK
2 MASK_IMAGE
```

## 修复要求

修改：

```text
src/apps/generation/comfyui.py
```

在 `remove_print_background()` 中，把旧节点：

```python
"2": {"class_type": "Image Remove Background (RMBG)",
      "inputs": {"images": ["1", 0]}},
```

替换为当前 ComfyUI 实际存在的：

```python
"2": {
    "class_type": "RMBG",
    "inputs": {
        "image": ["1", 0],
        "model": "RMBG-2.0",
        "background": "Alpha",
        "process_res": 1024,
        "sensitivity": 1.0,
        "mask_blur": 0,
        "mask_offset": 0,
        "invert_output": False,
        "refine_foreground": False,
    }
},
```

保存图片节点继续使用输出 0：

```python
"3": {"class_type": "SaveImage",
      "inputs": {"filename_prefix": "pod_transparent", "images": ["2", 0]}},
```

因为 `RMBG` 的输出 0 是透明背景 IMAGE。

## 兼容建议

为了以后更稳，可以在构建去背 workflow 前通过 `/object_info` 检测可用节点：

1. 优先使用 `RMBG`
2. 如果没有 `RMBG`，再尝试 `BiRefNetRMBG`
3. 不要再使用不存在的旧 class_type：`Image Remove Background (RMBG)`

但本次最小修复只需要替换为 `RMBG` 即可。

## 验证

请执行：

```powershell
cd C:\Users\VincentLin\PycharmProjects\tk-erp
python src\manage.py test
```

手动验证 POD 生成：

1. ComfyUI 不再出现：

```text
Node 'Image Remove Background (RMBG)' not found
```

2. 去背步骤能输出 `pod_transparent`。
3. 后续合成步骤继续执行。

## 重要约束

1. 不要改模型配置。
2. 不要自动 fallback checkpoint。
3. 不要影响 AI 直出商品图模式。
4. 本次只修去背节点 class_type 和输入参数。
---

# 追加任务：POD 印花生成出 T 恤 mockup、背景矩形被贴到衣服上的问题

## 用户反馈

POD 贴图生成结果出现两个严重问题：

1. 印花生成阶段生成了“带 T 恤的商品图/mockup”，然后整件小 T 恤被贴到了用户模板 T 恤上。
2. 有些印花白色/灰色背景没有去掉，整个矩形背景被贴到了衣服上。

用户截图表现：

- 黑色 T 恤模板胸口贴了一个白/灰矩形。
- 矩形里甚至包含一件完整小黑 T 恤商品图。
- 另一个案例是羽毛图案，但白色背景矩形也被完整贴上去了。

## 根因分析

ChatGPT 已检查当前代码：

```text
src/apps/generation/print_variants.py
src/apps/generation/comfyui.py
src/apps/dashboard/views.py::_run_pod_generation
```

### 根因 A：印花 prompt 仍容易诱导模型生成 T 恤商品图

当前 `build_random_print_prompt()` 尾部追加：

```python
'flat graphic design, no text, no letters, no logo, no human, white background'
```

问题：

1. `white background` 会鼓励模型生成白底方图。
2. 部分印花 preset 内容里有 `t-shirt print design`、`for a black t-shirt`、`chest print` 等词，模型容易理解成“生成一张 T 恤商品图”。
3. negative 虽然有 `t-shirt, clothing, mockup`，但正向词仍然反复出现 T 恤语义，普通 SDXL/Juggernaut 很容易跑偏。

### 根因 B：去背失败会静默 passthrough 原图

当前 `remove_print_background()`：

```python
except Exception as e:
    pass

return ImageResult(
    images=[image],
    metadata={'method': 'passthrough', 'warning': 'RMBG node not available...'}
)
```

如果 RMBG 失败或输出不符合预期，系统会继续拿原始白底图去合成，用户看不到明确失败。

### 根因 C：合成时没有使用去背 mask，强行使用整块 SolidMask

当前 `composite_pod_image()`：

```python
"4": {"class_type": "SolidMask",
      "inputs": {"value": 1.0, "width": width, "height": height}},

"5": {"class_type": "ImageCompositeMasked",
      "inputs": {"destination": ["1", 0], "source": ["3", 0],
                 "x": x, "y": y, "resize_source": False, "mask": ["4", 0]}},
```

这等于告诉 ComfyUI：把整个矩形区域都贴上去。

因此即使前一步生成/去背有透明信息，只要这里使用 `SolidMask`，白底矩形仍然会被完整贴上去。

## 修复目标

1. POD 印花生成必须只生成“孤立平面图案”，不能生成 T 恤、衣服、商品图、mockup、海报、场景。
2. 印花图不能要求 `white background`，应改成“plain transparent/alpha intent or isolated design, no background”；如果 txt2img 无法直接透明，也应生成纯色背景方便 RMBG 去背。
3. 去背失败不能静默继续合成原图。
4. 合成时必须使用 RMBG 输出的真实 mask/alpha，不能再用 `SolidMask` 全白矩形。
5. 如果生成阶段生成了整件 T 恤，应判定为无效印花，失败并提示重试，而不是继续贴图。

## Task A：重写 POD 印花 prompt 的系统约束 ✅ 已完成

修改：

```text
src/apps/generation/print_variants.py
```

在 `build_random_print_prompt()` 中，为 POD 印花追加更强的系统约束，替换当前末尾：

```python
'flat graphic design, no text, no letters, no logo, no human, white background'
```

建议改成类似：

```python
POD_PRINT_SYSTEM_PROMPT = """
Create ONLY a standalone flat printable graphic artwork.
The image must contain the print design only.
No t-shirt, no clothing, no apparel mockup, no product photo, no hanger, no model, no scene.
No rectangular poster, no framed image, no background panel.
Do not show the design printed on anything.
Use isolated centered artwork on a plain removable background.
Flat 2D vector/screen-print style, clean edges, print-ready.
"""
```

并把正向 prompt 里容易诱导 T 恤的词替换或清理：

- `t-shirt print design` -> `printable graphic artwork`
- `for a black t-shirt` -> `high contrast artwork suitable for dark fabric`
- `for a white t-shirt` -> `artwork suitable for light fabric`
- `chest print` -> `compact centered print artwork`
- `graphic tee style` -> `streetwear graphic art style`

同时不要再追加 `white background`。

如果确实需要便于去背的背景，改成：

```text
plain solid white removable background, artwork only, no border, no rectangle frame
```

但负面词必须强制：

```text
t-shirt, shirt, clothing, garment, apparel, mockup, product photo, printed on shirt, hanger, collar, sleeve, fabric folds, rectangular background, white rectangle, poster, frame
```

## Task B：同步修正已有 6 个印花 preset 文案 ✅ 已完成

当前 `data/print_prompts/*/*.md` 中有类似：

```text
Create a standalone flat t-shirt print design
for a black t-shirt
for a white t-shirt
chest print
```

请把这些词替换成“平面印花图案/适合深色或浅色面料”，避免正向 prompt 继续出现 `t-shirt`。

例如：

```text
Create a standalone flat printable graphic artwork.
High contrast artwork suitable for dark fabric.
Compact centered printable design.
```

修改后提醒用户在前端点击「同步提示词」或自动触发同步，让 DB 里的 `PrintDesignPreset` 更新。

## Task C：去背失败不能 passthrough 原图 ✅ 已完成

修改：

```text
src/apps/generation/comfyui.py::remove_print_background()
```

当前异常后返回原图会造成白底矩形贴图。请改成：

- 如果 RMBG workflow 报错，抛出异常或返回 `metadata['method']='failed'`，并让 `_run_pod_generation()` 将产品状态设为 failed。
- 不允许在 POD 合成阶段继续使用原始白底图。

建议：

```python
except Exception as e:
    raise RuntimeError(f'RMBG background removal failed: {e}')
```

如果要保留 fallback，也必须是“本地 alpha 处理 fallback”，不能直接原图 passthrough。

## Task D：合成时使用真实 mask，不要使用 SolidMask ✅ 已完成

最推荐：把“去背 + 缩放 + 合成”放到同一个 ComfyUI workflow 里，直接使用 RMBG 输出的 mask。

当前可用 RMBG 节点：

```text
class_type: RMBG
inputs:
- image: ["2", 0]
- model: "RMBG-2.0"
- background: "Alpha"
outputs:
0 IMAGE
1 MASK
2 MASK_IMAGE
```

合成流程建议：

```text
LoadImage(template) -> destination
LoadImage(raw_print) -> RMBG
RMBG output 0 IMAGE -> resize image
RMBG output 1 MASK -> resize mask
ImageCompositeMasked(destination, resized_image, x, y, resize_source=False, mask=resized_mask)
SaveImage
```

用户当前 ComfyUI 有 `AILab_ImageResize`，它支持同时输入 image 和 mask，输出：

```text
0 IMAGE
1 MASK
2 WIDTH
3 HEIGHT
```

因此可以用：

```python
"3": {"class_type": "RMBG",
      "inputs": {"image": ["2", 0], "model": "RMBG-2.0",
                 "background": "Alpha", "process_res": 1024}},

"4": {"class_type": "AILab_ImageResize",
      "inputs": {
          "image": ["3", 0],
          "mask": ["3", 1],
          "custom_width": width,
          "custom_height": height,
          "megapixels": 0.0,
          "scale_by": 1.0,
          "resize_mode": "longest_side",
          "resize_value": 0,
          "upscale_method": "lanczos",
          "device": "cpu",
          "divisible_by": 2,
          "output_mode": "stretch",
          "crop_position": "center",
          "pad_color": "#FFFFFF"
      }},

"5": {"class_type": "ImageCompositeMasked",
      "inputs": {
          "destination": ["1", 0],
          "source": ["4", 0],
          "x": x,
          "y": y,
          "resize_source": False,
          "mask": ["4", 1],
      }},
```

如果不想依赖 `AILab_ImageResize`，可以先用 Python/PIL 处理 alpha mask，但用户之前要求图片操作尽量走 ComfyUI；优先按上面 ComfyUI workflow 做。

关键点：

- 删除/不要使用 `SolidMask`。
- `ImageCompositeMasked.mask` 必须来自 RMBG 输出 mask 或透明 alpha 转换，不是全白矩形。

## Task E：增加无效印花检测 ✅ 已完成 (prompt-level sanitize)

在保存 raw print 后、去背/合成前，可以做一个简单防呆：

如果 generated print image 明显像商品图或 T 恤 mockup，应失败并提示。

可先做轻量规则：

- 如果 prompt 或 negative 中仍含高风险词，记录 warning。
- 如果 raw print 四周大面积接近白/灰背景，且中心主体 bounding box 接近整张矩形，提示“背景去除失败或生成了商品图”。

第一版至少要在 `PrintDesign` 详情或 product error 中保存：

```text
生成结果疑似商品图/带背景，请优化印花提示词后重试
```

## 验证

请用用户截图中的黑色模板验证：

1. 生成结果不能再出现“小 T 恤印在大 T 恤上”。
2. 不能再出现白/灰色矩形背景块。
3. 印花只显示彩色图案本体。
4. ComfyUI 日志不再出现 missing node / missing resize_source。
5. 如果 RMBG 失败，产品应显示 failed/error，而不是生成带白底的错误商品图。

## 重要约束

1. 不要改 AI 直出商品图模式。
2. 不要自动 fallback checkpoint。
3. 不要把产品图提示词和印花提示词混用。
4. POD 印花 prompt 中不要再出现诱导模型生成衣服的正向词。
5. 失败时宁可失败并提示，也不要把错误白底图继续贴到模板上。
---

# 追加产品定义：POD 印花生成本质是热门 logo / 表情包 / 图案，不要包含衣服元素

## 用户最新补充

用户明确说明：

> 印花的本质其实是个当下热门的 logo，表情包，图案。生成印花时其实不需要和衣服相关的元素。

这条是 POD 印花模式的核心产品定义，请后续所有印花提示词、随机变体、生成逻辑都按这个方向理解。

## 新的产品边界

POD 印花生成阶段只负责生成：

```text
独立的流行视觉符号 / logo-like 图案 / 表情包风格图案 / 潮流图形 / 可售卖的装饰图案
```

它不负责生成：

```text
T 恤、衣服、穿搭、商品图、模特、衣架、布料、胸口、印在衣服上的效果
```

衣服模板和贴图位置是后续 POD 合成阶段负责的事情。

## 对提示词系统的要求

修改或检查：

```text
src/apps/generation/print_variants.py
data/print_prompts/**/*.md
PrintDesignPreset 上传/同步后的内容
```

### 正向 prompt 应该强调

可以使用这些方向：

```text
standalone viral sticker design
trending meme-style graphic
logo-like icon artwork
mascot-style symbol
cute expressive emoji-like character
bold streetwear graphic mark
flat vector emblem
sticker-style illustration
internet culture inspired graphic
simple memorable visual symbol
print-ready standalone artwork
transparent background or removable plain background
```

### 正向 prompt 禁止出现

印花生成阶段不要再出现这些正向词：

```text
t-shirt
shirt
clothing
garment
apparel
chest
chest print
printed on shirt
for a black t-shirt
for a white t-shirt
mockup
product photo
hanger
fabric
cotton
sleeve
collar
model
wardrobe
```

如果确实需要区分适合黑色/白色模板，只用：

```text
suitable for dark backgrounds
suitable for light backgrounds
high contrast for dark surface
soft colors for light surface
```

不要写 `for black t-shirt` 或 `for white t-shirt`。

## 建议重构 `build_random_print_prompt()`

请把 POD 印花系统提示词改成类似：

```python
POD_PRINT_SYSTEM_PROMPT = """
Create only one standalone print-ready graphic artwork.
The design should look like a trending logo, meme sticker, mascot icon, emoji-like symbol, or bold decorative graphic.
No clothing, no t-shirt, no apparel mockup, no product photo, no scene.
Do not show the artwork printed on anything.
Do not include a rectangular poster, frame, card, or background panel.
No text, no letters, no readable words, no brand name.
Flat 2D vector/sticker/screen-print style with clean edges.
Centered isolated artwork, transparent background or plain removable background.
"""
```

然后随机池也要从“服装印花”改成“流行视觉图案”：

```python
DEFAULT_VARIATION_POOL = {
    "theme": [
        "viral meme sticker",
        "cute mascot icon",
        "bold logo-like symbol",
        "streetwear emblem",
        "emoji-like expression graphic",
        "retro internet culture badge",
        "kawaii character symbol",
        "abstract trendy icon",
    ],
    "composition": [
        "single centered icon",
        "compact circular sticker",
        "bold silhouette with small accent shapes",
        "mascot head icon",
        "symmetrical emblem",
        "simple memorable symbol",
    ],
    "elements": [
        "smiling blob character, star sparks, rounded shapes",
        "cartoon skull icon, lightning bolts, dots",
        "cute ghost-like mascot, tiny hearts, sparkle marks",
        "bold abstract animal face, geometric accents",
        "flame icon, checker fragments, bubble shapes",
        "mushroom mascot, sun dot, curved leaves",
    ],
    "style": [
        "flat vector sticker style",
        "bold screen-print graphic",
        "clean logo-like icon",
        "Japanese kawaii sticker style",
        "retro pop art emblem",
        "Y2K internet sticker style",
    ],
}
```

注意：上面只是示例，Claude 可以按现有字段结构实现，但不要再围绕 T 恤/胸口/衣服组织随机词。

## 建议更新现有 6 个印花 .md

当前 6 个 `data/print_prompts` 文件需要从“某颜色 T 恤印花”改成“适合某底色的独立图案”。

示例：

旧：

```text
Create a standalone flat t-shirt print design
High contrast compact chest print for a black t-shirt
```

新：

```text
Create a standalone print-ready viral sticker graphic.
High contrast logo-like artwork suitable for dark backgrounds.
```

旧：

```text
The artwork should be suitable for printing on a white cotton t-shirt.
```

新：

```text
The artwork should be suitable for light backgrounds.
```

## 结果判断标准

生成的 raw print 应该像：

```text
一个独立贴纸 / logo / 表情包图案 / 图形符号
```

不应该像：

```text
商品图、T 恤 mockup、海报、白底矩形卡片、印在衣服上的效果图
```

## 重要约束

1. POD 印花生成不再包含任何衣服相关正向语义。
2. 衣服只存在于模板合成阶段。
3. 颜色分类只表达“适合深色/浅色背景”，不要表达“黑色/白色 T 恤”。
4. 不要影响 AI 直出商品图模式，那一套仍然可以描述 T 恤和场景。
---

# 追加任务：修复 ImageCompositeMasked mask 接入 IMAGE 导致类型不匹配

## 用户反馈

POD 贴图生成时报错：

```text
Failed to validate prompt for output 7:
* ImageCompositeMasked 6:
  - Return type mismatch between linked nodes: mask, received_type(IMAGE) mismatch input_type(MASK)
Output will be ignored
```

## 根因

ChatGPT 已检查当前代码：

```text
src/apps/generation/comfyui.py::composite_pod_image()
```

当前 workflow 片段：

```python
"3": {"class_type": "RMBG", ...},  # output 0=IMAGE, output 1=MASK, output 2=IMAGE

"4": {"class_type": "ImageScale",
      "inputs": {"image": ["3", 0], ...}},

"5": {"class_type": "ImageScale",
      "inputs": {"image": ["3", 1], ...}},

"6": {"class_type": "ImageCompositeMasked",
      "inputs": {
          "destination": ["1", 0],
          "source": ["4", 0],
          "x": x,
          "y": y,
          "resize_source": False,
          "mask": ["5", 0],
      }},
```

问题：

1. `RMBG` 输出 1 本来是 `MASK`。
2. 但代码把 `["3", 1]` 接进了 `ImageScale`。
3. `ImageScale` 的输入/输出都是 `IMAGE`，不能处理 `MASK`。
4. 所以 `["5", 0]` 是 `IMAGE`，接到 `ImageCompositeMasked.mask` 就报：

```text
received_type(IMAGE) mismatch input_type(MASK)
```

## 当前 ComfyUI 节点能力

ChatGPT 通过当前 ComfyUI API 确认：

```text
RMBG outputs:
0 IMAGE
1 MASK
2 IMAGE

AILab_ImageResize outputs:
0 IMAGE
1 MASK
2 WIDTH
3 HEIGHT

ImageCompositeMasked mask input:
MASK
```

`AILab_ImageResize` 支持同时输入 `image` 和可选 `mask`，并输出缩放后的 `IMAGE` 和 `MASK`。

## 修复要求

修改：

```text
src/apps/generation/comfyui.py::composite_pod_image()
```

不要用 `ImageScale` 缩放 mask。

推荐改为一个 `AILab_ImageResize` 节点同时缩放 RMBG 的透明图和 mask：

```python
"4": {"class_type": "AILab_ImageResize",
      "inputs": {
          "image": ["3", 0],
          "mask": ["3", 1],
          "custom_width": width,
          "custom_height": height,
          "megapixels": 0.0,
          "scale_by": 1.0,
          "resize_mode": "longest_side",
          "resize_value": 0,
          "upscale_method": "lanczos",
          "device": "cpu",
          "divisible_by": 2,
          "output_mode": "stretch",
          "crop_position": "center",
          "pad_color": "#FFFFFF",
      }},

"5": {"class_type": "ImageCompositeMasked",
      "inputs": {
          "destination": ["1", 0],
          "source": ["4", 0],
          "x": x,
          "y": y,
          "resize_source": False,
          "mask": ["4", 1],
      }},

"6": {"class_type": "SaveImage",
      "inputs": {"filename_prefix": "pod_composite", "images": ["5", 0]}},
```

注意：

- `mask` 必须接 `["4", 1]`，这是 `MASK` 类型。
- 不要接 `["4", 0]`，那是 `IMAGE`。
- 不要再使用 `SolidMask`。
- 不要使用 `ImageScale` 来缩放 mask。

## 备选方案

如果不想依赖 `AILab_ImageResize`，也可以：

1. 用 `RMBG` 输出 0 的透明图。
2. `ImageScale` 缩放透明图。
3. `ImageToMask(channel="alpha")` 从缩放后的透明图提取 alpha mask。
4. 把 `ImageToMask` 输出接入 `ImageCompositeMasked.mask`。

但当前用户 ComfyUI 已存在 `AILab_ImageResize`，优先用推荐方案。

## 验证

请执行：

```powershell
cd C:\Users\VincentLin\PycharmProjects\tk-erp
python src\manage.py test
```

手动生成 POD 贴图，确认 ComfyUI 不再出现：

```text
received_type(IMAGE) mismatch input_type(MASK)
```

并确认：

1. 白/灰背景矩形不再被贴上去。
2. 只贴图案主体。
3. 合成节点输出 `pod_composite`。

## 重要约束

1. 不要改模型配置。
2. 不要自动 fallback checkpoint。
3. 不要影响 AI 直出商品图模式。
4. 本次重点是修复 mask 类型连接错误。

---

# 追加产品规则：印花提示词不再区分黑 T / 白 T，所有印花都可以印

## 用户补充

用户说明：

> 印花提示词就不分黑T白T了，都可以印

之前的 `white/black` 分类来自模板颜色，但 POD 印花本身不是“黑 T 专用”或“白 T 专用”。印花是独立图案，后续可以贴到任意模板上。

## 修复方向

请调整印花提示词管理和生成逻辑：

1. `PrintDesignPreset` 不应强依赖 `shirt_color=white/black`。
2. 印花提示词目录可以统一为：

```text
data/print_prompts/
```

或保留子目录但同步时统一标记为：

```text
shirt_color = "other"
```

3. 前端「印花提示词」管理页不要再强调黑 T / 白 T 分类。
4. POD 创建页选择印花时，所有印花预设都可用于任意模板颜色。
5. 如果要表达色彩兼容性，只用 prompt 文案描述：

```text
suitable for both dark and light backgrounds
clear contrast on dark or light surfaces
```

不要写：

```text
for black t-shirt
for white t-shirt
black t-shirt prompt
white t-shirt prompt
```

## 注意

AI 直出商品图模式的 `PromptPreset` 仍然可以按白 T / 黑 T 分类，因为那一套会直接生成整件商品图。

这个规则只适用于 POD 印花提示词 `PrintDesignPreset`。
---

# 追加任务：启用 LogoRedmond LoRA，并在 POD 印花 prompt 中加入触发词 LogoRedAF

## 用户确认

用户本机 LoRA 文件名是：

```text
LogoRedmondV2-Logo-LogoRedmAF.safetensors
```

ChatGPT 已通过当前 ComfyUI API 查询确认，`LoraLoader` 可用列表包含：

```text
LogoRedmondV2-Logo-LogoRedmAF.safetensors
_diagnose_test.safetensors
```

也就是说 LoRA 文件已经安装成功。

## 重要区分

LoRA 文件名：

```text
LogoRedmondV2-Logo-LogoRedmAF.safetensors
```

Prompt 触发词：

```text
LogoRedAF
```

不要把文件名里的 `LogoRedmAF` 当成触发词。触发词按用户询问和模型常见用法使用：

```text
LogoRedAF
```

## 当前问题

当前 `data/config.json` 仍然是：

```json
"print_lora_name": ""
```

并且 `src/apps/generation/print_variants.py::build_random_print_prompt()` 当前没有把：

```text
LogoRedAF
```

加入 positive prompt。

因此即使 LoRA 文件已经安装，POD 印花生成目前也没有真正使用 LogoRedmond LoRA。

## 修复要求

### Task A：启用 LoRA 配置

修改：

```text
data/config.json
```

设置：

```json
"print_lora_name": "LogoRedmondV2-Logo-LogoRedmAF.safetensors",
"print_lora_strength_model": 0.8,
"print_lora_strength_clip": 0.8,
"print_lora_trigger": "LogoRedAF"
```

如果当前配置读取逻辑没有 `print_lora_trigger`，请补上默认值：

```python
'print_lora_trigger': 'LogoRedAF',
```

### Task B：POD prompt 自动加触发词

修改：

```text
src/apps/generation/comfyui.py
src/apps/generation/print_variants.py
```

推荐方案：

1. `ComfyUIProvider._load_pod_config()` 读取 `print_lora_trigger`。
2. 在 `generate_print_design()` 调用 ComfyUI 前，如果：

```python
lora_name
```

非空，并且：

```python
print_lora_trigger
```

非空，则把触发词加到 positive prompt 开头。

示例：

```python
trigger = pod_config.get('print_lora_trigger', '').strip()
if lora_name and trigger and trigger.lower() not in prompt.lower():
    prompt = f'{trigger}, {prompt}'
```

这样触发词只影响 POD 印花生成，不影响 AI 直出商品图。

### Task C：保留依赖校验

生成前继续校验 `print_lora_name` 是否存在于 ComfyUI `LoraLoader` 列表。

如果不存在，错误提示必须显示：

```text
缺少 ComfyUI LoRA：LogoRedmondV2-Logo-LogoRedmAF.safetensors
请下载到 ComfyUI/models/loras/ 后刷新或重启 ComfyUI
```

但当前用户机器已经存在，不应该报缺失。

## 验证

请手动生成一次 POD 印花，并在日志中打印或调试确认 positive prompt 开头包含：

```text
LogoRedAF
```

ComfyUI workflow 中应出现：

```text
LoraLoader
lora_name = LogoRedmondV2-Logo-LogoRedmAF.safetensors
```

## 重要约束

1. LogoRedmond LoRA 只用于 POD 印花生成。
2. 不要影响 AI 直出商品图模式。
3. LoRA 文件名使用 `LogoRedmondV2-Logo-LogoRedmAF.safetensors`。
4. Prompt 触发词使用 `LogoRedAF`。
5. 不要把 LoRA 当 checkpoint。
---

# 追加修正：LogoRedmond LoRA 触发词应使用 `logo, logoredmaf`

## 用户要求

用户不确定 LogoRedmond 的触发词，让 ChatGPT 查资料确认。

## 查证结果

ChatGPT 查到 MonAI 的 LogoRedmond LoRA 说明页：

```text
LoRA Name: LogoRedmondV2-Logo-LogoRedmAF
Trigger Word: logo, logoredmaf
```

来源：

```text
https://wiki.monai.art/en/LoRAs/LogoRedmond
```

该页面还说明：

```text
The LogoRedmondV2-Logo-LogoRedmAF LoRA is weighted at 1.0 and both triggers - logo and logoredmaf - are included.
```

因此之前写成：

```text
LogoRedAF
```

是不准确的。

## 正确配置

LoRA 文件名：

```text
LogoRedmondV2-Logo-LogoRedmAF.safetensors
```

Prompt 触发词：

```text
logo, logoredmaf
```

建议强度：

```text
1.0
```

如果当前使用 `0.8` 也可以先保守测试，但官方说明页示例提到 weighted at `1.0`。

## 修复要求

修改此前关于 LogoRedmond 的实现/配置：

1. 不要使用：

```text
LogoRedAF
```

2. 改为使用：

```text
logo, logoredmaf
```

3. 如果增加了 `print_lora_trigger` 配置，应设为：

```json
"print_lora_trigger": "logo, logoredmaf"
```

4. 如果已经把 `LogoRedAF` 写入代码、配置或提示词，请清除并替换。

5. `generate_print_design()` 拼接 trigger 时，最终 positive prompt 开头应类似：

```text
logo, logoredmaf, Create only one standalone print-ready graphic artwork...
```

## 当前用户本机 LoRA 文件已确认存在

ComfyUI `LoraLoader` 可用列表包含：

```text
LogoRedmondV2-Logo-LogoRedmAF.safetensors
```

所以不需要提示用户重新下载该 LoRA。

## 重要约束

1. 文件名仍然使用 `LogoRedmondV2-Logo-LogoRedmAF.safetensors`。
2. 触发词使用小写 `logo, logoredmaf`。
3. LogoRedmond LoRA 只用于 POD 印花生成。
4. 不要影响 AI 直出商品图模式。
5. 不要把 LoRA 当 checkpoint。
---

# 追加任务：POD 产品生成完成后没有生成标题和描述

## 用户反馈

用户说明：

> 产品生成了，但是标题没有生成

这是 POD 贴图模式的问题，不是 AI 直出商品图模式。

## 根因

ChatGPT 已检查：

```text
src/apps/dashboard/views.py
```

Direct 模式 `_run_preset_generation()` 在图片生成后会调用：

```python
_generate_text_v2(product_id)
Product.objects.filter(id=product_id).update(status='completed')
```

但 POD 模式 `_run_pod_generation()` 在保存 SKU 后直接：

```python
Product.objects.filter(id=product_id).update(status='completed', seed=base_seed)
print(f'POD Product#{product_id} completed')
```

没有调用 `_generate_text_v2(product_id)`，所以 POD 产品标题和描述为空。

另外 `_generate_text_v2()` 当前只会从：

```python
product.prompt_preset
product.category.print_prompt
else 'stylish print design'
```

取描述。POD 产品没有 `prompt_preset` 和 `category`，但有：

```python
product.print_design
```

所以即使调用 `_generate_text_v2()`，也会 fallback 到泛化的 `stylish print design`，标题质量会很差。

## 修复目标

1. POD 产品生成成功后也要自动生成标题和描述。
2. POD 文案生成应使用 `product.print_design.prompt` 或 `product.print_design.preset.name/content` 作为图案描述来源。
3. 如果文案生成失败，状态应变为 `text_pending`，不要把产品标记为完全 completed。
4. 不影响 AI 直出商品图模式。

## Task A：POD 完成后调用 `_generate_text_v2()`

修改：

```text
src/apps/dashboard/views.py::_run_pod_generation()
```

把结尾从：

```python
Product.objects.filter(id=product_id).update(status='completed', seed=base_seed)
print(f'POD Product#{product_id} completed')
```

改为类似 direct 模式：

```python
try:
    _generate_text_v2(product_id)
    Product.objects.filter(id=product_id).update(status='completed', seed=base_seed)
except Exception as e:
    import traceback
    Product.objects.filter(id=product_id).update(
        status='text_pending',
        seed=base_seed,
        error_message=str(e)[:500],
    )
    print(f'POD text gen failed for {product_id}: {e}\n{traceback.format_exc()}')
    return

print(f'POD Product#{product_id} completed')
```

## Task B：让 `_generate_text_v2()` 支持 POD `print_design`

修改：

```text
src/apps/dashboard/views.py::_generate_text_v2()
```

当前查询：

```python
product = Product.objects.select_related('country', 'category', 'prompt_preset').get(id=product_id)
```

应加入：

```python
'print_design',
'print_design__preset',
```

例如：

```python
product = Product.objects.select_related(
    'country', 'category', 'prompt_preset',
    'print_design', 'print_design__preset',
).get(id=product_id)
```

描述来源优先级建议：

```python
if product.generation_mode == 'pod' and product.print_design:
    desc = product.print_design.prompt[:300]
    if product.print_design.preset:
        desc = f'{product.print_design.preset.name}: {desc}'
elif product.prompt_preset:
    desc = product.prompt_preset.content[:100]
elif product.category and product.category.print_prompt:
    desc = product.category.print_prompt[:100]
else:
    desc = 'stylish print design'
```

注意 POD 的 `print_design.prompt` 可能很长，建议截取 300-500 字，不要只取 100 字，否则可能只截到系统约束。

## Task C：文案内容避免出现“独立图案/无衣服”等技术约束

POD 的 `print_design.prompt` 里包含很多系统约束：

```text
No clothing, no t-shirt, no mockup...
```

这些不适合直接给 DeepSeek 写标题。

建议新增一个轻量清洗函数，比如：

```python
def _summarize_pod_print_for_text(print_design):
    ...
```

优先提取：

- `variation_metadata.theme`
- `variation_metadata.elements`
- `variation_metadata.style`
- `variation_metadata.palette`
- `print_design.preset.name`

组成更干净的描述：

```text
viral meme sticker, cute mascot icon, neon green and hot pink palette, flat vector sticker style
```

如果暂时不做复杂清洗，至少不要把 negative prompt 传入标题生成。

## 验证

请验证：

1. 新建 POD 产品。
2. 图片生成成功后，标题不为空。
3. 描述不为空。
4. 如果 DeepSeek 失败，产品状态为 `text_pending`，错误显示在 `error_message`。
5. AI 直出商品图标题生成不受影响。

## 重要约束

1. 不要把 POD 产品直接 completed 后跳过文案。
2. 不要让标题使用泛化的 `stylish print design`，应尽量基于实际 print_design。
3. 不要影响 direct 模式。
---

# 追加任务：POD 印花更随机、更异形，并支持随机提示词批量生成

## 用户反馈

用户观察到当前生成的印花：

1. 大部分都有椭圆外框包裹。
2. 椭圆徽章本身可以保留，但不要每张都是这种。
3. 希望图案更随机、更异形一点。
4. 希望多一些当下热门图案方向，例如 logo-like、表情包、贴纸、meme、潮流 icon。
5. 生成产品时希望可以选择“随机提示词”，用户只输入生成数量，系统自动随机选择提示词批量生成产品。

## ChatGPT 已新增提示词文件

ChatGPT 已在项目中新增 12 个通用 POD 印花提示词：

```text
data/print_prompts/general/01-viral-mood-blob-sticker.md
data/print_prompts/general/02-glitch-star-runner-symbol.md
data/print_prompts/general/03-cute-ghost-flame-mascot.md
data/print_prompts/general/04-cyber-cat-head-icon.md
data/print_prompts/general/05-ramen-planet-mascot.md
data/print_prompts/general/06-lucky-mushroom-spark.md
data/print_prompts/general/07-chaos-smiley-burst.md
data/print_prompts/general/08-retro-pixel-pocket-monster.md
data/print_prompts/general/09-liquid-chrome-heart-icon.md
data/print_prompts/general/10-wilderkind-moss-eye-symbol.md
data/print_prompts/general/11-hot-sauce-flame-face.md
data/print_prompts/general/12-abstract-duck-bubble-icon.md
```

这些提示词不再按黑 T / 白 T 分类，都是通用印花。

每个文件都包含：

- 热门贴纸 / meme / logo-like / mascot / Y2K / 食物梗 / 游戏感 / 自然奇幻等方向
- `VARIATION POOL`
- 明确的 `no oval badge`, `no circular frame`, `irregular die-cut silhouette` 等约束

## Task A：同步逻辑改成递归扫描通用印花目录

当前 `src/apps/categories/prompt_sync.py::sync_print_presets_from_disk()` 仍然只扫描：

```python
for color_dir_name in ('white', 'black'):
```

这不适合 POD 印花了。

请改成递归扫描：

```text
data/print_prompts/**/*.md
```

要求：

1. 支持：

```text
data/print_prompts/general/*.md
data/print_prompts/*.md
data/print_prompts/任意子目录/*.md
```

2. 所有 `PrintDesignPreset.shirt_color` 默认设为：

```python
'other'
```

或改名为更合理的通用字段，但最小改动先用 `other`。

3. slug 用相对 `data/print_prompts` 的路径生成，避免同名冲突。

4. 不要再根据目录名 `white/black` 判断 POD 印花适用颜色。

5. 原 AI 直出商品图 `PromptPreset` 的同步逻辑不要改，仍可按 white/black。

## Task B：减少椭圆/徽章外框的默认倾向

修改：

```text
src/apps/generation/print_variants.py
```

当前随机池里如果仍有：

```text
compact circular sticker
symmetrical emblem
retro internet culture badge
```

这些可以保留少量，但不能占主导。

建议：

1. 增加更多异形构图：

```text
irregular die-cut sticker silhouette
asymmetric floating accent cluster
jagged freeform burst
single mascot with no frame
drippy liquid contour
organic freeform shape
diagonal flying shape with no frame
fragmented glitch silhouette
```

2. 在系统 prompt 加：

```text
Use varied silhouettes. Avoid making every design an oval badge or circular emblem.
Frames and borders are optional, not default.
Prefer irregular die-cut sticker shapes, freeform silhouettes, mascot icons, and abstract symbols.
```

3. negative prompt 中保留：

```text
perfect oval frame, repeated oval badge, circular seal, rectangular card, poster frame
```

注意：不要完全禁止 oval，因为用户说椭圆也可以，只是不要全是。

## Task C：新增“随机提示词”批量生成模式

修改：

```text
src/apps/dashboard/templates/dashboard/product_create.html
src/apps/dashboard/views.py::product_create()
```

POD 模式下增加一个选项：

```text
提示词选择方式：
- 手动选择提示词
- 随机选择提示词
```

建议表单字段：

```html
<input type="radio" name="print_preset_mode" value="manual" checked>
<input type="radio" name="print_preset_mode" value="random">
```

当选择 `random`：

- 不要求用户勾选任何印花提示词。
- 用户只需要选择国家、POD 模板、数量。
- `count` 表示最终生成产品数量，不再是“每个提示词 × 数量”。
- 每个产品创建时从所有 active `PrintDesignPreset` 中随机抽一个。

后端逻辑示例：

```python
if mode == 'pod':
    preset_mode = request.POST.get('print_preset_mode', 'manual')
    active_print_presets = list(PrintDesignPreset.objects.filter(is_active=True))

    if preset_mode == 'random':
        if not active_print_presets:
            messages.error(request, '没有可用印花提示词，请先同步或上传')
            return redirect(f'{request.path}?mode=pod')

        total = 0
        rng = random.Random()
        for i in range(count):
            pp = rng.choice(active_print_presets)
            product = Product.objects.create(...)
            threading.Thread(target=_run_pod_generation, args=(product.id, pp.id), daemon=True).start()
            total += 1

        messages.success(request, f'随机创建 {total} 个 POD 产品，正在生成...')
        return redirect('product_list')
```

手动模式保留当前逻辑：

```text
选中的提示词 × 数量 = 总产品数
```

但随机模式：

```text
数量 = 总产品数
```

## Task D：前端交互

POD 模式页面需要：

1. 选择“随机提示词”时，隐藏或弱化提示词勾选列表。
2. 校验逻辑 `validateForm()`：
   - manual 模式：必须至少勾选一个提示词。
   - random 模式：不需要勾选提示词。
3. 数量说明文案动态变化：
   - manual：`每个选中提示词 × 数量 = 总产品数`
   - random：`随机抽取提示词，数量 = 总产品数`

## Task E：避免真实 IP / 真实品牌侵权

新增热门图案方向时，不要直接生成真实品牌 logo、真实 meme IP、影视动漫角色。

可以使用：

```text
logo-like
meme-style
mascot-style
internet culture inspired
retro game inspired
Y2K sticker style
```

不要使用：

```text
Nike
Supreme
Pokemon
Hello Kitty
Pepe
Disney
Sanrio
Marvel
真实品牌或真实角色名
```

## 验证

1. 点击「同步提示词」后，`data/print_prompts/general/*.md` 能进入前端印花提示词列表。
2. POD 模式选择“随机提示词”，只输入数量 5，应只创建 5 个产品。
3. 5 个产品的 `print_design.preset` 应尽量随机分布。
4. 生成图案不应全是椭圆徽章。
5. 手动选择提示词模式仍保持原逻辑。
6. AI 直出商品图模式不受影响。
---

# 新模块任务：图片素材库，直接用采集图片生成产品

## 用户需求

用户现在有一批已经采集好的 T 恤产品图片，希望新增一个模块管理这些图片，并能直接通过这些图片生成产品。

核心要求：

1. 新增「图片素材库」模块，用于上传、管理采集图片。
2. 图片已经是成品图，不需要再做 ComfyUI 生成、POD 贴图、去背、裁剪、二次处理。
3. 通过图片生成产品时：
   - 直接把原图片作为产品/SKU 图片。
   - 只需要生成对应的产品标题和描述。
   - SKU 名称为 T 恤颜色。
4. 当前颜色只有：
   - 黑色
   - 白色
5. 图片通常已经按文件夹分类，颜色可以：
   - 根据上传的文件夹名称自动识别；
   - 或上传时让用户选择黑/白。
6. 该模块必须独立，不影响现有：
   - AI 直出商品图模式
   - POD 贴图模式
   - 提示词预设管理
   - 模板管理

## 产品形态

新增一个侧边栏入口：

```text
图片素材库
```

模块页面建议包含：

1. 批量上传图片
2. 图片列表/缩略图管理
3. 按颜色筛选：全部 / 黑色 / 白色
4. 批量选择图片
5. 批量生成产品
6. 删除/停用素材

## 颜色识别规则

当前只支持黑/白。

### 上传时手动选择

上传表单增加：

```text
图片颜色：
- 黑色 T 恤
- 白色 T 恤
```

用户选择后，所有本次上传图片都标记为该颜色。

### 文件夹名识别

如果实现文件夹上传，或者上传文件名包含相对路径，可根据路径/文件夹名识别：

黑色关键词：

```text
black
黑
黑色
black_tshirts
black-tshirts
```

白色关键词：

```text
white
白
白色
white_tshirts
white-tshirts
```

如果无法识别，则使用上传表单里选择的默认颜色。

## 数据模型建议

新增模型，建议放在 `apps.products.models` 或新增 app 均可，优先少改结构。

```python
class ImageAsset(models.Model):
    COLOR_CHOICES = [
        ('black', '黑色'),
        ('white', '白色'),
    ]

    image = models.ImageField(upload_to='assets/source/%Y/%m/')
    color = models.CharField(max_length=16, choices=COLOR_CHOICES)
    original_filename = models.CharField(max_length=512, blank=True, default='')
    source_folder = models.CharField(max_length=512, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_product = models.ForeignKey(
        'products.Product',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='source_assets',
    )
    created_at = models.DateTimeField(auto_now_add=True)
```

也可以用 `Product.generation_mode='source_image'` 标识这类产品。

请给 `Product.generation_mode` 增加：

```python
('source_image', '图片素材')
```

## SKU 名称字段

当前 `ProductSKU` 只有：

```python
template
mockup_image
```

图片素材生成的 SKU 没有模板，但需要显示 SKU 名称为 T 恤颜色。

请给 `ProductSKU` 增加字段：

```python
sku_name = models.CharField(max_length=128, blank=True, default='')
```

显示逻辑：

1. 如果 `sku.sku_name` 有值，优先显示 `sku.sku_name`。
2. 否则如果有 `template`，显示模板颜色。
3. 否则显示 `SKU#id`。

图片素材生成产品时：

```python
sku_name = 'Black' if asset.color == 'black' else 'White'
```

或中文也可以，但建议导出/跨境场景用英文：

```text
Black
White
```

## 生成产品逻辑

新增页面/接口：

```text
/image-assets/
/image-assets/upload/
/image-assets/create-products/
```

用户选择若干素材后点击「生成产品」。

每张图片生成一个 Product：

```python
product = Product.objects.create(
    country=country,
    generation_mode='source_image',
    size_info='XS,S,M,L,XL,XXL,3XL,4XL',
    status='processing',
)
```

然后创建一个 SKU：

```python
sku = ProductSKU.objects.create(
    product=product,
    sku_name='Black' or 'White',
)
sku.mockup_image.save(...原图文件...)
```

注意：

- 不调用 ComfyUI。
- 不调用 POD 合成。
- 不调用图片分析。
- 不修改原图。

## 标题/描述生成

图片素材生成产品只需要生成标题和描述。

建议复用现有：

```text
_generate_text_v2(product_id)
DeepSeekProvider
build_text_prompt
```

但 `_generate_text_v2()` 当前主要依赖 prompt/category/print_design。

请扩展它支持：

```python
product.generation_mode == 'source_image'
```

描述来源可以先用颜色 + 泛化描述：

```text
black t-shirt with graphic print
white t-shirt with graphic print
```

如果 `ImageAsset.original_filename` 有可读关键词，可以追加清洗后的文件名关键词。

第一版不要做 AI 看图分析，避免复杂度上升。

例如：

```python
if product.generation_mode == 'source_image':
    asset = product.source_assets.first()
    color = asset.color if asset else 't-shirt'
    desc = f'{color} t-shirt with trendy graphic print'
```

标题生成成功后：

```python
status='completed'
```

如果文案失败：

```python
status='text_pending'
error_message=...
```

## 前端页面建议

### 图片素材库列表

每个素材卡片显示：

- 缩略图
- 颜色 badge：Black / White
- 原始文件名
- 是否已生成产品
- 选择框
- 删除/停用按钮

顶部操作：

- 上传图片
- 筛选颜色
- 批量生成产品

### 上传页面

字段：

```text
国家：可选，也可以生成产品时再选
图片颜色：黑色 / 白色
选择图片：multiple
```

如果浏览器支持文件夹上传，可以增加：

```html
<input type="file" name="images" multiple webkitdirectory>
```

但第一版普通多图上传即可，颜色通过表单选择。

### 批量生成产品

生成时必须选择国家。

每个选中的素材生成一个产品。

如果素材已生成过产品，建议：

- 默认跳过；
- 或弹窗确认是否重复生成。

第一版建议跳过已生成的素材，避免重复产品。

## 导出兼容

请检查导出逻辑：

```text
src/apps/export_app/services.py
```

如果导出里依赖 `sku.template.get_color_display()`，需要改为优先：

```python
sku.sku_name
```

否则图片素材产品导出 SKU 颜色会为空。

## 侧边栏入口

修改：

```text
src/apps/dashboard/templates/dashboard/base.html
```

新增导航：

```text
图片素材库
```

图标可用 Bootstrap icon：

```text
bi-images
```

## 验证

请验证：

1. 上传 3 张黑色 T 恤图片，颜色选择黑色。
2. 图片素材库显示 3 张素材，颜色为 Black。
3. 选择 3 张素材，选择国家，点击生成产品。
4. 生成 3 个产品，每个产品 1 个 SKU。
5. SKU 图片与原图一致，没有经过 ComfyUI 或任何修改。
6. SKU 名称显示为 Black。
7. 标题和描述自动生成。
8. 产品状态最终为 completed；如果文案失败则为 text_pending。
9. 现有 AI 直出和 POD 模式不受影响。

## 重要约束

1. 这个模块不做图片处理。
2. 不调用 ComfyUI。
3. 不做 POD 贴图。
4. 不生成新图片。
5. 一张素材图生成一个产品，一个产品一个 SKU。
6. 当前颜色只支持黑/白，后续再扩展。
7. SKU 名称为 T 恤颜色。
---

# 追加修正：图片素材库首版必须支持文件夹上传

## 用户补充

用户明确要求：

> 我现在就要支持文件夹上传，可以先让我选颜色再让我选文件夹

因此图片素材库上传功能第一版就必须支持选择文件夹，不是后续增强。

## 上传流程要求

上传页面流程：

1. 用户先选择颜色：

```text
Black / White
```

2. 用户再选择本地文件夹。
3. 系统批量读取该文件夹内图片并上传。
4. 本次上传的所有图片都使用用户选择的颜色。

## 前端实现

在图片素材上传页面使用：

```html
<input
  type="file"
  name="images"
  multiple
  webkitdirectory
  directory
  accept="image/*"
>
```

注意：

- `webkitdirectory` 是 Chrome/Edge 支持文件夹上传的关键。
- 用户当前在 Windows + Chrome 环境，可以使用。
- 表单必须是：

```html
enctype="multipart/form-data"
```

前端文案：

```text
1. 选择 T 恤颜色
2. 选择图片文件夹
```

## 后端实现

后端通过：

```python
request.FILES.getlist('images')
```

获取文件。

文件夹相对路径通常在：

```python
uploaded_file.name
```

里可能包含：

```text
folder/subfolder/image.jpg
```

请保存：

```python
original_filename = Path(uploaded_file.name).name
source_folder = str(Path(uploaded_file.name).parent)
```

如果浏览器只传文件名，也允许 `source_folder=''`。

## 图片过滤

只导入图片类型：

```text
.jpg
.jpeg
.png
.webp
.bmp
```

忽略：

```text
.txt
.json
.psd
.ai
.zip
隐藏文件
```

如果上传文件夹里有非图片文件，不要报错中断，跳过即可。

## 去重建议

首版建议按以下简单规则避免重复：

```text
同 original_filename + source_folder + color 已存在，则跳过
```

如果要更稳，可以后续加文件 hash，但第一版不强制。

上传完成后提示：

```text
已导入 N 张，跳过 M 个非图片/重复文件
```

## 重要约束

1. 文件夹上传是首版必须支持。
2. 颜色由用户先选择，不需要自动识别。
3. 文件夹内所有图片使用同一个颜色。
4. 不要对图片做任何处理。
5. 不调用 ComfyUI。
---

# 追加任务：图片素材上传页颜色选择选中态不明显

## 用户反馈

在「上传图片素材」页面选择颜色时，用户选择白色后，白色/黑色两个按钮看起来都像黑色背景，无法判断当前选中了哪个。

用户截图表现：

```text
白色 T 恤 / 黑色 T 恤 两个选项都在深色按钮区域里
选择白色时视觉差异不明显
```

## 修复目标

颜色选择必须一眼能看出当前选中的是：

```text
白色 T 恤
```

还是：

```text
黑色 T 恤
```

## 推荐 UI

不要让两个选项默认都像黑色按钮。

建议实现为两个大号 radio card / segmented button：

### 白色 T 恤选项

未选中：

```text
白底、深色文字、浅灰边框
```

选中：

```text
白底、蓝色/绿色高亮边框、明显 check 图标、轻微阴影
```

### 黑色 T 恤选项

未选中：

```text
深色底、白色文字、灰色边框
```

选中：

```text
黑底、绿色/蓝色高亮边框、明显 check 图标、轻微阴影
```

## 实现建议

修改图片素材上传模板，可能是：

```text
src/apps/dashboard/templates/dashboard/image_asset_upload.html
```

或 Claude 新增的对应模板。

使用 radio input + label card：

```html
<input class="btn-check" type="radio" name="color" id="colorWhite" value="white" required>
<label class="color-option color-white" for="colorWhite">
  <span class="swatch"></span>
  <span>白色 T 恤</span>
  <i class="bi bi-check-circle-fill selected-icon"></i>
</label>

<input class="btn-check" type="radio" name="color" id="colorBlack" value="black" required>
<label class="color-option color-black" for="colorBlack">
  <span class="swatch"></span>
  <span>黑色 T 恤</span>
  <i class="bi bi-check-circle-fill selected-icon"></i>
</label>
```

CSS 示例：

```css
.color-option {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 140px;
  padding: 12px 14px;
  border: 2px solid #d1d5db;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  position: relative;
}
.color-white {
  background: #fff;
  color: #111827;
}
.color-black {
  background: #111827;
  color: #fff;
}
.selected-icon {
  display: none;
  margin-left: auto;
}
.btn-check:checked + .color-option {
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37,99,235,.18);
}
.btn-check:checked + .color-option .selected-icon {
  display: inline-block;
}
.swatch {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  border: 1px solid #9ca3af;
}
.color-white .swatch { background: #fff; }
.color-black .swatch { background: #111827; border-color: #6b7280; }
```

## 验证

1. 打开上传图片素材页。
2. 选择白色，白色选项有明显高亮和 check，黑色不高亮。
3. 选择黑色，黑色选项有明显高亮和 check，白色不高亮。
4. 不要只靠颜色表达状态，必须有 check 图标或文字状态，避免看不清。

## 重要约束

1. 只修图片素材上传页颜色选择 UI。
2. 不影响图片上传逻辑。
3. 不影响其他模块。
---

# 追加任务：图片素材生成产品时国家选择不应手输，并修复点击后不生成产品

## 用户反馈

用户在「图片素材库」中选择 3 张图片后点击生成产品：

1. 页面弹窗要求输入国家代码。
2. 实际应从当前已有国家中选择，而不是手动输入代码。
3. 用户点击确定后，产品库中没有生成产品。

## 根因

ChatGPT 已检查：

```text
src/apps/dashboard/templates/dashboard/image_asset_list.html
src/apps/dashboard/views.py::image_asset_create_products()
```

当前前端 JS：

```javascript
const country = prompt('请输入国家代码（如 ID 或 TH）:', 'ID');
```

问题一：用户体验不对。国家应使用已有 `Country.objects.all()` 渲染出来的下拉/单选，不应手输。

问题二：当前页面不是一个真实 POST form，JS 动态创建表单时取：

```javascript
document.querySelector('[name=csrfmiddlewaretoken]').value
```

但 `image_asset_list.html` 页面本身没有 `{% csrf_token %}`，所以这个 selector 很可能为空，JS 报错后没有提交表单，导致后端没有创建产品。

后端 `image_asset_list()` 已经传了：

```python
'countries': Country.objects.all()
```

但模板没有使用它。

## 修复目标

1. 图片素材库页面显示国家选择控件，来自当前数据库已有国家。
2. 用户批量生成产品时，从下拉/单选选择国家。
3. 不再使用 `prompt()` 输入国家代码。
4. 修复 CSRF，确保 POST 能正常提交。
5. 点击生成后产品能在产品库中出现。

## 推荐实现

### Task A：把生成产品操作改成真实表单

修改：

```text
src/apps/dashboard/templates/dashboard/image_asset_list.html
```

用一个真实 form 包住批量操作，或新增顶部批量生成 form。

示例：

```html
<form method="post" action="{% url 'image_asset_create_products' %}" id="createProductsForm">
    {% csrf_token %}

    <select name="country" id="assetCountry" class="form-select form-select-sm" required>
        <option value="">选择国家</option>
        {% for c in countries %}
        <option value="{{ c.code }}">{{ c.name }} ({{ c.code }})</option>
        {% endfor %}
    </select>

    <button type="button" class="btn btn-success rounded-pill" onclick="createProducts()">
        <i class="bi bi-stars"></i> 生成产品
    </button>
</form>
```

因为素材 checkbox 分散在卡片里，可以在 JS 中把选中的 ids 添加为 hidden input 到这个 form。

### Task B：删除 prompt 输入国家代码

删除：

```javascript
const country = prompt(...)
```

改成：

```javascript
const country = document.getElementById('assetCountry').value;
if (!country) {
    alert('请先选择国家');
    return;
}
```

### Task C：修复 CSRF

如果继续动态创建 form，也必须保证页面有 CSRF token：

```html
{% csrf_token %}
```

但推荐直接使用真实 form，避免动态取不到 token。

如果使用真实 form：

```javascript
const form = document.getElementById('createProductsForm');
form.querySelectorAll('input[name="ids"]').forEach(el => el.remove());
ids.forEach(id => {
    const input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'ids';
    input.value = id;
    form.appendChild(input);
});
form.submit();
```

### Task D：后端增加日志/结果提示

`image_asset_create_products()` 当前逻辑基本可用，但请增加调试友好的提示：

1. 如果国家无效，提示具体传入值。
2. 创建成功后跳转到产品库更符合用户预期，或消息里提供入口。

建议创建成功后：

```python
messages.success(request, f'已创建 {created} 个产品，跳过 {skipped} 个已生成素材')
return redirect('product_list')
```

如果仍跳回素材库，也要保证消息可见。

### Task E：确认产品生成后文案线程不会阻塞产品创建

当前后端创建 product/SKU 后再启动：

```python
threading.Thread(target=_generate_text_v2, args=(product.id,), daemon=True).start()
```

即使标题生成慢，产品也应该先出现在产品库，状态为 `processing` 或后续变为 `completed/text_pending`。

请确认产品创建和 SKU 图片保存发生在文案线程之前，且不会因为 `_generate_text_v2` 异常导致产品未创建。

## 验证

1. 图片素材库选择 3 张素材。
2. 页面上选择国家下拉，例如印尼/泰国。
3. 点击生成产品。
4. 不出现手输国家代码弹窗。
5. 后端成功创建 3 个 `Product(generation_mode='source_image')`。
6. 产品库能看到 3 个产品。
7. 每个产品有 1 个 SKU，SKU 图片为原素材图。
8. SKU 名称为 `Black` 或 `White`。
9. 标题生成中/完成不影响产品先出现在产品库。

## 重要约束

1. 国家必须从已有 `Country` 列表选择。
2. 不要再让用户手动输入国家代码。
3. 不要调用 ComfyUI。
4. 不要影响 AI 直出和 POD 模式。
---

# 追加任务：侧边栏菜单重排，并从菜单隐藏分类管理

## 用户反馈

用户认为现在「分类管理」这一块基本用不到了，希望左侧菜单重新排序。

用户指定新的菜单顺序：

### 主菜单

```text
工作台
店铺管理
T恤模板
提示词预设
图片素材库
创建产品
产品库
```

### 系统

```text
用户管理
系统设置
退出登录
```

## 当前问题

ChatGPT 已检查：

```text
src/apps/dashboard/templates/dashboard/base.html
```

当前侧栏顺序大致是：

```text
工作台
店铺管理
用户管理
提示词预设
分类管理
T恤模板
创建产品
产品库
图片素材库
系统设置
退出登录
```

问题：

1. `用户管理` 现在在主菜单中，应该移动到系统分组。
2. `分类管理` 仍显示在主菜单，但当前用户不再需要。
3. `图片素材库` 应排在 `提示词预设` 后、`创建产品` 前。
4. `T恤模板` 应排在 `店铺管理` 后。

## 修复要求

只修改左侧导航展示顺序，不要删除分类管理后端代码和 URL。

也就是说：

- 从侧边栏隐藏「分类管理」
- 保留 `category_list` 等 URL 和 view，避免老数据/旧链接需要时还能访问
- 不要删除 `PrintCategory` 模型
- 不要删除分类相关路由

## 目标侧边栏结构

修改：

```text
src/apps/dashboard/templates/dashboard/base.html
```

侧边栏应按下面顺序渲染。

### 主菜单

```django
<div class="nav-section">主菜单</div>

工作台        -> dashboard          icon: bi-speedometer2
店铺管理      -> country_list       icon: bi-building
T恤模板       -> template_list      icon: bi-grid
提示词预设    -> preset_list        icon: bi-file-text
图片素材库    -> image_asset_list   icon: bi-images
创建产品      -> product_create     icon: bi-stars
产品库        -> product_list       icon: bi-box-seam
```

### 系统

```django
<div class="nav-section">系统</div>

用户管理      -> user_list          icon: bi-people
系统设置      -> settings_page      icon: bi-gear
退出登录      -> /admin/logout/     icon: bi-box-arrow-right
```

## Active 状态

Active 判断保留或调整为：

```django
dashboard: request.resolver_match.url_name == 'dashboard'
country_list: 'country' in request.resolver_match.url_name
template_list: 'template' in request.resolver_match.url_name
preset_list: 'preset' in request.resolver_match.url_name
image_asset_list: 'image_asset' in request.resolver_match.url_name
product_create: request.resolver_match.url_name == 'product_create'
product_list: request.resolver_match.url_name == 'product_list'
user_list: 'user' in request.resolver_match.url_name
settings_page: 'settings' in request.resolver_match.url_name
```

## 中文乱码问题

当前 `base.html` 有明显乱码，例如：

```text
涓昏彍鍗?
宸ヤ綔鍙?
```

请用 UTF-8 正确保存模板，把侧边栏中文恢复为正常中文：

```text
主菜单
工作台
店铺管理
T恤模板
提示词预设
图片素材库
创建产品
产品库
系统
用户管理
系统设置
退出登录
```

## 验证

1. 刷新任意后台页面。
2. 左侧菜单顺序与用户指定完全一致。
3. 「分类管理」不再出现在左侧菜单。
4. 用户管理出现在「系统」分组下。
5. 各菜单点击正常。
6. Active 高亮正常。
7. 分类相关 URL 不删除，只是不显示入口。

## 重要约束

1. 不删除分类管理代码。
2. 不删除分类路由。
3. 只调整侧边栏导航展示。
4. 不影响现有功能。
---

# 追加任务：图片素材库上传时按图片内容去重

## 用户补充

用户要求：

> 在我上传图片到图片素材库的时候记得去重

## 当前状态

ChatGPT 已检查当前实现：

```text
src/apps/products/models.py::ImageAsset
src/apps/dashboard/views.py::image_asset_upload()
```

当前上传逻辑已有简单去重：

```python
ImageAsset.objects.filter(
    original_filename=orig_name,
    source_folder=src_folder,
    color=color
).exists()
```

问题：

1. 同一张图片改文件名后会重复导入。
2. 同一张图片复制到不同文件夹后会重复导入。
3. 同一批上传中如果有重复图片，也可能重复。

## 修复目标

图片素材库上传时必须按图片内容去重。

推荐使用：

```text
SHA256(file bytes)
```

作为 `file_hash`。

## Task A：给 ImageAsset 增加 file_hash 字段

修改：

```text
src/apps/products/models.py
```

在 `ImageAsset` 增加：

```python
file_hash = models.CharField(max_length=64, blank=True, default='', db_index=True)
```

建议增加约束：

- 如果只想全局去重：`file_hash` 全局唯一。
- 如果允许黑/白两种颜色各保留一份同图：用 `file_hash + color` 唯一。

用户当前黑/白素材是两套商品图，建议第一版使用：

```python
UniqueConstraint(fields=['file_hash', 'color'], name='uniq_image_asset_hash_color')
```

这样：

- 同一张黑色图重复上传会跳过。
- 同一张图如果用户分别作为黑/白上传，仍可保留两条，避免误伤。

如果你认为同图无论颜色都应跳过，也可以全局唯一，但请优先采用 `hash + color`。

生成 migration。

## Task B：上传时计算 SHA256

修改：

```text
src/apps/dashboard/views.py::image_asset_upload()
```

上传每个文件时：

```python
import hashlib

data = f.read()
file_hash = hashlib.sha256(data).hexdigest()
f.seek(0)
```

注意：

- 计算 hash 后必须 `f.seek(0)`，否则保存 ImageField 时文件内容可能为空。
- 如果用 `ContentFile(data)` 保存，也可以不 seek。

## Task C：同批次和历史库都去重

在一次上传处理中维护：

```python
seen_hashes = set()
```

逻辑：

```python
hash_key = (file_hash, color)
if hash_key in seen_hashes:
    skipped_duplicate += 1
    continue
seen_hashes.add(hash_key)

if ImageAsset.objects.filter(file_hash=file_hash, color=color).exists():
    skipped_duplicate += 1
    continue
```

保留原来的文件名/文件夹去重作为兜底也可以，但内容 hash 应优先。

## Task D：老数据补 hash

如果数据库里已有 ImageAsset，migration 后老记录 `file_hash=''`。

请新增一个管理命令或在 migration 中补齐 hash。

优先简单管理命令：

```text
python src/manage.py backfill_image_asset_hashes
```

命令逻辑：

1. 遍历 `ImageAsset.objects.filter(file_hash='')`
2. 读取 `asset.image.path`
3. 计算 SHA256
4. 保存
5. 如果遇到重复 hash+color，可跳过或报告，不要自动删除用户数据

如果不想新增管理命令，也至少在上传逻辑中不受老数据影响，并在测试说明中提示老素材可后续补 hash。

## Task E：上传结果提示更清楚

上传完成后提示：

```text
已导入 N 张，跳过 M 个重复图片，跳过 K 个非图片文件
```

不要只写：

```text
跳过 M 个非图片/重复文件
```

用户需要知道是重复还是非图片。

## 验证

1. 上传一个文件夹，包含同一张图片的两个副本，文件名不同。
2. 只导入 1 张，重复副本跳过。
3. 再次上传同一文件夹，全部识别为重复并跳过。
4. 上传非图片文件，不报错，计入非图片跳过。
5. 上传成功的图片仍可生成产品。
6. 不影响 AI 直出和 POD 模式。

## 重要约束

1. 去重不能依赖文件名。
2. 必须按文件内容 hash 去重。
3. 计算 hash 后不能导致保存文件为空。
4. 不要自动删除已有素材。
---

# 追加任务：图片素材生成的产品一直停留在“生成中”

## 用户反馈

用户通过图片素材库选择 3 张图片生成产品后，产品库中产品一直显示：

```text
生成中
```

标题仍为：

```text
待生成
```

用户截图中有 3 个 `source_image` 产品，SKU 图片已经存在，但状态一直是 processing。

## 根因

ChatGPT 已检查数据库和代码：

当前数据库最新产品：

```python
[(312, 'source_image', 'processing', '', ''),
 (311, 'source_image', 'processing', '', ''),
 (310, 'source_image', 'processing', '', '')]
```

当前代码：

```text
src/apps/dashboard/views.py::image_asset_create_products()
```

创建 source_image 产品后只启动：

```python
threading.Thread(target=_generate_text_v2, args=(product.id,), daemon=True).start()
```

但 `_generate_text_v2(product_id)` 只做：

```python
product.title = result.title
product.description = result.description
product.save()
```

它不会把状态改为：

```text
completed
```

direct / POD 模式之所以能完成，是因为外层调用后有：

```python
_generate_text_v2(product_id)
Product.objects.filter(id=product_id).update(status='completed')
```

source_image 没有这个外层包装，所以即使标题生成成功，也会一直停留在 `processing`；如果标题生成失败，当前线程也没有捕获异常并写回 `text_pending/error_message`。

## 修复目标

1. source_image 产品创建后，标题生成成功必须把状态改为 `completed`。
2. 标题生成失败必须把状态改为 `text_pending`，并保存 `error_message`。
3. 不要让后台线程异常静默失败。
4. 已经卡住的 source_image 产品要能补救。

## Task A：新增 source_image 文案线程包装函数

在：

```text
src/apps/dashboard/views.py
```

新增函数：

```python
def _run_source_image_text_generation(product_id):
    try:
        _generate_text_v2(product_id)
        Product.objects.filter(id=product_id).update(status='completed')
    except Exception as e:
        import traceback
        Product.objects.filter(id=product_id).update(
            status='text_pending',
            error_message=str(e)[:500],
        )
        print(f'Source image text gen failed for {product_id}: {e}\n{traceback.format_exc()}')
```

### 注意

不要让 `_generate_text_v2()` 自己无条件改状态，因为 direct / POD 外层已经负责状态，避免重复改动造成副作用。

## Task B：图片素材生成产品时调用包装函数

修改：

```text
src/apps/dashboard/views.py::image_asset_create_products()
```

把：

```python
threading.Thread(target=_generate_text_v2, args=(product.id,), daemon=True).start()
```

改成：

```python
threading.Thread(target=_run_source_image_text_generation, args=(product.id,), daemon=True).start()
```

这样 source_image 的标题/描述生成成功后会自动 completed。

## Task C：补救已卡住产品

当前已有卡住产品：

```text
Product #310
Product #311
Product #312
```

请提供一个管理命令或临时后台动作处理：

```text
source_image + status=processing + title=''
```

建议新增管理命令：

```text
python src/manage.py repair_source_image_products
```

逻辑：

1. 查找：

```python
Product.objects.filter(generation_mode='source_image', status='processing')
```

2. 对每个产品调用 `_run_source_image_text_generation(product.id)`。

如果不想新增命令，也可以在 Claude 修完代码后临时执行 shell 修复。

## Task D：防止标题接口失败导致长期 processing

如果 DeepSeek API 不可用、key 错误、超时或返回异常：

```text
status = text_pending
error_message = 错误摘要
```

产品应仍然出现在产品库，SKU 图片可见，用户可以后续补标题或重试文案。

## 验证

1. 从图片素材库选择 3 张图片生成产品。
2. 产品库立即可见 3 个产品，初始 processing。
3. 文案生成成功后变为 completed，标题不再是待生成。
4. 如果 DeepSeek 失败，变为 text_pending，并显示 error_message。
5. 已有 #310/#311/#312 能被补救，不再长期 processing。
6. AI 直出和 POD 模式不受影响。

## 重要约束

1. 不调用 ComfyUI。
2. 不修改图片。
3. 不影响 direct / POD 状态流。
4. source_image 必须有自己的文案线程状态包装。
---

# 追加任务：source_image 标题生成失败，报 No module named 'ai'

## 用户反馈

图片素材生成的产品状态从 `processing` 变成了：

```text
待补全文本 / text_pending
```

但标题仍然没有生成。

## 根因

ChatGPT 已查询数据库，最新 source_image 产品错误为：

```text
No module named 'ai'
```

示例：

```text
Product #313 status=text_pending title='' error="No module named 'ai'"
Product #314 status=text_pending title='' error="No module named 'ai'"
Product #315 status=text_pending title='' error="No module named 'ai'"
```

当前：

```text
src/apps/dashboard/views.py::_generate_text_v2()
```

内部会导入：

```python
from ai.prompts.loader import build_text_prompt
```

direct / POD 后台线程在开始时都有：

```python
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
```

但新加的：

```text
_run_source_image_text_generation()
```

没有做这一步，所以后台线程里找不到项目根目录下的 `ai` 包，导致 `No module named 'ai'`。

## 修复要求

修改：

```text
src/apps/dashboard/views.py::_run_source_image_text_generation()
```

在函数开头加入与 direct/POD 一致的路径初始化：

```python
def _run_source_image_text_generation(product_id):
    """source_image 产品文案生成 + 状态更新"""
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    try:
        _generate_text_v2(product_id)
        Product.objects.filter(id=product_id).update(status='completed', error_message='')
    except Exception as e:
        import traceback
        Product.objects.filter(id=product_id).update(
            status='text_pending',
            error_message=str(e)[:500],
        )
        print(f'Source image text gen failed for {product_id}: {e}\n{traceback.format_exc()}')
```

注意：

- 成功时建议清空 `error_message`。
- 不要改 `_generate_text_v2()` 的导入方式。
- 保持 direct / POD 不受影响。

## 补救已有 text_pending 产品

修复后需要对现有 source_image 文本失败产品重新跑文案生成。

当前至少有：

```text
Product #313
Product #314
Product #315
```

请提供管理命令或临时 shell：

```powershell
python src\manage.py shell -c "from apps.products.models import Product; from apps.dashboard.views import _run_source_image_text_generation; [_run_source_image_text_generation(p.id) for p in Product.objects.filter(generation_mode='source_image', status='text_pending')]"
```

如果担心一次执行太久，可以只处理最近的：

```powershell
python src\manage.py shell -c "from apps.dashboard.views import _run_source_image_text_generation; [_run_source_image_text_generation(i) for i in [313,314,315]]"
```

## 验证

1. 新上传图片素材并生成产品。
2. 产品不再报 `No module named 'ai'`。
3. 文案成功后状态变为 `completed`。
4. 标题不为空。
5. 已有 text_pending 的 source_image 产品重新跑后能生成标题。

## 重要约束

1. 只修 source_image 文案线程路径初始化。
2. 不影响 AI 直出和 POD 生成流程。
3. 不调用 ComfyUI。

## 2026-06-07 补充：图片素材库产品标题清洗与分类显示修复

### 用户反馈

1. 通过图片素材库生成产品后，产品标题里不要出现 `**` 字符。
2. 产品库列表中，通过图片素材库生成的产品，分类列应显示为 `图片素材库`，不要显示 `-`。

### 当前排查结论

1. `src/apps/dashboard/views.py` 的 `_generate_text_v2()` 里目前直接保存 AI 返回值：

```python
product.title = result.title
product.description = result.description
product.save()
```

DeepSeek / LLM 有时会返回 Markdown 格式标题，例如 `**Some Product Title**`，因此 `**` 被原样保存到了产品标题。

2. `src/apps/dashboard/templates/dashboard/product_list.html` 的分类列当前只判断：

```django
{% if p.prompt_preset %}
...
{% elif p.category %}
...
{% else %}
-
{% endif %}
```

通过图片素材库生成的产品通常是 `generation_mode == 'source_image'`，没有 `prompt_preset` / `category`，所以列表显示为 `-`。

3. 导出逻辑 `src/apps/export_app/services.py` 里也有类似分类 fallback，建议同步处理，否则导出文件里图片素材库产品分类也会是 `-`。

### 请 Claude 修复

#### 1. 生成标题/描述入库前做文本清洗

在 `src/apps/dashboard/views.py` 增加小范围文本清洗 helper，例如：

```python
import re

def _clean_generated_title(text: str) -> str:
    if not text:
        return ''
    text = text.replace('**', '').replace('__', '')
    text = re.sub(r'^\s*(Title|标题)\s*[:：]\s*', '', text, flags=re.IGNORECASE)
    text = text.strip().strip('"“”')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def _clean_generated_description(text: str) -> str:
    if not text:
        return ''
    text = text.replace('**', '').replace('__', '')
    return text.strip()
```

然后在 `_generate_text_v2()` 保存前使用：

```python
product.title = _clean_generated_title(result.title)
product.description = _clean_generated_description(result.description)
```

要求：
- 不要影响现有直接生成产品图 / POD 贴图模式的生成流程，只在保存文本时统一清洗。
- 如果标题清洗后为空，保留当前兜底逻辑或给出安全兜底标题，不能让已完成产品标题为空。
- 建议顺手处理已有数据：把数据库里已有标题中的 `**` 清掉，避免用户已经生成的产品继续显示异常标题。

#### 2. 产品库分类列显示图片素材库

在 `src/apps/dashboard/templates/dashboard/product_list.html` 的分类列中，优先判断：

```django
{% if p.generation_mode == 'source_image' %}
  <span class="badge bg-light text-dark">图片素材库</span>
{% elif p.prompt_preset %}
...
{% elif p.category %}
...
{% else %}
...
{% endif %}
```

要求：
- 只影响显示，不要把这类产品强行写入旧的分类管理表。
- 通过图片素材库生成的产品，在产品库里分类列必须稳定显示 `图片素材库`。

#### 3. 同步修复导出分类

在 `src/apps/export_app/services.py` 中，导出分类字段时也加同样逻辑：

```python
if product.generation_mode == 'source_image':
    category_name = '图片素材库'
elif product.prompt_preset:
    ...
elif product.category:
    ...
else:
    category_name = '-'
```

#### 4. 顺手确认 SKU 名称展示

如果产品库或导出里 SKU 列仍然只显示 `SKU#id` 或模板颜色，请优先使用 `ProductSKU.sku_name`：

```django
{% if sku.sku_name %}
  {{ sku.sku_name }}
{% elif sku.template %}
  {{ sku.template.get_color_display }}
{% else %}
  SKU#{{ sku.id }}
{% endif %}
```

图片素材库产品的 SKU 名称应为上传时选择的 T 恤颜色，例如 `白色 T恤` / `黑色 T恤`。

### 验收标准

1. 新生成的产品标题不再包含 `**`。
2. 已有标题中带 `**` 的产品，被清理后产品库不再显示 `**`。
3. 图片素材库生成的产品，在产品库分类列显示 `图片素材库`。
4. 导出时该类产品分类也为 `图片素材库`。
5. 不影响现有 AI 直出商品图、POD 贴图模式、提示词预设等已有功能。

## 2026-06-07 补充：POD 贴图模式支持大批量生成，但必须分批执行

### 用户需求

当前使用 POD 贴图模式创建产品时，数量输入框最大只能输入 10。用户需要大批量生成，例如输入 100、500，最高支持单次提交 1000 个产品。

但注意：用户明确要求不要一次性把 100 / 1000 个产品同时丢给 ComfyUI 生成，必须分批生成，避免 ComfyUI 或后台线程被打爆。

### 当前问题

`src/apps/dashboard/templates/dashboard/product_create.html` 当前数量输入限制为：

```html
<input type="number" name="count" value="1" min="1" max="10" ...>
```

`src/apps/dashboard/views.py` 的 POD 创建逻辑目前在循环里为每个产品直接启动：

```python
threading.Thread(target=_run_pod_generation, args=(product.id, pp.id), daemon=True).start()
```

如果直接把前端 max 改成 1000，会导致一次性启动大量线程，同时向 ComfyUI 提交大量任务，风险很高。

### 请 Claude 实现

#### 1. 前端数量上限改为 1000

在 `product_create.html` 中：

- 数量输入框 `max` 改为 `1000`。
- POD 模式下的提示文案改成类似：

```text
POD 模式支持最多 1000 个产品，系统会自动分批生成，可在产品库查看进度。
```

#### 2. 后端同步校验最大数量

在 `product_create` view 里读取 `count` 后，后端也必须校验：

```python
total/count <= 1000
```

不要只依赖前端 input max。

要求：

- 直接生成模式如已有数量限制，可以保持原逻辑。
- 本次重点只改 POD 模式。
- POD 随机提示词模式、手动选择提示词模式都要支持最多 1000 个最终产品。

#### 3. POD 产品创建后，不要逐个直接启动线程

把 POD 模式改为：

1. 先按用户选择创建所有 `Product`，状态为 `pending` 或现有合适状态。
2. 收集待生成任务列表，例如：

```python
jobs = [(product.id, print_preset_id), ...]
```

3. 只启动一个后台批量 worker 线程：

```python
threading.Thread(target=_run_pod_generation_batch, args=(jobs,), daemon=True).start()
```

#### 4. 新增 `_run_pod_generation_batch`

建议放在 `views.py` 中，先用轻量实现，不新增复杂队列表：

```python
def _run_pod_generation_batch(jobs, batch_size=3, batch_sleep=2):
    for index, (product_id, print_preset_id) in enumerate(jobs, start=1):
        try:
            _run_pod_generation(product_id, print_preset_id)
        except Exception as e:
            Product.objects.filter(id=product_id).update(
                status='failed',
                error_message=str(e)[:1000],
            )

        if index % batch_size == 0:
            time.sleep(batch_sleep)
```

说明：

- 默认 `batch_size=3`，`batch_sleep=2` 秒。
- 这里可以先串行跑，每 3 个休息一下；稳定性优先。
- 如果 Claude 判断 ComfyUI 当前实现已经天然排队，也仍然不要一次性启动 1000 个线程。
- 单个产品失败只标记该产品失败，不要中断整批任务。

#### 5. 创建成功提示文案

POD 创建成功后提示：

```text
已创建 X 个 POD 产品，将分批生成，请到产品库查看进度。
```

不要提示成“正在一次性生成”。

#### 6. 状态显示要求

产品库里新建的 POD 产品应该能看到：

- 未开始：`pending` / 等待生成
- 生成中：`processing`
- 完成：`completed`
- 失败：`failed`

如果当前 `_run_pod_generation()` 内部已经会把单个产品状态改成 `processing/completed/failed`，批量 worker 直接复用即可。

### 验收标准

1. POD 模式数量输入可以输入 `1000`。
2. 输入 `100` 时，后端只启动 1 个批量 worker，不会启动 100 个线程。
3. POD 随机提示词模式输入 `100` 时，实际创建 100 个产品，每个产品随机抽取提示词。
4. POD 手动选择提示词模式时，总产品数最多不能超过 1000。
5. ComfyUI 任务按小批次执行，不会瞬间堆满。
6. 某个产品失败不会阻断后续产品继续生成。
7. 不影响 AI 直出商品图模式、图片素材库模式、提示词预设管理等已有功能。

## 2026-06-07 补充：POD 分批生成需要可见进度，不能一直显示等待生成

### 用户反馈

POD 贴图模式现在已经可以分批生成了，但用户在产品库里看不到进度，只能看到产品一直是“等待生成”。

### 当前排查结论

`src/apps/dashboard/views.py` 中 `_run_pod_generation_batch()` 当前是串行/分批调用：

```python
for index, (product_id, print_preset_id) in enumerate(jobs, start=1):
    try:
        _run_pod_generation(product_id, print_preset_id)
```

但 `_run_pod_generation(product_id, print_preset_id)` 开始执行后，并没有第一时间把当前产品状态更新为 `processing`。

所以：

- 已创建但还没轮到的产品：`pending` / 等待生成。
- 正在被 ComfyUI 处理的产品：仍然也是 `pending` / 等待生成。
- 用户在产品库无法区分“排队中”和“正在生成中”。
- 如果页面不刷新，用户也看不到状态变化。

### 请 Claude 修复

#### 1. `_run_pod_generation()` 开始时立即更新状态

在 `_run_pod_generation(product_id, print_preset_id)` 成功读取到产品后，尽快执行：

```python
Product.objects.filter(id=product_id).update(
    status='processing',
    error_message=''
)
```

建议放在：

```python
product = Product.objects.select_related('template', 'country').get(id=product_id)
pp = PrintDesignPreset.objects.get(id=print_preset_id)
```

之后、模板校验之前。

这样当前真正开始生成的产品会立刻从“等待生成”变成“生成中”。

#### 2. 批量 worker 可选增加轻量日志

在 `_run_pod_generation_batch()` 中增加控制台日志，方便排查：

```python
print(f'POD batch progress: {index}/{len(jobs)} product_id={product_id}')
```

不需要复杂 UI，但后台要能看到当前批量任务跑到第几个。

#### 3. 产品库页面自动刷新状态

在 `src/apps/dashboard/templates/dashboard/product_list.html` 增加轻量自动刷新逻辑：

要求：

- 当当前列表里存在 `pending` / `processing` / `text_pending` 产品时，每 5 秒自动刷新一次页面。
- 如果当前筛选条件里没有这些状态，就不要刷新。
- 保留当前 URL 查询参数，例如国家筛选、状态筛选。

实现方式可以简单一些，例如在模板中计算是否有未完成产品：

```django
{% with has_active=False %}
...
{% endwith %}
```

或者更直接在 view 里传：

```python
has_active_products = products.filter(status__in=['pending', 'processing', 'text_pending']).exists()
```

然后模板：

```django
{% if has_active_products %}
setTimeout(() => window.location.reload(), 5000);
{% endif %}
```

注意如果 `products` 在 view 中已经被分页/转 list，需要用合适方式判断，不要引入额外错误。

#### 4. 状态文案建议

如果当前 `pending` 显示为“等待生成”，`processing` 显示为“生成中”，可以保持。

但 POD 分批生成时用户需要理解：

- `等待生成` = 已进入队列，还没轮到。
- `生成中` = 当前正在调用 ComfyUI。
- `已完成` = 图片和文本完成。
- `待补全文本` = 图已生成，标题/描述还没补完。

如果当前页面空间允许，可以在产品库顶部加一行很轻的提示：

```text
有产品正在生成，页面会自动刷新进度。
```

不要做复杂弹窗。

### 验收标准

1. POD 批量生成 100 个产品时，只有当前执行中的产品显示为“生成中”，未轮到的产品显示“等待生成”。
2. 产品完成后状态变为“已完成”或失败时变为“生成失败”。
3. 产品库页面在存在未完成产品时能自动刷新，用户不用手动刷新才能看到进度变化。
4. 不影响 AI 直出商品图模式、图片素材库模式。
5. 不要为了进度显示一次性启动多个 POD 线程，仍然保持分批执行策略。

## 2026-06-07 补充：POD 分批生成速度优化，支持小并发但不要打爆 ComfyUI

### 用户反馈

POD 分批生成现在稳定性比一次性提交好，但生成速度偏慢。用户希望加快生成速度。

### 当前原因

上一版批量 worker 建议是串行执行：

```python
for index, (product_id, print_preset_id) in enumerate(jobs, start=1):
    _run_pod_generation(product_id, print_preset_id)
    if index % batch_size == 0:
        time.sleep(batch_sleep)
```

这样虽然安全，但实际是一个产品完整跑完“生成印花 → 去背景 → 合成 → 生成标题”后才跑下一个，大批量时会明显慢。

### 请 Claude 优化

#### 1. 把 POD 批量 worker 从纯串行改成“小并发”

目标：

- 不要一次性为所有产品启动线程。
- 允许同时生成少量 POD 产品。
- 默认并发建议：`2`。
- 允许后续通过配置调整为 `1/2/3`，但不要默认超过 `3`。

建议实现：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

POD_BATCH_CONCURRENCY = 2
POD_BATCH_SLEEP = 1

def _run_pod_generation_batch(jobs, max_workers=POD_BATCH_CONCURRENCY, batch_sleep=POD_BATCH_SLEEP):
    total = len(jobs)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(_run_pod_generation, product_id, print_preset_id): (idx, product_id)
            for idx, (product_id, print_preset_id) in enumerate(jobs, start=1)
        }
        for future in as_completed(future_map):
            idx, product_id = future_map[future]
            try:
                future.result()
                print(f'POD batch progress: {idx}/{total} product_id={product_id} done')
            except Exception as e:
                Product.objects.filter(id=product_id).update(
                    status='failed',
                    error_message=str(e)[:500],
                )
                print(f'POD batch progress: {idx}/{total} product_id={product_id} failed: {e}')
            time.sleep(batch_sleep)
```

也可以用手写分批切片方式：

- 每批取 2 个 job。
- 批内并发执行。
- 批完成后 sleep 1 秒。

这两种都可以，但要求最多只同时运行 `2` 个 `_run_pod_generation()`。

#### 2. 并发数做成可配置

优先从 Django settings 或现有配置文件读取，例如：

```python
POD_BATCH_CONCURRENCY = getattr(settings, 'POD_BATCH_CONCURRENCY', 2)
POD_BATCH_SLEEP = getattr(settings, 'POD_BATCH_SLEEP', 1)
```

如果项目已有 `data/config.json` 管理生成配置，也可以放到那里，但不要做复杂 UI。

#### 3. 注意 ComfyUI 特性

ComfyUI 本身有队列，但这里仍然不要一次性提交 1000 个 prompt。

小并发的目的只是让：

- 当前 A 产品在等 ComfyUI / 文件 IO / 文案生成时，B 产品可以推进。
- 但整体仍然控制在可接受负载。

#### 4. 保留状态可见性

必须结合上一条任务：

- `_run_pod_generation()` 一开始要把当前产品设为 `processing`。
- 产品库自动刷新。
- 小并发时最多会看到 2 个左右产品处于 `生成中`，其他是 `等待生成`。

#### 5. 文案生成不要拖慢图片批量

如果 Claude 判断 DeepSeek 文案生成明显拖慢 POD 图片生成，可以考虑：

- 图片合成成功后先保存 SKU。
- 状态临时进入 `text_pending`。
- 后续单独补全文案。

但本次优先做“小并发生成”，不要引入复杂队列表，避免改动过大。

### 验收标准

1. POD 批量生成 20 个产品时，速度明显快于纯串行。
2. 后台不会一次性启动 20/100/1000 个线程。
3. 默认最多同时处理 2 个 POD 产品。
4. 产品库能看到最多约 2 个 `生成中`，其他 `等待生成`。
5. 单个产品失败不会影响其他产品。
6. 不影响 AI 直出商品图模式、图片素材库模式。

### 用户补充：配置允许时并发数可以更高

用户补充说明：如果他在配置里明确允许，POD 并发数可以高一点。

请 Claude 调整上面的实现要求：

1. 默认并发仍然保守，建议 `2`。
2. 但并发数必须支持配置读取，例如：

```python
POD_BATCH_CONCURRENCY = int(get_config('pod_batch_concurrency', 2))
```

或从 Django settings 读取：

```python
POD_BATCH_CONCURRENCY = getattr(settings, 'POD_BATCH_CONCURRENCY', 2)
```

3. 建议增加一个硬上限，防止误填过大：

```python
POD_BATCH_CONCURRENCY = max(1, min(POD_BATCH_CONCURRENCY, 8))
```

4. 如果用户之后把配置调成 `4` / `6` / `8`，系统应按配置并发执行。
5. 不要在前端或代码里写死只能 `2`，`2` 只是默认值。
6. 如果配置值非法、为空、不是数字，自动回落到 `2`。

验收补充：

- 默认配置下最多 2 个 POD 产品同时 `processing`。
- 配置为 4 后，最多 4 个 POD 产品同时 `processing`。
- 无论配置多少，都不能超过硬上限 8。

## 2026-06-07 紧急修复：POD 标题没有生成，原因是缺少 `import re`

### 用户反馈

POD 产品图片生成了，但标题没有生成。

### 当前排查结果

我查询了最近的产品状态，最近一批 POD 产品全部是：

```text
generation_mode = pod
status = text_pending
title = ''
error_message = "name 're' is not defined"
```

说明图片生成和合成都已经走完了，失败发生在文案生成/保存阶段。

### 根因

`src/apps/dashboard/views.py` 中新增了标题/描述清洗函数：

```python
def _clean_generated_title(text: str) -> str:
    ...
    text = re.sub(...)
```

但文件顶部没有导入：

```python
import re
```

所以 `_generate_text_v2()` 调用 `_clean_generated_title()` 时抛出 `NameError: name 're' is not defined`，导致产品状态变成 `text_pending`，标题为空。

### 请 Claude 修复

#### 1. 在 `views.py` 顶部补充导入

```python
import re
```

#### 2. 检查 `_clean_generated_title()` 的正则是否正常

当前文件里因为中文编码显示异常，正则附近看起来可能是：

```python
re.sub(r'^\s*(Title|鏍囬|Judul)\s*[:锛歖\s*', '', text, flags=re.IGNORECASE)
```

请 Claude 顺手修成安全、简单、不依赖中文冒号乱码的版本：

```python
text = re.sub(r'^\s*(Title|Judul|标题)\s*[:：-]\s*', '', text, flags=re.IGNORECASE)
```

如果担心编码问题，可以只保留英文前缀：

```python
text = re.sub(r'^\s*(Title|Judul)\s*[:：-]\s*', '', text, flags=re.IGNORECASE)
```

关键是不要让正则本身因为乱码变得不可读。

#### 3. 补生成现有 `text_pending` 产品标题

修复代码后，需要对已有 `text_pending` 且标题为空的产品重新跑文案生成。

建议临时管理命令或 Django shell 处理：

```python
from apps.products.models import Product
from apps.dashboard.views import _generate_text_v2

qs = Product.objects.filter(status='text_pending', title='', generation_mode__in=['pod', 'source_image'])
for p in qs:
    try:
        _generate_text_v2(p.id)
        p.status = 'completed'
        p.error_message = ''
        p.save(update_fields=['status', 'error_message'])
        print('fixed', p.id)
    except Exception as e:
        p.error_message = str(e)[:500]
        p.save(update_fields=['error_message'])
        print('failed', p.id, e)
```

注意：

- 不要重新生成图片。
- 只补标题和描述。
- 已经有 mockup 图的产品只需要补文案。

### 验收标准

1. 新 POD 产品生成完成后标题不为空。
2. 最近状态为 `text_pending` 且错误为 `name 're' is not defined` 的产品，重新补全文案后变成 `completed`。
3. 不重新调用 ComfyUI 生成图片。
4. 产品标题不包含 `**`。

### 用户追加要求：修复后必须补全之前的文本

用户明确要求：代码修好后，之前已经生成图片但标题/描述没生成的产品，也要帮他补全文本。

请 Claude 不要只修新生成流程，必须执行一次历史数据补全文案：

目标产品：

```python
Product.objects.filter(
    status='text_pending',
    title='',
    generation_mode__in=['pod', 'source_image'],
)
```

执行要求：

1. 只调用 `_generate_text_v2(product.id)` 补标题和描述。
2. 不要重新调用 ComfyUI。
3. 不要删除或覆盖已有 SKU 图片。
4. 成功后把状态改成 `completed`，清空 `error_message`。
5. 失败的保持 `text_pending`，并写入新的 `error_message`。
6. 在终端输出补全结果，例如：

```text
text backfill completed: success=xx failed=xx
```

如果 Claude 使用 Django shell 执行，请在修复 `import re` 后再跑，否则仍然会失败。

## 2026-06-07 补充：POD 印花尺寸偏小、风格过于卡通，需要放大并增加多样性

### 用户反馈

用户查看当前生成结果后反馈：

1. 印花图案贴到 T 恤上后偏小，希望再放大一点。
2. 当前生成的图案大多偏卡通、可爱，希望风格更多样化。
3. 用户询问这是 LoRA 问题还是提示词问题。

### 当前排查结论

#### 1. 图案偏小的可能原因

当前 `src/apps/generation/comfyui.py` 的 `composite_pod_image()` 是：

```python
RMBG -> AILab_ImageResize -> ImageCompositeMasked
```

`AILab_ImageResize` 使用传入的 `width/height` 做 resize，但如果生成的印花图本身主体周围有较大留白，RMBG 后仍按整张画布缩放，最终“有效主体”会显得偏小。

因此偏小不一定是用户框选区域太小，更可能是：

- 印花源图主体占画布比例偏小；
- 合成前没有按 mask/透明区域裁掉空白；
- 合成时没有给可配置放大系数。

#### 2. 过于卡通的原因

这是“提示词 + LoRA”共同造成的，但提示词权重更明显。

当前 `src/apps/generation/print_variants.py` 的默认池里大量词汇偏向：

```text
cute mascot icon
emoji-like expression graphic
kawaii character symbol
flat vector sticker style
Japanese kawaii sticker style
smiling blob character
cute ghost-like mascot
```

同时 `data/config.json` 里当前配置：

```json
{
  "print_lora_name": "LogoRedmondV2-Logo-LogoRedmAF.safetensors",
  "print_lora_strength_model": 1.0,
  "print_lora_strength_clip": 1.0,
  "print_lora_trigger": "logo, logoredmaf"
}
```

LogoRedmond LoRA 会增强 logo / sticker / icon 感，`1.0` 强度偏高时会让风格更集中。

另外当前负向词里包含：

```python
'text', 'letters', 'words', 'typography', 'watermark', 'logo',
```

但正向触发词又是：

```text
logo, logoredmaf
```

这里有冲突：正向要求 logo，负向又禁止 logo。既然使用 LogoRedmond LoRA，负向词里不要再禁 `logo`，应只禁 `brand logo / readable text / watermark / letters` 等。

### 请 Claude 修复

#### 1. 放大印花：优先裁掉透明留白，再按区域放大

请优化 `composite_pod_image()` 的合成逻辑，目标是让有效印花主体更接近用户框选区域大小。

推荐方案：

1. RMBG 后拿到透明图和 mask。
2. 在 resize 前，根据 mask / alpha bbox 裁掉透明或近透明留白。
3. 再把裁剪后的印花缩放到目标区域。
4. 增加一个可配置放大系数，默认 `1.15`。
5. 放大后仍然不能超出用户框选区域太多，不能印到袖子或领口。

如果 ComfyUI 工作流里有合适节点，例如 mask bbox crop / crop by mask，请优先用 ComfyUI。

如果当前 ComfyUI 节点不好做，可以在 Python 里对 RMBG 后的 PIL 图片按 alpha bbox 做轻量裁剪，再上传裁剪后的透明图给 ComfyUI 合成。这个操作只处理透明边缘，不改变图案内容，可以接受。

建议配置项：

```json
"pod_print_scale": 1.15
```

并做安全限制：

```python
scale = max(1.0, min(config_scale, 1.35))
```

验收效果：

- 印花主体视觉上比现在大约放大 15% 到 25%。
- 仍然位于胸口框选区域。
- 不超过袖子，不贴近领口。

#### 2. 风格多样化：重构默认变体池

请调整 `src/apps/generation/print_variants.py` 的 `DEFAULT_VARIATION_POOL`，不要让默认风格大面积集中在 cute / kawaii / mascot。

建议把风格分成多组并随机抽取，例如：

```python
style_family = [
    'streetwear bold emblem',
    'abstract geometric logo mark',
    'vintage tattoo flash graphic',
    'grunge skate sticker graphic',
    'cyberpunk chrome symbol',
    'minimal modern icon mark',
    'retro surf/skate badge without text',
    'botanical ornamental graphic',
    'dark gothic ornamental symbol',
    'pop surreal object icon',
    'halftone comic graphic, not childish',
    'Y2K cyber icon',
]
```

元素池也要扩展，减少可爱表情类比例，例如：

```python
elements = [
    'abstract lightning serpent, sharp sparks, broken rings',
    'chrome liquid heart, asymmetric droplets, star cuts',
    'vintage skull flower, ornamental leaves, sun rays',
    'geometric panther head, angular shards, bold outline',
    'retro mushroom planet, orbit rings, small stars',
    'flame eye symbol, checker fragments, spray dots',
    'botanical snake curve, thorn branches, crescent moon',
    'surf wave skull, sunburst, rough ink texture',
    'glitch butterfly, pixel shards, neon accents',
    'minimal lucky charm icon, freeform contour',
]
```

保留少量 cute / mascot / meme，但不要作为默认大多数。

#### 3. LoRA 强度改成可配置/可随机弱化

不要删除 LogoRedmond LoRA，它对 logo 类图案有用。

但建议：

- 默认强度从 `1.0 / 1.0` 降到 `0.65 ~ 0.8`。
- 每次生成可以根据风格随机选择强度：
  - logo/emblem/icon：`0.75-0.9`
  - tattoo/grunge/abstract/botanical：`0.45-0.7`
  - cute sticker：`0.7-0.9`
- 如果项目实现复杂，先允许用户在 `data/config.json` 配置：

```json
"print_lora_strength_model": 0.75,
"print_lora_strength_clip": 0.75
```

后续再做 per-style strength。

#### 4. 修正 negative prompt 里的 LoRA 冲突

当前 negative prompt 必须禁止文字，但不要禁止 `logo` 本身。

请把 required negatives 中的：

```python
'text', 'letters', 'words', 'typography', 'watermark', 'logo',
```

改成：

```python
'text', 'letters', 'words', 'typography', 'watermark',
'brand logo', 'readable logo text', 'company logo',
```

原因：

- 用户要的是“热门 logo / 表情包 / 图案”的视觉形态。
- LogoRedmond 的触发词本身就包含 `logo`。
- 负向里写 `logo` 会抵消正向和 LoRA 效果。

#### 5. Prompt 中减少“卡通默认倾向”

`POD_PRINT_SYSTEM_PROMPT` 当前有：

```text
meme sticker, mascot icon, emoji-like symbol
Flat 2D vector/sticker/screen-print style
```

建议改成更中性的：

```text
Create one standalone print-ready graphic artwork.
The design can be a trending emblem, abstract logo mark, meme-inspired icon,
streetwear symbol, tattoo-flash graphic, ornamental motif, or bold decorative mark.
Use varied silhouettes and style families.
Avoid making every design cute, kawaii, childish, or mascot-like.
No readable text, no letters, no brand names.
Flat print-ready graphic with clean edges, suitable for screen print or DTG.
Centered isolated artwork, removable background.
```

注意：

- 不是完全禁止卡通，只是降低比例。
- 卡通、表情包、meme 仍可保留为一部分风格。

### 验收标准

1. 新生成的 POD 印花在 T 恤胸口视觉上比当前大，主体不要显得太小。
2. 印花仍然限制在用户框选区域内，不超过袖子、不靠近领口。
3. 连续生成 20 个 POD 产品时，风格应明显更多样，不应大多数都是可爱卡通心形/小表情。
4. 结果中应混合出现：街头、抽象、复古、几何、暗黑、植物、Y2K、meme/cute 等多种方向。
5. 不生成文字、字母、品牌名。
6. 不生成 T 恤/衣服元素作为印花内容。
7. 不影响图片素材库直接生成产品模式。

## 2026-06-07 紧急修复：POD 全部生成失败，`seed` 在赋值前被使用

### 用户反馈

用户反馈：现在 POD 产品全部生成失败。

### 当前排查结果

我查询最近失败产品，最近 100 个失败产品错误完全一致：

```text
Print gen failed: cannot access local variable 'seed' where it is not associated with a value
```

失败产品示例：

```text
515 pod failed '' "Print gen failed: cannot access local variable 'seed' where it is not associated with a value"
514 pod failed '' "Print gen failed: cannot access local variable 'seed' where it is not associated with a value"
...
```

说明失败发生在 POD 印花生成第一步，不是新增提示词文件本身的问题，也不是 ComfyUI 节点校验问题。

### 根因

`src/apps/generation/comfyui.py` 的 `generate_print_design()` 中，最近为了随机 LoRA 强度加入了：

```python
if lora_name:
    import random as _rnd
    rng = _rnd.Random(seed)
    lora_str = rng.uniform(0.55, 0.85)
    lora_strength_model = params.get('lora_strength_model', lora_str)
    lora_strength_clip = params.get('lora_strength_clip', lora_str)
```

但 `seed` 是在后面才定义的：

```python
seed = params.get('seed', 0)
```

所以只要启用了 LoRA，就会在 `seed` 赋值前报错，导致所有 POD 印花生成失败。

### 请 Claude 修复

#### 1. 把 `seed` 提前到 LoRA 随机强度之前

在 `generate_print_design()` 里，`params = params or {}` 后尽早定义：

```python
seed = params.get('seed', 0)
```

推荐结构：

```python
def generate_print_design(self, prompt: str, params: dict | None = None) -> ImageResult:
    params = params or {}
    seed = params.get('seed', 0)

    pod_config = self._load_pod_config()
    ...

    if lora_name:
        import random as _rnd
        rng = _rnd.Random(seed)
        lora_str = rng.uniform(0.55, 0.85)
        lora_strength_model = params.get('lora_strength_model', lora_str)
        lora_strength_clip = params.get('lora_strength_clip', lora_str)
```

然后删除后面重复的：

```python
seed = params.get('seed', 0)
```

避免重复定义造成混乱。

#### 2. 增加兜底，确保 seed 是整数

为了避免前端或配置传入字符串，建议：

```python
try:
    seed = int(params.get('seed', 0) or 0)
except (TypeError, ValueError):
    seed = 0
```

#### 3. 修复后处理已失败产品

这批失败产品没有生成图片，只有产品记录是 `failed`。

请 Claude 在修复后提供/执行一种恢复方式：

方案 A：把最近这批同错误的 POD 产品状态重置为 `pending`，并重新加入 POD 批量生成队列。

筛选条件：

```python
Product.objects.filter(
    generation_mode='pod',
    status='failed',
    error_message__contains="cannot access local variable 'seed'",
)
```

注意：

- 这些产品需要保留原本对应的 `print_preset_id` 才能自动重跑。
- 如果当前 Product 没有保存对应的 `PrintDesignPreset`，无法准确重跑时，不要乱跑；请提示用户删除这批失败产品后重新创建。

方案 B：如果无法恢复原提示词关联，请至少把这批失败产品批量删除或标记清晰，让用户重新创建。

优先不要自动删除用户数据，除非用户确认。

#### 4. 加一个最小防回归检查

修复后可以用 Django shell 直接调用一次：

```python
from apps.generation.comfyui import ComfyUIProvider
p = ComfyUIProvider()
# 不一定要真正跑完整 ComfyUI，可至少确认 generate_print_design 进入前不会 NameError
```

更实用的验收是创建 1 个 POD 产品，确认不再立即失败为 seed 报错。

### 验收标准

1. 新建 POD 产品不再出现：

```text
cannot access local variable 'seed' where it is not associated with a value
```

2. 启用 `LogoRedmondV2-Logo-LogoRedmAF.safetensors` LoRA 时也能正常生成。
3. 失败产品恢复策略明确：能重跑就重跑，不能重跑就提示用户删除后重新创建。
4. 不影响 AI 直出商品图和图片素材库模式。

## 2026-06-07 紧急修复：POD 印花放大后位置偏移，不在框选中心

### 用户反馈

用户反馈：印花放大后偏了，不在正中间。

用户示例图中，印花主体明显没有按照原胸口框选区域的中心点缩放，而是放大后出现位置漂移。

### 当前排查结论

`src/apps/generation/comfyui.py` 的 `composite_pod_image()` 里目前放大逻辑类似：

```python
scale = max(1.0, min(scale, 1.35))
scaled_w = int(width * scale)
scaled_h = int(height * scale)
...
"custom_width": scaled_w,
"custom_height": scaled_h,
...
"x": x,
"y": y,
```

问题在于：

- `width/height` 被放大了；
- 但是 `x/y` 仍然使用原框选区域左上角；
- 因此图案是从原来的左上角向右下角扩张，而不是围绕原框中心放大；
- 视觉结果就是印花中心偏移。

### 请 Claude 修复

#### 1. 放大必须以原框中心为锚点

在 `composite_pod_image(template_image, print_image, x, y, width, height, scale=...)` 中，计算：

```python
center_x = x + width / 2
center_y = y + height / 2

scaled_w = int(width * scale)
scaled_h = int(height * scale)

scaled_x = int(center_x - scaled_w / 2)
scaled_y = int(center_y - scaled_h / 2)
```

然后 `ImageCompositeMasked` 使用：

```python
"x": scaled_x,
"y": scaled_y,
```

而不是原始 `x/y`。

#### 2. 增加边界保护

因为放大后 `scaled_x/scaled_y` 可能小于 0 或超出模板尺寸，请根据模板图尺寸做 clamp：

```python
template_w, template_h = template_image.size
scaled_x = max(0, min(scaled_x, template_w - scaled_w))
scaled_y = max(0, min(scaled_y, template_h - scaled_h))
```

注意：

- 如果 `scaled_w > template_w` 或 `scaled_h > template_h`，要先限制 scale 或限制 scaled size，避免 `template_w - scaled_w` 为负导致逻辑异常。
- 由于印花区域本来是胸口区域，正常不会接近整个模板大小，但这里要防御极端情况。

#### 3. 不要破坏用户框选中心语义

用户在模板管理中框选的是“胸口印花区域”。放大只应该在该区域中心附近扩大视觉主体，不能改变用户选择的中心点。

也就是说：

- 原框中心点应保持不变；
- 放大后印花中心仍对齐原框中心；
- 不能因为 scale 把图案整体向右下角推。

#### 4. 建议增加日志方便确认

可以临时打印：

```python
print(f'POD composite area: original=({x},{y},{width},{height}) scaled=({scaled_x},{scaled_y},{scaled_w},{scaled_h}) scale={scale}')
```

便于后续排查模板坐标。

### 验收标准

1. `pod_print_scale > 1.0` 时，印花视觉中心仍然位于用户框选区域中心。
2. 图案不会因为放大整体向右下或其他方向漂移。
3. 图案仍然在胸口区域，不贴近领口，不压到袖子。
4. `pod_print_scale = 1.0` 时行为和旧逻辑一致。
5. 不影响 ComfyUI 印花生成、RMBG、标题生成。
