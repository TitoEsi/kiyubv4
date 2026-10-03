"""DXF/PDF export. Input FloorPlan is canonical meters; labels use the requested display unit."""
import ezdxf
from ezdxf.enums import TextEntityAlignment
import io

from generation_units import format_dimensions

DEFAULT_WIDTH_M = 12.0
DEFAULT_DEPTH_M = 10.5
DXF_INSUNITS_METERS = 6


def export_to_dxf(floor_plan: dict, unit: str = "m") -> bytes:
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = DXF_INSUNITS_METERS
    msp = doc.modelspace()

    doc.layers.add("BOUNDARY", color=1)
    doc.layers.add("ROOMS", color=7)
    doc.layers.add("LABELS", color=3)
    doc.layers.add("DIMENSIONS", color=2)

    total_w = float(floor_plan.get("totalWidth", DEFAULT_WIDTH_M))
    total_h = float(floor_plan.get("totalHeight", DEFAULT_DEPTH_M))

    # Outer boundary
    msp.add_lwpolyline(
        [(0, 0), (total_w, 0), (total_w, total_h), (0, total_h)],
        close=True,
        dxfattribs={"layer": "BOUNDARY", "lineweight": 50},
    )

    for room in floor_plan.get("rooms", []):
        rx = float(room["x"])
        ry_dxf = total_h - float(room["y"]) - float(room["height"])  # flip Y axis
        rw = float(room["width"])
        rh = float(room["height"])

        # Room rectangle
        msp.add_lwpolyline(
            [(rx, ry_dxf), (rx + rw, ry_dxf), (rx + rw, ry_dxf + rh), (rx, ry_dxf + rh)],
            close=True,
            dxfattribs={"layer": "ROOMS", "lineweight": 25},
        )

        cx = rx + rw / 2
        cy = ry_dxf + rh / 2
        font_h = min(rw, rh) * 0.09

        name_text = msp.add_text(
            room.get("name", "Room"),
            dxfattribs={"layer": "LABELS", "height": max(0.3, font_h)},
        )
        name_text.set_placement((cx, cy + 0.18), align=TextEntityAlignment.MIDDLE_CENTER)

        dim_text = msp.add_text(
            format_dimensions(rw, rh, unit),
            dxfattribs={"layer": "DIMENSIONS", "height": max(0.2, font_h * 0.7)},
        )
        dim_text.set_placement((cx, cy - 0.18), align=TextEntityAlignment.MIDDLE_CENTER)

    stream = io.BytesIO()
    doc.write(stream)
    stream.seek(0)
    return stream.getvalue()


def _pdf_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .encode("latin-1", "replace")
        .decode("latin-1")
    )


def _build_pdf(content: bytes, page_w: float, page_h: float) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_w:.0f} {page_h:.0f}] "
            f"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ).encode("ascii"),
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    # object 4 length is baked in; rebuild with correct stream wrapper
    objects[3] = b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content)
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{i} 0 obj\n".encode("ascii"))
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    return bytes(out)


def export_to_pdf(floor_plan: dict, unit: str = "m") -> bytes:
    """Draw the current FloorPlan. Plan Y is down (same as 2D ArchPlan).

    PDF Y is up. Mapping: pdf_y = page_h - margin - plan_y * scale, so smaller
    plan-y is higher on the page (north). DXF export instead flips to CAD Y-up
    with ry_dxf = total_h - y - height in plan units.
    """
    page_w, page_h = 792.0, 612.0
    margin = 40.0
    title_h = 28.0
    name = str(floor_plan.get("name") or "Floor Plan")
    total_w = max(float(floor_plan.get("totalWidth") or DEFAULT_WIDTH_M), 0.3)
    total_h = max(float(floor_plan.get("totalHeight") or DEFAULT_DEPTH_M), 0.3)
    rooms = floor_plan.get("rooms") or []
    doors = floor_plan.get("doors") or []

    draw_w = page_w - margin * 2
    draw_h = page_h - margin * 2 - title_h
    scale = min(draw_w / total_w, draw_h / total_h)
    ox = margin + (draw_w - total_w * scale) / 2
    oy_top = margin + title_h

    def to_pdf(x: float, y: float) -> tuple[float, float]:
        return ox + x * scale, page_h - (oy_top + y * scale)

    ops: list[str] = []
    ops.append("0.12 0.13 0.15 RG")
    ops.append("0.9 w")
    bx, by = to_pdf(0, total_h)
    ops.append(f"{bx:.2f} {by:.2f} {total_w * scale:.2f} {total_h * scale:.2f} re S")

    for room in rooms:
        rx = float(room.get("x") or 0)
        ry = float(room.get("y") or 0)
        rw = float(room.get("width") or 0)
        rh = float(room.get("height") or 0)
        px, py = to_pdf(rx, ry + rh)
        ops.append("0.93 0.94 0.95 rg")
        ops.append("0.12 0.13 0.15 RG")
        ops.append(f"{px:.2f} {py:.2f} {rw * scale:.2f} {rh * scale:.2f} re B")
        cx, cy = to_pdf(rx + rw / 2, ry + rh / 2)
        label = _pdf_escape(str(room.get("name") or "Room"))
        dim = _pdf_escape(format_dimensions(rw, rh, unit))
        ops.append("0 g")
        ops.append("BT /F1 9 Tf")
        ops.append(f"1 0 0 1 {cx - 22:.2f} {cy + 4:.2f} Tm ({label}) Tj ET")
        ops.append("BT /F1 7 Tf")
        ops.append(f"1 0 0 1 {cx - 22:.2f} {cy - 8:.2f} Tm ({dim}) Tj ET")

    for door in doors:
        dx = float(door.get("x") or 0)
        dy = float(door.get("y") or 0)
        px, py = to_pdf(dx, dy)
        ops.append("0.15 0.28 0.32 rg")
        ops.append(f"{px:.2f} {py:.2f} 3.5 3.5 re f")

    ops.append("0 g")
    ops.append("BT /F1 14 Tf")
    ops.append(f"1 0 0 1 {margin:.2f} {page_h - 26:.2f} Tm ({_pdf_escape(name)}) Tj ET")
    ops.append("BT /F1 8 Tf")
    ops.append(
        f"1 0 0 1 {margin:.2f} {page_h - 40:.2f} Tm "
        f"(KIYUB  ·  plan Y-down matches 2D canvas) Tj ET"
    )

    stream = "\n".join(ops).encode("latin-1", "replace")
    return _build_pdf(stream, page_w, page_h)
