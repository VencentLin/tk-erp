import pytest
import csv
import io
from django.contrib.auth import get_user_model
from apps.core.models import Country
from apps.patterns.models import Pattern
from apps.templates_app.models import TShirtTemplate
from apps.products.models import Product
from apps.export_app.services import export_products_csv, export_products_zip

User = get_user_model()


@pytest.mark.django_db
class TestExport:
    def setup_method(self):
        self.user = User.objects.create_user(username='test', password='test')
        self.country = Country.objects.create(code='ID', name='Indonesia')
        self.pattern = Pattern.objects.create(uploaded_by=self.user)
        self.template = TShirtTemplate.objects.create(name='White', color='white')
        self.p1 = Product.objects.create(country=self.country, pattern=self.pattern, template=self.template,
                                         title='Kaos Test 1', description='Desc 1', size_info='S,M,L', status='completed')
        self.p2 = Product.objects.create(country=self.country, pattern=self.pattern, template=self.template,
                                         title='Kaos Test 2', description='Desc 2', size_info='M,L,XL', status='completed')

    def test_export_csv_has_header(self):
        csv_str = export_products_csv([self.p1.id, self.p2.id])
        reader = csv.reader(io.StringIO(csv_str))
        header = next(reader)
        assert 'Product ID' in header
        assert 'Title' in header

    def test_export_csv_content(self):
        csv_str = export_products_csv([self.p1.id])
        assert 'Kaos Test 1' in csv_str
        assert 'Desc 1' in csv_str
        assert 'S,M,L' in csv_str

    def test_export_zip(self):
        data = export_products_zip([self.p1.id])
        assert len(data) > 0
        assert data[:2] == b'PK'

    def test_export_empty_list(self):
        csv_str = export_products_csv([])
        lines = csv_str.strip().split('\n')
        assert len(lines) == 1
