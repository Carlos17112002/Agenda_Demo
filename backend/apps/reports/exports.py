from decimal import Decimal
from io import BytesIO

import openpyxl
from django.utils import timezone
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _amount(value):
    try:
        return float(Decimal(str(value or 0)))
    except (ArithmeticError, TypeError, ValueError):
        return 0.0


def _clp(value):
    return "$" + f"{_amount(value):,.0f}".replace(",", ".")


def _percent(value):
    return f"{_amount(value):.2f}%"


def _number(value):
    return f"{_amount(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _period(date_from, date_to):
    start = date_from.isoformat() if date_from else "inicio"
    end = date_to.isoformat() if date_to else "hoy"
    return f"{start} a {end}"


def _range_label(sales):
    start = sales["range"]["date_from"] or "inicio"
    end = sales["range"]["date_to"] or "hoy"
    return f"{start} a {end}"


def _context_line(sales, branch, worker):
    parts = [f"Período: {_range_label(sales)}"]
    parts.append(f"Local: {branch.name}" if branch is not None else "Local: todos")
    parts.append(f"Trabajador: {_worker_name(worker)}" if worker is not None else "Trabajador: todos")
    parts.append(f"Generado: {timezone.localtime().strftime('%d-%m-%Y %H:%M')}")
    return " · ".join(parts)


def _worker_name(worker):
    return f"{worker.first_name} {worker.last_name}".strip() or "Sin nombre"


def _summary_rows(sales, cash):
    totals = sales["totals"]
    bookings = totals["bookings"]
    cash_totals = cash["totals"]
    return [
        ("Ventas completadas", str(totals["sales"])),
        ("Subtotal", _clp(totals["subtotal"])),
        ("Descuentos", _clp(totals["discounts"])),
        ("Total vendido", _clp(totals["total"])),
        ("Pagado", _clp(totals["paid"])),
        ("Costo", _clp(totals["cost"])),
        ("Ganancia", _clp(totals["profit"])),
        ("Margen", _percent(totals["margin_percent"])),
        ("Ticket promedio", _clp(totals["average_ticket"])),
        ("Citas agendadas", str(bookings["total"])),
        ("Citas completadas", str(bookings["completed"])),
        ("Citas canceladas", str(bookings["canceled"])),
        ("Citas no asistió", str(bookings["no_show"])),
        ("Sesiones de caja", str(cash_totals["sessions"])),
        ("Ventas en efectivo", _clp(cash_totals["cash_sales"])),
        ("Gastos", _clp(cash_totals["expenses"])),
    ]


WORKER_HEADERS = [
    "Trabajador", "Citas", "Completadas", "Canceladas", "No asistió",
    "Ventas", "Total vendido", "Ganancia",
]


def _worker_rows(sales):
    return [
        [
            row["worker_name"], row["bookings"]["total"], row["bookings"]["completed"],
            row["bookings"]["canceled"], row["bookings"]["no_show"],
            row["sales"], _amount(row["total"]), _amount(row["profit"]),
        ]
        for row in sales["by_worker"]
    ]


def _day_rows(sales):
    return [
        [row["date"], row["sales"], _amount(row["subtotal"]), _amount(row["discounts"]),
         _amount(row["total"]), _amount(row["cost"]), _amount(row["profit"])]
        for row in sales["by_day"]
    ]


def _method_rows(sales):
    return [
        [row["method_display"], row["count"], _amount(row["amount"])]
        for row in sales["by_payment_method"]
    ]


def _branch_rows(sales):
    return [
        [row["branch_name"], row["sales"], _amount(row["subtotal"]),
         _amount(row["discounts"]), _amount(row["total"]), _amount(row["cost"])]
        for row in sales["by_branch"]
    ]


def _top_rows(rows, field):
    return [
        [row[field], row["description"], row["sku"] or "", _amount(row["quantity"]),
         _amount(row["total"]), _amount(row["cost"]), _amount(row["profit"])]
        for row in rows
    ]


def _cash_rows(cash):
    labels = {"open": "Abierta", "closed": "Cerrada"}
    return [
        [row["number"], row["branch_name"], labels.get(row["status"], row["status"]),
         _amount(row["opening_amount"]), _amount(row["cash_sales"]),
         _amount(row["cash_expenses"]), _amount(row["expected"]),
         _amount(row["closing_amount"]), _amount(row["difference"])]
        for row in cash["sessions"]
    ]


def _expense_rows(cash):
    return [[row["category"], _amount(row["total"])] for row in cash["expenses_by_category"]]


def _table(data, widths):
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return table


