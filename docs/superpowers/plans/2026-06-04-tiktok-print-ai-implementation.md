# TikTok 东南亚印花T恤 AI生成系统 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个 Django Web 应用，支持上传印花T恤图片，通过 ComfyUI + Ollama 进行 AI 裂变生成新印花和商品信息（泰文/印尼文），并导出产品数据。

**Architecture:** Django 4.2 单体应用，Celery 任务队列处理 AI 流水线，PostgreSQL 存元数据，MinIO 存图片，ComfyUI + Ollama 自建 AI 推理。

**Tech Stack:** Python 3.11+, Django 4.2, Celery 5.x, Redis, PostgreSQL 15, MinIO, ComfyUI (HTTP API), Ollama (HTTP API), Docker Compose

**设计文档:** `docs/superpowers/specs/2026-06-04-tiktok-print-ai-design.md`

---

## 文件结构

```
tk-erp/
├── docker-compose.yml          # 新建 - 所有服务编排
├── Dockerfile                  # 新建 - Django + Celery 镜像
├── requirements.txt            # 新建 - Python 依赖
├── .env.example                # 新建 - 环境变量模板
├── .env                        # 新建 - 本地环境变量（不提交）
├── .gitignore                  # 新建 - Git 忽略规则
├── src/
│   ├── manage.py               # 新建 - Django 入口
│   ├── config/                 # 新建 - Django 项目配置
│   │   ├── __init__.py
│   │   ├── settings/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # 公共配置
│   │   │   └── dev.py          # 开发环境覆盖
│   │   ├── urls.py             # 根 URL 路由
│   │   ├── wsgi.py
│   │   └── celery.py           # Celery 配置
│   ├── apps/                   # 新建 - 业务应用
│   │   ├── __init__.py
│   │   ├── accounts/           # 用户与权限
│   │   │   ├── __init__.py
│   │   │   ├── models.py       # User 扩展
│   │   │   ├── admin.py        # 用户管理 Admin
│   │   │   └── apps.py
│   │   ├── core/               # 共享基础模型
│   │   │   ├── __init__.py
│   │   │   ├── models.py       # Country, Store
│   │   │   ├── admin.py
│   │   │   └── apps.py
│   │   ├── patterns/           # 原始印花
│   │   │   ├── __init__.py
│   │   │   ├── models.py       # Pattern
│   │   │   ├── admin.py
│   │   │   └── apps.py
│   │   ├── templates_app/      # T恤模板管理
│   │   │   ├── __init__.py
│   │   │   ├── models.py       # TShirtTemplate
│   │   │   ├── admin.py
│   │   │   └── apps.py
│   │   ├── products/           # 生成产品
│   │   │   ├── __init__.py
│   │   │   ├── models.py       # Product, GenerationLog
│   │   │   ├── admin.py
│   │   │   └── apps.py
│   │   ├── generation/         # AI 引擎
│   │   │   ├── __init__.py
│   │   │   ├── provider.py     # AIProvider 抽象接口
│   │   │   ├── comfyui.py      # ComfyUI provider
│   │   │   ├── ollama.py       # Ollama provider
│   │   │   ├── variants.py     # 变体策略生成
│   │   │   └── apps.py
│   │   └── export_app/         # 产品导出
│   │       ├── __init__.py
│   │       ├── services.py     # CSV/图片导出逻辑
│   │       ├── admin.py
│   │       └── apps.py
│   └── celery_app/             # Celery 任务
│       ├── __init__.py
│       ├── preprocessing.py    # 抠图/去背景
│       ├── image_gen.py        # 印花变体生成
│       ├── text_gen.py         # 商品文本生成
│       └── pipeline.py         # 完整流水线编排
├── ai/
│   ├── comfy_workflows/        # ComfyUI 工作流 JSON
│   │   └── print_variation.json
│   └── prompts/                # Prompt 模板
│       ├── __init__.py
│       ├── loader.py           # Prompt 加载工具
│       ├── image_variants.toml
│       ├── title_th.txt
│       └── title_id.txt
├── data/                       # 持久化数据（gitignore）
└── docs/
    └── superpowers/
        ├── specs/
        └── plans/
```

---

### Task 1: 项目基础脚手架

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `.env`
- Create: `src/manage.py`
- Create: `src/config/__init__.py`
- Create: `src/config/settings/__init__.py`
- Create: `src/config/settings/base.py`
- Create: `src/config/settings/dev.py`
- Create: `src/config/urls.py`
- Create: `src/config/wsgi.py`
- Create: `src/config/celery.py`
- Create: `src/config/__init__.py`
- Create: `src/apps/__init__.py`

- [ ] **Step 1: 创建 requirements.txt**

```txt
Django>=4.2,<5.0
celery[redis]>=5.3,<6.0
psycopg2-binary>=2.9
django-storages[s3]>=1.14
minio>=7.2
Pillow>=10.0
rembg>=2.0
httpx>=0.25
django-celery-results>=2.5
python-decouple>=3.8
django-htmx>=1.17
```

- [ ] **Step 2: 创建 .gitignore**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
.venv/

# Environment
.env
.env.local

# Data (persistent volumes)
data/

# IDE
.idea/
.vscode/
*.swp

# OS
.DS_Store
Thumbs.db

# Media uploads
media/

# Static
staticfiles/
```

- [ ] **Step 3: 创建 .env.example**

```
DJANGO_SECRET_KEY=change-me-to-random-string
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

POSTGRES_DB=tkerp
POSTGRES_USER=tkerp
POSTGRES_PASSWORD=change-me
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

REDIS_URL=redis://localhost:6379/0

MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=tkerp-images

COMFYUI_BASE_URL=http://localhost:7860
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:14b
```

- [ ] **Step 4: 创建 .env（开发用，从 .env.example 复制）**

Run: `cp .env.example .env`

- [ ] **Step 5: 创建 src/config/settings/base.py**

```python
import os
from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('DJANGO_SECRET_KEY', default='dev-secret-key-change-me')
DEBUG = config('DJANGO_DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # 三方
    'django_celery_results',
    'storages',
    # 业务
    'apps.accounts',
    'apps.core',
    'apps.patterns',
    'apps.templates_app',
    'apps.products',
    'apps.generation',
    'apps.export_app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB', default='tkerp'),
        'USER': config('POSTGRES_USER', default='tkerp'),
        'PASSWORD': config('POSTGRES_PASSWORD', default='tkerp'),
        'HOST': config('POSTGRES_HOST', default='localhost'),
        'PORT': config('POSTGRES_PORT', default='5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery
CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Shanghai'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes max per task

# MinIO / S3-compatible storage
AWS_ACCESS_KEY_ID = config('MINIO_ACCESS_KEY', default='minioadmin')
AWS_SECRET_ACCESS_KEY = config('MINIO_SECRET_KEY', default='minioadmin')
AWS_STORAGE_BUCKET_NAME = config('MINIO_BUCKET', default='tkerp-images')
AWS_S3_ENDPOINT_URL = f"http://{config('MINIO_ENDPOINT', default='localhost:9000')}"
AWS_S3_REGION_NAME = 'us-east-1'
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = False

# AI provider settings
COMFYUI_BASE_URL = config('COMFYUI_BASE_URL', default='http://localhost:7860')
OLLAMA_BASE_URL = config('OLLAMA_BASE_URL', default='http://localhost:11434')
OLLAMA_MODEL = config('OLLAMA_MODEL', default='qwen2.5:14b')
```

- [ ] **Step 6: 创建 src/config/settings/dev.py**

```python
from .base import *

DEBUG = True

# 开发环境使用 SQLite 方便快速启动（可选），正式用 PostgreSQL
# 如果想本地快速跑，取消下面注释并把 base.py 的 DATABASES 注释掉
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }
```

- [ ] **Step 7: 创建 src/config/settings/__init__.py**

```python
# 默认使用 dev 配置
from .dev import *
```

- [ ] **Step 8: 创建 src/manage.py**

```python
#!/usr/bin/env python
import os
import sys

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
```

- [ ] **Step 9: 创建 src/config/urls.py**

```python
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('admin/', admin.site.urls),
]
```

- [ ] **Step 10: 创建 src/config/wsgi.py**

```python
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
application = get_wsgi_application()
```

- [ ] **Step 11: 创建 src/config/celery.py**

```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('tk_erp')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

- [ ] **Step 12: 创建 src/config/__init__.py（Celery 引导）**

```python
from .celery import app as celery_app

__all__ = ('celery_app',)
```

- [ ] **Step 13: 创建所有 apps 的空 __init__.py 和 apps.py 文件**

Run:
```bash
mkdir -p src/apps/accounts src/apps/core src/apps/patterns src/apps/templates_app src/apps/products src/apps/generation src/apps/export_app
touch src/apps/__init__.py
for app in accounts core patterns templates_app products generation export_app; do
    touch src/apps/$app/__init__.py
done
```

- [ ] **Step 14: 创建所有 apps.py 文件**

`src/apps/accounts/apps.py`:
```python
from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = '用户管理'
```

`src/apps/core/apps.py`:
```python
from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = '基础数据'
```

`src/apps/patterns/apps.py`:
```python
from django.apps import AppConfig

class PatternsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.patterns'
    verbose_name = '原始印花'
```

`src/apps/templates_app/apps.py`:
```python
from django.apps import AppConfig

class TemplatesAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.templates_app'
    verbose_name = 'T恤模板'
```

`src/apps/products/apps.py`:
```python
from django.apps import AppConfig

class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.products'
    verbose_name = '生成产品'
```

`src/apps/generation/apps.py`:
```python
from django.apps import AppConfig

class GenerationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.generation'
    verbose_name = 'AI生成引擎'
```

`src/apps/export_app/apps.py`:
```python
from django.apps import AppConfig

class ExportAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.export_app'
    verbose_name = '产品导出'
```

