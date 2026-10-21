import os
import time
import requests
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# Fetch keys securely from the server's hidden environment variables
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

# --- YOUR API CREDENTIALS ---
API_KEY = "your_key_here"
SECRET_KEY = "secret key here"

# Initialize Alpaca Clients (Paper Trading Mode)
trading_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

# Watchlist & Risk Limits
WATCHLIST = ["SPY", "QQQ"]
MAX_SPREAD_PCT = 10.0
MAX_DAILY_TRADES = 2  # Safety cap so it doesn't over-trade while you're away
trades_executed_today = 0

def check_account():
    try:
        account = trading_client.get_account()
        print(f"[INIT] Connected to Alpaca Paper Trading. Cash Balance: ${float(account.cash):,.2f}")
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")

def execute_paper_trade(contract_symbol):
    global trades_executed_today
    if trades_executed_today >= MAX_DAILY_TRADES:
        print("[SAFETY] Daily trade limit reached. Skipping execution.")
        return

    try:
        order_request = MarketOrderRequest(
            symbol=contract_symbol,
            qty=1,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY
        )
        paper_order = trading_client.submit_order(order_data=order_request)
        trades_executed_today += 1
        print(f"🚀 [AUTOMATED BUY] Successfully placed paper order for: {contract_symbol}")
    except Exception as e:
        print(f"❌ [ORDER ERROR] Failed to execute trade: {e}")

def run_background_bot():
    print("\n🤖 Automated Paper Trading Bot is running...")
    
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
                                
                                # If a contract meets clean liquidity rules, trigger automated trade
                                if spread_pct <= MAX_SPREAD_PCT and opt_ask > 0.10:
                                    print(f"🎯 [MATCH FOUND] {opt_symbol} | Spread: {spread_pct:.1f}%")
                                    execute_paper_trade(opt_symbol)
                                    break  # Take the first clean match and wait for next cycle
                                    
        except Exception as e:
            print(f"[LOOP ERROR] {e}")

        # Wait 2 minutes between scan cycles to conserve API limits
        time.sleep(120)

if __name__ == "__main__":
    check_account()
    run_background_bot()