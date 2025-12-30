# 打造你的“彭博终端” (Streamlit Web App)
import streamlit as st
import pandas as pd
import akshare as ak
import plotly.graph_objects as go # 交互式画图库
from datetime import datetime
from sqlalchemy import create_engine
from config import DB_URL

# --- 1. 网页基础设置 ---
st.set_page_config(page_title='符清华的量化看板',layout='wide')
# 侧边栏 (Sidebar)
st.sidebar.title = ('🎛️ 基金指挥舱')
fund_code = st.sidebar.text_input('输入基金代码',value = '012363')
fund_name = st.sidebar.text_input('基金名称 (备注)',value='国泰证券')
days = st.sidebar.slider('查看最近多少天?',min_value = 30,max_value=365,value=120)
st.sidebar.markdown('---')
st.sidebar.subheader('🛠️ 策略实验室')
rsi_input=st.sidebar.slider('RSI 抄底阈值',10,50,37)
# --- 2. 核心函数: 获取数据 ---
# @st.cache_data 是个魔法：它会把数据存起来，下次不用重新抓，速度飞快
@st.cache_data
def get_data(code):
    engine = create_engine(DB_URL)
    
    # 1. 修改 SQL：表名改为 fund_nav_history，列名改为 nav_date, nav_value
    sql = f"""
    SELECT nav_date, nav_value 
    FROM fund_nav_history 
    WHERE fund_code = '{code}' 
    ORDER BY nav_date ASC
    """
    
    try:
        df = pd.read_sql(sql, engine)
        
        # 2. 修改适配层：把 nav_date/nav_value 映射回 净值日期/单位净值
        df.rename(columns={
            'nav_date': '净值日期', 
            'nav_value': '单位净值'
        }, inplace=True)
        
        # 3. 格式确保
        df['净值日期'] = pd.to_datetime(df['净值日期'])
        df['单位净值'] = pd.to_numeric(df['单位净值'])
        
        return df
        
    except Exception as e:
        st.error(f"数据库读取失败: {e}")
        return pd.DataFrame()
# --- 3. 核心函数: 计算指标 ---
def calculate_indicators(df,rsi_threshold=30):
    # 算 RSI
    change = df['单位净值'].diff()
    gain = change.clip(lower = 0)
    loss = change.clip(upper = 0).abs()
    avg_gain = gain.ewm(alpha = 1/14,adjust = False).mean()
    avg_loss = loss.ewm(alpha =1/14,adjust = False).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100/(1+rs))
    # 算 布林带
    df['MA20'] = df['单位净值'].rolling(20).mean()
    df['STD'] = df['单位净值'].rolling(20).std()
    df['UP'] = df['MA20'] + 2*df['STD']
    df['LOW'] = df['MA20'] - 2*df['STD']
    # 1. 市场基准收益 (pct_change 是 Pandas 计算涨跌幅的神器)
    df['market_ret'] = df['单位净值'].pct_change().fillna(0)
    # 2. 生成信号
    # 逻辑：如果 RSI 小于你拖动的阈值，就设为 1 (持有)，否则 0 (空仓)
    import numpy as np
    df['signal'] = np.where(df['RSI']<rsi_threshold,1,0)
    # 3. 计算策略收益 (核心技术点：Shift)
    df['strategy_ret'] = df['signal'].shift(1)*df['market_ret']
    # 4. 计算净值曲线 (从 1 开始的累乘)
    df['strategy_curve'] = (1+df['strategy_ret']).cumprod()
    df['market_curve'] = (1+df['market_ret']).cumprod()

    return df
# --- 4. 主界面逻辑 ---
st.title(f'📈 {fund_name} ({fund_code}) 实战分析')

