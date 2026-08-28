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
    """Check that the uploaded bytes match the declared image type."""
    header = file.read(12)
    file.seek(0)
    signatures = {
        'png': header.startswith(b'\x89PNG\r\n\x1a\n'),
        'jpg': header.startswith(b'\xff\xd8\xff'),
        'jpeg': header.startswith(b'\xff\xd8\xff'),
        'webp': header.startswith(b'RIFF') and header[8:12] == b'WEBP'
    }
    return signatures.get(extension, False)

def parse_receipt_text(text):
    """
    Parse raw receipt/invoice OCR text to accurately extract:
    - Merchant Name
    - Receipt Date (ISO YYYY-MM-DD)
    - Total Amount (INR float)
    - Raw OCR text

    No hardcoded demo values are used.
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

    raw_lines = [l.strip() for l in text.split('\n') if l.strip()]

    # -------------------------------------------------------------
    # 1. MERCHANT EXTRACTION
    # -------------------------------------------------------------
    # Exclude common noise headers, invoice labels, phone/tax IDs
    ignore_merchant_patterns = [
        r'^(tax\s+invoice|invoice|bill|receipt|cash\s+memo|estimate|order|cash\s+receipt)',
        r'^(gstin|gst\s*no|vat\s*no|pan|cin|fssai|tin|cin\s*no)',
        r'^(tel|phone|ph|mobile|fax|email|website|www\.|https?:)',
        r'^(customer\s+copy|duplicate|original|merchant\s+copy)',
        r'^(date|time|table|waiter|cashier|pos|token|bill\s*no|inv\s*no)',
        r'^(welcome|thank\s+you|visit\s+again)',
        r'^[0-9\W_]+$', # Line with only digits or symbols
    ]

    for line in raw_lines:
        line_clean = re.sub(r'[^a-zA-Z0-9\s&\-\'\.,]', '', line).strip()
        if len(line_clean) < 3:
            continue

        # Check against ignore patterns
        should_ignore = False
        for pattern in ignore_merchant_patterns:
            if re.search(pattern, line_clean, re.IGNORECASE):
                should_ignore = True
                break

        # Must contain at least some alphabetic letters
        if not re.search(r'[a-zA-Z]{3,}', line_clean):
            should_ignore = True

        if not should_ignore:
            merchant = line_clean[:100]
            break

    # -------------------------------------------------------------
    # 2. DATE EXTRACTION
    # -------------------------------------------------------------
    # Search for explicit labeled date lines first, then scan full text
    date_candidates = []

    # Look for labeled date lines
    labeled_date_match = re.search(
        r'(?:date|bill\s*date|invoice\s*date|txn\s*date|dated)[\s:]*([0-9]{1,4}[-/.][0-9]{1,2}[-/.][0-9]{1,4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{2,4}|[A-Za-z]{3,9}\s+[0-9]{1,2},?\s+[0-9]{2,4})',
        text,
        re.IGNORECASE
    )
    if labeled_date_match:
        date_candidates.append(labeled_date_match.group(1).strip())

    # Regex for standard numerical dates: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY, MM/DD/YYYY
    numeric_dates = re.findall(r'\b(\d{1,4}[-/.\s]\d{1,2}[-/.\s]\d{1,4})\b', text)
    date_candidates.extend(numeric_dates)

    # Word month dates: 15-Aug-2026, 15 Aug 2026, Aug 15 2026, 15-August-2026
    word_dates = re.findall(
        r'\b(\d{1,2}[-\s/]+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[-\s/]+\d{2,4})\b',
        text,
        re.IGNORECASE
    )
    date_candidates.extend(word_dates)

    month_first_dates = re.findall(
        r'\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})\b',
        text,
        re.IGNORECASE
    )
    date_candidates.extend(month_first_dates)

    date_formats = (
        '%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d',
        '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y',
        '%d-%m-%y', '%d/%m/%y', '%d.%m.%y',
        '%m/%d/%Y', '%m-%d-%Y',
        '%d %b %Y', '%d-%b-%Y', '%d/%b/%Y',
        '%d %B %Y', '%d-%B-%Y', '%d/%B/%Y',
        '%b %d, %Y', '%b %d %Y', '%B %d, %Y', '%B %d %Y',
        '%d %b %y', '%d-%b-%y',
    )

    for cand in date_candidates:
        cand_clean = re.sub(r'[,]', '', cand).strip()
        cand_clean = re.sub(r'\s+', ' ', cand_clean)
        parsed_dt = None
        for fmt in date_formats:
            try:
                parsed_dt = datetime.strptime(cand_clean, fmt)
                # Ensure year is reasonable (between 2000 and 2099)
                if parsed_dt.year < 100:
                    parsed_dt = parsed_dt.replace(year=parsed_dt.year + 2000)
                if 2000 <= parsed_dt.year <= 2099:
                    receipt_date = parsed_dt.strftime('%Y-%m-%d')
                    break
                else:
                    parsed_dt = None
            except ValueError:
                continue
        if parsed_dt:
            break

    # -------------------------------------------------------------
    # 3. TOTAL AMOUNT EXTRACTION
    # -------------------------------------------------------------
    amount_found = None

    # Priority 1: Lines explicitly stating Grand Total / Total Amount / Net Amount / Total / Balance Due
    priority_keywords = [
        r'grand\s*total',
        r'total\s*amount',
        r'net\s*amount',
        r'amount\s*payable',
        r'net\s*payable',
        r'total\s*payable',
        r'final\s*total',
        r'bill\s*total',
        r'balance\s*due',
        r'amount\s*due',
        r'sub\s*total',
        r'total',
    ]

    for kw in priority_keywords:
        pattern = rf'(?:{kw})[\s\:\-\=]*(?:₹|rs\.?|inr)?\s*([0-9]{{1,3}}(?:,[0-9]{{2,3}})*(?:\.[0-9]{{1,2}})?|[0-9]+(?:\.[0-9]{{1,2}})?)(?!\s*[0-9])'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_val = match.group(1).replace(',', '')
            try:
                val = float(raw_val)
                # Avoid selecting 0 or absurd numbers (e.g. phone numbers or invoice numbers with many digits)
                if 0.01 <= val <= 10000000.0:
                    amount_found = val
                    break
            except ValueError:
                continue

    # Priority 2: Lines with Rupee symbols or Rs prefix (e.g. ₹ 1,250.00 or Rs. 560.00)
    if amount_found is None:
        rupee_matches = re.findall(r'(?:₹|rs\.?|inr)\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]{1,2})?|[0-9]+(?:\.[0-9]{1,2})?)', text, re.IGNORECASE)
        for rm in reversed(rupee_matches):
            try:
                val = float(rm.replace(',', ''))
                if 0.01 <= val <= 10000000.0:
                    amount_found = val
                    break
            except ValueError:
                continue

    # Priority 3: Fallback - look for decimal numbers and take the most sensible candidate
    if amount_found is None:
        decimal_matches = re.findall(r'\b([0-9]{1,6}\.[0-9]{2})\b', text)
        valid_decimals = []
        for dm in decimal_matches:
            try:
                val = float(dm)
                if 0.01 <= val <= 10000000.0:
                    valid_decimals.append(val)
            except ValueError:
                continue
        if valid_decimals:
            amount_found = max(valid_decimals)

    if amount_found is not None:
        total_amount = round(amount_found, 2)

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
    - Upscale low-resolution images
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

        # 3. Dynamic scaling: if the image width is under 1200px, upscale with lanczos/bicubic
        w, h = img.size
        if w < 1200 and h < 1200:
            scale = max(2.0, 1200.0 / float(max(w, 1)))
            new_w = int(w * scale)
            new_h = int(h * scale)
            resampling = getattr(Image, 'Resampling', Image).LANCZOS
            img = img.resize((new_w, new_h), resampling)

        # 4. Convert to Grayscale for text extraction
        gray = img.convert('L')

        # 5. Enhance contrast and sharpness
        contrast_enhancer = ImageEnhance.Contrast(gray)
        gray = contrast_enhancer.enhance(1.8)

        sharpness_enhancer = ImageEnhance.Sharpness(gray)
        gray = sharpness_enhancer.enhance(1.5)

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
                if not extracted_text.strip():
                    # Retry with standard psm 3
                    extracted_text = pytesseract.image_to_string(processed_img, config='--oem 3 --psm 3')
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
