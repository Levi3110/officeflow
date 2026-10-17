import pytest
from pydantic import ValidationError

from synthetic_human.models import Product
from synthetic_human.workers import ParserWorker


def test_external_data_must_pass_schema_even_when_updating_existing_product():
    product = Product(name="Orion", price=120, source_url="http://localhost/orion", evidence_id="source-1")
    text = "Product details: Orion\nPrice: USD 120.00\nWarranty: 999 months\n"
    with pytest.raises(ValidationError):
        ParserWorker().details(text, product, "source-2")
