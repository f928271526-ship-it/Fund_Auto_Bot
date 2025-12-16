# backtest.py
# --- 回测系统：用历史数据验证策略 ---

import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import create_engine
from urllib.parse import quote_plus
import config 

# 中文设置
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

class Backtest:
    def __init__(self, fund_code, initial_cash=1000):
        """
        fund_code: 要回测的基金
        initial_cash: 初始本金 (比如 1000元)
        """
        self.code = fund_code
        self.cash = initial_cash
        self.share = 0 # 持有份额
        self.initial_cash = initial_cash
        
        # 连接数据库
        db_cfg = config.DB_CONFIG
        safe_pass = quote_plus(db_cfg['password'])
        conn_str = f"mysql+pymysql://{db_cfg['user']}:{safe_pass}@{db_cfg['host']}:{db_cfg['port']}/{db_cfg['database']}"
        self.engine = create_engine(conn_str)

    def prepare_data(self):
        """准备数据：算出 RSI"""
        print(f"📊 正在准备 {self.code} 的历史数据...")
        sql = f"SELECT nav_date, nav_value FROM fund_nav_history WHERE fund_code = '{self.code}' ORDER BY nav_date ASC"
        df = pd.read_sql(sql, self.engine)
        
        # 算 RSI (直接复用之前的逻辑)
        df['change'] = df['nav_value'].diff()
        df['gain'] = df['change'].clip(lower=0)
        df['loss'] = df['change'].clip(upper=0).abs()
        avg_gain = df['gain'].ewm(alpha=1/14, adjust=False).mean()
        avg_loss = df['loss'].ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        return df.dropna()

    def run(self):
        """开始模拟交易"""
        df = self.prepare_data()
        
        # 记录每一天的总资产
        portfolio_values = []
        buy_signals = [] # 记录买点
        sell_signals = [] # 记录卖点
        
        print("🎮 回测开始！模拟交易中...")
        
        # 遍历每一天
        for i in range(len(df)):
            today = df.iloc[i]
            price = today['nav_value']
            rsi = today['rsi']
            date = today['nav_date']
            
            # --- 策略逻辑 (RSI) ---
            
            # 买入信号：RSI < 30 且 还有钱
            if rsi < 30 and self.cash > 0:
                # 全仓买入 (为了简化计算，假设每次都梭哈)
                # 实际上你可以写成 "买300元"
                buy_share = self.cash / price
                self.share += buy_share
                self.cash = 0
                buy_signals.append((date, price))
                # print(f"💎 {date} 买入: 价格 {price:.4f}, RSI {rsi:.2f}")
                
            # 卖出信号：RSI > 70 且 有持仓
            elif rsi > 70 and self.share > 0:
                # 全仓卖出
                sell_amount = self.share * price
                self.cash += sell_amount
                self.share = 0
                sell_signals.append((date, price))
                # print(f"🔥 {date} 卖出: 价格 {price:.4f}, RSI {rsi:.2f}")
            
            # 计算当天总资产 (现金 + 持仓市值)
            total_value = self.cash + (self.share * price)
            portfolio_values.append(total_value)
            
        # --- 结果结算 ---
        df['total_value'] = portfolio_values
        final_value = df.iloc[-1]['total_value']
        profit = (final_value - self.initial_cash) / self.initial_cash * 100
        
        # 基准收益 (如果一开始就买入并死拿不动)
        start_price = df.iloc[0]['nav_value']
        end_price = df.iloc[-1]['nav_value']
        base_profit = (end_price - start_price) / start_price * 100
        
        print("-" * 30)
        print(f"🏆 回测报告 ({self.code}):")
        print(f"初始资金: {self.initial_cash} 元")
        print(f"最终资产: {final_value:.2f} 元")
        print(f"🤖 策略收益率: {profit:.2f}%")
        print(f"🐢 死拿收益率: {base_profit:.2f}%")
        
        if profit > base_profit:
            print("✅ 结论：瞎折腾比死拿强！策略有效！")
        else:
            print("❌ 结论：一顿操作猛如虎，不如原地葛优躺。")
            
        # --- 画图 ---
        plt.figure(figsize=(12, 6))
        plt.plot(df['nav_date'], df['total_value'], label='我的资产曲线', color='red')
        
        # 把买卖点标出来
        # 解压买卖点列表
        if buy_signals:
            b_dates, b_prices = zip(*buy_signals)
            # 注意：这里的Y轴要对应资产，简单起见我们只标日期
            for date, price in buy_signals:
                plt.axvline(x=date, color='gray', linestyle=':', alpha=0.5)
        
        plt.title(f'RSI 策略回测资金曲线 (最终: {final_value:.0f})', fontsize=15)
        plt.legend()
        plt.grid(True)
        plt.show()

# --- 运行 ---
if __name__ == "__main__":
    # 回测一下国泰证券
    bot = Backtest('012363', initial_cash=1000)
    bot.run()