# main.py
# --- 终极指挥官：调度所有模块，一键运行 ---

import time
import requests
import config
from data_engine import DataEngine
from analysis import FundAnalyzer

def send_wechat(title, content):
    """发送微信消息 (调用 PushPlus)"""
    url = 'http://www.pushplus.plus/send'
    data = {
        "token": config.PUSH_CONFIG['token'],
        "title": title,
        "content": content,
        "template": "html"
    }
    try:
        resp = requests.post(url, json=data)
        print(f"📨 微信推送状态: {resp.text}")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

def job():
    print("\n⏰ ========= 量化机器人启动 =========")
    
    # 1. 启动引擎：更新数据
    print("Step 1: 更新数据库...")
    engine = DataEngine()
    engine.run_all()
    
    # 2. 启动大脑：分析数据
    print("\nStep 2: 量化分析中...")
    brain = FundAnalyzer()
    report = brain.run_analysis()
    
    # 3. 发送报告
    print("\nStep 3: 推送微信...")
    # 把换行符 \n 变成 HTML 的 <br>，这样微信里才能换行
    wechat_content = report.replace('\n', '<br>')
    
    send_wechat(
        title="符清华的基金日报",
        content=wechat_content
    )
    
    print("✅ ========= 任务全部完成 =========")

if __name__ == "__main__":
    # 这里以后可以加定时任务，现在先手动跑一次
    job()