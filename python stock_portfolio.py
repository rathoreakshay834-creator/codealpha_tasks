"""Interactive paper-trading portfolio tracker.

This program uses simulated prices only. It does not connect to a broker and
does not provide real-time market data or investment advice.
"""

import json
import random
from datetime import datetime
from pathlib import Path


INITIAL_STOCKS = [
    {"symbol": "AAPL", "name": "Apple", "price": 180.00, "sector": "Technology"},
    {"symbol": "TSLA", "name": "Tesla", "price": 250.00, "sector": "Automotive"},
    {"symbol": "MSFT", "name": "Microsoft", "price": 420.00, "sector": "Technology"},
    {"symbol": "GOOGL", "name": "Alphabet", "price": 175.00, "sector": "Technology"},
    {"symbol": "AMZN", "name": "Amazon", "price": 190.00, "sector": "Consumer"},
    {"symbol": "NVDA", "name": "Nvidia", "price": 930.00, "sector": "Technology"},
    {"symbol": "META", "name": "Meta Platforms", "price": 520.00, "sector": "Technology"},
    {"symbol": "NFLX", "name": "Netflix", "price": 610.00, "sector": "Entertainment"},
    {"symbol": "JPM", "name": "JPMorgan Chase", "price": 198.00, "sector": "Finance"},
    {"symbol": "KO", "name": "Coca-Cola", "price": 62.00, "sector": "Consumer"},
    {"symbol": "DIS", "name": "Disney", "price": 112.00, "sector": "Entertainment"},
    {"symbol": "INTC", "name": "Intel", "price": 34.00, "sector": "Technology"},
]

DATA_FILE = Path(__file__).with_name("portfolio_data.json")
MAX_PRICE_HISTORY = 30
MAX_TRANSACTIONS = 500


def timestamp():
    """Return a readable local timestamp for transaction records."""
    return datetime.now().astimezone().isoformat(timespec="seconds")


def fresh_state():
    """Build a clean in-memory application state."""
    stocks = {}
    for item in INITIAL_STOCKS:
        stock = dict(item)
        stock["history"] = [stock["price"]]
        stocks[stock["symbol"]] = stock

    return {
        "stocks": stocks,
        "portfolio": {},
        "transactions": [],
        "watchlist": [],
        "alerts": [],
        "cash": 100000.00,
    }


def positive_number(value, label):
    """Convert text to a finite positive number, or raise a useful error."""
    try:
        number = float(value)
    except ValueError as error:
        raise ValueError(f"{label} must be a number.") from error

    if number <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return number


def positive_integer(value, label):
    """Convert text to a positive whole number."""
    try:
        number = int(value)
    except ValueError as error:
        raise ValueError(f"{label} must be a whole number.") from error

    if number <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return number


def money(value):
    """Format a numeric amount consistently."""
    return f"${value:,.2f}"


def normalize_symbol(value):
    """Normalize and validate a stock symbol string."""
    symbol = value.strip().upper()
    if not symbol:
        raise ValueError("Stock symbol cannot be empty.")

    if len(symbol) > 10 or not symbol.replace(".", "").isalnum():
        raise ValueError("Use a symbol of up to 10 letters, digits, or dots.")
    return symbol