- [ ] **Step 15: 验证项目能启动**

```bash
cd src && pip install -r ../requirements.txt
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 16: 提交**

```bash
git add -A
git commit -m "feat: scaffold Django project structure with settings, Celery, and app stubs

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Docker 部署环境

**Files:**
- Create: `docker-compose.yml`
- Create: `Dockerfile`

- [ ] **Step 1: 创建 Dockerfile**

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

WORKDIR /app/src
RUN python manage.py collectstatic --noinput || true

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2"]
```

- [ ] **Step 2: 创建 docker-compose.yml**

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: tkerp
      POSTGRES_USER: tkerp
      POSTGRES_PASSWORD: tkerp
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tkerp"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - ./data/redis:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - ./data/minio:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 5s
      timeout: 5s
      retries: 5

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      minio:
        condition: service_healthy

  celery_worker:
    build: .
    command: celery -A config worker -l info -c 2
    volumes:
      - .:/app
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery_beat:
    build: .
    command: celery -A config beat -l info
    volumes:
      - .:/app
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
```

- [ ] **Step 3: 验证 Docker Compose 语法**

```bash
docker compose config --quiet
```

Expected: no output (config is valid).

- [ ] **Step 4: 提交**

```bash
git add Dockerfile docker-compose.yml
git commit -m "feat: add Docker Compose setup with PostgreSQL, Redis, MinIO, and Celery

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 基础数据模型 — Country 和 Store

**Files:**
- Create: `src/apps/core/models.py`
- Create: `src/apps/core/admin.py`
- Create: `src/apps/core/migrations/` (auto via makemigrations)

- [ ] **Step 1: 写 Country 和 Store model 测试**

Create `tests/test_core_models.py`:
```python
import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from apps.core.models import Country, Store

User = get_user_model()

@pytest.mark.django_db
class TestCountry:
    def test_create_country(self):
        c = Country.objects.create(code='ID', name='Indonesia')
        assert str(c) == 'Indonesia'
        assert c.code == 'ID'

    def test_country_code_unique(self):
        Country.objects.create(code='ID', name='Indonesia')
        with pytest.raises(Exception):
            Country.objects.create(code='ID', name='Duplicate')

@pytest.mark.django_db
class TestStore:
    def test_create_store(self):
        user = User.objects.create_user(username='test', password='test')
        country = Country.objects.create(code='TH', name='Thailand')
        store = Store.objects.create(
            name='ShopThai01',
            country=country,
            owner=user,
            api_credentials={'shop_id': '12345', 'access_token': 'xxx'}
        )
        assert str(store) == 'ShopThai01'
        assert store.country.code == 'TH'

    def test_store_string_repr(self):
        user = User.objects.create_user(username='owner', password='test')
        country = Country.objects.create(code='ID', name='Indonesia')
        store = Store.objects.create(name='MyStore', country=country, owner=user)
        assert str(store) == 'MyStore'
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd src && pytest tests/test_core_models.py -v
```

Expected: FAIL (models not defined yet)

- [ ] **Step 3: 创建 src/apps/core/models.py**

```python
from django.db import models
from django.conf import settings


class Country(models.Model):
    """国家（印尼/泰国/...）"""
    code = models.CharField(max_length=8, unique=True, help_text='ISO代码，如 ID, TH')
    name = models.CharField(max_length=64)

    class Meta:
        verbose_name = '国家'
        verbose_name_plural = '国家'
        ordering = ['code']

    def __str__(self):
        return self.name


class Store(models.Model):
    """TikTok Shop 店铺"""
    name = models.CharField(max_length=128)
    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, related_name='stores'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='stores'
    )
    api_credentials = models.JSONField(default=dict, blank=True, help_text='TikTok Shop API 凭证')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '店铺'
        verbose_name_plural = '店铺'
        ordering = ['country', 'name']

    def __str__(self):
        return self.name
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd src && pytest tests/test_core_models.py -v
```

Expected: all PASS

- [ ] **Step 5: 创建 src/apps/core/admin.py**

```python
from django.contrib import admin
from .models import Country, Store


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name']
    search_fields = ['code', 'name']


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ['name', 'country', 'owner', 'is_active', 'created_at']
    list_filter = ['country', 'is_active']
    search_fields = ['name', 'owner__username']
```

- [ ] **Step 6: 创建数据库迁移**

```bash
cd src && python manage.py makemigrations core
python manage.py migrate
```

- [ ] **Step 7: 提交**

```bash
git add tests/ src/apps/core/
git commit -m "feat: add Country and Store models with admin

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: T恤模板模型 — TShirtTemplate

**Files:**
- Create: `src/apps/templates_app/models.py`
- Create: `src/apps/templates_app/admin.py`
- Create: `src/apps/templates_app/storage.py` (MinIO storage backend 初始化)

- [ ] **Step 1: 创建 MinIO 存储后端初始化**

`src/apps/templates_app/storage.py`:
```python
from storages.backends.s3boto3 import S3Boto3Storage


class TemplateImageStorage(S3Boto3Storage):
    """T恤模板图片专用存储"""
    location = 'templates'
    file_overwrite = False
    default_acl = None
```

- [ ] **Step 2: 写模板模型测试**

Create `tests/test_template_models.py`:
```python
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.templates_app.models import TShirtTemplate

@pytest.mark.django_db
class TestTShirtTemplate:
    def test_create_template(self):
        tmpl = TShirtTemplate.objects.create(
            name='白色基础款',
            color='white',
        )
        assert str(tmpl) == '白色基础款 (white)'
        assert tmpl.color == 'white'

    def test_color_choices(self):
        tmpl = TShirtTemplate.objects.create(name='Red', color='other')
        assert tmpl.color == 'other'

    def test_default_is_active(self):
        tmpl = TShirtTemplate.objects.create(name='Test', color='black')
        assert tmpl.is_active is True

    def test_ordering_by_created_at_desc(self):
        old = TShirtTemplate.objects.create(name='Old', color='white')
        new = TShirtTemplate.objects.create(name='New', color='black')
        qs = list(TShirtTemplate.objects.all())
        assert qs[0] == new  # newer first
        assert qs[1] == old
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd src && pytest tests/test_template_models.py -v
```

Expected: FAIL

- [ ] **Step 4: 创建 src/apps/templates_app/models.py**

```python
from django.db import models
from .storage import TemplateImageStorage


class TShirtTemplate(models.Model):
    """T恤底图模板"""
    COLOR_CHOICES = [
        ('white', '白色'),
        ('black', '黑色'),
        ('gray', '灰色'),
        ('navy', '深蓝'),
        ('red', '红色'),
        ('other', '其他颜色'),
    ]

    name = models.CharField(max_length=128, help_text='模板名称，如"白色基础款圆领"')
    image = models.ImageField(
        upload_to='tshirt_templates/%Y/%m/',
        storage=TemplateImageStorage(),
        help_text='T恤底图（建议1024x1024以上PNG）'
    )
    color = models.CharField(max_length=16, choices=COLOR_CHOICES, default='white')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'T恤模板'
        verbose_name_plural = 'T恤模板'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.color})'
```

- [ ] **Step 5: 运行测试验证通过**

```bash
cd src && pytest tests/test_template_models.py -v
```

Expected: all PASS

- [ ] **Step 6: 创建 src/apps/templates_app/admin.py**

```python
from django.contrib import admin
from .models import TShirtTemplate


@admin.register(TShirtTemplate)
class TShirtTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'is_active', 'created_at']
    list_filter = ['color', 'is_active']
    search_fields = ['name']
    readonly_fields = ['created_at']
```

- [ ] **Step 7: 创建迁移并提交**

```bash
cd src && python manage.py makemigrations templates_app
python manage.py migrate
git add tests/ src/apps/templates_app/
git commit -m "feat: add TShirtTemplate model with color choices and MinIO storage

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 原始印花模型 — Pattern

**Files:**
- Create: `src/apps/patterns/models.py`
- Create: `src/apps/patterns/admin.py`
- Create: `src/apps/patterns/storage.py`

- [ ] **Step 1: 创建存储后端**

`src/apps/patterns/storage.py`:
```python
from storages.backends.s3boto3 import S3Boto3Storage


class PatternImageStorage(S3Boto3Storage):
    location = 'patterns'
    file_overwrite = False
    default_acl = None
```

- [ ] **Step 2: 写 Pattern 模型测试**

Create `tests/test_pattern_models.py`:
```python
import pytest
from django.contrib.auth import get_user_model
from apps.patterns.models import Pattern

User = get_user_model()

@pytest.mark.django_db
class TestPattern:
    def test_create_pattern(self):
        user = User.objects.create_user(username='uploader', password='test')
        p = Pattern.objects.create(
            uploaded_by=user,
            source_type='clean_print',
            note='参考印花 #001'
        )
        assert str(p).startswith('Pattern #')
        assert p.source_type == 'clean_print'

    def test_source_type_choices(self):
        user = User.objects.create_user(username='u2', password='test')
        p = Pattern.objects.create(
            uploaded_by=user,
            source_type='model_photo'
        )
        assert p.source_type == 'model_photo'

    def test_soft_delete(self):
        user = User.objects.create_user(username='u3', password='test')
        p = Pattern.objects.create(uploaded_by=user)
        p.is_deleted = True
        p.save()
        assert Pattern.objects.filter(is_deleted=False).count() == 0
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd src && pytest tests/test_pattern_models.py -v
```

Expected: FAIL

- [ ] **Step 4: 创建 src/apps/patterns/models.py**

```python
from django.db import models
from django.conf import settings
from .storage import PatternImageStorage


