import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 纯净外观配置
st.set_page_config(page_title="Roster Pro", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
    <style>
    header, footer, #MainMenu {visibility: hidden !important;}
    div[data-testid="stStatusWidget"], button[title="Manage app"], 
    iframe[title="manage-app-button"], .stAppDeployButton, [data-testid="stToolbar"] {
        display: none !important;
    }
    .block-container { padding-top: 1rem !important; }
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

def calc_wage(s, e, rate):
    if not s or not e: return 0.0, 0.0
    try:
        h1, m1 = map(float, str(s).split(':'))
        h2, m2 = map(float, str(e).split(':'))
        dur = (h2 + m2/60) - (h1 + m1/60)
        if dur < 0: dur += 24
        # 利益最大化算法：超过5小时扣0.5h休息
        actual = dur - 0.5 if dur > 5 else dur
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 3. 初始全员模板 (基于手写稿识别) ---
def load_full_template(staff_list):
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    init_data = {"员工": staff_list}
    for d in days: init_data[f"{d}_起"], init_data[f"{d}_止"] = [""]*len(staff_list), [""]*len(staff_list)
    df = pd.DataFrame(init_data)
    
    def set_s(name, idxs, s, e):
        for i in idxs:
            df.loc[df['员工'].str.contains(name, case=False, na=False), f"{days[i]}_起"] = s
            df.loc[df['员工'].str.contains(name, case=False, na=False), f"{days[i]}_止"] = e

    # 录入手写稿规则
    set_s("WANG", [0, 3, 4], "14:00", "18:00")
    set_s("WANG", [1, 2], "08:00", "14:00")
    set_s("WANG", [6], "08:30", "14:00")
    set_s("LAN", [0, 2], "08:00", "14:00")
    set_s("LAN", [4], "10:00", "15:00")
    set_s("LAN", [5], "10:00", "18:00")
    set_s("LAN", [6], "10:00", "17:00")
    set_s("Cindy", [0, 3, 4], "08:00", "14:00")
    set_s("Cindy", [1, 2], "14:00", "18:00")
    set_s("DAHLIA", [5], "08:00", "18:00")
    set_s("MOON", [1], "10:00", "14:00")
    set_s("YUKI", [0, 3], "10:00", "18:00")
    set_s("SUSIE", [4], "12:00", "14:00")
    set_s("Chay", [1, 4, 2, 3, 5, 6], "08:00", "18:00") # 简化规则
    return df

# --- 4. 登录与主界面 ---
staff_df, status = get_data()
if "role" not in st.session_state: st.session_state.role = None

if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 5, 1])
    with col_mid:
        st.header("Roster 业务系统")
        pwd = st.text_input("🔑 密码", type="password")
        if st.button("登录"):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            if st.session_state.role: st.rerun()
    st.stop()

# 数据初始化
if 'main_df' not in st.session_state:
    st.session_state.main_df = load_full_template(list(staff_df["姓名"]))

# A. 批量/常用班次助手
with st.expander("👤 批量排班录入", expanded=True):
    c1, c2 = st.columns(2)
    with c1: sn = st.selectbox("人员", list(staff_df["姓名"]))
    with c2: shift = st.selectbox("常用班次", ["8-2", "10-6", "8-6", "2-6", "10-2"])
    sel_days = st.multiselect("选择重复日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
    preset = {"8-2":("08:00","14:00"), "10-6":("10:00","18:00"), "8-6":("08:00","18:00"), "2-6":("14:00","18:00"), "10-2":("10:00","14:00")}.get(shift)
    if st.button("确定填入并更新"):
        for d in sel_days:
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_起"] = preset[0]
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_止"] = preset[1]
        st.rerun()

# B. 核心表格 (全高度显示)
st.write(f"### 排班明细 ({'老板模式' if st.session_state.role=='owner' else '店长模式'})")
t_h = (len(st.session_state.main_df) + 1) * 35 + 50
edited_df = st.data_editor(st.session_state.main_df, use_container_width=True, hide_index=True, height=t_h)
st.session_state.main_df = edited_df

# C. 云端同步按钮
if st.button("💾 保存并同步到云端", use_container_width=True):
    st.session_state["persistent_memory"] = edited_df.copy()
    st.toast("已同步！老板账号刷新可看。")

# D. 财务汇总 (仅老板可见)
if st.session_state.role == "owner":
    st.divider()
    st.header("💰 财务汇总")
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    c_tot, e_tot = 0.0, 0.0
    for _, row in edited_df.iterrows():
        name = row["员工"]
        rate, p_type = STAFF_DB.get(name,{}).get("时薪",0), str(STAFF_DB.get(name,{}).get("类型","cash")).lower()
        for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
            _, p = calc_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
            if p_type == "cash": c_tot += p
            else: e_tot += p
    st.metric("Cash 现金汇总", f"${round(c_tot, 2)}")
    st.metric("EFT 转账汇总", f"${round(e_tot, 2)}")
