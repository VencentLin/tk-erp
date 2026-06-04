from storages.backends.s3boto3 import S3Boto3Storage


class PatternImageStorage(S3Boto3Storage):
    location = 'patterns'
    file_overwrite = False
    default_acl = None