class Pattern(models.Model):
    """原始印花图"""
    SOURCE_CHOICES = [
        ('clean_print', '干净印花（透明底）'),
        ('model_photo', '模特上身图'),
        ('product_photo', '产品平铺图'),
    ]

    image = models.ImageField(
        upload_to='patterns/%Y/%m/',
        storage=PatternImageStorage(),
        help_text='原始印花图片'
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='patterns'
    )
    source_type = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default='clean_print',
        help_text='图片来源类型（决定是否需要抠图预处理）'
    )
    note = models.TextField(blank=True, default='')
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '原始印花'
        verbose_name_plural = '原始印花'
        ordering = ['-created_at']

    def __str__(self):
        return f'Pattern #{self.id}'
```

- [ ] **Step 5: 运行测试验证**

```bash
cd src && pytest tests/test_pattern_models.py -v
```

Expected: all PASS

- [ ] **Step 6: 创建 src/apps/patterns/admin.py**

```python
from django.contrib import admin
from .models import Pattern


@admin.register(Pattern)
class PatternAdmin(admin.ModelAdmin):
    list_display = ['id', 'uploaded_by', 'source_type', 'is_deleted', 'created_at']
    list_filter = ['source_type', 'is_deleted']
    search_fields = ['note']
    readonly_fields = ['created_at']
```

- [ ] **Step 7: 创建迁移并提交**

```bash
cd src && python manage.py makemigrations patterns
python manage.py migrate
git add tests/ src/apps/patterns/
git commit -m "feat: add Pattern model with source type detection for preprocessing

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 生成产品模型 — Product 和 GenerationLog

**Files:**
- Create: `src/apps/products/models.py`
- Create: `src/apps/products/admin.py`
- Create: `src/apps/products/storage.py`

- [ ] **Step 1: 创建存储后端**

`src/apps/products/storage.py`:
```python
from storages.backends.s3boto3 import S3Boto3Storage


class ProductImageStorage(S3Boto3Storage):
    location = 'products'
    file_overwrite = False
    default_acl = None
```

- [ ] **Step 2: 写 Product 和 GenerationLog 模型测试**

Create `tests/test_product_models.py`:
```python
import pytest
from django.contrib.auth import get_user_model
from apps.core.models import Country
from apps.patterns.models import Pattern
from apps.templates_app.models import TShirtTemplate
from apps.products.models import Product, GenerationLog

User = get_user_model()

@pytest.mark.django_db
class TestProduct:
    def setup_method(self):
        self.user = User.objects.create_user(username='test', password='test')
        self.country_id = Country.objects.create(code='ID', name='Indonesia')
        self.country_th = Country.objects.create(code='TH', name='Thailand')
        self.pattern = Pattern.objects.create(uploaded_by=self.user)
        self.template = TShirtTemplate.objects.create(name='White', color='white')

    def test_create_product(self):
        p = Product.objects.create(
            country=self.country_id,
            pattern=self.pattern,
            template=self.template,
            title='Kaos Unik Motif Bunga',
            description='Kaos katun nyaman dengan motif bunga tropis.',
            size_info='S, M, L, XL',
            status='completed'
        )
        assert p.status == 'completed'
        assert 'Kaos' in p.title

    def test_product_string(self):
        p = Product.objects.create(
            country=self.country_id, pattern=self.pattern,
            template=self.template, title='Test',
            description='Desc', size_info='S,M,L', status='completed'
        )
        assert str(p) == f'Product #{p.id} - Test'

    def test_default_status(self):
        p = Product.objects.create(
            country=self.country_id, pattern=self.pattern,
            template=self.template, title='', description='', size_info=''
        )
        assert p.status == 'pending'

    def test_filter_by_country(self):
        Product.objects.create(
            country=self.country_id, pattern=self.pattern, template=self.template,
            title='ID Product', description='', size_info=''
        )
        Product.objects.create(
            country=self.country_th, pattern=self.pattern, template=self.template,
            title='TH Product', description='', size_info=''
        )
        assert Product.objects.filter(country=self.country_id).count() == 1
        assert Product.objects.filter(country=self.country_th).count() == 1


@pytest.mark.django_db
class TestGenerationLog:
    def setup_method(self):
        self.user = User.objects.create_user(username='test', password='test')
        self.country = Country.objects.create(code='ID', name='Indonesia')
        self.pattern = Pattern.objects.create(uploaded_by=self.user)
        self.template = TShirtTemplate.objects.create(name='White', color='white')
        self.product = Product.objects.create(
            country=self.country, pattern=self.pattern, template=self.template,
            title='Test', description='', size_info=''
        )

    def test_create_log(self):
        log = GenerationLog.objects.create(
            product=self.product,
            step='image_gen',
            model_used='sdxl',
            params={'prompt': 'test prompt', 'batch_size': 4},
            duration_ms=3500,
            token_count=0
        )
        assert log.step == 'image_gen'
        assert log.duration_ms == 3500
        assert str(log).startswith('image_gen for Product #')
```

- [ ] **Step 3: 运行测试确认失败**

```bash
cd src && pytest tests/test_product_models.py -v
```

Expected: FAIL

- [ ] **Step 4: 创建 src/apps/products/models.py**

```python
from django.db import models
from apps.core.models import Country
from apps.patterns.models import Pattern
from apps.templates_app.models import TShirtTemplate
from .storage import ProductImageStorage


class Product(models.Model):
    """AI 生成的产品"""
    STATUS_CHOICES = [
        ('pending', '等待生成'),
        ('processing', '生成中'),
        ('completed', '已完成'),
        ('failed', '生成失败'),
        ('text_pending', '待补全文本'),
    ]

    # 关系
    country = models.ForeignKey(
        Country, on_delete=models.PROTECT, related_name='products'
    )
    pattern = models.ForeignKey(
        Pattern, on_delete=models.PROTECT, related_name='products',
        help_text='参考的原始印花'
    )
    template = models.ForeignKey(
        TShirtTemplate, on_delete=models.PROTECT, related_name='products',
        help_text='使用的T恤模板'
    )

    # 输出图片
    print_image = models.ImageField(
        upload_to='products/prints/%Y/%m/',
        storage=ProductImageStorage(),
        blank=True, null=True,
        help_text='生成的印花图'
    )
    mockup_image = models.ImageField(
        upload_to='products/mockups/%Y/%m/',
        storage=ProductImageStorage(),
        blank=True, null=True,
        help_text='印花+T恤效果图'
    )

    # 商品信息（根据 country 自动匹配语言）
    title = models.CharField(max_length=512, blank=True, default='')
    description = models.TextField(blank=True, default='')
    size_info = models.CharField(max_length=256, blank=True, default='',
                                  help_text='尺码信息')

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True
    )
    error_message = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = '生成产品'
        verbose_name_plural = '生成产品'
        ordering = ['-created_at']

    def __str__(self):
        return f'Product #{self.id} - {self.title[:50]}'


class GenerationLog(models.Model):
    """AI 生成记录"""
    STEP_CHOICES = [
        ('preprocess', '预处理（抠图）'),
        ('image_gen', '印花生成'),
        ('text_gen', '文本生成'),
        ('write_storage', '存储写入'),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='generation_logs'
    )
    step = models.CharField(max_length=20, choices=STEP_CHOICES)
    model_used = models.CharField(max_length=128, blank=True, default='')
    params = models.JSONField(default=dict, blank=True)
    duration_ms = models.PositiveIntegerField(default=0, help_text='耗时（毫秒）')
    token_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '生成记录'
        verbose_name_plural = '生成记录'
        ordering = ['product', 'created_at']

    def __str__(self):
        return f'{self.step} for Product #{self.product_id}'
```

- [ ] **Step 5: 运行测试验证**

```bash
cd src && pytest tests/test_product_models.py -v
```

Expected: all PASS

- [ ] **Step 6: 创建 src/apps/products/admin.py**

```python
from django.contrib import admin
from .models import Product, GenerationLog


class GenerationLogInline(admin.TabularInline):
    model = GenerationLog
    readonly_fields = ['step', 'model_used', 'duration_ms', 'created_at']
    extra = 0
    can_delete = False


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'country', 'status', 'created_at']
    list_filter = ['country', 'status']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [GenerationLogInline]


@admin.register(GenerationLog)
class GenerationLogAdmin(admin.ModelAdmin):
    list_display = ['product', 'step', 'model_used', 'duration_ms', 'created_at']
    list_filter = ['step']
    readonly_fields = ['created_at']
```

- [ ] **Step 7: 创建迁移并提交**

```bash
cd src && python manage.py makemigrations products
python manage.py migrate
git add tests/ src/apps/products/
git commit -m "feat: add Product and GenerationLog models with status tracking

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: 用户模型扩展与角色权限

**Files:**
- Create: `src/apps/accounts/models.py`
- Create: `src/apps/accounts/admin.py`

- [ ] **Step 1: 写用户角色测试**

Create `tests/test_account_models.py`:
```python
import pytest
from django.contrib.auth import get_user_model
from apps.accounts.models import UserProfile

User = get_user_model()

@pytest.mark.django_db
class TestUserProfile:
    def test_profile_created_with_user(self):
        user = User.objects.create_user(username='operator1', password='test')
        assert hasattr(user, 'profile')
        assert user.profile.role == 'operator'

    def test_admin_role(self):
        user = User.objects.create_user(username='admin1', password='test')
        user.is_staff = True
        user.profile.role = 'admin'
        user.profile.save()
        assert user.profile.role == 'admin'

    def test_country_lead_role(self):
        user = User.objects.create_user(username='lead_id', password='test')
        user.profile.role = 'country_lead'
        user.profile.save()
        assert user.is_staff  # country_lead 有 staff 权限访问 admin
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd src && pytest tests/test_account_models.py -v
```

Expected: FAIL

- [ ] **Step 3: 创建 src/apps/accounts/models.py**

```python
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('admin', '管理员'),
        ('country_lead', '国家负责人'),
        ('operator', '操作员'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='operator')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = '用户配置'
        verbose_name_plural = '用户配置'

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'

    def save(self, *args, **kwargs):
        if self.role in ('admin', 'country_lead'):
            self.user.is_staff = True
        else:
            self.user.is_staff = False
        self.user.save()
        super().save(*args, **kwargs)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
