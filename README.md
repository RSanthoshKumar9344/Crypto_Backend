# Cryptocurrency Market Research API

A FastAPI backend for a mobile cryptocurrency market research application. It
uses the CoinGecko API and returns bundled sample data when CoinGecko responds
with HTTP 429 (rate limited).

## Requirements

- Python 3.10+
- A CoinGecko API key is optional. Set `COINGECKO_API_KEY` to use the
  `x-cg-demo-api-key` request header.

## Install and run

Confirm `python3 --version` reports Python 3.10 or newer. On macOS, if you
have multiple Python versions installed, use the matching executable (for
example, `python3.12`) in place of `python3` below.

```bash
cd crypto_backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Interactive API documentation is available at <http://localhost:8000/docs>.

## Endpoints

- `GET /api/v1/coins`
- `GET /api/v1/coins/{coin_id}`
- `GET /api/v1/coins/{coin_id}/chart?period=1D|7D|30D|1Y`
- `GET /api/v1/market/stats`
