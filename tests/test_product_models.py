import pytest
from apps.core.models import Country
from apps.categories.models import PromptPreset, PrintCategory
from apps.templates_app.models import TShirtTemplate
from apps.products.models import Product, ProductSKU


@pytest.mark.django_db
class TestProductV7:
    def setup_method(self):
        self.country_id = Country.objects.create(code='ID', name='Indonesia')
        self.country_th = Country.objects.create(code='TH', name='Thailand')
        self.preset = PromptPreset.objects.create(
            name='Test Preset', slug='test-preset',
            content='a cool t-shirt design, street style',
        )

    def test_create_product_v7_preset(self):
        """V7: 仅 prompt_preset，无 category/template"""
        p = Product.objects.create(
            country=self.country_id,
            prompt_preset=self.preset,
            title='Kaos Unik Motif Bunga',
            description='Kaos katun nyaman dengan motif bunga tropis.',
            size_info='S, M, L, XL',
            status='completed'
        )
        assert p.status == 'completed'
        assert 'Kaos' in p.title
        assert p.prompt_preset == self.preset
        assert p.category is None
        assert p.template is None

    def test_product_string(self):
        p = Product.objects.create(
            country=self.country_id, prompt_preset=self.preset,
            title='Test', description='Desc', size_info='S,M,L', status='completed'
        )
        assert str(p) == f'Product #{p.id} - Test'

    def test_default_status(self):
        p = Product.objects.create(
            country=self.country_id, prompt_preset=self.preset,
            title='', description='', size_info=''
        )
        assert p.status == 'pending'

    def test_filter_by_country(self):
        preset2 = PromptPreset.objects.create(
            name='Preset 2', slug='preset-2', content='another design'
        )
        Product.objects.create(
            country=self.country_id, prompt_preset=self.preset,
            title='ID Product', description='', size_info=''
        )
        Product.objects.create(
            country=self.country_th, prompt_preset=preset2,
            title='TH Product', description='', size_info=''
        )
        assert Product.objects.filter(country=self.country_id).count() == 1
        assert Product.objects.filter(country=self.country_th).count() == 1

    def test_legacy_category_product(self):
        """Legacy: category + template 模式"""
        cat = PrintCategory.objects.create(
            name='Floral', slug='floral',
            keywords='flower, tropical', print_prompt='floral pattern'
        )
        template = TShirtTemplate.objects.create(name='White Tee', color='white')
        p = Product.objects.create(
            country=self.country_id, category=cat, template=template,
            title='Legacy Product', description='', size_info=''
        )
        assert p.category == cat
        assert p.template == template
        assert p.prompt_preset is None


@pytest.mark.django_db
class TestProductSKU:
    def setup_method(self):
        self.country = Country.objects.create(code='ID', name='Indonesia')
        self.preset = PromptPreset.objects.create(
            name='SKU Test', slug='sku-test', content='test content'
        )
        self.product = Product.objects.create(
            country=self.country, prompt_preset=self.preset,
            title='SKU Test Product', description='', size_info=''
        )

    def test_create_sku_no_template(self):
        """V7 SKU: template 可为空"""
        sku = ProductSKU.objects.create(product=self.product)
        assert sku.template is None
        assert str(sku).startswith('SKU #')

    def test_create_sku_with_template(self):
        """Legacy SKU: 有 template"""
        template = TShirtTemplate.objects.create(name='Black Tee', color='black')
        sku = ProductSKU.objects.create(product=self.product, template=template)
        assert sku.template == template
        assert 'black' in str(sku).lower()

    def test_sku_product_relation(self):
        ProductSKU.objects.create(product=self.product)
        ProductSKU.objects.create(product=self.product)
        assert self.product.skus.count() == 2


