"""Render docs/prompt_log.json into docs/SplitStack_Prompt_Log.pdf.

Usage: python docs/tools/build_prompt_pdf.py   (needs: pip install reportlab)
Contains every executed prompt plus the planned prompts that complete the project.
"""
import json
import os
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

DOCS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(DOCS, 'prompt_log.json')
OUT = os.path.join(DOCS, 'SplitStack_Prompt_Log.pdf')

ACCENT = colors.HexColor('#4F46E5')
INK = colors.HexColor('#1E2440')
MUTED = colors.HexColor('#5B6475')
SOFT = colors.HexColor('#F1F2F8')
PLANNED = colors.HexColor('#B45309')


def register_fonts():
    fonts = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
    try:
        pdfmetrics.registerFont(TTFont('Body', os.path.join(fonts, 'calibri.ttf')))
        pdfmetrics.registerFont(TTFont('Body-Bold', os.path.join(fonts, 'calibrib.ttf')))
        pdfmetrics.registerFont(TTFont('Mono', os.path.join(fonts, 'consola.ttf')))
        pdfmetrics.registerFontFamily('Body', normal='Body', bold='Body-Bold')
        return 'Body', 'Body-Bold', 'Mono'
    except Exception:  # non-Windows fallback
        return 'Helvetica', 'Helvetica-Bold', 'Courier'


BODY, BOLD, MONO = register_fonts()

S = {
    'kicker': ParagraphStyle('kicker', fontName=BOLD, fontSize=11, textColor=ACCENT, spaceAfter=6),
    'title': ParagraphStyle('title', fontName=BOLD, fontSize=28, leading=33, textColor=INK, spaceAfter=10),
    'subtitle': ParagraphStyle('subtitle', fontName=BODY, fontSize=13, leading=17, textColor=MUTED, spaceAfter=28),
    'meta': ParagraphStyle('meta', fontName=BODY, fontSize=11, leading=16, textColor=INK),
    'h1': ParagraphStyle('h1', fontName=BOLD, fontSize=19, leading=23, textColor=INK, spaceBefore=6, spaceAfter=10),
    'h2': ParagraphStyle('h2', fontName=BOLD, fontSize=14, leading=18, textColor=ACCENT, spaceBefore=14, spaceAfter=6),
    'h3': ParagraphStyle('h3', fontName=BOLD, fontSize=12, leading=15, textColor=INK, spaceBefore=12, spaceAfter=2),
    'small': ParagraphStyle('small', fontName=BODY, fontSize=9, leading=12, textColor=MUTED, spaceAfter=4),
    'label': ParagraphStyle('label', fontName=BOLD, fontSize=8, leading=10, textColor=ACCENT, spaceBefore=6, spaceAfter=2),
    'body': ParagraphStyle('body', fontName=BODY, fontSize=10.5, leading=14, textColor=colors.HexColor('#222222'), alignment=TA_LEFT),
    'prompt': ParagraphStyle('prompt', fontName=MONO, fontSize=9, leading=12.5, textColor=colors.HexColor('#1F2937')),
    'cell': ParagraphStyle('cell', fontName=BODY, fontSize=9, leading=11.5),
    'cellh': ParagraphStyle('cellh', fontName=BOLD, fontSize=9, leading=11.5, textColor=colors.white),
}


def p(text, style):
    return Paragraph(escape(str(text)), S[style])


def prompt_box(text):
    t = Table([[Paragraph(escape(text), S['prompt'])]], colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), SOFT),
        ('LINEBEFORE', (0, 0), (0, -1), 3, ACCENT),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def grid(widths, header, rows):
    data = [[Paragraph(escape(h), S['cellh']) for h in header]]
    data += [[Paragraph(escape(str(c)), S['cell']) for c in r] for r in rows]
    t = Table(data, colWidths=[w * mm for w in widths], repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), ACCENT),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F7F7FB')]),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#D9DBE5')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t


