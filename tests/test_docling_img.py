import asyncio
import pytest
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
import sys

@pytest.mark.asyncio
async def test_docling():
    opts = PdfPipelineOptions()
    opts.generate_picture_images = True
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
    )
    # We need a small PDF file with an image
    # Let's see if there is any PDF in the project
    pass

if __name__ == "__main__":
    asyncio.run(test_docling())