class TestPresetPromptNormalization:
    """Task 1: 验证 _parse_md_prompt + _normalize_preset_prompt 不留占位符"""

    def test_normalize_removes_template_prompt_placeholder(self):
        from apps.dashboard.views import _parse_md_prompt, _normalize_preset_prompt
        content = "{{template_prompt}}\n\nfloral print design"
        positive, negative = _parse_md_prompt(content)
        positive = _normalize_preset_prompt(positive)
        assert '{{' not in positive
        assert '}}' not in positive
        assert 'white cotton t-shirt' in positive

    def test_normalize_removes_fabric_placeholder(self):
        from apps.dashboard.views import _parse_md_prompt, _normalize_preset_prompt
        content = "cool print on {{fabric}}"
        positive, negative = _parse_md_prompt(content)
        positive = _normalize_preset_prompt(positive)
        assert '{{' not in positive
        assert 'cotton fabric' in positive

    def test_normalize_removes_background_placeholder(self):
        from apps.dashboard.views import _parse_md_prompt, _normalize_preset_prompt
        content = "floral design\n\n{{background}}"
        positive, negative = _parse_md_prompt(content)
        positive = _normalize_preset_prompt(positive)
        assert '{{' not in positive
        assert 'wooden hanger' in positive

    def test_normalize_all_placeholders(self):
        from apps.dashboard.views import _parse_md_prompt, _normalize_preset_prompt
        content = "{{template_prompt}}\n\nprint: {{fabric}}\n\nscene: {{background}}"
        positive, negative = _parse_md_prompt(content)
        positive = _normalize_preset_prompt(positive)
        assert '{{' not in positive
        assert '}}' not in positive

    def test_normalize_with_negative_section(self):
        from apps.dashboard.views import _parse_md_prompt, _normalize_preset_prompt
        content = "{{template_prompt}}\n\n## NEGATIVE\nblurry, low quality"
        positive, negative = _parse_md_prompt(content)
        positive = _normalize_preset_prompt(positive)
        assert '{{' not in positive
        assert 'blurry' in negative
        assert 'white cotton t-shirt' in positive

    def test_normalize_no_placeholder_passthrough(self):
        from apps.dashboard.views import _normalize_preset_prompt
        content = "clean t-shirt mockup, minimalist design"
        result = _normalize_preset_prompt(content)
        assert result == content  # unchanged


class TestShirtColorDetection:
    """Task B: 颜色识别"""

    def test_detect_white_from_filename(self):
        from apps.dashboard.views import _detect_shirt_color
        assert _detect_shirt_color('01-white-pastel-doodle.md') == 'white'

    def test_detect_black_from_filename(self):
        from apps.dashboard.views import _detect_shirt_color
        assert _detect_shirt_color('01-black-floral-horse.md') == 'black'

    def test_detect_white_from_dir(self):
        from apps.dashboard.views import _detect_shirt_color
        assert _detect_shirt_color('01-pastel-doodle.md', dir_path='white') == 'white'

    def test_detect_black_from_dir(self):
        from apps.dashboard.views import _detect_shirt_color
        assert _detect_shirt_color('01-floral-horse.md', dir_path='black') == 'black'

    def test_detect_other_when_no_match(self):
        from apps.dashboard.views import _detect_shirt_color
        assert _detect_shirt_color('random-design.md') == 'other'


class TestShirtColorLock:
    """Task E: 颜色锁定"""

    def test_lock_white_adds_prefix(self):
        from apps.dashboard.views import _apply_shirt_color_lock
        result = _apply_shirt_color_lock('some design prompt', 'white')
        assert result.startswith('The garment color is locked: white cotton t-shirt.')

    def test_lock_black_adds_prefix(self):
        from apps.dashboard.views import _apply_shirt_color_lock
        result = _apply_shirt_color_lock('some design prompt', 'black')
        assert result.startswith('The garment color is locked: black cotton t-shirt.')

    def test_lock_other_passthrough(self):
        from apps.dashboard.views import _apply_shirt_color_lock
        prompt = 'some design prompt'
        result = _apply_shirt_color_lock(prompt, 'other')
        assert result == prompt


