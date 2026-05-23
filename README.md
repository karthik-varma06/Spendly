# Spendly

**Spendly** is an AI-powered expense tracker that helps users upload receipts, extract expense data automatically, review and save transactions, track budgets, receive alerts, chat with finance data in natural language, and export complete dashboard reports.

---


## Features

### 1) Authentication
- Sign up and log in securely
- Protected pages for logged-in users
- Automatic session handling
- Secure access token cookies

### 2) Receipt / Bill Upload
- Upload PDF, CSV, and image files
- Automatically detects the uploaded file type
- PDFs and CSVs are parsed using Python libraries
- Images are processed using AI Vision models
- OCR is used as a fallback if image extraction fails
- Extracted text is passed to the LLM for structured expense data
- AI automatically detects the expense category
- Save uploaded file metadata and extracted content

### 3) Expense Review and Save
- Review extracted bill details before saving
- Edit vendor, items, taxes, totals, and payment details
- Save complete expense records securely

### 4) Dashboard Analytics
- Monthly expense
- Yearly expense
- Savings
- Category breakdown
- Top merchants
- Top items
- Spending trends
- Most expensive month
- Income vs expense overview

### 5) Budget Monitoring
- Set budgets for different expense categories
- Support for weekly, monthly, and custom date budgets
- Automatically track spending progress
- Detect when a budget limit is crossed
- Send detailed budget alert emails
- AI-generated spending summary and suggestions in alert emails

### 6) Notifications and Email Alerts
- In-app notifications
- Expense added alerts
- Budget warning alerts
- Budget exceeded alerts
- Weekly / monthly budget summaries
- Email alerts 

### 7) AI Finance Chat
- AI-powered finance assistant
- Ask questions about expenses, income, budgets, savings, and spending
- Uses your dashboard data and recent activity for better answers
- Saves chat history for context

### 8) Export
- PDF dashboard export
- Excel workbook export
- Profile + dashboard + expenses + budgets + uploads + income + trends

### 9) Profile and Settings
- View account details
- Access profile information securely
- Export dashboard data as PDF or Excel files

---

## Tech Stack

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- Framer Motion
- React Router
- Lucide React
- Recharts

### Backend
- FastAPI
- SQLAlchemy  — handles database operations using Python code
- PostgreSQL
- Pydantic — validates and structures API data
- JWT authentication 

### AI / Automation
- OpenRouter
- OCR with Tesseract
- OpenCV
- pdfplumber
- PyMuPDF
- Pandas
- Resend for email delivery

### Export / Reporting
- ReportLab for PDF
- OpenPyXL for Excel export

---

## LLMs Used

Spendly uses OpenRouter for  extraction, reasoning, and chat.

### Vision / Receipt Extraction
- `nvidia/nemotron-nano-12b-v2-vl:free`

### Chat / Reasoning
- `openrouter/free`

### Fallback Behavior
If the AI call fails or no API key is configured:
- the app falls back to local parsing rules
- OCR text is still used
- structured defaults are returned safely

---
## Setup
#### Backend


```bash
cd backend
python -m venv venv
venv\Scripts\activate
```
Install backend dependencies:

```bash
pip install -r requirements.txt
```

Run the backend server:

```bash
uvicorn app.main:app --reload
```

#### Frontend

Open a second terminal and go to the frontend folder:

```bash
cd frontend
```

Install frontend dependencies:

```bash
npm i
```

Run the frontend development server:

```bash
npm run dev
```

## Backend `.env`

```env
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/ai_finance_tracker
SECRET_KEY=please-change-me-to-a-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
OPENROUTER_API_KEY=
OPENROUTER_VISION_MODEL=nvidia/nemotron-nano-12b-v2-vl:free
OPENROUTER_CHAT_MODEL=openrouter/free
FRONTEND_ORIGIN=http://localhost:5173
RESEND_API_KEY=
RESEND_FROM_EMAIL=onboarding@resend.dev
UPLOAD_DIR=uploads
TESSERACT_CMD=C:\Users\asus\AppData\Local\Programs\Tesseract-OCR\tesseract.exe
```

## Frontend `.env`

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

---
## Backend Logic Flow

### 1) Login / Register Flow
`frontend → /auth/login or /auth/register → set HTTP-only cookie → /auth/me → protected pages`

### 2) Upload Flow
`Upload file → detect type → extract text / OCR → LLM extraction → normalize fields → show review form → save reviewed expense → create expense items → update uploaded file status`

