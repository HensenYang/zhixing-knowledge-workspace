import io

import pytest
from fastapi import HTTPException
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from backend.exporters import material_docx, material_markdown, material_pdf
from backend.importers import detect_source_type, import_pdf


def sample_record():
    return {
        'object': {
            'id': 'object-1', 'title': '机器人动作表示', 'kind': 'resource',
            'tags': ['VLA', '论文'], 'source_url': 'https://example.org/paper',
            'version': 2, 'summary': '动作空间与坐标系摘要',
            'body_md': '## 核心内容\n\n动作 $a_t$ 需要明确坐标系。',
            'metadata': {'authors': '测试作者'},
        },
        'relations': [{
            'id': 'relation-1', 'source_id': 'object-1', 'target_id': 'object-2',
            'source_title': '机器人动作表示', 'target_title': 'VLA',
            'relation_type': 'depends_on', 'description': '理解动作输出的前置知识',
            'evidence': [{'locator': '第 2 页', 'explanation': '原文定义', 'source_url': 'https://example.org/paper#page=2'}],
        }],
        'attachments': [{'original_name': 'paper.pdf', 'size_bytes': 1024}],
    }


def test_material_renderers_produce_openable_files():
    markdown = material_markdown(sample_record())
    assert '# 机器人动作表示' in markdown
    assert '第 2 页' in markdown
    docx = material_docx(markdown)
    pdf = material_pdf(markdown)
    assert docx.startswith(b'PK')
    assert pdf.startswith(b'%PDF')
    assert len(PdfReader(io.BytesIO(pdf)).pages) >= 1


def test_pdf_import_extracts_text_and_metadata():
    output = io.BytesIO()
    document = canvas.Canvas(output)
    document.setTitle('Import Test')
    document.setAuthor('Knowledge Team')
    document.drawString(72, 760, 'A lightweight import test.')
    document.save()
    preview = import_pdf(output.getvalue(), 'test.pdf')
    assert preview['source_type'] == 'pdf'
    assert preview['title'] == 'Import Test'
    assert 'lightweight import test' in preview['body_md']
    assert preview['metadata']['pages'] == 1
    assert preview['metadata']['pdf_extraction_mode'] == 'plain'
    assert preview['metadata']['layout_reflow_pages'] == []
    assert not any('碎片化' in warning for warning in preview['warnings'])


def test_pdf_import_reflows_fragmented_word_lines():
    output = io.BytesIO()
    document = canvas.Canvas(output)
    words = (
        'This personal reflection document should remain one coherent sentence '
        'after importing because separate word lines make research notes difficult '
        'to read review connect annotate share export and reuse across projects'
    ).split()
    x, y = 72, 760
    for word in words:
        width = document.stringWidth(word)
        if x + width > 520:
            x, y = 72, y - 24
        document.drawString(x, y, word)
        x += width + 10
    document.save()

    preview = import_pdf(output.getvalue(), 'fragmented.pdf')

    assert 'This personal reflection document should remain one coherent sentence' in preview['body_md']
    assert '\nThis\npersonal\nreflection\n' not in preview['body_md']
    assert preview['metadata']['pdf_extraction_mode'] == 'adaptive-layout'
    assert preview['metadata']['layout_reflow_pages'] == [1]
    assert any('碎片化' in warning for warning in preview['warnings'])


def test_source_detection_is_limited_to_supported_sources():
    assert detect_source_type('https://arxiv.org/abs/2401.01234') == 'arxiv'
    assert detect_source_type('10.1000/example') == 'doi'
    assert detect_source_type('https://github.com/openai/example') == 'github'
    with pytest.raises(HTTPException) as error:
        detect_source_type('https://127.0.0.1/private')
    assert error.value.status_code == 422