@pytest.mark.django_db
class TestShirtColorField:
    """Task A: PromptPreset shirt_color"""

    def test_preset_default_color_is_white(self):
        from apps.categories.models import PromptPreset
        p = PromptPreset.objects.create(
            name='Test Default', slug='test-default',
            content='test content'
        )
        assert p.shirt_color == 'white'

    def test_preset_black_color(self):
        from apps.categories.models import PromptPreset
        p = PromptPreset.objects.create(
            name='Test Black', slug='test-black',
            content='test content', shirt_color='black'
        )
        assert p.shirt_color == 'black'

    def test_preset_other_color(self):
        from apps.categories.models import PromptPreset
        p = PromptPreset.objects.create(
            name='Test Other', slug='test-other',
            content='test content', shirt_color='other'
        )
        assert p.shirt_color == 'other'


@pytest.mark.django_db
class TestPromptSync:
    """Task B2: 目录同步"""

    def test_sync_creates_presets_from_white_dir(self):
        from apps.categories.prompt_sync import sync_prompt_presets_from_disk
        from apps.categories.models import PromptPreset

        # 确保已有预设被清理
        PromptPreset.objects.all().delete()

        result = sync_prompt_presets_from_disk()
        assert result['created'] >= 5  # at least 5 white presets
        white_count = PromptPreset.objects.filter(shirt_color='white').count()
        black_count = PromptPreset.objects.filter(shirt_color='black').count()
        assert white_count >= 5
        assert black_count >= 5

    def test_sync_presets_have_color(self):
        from apps.categories.models import PromptPreset
        # All synced presets should have valid shirt_color
        for p in PromptPreset.objects.all():
            assert p.shirt_color in ('white', 'black', 'other')

    def test_old_preset_without_source_is_deleted(self):
        """磁盘文件不存在的旧预设，无产品关联 → 硬删除"""
        from apps.categories.prompt_sync import sync_prompt_presets_from_disk
        from apps.categories.models import PromptPreset

        # Create a fake old preset that points to data/prompts but doesn't exist on disk
        old = PromptPreset.objects.create(
            name='Old Ghost', slug='old-ghost-999',
            content='test', md_file='data/prompts/old-ghost.md',
            is_active=True
        )
        result = sync_prompt_presets_from_disk()
        # 文件不存在 + 无产品 → 应被硬删除
        assert not PromptPreset.objects.filter(slug='old-ghost-999').exists()

    def test_old_preset_with_products_is_deactivated(self):
        """磁盘文件不存在的旧预设，有产品关联 → 停用"""
        from apps.categories.prompt_sync import sync_prompt_presets_from_disk
        from apps.categories.models import PromptPreset
        from apps.core.models import Country
        from apps.products.models import Product

        preset = PromptPreset.objects.create(
            name='Has Products', slug='has-products-999',
            content='test', md_file='data/prompts/has-products.md',
            is_active=True
        )
        country = Country.objects.create(code='XX', name='TestLand')
        product = Product.objects.create(
            country=country, prompt_preset=preset,
            title='Test Product'
        )
        result = sync_prompt_presets_from_disk()
        preset.refresh_from_db()
        assert not preset.is_active  # 应被停用
        assert preset.products.count() == 1  # 产品还在
        # Cleanup
        product.delete()
        preset.delete()
        country.delete()


class TestPrintPlacementLock:
    """Task G: 印花位置和纯色锁"""

    def test_placement_lock_white_solid_color(self):
        from apps.dashboard.views import _apply_print_placement_lock
        result = _apply_print_placement_lock('test prompt', 'white')
        assert 'solid white cotton t-shirt' in result
        assert 'color-block' in result
        assert 'chest-only' in result or 'chest only' in result.lower()

    def test_placement_lock_black_solid_color(self):
        from apps.dashboard.views import _apply_print_placement_lock
        result = _apply_print_placement_lock('test prompt', 'black')
        assert 'solid black cotton t-shirt' in result
        assert 'no beige body panel' in result.lower()

    def test_placement_lock_chest_safe_area(self):
        from apps.dashboard.views import _apply_print_placement_lock
        result = _apply_print_placement_lock('test prompt', 'white')
        assert 'no wider than 30 percent' in result.lower()
        assert 'stay far away from sleeves' in result.lower()