def normalize_state(data):
    """Validate persisted data and migrate the earlier shares-only format."""
    state = fresh_state()
    if not isinstance(data, dict):
        raise ValueError("The saved portfolio must contain a JSON object.")

    saved_stocks = data.get("stocks", {})
    if isinstance(saved_stocks, dict):
        for symbol, saved in saved_stocks.items():
            if not isinstance(saved, dict):
                continue
            clean_symbol = normalize_symbol(symbol)
            try:
                price = positive_number(str(saved["price"]), "Saved price")
            except (KeyError, ValueError):
                continue

            baseline = state["stocks"].get(clean_symbol, {})
            history = saved.get("history", [price])
            if not isinstance(history, list):
                history = [price]

            valid_history = []
            for item in history[-MAX_PRICE_HISTORY:]:
                try:
                    valid_history.append(positive_number(str(item), "History price"))
                except ValueError:
                    continue
            if not valid_history:
                valid_history = [price]

            state["stocks"][clean_symbol] = {
                "symbol": clean_symbol,
                "name": str(saved.get("name", baseline.get("name", clean_symbol))),
                "sector": str(saved.get("sector", baseline.get("sector", "Other"))),
                "price": price,
                "history": valid_history,
            }

    saved_portfolio = data.get("portfolio")
    if not isinstance(saved_portfolio, dict):
        # Earlier versions stored just {symbol: quantity}.
        saved_portfolio = data

    for symbol, saved in saved_portfolio.items():
        if symbol in {"stocks", "transactions", "watchlist", "alerts", "cash"}:
            continue
        try:
            clean_symbol = normalize_symbol(symbol)
        except ValueError:
            continue

        if isinstance(saved, dict):
            quantity = saved.get("quantity", 0)
            average_cost = saved.get("average_cost", 0)
        else:
            quantity = saved
            average_cost = state["stocks"].get(clean_symbol, {}).get("price", 0)

        try:
            quantity = positive_integer(str(quantity), "Saved quantity")
            average_cost = positive_number(str(average_cost), "Saved average cost")
        except ValueError:
            continue

        if clean_symbol not in state["stocks"]:
            state["stocks"][clean_symbol] = {
                "symbol": clean_symbol,
                "name": clean_symbol,
                "sector": "Other",
                "price": average_cost,
                "history": [average_cost],
            }

        state["portfolio"][clean_symbol] = {
            "quantity": quantity,
            "average_cost": average_cost,
        }

    transactions = data.get("transactions", [])
    if isinstance(transactions, list):
        state["transactions"] = [
            item for item in transactions[-MAX_TRANSACTIONS:]
            if isinstance(item, dict)
        ]

    watchlist = data.get("watchlist", [])
    if isinstance(watchlist, list):
        for symbol in watchlist:
            try:
                clean_symbol = normalize_symbol(str(symbol))
            except ValueError:
                continue
            if clean_symbol not in state["watchlist"]:
                state["watchlist"].append(clean_symbol)

    alerts = data.get("alerts", [])
    if isinstance(alerts, list):
        state["alerts"] = [
            item for item in alerts
            if isinstance(item, dict)
            and item.get("symbol") in state["stocks"]
            and item.get("direction") in {"above", "below"}
            and isinstance(item.get("target"), (int, float))
            and item["target"] > 0
        ]

    try:
        state["cash"] = max(0.0, float(data.get("cash", 100000.00)))
    except (TypeError, ValueError):
        state["cash"] = 100000.00
    return state


def load_state():
    """Load saved data, returning a fresh state when no file exists."""
    if not DATA_FILE.exists():
        return fresh_state()

    try:
        with DATA_FILE.open("r", encoding="utf-8") as file:
            return normalize_state(json.load(file))
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Saved data could not be loaded: {error}")
        print("A fresh portfolio will be used; the saved file is unchanged.")
        return fresh_state()


def save_state(state):
    """Write application state to disk and report persistence failures."""
    try:
        with DATA_FILE.open("w", encoding="utf-8") as file:
            json.dump(state, file, indent=2)
    except OSError as error:
        print(f"Could not save portfolio data: {error}")


def pause():
    try:
        input("\nPress Enter to continue...")
    except EOFError:
        print() 


def print_header(title):
    print("\n" + "=" * 64)
    print(f"  {title}")
    print("=" * 64)


def ask_symbol(prompt):
    """Read a stock symbol without allowing blank input."""
    while True:
        try:
            return normalize_symbol(input(prompt))
        except ValueError as error:
            print(error)


def get_stock(state, symbol):
    """Return a known stock or raise a message suitable for the menu."""
    stock = state["stocks"].get(symbol)
    if stock is None:
        raise ValueError(f"{symbol} is not in the market list.")
    return stock


