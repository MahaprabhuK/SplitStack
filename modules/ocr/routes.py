from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file, abort, current_app
from modules.auth.utils import login_required
from modules.ocr.services import allowed_file, process_receipt_image, valid_image_content
from modules.finance.services import add_expense, get_categories, validate_category
from database.db import execute_db, query_db
import os
import uuid

ocr_bp = Blueprint('ocr', __name__, template_folder='../../templates')

@ocr_bp.route('/receipt-scan', methods=['GET', 'POST'])
@login_required
def receipt_scan():
    """Upload receipt image for OCR extraction."""
    if request.method == 'POST':
        if 'receipt_file' not in request.files:
            flash('No receipt file selected.', 'danger')
            return redirect(request.url)

        file = request.files['receipt_file']
        if file.filename == '':
            flash('Please select an image file to upload.', 'danger')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            if not valid_image_content(file, ext):
                flash('The uploaded file is not a valid receipt image.', 'danger')
                return redirect(request.url)
            unique_filename = f"{uuid.uuid4().hex}.{ext}"
            upload_dir = os.path.join(current_app.root_path, 'uploads', 'receipts')
            os.makedirs(upload_dir, exist_ok=True)
            save_path = os.path.join(upload_dir, unique_filename)
            file.save(save_path)

            # Process OCR
            parsed_data = process_receipt_image(save_path)
            user_id = session['user_id']
            categories = get_categories(user_id, cat_type='expense')

            # Save in receipts table
            receipt_id = execute_db("""
                INSERT INTO receipts (user_id, image_path, merchant, total_amount, receipt_date, raw_ocr_text, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'scanned')
            """, (user_id, os.path.relpath(save_path, current_app.root_path), parsed_data['merchant'], parsed_data['total_amount'], parsed_data['receipt_date'], parsed_data['raw_text']))

            flash(f"Receipt scanned with {parsed_data['ocr_engine']}! Please verify and confirm before saving.", 'success')
            return render_template(
                'finance/receipt_confirm.html',
                data=parsed_data,
                image_url=url_for('ocr.receipt_image', receipt_id=receipt_id),
                categories=categories
            )
        else:
            flash('Invalid file format. Allowed formats: PNG, JPG, JPEG, WEBP.', 'danger')

    return render_template('finance/receipt_scan.html')

@ocr_bp.route('/receipt-scan/image/<int:receipt_id>')
@login_required
def receipt_image(receipt_id):
    receipt = query_db(
        "SELECT image_path FROM receipts WHERE id = %s AND user_id = %s",
        (receipt_id, session['user_id']), one=True
    )
    if not receipt:
        abort(404)
    image_path = os.path.abspath(os.path.join(current_app.root_path, receipt['image_path']))
    if not image_path.startswith(os.path.abspath(os.path.join(current_app.root_path, 'uploads', 'receipts')) + os.sep) or not os.path.isfile(image_path):
        abort(404)
    return send_file(image_path)

@ocr_bp.route('/receipt-scan/confirm', methods=['POST'])
@login_required
def confirm_receipt_expense():
    """User confirms and saves extracted receipt data as an expense."""
    user_id = session['user_id']
    amount = request.form.get('amount')
    description = request.form.get('description', 'Receipt Purchase')
    category_id = request.form.get('category_id')
    expense_date = request.form.get('expense_date')
    payment_method = request.form.get('payment_method', 'upi')

    cat_id, category_error = validate_category(user_id, category_id, 'expense')
    if category_error:
        flash(category_error, 'danger')
        return redirect(url_for('ocr.receipt_scan'))
    exp_id, err = add_expense(user_id, cat_id, amount, description, expense_date, payment_method)
    if err:
        flash(err, 'danger')
        return redirect(url_for('ocr.receipt_scan'))

    flash('Expense confirmed and added from receipt successfully!', 'success')
    return redirect(url_for('finance.expenses'))
