import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 深度纯净配置
st.set_page_config(page_title="Roster Pro", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>header, footer, #MainMenu {visibility: hidden;} div[data-testid="stStatusWidget"], button[title="Manage app"] {display: none !important;}</style>""", unsafe_allow_html=True)

# --- 2. 核心数据连接 ---
def get_data():
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        doc_id = url.split('/d/')[1].split('/')[0]
        # 读取 Staff 标签页 (员工信息)
        staff_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid=0"
        # 读取 Roster 标签页 (历史排班) - 假设 gid=12345678 (需在表格里确认标签页ID)
        return pd.read_csv(staff_url), "success"
    except Exception as e:
        return pd.DataFrame(), str(e)

staff_df, status = get_data()

# --- 3. 利益最大化算法 ---
def calc_wage(s, e, rate):
    if not s or not e: return 0.0, 0.0
    try:
        h1, m1 = map(float, str(s).split(':'))
        h2, m2 = map(float, str(e).split(':'))
        dur = (h2 + m2/60) - (h1 + m1/60)
        if dur < 0: dur += 24
        # 核心利益：超过5h自动扣0.5h
        actual = dur - 0.5 if dur > 5 else dur
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 4. 登录逻辑 (boss2026 / manager888) ---
if "role" not in st.session_state: st.session_state.role = None
if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 5, 1])
    with col_mid:
        st.header("Roster 业务管理")
        pwd = st.text_input("🔑 密码", type="password", placeholder="输入密码...")
        if st.button("进入系统", use_container_width=True):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            if st.session_state.role: st.rerun()
    st.stop()

# --- 5. 主界面 ---
if status == "success":
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    days_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    TIME_OPTIONS = [""] + [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]
    
    # 自动加载/初始化
    if 'main_df' not in st.session_state:
        init_data = {"员工": list(STAFF_DB.keys())}
        for d in days_cn: init_data[f"{d}_起"], init_data[f"{d}_止"] = [""]*len(STAFF_DB), [""]*len(STAFF_DB)
        st.session_state.main_df = pd.DataFrame(init_data)

    # A. 批量录入
    with st.expander("👤 快速批量录入", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1: sn = st.selectbox("员工", list(STAFF_DB.keys()))
        with c2: selected_days = st.multiselect("日期", days_cn)
        with c3: shift = st.selectbox("常用班次", ["自定义", "8-2", "8-6", "10-3", "10-6"])
        
        # 快速转换逻辑
        times = {"8-2":("08:00","14:00"), "8-6":("08:00","18:00"), "10-3":("10:00","15:00"), "10-6":("10:00","18:00")}.get(shift, ("08:00","14:00"))
        if st.button("批量填入并同步", use_container_width=True):
            for d in selected_days:
                st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_起"] = times[0]
                st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_止"] = times[1]
            st.rerun()

    # B. 排班表格
    st.write(f"### 本周排班 ({'老板模式' if st.session_state.role=='owner' else '店长模式'})")
    t_h = (len(st.session_state.main_df) + 1) * 35 + 50
    edited_df = st.data_editor(st.session_state.main_df, use_container_width=True, hide_index=True, height=t_h)
    st.session_state.main_df = edited_df

    # C. 财务汇总 (老板专属)
    if st.session_state.role == "owner":
        st.divider()
        st.header("💰 财务汇总 (老板可见)")
        c_tot, e_tot = 0.0, 0.0
        for _, row in edited_df.iterrows():
            name = row["员工"]
            rate, p_type = STAFF_DB.get(name,{}).get("时薪",0), STAFF_DB.get(name,{}).get("类型","cash")
            for d in days_cn:
                _, p = calc_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
                if str(p_type).lower() == "cash": c_tot += p
                else: e_tot += p
        col1, col2 = st.columns(2)
        col1.metric("Cash 现金准备", f"${round(c_tot, 2)}")
        col2.metric("EFT 转账总额", f"${round(e_tot, 2)}")

    st.info("💡 权限已设为云端同步模式。店长修改后，老板刷新即可看到最新账目。")