def build_pdf(*, company, sales, cash, branch, worker):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=14 * mm, rightMargin=14 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
        title=f"Informe {company.name}", author=company.name,
    )
    base = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=base["Title"], fontSize=17, alignment=0, spaceAfter=2,
    )
    meta_style = ParagraphStyle(
        "ReportMeta", parent=base["Normal"], fontSize=8, textColor=colors.HexColor("#475569"),
    )
    heading_style = ParagraphStyle(
        "ReportHeading", parent=base["Heading2"], fontSize=10.5,
        textColor=colors.HexColor("#0F172A"), spaceBefore=2, spaceAfter=1,
    )

    story = [
        Paragraph(f"Informe de {company.name}", title_style),
        Paragraph(_context_line(sales, branch, worker), meta_style),
        Spacer(1, 5 * mm),
        _table([["Concepto", "Valor"], *[list(row) for row in _summary_rows(sales, cash)]],
               widths=[70 * mm, 40 * mm]),
    ]

    sections = [
        ("Por trabajador", WORKER_HEADERS, _worker_rows(sales),
         [34, 13, 20, 20, 20, 14, 24, 22]),
        ("Ventas por día", ["Fecha", "Ventas", "Subtotal", "Descuentos", "Total", "Costo", "Ganancia"],
         _day_rows(sales), [24, 14, 24, 22, 24, 22, 24]),
        ("Métodos de pago", ["Método", "Cantidad", "Monto"], _method_rows(sales), [40, 20, 32]),
        ("Por sucursal", ["Sucursal", "Ventas", "Subtotal", "Descuentos", "Total", "Costo"],
         _branch_rows(sales), [42, 16, 26, 24, 26, 24]),
        ("Top productos", ["Producto", "Descripción", "SKU", "Cantidad", "Total", "Costo", "Ganancia"],
         _top_rows(sales["top_products"], "product"), [24, 58, 22, 18, 22, 20, 22]),
        ("Top servicios", ["Servicio", "Descripción", "SKU", "Cantidad", "Total", "Costo", "Ganancia"],
         _top_rows(sales["top_services"], "service"), [24, 58, 22, 18, 22, 20, 22]),
        ("Caja", ["N°", "Sucursal", "Estado", "Apertura", "Efectivo", "Gastos",
                  "Esperado", "Cierre", "Diferencia"],
         _cash_rows(cash), [14, 36, 18, 22, 22, 18, 22, 22, 20]),
        ("Gastos por categoría", ["Categoría", "Total"], _expense_rows(cash), [60, 32]),
    ]
    for name, headers, rows, widths in sections:
        if not rows:
            continue
        story.extend([
            Spacer(1, 4 * mm),
            Paragraph(name, heading_style),
            Spacer(1, 1.5 * mm),
            _table([headers, *rows], widths=[value * mm for value in widths]),
        ])

    doc.build(story)
    return buffer.getvalue()


def _sheet(workbook, title, headers, rows):
    sheet = workbook.create_sheet(title=title)
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        sheet.append(row)
    for index in range(1, len(headers) + 1):
        sheet.column_dimensions[get_column_letter(index)].width = 20
    sheet.freeze_panes = "A2"
    return sheet


def build_excel(*, company, sales, cash):
    workbook = openpyxl.Workbook()
    summary = workbook.active
    summary.title = "Resumen"
    summary.append(["Informe", company.name])
    summary.append(["Período", _range_label(sales)])
    summary.append(["Local", sales["range"]["branch"] or "todos"])
    summary.append(["Generado", timezone.localtime().strftime("%d-%m-%Y %H:%M")])
    summary.append([])
    summary.append(["Concepto", "Valor"])
    for cell in summary[6]:
        cell.font = Font(bold=True)
    for label, value in _summary_rows(sales, cash):
        summary.append([label, value])
    summary.column_dimensions["A"].width = 28
    summary.column_dimensions["B"].width = 24
    summary.freeze_panes = "A7"

    _sheet(workbook, "Por trabajador", WORKER_HEADERS, _worker_rows(sales))
    _sheet(workbook, "Ventas por día",
           ["Fecha", "Ventas", "Subtotal", "Descuentos", "Total", "Costo", "Ganancia"],
           _day_rows(sales))
    _sheet(workbook, "Métodos de pago", ["Método", "Cantidad", "Monto"], _method_rows(sales))
    _sheet(workbook, "Por sucursal",
           ["Sucursal", "Ventas", "Subtotal", "Descuentos", "Total", "Costo"],
           _branch_rows(sales))
    _sheet(workbook, "Top productos",
           ["Producto", "Descripción", "SKU", "Cantidad", "Total", "Costo", "Ganancia"],
           _top_rows(sales["top_products"], "product"))
    _sheet(workbook, "Top servicios",
           ["Servicio", "Descripción", "SKU", "Cantidad", "Total", "Costo", "Ganancia"],
           _top_rows(sales["top_services"], "service"))
    _sheet(workbook, "Caja",
           ["N°", "Sucursal", "Estado", "Apertura", "Efectivo", "Gastos",
            "Esperado", "Cierre", "Diferencia"],
           _cash_rows(cash))
    _sheet(workbook, "Gastos por categoría", ["Categoría", "Total"], _expense_rows(cash))

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def export_filename(company, sales, extension):
    slug = getattr(company, "slug", "") or "empresa"
    start = sales["range"]["date_from"] or "inicio"
    end = sales["range"]["date_to"] or "hoy"
    return f"informe-{slug}-{start}-{end}.{extension}"
