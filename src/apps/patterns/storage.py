from django.core.files.storage import FileSystemStorage


class PatternImageStorage(FileSystemStorage):
    """原始印花图片专用存储（本地文件系统）"""
    location = 'patterns'
