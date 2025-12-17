import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns


plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# --- 1. 定义宏观战队 (Global Macro Teams) ---
# 我为你精选了各赛道的代表性基金 (多为 ETF 联接 C 类)
sectors = {
   # --- 你的持仓 ---
    '012363': '国泰证券 (牛市旗手)',
    '013275': '富国煤炭 (旧能源/防守)',
    
    # --- 科技进攻 (全球主线) ---
    '024663': '富国创业板人工智能 (人工智能)', 
    '018957': '中航机遇领航 (CPO/6G)', 
    '010524':'银华中证5G',
    
    # --- 制造出海 (中国优势) ---
    '005538': '中航新起航 (新能源/固态)',
    
    # --- 宏观避险 (降息/战争) ---
    '019005': '国投白银 (贵金属/抗通胀)' 
}

print("🌍 正在扫描全球宏观赛道，数据量较大请稍候...")

# 咱们看最近 60 个交易日 (大约一个季度) 的表现
lookback_days = 60
combined_df = pd.DataFrame()

# --- 2. 循环抓取 & 归一化 ---
for code, name in sectors.items():
    print(f"📡 连线: {name}...")
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        df['date'] = pd.to_datetime(df['净值日期'])
        df['price'] = pd.to_numeric(df['单位净值'])
        df = df.sort_values('date').set_index('date')
        
        # 只取最近 N 天
        recent = df['price'].tail(lookback_days)
        
        # 【核心步骤】归一化 (Rebase)
        # 让所有基金在 60 天前都变成 1.0 (起点公平)
        # 公式: 今天的价格 / 起跑线的价格
        start_price = recent.iloc[0]
        normalized_trend = recent / start_price
        
        combined_df[name] = normalized_trend
        
    except Exception as e:
        print(f"❌ {name} 数据获取失败: {e}")

# --- 3. 可视化 (赛马图) ---
plt.figure(figsize=(14, 8))

# 遍历每一列画线
# 你的持仓用虚线，热门赛道用实线，方便对比
for column in combined_df.columns:
    linewidth = 2
    linestyle = '-'
    alpha = 0.8
    
    if '国泰证券' in column or '富国煤炭' in column:
        linewidth = 3
        linestyle = '--' # 虚线表示你的持仓
        alpha = 1.0      # 高亮显示
        
    plt.plot(combined_df.index, combined_df[column], label=column, linewidth=linewidth, linestyle=linestyle, alpha=alpha)

plt.axhline(1.0, color='black', linestyle=':', alpha=0.5) # 成本线
plt.title(f'全球宏观对冲雷达：最近 {lookback_days} 交易日收益走势 (起点=1.0)', fontsize=16)
plt.ylabel('累计收益倍数 (1.2 = 赚20%)')
plt.grid(True, alpha=0.3)
plt.legend(loc='upper left', fontsize=10)
plt.show()

# --- 4. 生成战力榜 ---
# 算一下这一季度的总涨幅
total_return = (combined_df.iloc[-1] - 1) * 100
rank = total_return.sort_values(ascending=False)

print("\n🏆 本季度宏观战力排行榜:")
print(rank)

# --- 5. AI 时政分析 ---
champion = rank.index[0]
print("-" * 40)
print(f"👑 当前王者：【{champion}】")
if 'AI' in champion or '通信' in champion:
    print("💡 宏观逻辑：全球算力军备竞赛。OpenAI、英伟达持续创新高，带动国内光模块(CPO)产业链爆发。")
    print("👉 建议：这是进攻矛，大跌大买，回调是机会。")
elif '白银' in champion:
    print("💡 宏观逻辑：避险情绪升温 + 工业需求复苏。地缘冲突不断，且光伏/电子行业需要大量白银。")
    print("👉 建议：这是避险盾，适合配置对抗不确定性。")
elif '电池' in champion:
    print("💡 宏观逻辑：超跌反弹 + 固态电池技术突破。")
print("-" * 40)  