```

- [ ] **Step 4: 运行测试验证**

```bash
cd src && pytest tests/test_account_models.py -v
```

Expected: all PASS

- [ ] **Step 5: 创建 src/apps/accounts/admin.py**

```python
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = '角色配置'


class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ['username', 'email', 'get_role', 'is_active', 'date_joined']

    @admin.display(description='角色')
    def get_role(self, obj):
        return obj.profile.get_role_display() if hasattr(obj, 'profile') else '-'


# 替换默认 UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
```

- [ ] **Step 6: 创建迁移并提交**

```bash
cd src && python manage.py makemigrations accounts
python manage.py migrate
git add tests/ src/apps/accounts/
git commit -m "feat: add UserProfile with role system (admin/country_lead/operator)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: Prompt 模板系统

**Files:**
- Create: `ai/prompts/__init__.py`
- Create: `ai/prompts/loader.py`
- Create: `ai/prompts/image_variants.toml`
- Create: `ai/prompts/title_th.txt`
- Create: `ai/prompts/title_id.txt`

- [ ] **Step 1: 创建 Prompt 模板数据文件**

`ai/prompts/image_variants.toml`:
```toml
[default]
batch_size = 4
image_size = [1024, 1024]
steps = 30
cfg_scale = 7.0
denoising_strength = 0.65

[base_prompt]
template = "seamless pattern design, {style_tags}, {color_scheme}, t-shirt print, vector style, high quality, clean edges, isolated on transparent background"

[negative_prompt]
template = "photo, realistic, human, face, text, watermark, logo, blurry, low quality, distorted, messy edges"

[variants.color_shift]
label = "换色系"
style_tags = "{original_style}"
color_scheme = "{new_color_palette}"

[variants.style_transfer]
label = "风格迁移"
style_tags = "{new_style}"
color_scheme = "{original_colors}"

[variants.element_add]
label = "元素加减"
style_tags = "{original_style} with {new_elements}"
color_scheme = "{original_colors}"

[variants.composition_tweak]
label = "构图微调"
style_tags = "{original_style}"
color_scheme = "{original_colors}"
denoising_strength = 0.75
```

`ai/prompts/title_th.txt`:
```text
คุณคือผู้เชี่ยวชาญด้านการเขียนชื่อสินค้าสำหรับ TikTok Shop ภาษาไทย

สร้างชื่อสินค้าเสื้อยืดลายพิมพ์ที่ดึงดูดและกระชับ โดยอิงจากลักษณะลายพิมพ์ต่อไปนี้:

ลายพิมพ์: {print_description}
สีหลัก: {colors}
สไตล์: {style}

ข้อกำหนด:
- เขียนเป็นภาษาไทยเท่านั้น
- ความยาว 50-120 ตัวอักษร
- ใส่คำว่า "เสื้อยืด" หรือ "เสื้อทีเชิร์ต" ในชื่อ
- เน้นจุดขาย เช่น "ผ้านุ่ม", "พิมพ์คมชัด", "ลายไม่หลุด"
- ใส่สีของเสื้อ {shirt_color}

สร้างชื่อสินค้า 1 ชื่อ:
```

`ai/prompts/title_id.txt`:
```text
Anda adalah ahli penulisan judul produk untuk TikTok Shop dalam Bahasa Indonesia.

Buatlah judul produk kaos sablon yang menarik dan ringkas berdasarkan karakteristik sablon berikut:

Motif sablon: {print_description}
Warna utama: {colors}
Gaya: {style}

Persyaratan:
- Tulis dalam Bahasa Indonesia saja
- Panjang 50-120 karakter
- Sertakan kata "Kaos" atau "Baju Kaos" dalam judul
- Tonjolkan nilai jual seperti "bahan nyaman", "sablon berkualitas", "tidak luntur"
- Sertakan warna kaos {shirt_color}

Buat 1 judul produk:
```

- [ ] **Step 2: 创建 Prompt 加载工具**

`ai/prompts/loader.py`:
```python
"""Prompt 模板加载工具"""
from pathlib import Path
import tomllib

PROMPTS_DIR = Path(__file__).resolve().parent


def load_image_variants_config() -> dict:
    """加载印花变体配置"""
    config_path = PROMPTS_DIR / 'image_variants.toml'
    with open(config_path, 'rb') as f:
        return tomllib.load(f)


def load_text_prompt(language: str, template_name: str) -> str:
    """加载文本生成 Prompt 模板

    Args:
        language: 'th' (泰文) or 'id' (印尼文)
        template_name: 'title' or 'description'
    """
    filename = f'{template_name}_{language}.txt'
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f'Prompt template not found: {path}')
    return path.read_text(encoding='utf-8')


def build_image_prompt(
    variant_type: str,
    original_style: str,
    colors_or_style: str,
) -> tuple[str, str, dict]:
    """构建图像生成的 prompt

    Returns:
        (positive_prompt, negative_prompt, extra_params)
    """
    config = load_image_variants_config()
    base = config['base_prompt']['template']
    neg = config['negative_prompt']['template']
    variant_cfg = config['variants'].get(variant_type, config['variants']['style_transfer'])

    prompt = base.format(
        style_tags=variant_cfg.get('style_tags', original_style),
        color_scheme=colors_or_style,
    )

    extra_params = {
        'denoising_strength': variant_cfg.get('denoising_strength', 0.65)
    }

    return prompt, neg, extra_params


def build_text_prompt(
    language: str,
    print_description: str,
    colors: str = '',
    style: str = '',
    shirt_color: str = ' putih / hitam',
) -> str:
    """构建商品文本生成的 prompt

    Args:
        language: 'th' or 'id'
        print_description: 印花特征描述
        colors: 主色调
        style: 风格标签
        shirt_color: T恤颜色
    """
    template = load_text_prompt(language, 'title')
    return template.format(
        print_description=print_description,
        colors=colors,
        style=style,
        shirt_color=shirt_color,
    )
```

- [ ] **Step 3: 写 Prompt 加载测试**

Create `tests/test_prompt_loader.py`:
```python
from ai.prompts.loader import (
    load_image_variants_config,
    load_text_prompt,
    build_image_prompt,
    build_text_prompt,
)


class TestImagePrompt:
    def test_load_config(self):
        config = load_image_variants_config()
        assert 'base_prompt' in config
        assert 'variants' in config
        assert 'color_shift' in config['variants']

    def test_build_color_shift_prompt(self):
        pos, neg, params = build_image_prompt(
            'color_shift',
            original_style='floral vintage',
            colors_or_style='pastel pink and mint green',
        )
        assert 'floral vintage' in pos
        assert 'pastel pink' in pos
        assert 'photo' in neg
        assert 'denoising_strength' in params

    def test_build_style_transfer_prompt(self):
        pos, neg, params = build_image_prompt(
            'style_transfer',
            original_style='geometric tribal',
            colors_or_style='monochrome black and white',
        )
        assert 'monochrome' in pos
        assert len(params) > 0


class TestTextPrompt:
    def test_load_thai_title_template(self):
        tmpl = load_text_prompt('th', 'title')
        assert 'ภาษาไทย' in tmpl
        assert '{print_description}' in tmpl

    def test_load_indonesian_title_template(self):
        tmpl = load_text_prompt('id', 'title')
        assert 'Indonesia' in tmpl
        assert '{print_description}' in tmpl

    def test_build_thai_prompt(self):
        result = build_text_prompt(
            language='th',
            print_description='ดอกไม้เขตร้อนสีสันสดใส',
            colors='แดง, เขียว, เหลือง',
            style='tropical',
            shirt_color='ขาว',
        )
        assert 'ดอกไม้เขตร้อน' in result
        assert 'ขาว' in result

    def test_build_indonesian_prompt(self):
        result = build_text_prompt(
            language='id',
            print_description='motif bunga tropis warna cerah',
            colors='merah, hijau, kuning',
            style='tropical',
            shirt_color='putih',
        )
        assert 'bunga tropis' in result
        assert 'putih' in result

    def test_missing_template_raises_error(self):
        import pytest
        with pytest.raises(FileNotFoundError):
            load_text_prompt('xx', 'title')
```

- [ ] **Step 4: 运行测试确认失败/通过（prompt 文件不存在前会失败）**

```bash
cd src && PYTHONPATH=.. pytest ../tests/test_prompt_loader.py -v
```

Expected: some tests pass (config), text tests FAIL (files not exist yet — wait, they were created in Step 1)

Actually, we just need to make sure the PYTHONPATH is set correctly.

- [ ] **Step 5: 运行测试验证通过**

```bash
cd src && PYTHONPATH=.. pytest ../tests/test_prompt_loader.py -v
```

Expected: all PASS

- [ ] **Step 6: 提交**

```bash
git add ai/ tests/test_prompt_loader.py
git commit -m "feat: add prompt template system with Thai and Indonesian support

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: AI Provider 抽象接口

**Files:**
- Create: `src/apps/generation/__init__.py`
- Create: `src/apps/generation/provider.py`

- [ ] **Step 1: 写 AIProvider 接口测试**

Create `tests/test_ai_provider.py`:
```python
import pytest
from dataclasses import dataclass
from PIL import Image
from apps.generation.provider import (
    AIProvider, ImageResult, AnalysisResult, TextResult
)


