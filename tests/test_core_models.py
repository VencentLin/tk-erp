import pytest
from django.contrib.auth import get_user_model
from apps.core.models import Country, Store

User = get_user_model()


@pytest.mark.django_db
class TestCountry:
    def test_create_country(self):
        c = Country.objects.create(code='ID', name='Indonesia')
        assert str(c) == 'Indonesia'
        assert c.code == 'ID'

    def test_country_code_unique(self):
        Country.objects.create(code='ID', name='Indonesia')
        with pytest.raises(Exception):
            Country.objects.create(code='ID', name='Duplicate')


@pytest.mark.django_db
class TestStore:
    def test_create_store(self):
        user = User.objects.create_user(username='test', password='test')
        country = Country.objects.create(code='TH', name='Thailand')
        store = Store.objects.create(
            name='ShopThai01',
            country=country,
            owner=user,
            api_credentials={'shop_id': '12345', 'access_token': 'xxx'}
        )
        assert str(store) == 'ShopThai01'
        assert store.country.code == 'TH'

    def test_store_string_repr(self):
        user = User.objects.create_user(username='owner', password='test')
        country = Country.objects.create(code='ID', name='Indonesia')
        store = Store.objects.create(name='MyStore', country=country, owner=user)
        assert str(store) == 'MyStore'
