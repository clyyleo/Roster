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
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 数据连接与核心算法 ---
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
        # 利益最大化：超过5小时扣0.5h休息
        actual = dur - 0.5 if dur > 5 else dur
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 3. 初始模板 (含全员预设) ---
def load_all_template(staff_list):
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    df = pd.DataFrame({"员工": staff_list})
    for d in days: df[f"{d}_起"], df[f"{d}_止"] = "", ""
    # 此处可根据之前的逻辑继续内置 set_shift 规则...
    return df

# --- 4. 权限与登录 ---
staff_df, status = get_data()
if "role" not in st.session_state: st.session_state.role = None
if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 5, 1])
    with col_mid:
        st.header("Roster 财务管理系统")
        pwd = st.text_input("🔑 密码", type="password")
        if st.button("登录"):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            st.rerun()
    st.stop()

# 数据初始化
if 'main_df' not in st.session_state:
    st.session_state.main_df = load_all_template(list(staff_df["姓名"]))
if 'daily_sales' not in st.session_state:
    st.session_state.daily_sales = {d: 0.0 for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]}

# --- 5. 功能区 ---
st.title(f"🚀 {'老板' if st.session_state.role=='owner' else '店长'}排班终端")

# A. 快速录入助手 (日期多选)
with st.expander("👤 快速排班导入 (多选日期)", expanded=False):
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1: sn = st.selectbox("选择员工", list(staff_df["姓名"]))
    with c2: days_sel = st.multiselect("选择重复日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
    with c3: shift = st.selectbox("选择班次", ["8-2", "10-6", "8-6", "2-6", "10-3"])
    
    preset = {"8-2":("08:00","14:00"), "10-6":("10:00","18:00"), "8-6":("08:00","18:00"), "2-6":("14:00","18:00"), "10-3":("10:00","15:00")}.get(shift)
    if st.button("一键填入并保存"):
        for d in days_sel:
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_起"] = preset[0]
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_止"] = preset[1]
        st.rerun()

# B. 核心排班表
t_h = (len(st.session_state.main_df) + 1) * 35 + 60
edited_df = st.data_editor(st.session_state.main_df, use_container_width=True, hide_index=True, height=t_h)
st.session_state.main_df = edited_df

# C. 云端同步按钮
cc1, cc2 = st.columns(2)
if cc1.button("💾 保存并同步至云端", use_container_width=True):
    st.session_state["cloud_db"] = edited_df.copy()
    st.toast("已保存！")
if cc2.button("📥 下载最新云端模板", use_container_width=True):
    if "cloud_db" in st.session_state:
        st.session_state.main_df = st.session_state["cloud_db"].copy()
        st.rerun()

# --- 6. 财务与工占比分析 (老板模式) ---
if st.session_state.role == "owner":
    st.divider()
    st.header("📊 营业额与工占比分析")
    
    # 营业额录入区
    st.write("请录入每日营业额 ($):")
    sc = st.columns(7)
    days_list = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for i, d in enumerate(days_list):
        st.session_state.daily_sales[d] = sc[i].number_input(d, value=st.session_state.daily_sales[d], step=100.0)

    # 数据汇总计算
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    daily_wages = {d: 0.0 for d in days_list}
    daily_hours = {d: 0.0 for d in days_list}
    staff_summary = []
    
    total_cash = 0.0
    total_eft = 0.0

    for _, row in edited_df.iterrows():
        name = row["员工"]
        rate = STAFF_DB.get(name, {}).get("时薪", 0)
        p_type = str(STAFF_DB.get(name, {}).get("类型", "cash")).lower()
        
        row_total_h, row_total_w = 0.0, 0.0
        for d in days_list:
            h, w = calc_wage_details(row[f"{d}_起"], row[f"{d}_止"], rate)
            daily_hours[d] += h
            daily_wages[d] += w
            row_total_h += h
            row_total_w += w
            
        if p_type == "cash": total_cash += row_total_w
        else: total_eft += row_total_w
        
        staff_summary.append({"员工": name, "每周总工时": row_total_h, "每周总薪资": f"${round(row_total_w, 2)}", "支付": p_type.upper()})

    # 计算每日工占比和周平均
    total_sales = sum(st.session_state.daily_sales.values())
    total_wages = sum(daily_wages.values())
    
    analysis_df = pd.DataFrame({
        "指标": ["总工时 (h)", "总工资 ($)", "营业额 ($)", "工占比 (%)"],
        **{d: [daily_hours[d], round(daily_wages[d], 2), st.session_state.daily_sales[d], 
               f"{round(daily_wages[d]/st.session_state.daily_sales[d]*100, 1)}%" if st.session_state.daily_sales[d]>0 else "0%"] 
           for d in days_list}
    })
    
    st.table(analysis_df)
    
    # 周汇总
    st.divider()
    avg_labor_cost = f"{round(total_wages/total_sales*100, 1)}%" if total_sales > 0 else "0%"
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("周总营业额", f"${round(total_sales, 2)}")
    m2.metric("周总工资支出", f"${round(total_wages, 2)}")
    m3.metric("本周平均工占比", avg_labor_cost)
    m4.metric("现金准备", f"${round(total_cash, 2)}")

    with st.expander("查看员工个人明细"):
        st.table(pd.DataFrame(staff_summary))
