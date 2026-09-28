# Border Ace — Backend

Border Ace is an AI-powered fake identity and document screening platform for border checkpoints. This repository contains its FastAPI backend: the service that receives identity and travel documents, extracts and validates their details, compares faces, assesses risk, and keeps a verifiable record of the screening workflow.

The goal is to help border-security personnel make consistent, evidence-based decisions in seconds rather than relying only on time-consuming manual inspection.

**Frontend:** [border-ace.vercel.app](https://border-ace.vercel.app/)

**System Design and Workflow:** [System workflow link](https://excalidraw.com/#json=oW_hR1GxT1uW0RQjP1wzY,rM660n_JaAYtFmNtC7P_Dg)

**System Mockup** [link](https://excalidraw.com/#json=_MXPk5sCLtLV-Zfuc7ATU,pPEFB53P7VyleKg54W66Uw)

**Project resources, sample images, and supporting information:** [Google Drive folder](https://drive.google.com/drive/folders/12KQaR0Bqt4Xpok-gTGaW1byQ5Nr0c_e4?usp=sharing)

## The challenge

Border checkpoints must process large volumes of passports, visas, national identity cards, permits, and travel authorizations. Manual review and basic database lookups can miss sophisticated fraud and introduce delays. Border Ace is designed to address issues including:

- Forged passports, visas, and visa stamps
- Altered photographs, personal details, dates of birth, and other document text
- Identity impersonation and multiple identities associated with one person
- Expired, tampered, or blacklisted travel documents
- Inconsistent screening decisions caused by high passenger volume

## What Border Ace does

### Document intelligence

- Accepts identity and travel-document images, including passports, visas, national IDs, driving licences, and permits.
- Uses OCR to extract key details such as name, document number, nationality, date of birth, gender, issue date, expiry date, address, and MRZ information.
- Stores the document and extracted fields so officers can review the result in the screening workflow.

### Validation and fraud signals

- Validates passport machine-readable zones (MRZ).
- Includes Aadhaar QR verification and document-forensics helpers.
- Provides foundations for detecting text manipulation, photo replacement, stamp forgery, image metadata anomalies, and other physical or digital tampering signals.

### Face and identity verification

- Captures a presented face image and compares it with the portrait on a document.
- Verifies an officer's face before opening a screening session.
- Uses face-match results alongside document and OCR evidence in the verification workflow.

### Risk, workflow, and auditability

- Combines OCR confidence, face-match scores, document validation, and blockchain checks into a risk-oriented screening result.
- Supports officer and system sessions, verification status updates, and case history.
- Can register canonical document hashes on Ethereum Sepolia and later verify the stored record for tamper-evident document checks.
- Uses JWT authentication and role-aware users for controlled operational access.

## Architecture

```text
Frontend (Vercel)
        |
        v
FastAPI API ──> PostgreSQL
    |   |             |
    |   ├─ OCR / MRZ / QR validation / forensics
    |   ├─ Face matching
    |   └─ Risk, session, and history workflows
    |
    └──> Ethereum Sepolia (optional document-hash verification)
```

## Project structure

```text
app/
├── api/v1/endpoints/  API routes for users, verification, workflow, documents,
│                      systems, sessions, history, authentication, and blockchain
├── blockchain/        Web3 integration, contract ABI, and document hashing
├── core/              configuration, database, bootstrap, security, OCR, face
│                      matching, MRZ validation, and forensic utilities
├── models/            SQLAlchemy database models
├── schemas/           Pydantic request and response schemas
└── main.py            FastAPI application and router registration
.env.example           Environment-variable template
requirements.txt       Python dependencies
```

## Quick start

### Prerequisites

- Python 3.11 or newer
- PostgreSQL
- Optional for blockchain functions: a Sepolia RPC URL, funded wallet private key, deployed contract address, and compatible contract ABI

### 1. Create a virtual environment and install dependencies

From the repository root:

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Configure `.env`

Copy the template and replace its placeholder values with local development values. Never commit `.env`, database passwords, JWT secrets, or wallet keys.

```bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS/Linux
cp .env.example .env
```

Configure the following groups in `.env`:

| Group | Variables | Purpose |
| --- | --- | --- |
| PostgreSQL | `POSTGRES_SERVER`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Database connection; the backend constructs the PostgreSQL URL from these values. |
| Bootstrap administrator | `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_PASSWORD`, `BOOTSTRAP_ADMIN_NAME`, `BOOTSTRAP_ADMIN_DOB`, `BOOTSTRAP_ADMIN_GENDER`, `BOOTSTRAP_ADMIN_AADHAR`, `BOOTSTRAP_ADMIN_PHONE`, `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_FACE_IMAGE` | Details for the first administrator account. `BOOTSTRAP_ADMIN_FACE_IMAGE` is an optional local image path. |
| Bootstrap system | `BOOTSTRAP_SYSTEM_NAME` | Name for the first Border Ace screening system. |
| JWT | `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | Token signing and expiry settings. Use a long, unique secret. |
| Blockchain (optional) | `SEPOLIA_RPC_URL`, `BLOCKCHAIN_PRIVATE_KEY`, `CONTRACT_ADDRESS` | Required only for Ethereum Sepolia document-registration and verification features. |

### 3. First-time database bootstrap

The first administrator and initial system are created from the bootstrap values in `.env`; no JWT bypass or manual first-user API call is needed.

Before starting the application for the first time, open [`app/main.py`](app/main.py) and uncomment this line:

```python
initialize_database()
```

Start the API once:

```bash
uvicorn app.main:app --reload
```

The bootstrap routine creates the database tables, the administrator, and the initial system. Once it has completed successfully, stop the server and comment out or remove `initialize_database()` again, as indicated in `app/main.py`. This prevents the bootstrap code from running on every startup.

### 4. Start the API normally

```bash
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`.

- `GET /health` — health check
- `GET /docs` — interactive Swagger/OpenAPI documentation
- `GET /redoc` — ReDoc documentation
- `GET /api/v1/openapi.json` — OpenAPI schema

## Screening workflow

1. Configure the bootstrap administrator and system in `.env`, then complete the one-time bootstrap described above.
2. Sign in through the user login endpoint and use the returned bearer token for protected API requests.
3. Verify the officer's face and open a session on an available screening system.
4. Upload a travel or identity document. Border Ace extracts the available document fields through OCR.
5. Submit the presented person's image and extracted document data for face matching and document-specific validation.
6. Review validation results, face-match score, OCR confidence, blockchain result (when configured), and the resulting risk information.
7. Update the case status, review its history, and close the officer session.

## API areas

The live API contract, request fields, and response examples are available in Swagger at `/docs` when the server is running. The main route groups are:

| Route prefix | Responsibility |
| --- | --- |
| `/api/v1/users` | User management, face-image upload, and login |
| `/api/v1/verification` | Officer face verification and session creation |
| `/api/v1/workflow` | Document upload, person verification, and case status |
| `/api/v1/documents` | Stored document, person, and user-face images |
| `/api/v1/system` | Screening-system availability and creation |
| `/api/v1/session` | Active and historical session information |
| `/api/v1/data` | Screening history |
| `/api/v1/blockchain` | Document upload, registration, and hash verification |
| `/api/v1/auth` | Logout |

## Security notes

- Keep `.env` private. It can contain database credentials, an administrator password, JWT signing material, and a blockchain wallet private key.
- Replace every example placeholder before use, especially `SECRET_KEY` and blockchain credentials.
- Use HTTPS, restricted CORS origins, strong secrets, and a managed secret store before deploying beyond development.
- Blockchain features are optional; do not use a production wallet or real private key in demo configuration.

## Expected impact

Border Ace is intended to reduce document verification from minutes to seconds, improve detection of forged and tampered documents, standardize screening decisions, and create a useful digital trail for investigation and intelligence work.
