import os
import sys
import django
from django.conf import settings

# Ensure the src directory is on sys.path so Django apps can be imported
_this_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.join(os.path.dirname(_this_dir), 'src')
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

if not settings.configured:
    settings.configure(
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.admin',
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.messages',
            'django.contrib.staticfiles',
            'django_celery_results',
            'storages',
            'apps.accounts',
            'apps.core',
            'apps.patterns',
            'apps.templates_app',
            'apps.products',
            'apps.generation',
            'apps.export_app',
        ],
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
        SECRET_KEY='test-secret',
        MIDDLEWARE=[
            'django.middleware.security.SecurityMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.middleware.common.CommonMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
            'django.contrib.auth.middleware.AuthenticationMiddleware',
            'django.contrib.messages.middleware.MessageMiddleware',
        ],
        TEMPLATES=[{
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': True,
            'OPTIONS': {'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ]},
        }],
        LANGUAGE_CODE='zh-hans',
        TIME_ZONE='Asia/Shanghai',
        USE_I18N=True,
        USE_TZ=True,
        CELERY_BROKER_URL='redis://localhost:6379/0',
        CELERY_RESULT_BACKEND='django-db',
        CELERY_TASK_ALWAYS_EAGER=True,
        COMFYUI_BASE_URL='http://localhost:7860',
        OLLAMA_BASE_URL='http://localhost:11434',
        OLLAMA_MODEL='qwen2.5:14b',
    )
    django.setup()