class TestProviderInterface:
    def test_provider_is_abstract(self):
        provider = AIProvider()
        with pytest.raises(NotImplementedError):
            provider.generate_image('prompt', None, {})

        with pytest.raises(NotImplementedError):
            provider.analyze_image(None)

        with pytest.raises(NotImplementedError):
            provider.generate_text('prompt', 'th')

    def test_image_result_dataclass(self):
        img = Image.new('RGB', (64, 64), color='red')
        result = ImageResult(images=[img], metadata={'seed': 12345})
        assert len(result.images) == 1
        assert result.metadata['seed'] == 12345

    def test_analysis_result_dataclass(self):
        result = AnalysisResult(
            tags=['floral', 'vintage'],
            colors=['#FF6B6B', '#4ECDC4'],
            description='A vintage floral pattern'
        )
        assert 'floral' in result.tags
        assert len(result.colors) == 2

    def test_text_result_dataclass(self):
        result = TextResult(
            title='Kaos Motif Bunga Tropis',
            description='Kaos katun nyaman dengan motif bunga tropis',
            size_info='S, M, L, XL'
        )
        assert 'Kaos' in result.title
        assert 'XL' in result.size_info
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd src && pytest tests/test_ai_provider.py -v
```

Expected: FAIL

- [ ] **Step 3: 创建 src/apps/generation/provider.py**

```python
"""AI 提供商抽象接口"""
from dataclasses import dataclass, field
from typing import Any
from PIL.Image import Image


@dataclass
class ImageResult:
    """图像生成结果"""
    images: list  # list of PIL.Image
    metadata: dict = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """图像分析结果"""
    tags: list[str] = field(default_factory=list)
    colors: list[str] = field(default_factory=list)
    description: str = ''


@dataclass
class TextResult:
    """文本生成结果"""
    title: str = ''
    description: str = ''
    size_info: str = ''


class AIProvider:
    """AI 提供商抽象基类"""

    def generate_image(self, prompt: str, reference_image: Image | None = None,
                       params: dict | None = None) -> ImageResult:
        """生成图像

        Args:
            prompt: 正向 prompt
            reference_image: 参考图（img2img 模式）
            params: 额外参数（steps, cfg_scale, denoising_strength 等）

        Returns:
            ImageResult 包含生成的图片列表
        """
        raise NotImplementedError

    def analyze_image(self, image: Image) -> AnalysisResult:
        """分析图像内容

        Args:
            image: 待分析的图片

        Returns:
            AnalysisResult 包含标签、主色调、描述
        """
        raise NotImplementedError

    def generate_text(self, prompt: str, language: str = 'id') -> TextResult:
        """生成商品文本

        Args:
            prompt: 完整的文本生成 prompt
            language: 目标语言 ('th' or 'id')

        Returns:
            TextResult 包含标题、描述、尺码
        """
        raise NotImplementedError
```

- [ ] **Step 4: 运行测试验证**

```bash
cd src && pytest tests/test_ai_provider.py -v
```

Expected: all PASS

- [ ] **Step 5: 提交**

```bash
git add tests/ src/apps/generation/
git commit -m "feat: add AIProvider abstract interface with result dataclasses

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 10: ComfyUI Provider 实现

**Files:**
- Create: `src/apps/generation/comfyui.py`

- [ ] **Step 1: 创建 ComfyUI Provider**

`src/apps/generation/comfyui.py`:
```python
"""ComfyUI 图像生成提供商"""
import json
import time
import httpx
from io import BytesIO
from typing import Any
from PIL import Image
from django.conf import settings
from .provider import AIProvider, ImageResult


class ComfyUIProvider(AIProvider):
    """ComfyUI HTTP API 封装"""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.COMFYUI_BASE_URL
        self.client = httpx.Client(timeout=120.0)

    def generate_image(
        self,
        prompt: str,
        reference_image: Image | None = None,
        params: dict | None = None,
    ) -> ImageResult:
        """通过 ComfyUI 生成印花图

        使用 txt2img 或 img2img 工作流
        """
        params = params or {}
        workflow = self._build_workflow(prompt, reference_image, params)
        prompt_id = self._queue_prompt(workflow)
        images_data = self._wait_for_result(prompt_id)

        generated = [Image.open(BytesIO(data)) for data in images_data]
        return ImageResult(
            images=generated,
            metadata={'prompt_id': prompt_id, 'node_id': 'output'}
        )

    def _build_workflow(
        self, prompt: str, reference_image: Image | None, params: dict
    ) -> dict:
        """构建 ComfyUI API 工作流 JSON

        加载基础工作流文件，动态替换 prompt 节点
        """
        import json
        from pathlib import Path

        workflow_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / 'ai' / 'comfy_workflows' / 'print_variation.json'
        )

        if workflow_path.exists():
            with open(workflow_path) as f:
                workflow = json.load(f)
        else:
            # 回退：使用简单的工作流模板
            workflow = self._default_workflow()

        # 遍历找到 CLIP Text Encode 节点并替换 prompt
        for node_id, node in workflow.items():
            if node.get('class_type') == 'CLIPTextEncode':
                if node.get('_meta', {}).get('title') == 'Positive Prompt':
                    node['inputs']['text'] = prompt
            if node.get('class_type') == 'KSampler':
                node['inputs']['steps'] = params.get('steps', 30)
                node['inputs']['cfg'] = params.get('cfg_scale', 7.0)
                if 'denoising' in params:
                    node['inputs']['denoise'] = params['denoising']

        return workflow

    def _default_workflow(self) -> dict:
        """构建默认的 SDXL txt2img 工作流（不含参考图时使用）"""
        return {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": ""}, "_meta": {"title": "Positive Prompt"}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": ""}, "_meta": {"title": "Negative Prompt"}},
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 4}},
            "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "seed": 0, "steps": 30, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
            "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "print_variant", "images": ["6", 0]}},
        }

    def _queue_prompt(self, workflow: dict) -> str:
        """提交工作流到 ComfyUI 队列，返回 prompt_id"""
        resp = self.client.post(f'{self.base_url}/prompt', json={'prompt': workflow})
        resp.raise_for_status()
        return resp.json()['prompt_id']

    def _wait_for_result(self, prompt_id: str, poll_interval: float = 2.0,
                         max_wait: float = 300.0) -> list[bytes]:
        """轮询等待 ComfyUI 生成完成，返回图片数据列表"""
        elapsed = 0.0
        while elapsed < max_wait:
            time.sleep(poll_interval)
            elapsed += poll_interval

            try:
                resp = self.client.get(f'{self.base_url}/history/{prompt_id}')
                resp.raise_for_status()
                data = resp.json()
                if prompt_id in data:
                    history = data[prompt_id]
                    # 提取 SaveImage 节点的输出
                    images = []
                    for node_id, node_output in history.get('outputs', {}).items():
                        for img_info in node_output.get('images', []):
                            img_resp = self.client.get(
                                f'{self.base_url}/view',
                                params={
                                    'filename': img_info['filename'],
                                    'subfolder': img_info.get('subfolder', ''),
                                    'type': img_info.get('type', 'output'),
                                }
                            )
                            img_resp.raise_for_status()
                            images.append(img_resp.content)
                    if images:
                        return images
            except httpx.HTTPError:
                continue

        raise TimeoutError(f'ComfyUI generation timed out after {max_wait}s')

    def analyze_image(self, image: Image) -> Any:
        """ComfyUI 不直接提供图像分析，留空"""
        raise NotImplementedError('ComfyUI does not support image analysis')

    def generate_text(self, prompt: str, language: str = 'id') -> Any:
        """ComfyUI 不提供文本生成"""
        raise NotImplementedError('ComfyUI does not support text generation')
```

- [ ] **Step 2: 创建一个简单的 ComfyUI 工作流 JSON**

`ai/comfy_workflows/print_variation.json`:
```json
{
  "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
  "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": ""}, "_meta": {"title": "Positive Prompt"}},
  "3": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": ""}, "_meta": {"title": "Negative Prompt"}},
  "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 4}},
  "5": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0], "seed": 0, "steps": 30, "cfg": 7.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}},
  "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
  "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "print_variant", "images": ["6", 0]}}
}
```

- [ ] **Step 3: 提交**

```bash
git add src/apps/generation/comfyui.py ai/comfy_workflows/
git commit -m "feat: add ComfyUI HTTP API provider for image generation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 11: Ollama Provider 实现

**Files:**
- Create: `src/apps/generation/ollama.py`

- [ ] **Step 1: 创建 Ollama Provider**

`src/apps/generation/ollama.py`:
```python
"""Ollama 文本生成提供商"""
import json
import httpx
from django.conf import settings
from .provider import AIProvider, AnalysisResult, TextResult


class OllamaProvider(AIProvider):
    """Ollama HTTP API 封装"""

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        self.client = httpx.Client(timeout=120.0)

    def generate_image(self, *args, **kwargs):
        raise NotImplementedError('Ollama does not support image generation')

    def analyze_image(self, image) -> AnalysisResult:
        """使用 Ollama vision model 分析印花图"""
        import base64
        from io import BytesIO

        buffered = BytesIO()
        image.save(buffered, format='PNG')
        img_base64 = base64.b64encode(buffered.getvalue()).decode()

        analysis_prompt = """Analyze this print/t-shirt design image. Return a JSON object with:
{
  "tags": ["style1", "style2", ...],        // 3-5 style keywords (e.g., floral, geometric, cartoon, vintage, tribal)
  "colors": ["#HEX1", "#HEX2", "#HEX3"],    // 3 main colors as HEX codes
  "description": "A concise description in English of the print pattern"
}
Only return the JSON, no other text."""

        resp = self.client.post(f'{self.base_url}/api/generate', json={
            'model': self.model,
            'prompt': analysis_prompt,
            'images': [img_base64],
            'stream': False,
        })
        resp.raise_for_status()

        result = resp.json()
        # Parse the JSON from the model response
        try:
            text = result['response'].strip()
            # Handle markdown code blocks
            if text.startswith('```'):
                text = text.split('\n', 1)[1]
                if text.endswith('```'):
                    text = text[:-3]
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {'tags': [], 'colors': [], 'description': result['response']}

        return AnalysisResult(
            tags=data.get('tags', []),
            colors=data.get('colors', []),
            description=data.get('description', ''),
        )

    def generate_text(self, prompt: str, language: str = 'id') -> TextResult:
        """使用 Ollama 生成商品标题和描述"""
        resp = self.client.post(f'{self.base_url}/api/generate', json={
            'model': self.model,
            'prompt': prompt,
            'stream': False,
        })
        resp.raise_for_status()

        result = resp.json()
        generated_text = result['response'].strip()

        # 解析生成的文本：第一行是标题，后续是描述
        lines = [line.strip() for line in generated_text.split('\n') if line.strip()]
        title = lines[0] if lines else ''
        description = '\n'.join(lines[1:]) if len(lines) > 1 else ''

        # 默认尺码
        size_info = 'S, M, L, XL, XXL'

        return TextResult(
            title=title,
            description=description,
            size_info=size_info,
        )
