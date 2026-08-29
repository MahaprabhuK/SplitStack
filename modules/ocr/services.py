# -*- coding: utf-8 -*-
import os
import re
import shutil
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
from database.db import execute_db, query_db

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def _configure_tesseract():
    """Discover and configure Tesseract binary path and tessdata directory."""
    try:
        import pytesseract

        candidate_paths = [
            os.environ.get('TESSERACT_CMD'),
            shutil.which('tesseract'),
            r'C:\Users\Pavithran\AppData\Local\Programs\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            os.path.expanduser(r'~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'),
        ]

        for path in candidate_paths:
            if path and os.path.isfile(path) and os.access(path, os.X_OK):
                pytesseract.pytesseract.tesseract_cmd = path
                tessdata_dir = os.path.join(os.path.dirname(path), 'tessdata')
                if os.path.isdir(tessdata_dir):
                    os.environ['TESSDATA_PREFIX'] = tessdata_dir
                return True, pytesseract
        return False, pytesseract
    except ImportError:
        return False, None


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def valid_image_content(file, extension):
    """Check that the uploaded bytes match the declared image type signature."""
    header = file.read(12)
    file.seek(0)
    signatures = {
        'png': header.startswith(b'\x89PNG\r\n\x1a\n'),
        'jpg': header.startswith(b'\xff\xd8\xff'),
        'jpeg': header.startswith(b'\xff\xd8\xff'),
        'webp': header.startswith(b'RIFF') and header[8:12] == b'WEBP'
    }
    return signatures.get(extension, False)


def _parse_date_string(date_str):
    """Attempt to parse various date formats into ISO YYYY-MM-DD."""
    if not date_str:
        return None
    clean_str = re.sub(r'[,]', '', date_str).strip()
    clean_str = re.sub(r'\s+', ' ', clean_str)

    date_formats = [
        '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',
        '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y',
        '%d-%m-%y', '%d/%m/%y', '%d.%m.%y',
        '%m/%d/%Y', '%m-%d-%Y', '%m.%d.%Y',
        '%d %b %Y', '%d-%b-%Y', '%d/%b/%Y',
        '%d %B %Y', '%d-%B-%Y', '%d/%B/%Y',
        '%b %d %Y', '%b %d, %Y', '%B %d %Y', '%B %d, %Y',
        '%d %b %y', '%d-%b-%y', '%d/%b/%y',
        '%d %B %y', '%d-%B-%y', '%d/%B/%y',
    ]

    for fmt in date_formats:
        try:
            dt = datetime.strptime(clean_str, fmt)
            if dt.year < 100:
                dt = dt.replace(year=dt.year + 2000)
            if 2000 <= dt.year <= 2099:
                return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None


def extract_merchant_name(lines):
    """
    Extract a meaningful merchant/store/business name from OCR lines.
    Returns 'Not detected' if uncertain.
    """
    ignore_patterns = [
        r'^(tax\s+invoice|invoice|bill|receipt|cash\s+memo|estimate|order|cash\s+receipt|retail\s+invoice)',
        r'^(gstin|gst\s*no|vat\s*no|pan|cin|fssai|tin|cin\s*no|reg\s*no|tan\s*no)',
        r'^(tel|phone|ph|mobile|mob|fax|email|website|www\.|https?:|http:)',
        r'^(customer\s+copy|duplicate|original|merchant\s+copy|triplicate)',
        r'^(date|time|table|waiter|cashier|pos|token|bill\s*no|inv\s*no|order\s*no|server)',
        r'^(welcome|thank\s+you|visit\s+again|have\s+a\s+nice\s+day)',
        r'^[0-9\W_]+$',
    ]

    for line in lines[:8]:
        raw_cleaned = re.sub(r'^[\W_]+', '', line).strip()
        raw_cleaned = re.sub(r'[\W_]+$', '', raw_cleaned).strip()
        if len(raw_cleaned) < 3:
            continue

        lower_line = raw_cleaned.lower()

        # Check table header
        if any(h in lower_line for h in ['qty', 'price', 'rate', 'item', 'description', 'particulars']):
            continue

        should_ignore = False
        for pattern in ignore_patterns:
            if re.search(pattern, raw_cleaned, re.IGNORECASE):
                should_ignore = True
                break

        if should_ignore:
            continue

        # Must contain at least some alphabetic word of length >= 3
        if not re.search(r'[a-zA-Z]{3,}', raw_cleaned):
            continue

        # Strip trailing receipt/invoice words from merchant name
        candidate = re.sub(r'\s+(tax\s+invoice|invoice|receipt|bill|cash\s+memo)$', '', raw_cleaned, flags=re.IGNORECASE).strip()
        if candidate and len(candidate) >= 3:
            return candidate[:100]

    return "Not detected"


