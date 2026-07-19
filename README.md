# FastAPI Payment API

A REST API built with FastAPI, PostgreSQL, Docker, and Stripe Checkout.

The project demonstrates JWT authentication, protected API routes, Stripe subscription payments, webhook signature verification, and persistent customer and subscription data.

## Features

- User registration
- User login with JWT access tokens
- Protected current-user endpoint
- Stripe subscription Checkout Session creation
- Stripe webhook signature verification
- Stripe customer ID persistence
- Subscription persistence in PostgreSQL
- Webhook event idempotency
- PostgreSQL with asynchronous SQLAlchemy
- Alembic database migrations
- Docker and Docker Compose
- Swagger/OpenAPI documentation
- Health and database health endpoints

## Technology Stack

- Python 3.12
- FastAPI
- PostgreSQL
- SQLAlchemy
- AsyncPG
- Alembic
- Stripe Python SDK
- JWT authentication
- Docker
- Docker Compose

## Project Structure

```text
fastapi-payment-api/
├── alembic/
├── app/
│   ├── api/
│   │   ├── dependencies.py
│   │   └── routes/
│   │       ├── auth.py
│   │       ├── checkout.py
│   │       └── webhooks.py
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   ├── db/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   │   └── stripe_service.py
│   └── main.py
├── .env.example
├── .gitignore
├── alembic.ini
├── compose.yaml
├── Dockerfile
├── LICENSE
├── README.md
└── requirements.txt
```

## Environment Setup

Copy the example environment file:

```bash
cp .env.example .env
```

Update `.env` with your local values:

```env
APP_NAME=FastAPI Payment API
APP_ENV=development
DEBUG=true

DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/payment_db

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=payment_db

STRIPE_SECRET_KEY=sk_test_replace_me
STRIPE_WEBHOOK_SECRET=whsec_replace_me
STRIPE_PRICE_ID=price_replace_me

FRONTEND_SUCCESS_URL=http://127.0.0.1:8001/docs
FRONTEND_CANCEL_URL=http://127.0.0.1:8001/docs

JWT_SECRET_KEY=replace_with_a_long_random_secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

Never commit the real `.env` file.

Generate a secure JWT key:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

## Run with Docker

Start the API and PostgreSQL:

```bash
docker compose up -d --build
```

Check the containers:

```bash
docker compose ps
```

View API logs:

```bash
docker compose logs -f api
```

Stop the services:

```bash
docker compose down
```

## Database Migrations

Run migrations inside the API container:

```bash
docker compose exec api alembic upgrade head
```

Create a new migration:

```bash
docker compose exec api alembic revision --autogenerate -m "Migration description"
```

## API Documentation

After starting the application, open:

```text
http://127.0.0.1:8001/docs
```

OpenAPI JSON:

```text
http://127.0.0.1:8001/openapi.json
```

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register a user |
| POST | `/api/v1/auth/login` | Log in and receive a JWT |
| GET | `/api/v1/auth/me` | Return the authenticated user |

### Checkout

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/checkout/session` | Create a Stripe subscription Checkout Session |

### Webhooks

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/webhooks/stripe` | Receive and process Stripe webhook events |

### Health

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Application health check |
| GET | `/health/db` | Database health check |

## Authentication Example

Register:

```bash
curl -X POST \
  http://127.0.0.1:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "johan@example.com",
    "password": "StrongPassword123!"
  }'
```

Login:

```bash
curl -X POST \
  http://127.0.0.1:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "johan@example.com",
    "password": "StrongPassword123!"
  }'
```

Save the access token:

```bash
TOKEN=$(curl -fsS -X POST \
  http://127.0.0.1:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "johan@example.com",
    "password": "StrongPassword123!"
  }' | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['access_token'])")
```

Test the protected current-user endpoint:

```bash
curl -sS \
  http://127.0.0.1:8001/api/v1/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

## Stripe Setup

Create a recurring product price in Stripe Sandbox.

Set the recurring price ID in `.env`:

```env
STRIPE_PRICE_ID=price_replace_me
```

Start the local Stripe listener:

```bash
STRIPE_KEY=$(grep '^STRIPE_SECRET_KEY=' .env | cut -d= -f2-)

stripe listen \
  --api-key "$STRIPE_KEY" \
  --forward-to http://127.0.0.1:8001/api/v1/webhooks/stripe
```

Copy the listener signing secret into `.env`:

```env
STRIPE_WEBHOOK_SECRET=whsec_replace_me
```

Recreate the API container after changing `.env`:

```bash
docker compose up -d --force-recreate api
```

## Create a Checkout Session

```bash
curl -sS -X POST \
  http://127.0.0.1:8001/api/v1/checkout/session \
  -H "Authorization: Bearer $TOKEN"
```

The response contains:

```json
{
  "checkout_url": "https://checkout.stripe.com/...",
  "session_id": "cs_test_..."
}
```

Open `checkout_url` in your browser.

Use Stripe's test card:

```text
Card number: 4242 4242 4242 4242
Expiration: any future date
CVC: any 3 digits
ZIP: any valid ZIP code
```

## Stripe Webhook Flow

```text
Authenticated user
      ↓
Create Checkout Session
      ↓
Stripe-hosted Checkout
      ↓
Test subscription payment
      ↓
Stripe webhook event
      ↓
FastAPI signature verification
      ↓
Customer and subscription saved in PostgreSQL
```

The application processes events including:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `invoice.created`
- `invoice.paid`
- `invoice.payment_succeeded`
- `payment_intent.succeeded`
- `charge.succeeded`

## Verify Subscription Data

```bash
docker compose exec db psql \
  -U postgres \
  -d payment_db \
  -c "SELECT
        stripe_subscription_id,
        stripe_price_id,
        status,
        current_period_end
      FROM subscriptions;"
```

Verify the user's Stripe customer ID:

```bash
docker compose exec db psql \
  -U postgres \
  -d payment_db \
  -c "SELECT email, stripe_customer_id
      FROM users;"
```

Verify webhook events:

```bash
docker compose exec db psql \
  -U postgres \
  -d payment_db \
  -c "SELECT event_type, stripe_event_id, processed_at
      FROM webhook_events
      ORDER BY processed_at DESC
      LIMIT 20;"
```

## Security

- Passwords are stored as hashes.
- JWT tokens protect private endpoints.
- Stripe signatures are verified before processing webhooks.
- Webhook event IDs are stored to prevent duplicate processing.
- Real credentials belong only in `.env`.
- `.env` is excluded through `.gitignore`.
- `.env.example` contains placeholders only.
- Exposed Stripe keys should be rotated immediately.

Check that `.env` is ignored:

```bash
git check-ignore .env
```

Check that Stripe secrets are not committed:

```bash
git grep -n -E "sk_test_|whsec_" -- . ':!.env'
```

## Future Improvements

- Stripe Customer Portal
- Subscription cancellation endpoint
- Subscription upgrade and downgrade
- Refund handling
- Email notifications
- Automated test suite
- GitHub Actions CI
- Deployment configuration
- Frontend payment success and cancellation pages

## Author

**Johan Bergman**

GitHub: `prosoftdev999`

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.