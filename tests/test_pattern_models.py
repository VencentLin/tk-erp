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