# [修复1] 加上 try-except 捕获所有潜在错误
try:
    with st.spinner('正在从阿里云/本地数据库拉取数据...'):
        # 1. 获取并清洗数据
        raw_df = get_data(fund_code)
        
        # [修复2] 关键防御：如果数据库里没这个基金，直接报错并停止，别硬往下跑！
        if raw_df.empty:
            st.error(f"❌ 错误：数据库中找不到基金 {fund_code}！")
            st.info("💡 解决办法：请先运行 data_engine.py 把这个基金的数据抓取入库，再来刷新网页。")
            st.stop() # 强制停止后续代码执行

        # 2. 计算指标
        df = calculate_indicators(raw_df, rsi_input)
        
        # 3. 截取最近 N 天
        data = df.tail(days)
        
        # [修复3] 二次防御：确保截取后还有数据
        if data.empty:
             st.warning("⚠️ 数据不足，无法分析。")
             st.stop()

        last_day = data.iloc[-1]
        
        # --- 5. 展示关键指标 (KPI) ---
        # [修复4] 规范缩进：st.columns 必须对齐
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 计算涨跌值
            prev_price = data.iloc[-2]['单位净值'] if len(data) > 1 else last_day['单位净值']
            diff = last_day['单位净值'] - prev_price
            st.metric("最新净值", f"{last_day['单位净值']:.4f}", f"{diff:.4f}")
            
        with col2:
            rsi_val = last_day['RSI']
            if rsi_val < 30:
                st.metric("RSI 情绪值", f"{rsi_val:.2f}", "💎 黄金坑 (机会)", delta_color="inverse")
            elif rsi_val > 70:
                st.metric("RSI 情绪值", f"{rsi_val:.2f}", "🔥 严重过热 (止盈)", delta_color="normal")
            else:
                st.metric("RSI 情绪值", f"{rsi_val:.2f}", "😐 正常震荡", delta_color="off")
            
        with col3:
            # 距离下轨空间
            dist = (last_day['单位净值'] - last_day['LOW']) / last_day['LOW'] * 100
            st.metric('距离下轨', f'{dist:.2f}%', delta_color='off')

        # --- 6. 画交互式 K 线图 (Plotly) ---
        st.subheader('📊 战术走势图')
        fig = go.Figure()
        
        # 画线
        fig.add_trace(go.Scatter(x=data['净值日期'], y=data['单位净值'], mode='lines', name='净值', line=dict(color='black', width=2)))
        fig.add_trace(go.Scatter(x=data['净值日期'], y=data['UP'], mode='lines', name='压力线', line=dict(color='green', width=1)))
        fig.add_trace(go.Scatter(x=data['净值日期'], y=data['LOW'], mode='lines', name='支撑线', line=dict(color='red', width=1)))

        # 黄金坑标记
        buy_signals = data[data['RSI'] < 30]
        if not buy_signals.empty:
            fig.add_trace(go.Scatter(
                x=buy_signals['净值日期'], 
                y=buy_signals['LOW'],
                mode='markers',
                name='黄金坑买点',
                marker=dict(symbol='triangle-up', size=12, color='#00CC00')
            ))

        fig.update_layout(height=500, xaxis_title='日期', yaxis_title='净值', hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)

        # --- 资金曲线 ---
        st.markdown('### 🆚 收益率大比拼')
        start_total = (df['strategy_curve'].iloc[-1] - 1) * 100
        market_total = (df['market_curve'].iloc[-1] - 1) * 100
        
        c1, c2 = st.columns(2)
        c1.metric('傻傻拿着(基准)', f'{market_total:.2f}%')
        c2.metric(f'RSI<{rsi_input}波段策略', f'{start_total:.2f}%', delta=f'{start_total - market_total:.2f}%')
        
        fig_bt = go.Figure()
        fig_bt.add_trace(go.Scatter(x=df['净值日期'], y=df['market_curve'], name='躺平不动', line=dict(dash='dash', color='gray')))
        fig_bt.add_trace(go.Scatter(x=df['净值日期'], y=df['strategy_curve'], name='波段操作', line=dict(color='red', width=2)))
        st.plotly_chart(fig_bt, use_container_width=True)

        # --- 7. AI 建议 ---
        st.subheader('🤖 符清华 AI 助理建议')
        if rsi_val < 30:
            st.error(f'💎 触发【黄金坑】信号! RSI={rsi_val:.2f} 建议: 考虑分批建仓！')
        elif dist < 0:
            st.warning(f'🔥 触发【破轨】信号！跌破下轨 {dist:.2f}%。建议：关注反弹机会。')
        elif rsi_val > 70:
            st.error(f'🚨 触发【过热】信号! RSI = {rsi_val:.2f}。建议：止盈/减仓！')
        else:
            st.info('☁️ 目前处于垃圾时间 (震荡区)。建议：多看少动，喝杯茶。')

except Exception as e:
    # 这里会捕获 SQL 连接失败等系统级错误
    st.error(f'系统崩溃了：{e}')
    st.markdown("Please check your `config.py` or Database connection.") 

          
        
                   
        