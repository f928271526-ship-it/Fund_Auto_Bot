# realtime.py
# --- 实时侦察兵 v4.0 (云端脱机版) ---
# 修改日志：
# 1. 移除数据库依赖，改用 Akshare 现场抓取历史数据，解决 GitHub Action 连不上库的问题。
# 2. 增加 CPO/5G 策略通道。

import requests
import json
import re
import pandas as pd
import akshare as ak  # 必须确保 requirements.txt 里有 akshare
import config 

def get_realtime_estimate(code):
    """
    获取实时估值 (爬取天天基金估值接口)
    """
    url = f"http://fundgz.1234567.com.cn/js/{code}.js"
    try:
        resp = requests.get(url, timeout=3)
        match = re.search(r'jsonpgz\((.*?)\);', resp.text)
        if match:
            data = json.loads(match.group(1))
            return float(data['gszzl']), data['gztime']
        return None, None
    except Exception as e:
        print(f"❌ {code} 实时估值抓取失败: {e}")
        return None, None

def calculate_realtime_rsi_online(code, current_growth):
    """
    🔥 核心升级：不连数据库，直接从互联网抓历史净值 + 实时涨跌 -> 算出 RSI
    """
    try:
        # 1. 临时抓取最近的历史净值 (利用 Akshare)
        # indicator="单位净值走势" 能抓到该基金所有历史数据
        df_hist = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        
        # 2. 清洗数据
        df_hist = df_hist[['净值日期', '单位净值']]
        df_hist.columns = ['date', 'value']
        df_hist['value'] = pd.to_numeric(df_hist['value'])
        
        # 3. 截取最近 30 天 (减少计算量)
        df = df_hist.tail(30).copy()
        
        # 4. 构造“今天”的数据 (T日)
        # 逻辑：今天的估算净值 = 昨天的净值 * (1 + 实时涨跌幅%)
        last_nav = df['value'].iloc[-1]
        current_nav = float(last_nav) * (1 + current_growth / 100)
        
        # 5. 拼接到最后
        new_row = pd.DataFrame({'date': ['Today'], 'value': [current_nav]})
        df = pd.concat([df, new_row], ignore_index=True)
        
        # 6. 计算 RSI (标准的 pandas 算法)
        change = df['value'].diff()
        gain = change.clip(lower=0)
        loss = change.clip(upper=0).abs()
        
        avg_gain = gain.ewm(com=13, adjust=False).mean() # com=13 等同于 alpha=1/14
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        
        # 防除零错误
        if avg_loss.iloc[-1] == 0:
            return 100
            
        rs = avg_gain.iloc[-1] / avg_loss.iloc[-1]
        rsi = 100 - (100 / (1 + rs))
        
        return rsi

    except Exception as e:
        print(f"⚠️ {code} RSI 计算出错 (Akshare): {e}")
        return None

def send_wechat(title, content):
    """发送微信 (PushPlus)"""
    if not config.PUSH_CONFIG['token']: 
        print("⚠️ 未配置 Push Token，跳过发送")
        return
        
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
    print(f"⏰ 14:50 实时监控启动 (Cloud Mode)...")
    msg_lines = []
    
    # 遍历配置里的基金列表
    for code, name in config.MY_FUNDS.items():
        print(f"正在侦察: {name} ({code})...")
        growth, update_time = get_realtime_estimate(code)
        
        if growth is None:
            print(f"  -> 无法获取估值，跳过")
            continue
            
        # 算 RSI (云端版)
        real_rsi = calculate_realtime_rsi_online(code, growth)
        
        # --- 决策逻辑 ---
        action = "⚪ 观望"
        color = "black"
        rsi_msg = f"{real_rsi:.1f}" if real_rsi else "N/A"
        
        # =========== 🔥 策略分流 (Strategy Router) ===========
        
        # 1. 国泰证券 / 券商
        if "证券" in name:
            target_rsi = 37
            if real_rsi and real_rsi < target_rsi:
                action = f"🟢 【黄金坑! RSI<{target_rsi}】"
                color = "#00CC00" # 亮绿
            elif real_rsi and real_rsi > 75: 
                action = "🔴 【过热! 建议止盈】"
                color = "red"
            elif growth < -1.2:
                action = "🟢 【大跌博反弹】"
                color = "green"

        # 2. 纳指 / 美股 (防守)
        elif "纳" in name or "标普" in name:
            if real_rsi and real_rsi < 30: 
                action = "💎 【罕见机会! 加仓!】" 
                color = "purple"
            else:
                action = "🔵 【躺平持有】" 
                color = "gray"
        
        # 3. CPO / 5G / 科技 (高波动新宠)
        elif "5G" in name or "CPO" in name or "科技" in name:
             if real_rsi and real_rsi < 35: 
                 action = "🟢 【科技超跌】"
                 color = "green"
             elif real_rsi and real_rsi > 70:
                 action = "🔥 【高危预警! 减仓】"
                 color = "#FF4500" # 橙红
             else:
                 action = "😐 【震荡观察】"
                 
        # 4. 其他 (默认)
        else:
             if real_rsi and real_rsi < 30:
                 action = "🟢 【RSI低位】"
                 color = "green"
        
        # =======================================================

        print(f"  -> 结果: {growth}% (RSI:{rsi_msg}) -> {action}")
        
        # 构造 HTML 消息行
        # 格式： 基金名: +1.5% (RSI: 65)
        #       [操作建议]
        line = f"<b>{name}</b> ({code}): <span style='color:{'red' if growth>0 else 'green'}'>{growth}%</span> (RSI:{rsi_msg}) <br>{action}"
        msg_lines.append(line)

    if msg_lines:
        send_wechat("14:50 盘中信号", "<br><br>".join(msg_lines))
        print("✅ 所有任务完成！")

if __name__ == "__main__":
    job_1450()