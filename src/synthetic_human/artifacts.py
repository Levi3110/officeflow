"""Blank ODF templates and read-only verification. Production content is entered by GUI."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)


def q(prefix, name):
    return f"{{{NS[prefix]}}}{name}"


def write_odf(path: Path, cells=None, text=""):
    """Only simulation may pass content here. Live mode uses empty seed documents."""
    sheet = path.suffix == ".ods"
    root = ET.Element(
        q("office", "document-content"),
        {q("office", "version"): "1.2", "xmlns:of": "urn:oasis:names:tc:opendocument:xmlns:of:1.2"},
    )
    body = ET.SubElement(root, q("office", "body"))
    if sheet:
        spreadsheet = ET.SubElement(body, q("office", "spreadsheet"))
        table = ET.SubElement(spreadsheet, q("table", "table"), {q("table", "name"): "Comparison"})
        cells = cells or {}
        for rownum in range(1, max([int(re.search(r"\d+", c)[0]) for c in cells] + [1]) + 1):
            row = ET.SubElement(table, q("table", "table-row"))
            for col in "ABCDEFGH":
                value = str(cells.get(f"{col}{rownum}", ""))
                attributes = {q("office", "value-type"): "string"}
                if value.startswith("="):
                    formula = re.sub(r"\b([A-H]\d+)\b", r"[.\1]", value)
                    attributes = {q("table", "formula"): "of:" + formula, q("office", "value-type"): "float"}
                    # Simple fixture formula evaluator, deliberately scoped to simulation.
                    m = re.fullmatch(r"=B(\d+)\*1.08", value)
                    calculated = float(cells[f"B{m[1]}"]) * 1.08 if m else 0.0
                    attributes[q("office", "value")] = str(calculated)
                elif re.fullmatch(r"\d+(\.\d+)?", value):
                    attributes = {q("office", "value-type"): "float", q("office", "value"): value}
                cell = ET.SubElement(row, q("table", "table-cell"), attributes)
                ET.SubElement(cell, q("text", "p")).text = value
    else:
        doc = ET.SubElement(body, q("office", "text"))
        for line in text.split("\n"):
            ET.SubElement(doc, q("text", "p")).text = line
    mime = "application/vnd.oasis.opendocument." + ("spreadsheet" if sheet else "text")
    manifest = f'''<?xml version="1.0"?><manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2"><manifest:file-entry manifest:full-path="/" manifest:media-type="{mime}"/><manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/></manifest:manifest>'''
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with ZipFile(temporary, "w") as z:
        z.writestr("mimetype", mime, compress_type=ZIP_STORED)
        z.writestr("META-INF/manifest.xml", manifest, compress_type=ZIP_DEFLATED)
        z.writestr(
            "content.xml",
            ET.tostring(root, encoding="utf-8", xml_declaration=True),
            compress_type=ZIP_DEFLATED,
        )
    temporary.replace(path)


def read_sheet(path):
    with ZipFile(path) as z:
        root = ET.fromstring(z.read("content.xml"))
    result = {}
    row_index = 1
    for row in root.findall(".//table:table-row", NS):
        repetitions = min(int(row.get(q("table", "number-rows-repeated"), "1")), 10000)
        col_index = 0
        for cell in row:
            if cell.tag not in (q("table", "table-cell"), q("table", "covered-table-cell")):
                continue
            repeat = min(int(cell.get(q("table", "number-columns-repeated"), "1")), 16384)
            value = cell.get(q("office", "value"))
            if value is None:
                value = "\n".join("".join(p.itertext()) for p in cell.findall("text:p", NS))
            formula = cell.get(q("table", "formula"))
            if value or formula:
                for offset in range(min(repeat, 26)):
                    if col_index + offset < 26:
                        result[f"{chr(65 + col_index + offset)}{row_index}"] = {
                            "value": value,
                            "formula": formula,
                        }
            col_index += repeat
        row_index += repetitions
    return result


def read_document(path):
    with ZipFile(path) as z:
        root = ET.fromstring(z.read("content.xml"))

    def content(element):
        if element.tag == q("text", "s"):
            return " " * int(element.get(q("text", "c"), "1"))
        if element.tag == q("text", "tab"):
            return "\t"
        if element.tag == q("text", "line-break"):
            return "\n"
        return (element.text or "") + "".join(content(c) + (c.tail or "") for c in element)

    return "\n".join(content(p) for p in root.iter() if p.tag in (q("text", "p"), q("text", "h")))
