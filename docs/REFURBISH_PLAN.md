# SplitStack Refurbishment Plan

The course requires **HTML + CSS** (Review 1), **JavaScript** (Review 2) and **Node.js + MongoDB** (Review 3).
The original SplitStack was built with Python/Flask + SQLite and Jinja templates, so it is being rebuilt on
the `refurbish` branch. The Flask version is preserved on the `legacy` branch.

Every step is recorded in [`SplitStack_Prompt_Log.docx`](SplitStack_Prompt_Log.docx) (source: `prompt_log.json`, rebuild with `npm run log`).

## Decisions

| Topic | Decision |
|---|---|
| Backend | Replace Flask with Express + Mongoose; Flask kept on `legacy` |
| Database | MongoDB Atlas free tier (connection string in `server/.env`) |
| Scope | Keep every feature, including receipt OCR (tesseract.js) and the spending forecast |
| Frontend JS | Vanilla ES modules, no jQuery |

## Layout

```
client/            static site: index.html, pages/*.html, css/, js/, assets/
server/            Express API + Mongoose models (Review 3)
docs/              plan, prompt log, tools
legacy files       app.py, modules/, templates/ ... removed at wrap-up (still on `legacy`)
```

## Review 1 - HTML + CSS
- Standalone semantic HTML pages that open from disk with realistic sample data: landing, login, register,
  dashboard, expenses (+form), income (+form), budgets, recurring, categories, groups, group detail, create group,
  shared expense form, settlements, shopping lists (+form, detail), analytics, receipt scan, receipt confirm,
  profile, 404.
- CSS split into cascade layers: tokens, base, layout, components, pages, utilities.
- Dark and light themes from one token set (`prefers-color-scheme` + `[data-theme]` hook for Review 2).
- Audit fixes: muted-text contrast >= 4.5:1, tables become cards under 640px, complete light theme,
  visible focus styles, ARIA landmarks/labels.
- CSS-only charts (conic-gradient doughnut, flex bar chart) and a CSS-only mobile drawer (checkbox + `:has()`).
- HTML5 form validation attributes (`required`, `min`, `step`, `pattern`, `type=email`).

## Review 2 - JavaScript
- ES modules: theme (no flash), navigation drawer with `aria-expanded`, toasts, confirm dialogs.
- Form validation with inline messages; live custom-split total; receipt drag-and-drop preview.
- Chart.js charts, budget gauges, shopping checklist, global search, notifications drawer.
- Debt simplification (greedy min-cash-flow) and spending forecast ported to JS.
- `api.js` data layer backed by `localStorage` with seed data, so the whole app works without a server.

## Review 3 - Node.js + MongoDB
- Express app, Mongoose models (users, categories, expenses, incomes, budgets, recurring, groups with embedded
  members, sharedExpenses with embedded shares, settlements, shoppingLists with embedded items, receipts, insights).
- REST API covering all 48 legacy routes; express-session + connect-mongo; bcrypt; helmet; express-rate-limit; CSRF.
- Receipt upload with multer + tesseract.js OCR; seed script; Jest + Supertest + mongodb-memory-server tests.
- `api.js` switched from `localStorage` to `fetch()`.

## Wrap-up
- Remove the Flask code from `refurbish` (kept on `legacy`), new README with setup and data model,
  optional Render + Atlas deployment.