def extract_receipt_date(text, lines):
    """
    Extract date from OCR text supporting multiple formats:
    DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, DD/MM/YY, DD-MM-YY, YYYY-MM-DD, Word Months.
    Prioritizes labeled date indicators. Does NOT default to today.
    """
    # 1. Search for labeled date lines
    labeled_pattern = r'(?:date|bill\s*date|invoice\s*date|txn\s*date|dated|receipt\s*date|date\s*of\s*issue|onto!|onte!|dt[\.:])\s*[:\-]?\s*([0-9]{1,4}[-/.][0-9]{1,2}[-/.][0-9]{1,4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{2,4}|[A-Za-z]{3,9}\s+[0-9]{1,2},?\s+[0-9]{2,4})'
    labeled_match = re.search(labeled_pattern, text, re.IGNORECASE)
    if labeled_match:
        parsed = _parse_date_string(labeled_match.group(1).strip())
        if parsed:
            return parsed

    # 2. Word month dates (e.g. 25 June 2022, 16 May 2024, 15-Aug-2026, 15 Aug 26)
    word_dates = re.findall(r'\b(\d{1,2}[-\s/]+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-\s/]+\d{2,4})\b', text, re.IGNORECASE)
    for wd in word_dates:
        parsed = _parse_date_string(wd)
        if parsed:
            return parsed

    month_first = re.findall(r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})\b', text, re.IGNORECASE)
    for mf in month_first:
        parsed = _parse_date_string(mf)
        if parsed:
            return parsed

    # 3. Numeric dates across lines
    numeric_dates = re.findall(r'\b(\d{1,4}[-/.]\s*\d{1,2}[-/.]\s*\d{1,4})\b', text)
    for nd in numeric_dates:
        clean_nd = re.sub(r'\s+', '', nd)
        parsed = _parse_date_string(clean_nd)
        if parsed:
            return parsed

    return ""


def extract_total_amount(text, lines):
    """
    Contextual scoring algorithm for total amount extraction.
    Supports INR, Rs, Rs., $, numbers with commas and decimals.
    Prioritizes Grand Total / Total Amount / Amount Payable / Net Total.
    """
    if not text or not text.strip():
        return 0.0

    HIGH_PRIORITY_KWS = [
        'grand total', 'total amount', 'net total', 'total payable',
        'amount payable', 'balance due', 'final total', 'bill total',
        'net payable', 'amount due', 'total amount payable', 'invoice total'
    ]
    MID_PRIORITY_KWS = [
        'totak', 'totai', 'tota1', 'totl', 'toial', 'total',
        'net amount', 'paid amount'
    ]
    SUBTOTAL_KWS = [
        'sub total', 'subtotal', 'sub-total'
    ]

    num_lines = len(lines)
    candidates = []

    for idx, line in enumerate(lines):
        line_lower = line.lower()

        in_table_header = bool(
            re.search(r'\b(qty|quantity|price|rate|desc|description|item|sl|no|particulars)\b', line_lower)
            and 'total' in line_lower
        )

        kw_type = None
        for kw in HIGH_PRIORITY_KWS:
            if kw in line_lower:
                kw_type = 'high'
                break
        if not kw_type:
            for kw in SUBTOTAL_KWS:
                if kw in line_lower:
                    kw_type = 'subtotal'
                    break
        if not kw_type:
            for kw in MID_PRIORITY_KWS:
                if kw in line_lower:
                    kw_type = 'mid'
                    break

        prev_kw_type = None
        if idx > 0:
            prev_lower = lines[idx - 1].lower()
            for kw in HIGH_PRIORITY_KWS:
                if kw in prev_lower:
                    prev_kw_type = 'high'
                    break
            if not prev_kw_type:
                for kw in SUBTOTAL_KWS:
                    if kw in prev_lower:
                        prev_kw_type = 'subtotal'
                        break
            if not prev_kw_type:
                for kw in MID_PRIORITY_KWS:
                    if kw in prev_lower:
                        prev_kw_type = 'mid'
                        break

        # Number pattern matching currency and decimal / comma formatted numbers
        matches = list(re.finditer(
            r'([\$₹€£]|rs\.?|inr)?\s*([0-9]{1,3}(?:,[0-9]{2,3})+(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)',
            line,
            re.IGNORECASE
        ))

        for m in matches:
            curr_sym = m.group(1)
            raw_digits = m.group(2).replace(',', '')
            if not raw_digits:
                continue
            try:
                val = float(raw_digits)
            except ValueError:
                continue

            if val < 0.5 or val > 50000000.0:
                continue

            score = 10.0

            # Position bonus
            pos_ratio = (idx + 1) / max(num_lines, 1)
            score += pos_ratio * 30.0

            # Tax/percentage penalty
            end_pos = m.end()
            if end_pos < len(line) and line[end_pos:end_pos+1] == '%':
                score -= 300.0

            if '%' in line and val < 100 and any(t in line_lower for t in ['gst', 'tax', 'vat', 'cgst', 'sgst']):
                score -= 150.0

            # Table header penalty
            if in_table_header:
                score -= 200.0

            # Keyword bonuses
            if kw_type == 'high':
                score += 200.0
            elif kw_type == 'mid':
                score += 150.0
            elif kw_type == 'subtotal':
                score += 80.0
            elif prev_kw_type == 'high':
                score += 190.0
            elif prev_kw_type == 'mid':
                score += 140.0
            elif prev_kw_type == 'subtotal':
                score += 75.0

            # Phone / Account / Invoice penalty
            if any(term in line_lower for term in ['phone', 'tel', 'mobile', 'account number', 'acc no', 'invoice no', 'inv no', 'gstin']):
                if not (kw_type == 'high' or prev_kw_type == 'high'):
                    score -= 250.0

            # Time penalty
            if re.search(r'\b\d{1,2}:\d{2}\b', line):
                score -= 200.0

            # Currency bonus
            if curr_sym:
                score += 40.0
            elif any(s in line for s in ['$', '₹', 'Rs', 'rs', 'INR', 'inr', '€', '£']):
                score += 25.0

            # Decimal bonus
            if '.' in m.group(2):
                score += 15.0

            candidates.append((score, val, line, kw_type or prev_kw_type))

    if not candidates:
        return 0.0

    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    best = candidates[0]
    if best[0] > 0:
        return round(best[1], 2)
    return 0.0


