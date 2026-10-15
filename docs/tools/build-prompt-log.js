// Renders docs/prompt_log.json into docs/SplitStack_Prompt_Log.docx
// Usage: npm run log
const fs = require('fs');
const path = require('path');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, BorderStyle, LevelFormat, Footer, Header, PageNumber, PageBreak,
} = require('docx');

const DOCS = path.join(__dirname, '..');
const log = JSON.parse(fs.readFileSync(path.join(DOCS, 'prompt_log.json'), 'utf8'));
const OUT = path.join(DOCS, 'SplitStack_Prompt_Log.docx');

const ACCENT = '4F46E5';
const MUTED = '5B6475';
const CONTENT_WIDTH = 9638; // A4 width (11906) minus 2 x 1134 margins

const text = (t, opts = {}) => new TextRun({ text: t, ...opts });
const para = (children, opts = {}) => new Paragraph({ children: Array.isArray(children) ? children : [children], ...opts });

function label(name) {
  return para(text(name.toUpperCase(), { bold: true, size: 17, color: ACCENT, characterSpacing: 20 }), { spacing: { before: 160, after: 60 } });
}

function body(t) {
  return para(text(t, { size: 21 }), { spacing: { after: 80 } });
}

function promptBlock(t) {
  return para(text(t, { font: 'Consolas', size: 19 }), {
    shading: { type: ShadingType.CLEAR, fill: 'F1F2F8', color: 'auto' },
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: ACCENT, space: 8 } },
    indent: { left: 160, right: 160 },
    spacing: { before: 40, after: 120, line: 276 },
  });
}

function cell(t, width, { header = false, fill } = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    shading: fill || header ? { type: ShadingType.CLEAR, fill: header ? ACCENT : fill, color: 'auto' } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [para(text(String(t), { size: 18, bold: header, color: header ? 'FFFFFF' : '222222' }))],
  });
}

function table(widths, headers, rows) {
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, widths[i], { header: true })) }),
      ...rows.map((r, ri) => new TableRow({
        children: r.map((v, i) => cell(v, widths[i], { fill: ri % 2 ? 'F7F7FB' : undefined })),
      })),
    ],
  });
}

const entries = log.entries;
const stageNames = Object.keys(log.stages);
const today = entries.length ? entries[entries.length - 1].date : '';

const titlePage = [
  para(text(''), { spacing: { before: 2400 } }),
  para(text(log.project.toUpperCase(), { bold: true, size: 22, color: ACCENT, characterSpacing: 60 })),
  para(text(log.title, { bold: true, size: 52, font: 'Calibri Light' }), { spacing: { before: 120, after: 160 } }),
  para(text(log.subtitle, { size: 24, color: MUTED }), { spacing: { after: 600 } }),
  ...[
    ['Student', log.author],
    ['Assistant', log.assistant],
    ['Repository', log.repository],
    ['Entries logged', String(entries.length)],
    ['Last updated', today],
  ].map(([k, v]) => para([text(`${k}:  `, { bold: true, size: 21 }), text(v, { size: 21 })], { spacing: { after: 60 } })),
  para(new PageBreak()),
];

const overview = [
  para(text('How to read this log'), { heading: HeadingLevel.HEADING_1 }),
  body('Each entry records one step of the refurbishment. "User prompt" entries are the student\'s own messages, quoted verbatim. "Working prompt" entries are the instructions the assistant executed to carry out that step, written so they can be reused to reproduce the work. Every entry lists its purpose, the files it touched, the result and how it was verified.'),
  para(text('Stages'), { heading: HeadingLevel.HEADING_2 }),
  table([2000, 5638, 2000], ['Stage', 'Scope', 'Entries'],
    stageNames.map((s) => [s, log.stages[s], String(entries.filter((e) => e.stage === s).length)])),
  para(text('Summary of entries'), { heading: HeadingLevel.HEADING_2, spacing: { before: 360 } }),
  table([700, 1500, 4538, 1500, 1400], ['#', 'Stage', 'Title', 'Type', 'Date'],
    entries.map((e) => [e.id, e.stage, e.title, e.type, e.date])),
  para(new PageBreak()),
];

const details = [para(text('Detailed log'), { heading: HeadingLevel.HEADING_1 })];
for (const stage of stageNames) {
  const inStage = entries.filter((e) => e.stage === stage);
  if (!inStage.length) continue;
  details.push(para(text(`${stage} - ${log.stages[stage]}`), { heading: HeadingLevel.HEADING_2, spacing: { before: 360 } }));
  for (const e of inStage) {
    details.push(
      para(text(`#${e.id}  ${e.title}`), { heading: HeadingLevel.HEADING_3, keepNext: true }),
      para(text(`${e.type}  |  ${e.date}`, { size: 18, color: MUTED }), { spacing: { after: 60 }, keepNext: true }),
      label('Prompt'),
      promptBlock(e.prompt),
      label('Purpose'), body(e.purpose),
      label('Files'),
      ...(e.files.length ? e.files : ['-']).map((f) => new Paragraph({ numbering: { reference: 'bullets', level: 0 }, children: [text(f, { size: 19, font: 'Consolas' })] })),
      label('Result'), body(e.result),
      label('Verification'), body(e.verification),
      para(text(''), { border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: 'D9DBE5', space: 4 } }, spacing: { after: 200 } }),
    );
  }
}

// Planned prompts that complete the project (not yet executed)
const planned = log.planned || [];
if (planned.length) {
  details.push(
    para(new PageBreak()),
    para(text('Planned prompts to complete the project'), { heading: HeadingLevel.HEADING_1 }),
    body('These prompts have not been run yet. Run them in order; after each one, move it into the log above with its result.'),
  );
  planned.forEach((e, i) => {
    details.push(
      para(text(`P${i + 1}  ${e.title}`), { heading: HeadingLevel.HEADING_3, keepNext: true }),
      para(text(`${e.stage}  |  ${e.type}`, { size: 18, color: MUTED }), { spacing: { after: 60 }, keepNext: true }),
      label('Prompt'),
      promptBlock(e.prompt),
      label('Purpose'), body(e.purpose),
      label('Files'), body(e.files.join(', ')),
    );
  });
}

const doc = new Document({
  creator: log.author,
  title: log.title,
  styles: {
    default: { document: { run: { font: 'Calibri', size: 21 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 34, bold: true, color: '1E2440', font: 'Calibri Light' }, paragraph: { spacing: { before: 240, after: 160 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 27, bold: true, color: ACCENT }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { size: 23, bold: true, color: '1E2440' }, paragraph: { spacing: { before: 240, after: 40 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [{ reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 500, hanging: 260 } } } }] }],
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    headers: { default: new Header({ children: [para(text(`${log.project} - Prompt Log`, { size: 16, color: MUTED }), { alignment: AlignmentType.RIGHT })] }) },
    footers: { default: new Footer({ children: [para([text('Page ', { size: 16, color: MUTED }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: MUTED })], { alignment: AlignmentType.CENTER })] }) },
    children: [...titlePage, ...overview, ...details],
  }],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log(`Wrote ${path.relative(process.cwd(), OUT)} (${entries.length} entries)`);
});
