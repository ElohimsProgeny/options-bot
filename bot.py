import os
import time
import requests
import threading
from flask import Flask
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# --- MINI WEB SERVER (To satisfy Render's port requirement) ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Options Bot is running live in the background with data tracking!"

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- TRADING BOT LOGIC ---
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

WATCHLIST = ["SPY", "QQQ"]
MAX_SPREAD_PCT = 10.0
MAX_DAILY_TRADES = 2
trades_executed_today = 0

def log_market_match(contract_symbol, bid, ask, spread_pct, executed):
    """Records every matching contract into Render's cloud logs for offline analysis"""
    print(f"📊 [DATA LOG] Time: {time.strftime('%Y-%m-%d %H:%M:%S')} | "
          f"Contract: {contract_symbol} | Bid: ${bid:.2f} | Ask: ${ask:.2f} | "
          f"Spread: {spread_pct:.2f}% | Trade Executed: {executed}")

def execute_paper_trade(contract_symbol):
    global trades_executed_today
    if trades_executed_today >= MAX_DAILY_TRADES:
        print("[SAFETY] Daily trade limit reached. Skipping execution, but logging data.")
        return

    try:
        order_request = MarketOrderRequest(
            symbol=contract_symbol,
            qty=1,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY
        )
        trading_client.submit_order(order_data=order_request)
        trades_executed_today += 1
        print(f"🚀 [AUTOMATED BUY] Placed paper order for: {contract_symbol}")
    except Exception as e:
        print(f"❌ [ORDER ERROR] {e}")

def run_background_bot():
    print("\n🤖 Automated Paper Trading Bot & Data Tracker started...")
    while True:
        try:
            request_params = StockLatestQuoteRequest(symbol_or_symbols=WATCHLIST)
            latest_quotes = data_client.get_stock_latest_quote(request_params)
            
            for symbol in WATCHLIST:
                quote = latest_quotes.get(symbol)
                if quote:
                    url = f"https://data.alpaca.markets/v1beta1/options/snapshots/{symbol}"
                    headers = {
                        "accept": "application/json",
                        "APCA-API-KEY-ID": API_KEY,
                        "APCA-API-SECRET-KEY": SECRET_KEY
                    }
                    response = requests.get(url, headers=headers, params={"type": "call", "limit": 10})
                    
                    if response.status_code == 200:
                        snapshots = response.json().get("snapshots", {})
                        for opt_symbol, snapshot in snapshots.items():
                            l_quote = snapshot.get("latest_quote", {})
                            opt_bid = l_quote.get("bp", 0.0)
                            opt_ask = l_quote.get("ap", 0.0)
                            
                            if opt_ask > 0:
                                spread_pct = ((opt_ask - opt_bid) / opt_ask) * 100
                                
                                # Check if contract meets liquidity rules
                                if spread_pct <= MAX_SPREAD_PCT and opt_ask > 0.10:
                                    is_trading = trades_executed_today < MAX_DAILY_TRADES
                                    
                                    # ALWAYS log the data point regardless of trade limit
                                    log_market_match(opt_symbol, opt_bid, opt_ask, spread_pct, executed=is_trading)
                                    
                                    # Execute trade only if under the daily limit
                                    if is_trading:
                                        execute_paper_trade(opt_symbol)
                                        break
        except Exception as e:
            print(f"[LOOP ERROR] {e}")

        time.sleep(120)

if __name__ == "__main__":
    # Start the trading bot and data tracker in a background thread
    bot_thread = threading.Thread(target=run_background_bot)
    bot_thread.daemon = True
    bot_thread.start()
    
    # Run the web server on the main thread to satisfy Render's port requirement
    run_web_server()