def entry_block(e, label):
    head = [
        p(f"{label}  {e['title']}", 'h3'),
        p(f"{e['type']}" + (f"  |  {e['date']}" if e.get('date') else ''), 'small'),
        p('PROMPT', 'label'),
        prompt_box(e['prompt']),
    ]
    rest = [p('PURPOSE', 'label'), p(e['purpose'], 'body')]
    if e.get('files'):
        rest += [p('FILES', 'label'), Paragraph(escape(', '.join(e['files'])), S['small'])]
    if 'result' in e:
        rest += [p('RESULT', 'label'), p(e['result'], 'body')]
    if 'verification' in e:
        rest += [p('VERIFICATION', 'label'), p(e['verification'], 'body')]
    return [KeepTogether(head), *rest, Spacer(1, 8)]


def on_page(canvas, doc):
    canvas.saveState()
    canvas.setFont(BODY, 8.5)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(A4[0] - 20 * mm, A4[1] - 12 * mm, 'SplitStack - Prompt Log')
    canvas.drawCentredString(A4[0] / 2, 10 * mm, f'Page {doc.page}')
    canvas.restoreState()


def main():
    log = json.load(open(SRC, encoding='utf-8'))
    entries, planned = log['entries'], log.get('planned', [])
    story = [
        Spacer(1, 50 * mm),
        p(log['project'].upper(), 'kicker'),
        p(log['title'], 'title'),
        p('All prompts used to analyse, plan and rebuild SplitStack, plus the planned prompts that complete the project.', 'subtitle'),
    ]
    for k, v in [('Student', log['author']), ('Assistant', log['assistant']), ('Repository', log['repository']),
                 ('Executed prompts', len(entries)), ('Planned prompts', len(planned)),
                 ('Last updated', entries[-1]['date'])]:
        story.append(Paragraph(f'<b>{escape(k)}:</b>  {escape(str(v))}', S['meta']))
    story.append(PageBreak())

    story += [p('How to read this log', 'h1'),
              p('Part A lists every step already carried out, in order. "User prompt" entries are the student\'s own messages, '
                'quoted verbatim; "Working prompt" entries are the instructions executed for that step, written so they can be reused. '
                'Part B lists the planned prompts that complete Review 2, Review 3 and the wrap-up; they have not been run yet and '
                'are marked "Planned prompt".', 'body'),
              p('Stages', 'h2'),
              grid([30, 115, 25], ['Stage', 'Scope', 'Prompts'],
                   [[s, d, len([e for e in entries + planned if e['stage'] == s])] for s, d in log['stages'].items()]),
              p('Summary', 'h2'),
              grid([12, 24, 92, 26, 16], ['#', 'Stage', 'Title', 'Type', 'Status'],
                   [[e['id'], e['stage'], e['title'], e['type'], 'Done'] for e in entries]
                   + [[f'P{i}', e['stage'], e['title'], e['type'], 'Planned'] for i, e in enumerate(planned, 1)]),
              PageBreak()]

    story.append(p('Part A - Executed prompts', 'h1'))
    for stage in log['stages']:
        group = [e for e in entries if e['stage'] == stage]
        if group:
            story.append(p(f"{stage} - {log['stages'][stage]}", 'h2'))
            for e in group:
                story += entry_block(e, f"#{e['id']}")

    if planned:
        story += [PageBreak(), p('Part B - Planned prompts to complete the project', 'h1'),
                  p('Run these in order. Each builds on the previous one; after each, add a log entry and rebuild this document.', 'body')]
        n = 0
        for stage in log['stages']:
            group = [e for e in planned if e['stage'] == stage]
            if group:
                story.append(p(f"{stage} - {log['stages'][stage]}", 'h2'))
                for e in group:
                    n += 1
                    story += entry_block(e, f'P{n}')

    doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                            bottomMargin=18 * mm, title=log['title'], author=log['author'])
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f'Wrote {OUT} ({len(entries)} executed + {len(planned)} planned)')


if __name__ == '__main__':
    main()
