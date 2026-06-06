from ai.prompts.loader import (
    load_text_prompt,
    build_text_prompt,
)


class TestTextPrompt:
    def test_load_language_template(self):
        """验证 load_text_prompt 对已知语言返回模板字符串"""
        for lang in ['id', 'th']:
            tmpl = load_text_prompt(lang, 'title')
            assert isinstance(tmpl, str)
            assert len(tmpl) > 10

    def test_build_text_prompt(self):
        """验证 build_text_prompt 生成包含传入描述的 prompt"""
        result = build_text_prompt(
            language='id',
            print_description='motif bunga tropis warna cerah',
            colors='merah, hijau, kuning',
            style='tropical',
            shirt_color='putih',
        )
        assert 'bunga tropis' in result
        assert 'Indonesia' in result  # 模板中应包含目标语言提示

    def test_unknown_language_returns_default_template(self):
        """验证未知语言返回默认模板（不抛异常）"""
        result = load_text_prompt('xx', 'title')
        assert isinstance(result, str)
        assert len(result) > 10
        assert '{print_description}' in result