def parse_receipt_text(text):
    """
    Parse raw receipt/invoice OCR text to accurately extract:
    - Merchant Name
    - Receipt Date (ISO YYYY-MM-DD)
    - Total Amount (float)
    - Raw OCR text

    No hardcoded or mock values are used.
    """
    merchant = "Not detected"
    total_amount = 0.0
    receipt_date = ""

    if not text or not text.strip():
        return {
            'merchant': merchant,
            'total_amount': total_amount,
            'receipt_date': receipt_date,
            'raw_text': text or ''
        }

    lines = [l.strip() for l in text.split('\n') if l.strip()]

    # 1. MERCHANT EXTRACTION
    merchant = extract_merchant_name(lines)

    # 2. DATE EXTRACTION
    receipt_date = extract_receipt_date(text, lines)

    # 3. AMOUNT EXTRACTION
    total_amount = extract_total_amount(text, lines)

    return {
        'merchant': merchant,
        'total_amount': total_amount,
        'receipt_date': receipt_date,
        'raw_text': text
    }


def preprocess_image(image_path):
    """
    Apply Pillow image preprocessing to optimize OCR accuracy:
    - Auto-orient based on EXIF
    - Convert to RGB / Grayscale
    - Dynamic upscaling for low-res receipts (crisp text recognition)
    - Enhance contrast & sharpness
    """
    try:
        from PIL import Image, ImageOps, ImageEnhance

        img = Image.open(image_path)

        # 1. EXIF orientation correction
        img = ImageOps.exif_transpose(img)

        # 2. Convert to RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')

        # 3. Dynamic scaling: upscale if dimensions are small
        w, h = img.size
        if max(w, h) < 1800:
            scale = 1800.0 / float(max(w, h, 1))
            new_w = int(w * scale)
            new_h = int(h * scale)
            resampling = getattr(Image, 'Resampling', Image).LANCZOS
            img = img.resize((new_w, new_h), resampling)

        # 4. Convert to Grayscale for text extraction
        gray = img.convert('L')

        # 5. Enhance contrast and sharpness
        contrast_enhancer = ImageEnhance.Contrast(gray)
        gray = contrast_enhancer.enhance(1.6)

        sharpness_enhancer = ImageEnhance.Sharpness(gray)
        gray = sharpness_enhancer.enhance(1.3)

        return gray
    except Exception as e:
        logger.warning(f"Image preprocessing warning: {e}")
        try:
            from PIL import Image
            return Image.open(image_path)
        except Exception:
            return None


def process_receipt_image(image_path):
    """
    Run OCR on an uploaded receipt image independently.
    Processes the exact image file provided with no caching or static mock data.
    """
    tesseract_ok, pytesseract = _configure_tesseract()
    extracted_text = ""
    engine_name = "Tesseract OCR 5.5"

    if tesseract_ok and pytesseract:
        try:
            processed_img = preprocess_image(image_path)
            if processed_img:
                extracted_text = pytesseract.image_to_string(processed_img, config='--oem 3 --psm 6')
                if not extracted_text.strip() or len(extracted_text.strip()) < 20:
                    text_psm3 = pytesseract.image_to_string(processed_img, config='--oem 3 --psm 3')
                    if len(text_psm3.strip()) > len(extracted_text.strip()):
                        extracted_text = text_psm3
            else:
                extracted_text = pytesseract.image_to_string(image_path)
        except Exception as e:
            logger.error(f"Tesseract execution error on {image_path}: {e}")
            extracted_text = ""
            engine_name = "OCR Error"
    else:
        logger.error("Tesseract OCR binary could not be found.")
        engine_name = "OCR Unavailable"

    logger.info(f"[OCR Process] File: {image_path} | Characters Extracted: {len(extracted_text)}")
    print(f"\n--- [RAW OCR EXTRACTED TEXT for {os.path.basename(image_path)}] ---\n{extracted_text}\n-----------------------------------\n")

    parsed = parse_receipt_text(extracted_text)
    parsed['ocr_engine'] = engine_name
    return parsed