def list_market(state, stocks=None):
    """Display market stocks from a list of stock dictionaries."""
    selected = stocks if stocks is not None else list(state["stocks"].values())
    if not selected:
        print("No matching stocks were found.")
        return

    print(f"{'SYMBOL':<10}{'NAME':<24}{'SECTOR':<18}{'PRICE':>12}")
    print("-" * 64)
    for stock in selected:
        print(
            f"{stock['symbol']:<10}"
            f"{stock['name'][:22]:<24}"
            f"{stock['sector'][:16]:<18}"
            f"{money(stock['price']):>12}"
        )


def show_market(state):
    print_header("AVAILABLE SIMULATED STOCKS")
    stocks = sorted(state["stocks"].values(), key=lambda item: item["symbol"])
    list_market(state, stocks)
    print("\nPrices are sample values, not live market quotes.")
    pause()


def add_market_stock(state):
    print_header("ADD A STOCK TO THE SIMULATED MARKET")
    symbol = ask_symbol("New stock symbol: ")
    if symbol in state["stocks"]:
        print(f"{symbol} is already listed.")
        pause()
        return

    name = input("Company name: ").strip()
    if not name:
        name = symbol
    sector = input("Sector (optional): ").strip()
    if not sector:
        sector = "Other"

    try:
        price = positive_number(input("Starting price: "), "Price")
    except ValueError as error:
        print(error)
        pause()
        return

    state["stocks"][symbol] = {
        "symbol": symbol,
        "name": name,
        "sector": sector,
        "price": price,
        "history": [price],
    }
    save_state(state)
    print(f"{symbol} was added at {money(price)}.")
    pause()


def search_market(state):
    print_header("SEARCH THE MARKET")
    query = input("Search by symbol, company, or sector: ").strip().casefold()
    if not query:
        print("Search text cannot be empty.")
        pause()
        return

    matches = []
    for stock in state["stocks"].values():
        searchable = (
            f"{stock['symbol']} {stock['name']} {stock['sector']}"
        ).casefold()
        if query in searchable:
            matches.append(stock)

    list_market(state, sorted(matches, key=lambda item: item["symbol"]))
    pause()


def append_transaction(state, action, symbol, quantity, price, total):
    state["transactions"].append({
        "time": timestamp(),
        "action": action,
        "symbol": symbol,
        "quantity": quantity,
        "price": round(price, 4),
        "total": round(total, 2),
    })
    state["transactions"] = state["transactions"][-MAX_TRANSACTIONS:]


def buy_stock(state):
    print_header("BUY SHARES (PAPER TRADE)")
    symbol = ask_symbol("Stock symbol: ")
    try:
        stock = get_stock(state, symbol)
        quantity = positive_integer(input("Number of shares: "), "Quantity")
    except ValueError as error:
        print(error)
        pause()
        return

    price = stock["price"]
    total = price * quantity
    print(f"{quantity} x {symbol} at {money(price)} = {money(total)}")
    print(f"Available paper cash: {money(state['cash'])}")
    confirm = input("Confirm purchase? (y/n): ").strip().casefold()
    if confirm not in {"y", "yes"}:
        print("Purchase cancelled.")
        pause()
        return
    if total > state["cash"]:
        print("Not enough paper cash for this purchase.")
        pause()
        return

    old = state["portfolio"].get(symbol)
    if old is None:
        state["portfolio"][symbol] = {
            "quantity": quantity,
            "average_cost": price,
        }
    else:
        old_quantity = old["quantity"]
        new_quantity = old_quantity + quantity
        old_cost = old["average_cost"] * old_quantity
        state["portfolio"][symbol] = {
            "quantity": new_quantity,
            "average_cost": (old_cost + total) / new_quantity,
        }

    state["cash"] -= total
    append_transaction(state, "BUY", symbol, quantity, price, total)
    save_state(state)
    print(f"Purchased {quantity} share(s) of {symbol}.")
    pause()


