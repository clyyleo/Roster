import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 纯净外观与深度清理 (彻底抹除 Manage App)
st.set_page_config(page_title="Roster Pro", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
    <style>
    header, footer, #MainMenu {visibility: hidden !important;}
    div[data-testid="stStatusWidget"], button[title="Manage app"], 
    iframe[title="manage-app-button"], .stAppDeployButton, [data-testid="stToolbar"] {
        display: none !important; visibility: hidden !important;
    }
    .block-container { padding-top: 1rem !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 核心数据连接与算法 ---
def get_data():
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        doc_id = url.split('/d/')[1].split('/')[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid=0"
        return pd.read_csv(csv_url), "success"
    except Exception as e:
        return pd.DataFrame(), str(e)

def calc_wage_details(s, e, rate):
    if not s or not e or s == "" or e == "": return 0.0, 0.0
    try:
        h1, m1 = map(float, str(s).split(':'))
        h2, m2 = map(float, str(e).split(':'))
        dur = (h2 + m2/60) - (h1 + m1/60)
        if dur < 0: dur += 24
        actual = dur - 0.5 if dur > 5 else dur # 利益最大化算法
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 3. 初始模板加载 ---
def load_all_template(staff_list):
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    df = pd.DataFrame({"员工": staff_list})
    for d in days: df[f"{d}_起"], df[f"{d}_止"] = "", ""
    return df

# --- 4. 权限与登录 ---
staff_df, status = get_data()
if "role" not in st.session_state: st.session_state.role = None
if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 5, 1])
    with col_mid:
        st.markdown("<h2 style='text-align: center;'>Roster 财务系统</h2>", unsafe_allow_html=True)
        pwd = st.text_input("🔑 密码", type="password", placeholder="请输入密码...")
        if st.button("登录进入", use_container_width=True):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            st.rerun()
    st.stop()

# --- 5. 主界面逻辑 ---
# A. 日期与周次处理
today = datetime.now()
monday_this_week = today - timedelta(days=today.weekday())
selected_monday = st.date_input("📅 选择排班周 (周一)", monday_this_week)
# 确保选中的永远是那个周的周一
actual_monday = selected_monday - timedelta(days=selected_monday.weekday())
week_key = actual_monday.strftime("%Y-%m-%d")

st.title(f"🚀 {actual_monday.strftime('%m/%d')} 班次排定 ({'老板' if st.session_state.role=='owner' else '店长'})")

# 数据初始化
if 'main_df' not in st.session_state:
    st.session_state.main_df = load_all_template(list(staff_df["姓名"]))
if 'cloud_storage' not in st.session_state:
    st.session_state.cloud_storage = {} # 模拟按日期存储的云端数据库

# B. 快速录入助手 (保持不变)
with st.expander("👤 快速批量排班导入", expanded=False):
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1: sn = st.selectbox("选择员工", list(staff_df["姓名"]))
    with c2: days_sel = st.multiselect("选择日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
    with c3: shift = st.selectbox("选择班次", ["8-2", "10-6", "8-6", "2-6", "10-3"])
    preset = {"8-2":("08:00","14:00"), "10-6":("10:00","18:00"), "8-6":("08:00","18:00"), "2-6":("14:00","18:00"), "10-3":("10:00","15:00")}.get(shift)
    if st.button("填入当前周表格"):
        for d in days_sel:
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_起"] = preset[0]
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_止"] = preset[1]
        st.rerun()

# C. 核心排班表 (自适应全员高度)
t_h = (len(st.session_state.main_df) + 1) * 35 + 65
edited_df = st.data_editor(st.session_state.main_df, use_container_width=True, hide_index=True, height=t_h)
st.session_state.main_df = edited_df

# D. 云端同步 (核心逻辑升级：带日期索引)
col_s1, col_s2 = st.columns(2)
if col_s1.button(f"💾 同步 {week_key} 数据至云端", use_container_width=True):
    st.session_state.cloud_storage[week_key] = edited_df.copy()
    st.success(f"已成功同步 {week_key} 周次数据！")

if col_s2.button(f"📥 下载 {week_key} 云端历史记录", use_container_width=True):
    if week_key in st.session_state.cloud_storage:
        st.session_state.main_df = st.session_state.cloud_storage[week_key].copy()
        st.rerun()
    else:
        st.warning(f"云端暂无 {week_key} 的历史记录")

# --- 6. 财务分析 (老板模式) ---
if st.session_state.role == "owner":
    st.divider()
    st.header(f"📊 财务分析 ({week_key})")
    
    # 营业额录入
    days_list = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    st.write("输入每日营业额 ($):")
    sc = st.columns(7)
    sales = {}
    for i, d in enumerate(days_list):
        sales[d] = sc[i].number_input(d, value=0.0, step=100.0, key=f"sale_{d}_{week_key}")

    # 计算
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    daily_w = {d: 0.0 for d in days_list}
    daily_h = {d: 0.0 for d in days_list}
    total_cash, total_eft = 0.0, 0.0

    for _, row in edited_df.iterrows():
        name = row["员工"]
        rate = STAFF_DB.get(name, {}).get("时薪", 0)
        p_type = str(STAFF_DB.get(name, {}).get("类型", "cash")).lower()
        row_w = 0.0
        for d in days_list:
            h, w = calc_wage_details(row[f"{d}_起"], row[f"{d}_止"], rate)
            daily_h[d] += h
            daily_w[d] += w
            row_w += w
        if p_type == "cash": total_cash += row_w
        else: total_eft += row_w

    # 显示看板
    total_sales = sum(sales.values())
    total_wages = sum(daily_w.values())
    
    analysis_df = pd.DataFrame({
        "指标": ["总工时 (h)", "总工资 ($)", "营业额 ($)", "工占比 (%)"],
        **{d: [daily_h[d], round(daily_w[d], 2), sales[d], 
               f"{round(daily_w[d]/sales[d]*100, 1)}%" if sales[d]>0 else "0%"] 
           for d in days_list}
    })
    st.table(analysis_df)
    
    avg_labor = f"{round(total_wages/total_sales*100, 1)}%" if total_sales > 0 else "0%"
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("周总营业额", f"${round(total_sales, 2)}")
    m2.metric("周总工资支出", f"${round(total_wages, 2)}")
    m3.metric("本周平均工占比", avg_labor)
    m4.metric("现金准备 (Cash)", f"${round(total_cash, 2)}")

if st.sidebar.button("退出系统"):
    st.session_state.role = None
    st.rerun()
