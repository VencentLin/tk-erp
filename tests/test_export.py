import pytest
import csv
import io
from apps.core.models import Country
from apps.categories.models import PromptPreset
from apps.products.models import Product
from apps.export_app.services import export_products_csv, export_products_zip


@pytest.mark.django_db
class TestExportV7:
    def setup_method(self):
        self.country = Country.objects.create(code='ID', name='Indonesia')
        self.preset = PromptPreset.objects.create(
            name='Floral Vintage', slug='floral-vintage',
            content='floral vintage print design on t-shirt'
        )
        self.p1 = Product.objects.create(country=self.country, prompt_preset=self.preset,
                                         title='Kaos Test 1', description='Desc 1',
                                         size_info='S,M,L', status='completed')
        self.p2 = Product.objects.create(country=self.country, prompt_preset=self.preset,
                                         title='Kaos Test 2', description='Desc 2',
                                         size_info='M,L,XL', status='completed')

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

    def test_export_csv_v7_category_column_shows_preset_name(self):
        """V7: 无 category 的产品导出时分类列显示 preset 名称"""
        csv_str = export_products_csv([self.p1.id])
        assert 'Floral Vintage' in csv_str

    def test_export_zip(self):
        data = export_products_zip([self.p1.id])
        assert len(data) > 0
        assert data[:2] == b'PK'

    def test_export_empty_list(self):
        csv_str = export_products_csv([])
        lines = csv_str.strip().split('\n')
        assert len(lines) == 1

    def test_export_csv_v7_no_category_no_error(self):
        """V7: 只有 prompt_preset、无 category/template 的产品导出不报错"""
        csv_str = export_products_csv([self.p1.id])
        # Should not raise any exception
        assert csv_str is not None
        assert 'Indonesia' in csv_str  # country column works