def sell_stock(state):
    print_header("SELL SHARES (PAPER TRADE)")
    symbol = ask_symbol("Stock symbol: ")
    holding = state["portfolio"].get(symbol)
    if holding is None:
        print(f"You do not own any {symbol} shares.")
        pause()
        return

    print(f"Shares owned: {holding['quantity']}")
    try:
        quantity = positive_integer(input("Number of shares to sell: "), "Quantity")
    except ValueError as error:
        print(error)
        pause()
        return

    if quantity > holding["quantity"]:
        print("You cannot sell more shares than you own.")
        pause()
        return

    stock = state["stocks"].get(symbol)
    if stock is None:
        print(f"No simulated price is available for {symbol}.")
        pause()
        return

    price = stock["price"]
    total = price * quantity
    proceeds = input(f"Sell for {money(total)}? (y/n): ").strip().casefold()
    if proceeds not in {"y", "yes"}:
        print("Sale cancelled.")
        pause()
        return

    holding["quantity"] -= quantity
    if holding["quantity"] == 0:
        del state["portfolio"][symbol]
    state["cash"] += total
    append_transaction(state, "SELL", symbol, quantity, price, total)
    save_state(state)
    print(f"Sold {quantity} share(s) of {symbol} for {money(total)}.")
    pause()


def portfolio_totals(state):
    """Calculate cost basis, market value, and unrealized profit or loss."""
    cost_basis = 0.0
    market_value = 0.0
    for symbol, holding in state["portfolio"].items():
        stock = state["stocks"].get(symbol)
        if stock is None:
            continue
        cost_basis += holding["average_cost"] * holding["quantity"]
        market_value += stock["price"] * holding["quantity"]
    return cost_basis, market_value, market_value - cost_basis


def show_portfolio(state):
    print_header("MY PORTFOLIO")
    if not state["portfolio"]:
        print("Your portfolio is empty. Use Buy Shares to get started.")
        print(f"Paper cash: {money(state['cash'])}")
        pause()
        return

    print(
        f"{'SYMBOL':<10}{'SHARES':>9}{'AVG COST':>14}"
        f"{'PRICE':>14}{'VALUE':>14}"
    )
    print("-" * 64)
    for symbol, holding in sorted(state["portfolio"].items()):
        stock = state["stocks"].get(symbol)
        if stock is None:
            continue
        value = stock["price"] * holding["quantity"]
        print(
            f"{symbol:<10}{holding['quantity']:>9}"
            f"{money(holding['average_cost']):>14}"
            f"{money(stock['price']):>14}{money(value):>14}"
        )

    basis, value, profit_loss = portfolio_totals(state)
    return_percent = profit_loss / basis * 100 if basis else 0.0
    print("-" * 64)
    print(f"Cost basis:         {money(basis)}")
    print(f"Market value:       {money(value)}")
    print(f"Unrealized P/L:     {money(profit_loss)} ({return_percent:.2f}%)")
    print(f"Paper cash:         {money(state['cash'])}")
    print(f"Total account value:{money(state['cash'] + value):>14}")
    pause()


def show_transactions(state):
    print_header("RECENT TRANSACTIONS")
    transactions = state["transactions"]
    if not transactions:
        print("There are no transactions yet.")
        pause()
        return

    print(
        f"{'TIME':<22}{'ACTION':<8}{'SYMBOL':<9}"
        f"{'SHARES':>8}{'PRICE':>12}{'TOTAL':>13}"
    )
    print("-" * 72)
    for transaction in reversed(transactions[-20:]):
        print(
            f"{str(transaction.get('time', ''))[:19]:<22}"
            f"{transaction.get('action', ''):<8}"
            f"{transaction.get('symbol', ''):<9}"
            f"{transaction.get('quantity', 0):>8}"
            f"{money(transaction.get('price', 0)):>12}"
            f"{money(transaction.get('total', 0)):>13}"
        )
    print("\nShowing up to the latest 20 transactions.")
    pause()


def add_to_watchlist(state):
    print_header("ADD TO WATCHLIST")
    symbol = ask_symbol("Stock symbol: ")
    try:
        get_stock(state, symbol)
    except ValueError as error:
        print(error)
        pause()
        return

    if symbol in state["watchlist"]:
        print(f"{symbol} is already on your watchlist.")
    else:
        state["watchlist"].append(symbol)
        save_state(state)
        print(f"{symbol} was added to your watchlist.")
    pause()


