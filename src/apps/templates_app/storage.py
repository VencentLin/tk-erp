from django.core.files.storage import FileSystemStorage


class TemplateImageStorage(FileSystemStorage):
    """T恤模板图片专用存储（本地文件系统）"""
    location = 'templates'
