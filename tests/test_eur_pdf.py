"""Phase 04.7.2 — EÜR PDF Smoke (optional, importorskip)."""
import pytest

weasyprint = pytest.importorskip("weasyprint")


def test_weasyprint_can_render_minimal():
    """Smoke: WeasyPrint kann eine minimale HTML -> PDF rendern."""
    html = "<html><body><h1>Test</h1></body></html>"
    pdf = weasyprint.HTML(string=html).write_pdf()
    assert pdf is not None
    assert len(pdf) > 100
