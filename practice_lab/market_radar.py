import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime

# Mac 字体设置
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# --- 1. 定义赛道名单 (主流板块代表基金) ---
# 这里我选了各板块比较有代表性的 ETF 联接 C 类
sectors = {
    '012363': '国泰证券 (你的)',
    '015916': '永赢医药 (你的)',
    '013275': '富国煤炭 (你的)',
    '008282': '国泰半导体 (科技进攻)',  # 芯片/科技代表
    '012414': '招商白酒 (消费防守)',  # 白酒代表
    '001593': '天弘新能源 (过气王者)' # 新能源代表
}

print("📡 正在扫描全市场热门赛道...")

ranking_data = []

# --- 2. 循环抓取数据 ---
for code, name in sectors.items():
    print(f"   正在分析: {name}...")
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        df['净值日期'] = pd.to_datetime(df['净值日期'])
        df['单位净值'] = pd.to_numeric(df['单位净值'])
        df = df.sort_values('净值日期')
        
        # --- 3. 计算动量 (Momentum) ---
        # 动量 = (现在的价格 - N天前的价格) / N天前的价格
        # 我们看两个周期：
        # 短期 (5天): 爆发力
        # 中期 (20天): 趋势强度
        
        latest_price = df.iloc[-1]['单位净值']
        
        # 5日涨幅
        price_5d_ago = df.iloc[-6]['单位净值'] # 倒数第6天
        mom_5d = (latest_price - price_5d_ago) / price_5d_ago * 100
        
        # 20日涨幅
        price_20d_ago = df.iloc[-21]['单位净值']
        mom_20d = (latest_price - price_20d_ago) / price_20d_ago * 100
        
        ranking_data.append({
            '板块': name,
            '短期爆发 (5日)': mom_5d,
            '中期趋势 (20日)': mom_20d,
            '综合得分': mom_5d + mom_20d  # 简单加权
        })
        
    except Exception as e:
        print(f"❌ {name} 获取失败: {e}")

# --- 4. 生成排行榜 ---
rank_df = pd.DataFrame(ranking_data)
# 按综合得分从高到低排序
rank_df = rank_df.sort_values('综合得分', ascending=False).reset_index(drop=True)

print("\n🏆 全市场战力排行榜 (Momentum Ranking):")
print(rank_df)

# --- 5. 可视化 (横向柱状图) ---
plt.figure(figsize=(10, 6))

# 画图：颜色越红越强，越蓝越弱
sns.barplot(x='综合得分', y='板块', data=rank_df, palette='RdBu_r')

plt.title('谁是版本之子？(基于5日+20日涨幅)', fontsize=15)
plt.xlabel('动量得分 (分越高越强)')
plt.grid(True, axis='x', alpha=0.3)
plt.axvline(0, color='black', linestyle='-') # 0分界线

plt.show()

# --- 6. 给出换车建议 ---
champion = rank_df.iloc[0]['板块']
loser = rank_df.iloc[-1]['板块']

print("-" * 30)
print(f"👑 版本之子: 【{champion}】 (进攻首选)")
print(f"💩 版本陷阱: 【{loser}】 (如果不幸持有，考虑止损)")
print("-" * 30)