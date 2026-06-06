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
