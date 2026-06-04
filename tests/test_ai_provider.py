import pytest
from PIL import Image
from apps.generation.provider import AIProvider, ImageResult, AnalysisResult, TextResult


class TestProviderInterface:
    def test_provider_is_abstract(self):
        provider = AIProvider()
        with pytest.raises(NotImplementedError):
            provider.generate_image('prompt', None, {})

        with pytest.raises(NotImplementedError):
            provider.analyze_image(None)

        with pytest.raises(NotImplementedError):
            provider.generate_text('prompt', 'th')

    def test_image_result_dataclass(self):
        img = Image.new('RGB', (64, 64), color='red')
        result = ImageResult(images=[img], metadata={'seed': 12345})
        assert len(result.images) == 1
        assert result.metadata['seed'] == 12345

    def test_analysis_result_dataclass(self):
        result = AnalysisResult(
            tags=['floral', 'vintage'],
            colors=['#FF6B6B', '#4ECDC4'],
            description='A vintage floral pattern'
        )
        assert 'floral' in result.tags
        assert len(result.colors) == 2

    def test_text_result_dataclass(self):
        result = TextResult(
            title='Kaos Motif Bunga Tropis',
            description='Kaos katun nyaman dengan motif bunga tropis',
            size_info='S, M, L, XL'
        )
        assert 'Kaos' in result.title
        assert 'XL' in result.size_info