```

- [ ] **Step 2: 提交**

```bash
git add src/apps/generation/ollama.py
git commit -m "feat: add Ollama provider for image analysis and text generation

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 12: 变体策略生成

**Files:**
- Create: `src/apps/generation/variants.py`

- [ ] **Step 1: 创建变体策略模块**

`src/apps/generation/variants.py`:
```python
"""印花变体策略 — 决定每张原图生成哪些变体"""

VARIANT_DIRECTIONS = [
    {
        'key': 'color_shift',
        'label': '换色系',
        'config_key': 'color_shift',
    },
    {
        'key': 'style_transfer',
        'label': '风格迁移',
        'config_key': 'style_transfer',
    },
    {
        'key': 'element_add',
        'label': '元素加减',
        'config_key': 'element_add',
    },
    {
        'key': 'composition_tweak',
        'label': '构图微调',
        'config_key': 'composition_tweak',
    },
]

ALTERNATE_COLORS = [
    'warm sunset orange and pink',
    'cool ocean blue and teal',
    'earthy brown and olive green',
    'pastel pink and lavender',
    'bold red and navy',
    'monochrome black and gray',
    'bright yellow and coral',
    'forest green and cream',
]

ALTERNATE_STYLES = [
    'watercolor painting style',
    'minimalist line art',
    'vintage retro 90s',
    'Japanese ukiyo-e style',
    'streetwear graffiti style',
    'bohemian ethnic pattern',
    'Scandinavian modern simple',
    'pop art bold comic style',
]

ELEMENT_ADDITIONS = [
    'tropical leaves',
    'small flowers',
    'geometric shapes',
    'stars and sparkles',
    'butterflies',
    'abstract waves',
    'palm trees',
    'celestial moon and sun',
]


def get_variant_directions(max_variants: int = 4) -> list[dict]:
    """返回本次生成要执行的变体方向列表"""
    import random
    if max_variants >= len(VARIANT_DIRECTIONS):
        return VARIANT_DIRECTIONS
    return random.sample(VARIANT_DIRECTIONS, max_variants)


def apply_variant(direction: dict, analysis: 'AnalysisResult') -> tuple[str, str]:
    """根据分析结果，为某个变体方向生成具体的 prompt 参数

    Returns:
        (variant_prompt_param, color_or_style_value)
    """
    import random

    key = direction['key']

    if key == 'color_shift':
        new_colors = random.choice(ALTERNATE_COLORS)
        return ', '.join(analysis.tags), new_colors

    elif key == 'style_transfer':
        new_style = random.choice(ALTERNATE_STYLES)
        return new_style, ', '.join(analysis.colors) if analysis.colors else 'original'

    elif key == 'element_add':
        addition = random.choice(ELEMENT_ADDITIONS)
        combined = ', '.join(analysis.tags) if analysis.tags else ''
        return f'{combined} with {addition}', ', '.join(analysis.colors) if analysis.colors else 'vibrant'

    elif key == 'composition_tweak':
        return ', '.join(analysis.tags) if analysis.tags else '', ', '.join(analysis.colors) if analysis.colors else 'original'

    return '', ''
```

- [ ] **Step 2: 写变体策略测试**

Create `tests/test_variants.py`:
```python
from apps.generation.variants import (
    VARIANT_DIRECTIONS,
    get_variant_directions,
    apply_variant,
)


class TestVariantDirections:
    def test_has_four_default_directions(self):
        assert len(VARIANT_DIRECTIONS) == 4
        keys = [d['key'] for d in VARIANT_DIRECTIONS]
        assert 'color_shift' in keys
        assert 'style_transfer' in keys
        assert 'element_add' in keys
        assert 'composition_tweak' in keys

    def test_get_all_directions(self):
        directions = get_variant_directions(max_variants=4)
        assert len(directions) == 4

    def test_get_limited_directions(self):
        directions = get_variant_directions(max_variants=2)
        assert len(directions) == 2

    def test_color_shift_variant(self):
        from apps.generation.provider import AnalysisResult
        analysis = AnalysisResult(
            tags=['floral', 'vintage'],
            colors=['#FF6B6B', '#4ECDC4'],
            description='A vintage floral pattern'
        )
        from apps.generation.variants import ALTERNATE_COLORS
        direction = {'key': 'color_shift', 'label': '换色系', 'config_key': 'color_shift'}
        style_param, color_param = apply_variant(direction, analysis)
        assert 'floral' in style_param
        assert color_param in ALTERNATE_COLORS

    def test_style_transfer_variant(self):
        from apps.generation.provider import AnalysisResult
        analysis = AnalysisResult(
            tags=['geometric', 'modern'],
            colors=['#000000'],
            description=''
        )
        from apps.generation.variants import ALTERNATE_STYLES
        direction = {'key': 'style_transfer', 'label': '风格迁移', 'config_key': 'style_transfer'}
        style_param, color_param = apply_variant(direction, analysis)
        assert style_param in ALTERNATE_STYLES
        assert '#000000' in color_param

    def test_element_add_variant(self):
        from apps.generation.provider import AnalysisResult
        analysis = AnalysisResult(
            tags=['minimalist'],
            colors=['#FFFFFF', '#333333'],
            description=''
        )
        from apps.generation.variants import ELEMENT_ADDITIONS
        direction = {'key': 'element_add', 'label': '元素加减', 'config_key': 'element_add'}
        style_param, color_param = apply_variant(direction, analysis)
        assert 'with' in style_param
        assert any(elem in style_param for elem in ELEMENT_ADDITIONS)
```

- [ ] **Step 3: 运行测试验证**

```bash
cd src && pytest tests/test_variants.py -v
```

Expected: all PASS

- [ ] **Step 4: 提交**

```bash
git add tests/ src/apps/generation/variants.py
git commit -m "feat: add print variant strategies (color shift, style transfer, etc)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 13: Celery 预处理任务 — 抠图

**Files:**
- Create: `src/celery_app/__init__.py`
- Create: `src/celery_app/preprocessing.py`

- [ ] **Step 1: 创建预处理任务**

`src/celery_app/__init__.py`:
```python
```

`src/celery_app/preprocessing.py`:
```python
"""印花预处理任务：抠图 + 去背景"""
import io
import logging
from PIL import Image
from celery import shared_task
from rembg import remove

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def remove_background_task(self, pattern_id: int) -> dict:
    """对 Pattern 的原始图进行抠图处理

    Args:
        pattern_id: Pattern 模型 ID

    Returns:
        {'success': bool, 'pattern_id': int, 'error': str|None}
    """
    from apps.patterns.models import Pattern

    try:
        pattern = Pattern.objects.get(id=pattern_id)
    except Pattern.DoesNotExist:
        return {'success': False, 'pattern_id': pattern_id, 'error': 'Pattern not found'}

    if not pattern.image:
        return {'success': False, 'pattern_id': pattern_id, 'error': 'No image file'}

    try:
        # 读取原图
        input_data = pattern.image.read()
        input_image = Image.open(io.BytesIO(input_data)).convert('RGBA')

        # rembg 抠图
        output_image = remove(input_image)

        # 保存处理后的图片到原 Pattern 的 image 字段
        output_buffer = io.BytesIO()
        output_image.save(output_buffer, format='PNG')
        output_buffer.seek(0)

        # 用 Django File 对象更新
        from django.core.files.base import ContentFile
        filename = f'pattern_{pattern_id}_nobg.png'
        pattern.image.save(filename, ContentFile(output_buffer.getvalue()), save=True)

        # 更新来源类型为干净印花
        pattern.source_type = 'clean_print'
        pattern.save(update_fields=['source_type'])

        logger.info(f'Pattern #{pattern_id} background removed successfully')
        return {'success': True, 'pattern_id': pattern_id, 'error': None}

    except Exception as exc:
        logger.error(f'Failed to remove background for Pattern #{pattern_id}: {exc}')
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {'success': False, 'pattern_id': pattern_id, 'error': str(exc)}
```

- [ ] **Step 2: 提交**

```bash
git add src/celery_app/
git commit -m "feat: add Celery preprocessing task for background removal

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 14: Celery 图像生成任务

**Files:**
- Create: `src/celery_app/image_gen.py`

- [ ] **Step 1: 创建图像生成任务**

