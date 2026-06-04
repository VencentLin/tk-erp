from storages.backends.s3boto3 import S3Boto3Storage


class ProductImageStorage(S3Boto3Storage):
    location = 'products'
    file_overwrite = False
    default_acl = None
