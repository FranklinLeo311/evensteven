# EvenSteven — split the bill by just talking

Snap a receipt, say who had what in plain words, and every friend gets a PayPal link for their exact share.

> "I had the pasta, Raj got the steak, Mia and I split the tiramisu, everyone shared the wine and bread."

EvenSteven reads the receipt with Claude, turns that sentence into an item-by-item split, spreads tax, tip and
discounts fairly, and creates a PayPal order for each person. The money goes straight to the friend who paid,
and their screen fills up live as people pay.

## Try it

**Live demo: https://evensteven.onrender.com** (PayPal sandbox: no real money moves)

1. Click **Try a sample receipt**, or upload a photo or PDF of your own receipt.
2. Add the people, say who had what in a sentence, and click **Split**.
3. Open a person's pay link and pay with a PayPal sandbox **Personal** test account
   (create one under *Testing Tools → Sandbox Accounts* in the [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/)).

The demo runs on a free plan: the first visit after a quiet spell takes up to a minute to wake up, and bills are cleared
when the service restarts. Each visitor can read 15 receipts or splits per hour.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/FranklinLeo311/evensteven)

## How it works

1. **Read** – Claude (vision + structured outputs) reads the photo or PDF: merchant, currency, every line, tax, tip and total, with warnings when the numbers don't add up.
2. **Understand** – Claude maps the group's description to the items, including uneven shares ("Sam had two of the three beers") and corrections ("actually Mia skipped the wine"). It flags real ambiguities and writes a short note for each person.
3. **Settle** – the amounts are worked out in code, not by the model: the bill total is spread in proportion to what each person had and rounded with the largest-remainder method, so the shares always add up to the receipt to the cent.
4. **Pay** – each share gets a pay page with PayPal Smart Buttons. The server creates a PayPal **Orders v2** order (with the payer's PayPal email as the `payee`, so money goes to them directly) and captures it after approval. `PayPal-Request-Id` keeps retries from creating duplicate orders or captures.

## Stack

- **Frontend:** React 19, Vite, Tailwind CSS 4, PayPal JS SDK
- **Backend:** Python, FastAPI, SQLite
- **AI:** Claude Opus 5.5 through the Anthropic Python SDK
- **Payments:** PayPal REST API (OAuth 2.0 client credentials, Orders v2 create + capture), sandbox

## Run it locally

You need Python 3.11+, Node 20+, a Claude API key and a PayPal developer sandbox app.

```bash
# backend
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt   # macOS/Linux: .venv/bin/pip
cp .env.example .env                             # fill in ANTHROPIC_API_KEY, PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET

# frontend (built into frontend/dist and served by the backend)
cd ../frontend
npm install
npm run build

# start
cd ../backend
.venv/Scripts/python -m uvicorn app.main:app --port 8090
```

Open http://localhost:8090. For frontend development, run `npm run dev` in `frontend` (port 5180, proxies `/api` to 8090).

### Testing with the PayPal sandbox

1. In the [PayPal Developer Dashboard](https://developer.paypal.com/dashboard/), open **Apps & Credentials** (Sandbox) and copy the client ID and secret of the default app into `backend/.env`.
2. Under **Testing Tools → Sandbox Accounts** there is a Personal and a Business test account. Use the Business account's email as "Their PayPal email" (the person who paid), and log in with the Personal account on the pay page.
3. Click **Try a sample receipt** on the home page if you don't have a receipt handy.

## API

| Method | Path | What it does |
|---|---|---|
| POST | `/api/bills` | Upload a receipt (multipart `file`); returns the read bill |
| POST | `/api/bills/{id}/split` | `{people, payer, payee_email, story[]}` → AI split + per-person shares |
| GET | `/api/bills/{id}` | Bill, split and payment status |
| GET | `/api/shares/{id}` | One person's share (pay page) |
| POST | `/api/shares/{id}/order` | Create the PayPal order for that share |
| POST | `/api/shares/{id}/capture` | Capture the approved order |

## Deploy your own copy (Render)

The repository has a `Dockerfile` (builds the React app and serves it from FastAPI) and a `render.yaml` Blueprint.

1. Push this repository to GitHub.
2. In [Render](https://dashboard.render.com/), choose **New → Blueprint** and pick the repository.
3. Fill in `ANTHROPIC_API_KEY`, `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET` (sandbox) when asked, then **Apply**.
4. When the deploy is live, open `https://<service-name>.onrender.com`. Pay links use that address automatically.

`AI_CALLS_PER_IP_PER_HOUR` and `AI_CALLS_PER_DAY` cap the Claude calls so a public demo can't run up the API bill.

## Built for the PayPal AI Hackathon

Everything in this repository was written during the hackathon submission period (November 2026).

## License

MIT
