# analysis.py
# --- 分析大脑：负责从数据库取数，计算指标，画图，给出建议 ---

import pandas as pd
import numpy as np # 需要用到 concat
from sqlalchemy import create_engine
from urllib.parse import quote_plus
import config 

# --- 引入画图库 ---
import matplotlib.pyplot as plt
import platform

# 根据系统自动选择字体
sys_name = platform.system()
if sys_name == 'Windows':
    plt.rcParams['font.sans-serif'] = ['SimHei']
elif sys_name == 'Darwin': # Mac
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS'] 
else:
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei']

plt.rcParams['axes.unicode_minus'] = False

class FundAnalyzer:
    def __init__(self):
        """初始化：连接数据库"""
        db_cfg = config.DB_CONFIG
        safe_pass = quote_plus(db_cfg['password'])
        self.conn_str = f"mysql+pymysql://{db_cfg['user']}:{safe_pass}@{db_cfg['host']}:{db_cfg['port']}/{db_cfg['database']}"
        self.engine = create_engine(self.conn_str)

    def get_fund_data(self, fund_code, limit=120):
        """读取数据"""
        sql = f"SELECT * FROM fund_nav_history WHERE fund_code = '{fund_code}' ORDER BY nav_date ASC"
        df = pd.read_sql(sql, self.engine)
        return df.tail(limit)

    def calculate_indicators(self, df):
        """计算 RSI 和 布林带"""
        # 1. 算 RSI
        df['change'] = df['nav_value'].diff()
        df['gain'] = df['change'].clip(lower=0)
        df['loss'] = df['change'].clip(upper=0).abs()
        avg_gain = df['gain'].ewm(alpha=1/14, adjust=False).mean()
        avg_loss = df['loss'].ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # 2. 算 布林带
        df['mid'] = df['nav_value'].rolling(window=20).mean()
        df['std'] = df['nav_value'].rolling(window=20).std()
        df['upper'] = df['mid'] + 2 * df['std']
        df['lower'] = df['mid'] - 2 * df['std']
        
        return df

    def predict_next_rsi_target(self, df, target_rsi=30):
        """
        🔮 奇异博士算法：倒推明天跌多少，RSI 会变成 30？
        """
        today = df.iloc[-1]
        last_price = today['nav_value']
        
        # 暴力搜索：从 +5% 到 -10%
        # 使用 numpy 生成序列更高效
        for change_pct in [x * 0.1 for x in range(50, -100, -1)]: 
            sim_price = last_price * (1 + change_pct / 100)
            
            # 构造临时数据
            temp_df = df.copy().tail(30) 
            # 兼容性写法：使用 pd.DataFrame 构造新行
            new_row = pd.DataFrame({'nav_value': [sim_price]})
            temp_df = pd.concat([temp_df, new_row], ignore_index=True)
            
            # 重算 RSI (只算最后部分)
            temp_df['change'] = temp_df['nav_value'].diff()
            temp_df['gain'] = temp_df['change'].clip(lower=0)
            temp_df['loss'] = temp_df['change'].clip(upper=0).abs()
            
            avg_gain = temp_df['gain'].ewm(alpha=1/14, adjust=False).mean()
            avg_loss = temp_df['loss'].ewm(alpha=1/14, adjust=False).mean()
            
            # 防错：除以0
            if avg_loss.iloc[-1] == 0:
                sim_rsi = 100
            else:
                rs = avg_gain.iloc[-1] / avg_loss.iloc[-1]
                sim_rsi = 100 - (100 / (1 + rs))
            
            if sim_rsi <= target_rsi:
                return change_pct, sim_price
                
        return None, None

    def plot_and_save(self, df, code, name):
        """画图并保存"""
        if len(df) < 30: return None

        print(f"🎨 绘制 {name}...")
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
        
        # 上图：布林带
        ax1.plot(df['nav_date'], df['nav_value'], label='净值', color='black')
        ax1.plot(df['nav_date'], df['upper'], label='上轨', color='green', linestyle='--', alpha=0.5)
        ax1.plot(df['nav_date'], df['lower'], label='下轨', color='red', linestyle='--', alpha=0.5)
        ax1.fill_between(df['nav_date'], df['upper'], df['lower'], color='gray', alpha=0.1)
        ax1.set_title(f'{name} ({code}) 布林带战术', fontsize=12)
        ax1.legend(loc='upper left')
        ax1.grid(True)
        
        # 下图：RSI
        ax2.plot(df['nav_date'], df['rsi'], label='RSI(14)', color='purple')
        ax2.axhline(30, color='green', linestyle='--')
        ax2.axhline(70, color='red', linestyle='--')
        ax2.set_title('RSI 情绪指标', fontsize=12)
        ax2.set_ylim(0, 100)
        ax2.legend(loc='upper left')
        ax2.grid(True)
        
        today_str = df.iloc[-1]['nav_date'].strftime('%Y%m%d')
        filename = f"{name}_{today_str}.png"
        plt.savefig(filename)
        plt.close()
        return filename

    def run_analysis(self):
        """指挥官：批量分析"""
        print("🧠 === 开始量化分析 ===")
        results = [] # 这是一个列表，用来装所有的文字报告
        
        for code, name in config.MY_FUNDS.items():
            # 1. 取数
            df = self.get_fund_data(code)
            if df.empty:
                print(f"⚠️ {name}: 没数据")
                continue
            
            # 2. 算指标
            df = self.calculate_indicators(df)
            
            # 3. 画图
            self.plot_and_save(df, code, name)
            
            # 4. 生成报告
            latest = df.iloc[-1]
            price = latest['nav_value']
            rsi = latest['rsi']
            lower = latest['lower']
            date_str = latest['nav_date'].strftime('%Y-%m-%d')
            
            # 算距离
            if pd.isna(lower): dist_to_low = 0
            else: dist_to_low = (price - lower) / lower * 100

            # 策略逻辑
            signal = "☁️ 观望"
            if rsi < 30: signal = "💎 极度超卖"
            elif dist_to_low < 0: signal = "🔥 跌破下轨"
            elif rsi > 70: signal = "🚨 过热"
            
            # 🔮 调用预测算法 (倒推明日)
            target_drop, target_price = self.predict_next_rsi_target(df, target_rsi=30)
            predict_msg = "安全(跌停也不破30)"
            if target_drop is not None:
                predict_msg = f"跌 {target_drop:.1f}% (价位{target_price:.4f}) 破30"

            # 组装单条报告
            report_item = (
                f"基金: {name}\n"
                f"日期: {date_str} | RSI: {rsi:.1f}\n"
                f"信号: {signal}\n"
                f"🔮 {predict_msg}\n"
                f"----------------"
            )
            print(report_item)
            
            # 【关键一步】把这一条塞进列表里！之前就是漏了逻辑或者没塞进去
            results.append(report_item)
            
        print("🏁 === 分析结束 ===")
        
        # 如果列表是空的，说明出问题了，手动加一条报错
        if not results:
            return "⚠️ 分析结果为空，请检查数据库数据！"
            
        # 把列表拼成字符串返回
        return "\n".join(results)

# --- 测试代码 ---
if __name__ == "__main__":
    brain = FundAnalyzer()
    print(brain.run_analysis())