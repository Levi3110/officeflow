from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from urllib.parse import urlparse

from .artifacts import read_document, read_sheet
from .models import Product


class ParserWorker:
    def catalog(self, text, base_url, evidence_id):
        matches = re.findall(r"\b(Orion|Lyra|Vega)\s+Price:\s*USD\s*(\d+(?:\.\d+)?)", text)
        products = [
            Product(
                name=name,
                price=float(price),
                source_url=f"{base_url}/{name.lower()}",
                evidence_id=evidence_id,
            )
            for name, price in matches
        ]
        if len(products) != 3 or len({p.name for p in products}) != 3:
            raise ValueError("expected three distinct product summaries in observed page text")
        return products

    def details(self, text, product, evidence_id):
        if f"Product details: {product.name}" not in text:
            raise ValueError("detail page does not match requested product")
        price = re.search(r"Price:\s*USD\s*(\d+(?:\.\d+)?)", text)
        warranty = re.search(r"Warranty:\s*(\d+)\s*months", text)
        if not price or not warranty or float(price[1]) != product.price:
            raise ValueError("missing warranty or inconsistent source price")
        return Product.model_validate(
            {
                **product.model_dump(),
                "warranty_months": int(warranty[1]),
                "evidence_id": evidence_id,
                "version": product.version + 1,
            }
        )


class SpreadsheetWorker:
    """Produces a plan only. This worker cannot acquire authority or send desktop input."""

    def plan(self, products):
        cells = [
            (f"{col}1", value)
            for col, value in zip(
                "ABCDE", ("Product", "Price USD", "Warranty months", "Price with 8% tax", "Source")
            )
        ]
        for row, product in enumerate(products, 2):
            cells += [
                (f"A{row}", product.name),
                (f"B{row}", str(product.price)),
                (f"C{row}", str(product.warranty_months)),
                (f"D{row}", f"=B{row}*1.08"),
                (f"E{row}", product.source_url),
            ]
        return cells


class DocumentWorker:
    def plan(self, products):
        cheapest = min(products, key=lambda p: p.price)
        lines = ["Product comparison", "Fictional demo products. Currency: USD; assumed tax: 8%.", ""]
        for p in products:
            lines += [
                f"{p.name}: USD {p.price:.2f}; tax-inclusive USD {p.price * 1.08:.2f}; warranty {p.warranty_months} months.",
                f"Source: {p.source_url}",
            ]
        lines += [
            "",
            f"Recommendation: {cheapest.name} has the lowest listed price.",
            "Warranty values were checked on each product detail page.",
        ]
        return "\n".join(lines)


class Verifier:
    def check(self, directory: Path, products, expected_text):
        errors = []
        sheet = read_sheet(directory / "comparison.ods")
        document = read_document(directory / "report.odt")
        for cell, expected in SpreadsheetWorker().plan(products):
            actual = sheet.get(cell, {})
            if expected.startswith("="):
                formula = (actual.get("formula") or "").replace("[.", "").replace("]", "")
                try:
                    cached_value = float(actual.get("value", "nan"))
                except ValueError:
                    cached_value = float("nan")
                p = products[int(cell[1:]) - 2]
                if formula.removeprefix("of:") != expected or not math.isclose(
                    cached_value, p.price * 1.08, rel_tol=1e-8
                ):
                    errors.append(f"formula or calculated result mismatch: {cell}")
            else:
                value = actual.get("value", "")
                if cell.startswith(("B", "C")) and cell[1:] != "1":
                    if value == "" or float(value) != float(expected):
                        errors.append(f"numeric mismatch: {cell}")
                elif value != expected:
                    errors.append(f"value mismatch: {cell}")
        if document != expected_text:
            errors.append("report text differs from verified product data")
        if any(p.warranty_months is None for p in products):
            errors.append("incomplete source data")
        evidence = directory / "evidence"
        for product in products:
            observed = evidence / f"{product.evidence_id}.txt"
            if not observed.exists() or product.name not in observed.read_text():
                errors.append(f"missing source evidence: {product.name}")
            else:
                try:
                    text = observed.read_text()
                    metadata = json.loads(observed.with_suffix(".json").read_text())
                    detail = ParserWorker().details(text, product, product.evidence_id)
                    if detail.warranty_months != product.warranty_months:
                        errors.append(f"source warranty mismatch: {product.name}")
                    if metadata["sha256"] != hashlib.sha256(text.encode()).hexdigest():
                        errors.append(f"source evidence digest mismatch: {product.name}")
                    if metadata["source_url"] != product.source_url:
                        errors.append(f"source URL mismatch: {product.name}")
                except (OSError, ValueError, KeyError) as exc:
                    errors.append(f"invalid source evidence for {product.name}: {exc}")
            if urlparse(product.source_url).scheme not in ("http", "https"):
                errors.append("invalid source URL")
        return {
            "passed": not errors,
            "errors": errors,
            "checked": [
                "source evidence",
                "cell values",
                "formulas",
                "cached calculation",
                "report consistency",
            ],
        }
