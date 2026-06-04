from storages.backends.s3boto3 import S3Boto3Storage


class TemplateImageStorage(S3Boto3Storage):
    """T恤模板图片专用存储"""
    location = 'templates'
    file_overwrite = False
    default_acl = None
