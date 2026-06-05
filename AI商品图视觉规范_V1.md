# AI商品图视觉规范 V1

## 一、品牌定位

### 风格关键词

- Korean Streetwear
- Vintage Graphic Tee
- Oversized Fit
- Youth Fashion
- Dark Aesthetic
- Y2K Street Style
- Urban Casual

### 目标用户

- 18-30岁
- 男女性均可
- 喜欢宽松版型
- 潮流印花T恤用户
- Shopee / Lazada / TikTok Shop用户

---

## 二、产品规范

### 版型

统一使用：

**Oversized T-Shirt**

特征：

- 落肩设计
- 宽松袖口
- 长衣长
- 宽衣身
- 圆领
- 230g-280g重磅棉

禁止：

- 修身版
- 紧身版
- 商务版

---

## 三、面料规范

关键词：

- premium cotton
- heavyweight cotton
- 230gsm cotton
- 280gsm cotton
- soft cotton texture
- natural wrinkles
- fabric folds

生成要求：

- 保留真实褶皱
- 不要完全平整
- 体现厚重感
- 有棉布纹理

---

## 四、印花规范

允许风格：

### Horror Graphic

- 黑白人物
- 尖叫
- 扭曲面孔
- 暗黑艺术

### Vintage Graphic

- 复古人物
- 老照片风格
- 胶片颗粒

### Abstract Graphic

- 线条人像
- 抽象图腾
- 极简艺术

### Typography

- 大字号英文
- 复古字体
- 扭曲字体
- 艺术字体

禁止：

- 儿童卡通
- 动漫风
- 二次元
- 可爱风
- 萌系设计

---

## 五、背景规范

### 优先级1：室内场景

- 办公椅
- 书架
- 木纹背景
- 咖啡馆
- 极简家居

关键词：

- minimalist interior
- wood furniture
- bookshelf background
- modern room
- soft ambient lighting

### 优先级2：纯色背景

- 浅灰
- 米白
- 浅蓝

禁止：

- 复杂户外背景
- 街道
- 商场
- 人群

---

## 六、灯光规范

统一：

- soft lighting
- ambient light
- natural daylight
- commercial photography

特点：

- 柔光
- 无强阴影
- 电商风
- 高亮面料细节

---

## 七、构图规范

### 商品平铺图

- front view
- center composition
- symmetrical layout
- full garment visible

### 商品实拍图

- 45 degree angle
- natural placement
- lifestyle presentation

### 模特图

- half body
- partial face visible
- focus on clothing
- product centered

---

## 八、基础 Prompt

```text
Young streetwear fashion model,
wearing oversized heavyweight cotton t-shirt,
premium 230gsm cotton,
natural fabric folds,
urban casual style,
soft indoor lighting,
minimalist interior background,
high detail fabric texture,
commercial apparel photography,
fashion catalog shot,
85mm lens,
ultra realistic,
8k
```

## 九、平铺图 Prompt

```text
oversized black t-shirt,
front view,
heavyweight cotton,
230gsm fabric,
natural wrinkles,
center composition,
clean background,
graphic print centered on chest,
fashion mockup,
commercial apparel presentation,
realistic cotton texture,
high detail,
8k
```

## 十、实拍商品图 Prompt

```text
oversized black graphic t-shirt,
placed on office chair,
modern bookshelf background,
streetwear aesthetic,
natural folds,
premium cotton texture,
soft daylight,
fashion product photography,
ecommerce product shot,
realistic fabric details,
high resolution,
8k
```

## 十一、负面 Prompt

```text
low quality,
blurry,
anime,
cartoon,
childish,
cute style,
plastic fabric,
polyester texture,
oversaturated,
bad anatomy,
deformed clothing,
cropped garment,
watermark,
logo distortion,
low resolution
```

## 十二、新品生成公式

商品颜色 + 商品版型 + 印花主题 + 基础Prompt + 背景Prompt

示例：

```text
oversized black t-shirt
horror graphic print
office chair background
premium cotton texture
soft indoor lighting
```
