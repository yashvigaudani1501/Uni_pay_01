import os
from flask import send_file,session, Blueprint
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from io import BytesIO
from datetime import datetime
import json
from utils.login_required import login_required

txn_bp = Blueprint("txn",__name__)

@txn_bp.route('/download_statement')
@login_required
def download_statement():
    username = session['user']
    
    # ✅ D: DRIVE ABSOLUTE PATH
    base_path = r"D:\Devansh\UniPay\payments_data"
    txn_file = os.path.join(base_path, f"{username}_transactions.json")
    
    print(f"🔍 Looking for: {txn_file}")  # DEBUG
    
    # CHECK FILE
    if not os.path.exists(txn_file):
        print(f"❌ File NOT found: {txn_file}")
        return f"Transactions file not found: {txn_file}", 404
    
    print(f"✅ File FOUND: {txn_file}")
    
    # LOAD JSON
    with open(txn_file, 'r', encoding='utf-8') as f:
        transactions = json.load(f)
    
    # CREATE BANK PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # HEADER
    story.append(Paragraph("🟦 UNIPAY DIGITAL BANK", styles['Title']))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(f"Account Holder: {username.upper()}", styles['Heading2']))
    story.append(Paragraph(f"Statement Date: {datetime.now().strftime('%d %B %Y')}", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # TABLE
    if transactions:
        table_data = [["#", "Date", "Type", "Description", "Debit ₹", "Credit ₹", "Balance ₹"]]
        balance = 0
        
        for i, tx in enumerate(transactions[-20:], 1):
            debit = tx['amount'] if tx.get('type') == 'debit' else 0
            credit = tx['amount'] if tx.get('type') == 'credit' else 0
            balance += credit - debit
            
            table_data.append([
                i,
                tx.get('date', 'N/A'),
                tx.get('type', '').upper(),
                str(tx.get('description', ''))[:25],
                f"{debit:,.0f}",
                f"{credit:,.0f}",
                f"{balance:,.0f}"
            ])
        
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkblue),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 12),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('FONTSIZE', (0,1), (-1,-1), 10),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.lightgrey]),
        ]))
        story.append(table)
    
    doc.build(story)
    buffer.seek(0)
    
    return send_file(buffer, 
                    as_attachment=True, 
                    download_name=f"{username}_statement_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mimetype="application/pdf")