### 3) Expense Save Flow
`Reviewed draft → expenses table → expense_items table → notification created → budget sync → email alerts if needed → dashboard refresh`

### 4) Dashboard Flow
`expenses + income + categories + items + budgets → analytics service → summary object → dashboard charts/cards`

### 5) Budget Flow
`new expense saved → budget insights rebuilt → threshold check → notification created → email sent if configured → email log stored`

### 6) Chat Flow
`user message → recent chat history → dashboard summary → budget insights → LLM prompt → AI response → save AI chat history`

### 7) Export Flow
`profile page → export request → backend collects profile + dashboard + expenses + budgets + uploads + income → PDF/XLSX generated → file download`

---


## Main Backend Modules

- `api/routes/auth.py` → authentication and session cookies
- `api/routes/uploads.py` → upload, OCR, extraction, save reviewed expense
- `api/routes/expenses.py` → manual expense creation and expense-item storage
- `api/routes/dashboard.py` → dashboard summary
- `api/routes/chat.py` → AI chat endpoint
- `api/routes/notifications.py` → notification APIs and budget watcher support
- `api/routes/export.py` → PDF and Excel export
- `services/analytics.py` → dashboard summary and chat context
- `services/llm.py` → AI extraction and finance chat
- `services/notifications.py` → budget alerts, summaries, and email logic
- `services/ocr.py` → PDF / CSV / image text extraction
- `main.py` → router registration and app startup

---

## Database 

Spendly stores:
- users
- sessions
- categories
- user settings
- uploaded files
- expenses
- expense items
- budgets
- notifications
- income
- recurring expenses
- AI chat history
- email logs



---
## Database Schema

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =========================================================
-- UPDATED_AT TRIGGER FUNCTION
-- =========================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =========================================================
-- USERS
-- =========================================================

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    profile_image TEXT,
    currency VARCHAR(10) DEFAULT 'INR',
    timezone VARCHAR(50) DEFAULT 'Asia/Kolkata',
    is_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- SESSIONS
-- =========================================================

CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    refresh_token TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    is_revoked BOOLEAN DEFAULT FALSE,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =========================================================
-- CATEGORIES
-- =========================================================

CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    icon VARCHAR(50),
    color VARCHAR(20),
    created_at TIMESTAMP DEFAULT NOW()
);

-- =========================================================
-- USER SETTINGS
-- =========================================================

CREATE TABLE user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    theme VARCHAR(20) DEFAULT 'LIGHT',
    weekly_email_enabled BOOLEAN DEFAULT TRUE,
    monthly_email_enabled BOOLEAN DEFAULT TRUE,
    budget_alerts_enabled BOOLEAN DEFAULT TRUE,
    ai_chat_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TRIGGER trg_user_settings_updated_at
BEFORE UPDATE ON user_settings
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- UPLOADED FILES
-- =========================================================

CREATE TABLE uploaded_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    file_type VARCHAR(20),
    file_size BIGINT,
    mime_type VARCHAR(100),
    extracted_text TEXT,
    extraction_status VARCHAR(50) DEFAULT 'PENDING',
    ocr_engine VARCHAR(50),
    llm_model VARCHAR(120),
    upload_source VARCHAR(50),
    processed_at TIMESTAMP,
    extraction_error TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =========================================================
-- EXPENSES
-- =========================================================

CREATE TABLE expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id),
    uploaded_file_id UUID REFERENCES uploaded_files(id),
    vendor_name VARCHAR(255),
    vendor_phone VARCHAR(50),
    vendor_email VARCHAR(255),
    vendor_address TEXT,
    invoice_number VARCHAR(120),
    expense_date DATE,
    expense_time TIME,
    subtotal NUMERIC(12,2) DEFAULT 0,
    cgst NUMERIC(12,2) DEFAULT 0,
    sgst NUMERIC(12,2) DEFAULT 0,
    igst NUMERIC(12,2) DEFAULT 0,
    tax_amount NUMERIC(12,2) DEFAULT 0,
    discount_amount NUMERIC(12,2) DEFAULT 0,
    total_amount NUMERIC(12,2) NOT NULL CHECK (total_amount >= 0),
    currency VARCHAR(10) DEFAULT 'INR',
    payment_method VARCHAR(50),
    notes TEXT,
    extraction_confidence FLOAT,
    is_reviewed BOOLEAN DEFAULT FALSE,
    is_manual BOOLEAN DEFAULT FALSE,
    status VARCHAR(30)
        CHECK (
            status IN (
                'PENDING_REVIEW',
                'COMPLETED',
                'FAILED',
                'PROCESSING'
            )
        )
        DEFAULT 'COMPLETED',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TRIGGER trg_expenses_updated_at