`src/celery_app/image_gen.py`:
```python
"""印花图像生成 Celery 任务"""
import io
import logging
from PIL import Image
from celery import shared_task
from django.core.files.base import ContentFile

from apps.generation.comfyui import ComfyUIProvider
from apps.generation.provider import AnalysisResult
from apps.generation.variants import get_variant_directions, apply_variant
from ai.prompts.loader import build_image_prompt

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def generate_print_variants_task(self, pattern_id: int, product_id: int,
                                 variant_count: int = 4,
                                 negative_prompt: str = '') -> dict:
    """为指定印花生成变体

    Args:
        pattern_id: Pattern ID
        product_id: 目标 Product ID（一个 product = 一个变体方向 + 一个图案）
        variant_count: 生成方向数量

    Returns:
        {'success': bool, 'product_id': int, 'variants_generated': int, 'error': str|None}
    """
    from apps.patterns.models import Pattern
    from apps.products.models import Product, GenerationLog
    import time

    try:
        pattern = Pattern.objects.get(id=pattern_id)
        product = Product.objects.get(id=product_id)
    except (Pattern.DoesNotExist, Product.DoesNotExist):
        return {'success': False, 'product_id': product_id, 'error': 'Pattern or Product not found'}

    try:
        # 读取印花原图
        pattern_data = pattern.image.read()
        reference = Image.open(io.BytesIO(pattern_data)).convert('RGB')

        # 获取分析结果（标签 + 颜色 + 描述）
        analysis_tags = []
        # 从 product 关联的 GenerationLog 中获取之前分析的结果
        prev_log = GenerationLog.objects.filter(
            product__pattern=pattern, step='text_gen'
        ).order_by('-created_at').first()

        # AI 图像生成
        provider = ComfyUIProvider()
        directions = get_variant_directions(max_variants=variant_count)

        generated_count = 0
        t0 = time.time()

        for direction in directions:
            # 从分析结果构建变体参数
            analysis = AnalysisResult(
                tags=analysis_tags or ['print', 'design'],
                colors=[], description=''
            )
            style_param, color_param = apply_variant(direction, analysis)

            # 构建 prompt
            pos_prompt, neg_prompt, params = build_image_prompt(
                direction['config_key'],
                original_style=style_param,
                colors_or_style=color_param,
            )
            neg_prompt = negative_prompt or neg_prompt

            try:
                result = provider.generate_image(
                    prompt=pos_prompt,
                    reference_image=reference if direction['key'] != 'composition_tweak' else None,
                    params=params,
                )
            except Exception as e:
                logger.error(f'ComfyUI generation failed for direction {direction["key"]}: {e}')
                continue

            # 保存生成的印花图到 Product
            for i, img in enumerate(result.images):
                buf = io.BytesIO()
                img.save(buf, format='PNG')
                buf.seek(0)

                product.print_image.save(
                    f'product_{product_id}_{direction["key"]}_{i}.png',
                    ContentFile(buf.getvalue()),
                    save=True,
                )
                generated_count += 1
                break  # 每个方向只取第一张

            # 记录生成日志
            duration = int((time.time() - t0) * 1000)
            GenerationLog.objects.create(
                product=product,
                step='image_gen',
                model_used='sdxl',
                params={
                    'variant': direction['key'],
                    'prompt': pos_prompt,
                    'cfg_scale': params.get('cfg_scale', 7.0),
                    'steps': params.get('steps', 30),
                },
                duration_ms=duration,
            )

        product.status = 'text_pending' if generated_count > 0 else 'failed'
        product.save(update_fields=['status'])

        return {
            'success': generated_count > 0,
            'product_id': product_id,
            'variants_generated': generated_count,
            'error': None if generated_count > 0 else 'No variants were generated',
        }

    except Exception as exc:
        logger.error(f'Image generation failed for Product #{product_id}: {exc}')
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            Product.objects.filter(id=product_id).update(status='failed', error_message=str(exc))
            return {'success': False, 'product_id': product_id, 'error': str(exc)}
```

- [ ] **Step 2: 提交**

```bash
git add src/celery_app/image_gen.py
git commit -m "feat: add Celery task for AI print variant generation via ComfyUI

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 15: Celery 文本生成任务

**Files:**
- Create: `src/celery_app/text_gen.py`

- [ ] **Step 1: 创建文本生成任务**

`src/celery_app/text_gen.py`:
```python
"""商品文本生成 Celery 任务"""
import logging
import time
from celery import shared_task
from apps.generation.ollama import OllamaProvider
from ai.prompts.loader import build_text_prompt

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def generate_product_text_task(self, product_id: int) -> dict:
    """为 Product 生成标题、描述、尺码

    Args:
        product_id: Product ID

    Returns:
        {'success': bool, 'product_id': int, 'title': str, 'error': str|None}
    """
    from apps.products.models import Product, GenerationLog

    try:
        product = Product.objects.select_related('country').get(id=product_id)
    except Product.DoesNotExist:
        return {'success': False, 'product_id': product_id, 'error': 'Product not found'}

    try:
        # 确定语言
        language_map = {'ID': 'id', 'TH': 'th'}
        language = language_map.get(product.country.code, 'id')

        # 图像分析 + 文本生成
        provider = OllamaProvider()

        # 分析印花图
        analysis_desc = 'stylish print design'
        if product.print_image:
            try:
                from PIL import Image
                import io
                data = product.print_image.read()
                img = Image.open(io.BytesIO(data))
                analysis = provider.analyze_image(img)
                analysis_desc = analysis.description or analysis_desc
            except Exception as e:
                logger.warning(f'Image analysis failed for Product #{product_id}: {e}')

        # 构建文本 prompt
        prompt = build_text_prompt(
            language=language,
            print_description=analysis_desc,
            colors='',
            style='',
            shirt_color='white/black',
        )

        # 调用 Ollama
        t0 = time.time()
        result = provider.generate_text(prompt, language=language)
        duration = int((time.time() - t0) * 1000)

        # 更新 Product
        product.title = result.title
        product.description = result.description
        product.size_info = result.size_info
        product.status = 'completed'
        product.save()

        # 记录日志
        GenerationLog.objects.create(
            product=product,
            step='text_gen',
            model_used=provider.model,
            params={'language': language},
            duration_ms=duration,
        )

        logger.info(f'Text generated for Product #{product_id}: {result.title[:50]}')
        return {
            'success': True,
            'product_id': product_id,
            'title': result.title,
            'error': None,
        }

    except Exception as exc:
        logger.error(f'Text generation failed for Product #{product_id}: {exc}')
        try:
            self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            Product.objects.filter(id=product_id).update(
                status='text_pending',
                error_message=str(exc)
            )
            return {'success': False, 'product_id': product_id, 'error': str(exc)}
```

- [ ] **Step 2: 提交**

```bash
git add src/celery_app/text_gen.py
git commit -m "feat: add Celery task for product text generation via Ollama

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 16: 完整流水线编排

**Files:**
- Create: `src/celery_app/pipeline.py`

- [ ] **Step 1: 创建流水线编排任务**

`src/celery_app/pipeline.py`:
```python
"""AI 生成完整流水线编排 — 从上传到产品生成全流程"""
import logging
from celery import chain, group, shared_task

from .preprocessing import remove_background_task
from .image_gen import generate_print_variants_task
from .text_gen import generate_product_text_task

logger = logging.getLogger(__name__)


@shared_task
def run_generation_pipeline(pattern_id: int, product_ids: list[int],
                            skip_preprocess: bool = False,
                            variant_count: int = 4) -> dict:
    """运行完整的生成流水线

    Args:
        pattern_id: 原始印花 ID
        product_ids: 目标 Product ID 列表（已预先创建）
        skip_preprocess: 是否跳过抠图（干净印花）
        variant_count: 每张原图生成多少个变体方向

    Returns:
        {'success': bool, 'pattern_id': int, 'products_processed': int, 'error': str|None}
    """
    from apps.patterns.models import Pattern
    from apps.products.models import Product

    try:
        pattern = Pattern.objects.get(id=pattern_id)
    except Pattern.DoesNotExist:
        return {'success': False, 'pattern_id': pattern_id, 'error': 'Pattern not found'}

    # 更新状态
    Product.objects.filter(id__in=product_ids).update(status='processing')

    # 构建任务链
    tasks = []

    # Step 1: 预处理（如需要）
    if not skip_preprocess and pattern.source_type != 'clean_print':
        preprocess_sig = remove_background_task.si(pattern_id)
        tasks.append(preprocess_sig)

    # Step 2: 为每个 Product 生成印花图（并行）
    image_tasks = [
        generate_print_variants_task.si(
            pattern_id=pattern_id,
            product_id=pid,
            variant_count=variant_count,
        )
        for pid in product_ids
    ]
    if image_tasks:
        tasks.append(group(image_tasks))

    # Step 3: 为每个 Product 生成文本（并行）
    text_tasks = [
        generate_product_text_task.si(product_id=pid)
        for pid in product_ids
    ]
    if text_tasks:
        tasks.append(group(text_tasks))

    # 串行执行
    if tasks:
        workflow = chain(*tasks)
        workflow.apply_async()

    return {
        'success': True,
        'pattern_id': pattern_id,
        'products_processed': len(product_ids),
        'error': None,
    }


@shared_task
def batch_upload_pipeline(pattern_ids: list[int], country_code: str,
                          template_id: int, variant_count: int = 4) -> dict:
    """批量上传入口：为一批印花创建产品并启动生成流水线

    Args:
        pattern_ids: Pattern ID 列表
        country_code: 目标国家代码（ID / TH）
        template_id: TShirtTemplate ID
        variant_count: 变体方向数量

    Returns:
        {'success': bool, 'products_created': int, 'error': str|None}
    """
    from apps.core.models import Country
    from apps.products.models import Product
    from apps.patterns.models import Pattern
    from apps.templates_app.models import TShirtTemplate

    try:
        country = Country.objects.get(code=country_code)
        template = TShirtTemplate.objects.get(id=template_id)
    except (Country.DoesNotExist, TShirtTemplate.DoesNotExist):
        return {'success': False, 'products_created': 0, 'error': 'Country or Template not found'}

    products_created = 0

    for pid in pattern_ids:
        try:
            pattern = Pattern.objects.get(id=pid)
        except Pattern.DoesNotExist:
            continue

        # 为这个方向创建 Product
        product = Product.objects.create(
            country=country,
            pattern=pattern,
            template=template,
            status='pending',
        )

        # 启动流水线
        run_generation_pipeline.delay(
            pattern_id=pid,
            product_ids=[product.id],
            skip_preprocess=(pattern.source_type == 'clean_print'),
            variant_count=variant_count,
        )
        products_created += 1

    return {
        'success': products_created > 0,
        'products_created': products_created,
        'error': None if products_created > 0 else 'No valid patterns found',
    }
```