def remove_from_watchlist(state):
    print_header("REMOVE FROM WATCHLIST")
    if not state["watchlist"]:
        print("Your watchlist is empty.")
        pause()
        return

    show_watchlist(state, wait=False)
    symbol = ask_symbol("Stock symbol to remove: ")
    if symbol not in state["watchlist"]:
        print(f"{symbol} is not on your watchlist.")
    else:
        state["watchlist"].remove(symbol)
        save_state(state)
        print(f"{symbol} was removed from your watchlist.")
    pause()


def show_watchlist(state, wait=True):
    print_header("MY WATCHLIST")
    if not state["watchlist"]:
        print("Your watchlist is empty.")
    else:
        stocks = [
            state["stocks"][symbol]
            for symbol in state["watchlist"]
            if symbol in state["stocks"]
        ]
        list_market(state, stocks)
    if wait:
        pause()


def add_price_alert(state):
    print_header("ADD PRICE ALERT")
    symbol = ask_symbol("Stock symbol: ")
    try:
        stock = get_stock(state, symbol)
        target = positive_number(input("Target price: "), "Target price")
    except ValueError as error:
        print(error)
        pause()
        return

    print(f"Current {symbol} price: {money(stock['price'])}")
    direction = input("Alert when price goes (above/below): ").strip().casefold()
    if direction not in {"above", "below"}:
        print("Choose either 'above' or 'below'.")
        pause()
        return

    state["alerts"].append({
        "symbol": symbol,
        "target": target,
        "direction": direction,
        "created": timestamp(),
    })
    save_state(state)
    print(f"Alert created: {symbol} {direction} {money(target)}.")
    pause()


def show_alerts(state):
    print_header("PRICE ALERTS")
    if not state["alerts"]:
        print("There are no active price alerts.")
        pause()
        return

    for index, alert in enumerate(state["alerts"], start=1):
        stock = state["stocks"].get(alert["symbol"])
        current = stock["price"] if stock else 0.0
        print(
            f"{index}. {alert['symbol']} {alert['direction']} "
            f"{money(alert['target'])} (now {money(current)})"
        )

    choice = input("\nEnter alert number to delete, or press Enter: ").strip()
    if choice:
        try:
            index = int(choice) - 1
            if index < 0 or index >= len(state["alerts"]):
                raise ValueError
        except ValueError:
            print("That is not a valid alert number.")
        else:
            removed = state["alerts"].pop(index)
            save_state(state)
            print(f"Deleted {removed['symbol']} price alert.")
    pause()


def check_price_alerts(state):
    """Print alerts that are triggered by a current simulated price."""
    triggered = []
    for alert in state["alerts"]:
        stock = state["stocks"].get(alert["symbol"])
        if stock is None:
            continue

        if alert["direction"] == "above":
            is_triggered = stock["price"] >= alert["target"]
        else:
            is_triggered = stock["price"] <= alert["target"]
        if is_triggered:
            triggered.append(alert)

    if triggered:
        print("\n*** PRICE ALERT ***")
        for alert in triggered:
            stock = state["stocks"][alert["symbol"]]
            print(
                f"{alert['symbol']} is {alert['direction']} "
                f"{money(alert['target'])}; current price "
                f"{money(stock['price'])}."
            )


def simulate_market(state):
    """Apply random price changes and keep a short list of recent prices."""
    print_header("SIMULATE ONE MARKET SESSION")
    changed = []
    for stock in state["stocks"].values():
        old_price = stock["price"]
        movement = random.uniform(-0.05, 0.05)
        new_price = max(0.01, old_price * (1 + movement))
        stock["price"] = round(new_price, 2)
        stock["history"].append(stock["price"])
        stock["history"] = stock["history"][-MAX_PRICE_HISTORY:]
        changed.append((stock["symbol"], old_price, stock["price"]))

    for symbol, old_price, new_price in sorted(changed):
        difference = new_price - old_price
        marker = "+" if difference >= 0 else ""
        print(
            f"{symbol:<8} {money(old_price):>12} -> "
            f"{money(new_price):>12} ({marker}{money(difference)})"
        )

    save_state(state)
    check_price_alerts(state)
    print("\nPrices were randomly changed by up to 5%.")
    pause()