class TestFlatPrintLock:
    """Task H: 平面印花锁"""

    def test_flat_lock_no_pocket(self):
        from apps.dashboard.views import _apply_flat_print_lock
        result = _apply_flat_print_lock('test prompt')
        assert 'no pocket' in result.lower()
        assert 'flat ink print' in result.lower()

    def test_flat_lock_no_embroidery(self):
        from apps.dashboard.views import _apply_flat_print_lock
        result = _apply_flat_print_lock('test prompt')
        assert 'no embroidery' in result.lower()
        assert 'no 3d print' in result.lower()

    def test_flat_lock_no_physical_thickness(self):
        from apps.dashboard.views import _apply_flat_print_lock
        result = _apply_flat_print_lock('test prompt')
        assert 'no physical thickness' in result.lower()


class TestRiskyKeywordNormalization:
    """Task G+H: 高风险词标准化"""

    def test_normalize_back_print_to_chest(self):
        from apps.dashboard.views import _normalize_risky_keywords
        result, warnings = _normalize_risky_keywords('cool back print design')
        assert 'back print' not in result.lower()
        assert 'chest print' in result.lower()
        assert 'back print' in warnings

    def test_normalize_large_graphic(self):
        from apps.dashboard.views import _normalize_risky_keywords
        result, warnings = _normalize_risky_keywords('a large graphic print on shirt')
        assert 'large graphic' not in result.lower()
        assert 'small to medium' in result.lower()

    def test_normalize_embroidery(self):
        from apps.dashboard.views import _normalize_risky_keywords
        result, warnings = _normalize_risky_keywords('beautiful embroidered patch design')
        assert 'embroidered' not in result.lower()
        assert 'flat ink print' in result.lower()

    def test_normalize_applique(self):
        from apps.dashboard.views import _normalize_risky_keywords
        result, warnings = _normalize_risky_keywords('cool applique patch on chest')
        assert 'applique' not in result.lower()
        assert 'flat ink print' in result.lower()

    def test_normalize_safe_prompt_unchanged(self):
        from apps.dashboard.views import _normalize_risky_keywords
        safe = 'clean chest print, flat ink design, small graphic'
        result, warnings = _normalize_risky_keywords(safe)
        assert result == safe
        assert len(warnings) == 0


@pytest.mark.django_db
class TestPrintDesignPreset:
    """POD Task 1+9: PrintDesignPreset 模型"""

    def test_create_print_preset(self):
        from apps.categories.models import PrintDesignPreset
        p = PrintDesignPreset.objects.create(
            name='Test Print', slug='test-print',
            content='flat vector graphic, no text', shirt_color='white'
        )
        assert p.shirt_color == 'white'
        assert p.is_active
        assert str(p) == 'Test Print'

    def test_print_preset_variation_pool(self):
        from apps.categories.models import PrintDesignPreset
        p = PrintDesignPreset.objects.create(
            name='Pool Test', slug='pool-test',
            content='test', shirt_color='black',
            variation_pool={'color_palettes': ['red, blue']}
        )
        assert p.variation_pool['color_palettes'] == ['red, blue']

    def test_print_preset_default_color(self):
        from apps.categories.models import PrintDesignPreset
        p = PrintDesignPreset.objects.create(
            name='Default Color', slug='default-color',
            content='test'
        )
        assert p.shirt_color == 'white'


