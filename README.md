# Document Screening System Backend

The Document Screening System is a FastAPI backend for secure identity and
document verification. It combines OCR, face matching, document-specific
validation, session management, and blockchain-backed document verification in
one API. It is intended for controlled officer and administrator workflows,
where a document can be uploaded, its details extracted, a person can be
matched against the document, and the verification result can be recorded for
later review.

## Main features

- REST API built with FastAPI and automatic OpenAPI documentation.
- PostgreSQL persistence using SQLAlchemy models and sessions.
- JWT-based authentication with password hashing using bcrypt.
- User and role support for officers and administrators.
- Officer/system online and offline session tracking.
- OCR extraction for identity-document fields such as name, document number,
  date of birth, gender, nationality, address, and expiry date.
- Face detection and face matching for identity verification.
- Passport MRZ validation and Aadhaar QR/forensic verification helpers.
- Document, verification, risk, history, and system workflow endpoints.
- Blockchain document registration and verification on the Ethereum Sepolia
  test network.
- Canonical document hashing and transaction-hash storage for tamper-evident
  verification.
- CORS middleware for frontend integration.

## Technology and libraries

| Area | Technology |
| --- | --- |
| API | Python, FastAPI, Uvicorn, Pydantic |
| Database | PostgreSQL, SQLAlchemy, Alembic |
| Authentication | JWT (`python-jose`), Passlib, bcrypt |
| OCR and image processing | RapidOCR, OpenCV, Pillow, NumPy |
| Face verification | InsightFace and ONNX Runtime |
| Document validation | MRZ validation, Aadhaar QR decoding and forensic checks |
| Blockchain | Ethereum Sepolia, Web3.py, contract ABI, document hashes |
| Supporting tools | Python dotenv, multipart uploads, NetworkX and scientific Python packages |

The scoring workflow uses face score, blockchain face score, blockchain result,
and OCR confidence. The current weights are documented in `meaningful.txt`.

## Project layout

```text
app/
|-- api/v1/endpoints/   API routers for users, workflow, verification, documents, and blockchain
|-- blockchain/         Web3 service, contract ABI, and hash utilities
|-- core/               configuration, database, OCR, face matching, security, and forensics
|-- models/             SQLAlchemy database models
|-- schemas/            Pydantic request and response schemas
`-- main.py             FastAPI application and router registration
```

## Setup

### 1. Prerequisites

- Python 3.11 or newer
- PostgreSQL
- An Ethereum Sepolia RPC endpoint
- A funded Sepolia wallet if blockchain registration is required
- The deployed smart-contract address and compatible contract ABI

### 2. Create an environment

From the repository root:

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

Install the pinned dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` to `.env` and replace every placeholder with the values
for your local PostgreSQL database, JWT configuration, and Sepolia deployment.
Do not commit `.env`, wallet private keys, or production secrets.

`app/core/config.py` builds the PostgreSQL connection string from
`POSTGRES_SERVER`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB`.
`DATABASE_URL` is therefore optional in the current implementation.

### 4. Initialize the database

The database tables are created through the initialization helper in
`app/core/init_db.py`. For a first-time local setup, either run the helper
directly:

```bash
python -m app.core.init_db
```

or temporarily uncomment `init_database()` in `app/main.py` and start the
application once. The call should be disabled again after initialization.
Review `app/main.py` and `app/core/init_db.py` for the complete database setup
and available inspection/reset commands. The reset operation deletes existing
data and should only be used deliberately.

### 5. Start the API

```bash
uvicorn app.main:app --reload
```

The default development server is available at
`http://127.0.0.1:8000`. Useful public endpoints are:

- `GET /` - service welcome message and version
- `GET /health` - health check
- `GET /docs` - Swagger UI
- `GET /redoc` - ReDoc
- `GET /api/v1/openapi.json` - OpenAPI schema

## Typical verification flow

1. Create a user and upload the user's reference face image.
2. Log in through the backend API and copy the returned JWT access token.
3. In Swagger UI, click **Authorize** and enter the bearer token.
4. Create or select an available system and start an officer session.
5. Upload a document for OCR and document-field extraction.
6. Run the person-verification workflow with the captured face image.
7. Use the blockchain endpoints to upload/register a document and check its
   stored hash and transaction-backed verification result.
8. Review history and end the session through the logout endpoint.

Most routes under verification, workflow, documents, history, session,
authentication, and blockchain require a valid JWT. The route prefixes and
router registration are defined in `app/main.py`.

## Important user creation and security note

There is intentionally no registration page in the frontend because creating
identity-verification users is a controlled administrative operation. To create
the first user, use the backend documentation at `/docs` and call
`POST /api/v1/users/create` before attempting protected requests. Then use
`POST /api/v1/users/login` to obtain a token. This initial
setup step is the documented JWT bypass: the public create-user endpoint lets
you establish the first account so that you can then log in and obtain a JWT.
After that, an administrator should manage user creation. The frontend does
not expose public registration; administrators can create users through the
backend API.

For database behavior and initialization details, refer to `app/main.py`,
`app/core/config.py`, and `app/core/init_db.py`. Never use real wallet keys or
production credentials in local example files.