def show_price_history(state):
    print_header("RECENT PRICE HISTORY")
    symbol = ask_symbol("Stock symbol: ")
    try:
        stock = get_stock(state, symbol)
    except ValueError as error:
        print(error)
        pause()
        return

    history = stock["history"]
    if len(history) < 2:
        print("There is not enough history. Simulate a market session first.")
    else:
        first = history[0]
        last = history[-1]
        for index, price in enumerate(history, start=1):
            bar_length = min(40, max(1, round(price / max(history) * 40)))
            print(f"{index:>2}: {money(price):>12} {'#' * bar_length}")
        change = last - first
        percent = change / first * 100
        print(f"\nChange over saved history: {money(change)} ({percent:.2f}%)")
    pause()


def show_market_movers(state):
    print_header("BIGGEST MOVERS IN THE LAST SESSION")
    changes = []
    for stock in state["stocks"].values():
        history = stock["history"]
        if len(history) >= 2 and history[-2] != 0:
            percent = (history[-1] - history[-2]) / history[-2] * 100
            changes.append((percent, stock))

    if not changes:
        print("Simulate a market session to calculate movers.")
        pause()
        return

    gainers = sorted(changes, key=lambda item: item[0], reverse=True)[:5]
    losers = sorted(changes, key=lambda item: item[0])[:5]
    print("\nTop gainers:")
    for percent, stock in gainers:
        print(f"  {stock['symbol']:<8} {percent:+.2f}%")
    print("\nTop decliners:")
    for percent, stock in losers:
        print(f"  {stock['symbol']:<8} {percent:+.2f}%")
    pause()


def show_sector_summary(state):
    print_header("PORTFOLIO BY SECTOR")
    sectors = {}
    for symbol, holding in state["portfolio"].items():
        stock = state["stocks"].get(symbol)
        if stock is None:
            continue
        sector = stock["sector"]
        value = stock["price"] * holding["quantity"]
        sectors[sector] = sectors.get(sector, 0.0) + value

    if not sectors:
        print("No portfolio holdings are available.")
    else:
        total = sum(sectors.values())
        for sector, value in sorted(
            sectors.items(), key=lambda item: item[1], reverse=True
        ):
            share = value / total * 100 if total else 0
            print(f"{sector:<20} {money(value):>14}  ({share:5.1f}%)")
    pause()


def export_transactions(state):
    print_header("EXPORT TRANSACTIONS")
    path_text = input("CSV file path (blank for portfolio_transactions.csv): ").strip()
    path = Path(path_text) if path_text else Path(__file__).with_name(
        "portfolio_transactions.csv"
    )
    headings = ["time", "action", "symbol", "quantity", "price", "total"]
    try:
        with path.open("w", encoding="utf-8", newline="") as file:
            import csv
            writer = csv.DictWriter(file, fieldnames=headings)
            writer.writeheader()
            for transaction in state["transactions"]:
                writer.writerow({
                    key: transaction.get(key, "")
                    for key in headings
                })
    except OSError as error:
        print(f"Could not export transactions: {error}")
    else:
        print(f"Exported {len(state['transactions'])} transactions to {path}.")
    pause()


def reset_portfolio(state):
    print_header("RESET PORTFOLIO")
    confirmation = input(
        "Delete holdings, transactions, alerts, and watchlist? (type RESET): "
    ).strip()
    if confirmation != "RESET":
        print("Reset cancelled.")
        pause()
        return

    state["portfolio"].clear()
    state["transactions"].clear()
    state["watchlist"].clear()
    state["alerts"].clear()
    state["cash"] = 100000.00
    save_state(state)
    print("Portfolio reset. Simulated market prices were not changed.")
    pause()


