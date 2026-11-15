# Changelog

All notable changes to this project are recorded here. Format based on [Keep a Changelog](https://keepachangelog.com/).

## [0.2.0] — 2026-11-17

Changes asked for after the demonstration (product review + teacher's comments).

### Added — backend

- Two-step verification by email code (OTP): `POST /auth/register` emails a code and the account is created by `POST /auth/register/verify` (which also signs the user in); `POST /auth/login` emails a code that is checked by `POST /auth/login/verify`; `POST /auth/resend-code`. Codes are 6 digits, stored hashed, expire after 10 minutes and stop working after 5 wrong tries. SMTP settings in `.env`; without them the API runs in demo mode and returns the code. `TWO_FACTOR_ENABLED` switches it off.
- AI folder recommendation (`services/recommend.py`): `GET /documents/{id}/analysis` returns `folder_recommendations` — the user's existing folders ranked by similar documents, folder-name match and the AI's own path, each with a reason; a new folder is only suggested when nothing fits.
- Folder rename (`PATCH /folders/{id}`), delete (`DELETE /folders/{id}`, documents go to the Recycle bin) and AI summary of a folder and its subfolders (`GET /folders/{id}/summary`, offline or OpenAI)
- Recycle bin: `POST /documents/{id}/trash`, `POST /documents/{id}/restore` (re-creates the original folder), `GET /trash`, `DELETE /trash`; new file status `DELETED` and columns `files.deleted_at`, `files.deleted_from_path`
- AI search also returns matching `folders` (by folder name and by where the best results are)
- `sort=updated_at` for `GET /documents`; `in_recycle_bin` in dashboard stats; `two_factor_enabled` / `email_configured` in `/health`
- Automatic database upgrade (`app/upgrade.py`): older databases get the new columns and status on the first request or with `flask init-db` — no data is lost
- 19 new backend tests (99 in total)

### Added — frontend

- Sign-in and sign-up code step (`VerificationCodeStep`), resend with countdown, demo-mode banner
- OneDrive-style sidebar with "+ Create or upload", **Home**, **My files**, **Recycle bin**
- **My files** explorer (`/files`): breadcrumb, folders and files together, list or tiles view, filter by name, sort, ⋯ menu (open, download, rename, delete, summarise), new folder
- **Home**: AI search box, **Your folders** tiles with "AI summary", **Recent files** list with filter and actions
- **Recycle bin** page (`/recycle-bin`): restore, delete for good, empty bin
- Review page: **AI suggested folder** card (best existing folder pre-selected); upload page shows the suggested folder
- AI Search shows matching **folders** with an Open button
- 8 new frontend tests (93 in total)

### Changed

- Deleting a document from the app now moves it to the Recycle bin (discarding an upload in review still deletes it at once)
- The old "All Folders" page is replaced by My files (`/folders` links redirect)

## [0.1.0] — 2026-10-30

First working version of the application.

### Added — backend (Flask)

- Registration and login with FR-01 password rules, BCrypt hashing, JWT (30 min), lockout after 5 failed logins
- Upload of PDF, DOCX, TXT, PNG and JPG with content-type check, size limit, integrity check and storage quota
- Exact duplicate detection (SHA-256, per user) with "upload anyway" option
- Background processing pipeline: PyMuPDF, python-docx, Tesseract OCR (optional) and plain-text extraction; scanned-PDF OCR fallback; automatic recovery of interrupted jobs
- Offline AI analyser: category, document type, title, summary, keywords, filename and folder suggestions (reuses the user's existing folders)
- Optional OpenAI GPT analysis with output validation and automatic fallback; optional OpenAI or Sentence-Transformers embeddings
- Similar-document detection using embeddings
- Natural-language search (semantic + keyword ranking) with a per-user in-memory index
- Review and approve flow, edit / rename / move, folders, categories, dashboard statistics, profile and password change
- Local or AWS S3 file storage with short-lived signed download links
- Audit log for logins, uploads, approvals, views, downloads, edits, deletes and searches
- CLI commands: `init-db`, `seed-demo` (demo account with 9 sample documents), `reindex`
- 80 automated backend tests (86% coverage)

### Added — frontend (React)

- Login, registration with live password checklist, dashboard, upload with drag-and-drop and progress, AI review page, review queue, natural-language search, documents list, document details with preview, folders, categories, profile and settings
- Responsive layout with off-canvas sidebar on phones; automatic sign-out when the session expires
- 85 automated tests (Vitest + React Testing Library)

### Added — tooling

- `setup.bat` (one-time Windows setup) and `start-dev.bat` (starts both servers and opens the browser)

### Changed — documentation

- API specification updated to the implemented v1.0 endpoints
- Architecture: AI providers, search design and technical decisions recorded
- Database design: duplicate columns on `document_metadata`, keyword order, `FULLTEXT` index removed
- Testing strategy: test results, AI evaluation and measured response times

## [0.0.1] — 2026-10-30

### Added

- Repository structure (`docs/`, `frontend/`, `backend/`, `database/`)
- Project documentation set based on the NIT3003 proposal and presentation
- MySQL schema `database/schema.sql`
- `.gitignore`, `.gitattributes`, pull request template, contributing guide

## Milestones

- **M2 — Oral presentation** (NIT3003): completed
- **M1 — Project proposal** (NIT3003): completed
