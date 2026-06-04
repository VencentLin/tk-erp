# TK-ERP — TikTok 东南亚印花T恤 AI生成系统

利用 AI 将印花T恤设计裂变生成新印花，并自动生成商品信息（泰文/印尼文），服务于 TikTok Shop 东南亚运营。

## 技术栈

- **Backend:** Django 4.2
- **任务队列:** Celery + Redis
- **数据库:** PostgreSQL 15
- **图片存储:** MinIO (S3兼容)
- **AI 图像:** ComfyUI (SDXL on RTX 5070)
- **AI 文本:** DeepSeek V4 Flash API (抖音 Coding Plan)
- **部署:** Docker Compose

## 快速启动

### 前置条件

- Python 3.11+
- Docker & Docker Compose
- NVIDIA GPU + ComfyUI (用于图像生成)
- DeepSeek API Key (抖音 Coding Plan)

### 本地开发

```bash
pip install -r requirements.txt
cd src
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

访问 http://localhost:8000/admin

### Docker 部署

```bash
cp .env.example .env
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

## 使用流程

1. 在 Admin 后台添加国家（印尼 ID / 泰国 TH）和店铺
2. 上传 T 恤模板图（白/黑/彩色底图）
3. 上传原始印花图
4. 选择目标国家和模板，启动生成
5. 在产品库查看结果，导出 CSV/ZIP

## 项目结构

```
tk-erp/
├── docker-compose.yml
├── src/
│   ├── config/              # Django 配置 + Celery
│   ├── apps/                # 业务模块
│   │   ├── accounts/        # 用户角色
│   │   ├── core/            # Country/Store
│   │   ├── patterns/        # 原始印花
│   │   ├── templates_app/   # T恤模板
│   │   ├── products/        # 生成产品
│   │   ├── generation/      # AI 引擎
│   │   └── export_app/      # 导出
│   └── celery_app/          # Celery 任务
├── ai/                      # AI 配置
└── docs/                    # 文档
```
