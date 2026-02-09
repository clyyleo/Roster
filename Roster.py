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
    /* 优化输入框焦点视觉 */
    input { caret-color: red; } 
    </style>
""", unsafe_allow_html=True)

# --- 2. 核心数据连接与时间逻辑 ---
def get_data():
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        doc_id = url.split('/d/')[1].split('/')[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid=0"
        return pd.read_csv(csv_url), "success"
    except Exception as e:
        return pd.DataFrame(), str(e)

TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]

def finalize_time_input(t):
    """智能补全：输8变08:00"""
    t = str(t).strip()
    if t.isdigit():
        return f"{int(t):02d}:00"
    return t

def calc_wage_details(s, e, rate):
    if not s or not e or s == "" or e == "": return 0.0, 0.0
    try:
        s, e = finalize_time_input(s), finalize_time_input(e)
        h1, m1 = map(float, s.split(':'))
        h2, m2 = map(float, e.split(':'))
        dur = (h2 + m2/60) - (h1 + m1/60)
        if dur < 0: dur += 24
        # 利益最大化：超过5小时扣0.5h休息
        actual = dur - 0.5 if duration > 5 else dur
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 3. 初始化与登录 ---
staff_df, status = get_data()
if "role" not in st.session_state: st.session_state.role = None
if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 5, 1])
    with col_mid:
        st.markdown("<h2 style='text-align: center;'>Roster 财务系统</h2>", unsafe_allow_html=True)
        pwd = st.text_input("🔑 密码", type="password", placeholder="请输入密码...")
        if st.button("进入系统", use_container_width=True):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            st.rerun()
    st.stop()

if 'main_df' not in st.session_state:
    # 自动加载 15 位员工排班模板
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    df = pd.DataFrame({"员工": list(staff_df["姓名"])})
    for d in days: df[f"{d}_起"], df[f"{d}_止"] = "", ""
    st.session_state.main_df = df

# --- 4. 主界面 ---
selected_monday = st.date_input("📅 选择周一日期", datetime.now() - timedelta(days=datetime.now().weekday()))
week_key = selected_monday.strftime("%Y-%m-%d")

# A. 快速排班助手 (保留功能)
with st.expander("👤 快速录入/常用班次", expanded=False):
    c1, c2, c3 = st.columns(3)
    with c1: sn = st.selectbox("员工", list(staff_df["姓名"]))
    with c2: days_sel = st.multiselect("日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
    with c3: shift_base = st.selectbox("模板", ["自定义", "8-2", "10-6", "8-6", "2-6", "10-2"])
    
    base_val = {"8-2":("08:00","14:00"), "10-6":("10:00","18:00"), "8-6":("08:00","18:00"), "2-6":("14:00","18:00"), "10-2":("10:00","14:00")}.get(shift_base, ("",""))
    cc1, cc2 = st.columns(2)
    new_s = cc1.text_input("开始 (输数字即可)", value=base_val[0])
    new_e = cc2.text_input("结束", value=base_val[1])
    if st.button("✨ 导入表格", use_container_width=True):
        for d in days_sel:
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_起"] = finalize_time_input(new_s)
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_止"] = finalize_time_input(new_e)
        st.rerun()

# B. 核心排班表 (支持模糊搜索)
column_config = {}
for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
    column_config[f"{d}_起"] = st.column_config.SelectboxColumn(f"{d}|起", options=TIME_OPTIONS)
    column_config[f"{d}_止"] = st.column_config.SelectboxColumn(f"{d}|止", options=TIME_OPTIONS)

t_h = (len(st.session_state.main_df) + 1) * 35 + 60
edited_df = st.data_editor(st.session_state.main_df, column_config=column_config, use_container_width=True, hide_index=True, height=t_h)
st.session_state.main_df = edited_df

# --- 5. 财务分析 (老板专属) ---
if st.session_state.role == "owner":
    st.divider()
    st.header("📊 营业额与成本监控")
    
    # 修改点：将营业额输入框设为 None，去除 0.0 干扰
    st.write("点击下方填写每日营业额 ($):")
    days_list = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    sc = st.columns(7)
    sales = {}
    for i, d in enumerate(days_list):
        # 使用 None 作为初始值，用户输入时不需要删除 0.0
        val = sc[i].number_input(d, value=None, step=100.0, key=f"sale_{d}", placeholder="输入")
        sales[d] = val if val is not None else 0.0

    # 汇总计算
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    daily_h, daily_w = {d:0.0 for d in days_list}, {d:0.0 for d in days_list}
    t_cash, t_eft = 0.0, 0.0

    for _, row in edited_df.iterrows():
        name = row["员工"]
        rate = STAFF_DB.get(name, {}).get("时薪", 0)
        p_type = str(STAFF_DB.get(name, {}).get("类型", "cash")).lower()
        person_w = 0.0
        for d in days_list:
            h, w = calc_wage_details(row[f"{d}_起"], row[f"{d}_止"], rate)
            daily_h[d] += h
            daily_w[d] += w
            person_w += w
        if p_type == "cash": t_cash += person_w
        else: t_eft += person_w

    # 显示看板
    total_sales = sum(sales.values())
    total_wages = sum(daily_w.values())
    total_hours = sum(daily_h.values())

    analysis_df = pd.DataFrame({
        "项目": ["总工时(h)", "总工资($)", "工占比(%)"],
        **{d: [daily_h[d], round(daily_w[d], 2), f"{round(daily_w[d]/sales[d]*100, 1) if sales[d]>0 else 0}%"] for d in days_list}
    })
    st.table(analysis_df)
    
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("每周总工时", f"{total_hours} h")
    m2.metric("每周总工资支出", f"${round(total_wages, 2)}")
    m3.metric("周平均工占比", f"{round(total_wages/total_sales*100, 1) if total_sales>0 else 0}%")
    m4.metric("现金准备 (Cash)", f"${round(t_cash, 2)}")
