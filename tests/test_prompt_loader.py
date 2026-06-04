from ai.prompts.loader import (
    load_image_variants_config,
    load_text_prompt,
    build_image_prompt,
    build_text_prompt,
)


class TestImagePrompt:
    def test_load_config(self):
        config = load_image_variants_config()
        assert 'base_prompt' in config
        assert 'variants' in config
        assert 'color_shift' in config['variants']

    def test_build_color_shift_prompt(self):
        pos, neg, params = build_image_prompt(
            'color_shift',
            original_style='floral vintage',
            colors_or_style='pastel pink and mint green',
        )
        assert 'floral vintage' in pos
        assert 'pastel pink' in pos
        assert 'photo' in neg
        assert 'denoising_strength' in params

    def test_build_style_transfer_prompt(self):
        pos, neg, params = build_image_prompt(
            'style_transfer',
            original_style='geometric tribal',
            colors_or_style='monochrome black and white',
        )
        assert 'monochrome' in pos
        assert len(params) > 0


class TestTextPrompt:
    def test_load_thai_title_template(self):
        tmpl = load_text_prompt('th', 'title')
        assert 'ภาษาไทย' in tmpl
        assert '{print_description}' in tmpl

    def test_load_indonesian_title_template(self):
        tmpl = load_text_prompt('id', 'title')
        assert 'Indonesia' in tmpl
        assert '{print_description}' in tmpl

    def test_build_thai_prompt(self):
        result = build_text_prompt(
            language='th',
            print_description='ดอกไม้เขตร้อนสีสันสดใส',
            colors='แดง, เขียว, เหลือง',
            style='tropical',
            shirt_color='ขาว',
        )
        assert 'ดอกไม้เขตร้อน' in result
        assert 'ขาว' in result

    def test_build_indonesian_prompt(self):
        result = build_text_prompt(
            language='id',
            print_description='motif bunga tropis warna cerah',
            colors='merah, hijau, kuning',
            style='tropical',
            shirt_color='putih',
        )
        assert 'bunga tropis' in result
        assert 'putih' in result

    def test_missing_template_raises_error(self):
        import pytest
        with pytest.raises(FileNotFoundError):
            load_text_prompt('xx', 'title')
