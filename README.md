# Hyperliquid BTC Daily Trend-Following Bot

Bot Python 3.11+ pour exécuter une stratégie BTC daily trend-following (long/short) sur Hyperliquid sans TradingView webhook.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Remplissez les secrets dans `.env` uniquement pour le mode live.

## Lancement

### Paper mode

```bash
BOT_MODE=paper python main.py
```

### Live mode

```bash
BOT_MODE=live python main.py
```

## Diagnostic rapide (400 bougies)

```bash
python main.py --diagnose --limit 400
```

## Notes importantes

- Le bot tourne en continu mais n'exécute la logique daily qu'une fois par nouvelle clôture UTC.
- Le trailing stop ATR est recalculé à la clôture daily, puis appliqué via stop exchange-side si possible; sinon surveillance locale du prix.
- `SYMBOL` correspond au coin Hyperliquid (souvent `BTC`). Vérifiez sur votre compte si `BTC` mappe bien `BTC-PERP`.
- Ne loggez jamais la clé privée.
