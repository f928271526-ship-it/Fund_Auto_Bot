# realtime.py
# --- 实时侦察兵 v2.0 (极速直连版) ---

import requests
import json
import re
import time
import config 

def get_realtime_estimate(code):
    """
    直接访问天天基金的 JS 接口，获取实时估值
    """
    # 这是一个神奇的接口，返回的是 JSONP 格式
    url = f"http://fundgz.1234567.com.cn/js/{code}.js"
    
    try:
        # 发送请求
        resp = requests.get(url, timeout=3)
        
        # 返回的数据长这样：jsonpgz({"fundcode":"012363","gszzl":"2.57", ...});
        # 我们要用正则表达式把它提取出来
        text = resp.text
        
        # 提取括号里的 JSON 内容
        match = re.search(r'jsonpgz\((.*?)\);', text)
        
        if match:
            data_str = match.group(1)
            data = json.loads(data_str)
            
            # gszzl = 估算增长率 (Gu Suan Zeng Zhang Lv)
            growth = float(data['gszzl']) 
            # gztime = 估值时间
            update_time = data['gztime']
            
            return growth, update_time
        else:
            return None, None
            
    except Exception as e:
        print(f"❌ {code} 抓取失败: {e}")
        return None, None

def send_wechat(title, content):
    """发送微信 (复用 main.py 的逻辑)"""
    if not config.PUSH_CONFIG['token']:
        print("⚠️ 没填 Token，跳过微信发送")
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
    print(f"⏰ 14:50 实时监控启动... (当前时间: {time.strftime('%H:%M:%S')})")
    msg_lines = []
    
    # 遍历你在 config.py 里配置的所有基金
    for code, name in config.MY_FUNDS.items():
        growth, update_time = get_realtime_estimate(code)
        
        if growth is None:
            print(f"❌ {name}: 无数据 (可能代码填错了？)")
            continue
            
        # --- 战术板 (根据跌幅生成建议) ---
        action = "⚪ 观望"
        color = "black" # 默认颜色
        
        # 证券策略
        if "证券" in name:
            if growth < -1.2:
                action = "🟢 【黄金坑！买入！】"
                color = "green"
            elif growth > 2.0:
                action = "🔴 【大涨！止盈观察】"
                color = "red"
        
        # 煤炭策略
       # 煤炭策略 (修改版)
        elif "煤炭" in name:
            if growth < -3.0:
                action = "⚪ 【超跌！别割肉】"
                color = "green"
            # --- 修改这里 ---
            elif growth > 0.1:  # 只要涨幅大于 0.1% (几乎是只要红了)
                action = "✂️ 【微红也是肉！减仓换车！】" 
                color = "red"
            # ---------------

        # 纳指策略
        elif "纳" in name:
             action = "🔵 【美股！长期持有】"

        # 打印到屏幕
        print(f"{name}: {growth}%  [{update_time}]")
        
        # 组装微信消息 (HTML格式)
        # style='color:...' 可以让微信里的字变色
        line = f"<b>{name}</b>: <span style='color:{color}'>{growth}%</span> ({action})"
        msg_lines.append(line)

    # 发送汇总
    if msg_lines:
        send_wechat("14:50 实时操作指令", "<br>".join(msg_lines))
        print("✅ 任务完成！")
    else:
        print("⚠️ 没有获取到任何数据，检查网络或代码。")

if __name__ == "__main__":
    job_1450()