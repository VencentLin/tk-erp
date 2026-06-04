import pytest
from django.contrib.auth import get_user_model
from apps.core.models import Country
from apps.patterns.models import Pattern
from apps.templates_app.models import TShirtTemplate
from apps.products.models import Product, GenerationLog

User = get_user_model()


@pytest.mark.django_db
class TestProduct:
    def setup_method(self):
        self.user = User.objects.create_user(username='test', password='test')
        self.country_id = Country.objects.create(code='ID', name='Indonesia')
        self.country_th = Country.objects.create(code='TH', name='Thailand')
        self.pattern = Pattern.objects.create(uploaded_by=self.user)
        self.template = TShirtTemplate.objects.create(name='White', color='white')

    def test_create_product(self):
        p = Product.objects.create(
            country=self.country_id,
            pattern=self.pattern,
            template=self.template,
            title='Kaos Unik Motif Bunga',
            description='Kaos katun nyaman dengan motif bunga tropis.',
            size_info='S, M, L, XL',
            status='completed'
        )
        assert p.status == 'completed'
        assert 'Kaos' in p.title

    def test_product_string(self):
        p = Product.objects.create(
            country=self.country_id, pattern=self.pattern,
            template=self.template, title='Test',
            description='Desc', size_info='S,M,L', status='completed'
        )
        assert str(p) == f'Product #{p.id} - Test'

    def test_default_status(self):
        p = Product.objects.create(
            country=self.country_id, pattern=self.pattern,
            template=self.template, title='', description='', size_info=''
        )
        assert p.status == 'pending'

    def test_filter_by_country(self):
        Product.objects.create(
            country=self.country_id, pattern=self.pattern, template=self.template,
            title='ID Product', description='', size_info=''
        )
        Product.objects.create(
            country=self.country_th, pattern=self.pattern, template=self.template,
            title='TH Product', description='', size_info=''
        )
        assert Product.objects.filter(country=self.country_id).count() == 1
        assert Product.objects.filter(country=self.country_th).count() == 1


@pytest.mark.django_db
class TestGenerationLog:
    def setup_method(self):
        self.user = User.objects.create_user(username='test', password='test')
        self.country = Country.objects.create(code='ID', name='Indonesia')
        self.pattern = Pattern.objects.create(uploaded_by=self.user)
        self.template = TShirtTemplate.objects.create(name='White', color='white')
        self.product = Product.objects.create(
            country=self.country, pattern=self.pattern, template=self.template,
            title='Test', description='', size_info=''
        )

    def test_create_log(self):
        log = GenerationLog.objects.create(
            product=self.product,
            step='image_gen',
            model_used='sdxl',
            params={'prompt': 'test prompt', 'batch_size': 4},
            duration_ms=3500,
            token_count=0
        )
        assert log.step == 'image_gen'
        assert log.duration_ms == 3500
        assert str(log).startswith('image_gen for Product #')
