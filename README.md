# AviaSales Tracker Bot

A Telegram bot that tracks flight deals and price alerts for AviaSales, sends daily subscriptions, and notifies users when ticket prices drop.

---

## Features

* **Hot Deals Tracking** – fetches the cheapest flight offers for selected origins.
* **Subscriptions** – users can subscribe to daily deals from specific cities at a chosen time.
* **Price Alerts** – users can set target prices for flights; the bot notifies when the price drops.
* **Localized Formatting** – messages include readable flight info in Russian.
* **Automatic Scheduler** – runs in the background to check subscriptions and alerts every minute.

---

## Installation

1. Clone the repository:

```bash
git clone https://github.com/Pursuit2703/aviasales_tracker.git
cd aviasales_tracker
```

2. Create and activate a virtual environment:

| Platform             | Command                                                  |
| -------------------- | -------------------------------------------------------- |
| Linux / macOS        | `python3 -m venv .venv` <br> `source .venv/bin/activate` |
| Windows (cmd)        | `python -m venv .venv` <br> `.venv\Scripts\activate.bat` |
| Windows (PowerShell) | `python -m venv .venv` <br> `.venv\Scripts\Activate.ps1` |

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Set your Telegram bot token:

| Platform             | Command                                  |
| -------------------- | ---------------------------------------- |
| Linux / macOS        | `export TELEGRAM_TOKEN="YOUR_BOT_TOKEN"` |
| Windows (cmd)        | `set TELEGRAM_TOKEN="YOUR_BOT_TOKEN"`      |
| Windows (PowerShell) | `$env:TELEGRAM_TOKEN="YOUR_BOT_TOKEN"`   |

---

## Database

Uses SQLite (`alerts.db`) to store:

* **Subscriptions** – scheduled daily deal notifications for users.
* **Alerts** – price alerts for specific flights.

Database is automatically initialized on first run.

---

## Commands

* `/deals ORIGIN` – Show the best current deals from a city.
* `/cities` – List available cities.
* `/subscribe ORIGIN HH MM` – Subscribe to daily deals at `HH:MM` from `ORIGIN`.
* `/alert ORIGIN DESTINATION [PRICE]` – Set a price alert for a flight.
* `/myalerts` – List your active alerts.
* `/unsubscribe` – Remove a subscription.
* `/help` – Show help text.

---

## Running the Bot

Start the bot and scheduler:

```bash
python main.py
```

* The bot polls Telegram updates.
* Scheduler runs in the background and sends subscriptions & alert notifications every minute.

---

## Code Structure

```
.
├── bot
│   ├── alerts.py
│   ├── bot.py
│   ├── db.py
│   ├── fetcher.py
│   ├── formatter.py
│   ├── handlers.py
│   ├── __init__.py
│   ├── scheduler.py
│   ├── state.py
│   └── utils.py
├── LICENSE
├── main.py
├── README.md
└── requirements.txt

```
---

## Notes

* Scheduler runs **every minute**, so alerts and subscriptions are processed promptly.
* `check_alerts_once(bot)` can also be run manually for testing.
* Subscriptions check the user-defined `hour` and `minute` and send the first 15 best deals.
* Price alerts are compared to `last_price` and optional `target_price`.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/xyz`)
3. Make your changes
4. Commit and push (`git commit -am "Add feature"`)
5. Open a pull request

---

## License

MIT License

