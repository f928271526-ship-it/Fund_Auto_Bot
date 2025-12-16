# analysis.py
# --- 分析大脑：负责从数据库取数，计算指标，画图，给出建议 ---

import pandas as pd
from sqlalchemy import create_engine
from urllib.parse import quote_plus
import config 

# --- 【新增】引入画图库 ---
import matplotlib.pyplot as plt
# 设置中文 (防止乱码)
import platform # 用来判断操作系统

# 根据系统自动选择字体
sys_name = platform.system()
if sys_name == 'Windows':
    plt.rcParams['font.sans-serif'] = ['SimHei'] # Windows 用 SimHei
elif sys_name == 'Darwin':
    # Mac 系统 (Darwin) 通常用 Arial Unicode MS 或者 PingFang HK
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS'] 
else:
    # Linux (云服务器) 用这个
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei']

plt.rcParams['axes.unicode_minus'] = False # 解决负号显示问题
class FundAnalyzer:
    def __init__(self):
        """初始化：连接数据库"""
        db_cfg = config.DB_CONFIG
        # 处理密码特殊字符
        safe_pass = quote_plus(db_cfg['password'])
        self.conn_str = f"mysql+pymysql://{db_cfg['user']}:{safe_pass}@{db_cfg['host']}:{db_cfg['port']}/{db_cfg['database']}"
        self.engine = create_engine(self.conn_str)

    def get_fund_data(self, fund_code, limit=120):
        """从阿里云读取最近 N 天的数据"""
        # 注意：这里读取时，直接按日期升序排好
        sql = f"SELECT * FROM fund_nav_history WHERE fund_code = '{fund_code}' ORDER BY nav_date ASC"
        df = pd.read_sql(sql, self.engine)
        return df.tail(limit)

    def calculate_indicators(self, df):
        """【新增】专门负责算指标的工具函数 (复用逻辑)"""
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

    def plot_and_save(self, df, code, name):
        """【新增】画出战术图并保存"""
        # 如果数据太少，就不画了，防止报错
        if len(df) < 30:
            return None

        print(f"🎨 正在绘制 {name} 的战术图...")
        
        # 准备画布 (上下两张)
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
        
        # --- 上图：净值 + 布林带 ---
        # df['nav_date'] 是日期列
        ax1.plot(df['nav_date'], df['nav_value'], label='净值', color='black')
        ax1.plot(df['nav_date'], df['upper'], label='上轨', color='green', linestyle='--', alpha=0.5)
        ax1.plot(df['nav_date'], df['lower'], label='下轨', color='red', linestyle='--', alpha=0.5)
        ax1.fill_between(df['nav_date'], df['upper'], df['lower'], color='gray', alpha=0.1)
        ax1.set_title(f'{name} ({code}) 布林带战术', fontsize=12)
        ax1.legend(loc='upper left')
        ax1.grid(True)
        
        # --- 下图：RSI ---
        ax2.plot(df['nav_date'], df['rsi'], label='RSI(14)', color='purple')
        ax2.axhline(30, color='green', linestyle='--') # 超卖线
        ax2.axhline(70, color='red', linestyle='--')   # 超买线
        ax2.set_title('RSI 情绪指标', fontsize=12)
        ax2.set_ylim(0, 100)
        ax2.legend(loc='upper left')
        ax2.grid(True)
        
        # 保存图片
        # 格式：名字_日期.png
        today_str = df.iloc[-1]['nav_date'].strftime('%Y%m%d') # 比如 20251209
        filename = f"{name}_{today_str}.png"
        
        plt.savefig(filename)
        plt.close() # 关掉画布，释放内存
        
        return filename

    def run_analysis(self):
        """指挥官：批量分析"""
        print("🧠 === 开始量化分析 ===")
        results = []
        
        for code, name in config.MY_FUNDS.items():
            # 1. 取数
            df = self.get_fund_data(code)
            if df.empty:
                print(f"⚠️ {name}: 没数据，跳过")
                continue
            
            # 2. 算指标 (调用新写的函数)
            df = self.calculate_indicators(df)
            
            # 3. 画图 (拍照)
            self.plot_and_save(df, code, name)
            
            # 4. 生成文字报告 (逻辑与之前一致)
            latest = df.iloc[-1]
            price = latest['nav_value']
            rsi = latest['rsi']
            lower = latest['lower']
            date_str = latest['nav_date'].strftime('%Y-%m-%d')
            
            # 计算距离下轨的空间
            # 注意：如果刚才计算产生了NaN(比如刚上市的基金)，这里要防错
            if pd.isna(lower):
                dist_to_low = 0
            else:
                dist_to_low = (price - lower) / lower * 100

            # 简单的策略逻辑
            signal = "☁️ 观望"
            if rsi < 30: signal = "💎 极度超卖"
            elif dist_to_low < 0: signal = "🔥 跌破下轨"
            elif rsi > 70: signal = "🚨 过热"
            
            report = f"{name}: {date_str} | RSI:{rsi:.1f} | 信号:{signal}"
            print(report)
            results.append(report)
            
        print("🏁 === 分析结束，图片已生成 ===")
        return "\n".join(results)

# --- 测试代码 ---
if __name__ == "__main__":
    brain = FundAnalyzer()
    brain.run_analysis()