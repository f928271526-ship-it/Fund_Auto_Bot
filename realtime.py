# realtime.py
# --- 实时侦察兵 v3.0 (RSI 智能版) ---

import requests
import json
import re
import time
import pandas as pd
from sqlalchemy import create_engine
import config 
# 引入数据库连接配置 (确保 config.py 里有这个变量)
from config import DB_URL 

def get_realtime_estimate(code):
    """获取实时估值 (和原来一样)"""
    url = f"http://fundgz.1234567.com.cn/js/{code}.js"
    try:
        resp = requests.get(url, timeout=3)
        match = re.search(r'jsonpgz\((.*?)\);', resp.text)
        if match:
            data = json.loads(match.group(1))
            return float(data['gszzl']), data['gztime']
        return None, None
    except Exception as e:
        print(f"❌ {code} 网络抓取失败: {e}")
        return None, None

def calculate_realtime_rsi(code, current_growth):
    """
    🔥 核心升级：结合历史数据 + 实时涨跌，算出现在的 RSI
    """
    try:
        # 1. 连数据库取最近 30 条数据
        engine = create_engine(DB_URL)
        # 注意：这里要用 nav_date 排序
        sql = f"SELECT nav_value FROM fund_nav_history WHERE fund_code='{code}' ORDER BY nav_date ASC LIMIT 30"
        df = pd.read_sql(sql, engine)
        
        if df.empty:
            return None # 没历史数据，算不了

        # 2. 构造“今天”的数据
        last_nav = df['nav_value'].iloc[-1]
        # 今天的估算净值 = 昨天的净值 * (1 + 涨跌幅%)
        current_nav = float(last_nav) * (1 + current_growth / 100)
        
        # 3. 把今天拼接到历史数据后面
        # 兼容性写法：用 DataFrame 构造新行
        new_row = pd.DataFrame({'nav_value': [current_nav]})
        df = pd.concat([df, new_row], ignore_index=True)
        
        # 4. 计算 RSI (和 analysis.py 的逻辑一模一样)
        change = df['nav_value'].diff()
        gain = change.clip(lower=0)
        loss = change.clip(upper=0).abs()
        
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        
        if avg_loss.iloc[-1] == 0:
            return 100
            
        rs = avg_gain.iloc[-1] / avg_loss.iloc[-1]
        rsi = 100 - (100 / (1 + rs))
        
        return rsi

    except Exception as e:
        print(f"⚠️ {code} RSI 计算出错: {e}")
        return None

def send_wechat(title, content):
    """发送微信"""
    if not config.PUSH_CONFIG['token']: return
    url = 'http://www.pushplus.plus/send'
    data = {
        "token": config.PUSH_CONFIG['token'],
        "title": title,
        "content": content,
        "template": "html"
    }
    try:
        requests.post(url, json=data)
        print("📨 微信推送已发出")
    except Exception as e:
        print(f"❌ 推送报错: {e}")

def job_1450():
    print(f"⏰ 14:50 实时监控启动...")
    msg_lines = []
    
    for code, name in config.MY_FUNDS.items():
        growth, update_time = get_realtime_estimate(code)
        
        if growth is None:
            continue
            
        # 算 RSI
        real_rsi = calculate_realtime_rsi(code, growth)
        
        # 默认状态
        action = "⚪ 观望"
        color = "black"
        rsi_msg = f"{real_rsi:.1f}" if real_rsi else "N/A"
        
        # =========== 🔥 核心：策略分流 (Strategy Router) ===========
        
        # 1. 国泰证券专用通道 (激进波段)
        if "证券" in name:
            target_rsi = 37  # 你的回测结论
            
            if real_rsi and real_rsi < target_rsi:
                action = f"🟢 【黄金坑! RSI<{target_rsi}】"
                color = "#00CC00" # 亮绿
            elif real_rsi and real_rsi > 75: # 证券波动大，卖点可以高一点
                action = "🔴 【过热! 止盈】"
                color = "red"
            elif growth < -1.5:
                action = "🟢 【大跌补仓(RSI盲补)】"
                color = "green"

        # 2. 纳指专用通道 (防守躺平)
        elif "纳" in name:
            # 纳指不看 RSI<37，只看极度恐慌 (比如 RSI<20 才是真崩盘) 或者无脑定投
            if real_rsi and real_rsi < 25: 
                action = "💎 【史诗级机会! 加仓!】" # 纳指很难跌到这，跌到就是送钱
                color = "purple"
            else:
                action = "🔵 【躺平持有】" # 平时不管怎么跌都不卖
                color = "gray"
        
        # 3. 煤炭/其他通道
        elif "煤" in name:
             if real_rsi and real_rsi < 30: # 煤炭可能还是适合 30
                 action = "🟢 【煤炭超跌】"
                 color = "green"
        
        # =======================================================

        print(f"{name}: {growth}% (RSI:{rsi_msg}) -> {action}")
        
        line = f"<b>{name}</b>: <span style='color:{color}'>{growth}%</span> (RSI:{rsi_msg}) <br>{action}"
        msg_lines.append(line)

    if msg_lines:
        send_wechat("14:50 盘中指令", "<br><br>".join(msg_lines))
        print("✅ 任务完成！")

if __name__ == "__main__":
    job_1450()