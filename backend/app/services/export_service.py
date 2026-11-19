import io
import csv
from datetime import datetime, date
from typing import List, Dict, Any
import openpyxl
from openpyxl.utils import get_column_letter
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def export_to_csv(transactions: List[Dict[str, Any]]) -> bytes:
    """Generate CSV file for transactions (FR-091, FR-094). Amounts as plain numbers."""
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ID",
        "Date",
        "Type",
        "Category",
        "Subcategory",
        "Payment Method",
        "Note",
        "Source",
        "Amount (INR)",
    ])

    for tx in transactions:
        writer.writerow([
            tx["id"],
            tx["date"],
            tx["type"],
            tx["category_name"],
            tx.get("subcategory_name") or "",
            tx["payment_method"],
            tx.get("note") or "",
            tx["source"],
            tx["amount"],  # plain integer
        ])

    return output.getvalue().encode("utf-8-sig")


def export_to_xlsx(transactions: List[Dict[str, Any]], summary: Dict[str, Any]) -> bytes:
    """Generate Excel (.xlsx) file with styled table and summary (FR-091, FR-094)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Transactions"

    # Styling definitions
    header_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    data_font = Font(name="Arial", size=9)
    bold_font = Font(name="Arial", size=10, bold=True)
    align_center = Alignment(horizontal="center", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    thin_border = Border(
        left=Side(style="thin", color="E5E7EB"),
        right=Side(style="thin", color="E5E7EB"),
        top=Side(style="thin", color="E5E7EB"),
        bottom=Side(style="thin", color="E5E7EB"),
    )

    # Title & Summary block
    ws.merge_cells("A1:I1")
    title_cell = ws["A1"]
    title_cell.value = "Expense Tracker - Transactions Export"
    title_cell.font = Font(name="Arial", size=14, bold=True, color="1F2937")

    ws["A3"] = "Total Transactions:"
    ws["B3"] = summary["count"]
    ws["A4"] = "Total Income (INR):"
    ws["B4"] = summary["total_income"]
    ws["A5"] = "Total Expense (INR):"
    ws["B5"] = summary["total_expense"]
    ws["A6"] = "Net Savings (INR):"
    ws["B6"] = summary["net"]

    for row in range(3, 7):
        ws[f"A{row}"].font = bold_font
        ws[f"B{row}"].font = data_font

    # Column Headers
    headers = [
        "ID",
        "Date",
        "Type",
        "Category",
        "Subcategory",
        "Payment Method",
        "Note",
        "Source",
        "Amount (INR)",
    ]
    start_row = 8
    for col_idx, h_text in enumerate(headers, start=1):
        c = ws.cell(row=start_row, column=col_idx, value=h_text)
        c.fill = header_fill
        c.font = header_font
        c.alignment = align_center

    # Data Rows
    current_row = start_row + 1
    for tx in transactions:
        ws.cell(row=current_row, column=1, value=tx["id"]).alignment = align_center
        ws.cell(row=current_row, column=2, value=str(tx["date"])).alignment = align_center
        ws.cell(row=current_row, column=3, value=tx["type"].title()).alignment = align_center
        ws.cell(row=current_row, column=4, value=tx["category_name"])
        ws.cell(row=current_row, column=5, value=tx.get("subcategory_name") or "-")
        ws.cell(row=current_row, column=6, value=tx["payment_method"]).alignment = align_center
        ws.cell(row=current_row, column=7, value=tx.get("note") or "-")
        ws.cell(row=current_row, column=8, value=tx["source"].title()).alignment = align_center
        amt_cell = ws.cell(row=current_row, column=9, value=tx["amount"])
        amt_cell.alignment = align_right

        for c_idx in range(1, 10):
            cell = ws.cell(row=current_row, column=c_idx)
            cell.font = data_font
            cell.border = thin_border

        current_row += 1

    # Column width auto-fit
    for col_idx, col in enumerate(ws.columns, start=1):
        max_len = 0
        col_letter = get_column_letter(col_idx)
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_to_pdf(transactions: List[Dict[str, Any]], summary: Dict[str, Any], username: str) -> bytes:
    """
    Generate PDF with transactions table and summary (FR-093).
    No charts in PDF. Clean, printable tabular format.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )
    story = []
    styles = getSampleStyleSheet()

    # Title style
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1A1A1A"),
    )

    meta_style = ParagraphStyle(
        "DocMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#6B6A66"),
    )

    story.append(Paragraph("Expense Tracker - Transactions Report", title_style))
    story.append(Spacer(1, 4))
    story.append(
        Paragraph(
            f"Generated for: <b>{username}</b> | Exported on: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            meta_style,
        )
    )
    story.append(Spacer(1, 14))

    # Summary Box Table
    summary_data = [
        ["Total Income", "Total Expense", "Net Balance", "Transactions Count"],
        [
            f"INR {summary['total_income']:,}",
            f"INR {summary['total_expense']:,}",
            f"INR {summary['net']:,}",
            str(summary["count"]),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[130, 130, 130, 130])
    summary_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F2F1ED")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1A1A1A")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 1), (-1, 1), 11),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E4E2DC")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E4E2DC")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(summary_table)
    story.append(Spacer(1, 18))

    # Transactions Table
    table_headers = ["Date", "Type", "Category", "Method", "Note", "Amount (INR)"]
    table_rows = [table_headers]

    for tx in transactions:
        note_str = (tx.get("note") or "")[:25]
        cat_disp = tx["category_name"]
        if tx.get("subcategory_name"):
            cat_disp += f" > {tx['subcategory_name']}"
        cat_disp = cat_disp[:20]

        amt_prefix = "+" if tx["type"] == "income" else "-"
        table_rows.append([
            str(tx["date"]),
            tx["type"].title(),
            cat_disp,
            tx["payment_method"],
            note_str,
            f"{amt_prefix}{tx['amount']:,}",
        ])

    tx_table = Table(
        table_rows,
        colWidths=[65, 55, 120, 60, 130, 90],
        repeatRows=1,
    )

    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#151518")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (1, -1), "CENTER"),
        ("ALIGN", (2, 0), (4, -1), "LEFT"),
        ("ALIGN", (5, 0), (5, -1), "RIGHT"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#E4E2DC")),
    ]

    # Alternate row colors
    for r_idx in range(1, len(table_rows)):
        if r_idx % 2 == 0:
            t_style.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#FAFAF8")))

    tx_table.setStyle(TableStyle(t_style))
    story.append(tx_table)

    doc.build(story)
    return buf.getvalue()