def show_market_statistics(state):
    print_header("SIMULATED MARKET STATISTICS")
    stocks = list(state["stocks"].values())
    if not stocks:
        print("There are no stocks in the market.")
        pause()
        return
    prices = [stock["price"] for stock in stocks]
    average = sum(prices) / len(prices)
    best = max(stocks, key=lambda stock: stock["price"])
    worst = min(stocks, key=lambda stock: stock["price"])
    print(f"Listed stocks: {len(stocks)}")
    print(f"Average share price: {money(average)}")
    print(f"Highest-priced: {best['symbol']} at {money(best['price'])}")
    print(f"Lowest-priced:  {worst['symbol']} at {money(worst['price'])}")
    print(f"Total of listed share prices: {money(sum(prices))}")
    sector_counts = {}
    for stock in stocks:
        sector = stock["sector"]
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
    print("\nNumber of listings by sector:")
    for sector, count in sorted(sector_counts.items()):
        print(f"  {sector:<20} {count}")
    history_sizes = [len(stock["history"]) for stock in stocks]
    average_points = sum(history_sizes) / len(history_sizes)
    print(f"\nAverage saved price-history points: {average_points:.1f}")
    print("Use the random-session option to refresh simulated prices.")
    pause()


def print_menu():
    print_header("STOCK PORTFOLIO TRACKER")
    menu_items = [
        ("1", "View available stocks"),
        ("2", "Search market"),
        ("3", "Add a stock to the market"),
        ("4", "Buy shares"),
        ("5", "Sell shares"),
        ("6", "View portfolio"),
        ("7", "View transactions"),
        ("8", "Simulate random market session"),
        ("9", "View stock price history"),
        ("10", "View market movers"),
        ("11", "View portfolio by sector"),
        ("12", "View / add / remove watchlist"),
        ("13", "Add price alert"),
        ("14", "View or delete price alerts"),
        ("15", "Export transactions to CSV"),
        ("16", "Reset portfolio"),
        ("17", "View simulated market statistics"),
        ("18", "Save portfolio"),
        ("0", "Save and exit"),
    ]
    for number, title in menu_items:
        print(f"{number:>2}. {title}")
    print("\nStarting paper cash: $100,000.00")


def watchlist_menu(state):
    """Offer watchlist operations in a small nested while loop."""
    while True:
        print_header("WATCHLIST")
        print("1. View watchlist")
        print("2. Add stock")
        print("3. Remove stock")
        print("0. Back to main menu")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            show_watchlist(state)
        elif choice == "2":
            add_to_watchlist(state)
        elif choice == "3":
            remove_from_watchlist(state)
        elif choice == "0":
            break
        else:
            print("Invalid choice. Enter 1, 2, 3, or 0.")
            pause()


def handle_choice(state, choice):
    """Run one menu action and return whether the app should keep running."""
    if choice == "1":
        show_market(state)
    elif choice == "2":
        search_market(state)
    elif choice == "3":
        add_market_stock(state)
    elif choice == "4":
        buy_stock(state)
    elif choice == "5":
        sell_stock(state)
    elif choice == "6":
        show_portfolio(state)
    elif choice == "7":
        show_transactions(state)
    elif choice == "8":
        simulate_market(state)
    elif choice == "9":
        show_price_history(state)
    elif choice == "10":
        show_market_movers(state)
    elif choice == "11":
        show_sector_summary(state)
    elif choice == "12":
        watchlist_menu(state)
    elif choice == "13":
        add_price_alert(state)
    elif choice == "14":
        show_alerts(state)
    elif choice == "15":
        export_transactions(state)
    elif choice == "16":
        reset_portfolio(state)
    elif choice == "17":
        show_market_statistics(state)
    elif choice == "18":
        save_state(state)
        print("Portfolio saved to disk.")
        pause()
    elif choice == "0":
        save_state(state)
        print("Portfolio saved. Goodbye!")
        return False
    else:
        print("Invalid option. Please select a number from the menu.")
        pause()
    return True


def main():
    """Start the interactive stock portfolio application."""
    state = load_state()
    print("Prices in this program are simulated and are not live quotes.")
    check_price_alerts(state)

    running = True
    while running:
        print_menu()
        choice = input("Select an option: ").strip()
        running = handle_choice(state, choice)


if __name__ == "__main__":
    main()
