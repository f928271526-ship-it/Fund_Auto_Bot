# 打造你的“彭博终端” (Streamlit Web App)
import streamlit as st
import pandas as pd
import akshare as ak
import plotly.graph_objects as go # 交互式画图库
from datetime import datetime

# --- 1. 网页基础设置 ---
st.set_page_config(page_title='符清华的量化看板',layout='wide')
# 侧边栏 (Sidebar)
st.sidebar.title = ('🎛️ 基金指挥舱')
fund_code = st.sidebar.text_input('输入基金代码',value = '012363')
fund_name = st.sidebar.text_input('基金名称 (备注)',value='国泰证券')
days = st.sidebar.slider('查看最近多少天?',min_value = 30,max_value=365,value=120)
# --- 2. 核心函数: 获取数据 ---
# @st.cache_data 是个魔法：它会把数据存起来，下次不用重新抓，速度飞快
@st.cache_data
def get_data(code):
    df = ak.fund_open_fund_info_em(symbol=code,indicator='单位净值走势')
    df['净值日期'] = pd.to_datetime(df['净值日期'])
    df['单位净值'] = pd.to_numeric(df['单位净值'])
    df.sort_values('净值日期',inplace=True)
    return df
# --- 3. 核心函数: 计算指标 ---
def calculate_indicators(df):
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

    return df
# --- 4. 主界面逻辑 ---
st.title(f'📈{fund_name}({fund_code})实战分析')

try:
    with st.spinner('正在从阿里云/互联网拉取数据...'):
         # 获取并清洗数据
         raw_df = get_data (fund_code)
         df = calculate_indicators(raw_df)
         # 截取最近 N 天
         data = df.tail(days)
         last_day = data.iloc[-1]
         # --- 5. 展示关键指标 (KPI) ---
         col1,col2,col3 = st.columns(3)
    with col1 :
             st.metric("最新净值", f"{last_day['单位净值']:.4f}", f"{last_day['单位净值'] - data.iloc[-2]['单位净值']:.4f}")
    with col2:
         rsi_val = last_day['RSI']
         # 根据 RSI 变颜色
         rsi_color = 'normal'
         if rsi_val <30 :rsi_color = 'inverse'
         st.metric("RSI 情绪值", f"{rsi_val:.2f}", delta="低于30是机会" if rsi_val < 30 else '正常')
    with col3 :
         # 距离下轨空间
         dist = (last_day['单位净值'] - last_day['LOW']) / last_day['LOW']*100 
         st.metric('距离下轨',f'{dist:.2f}%',delta_color='off')
     # --- 6. 画交互式 K 线图 (Plotly) ---
    st.subheader('📊 战术走势图')
    fig = go.Figure()
    # 画净值线
    fig.add_trace(go.Scatter(x=data['净值日期'],y = data['单位净值'],mode ='lines',name = '净值',line = dict(color = 'black',width = 2)))
    # 画布林带
    fig.add_trace(go.Scatter(x=data['净值日期'],y=data['UP'],mode = 'lines',name = '压力线',line = dict(color = 'green',width = 2)))
    fig.add_trace(go.Scatter(x=data['净值日期'],y=data['LOW'],mode = 'lines',name = '支撑线',line = dict(color = 'red',width = 2)))
    # 更新布局
    fig.update_layout(height = 500,xaxis_title = '日期',yaxis_title = '净值',hovermode = 'x unified')
    # 展示图表
    st.plotly_chart(fig,use_container_width=True)
    # --- 7. 给出 AI 建议 ---
    st.subheader('🤖 符清华 AI 助理建议')
    if rsi_val <30:
         st.error(f'💎 触发【黄金坑】信号! RSI={rsi_val:.2f}建议:买入!')
    elif dist<0:
         st.warning(f'🔥 触发【破轨】信号！跌破下轨 {dist:.2f}%。建议：分批抄底。')
    elif rsi_val > 70:
         st.error(f'🚨 触发【过热】信号! RSI = {rsi_val:.2f}。建议：止盈')
    else:
         st.info('☁️ 目前处于垃圾时间 (震荡区)。建议：多看少动，喝杯茶。')

except Exception as e:
     st.error(f'出错了：{e}。请检查代码是否正确。')            
        
                   
        