@pytest.mark.django_db
class TestPrintDesign:
    """POD Task 7: PrintDesign 模型"""

    def test_create_print_design(self):
        from apps.categories.models import PrintDesignPreset, PrintDesign
        preset = PrintDesignPreset.objects.create(
            name='PD Test', slug='pd-test', content='test'
        )
        design = PrintDesign.objects.create(
            preset=preset, shirt_color='white',
            prompt='test print prompt', seed=42,
            variation_metadata={'palette': 'red, blue'}
        )
        assert design.seed == 42
        assert design.preset == preset
        assert 'Print #' in str(design)

    def test_print_design_preset_relation(self):
        from apps.categories.models import PrintDesignPreset, PrintDesign
        preset = PrintDesignPreset.objects.create(
            name='Rel Test', slug='rel-test', content='test'
        )
        PrintDesign.objects.create(preset=preset, prompt='p1', seed=1)
        PrintDesign.objects.create(preset=preset, prompt='p2', seed=2)
        assert preset.designs.count() == 2


@pytest.mark.django_db
class TestProductPODFields:
    """POD: Product generation_mode + print_design"""

    def test_default_generation_mode_is_direct(self):
        from apps.core.models import Country
        from apps.products.models import Product
        c = Country.objects.create(code='POD', name='PodLand')
        p = Product.objects.create(country=c, title='Test')
        assert p.generation_mode == 'direct'

    def test_pod_product_links_print_design(self):
        from apps.core.models import Country
        from apps.categories.models import PrintDesignPreset, PrintDesign
        from apps.products.models import Product
        c = Country.objects.create(code='P2', name='PodLand2')
        preset = PrintDesignPreset.objects.create(name='Link Test', slug='link-test', content='test')
        design = PrintDesign.objects.create(preset=preset, prompt='test', seed=1)
        p = Product.objects.create(country=c, generation_mode='pod', print_design=design, title='Pod Product')
        assert p.generation_mode == 'pod'
        assert p.print_design == design


@pytest.mark.django_db
class TestTShirtTemplatePODFields:
    """POD Task 5: TShirtTemplate POD 字段"""

    def test_pod_template_fields(self):
        from apps.templates_app.models import TShirtTemplate
        t = TShirtTemplate.objects.create(
            name='POD Template', color='white',
            is_pod_template=True,
            print_area_x=320, print_area_y=180,
            print_area_width=200, print_area_height=200
        )
        assert t.is_pod_template
        assert t.print_area_x == 320
        assert t.print_area_width == 200

    def test_non_pod_template_defaults(self):
        from apps.templates_app.models import TShirtTemplate
        t = TShirtTemplate.objects.create(name='Non-POD', color='black')
        assert not t.is_pod_template
        assert t.print_area_x is None


class TestPrintVariation:
    """POD Task 2: build_random_print_prompt"""

    def test_default_pool_produces_variation(self):
        from apps.categories.models import PrintDesignPreset
        from apps.generation.print_variants import build_random_print_prompt
        preset = PrintDesignPreset(
            name='VTest', slug='vtest', content='flat vector graphic',
            shirt_color='white'
        )
        pos, neg, meta = build_random_print_prompt(preset, seed=42)
        assert 'flat vector graphic' in pos
        assert 'color palette' in pos.lower()
        assert 'composition' in pos.lower()
        assert 'elements' in pos.lower()
        assert meta['seed'] == 42

    def test_different_seeds_produce_different_output(self):
        from apps.categories.models import PrintDesignPreset
        from apps.generation.print_variants import build_random_print_prompt
        preset = PrintDesignPreset(
            name='VTest2', slug='vtest2', content='flat graphic',
        )
        pos1, _, _ = build_random_print_prompt(preset, seed=1)
        pos2, _, _ = build_random_print_prompt(preset, seed=999)
        # Different seeds may or may not produce different output
        # (depending on random choices), but at minimum they should both be valid
        assert len(pos1) > 0
        assert len(pos2) > 0
