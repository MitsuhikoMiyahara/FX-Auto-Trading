import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import os

# シンボル設定
SYMBOL = "BTCJPY"
TIMEFRAME = mt5.TIMEFRAME_M1  # 1分足データ
HISTORY_BARS = 20  # 過去20本のデータを使用

# MT5に接続
def connect_mt5():
    if not mt5.initialize():
        print("MT5に接続できません")
        return False
    print("MT5に接続しました")
    return True

# 口座情報を取得
def get_account_info():
    account_info = mt5.account_info()
    if account_info is None:
        print("口座情報を取得できません")
        return None, None
    return account_info.balance, account_info.equity

# 現在のポジションを取得
def get_positions(symbol):
    positions = mt5.positions_get(symbol=symbol)
    return positions if positions else None

# ✅ ボリンジャーバンドを計算して取得
def get_market_data(symbol, num_bars=HISTORY_BARS):
    """ 指定したシンボルの市場データ（価格とボリンジャーバンド）を取得 """
    rates = mt5.copy_rates_from_pos(symbol, TIMEFRAME, 0, num_bars)

    if rates is None or len(rates) == 0:
        print(f"⚠️ {symbol} の市場データを取得できません")
        return None

    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
    df.rename(columns={'close': 'Price'}, inplace=True)

    # ✅ ボリンジャーバンドの計算
    df['SMA'] = df['Price'].rolling(window=20).mean()
    df['STD'] = df['Price'].rolling(window=20).std()
    df['UpperBB'] = df['SMA'] + 2 * df['STD']  # 上限 (2σ)
    df['LowerBB'] = df['SMA'] - 2 * df['STD']  # 下限 (2σ)

    df.dropna(inplace=True)  # 欠損値を削除

    return df

# 決済
def close_position(symbol):
    """ 指定したシンボルのポジションをすべて決済 """
    positions = get_positions(symbol)
    if not positions:
        return False  # 決済するポジションがない場合は終了

    for pos in positions:
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(symbol).bid if close_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(symbol).ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": pos.volume,
            "type": close_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 10,
            "magic": 0,
            "comment": "Python_Close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"✅ {symbol} のポジション決済成功！")
        else:
            print(f"❌ {symbol} のポジション決済失敗: {result.retcode}")
            return False
    return True

# メイン処理
if __name__ == "__main__":
    if connect_mt5():
        while True:
            # 🔹 口座情報 & ポジション確認
            balance, equity = get_account_info()
            positions = get_positions(SYMBOL)

            if balance is None:
                print("❌ 口座情報取得エラー")
                time.sleep(10)
                continue

            action = "HOLD"

            # ✅ ボリンジャーバンドの計算
            market_data = get_market_data(SYMBOL)
            if market_data is not None:
                latest = market_data.iloc[-1]
                print(f"📊 ボリンジャーバンド (最新): Price={latest['Price']:.2f}, UpperBB={latest['UpperBB']:.2f}, LowerBB={latest['LowerBB']:.2f}")

                if latest['Price'] > latest['UpperBB']:
                    action = "SELL"
                elif latest['Price'] < latest['LowerBB']:
                    action = "BUY"


            # 🔹 新規注文（BUY / SELL）
            if action == "BUY":
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": SYMBOL,
                    "volume": 0.01,
                    "type": mt5.ORDER_TYPE_BUY,
                    "price": mt5.symbol_info_tick(SYMBOL).ask,
                    "deviation": 10,
                    "magic": 0,
                    "comment": "GA Trader Buy",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                result = mt5.order_send(request)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"✅ BTCJPY を購入しました。価格: {result.price}")
                else:
                    print(f"❌ 購入失敗: {result.comment}")

            elif action == "SELL":
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": SYMBOL,
                    "volume": 0.01,
                    "type": mt5.ORDER_TYPE_SELL,
                    "price": mt5.symbol_info_tick(SYMBOL).bid,
                    "deviation": 10,
                    "magic": 0,
                    "comment": "GA Trader Sell",
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                result = mt5.order_send(request)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"✅ BTCJPY を売却しました。価格: {result.price}")
                else:
                    print(f"❌ 売却失敗: {result.comment}")

            # 🔹 ポジション決済
            close_position(SYMBOL)

            # 🔹 5秒待機
            time.sleep(10)