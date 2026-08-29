# -*- coding: utf-8 -*-
import io
import os
import unittest
from datetime import datetime
from PIL import Image

from app import create_app
from database.db import query_db
from modules.auth.utils import get_csrf_token
from modules.ocr.services import (
    allowed_file,
    valid_image_content,
    parse_receipt_text,
    extract_merchant_name,
    extract_receipt_date,
    extract_total_amount,
    process_receipt_image
)


class ReceiptOCRUnitTests(unittest.TestCase):
    """Unit and Integration tests for the Receipt OCR Pipeline."""

    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_file_extension_validation(self):
        """Test allowed and disallowed file extensions."""
        self.assertTrue(allowed_file('receipt.png'))
        self.assertTrue(allowed_file('invoice.jpg'))
        self.assertTrue(allowed_file('bill.jpeg'))
        self.assertTrue(allowed_file('scan.webp'))
        self.assertFalse(allowed_file('document.pdf'))
        self.assertFalse(allowed_file('script.py'))
        self.assertFalse(allowed_file('executable.exe'))
        self.assertFalse(allowed_file('noextension'))

    def test_image_header_signature_validation(self):
        """Test magic byte signatures for image formats."""
        png_bytes = io.BytesIO(b'\x89PNG\r\n\x1a\n' + b'valid_png_content')
        jpg_bytes = io.BytesIO(b'\xff\xd8\xff' + b'valid_jpg_content')
        webp_bytes = io.BytesIO(b'RIFF\x00\x00\x00\x00WEBPVP8 ')
        fake_png = io.BytesIO(b'<!DOCTYPE html><html>')

        self.assertTrue(valid_image_content(png_bytes, 'png'))
        self.assertTrue(valid_image_content(jpg_bytes, 'jpg'))
        self.assertTrue(valid_image_content(jpg_bytes, 'jpeg'))
        self.assertTrue(valid_image_content(webp_bytes, 'webp'))
        self.assertFalse(valid_image_content(fake_png, 'png'))

    def test_merchant_name_extraction(self):
        """Test merchant extraction across different invoice styles."""
        # 1. Clean company name with noise header
        lines1 = [
            'TAX INVOICE',
            'FabIndia Overseas Pvt Ltd',
            'Brigade Road, Bengaluru',
            'GSTIN: 29AAAAA0000A1Z5'
        ]
        self.assertEqual(extract_merchant_name(lines1), 'FabIndia Overseas Pvt Ltd')

        # 2. Leading symbols & trailing INVOICE
        lines2 = [
            '\\)) STUDIO SHODWE INVOICE',
            'CREATIVE AGENCY',
            'REALLYGREATSITE.COM'
        ]
        self.assertEqual(extract_merchant_name(lines2), 'STUDIO SHODWE')

        # 3. Clean restaurant name
        lines3 = [
            'Sriganda Palace',
            'Service Rd, Bengaluru'
        ]
        self.assertEqual(extract_merchant_name(lines3), 'Sriganda Palace')

        # 4. Unknown/empty noise
        lines4 = [
            'TAX INVOICE',
            'GSTIN: 29AAAAA0000A1Z5',
            'TEL: 9876543210',
            '12345678'
        ]
        self.assertEqual(extract_merchant_name(lines4), 'Not detected')

    def test_date_extraction_formats(self):
        """Test date parsing for multiple standard formats."""
        # DD/MM/YYYY
        text1 = "Date: 18/08/2026\nGrand Total: 4599.50"
        self.assertEqual(extract_receipt_date(text1, text1.split('\n')), '2026-08-18')

        # YYYY-MM-DD
        text2 = "Bill Date: 2026-08-20\nTotal: 18499.00"
        self.assertEqual(extract_receipt_date(text2, text2.split('\n')), '2026-08-20')

        # Word month (DD-Mon-YYYY)
        text3 = "Dated: 25-Aug-2026\nAmount: 745.00"
        self.assertEqual(extract_receipt_date(text3, text3.split('\n')), '2026-08-25')

        # Word month (DD Month YYYY)
        text4 = "Ketut Susilo 25 June 2022\nInvoice 12345"
        self.assertEqual(extract_receipt_date(text4, text4.split('\n')), '2022-06-25')

        # DD.MM.YYYY
        text5 = "Invoice Date: 05.12.2025\nTotal: 1200"
        self.assertEqual(extract_receipt_date(text5, text5.split('\n')), '2025-12-05')

        # No date present (must return empty string, NOT today)
        text6 = "Store Receipt\nTotal Amount: 500"
        self.assertEqual(extract_receipt_date(text6, text6.split('\n')), '')

    def test_amount_contextual_scoring(self):
        """Test amount extraction using contextual priority scoring."""
        # Indian Rupee symbol with Grand Total
        text_inr = """
        FabIndia Overseas Pvt Ltd
        Date: 18/08/2026
        Cotton Kurta 1 2499.50 2499.50
        Silk Scarf 1 1500.00 1500.00
        Sub Total: 4599.50
        CGST 2.5%: 114.99
        SGST 2.5%: 114.99
        GRAND TOTAL: Rs. 4,599.50
        Thank you!
        """
        self.assertEqual(extract_total_amount(text_inr, [l.strip() for l in text_inr.split('\n') if l.strip()]), 4599.50)

        # Dollar Grand Total with line item numbers
        text_usd = """
        NO DESCRIPTION QTY PRICE TOTAL
        1 Logo Design 5 $100 $500
        2 Website Design 2 $800 $1600
        Sub Total : $7,650
        Tax 15%: $1,148
        PAYMENT METHOD : GRAND TOTAL: $8,798
        Account Number : 123-456-7890
        """
        self.assertEqual(extract_total_amount(text_usd, [l.strip() for l in text_usd.split('\n') if l.strip()]), 8798.00)

        # Multi-line wrap total
        text_wrap = """
        Sub-Total: 3000.00
        SGST 2.5%: 75.00
        Mode: Cash Totak &
        3250
        Time: 22:18
        """
        self.assertEqual(extract_total_amount(text_wrap, [l.strip() for l in text_wrap.split('\n') if l.strip()]), 3250.00)

    def test_three_different_invoices_produce_different_correct_results(self):
        """Verify that at least three distinct invoice images produce distinct, accurate OCR outputs."""
        inv1 = 'uploads/receipts/156f0765df7c431db2602a25622ef20a.png'
        inv2 = 'uploads/receipts/1d1b930e6dc14f83a81140551c613f1d.png'
        inv3 = 'uploads/receipts/test_invoice_3_fabindia.png'

        self.assertTrue(os.path.exists(inv1), f"Missing test invoice: {inv1}")
        self.assertTrue(os.path.exists(inv2), f"Missing test invoice: {inv2}")
        self.assertTrue(os.path.exists(inv3), f"Missing test invoice: {inv3}")

        res1 = process_receipt_image(inv1)
        res2 = process_receipt_image(inv2)
        res3 = process_receipt_image(inv3)

        # Verify results are distinct
        self.assertNotEqual(res1['merchant'], res2['merchant'])
        self.assertNotEqual(res2['merchant'], res3['merchant'])
        self.assertNotEqual(res1['merchant'], res3['merchant'])

        self.assertNotEqual(res1['total_amount'], res2['total_amount'])
        self.assertNotEqual(res2['total_amount'], res3['total_amount'])
        self.assertNotEqual(res1['total_amount'], res3['total_amount'])

        # Verify exact parsed values
        self.assertEqual(res1['merchant'], 'STUDIO SHODWE')
        self.assertEqual(res1['receipt_date'], '2022-06-25')
        self.assertEqual(res1['total_amount'], 8798.0)

        self.assertEqual(res2['merchant'], 'Sriganda Palace')
        self.assertEqual(res2['receipt_date'], '2024-05-16')
        self.assertEqual(res2['total_amount'], 3250.0)

        self.assertEqual(res3['merchant'], 'FabIndia Overseas Pvt Ltd')
        self.assertEqual(res3['receipt_date'], '2026-08-18')
        self.assertEqual(res3['total_amount'], 4599.50)

    def test_image_format_support_png_jpg_webp(self):
        """Test that OCR processes PNG, JPG, and WEBP image formats successfully."""
        png_file = 'uploads/receipts/test_invoice_3_fabindia.png'
        jpg_file = 'uploads/receipts/test_invoice_4_croma.jpg'
        webp_file = 'uploads/receipts/test_invoice_5_cafe.webp'

        res_png = process_receipt_image(png_file)
        self.assertEqual(res_png['merchant'], 'FabIndia Overseas Pvt Ltd')
        self.assertEqual(res_png['total_amount'], 4599.50)

        res_jpg = process_receipt_image(jpg_file)
        self.assertEqual(res_jpg['merchant'], 'CROMA ELECTRONICS MEGASTORE')
        self.assertEqual(res_jpg['total_amount'], 18499.00)

        res_webp = process_receipt_image(webp_file)
        self.assertEqual(res_webp['merchant'], 'Blue Leaf Cafe & Roastery')
        self.assertEqual(res_webp['total_amount'], 745.00)


if __name__ == '__main__':
    unittest.main()
