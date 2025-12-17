import akshare as ak
import pandas as pd
import matplotlib.pyplot as plt


plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 1. 选手入场
competitors = {
    '013275': '💩 富国煤炭 (你的)',
    '009180': '🛒 嘉实消费 (挑战者)',
    '018419': '🔋 广发碳中和 (挑战者)'
}

print("🥊 正在进行 30天 短期爆发力 PK...")
data = pd.DataFrame()

# 2. 抓取最近 30 天数据
for code, name in competitors.items():
    df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
    df['date'] = pd.to_datetime(df['净值日期'])
    df['price'] = pd.to_numeric(df['单位净值'])
    df = df.sort_values('date').set_index('date')
    
    # 归一化 (让大家都在30天前从 1.0 起跑)
    recent = df['price'].tail(30)
    data[name] = recent / recent.iloc[0]

# 3. 画图定胜负
plt.figure(figsize=(10, 6))
for col in data.columns:
    width = 3 if '煤炭' in col else 1.5 # 重点看煤炭
    style = '--' if '煤炭' in col else '-'
    plt.plot(data.index, data[col], label=col, linewidth=width, linestyle=style)

plt.axhline(1.0, color='black', alpha=0.3)
plt.title('换车决策图：谁比煤炭强？(近30天走势)', fontsize=15)
plt.legend()
plt.grid(True)
plt.show()

# 4. 计算跑赢了多少
last_day = data.iloc[-1]
coal_perf = last_day['💩 富国煤炭 (你的)']
print(f"当前煤炭净值归一: {coal_perf:.4f}")

for name, perf in last_day.items():
    if name == '💩 富国煤炭 (你的)': continue
    diff = (perf - coal_perf) * 100
    if diff > 0:
        print(f"✅ 【{name}】 跑赢煤炭 {diff:.2f}% -> 值得换车！")
    else:
        print(f"❌ 【{name}】 跑输煤炭 {abs(diff):.2f}% -> 别买，也是垃圾。")