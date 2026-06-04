from django.core.files.storage import FileSystemStorage


class ProductImageStorage(FileSystemStorage):
    """产品图片专用存储（本地文件系统）"""
