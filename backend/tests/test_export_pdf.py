from exporter import export_to_pdf


def test_export_pdf_draws_current_plan():
    pdf = export_to_pdf({
        "name": "Lot A",
        "totalWidth": 40,
        "totalHeight": 30,
        "rooms": [
            {"name": "Living", "x": 0, "y": 0, "width": 20, "height": 16},
            {"name": "Kitchen", "x": 20, "y": 0, "width": 14, "height": 12},
        ],
        "doors": [{"x": 10, "y": 8}],
    })
    assert pdf.startswith(b"%PDF")
    assert b"Living" in pdf
    assert b"Kitchen" in pdf
    assert b"Lot A" in pdf
