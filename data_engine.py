# data_engine.py
# --- 数据引擎：负责 ETL (抓取-清洗-入库) ---

import akshare as ak
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import time

# 导入你的配置文件 (这就是为什么要分开写 config.py)
import config 

class DataEngine:
    def __init__(self):
        """初始化：建立数据库连接"""
        print("🔌 正在连接阿里云数据库...")
        
        # --- 🔥【新增】优先读取环境变量 (针对 GitHub Actions) ---
        import os
        env_pass = os.environ.get('DB_PASSWORD')
        env_host = os.environ.get('DB_HOST')
        
        if env_pass and env_host:
            # 如果在云端，直接用环境变量，不用 config
            user = 'root'
            password = env_pass
            host = env_host
            port = 3306
            database = 'fund_db'
        else:
            # 如果在本地，才用 config
            db_cfg = config.DB_CONFIG
            user = db_cfg['user']
            password = db_cfg['password']
            host = db_cfg['host']
            port = db_cfg['port']
            database = db_cfg['database']
            
        # 处理密码特殊字符
        safe_pass = quote_plus(password)
        self.conn_str = f"mysql+pymysql://{user}:{safe_pass}@{host}:{port}/{database}"
        self.engine = create_engine(self.conn_str)
        # ...

    def _init_table(self):
        """内部方法：确保表结构存在"""
        sql = text("""
        CREATE TABLE IF NOT EXISTS fund_nav_history (
            fund_code VARCHAR(10),
            fund_name VARCHAR(50),
            nav_date DATE,
            nav_value DECIMAL(10, 4),
            daily_growth DECIMAL(10, 2)
        );
        """)
        with self.engine.connect() as conn:
            conn.execute(sql)

    def update_single_fund(self, code, name):
        """核心逻辑：更新单只基金的数据"""
        print(f"🔄 [ETL] 正在处理: {name} ({code})...")
        
        try:
            # 1. Extract (抓取)
            df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
            
            # 2. Transform (清洗)
            # 改名
            df = df.rename(columns={'净值日期': 'nav_date', '单位净值': 'nav_value'})
            # 格式转换
            df['nav_date'] = pd.to_datetime(df['nav_date'])
            df['nav_value'] = pd.to_numeric(df['nav_value'])
            df = df.sort_values(by='nav_date', ascending=True)
            # 自己算涨跌幅 (更稳)
            df['daily_growth'] = df['nav_value'].pct_change() * 100
            df['daily_growth'] = df['daily_growth'].fillna(0)
            # 加上身份信息
            df['fund_code'] = code
            df['fund_name'] = name
            # 过滤字段
            df = df[['fund_code', 'fund_name', 'nav_date', 'nav_value', 'daily_growth']]
            
            # 3. Load (入库 - 先删后存)
            with self.engine.connect() as conn:
                # 删旧的
                del_sql = text("DELETE FROM fund_nav_history WHERE fund_code = :code")
                conn.execute(del_sql, parameters={"code": code})
                conn.commit()
                
                # 存新的
                df.to_sql('fund_nav_history', self.engine, if_exists='append', index=False)
            
            print(f"✅ {name} 更新成功！(最新日期: {df['nav_date'].iloc[-1].date()})")
            return True

        except Exception as e:
            print(f"❌ {name} 更新失败: {e}")
            return False

    def run_all(self):
        """指挥官：批量更新所有基金"""
        print("🚀 === 全量更新任务开始 ===")
        funds = config.MY_FUNDS # 从配置里读取清单
        
        for code, name in funds.items():
            self.update_single_fund(code, name)
            # 稍微歇一下，防止请求太快被封IP
            time.sleep(1)
            
        print("🏁 === 全量更新任务结束 ===")

# --- 测试代码 (只有直接运行这个文件时才会执行) ---
if __name__ == "__main__":
    engine = DataEngine()
    engine.run_all()