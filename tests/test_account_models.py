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
        assert user.is_staff  # country_lead gets staff access
