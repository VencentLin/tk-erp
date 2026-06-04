from apps.generation.variants import (
    VARIANT_DIRECTIONS, get_variant_directions, apply_variant,
    ALTERNATE_COLORS, ALTERNATE_STYLES, ELEMENT_ADDITIONS,
)
from apps.generation.provider import AnalysisResult


class TestVariantDirections:
    def test_has_four_default_directions(self):
        assert len(VARIANT_DIRECTIONS) == 4
        keys = [d['key'] for d in VARIANT_DIRECTIONS]
        assert 'color_shift' in keys
        assert 'style_transfer' in keys
        assert 'element_add' in keys
        assert 'composition_tweak' in keys

    def test_get_all_directions(self):
        directions = get_variant_directions(max_variants=4)
        assert len(directions) == 4

    def test_get_limited_directions(self):
        directions = get_variant_directions(max_variants=2)
        assert len(directions) == 2

    def test_color_shift_variant(self):
        analysis = AnalysisResult(
            tags=['floral', 'vintage'],
            colors=['#FF6B6B', '#4ECDC4'],
            description='A vintage floral pattern'
        )
        direction = {'key': 'color_shift', 'label': '换色系', 'config_key': 'color_shift'}
        style_param, color_param = apply_variant(direction, analysis)
        assert 'floral' in style_param
        assert color_param in ALTERNATE_COLORS

    def test_style_transfer_variant(self):
        analysis = AnalysisResult(tags=['geometric', 'modern'], colors=['#000000'], description='')
        direction = {'key': 'style_transfer', 'label': '风格迁移', 'config_key': 'style_transfer'}
        style_param, color_param = apply_variant(direction, analysis)
        assert style_param in ALTERNATE_STYLES
        assert '#000000' in color_param

    def test_element_add_variant(self):
        analysis = AnalysisResult(tags=['minimalist'], colors=['#FFFFFF', '#333333'], description='')
        direction = {'key': 'element_add', 'label': '元素加减', 'config_key': 'element_add'}
        style_param, color_param = apply_variant(direction, analysis)
        assert 'with' in style_param
        assert any(elem in style_param for elem in ELEMENT_ADDITIONS)