BEFORE UPDATE ON expenses
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- =========================================================
-- EXPENSE ITEMS
-- =========================================================

CREATE TABLE expense_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    expense_id UUID REFERENCES expenses(id) ON DELETE CASCADE,
    item_name VARCHAR(255) NOT NULL,
    item_category VARCHAR(100),
    quantity NUMERIC(10,2) DEFAULT 1,
    unit_price NUMERIC(12,2) DEFAULT 0,
    total_price NUMERIC(12,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =========================================================
-- BUDGETS
-- =========================================================

CREATE TABLE budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id),
    budget_limit NUMERIC(12,2) NOT NULL
        CHECK (budget_limit >= 0),
    spent_amount NUMERIC(12,2) DEFAULT 0,
    period VARCHAR(20)
        CHECK (
            period IN ('WEEKLY', 'MONTHLY', 'YEARLY')
        ),
    start_date DATE,
    end_date DATE,
    notify_percentage INTEGER DEFAULT 80,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =========================================================
-- NOTIFICATIONS
-- =========================================================

CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    message TEXT,
    type VARCHAR(100),
    action_url TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =========================================================
-- INCOME
-- =========================================================

CREATE TABLE income (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    source VARCHAR(255),
    amount NUMERIC(12,2)
        CHECK (amount >= 0),
    income_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =========================================================
-- RECURRING EXPENSES
-- =========================================================

CREATE TABLE recurring_expenses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    category_id INTEGER REFERENCES categories(id),
    title VARCHAR(255),
    amount NUMERIC(12,2),
    frequency VARCHAR(20),
    next_due_date DATE,
    last_generated_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- =========================================================
-- AI CHAT HISTORY
-- =========================================================

CREATE TABLE ai_chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    user_message TEXT,
    ai_response TEXT,
    expense_context JSONB DEFAULT '{}',
    model_used VARCHAR(120),
    response_source VARCHAR(30),
    created_at TIMESTAMP DEFAULT NOW()
);

-- =========================================================
-- EMAIL LOGS
-- =========================================================

CREATE TABLE email_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    email_type TEXT,
    subject TEXT,
    status VARCHAR(50),
    sent_at TIMESTAMP DEFAULT NOW()
);

-- =========================================================
-- INDEXES
-- =========================================================

CREATE INDEX idx_expenses_user_id
ON expenses(user_id);

CREATE INDEX idx_expenses_date
ON expenses(expense_date);

CREATE INDEX idx_expenses_category
ON expenses(category_id);

CREATE INDEX idx_expenses_user_date
ON expenses(user_id, expense_date DESC);

CREATE INDEX idx_expenses_user_category
ON expenses(user_id, category_id);

CREATE INDEX idx_expense_items_name
ON expense_items(item_name);

CREATE INDEX idx_notifications_user
ON notifications(user_id);

CREATE INDEX idx_budget_user_active
ON budgets(user_id, is_active);

CREATE INDEX idx_ai_chat_user_created
ON ai_chat_history(user_id, created_at DESC);

CREATE INDEX idx_uploaded_files_user
ON uploaded_files(user_id);

CREATE INDEX idx_email_logs_user
ON email_logs(user_id);

CREATE INDEX idx_income_user
ON income(user_id);

-- =========================================================
-- DEFAULT CATEGORIES
-- =========================================================

INSERT INTO categories (name, icon, color)
VALUES
('FOOD', 'utensils', '#FF6B6B'),
('TRAVEL', 'plane', '#4ECDC4'),
('SHOPPING', 'shopping-bag', '#45B7D1'),
('ELECTRONICS', 'monitor', '#5D5FEF'),
('HEALTH', 'heart-pulse', '#FF8C42'),
('UTILITIES', 'bolt', '#6C757D'),
('ENTERTAINMENT', 'film', '#9B5DE5'),
('SUBSCRIPTIONS', 'repeat', '#F15BB5'),
('EDUCATION', 'book-open', '#00BBF9'),
('TRANSPORT', 'car', '#00F5D4'),
('OTHER', 'circle', '#ADB5BD');