- [ ] **Step 2: 提交**

```bash
git add src/celery_app/pipeline.py
git commit -m "feat: add generation pipeline orchestration with batch upload support

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 17: 产品导出服务

**Files:**
- Create: `src/apps/export_app/services.py`
- Create: `src/apps/export_app/admin.py`

- [ ] **Step 1: 创建导出服务**

`src/apps/export_app/services.py`:
```python
"""产品导出 — CSV + 图片包"""
import csv
import io
import zipfile
from django.http import HttpResponse
from apps.products.models import Product


def export_products_csv(product_ids: list[int]) -> str:
    """导出产品信息为 CSV 字符串"""
    products = Product.objects.filter(id__in=product_ids).select_related('country')

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Product ID', 'Title', 'Description', 'Size', 'Country',
                      'Print Image URL', 'Mockup URL', 'Status', 'Created At'])

    for p in products:
        writer.writerow([
            p.id,
            p.title,
            p.description,
            p.size_info,
            p.country.name,
            p.print_image.url if p.print_image else '',
            p.mockup_image.url if p.mockup_image else '',
            p.get_status_display(),
            p.created_at.strftime('%Y-%m-%d %H:%M'),
        ])

    return output.getvalue()


def export_products_zip(product_ids: list[int]) -> bytes:
    """导出产品 CSV + 所有图片为 ZIP 文件"""
    products = Product.objects.filter(id__in=product_ids).select_related('country')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # CSV
        csv_content = export_products_csv(product_ids)
        zf.writestr('products.csv', csv_content)

        # 图片
        for p in products:
            if p.print_image:
                try:
                    zf.writestr(f'images/{p.id}_print.png', p.print_image.read())
                except Exception:
                    pass
            if p.mockup_image:
                try:
                    zf.writestr(f'images/{p.id}_mockup.png', p.mockup_image.read())
                except Exception:
                    pass

    buf.seek(0)
    return buf.getvalue()


def build_export_response(product_ids: list[int], filename: str = 'export') -> HttpResponse:
    """构建 Django HTTP 响应，下载 ZIP"""
    zip_data = export_products_zip(product_ids)
    response = HttpResponse(zip_data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{filename}.zip"'
    return response
```

- [ ] **Step 2: 创建导出 Admin Action**

`src/apps/export_app/admin.py`:
```python
from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from apps.products.models import Product
from .services import build_export_response


def export_as_zip(modeladmin, request, queryset):
    """Admin action: 导出选中产品为 ZIP"""
    ids = list(queryset.values_list('id', flat=True))
    if not ids:
        messages.error(request, '请先选择要导出的产品')
        return HttpResponseRedirect(request.get_full_path())

    # 按国家分组
    products = Product.objects.filter(id__in=ids).select_related('country')
    countries = set(p.country.code for p in products)

    if len(countries) == 1:
        country_code = countries.pop()
        return build_export_response(ids, filename=f'tkerp_export_{country_code}')
    else:
        return build_export_response(ids, filename='tkerp_export_all')


export_as_zip.short_description = '导出选中的产品（ZIP：CSV+图片）'


def export_as_csv(modeladmin, request, queryset):
    """Admin action: 导出选中产品为 CSV"""
    from .services import export_products_csv
    from django.http import HttpResponse

    ids = list(queryset.values_list('id', flat=True))
    if not ids:
        messages.error(request, '请先选择要导出的产品')
        return HttpResponseRedirect(request.get_full_path())

    csv_content = export_products_csv(ids)
    response = HttpResponse(csv_content, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="tkerp_export.csv"'
    return response


export_as_csv.short_description = '导出选中的产品（CSV）'


# 注意：需要手动在 apps/products/admin.py 的 ProductAdmin 中添加：
#   actions = [export_as_zip, export_as_csv]
# 并在 products/admin.py 顶部添加：
#   from apps.export_app.admin import export_as_zip, export_as_csv
```

- [ ] **Step 3: 写导出服务测试**

Create `tests/test_export.py`:
```python
import pytest
import csv
import io
from django.contrib.auth import get_user_model
from apps.core.models import Country
from apps.patterns.models import Pattern
from apps.templates_app.models import TShirtTemplate
from apps.products.models import Product
from apps.export_app.services import export_products_csv, export_products_zip

User = get_user_model()


@pytest.mark.django_db
class TestExport:
    def setup_method(self):
        self.user = User.objects.create_user(username='test', password='test')
        self.country = Country.objects.create(code='ID', name='Indonesia')
        self.pattern = Pattern.objects.create(uploaded_by=self.user)
        self.template = TShirtTemplate.objects.create(name='White', color='white')
        self.p1 = Product.objects.create(
            country=self.country, pattern=self.pattern, template=self.template,
            title='Kaos Test 1', description='Desc 1', size_info='S,M,L',
            status='completed'
        )
        self.p2 = Product.objects.create(
            country=self.country, pattern=self.pattern, template=self.template,
            title='Kaos Test 2', description='Desc 2', size_info='M,L,XL',
            status='completed'
        )

    def test_export_csv_has_header(self):
        csv_str = export_products_csv([self.p1.id, self.p2.id])
        reader = csv.reader(io.StringIO(csv_str))
        header = next(reader)
        assert 'Product ID' in header
        assert 'Title' in header

    def test_export_csv_content(self):
        csv_str = export_products_csv([self.p1.id])
        assert 'Kaos Test 1' in csv_str
        assert 'Desc 1' in csv_str
        assert 'S,M,L' in csv_str

    def test_export_zip(self):
        data = export_products_zip([self.p1.id])
        assert len(data) > 0
        assert data[:2] == b'PK'  # ZIP magic bytes

    def test_export_empty_list(self):
        csv_str = export_products_csv([])
        lines = csv_str.strip().split('\n')
        assert len(lines) == 1  # only header
```

- [ ] **Step 4: 运行测试验证**

```bash
cd src && pytest tests/test_export.py -v
```

Expected: all PASS

- [ ] **Step 5: 提交**

```bash
git add tests/ src/apps/export_app/
git commit -m "feat: add product export services (CSV and ZIP with images)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 18: 最后提交 — README 和 .env.example 完善

**Files:**
- Create: `README.md`

- [ ] **Step 1: 创建 README.md**

```markdown
# TK-ERP — TikTok 东南亚印花T恤 AI生成系统

利用 AI 将印花T恤设计裂变生成新印花，并自动生成商品信息（泰文/印尼文），服务于 TikTok Shop 东南亚运营。

## 技术栈

- **Backend:** Django 4.2
- **任务队列:** Celery + Redis
- **数据库:** PostgreSQL 15
- **图片存储:** MinIO (S3兼容)
- **AI 图像:** ComfyUI (SDXL on RTX 5070)
- **AI 文本:** Ollama (Qwen2.5/Llama4)
- **部署:** Docker Compose

## 快速启动

### 前置条件

- Docker & Docker Compose
- NVIDIA GPU + Docker GPU runtime (用于 AI 推理)
- 已安装 ComfyUI 和 Ollama

### 启动

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际配置

# 2. 启动所有服务
docker compose up -d

# 3. 初始化数据库
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser

# 4. 访问
# Web Admin: http://localhost:8000/admin
# MinIO: http://localhost:9001
```

### 本地开发

```bash
# 安装依赖
pip install -r requirements.txt

# 启动数据库（仅 infra）
docker compose up -d db redis minio

# 启动 Django
cd src
python manage.py migrate
python manage.py runserver

# 启动 Celery Worker
celery -A config worker -l info

# 确保 ComfyUI 和 Ollama 正在运行
```

## 使用流程

1. 在 Admin 后台添加国家（印尼 ID / 泰国 TH）和店铺
2. 上传 T 恤模板图（白/黑/彩色底图）
3. 上传原始印花图（支持批量）
4. 选择目标国家和模板，启动生成
5. 在产品库查看结果，手动编辑或导出 CSV/ZIP

## 项目结构

```
tk-erp/
├── docker-compose.yml       # 服务编排
├── src/                     # Django 应用
│   ├── config/              # 项目配置 + Celery
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
│   ├── comfy_workflows/     # ComfyUI 工作流
│   └── prompts/             # Prompt 模板
└── docs/                    # 文档
```
```

- [ ] **Step 2: 最后整理并提交**

```bash
git add README.md
git commit -m "docs: add README with setup instructions and project overview

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
git push
```

---

## 实现顺序说明

任务按依赖关系排列，必须按顺序执行：

```
Task 1 (脚手架) → Task 2 (Docker) → Task 3 (Country/Store) → Task 4 (Template)
                                    → Task 5 (Pattern) → Task 6 (Product)
                                                       → Task 7 (User/Roles)
Task 8 (Prompt模板) → Task 9 (AI接口) → Task 10 (ComfyUI) → Task 11 (Ollama)
                                      → Task 12 (变体策略)
Task 13 (预处理) → Task 14 (图像任务) → Task 15 (文本任务) → Task 16 (流水线)
Task 17 (导出) → Task 18 (README)

任务 8-9 可与 3-7 并行
任务 10-11 可与 13 并行
```

## 设计文档

详见: `docs/superpowers/specs/2026-06-04-tiktok-print-ai-design.md`
