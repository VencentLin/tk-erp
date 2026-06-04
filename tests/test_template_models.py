import time

import pytest
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
        time.sleep(0.01)  # Ensure different created_at timestamps
        new = TShirtTemplate.objects.create(name='New', color='black')
        qs = list(TShirtTemplate.objects.all())
        assert qs[0] == new
        assert qs[1] == old
