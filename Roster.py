import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 深度纯净配置
st.set_page_config(page_title="Roster Pro", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>header,footer,#MainMenu{visibility:hidden;} button[title="Manage app"]{display:none !important;}</style>""", unsafe_allow_html=True)

# --- 2. 核心数据连接 ---
def get_data():
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        doc_id = url.split('/d/')[1].split('/')[0]
        staff_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid=0"
        return pd.read_csv(staff_url), "success"
    except Exception as e:
        return pd.DataFrame(), str(e)

# --- 3. 全员固定模板识别 (根据手写稿 image_6a7ddc.png) ---
def load_all_staff_template(staff_list):
    temp = {"员工": staff_list}
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for d in days:
        temp[f"{d}_起"], temp[f"{d}_止"] = [""]*len(staff_list), [""]*len(staff_list)
    
    df = pd.DataFrame(temp)
    
    # 填入识别到的全员规则
    def set_shift(name, start, end, day_indices):
        for idx in day_indices:
            df.loc[df['员工'].str.contains(name, case=False, na=False), f"{days[idx]}_起"] = start
            df.loc[df['员工'].str.contains(name, case=False, na=False), f"{days[idx]}_止"] = end

    # 按照您的手写原件导入
    set_shift("WANG", "14:00", "18:00", [0, 3, 4]) # 2-6
    set_shift("WANG", "08:00", "14:00", [1, 2])    # 8-2
    set_shift("WANG", "08:30", "14:00", [6])       # 8:30-2
    set_shift("LAN", "08:00", "14:00", [0, 2])     # 8-2
    set_shift("LAN", "10:00", "15:00", [4])        # 10-3
    set_shift("LAN", "10:00", "18:00", [5])        # 10-6
    set_shift("LAN", "10:00", "17:00", [6])        # 10-5
    set_shift("Cindy", "08:00", "14:00", [0, 3, 4])# 8-2
    set_shift("Cindy", "14:00", "18:00", [1, 2])    # 2-6
    set_shift("DAHLIA", "08:00", "18:00", [5])     # 8-6
    set_shift("MOON", "10:00", "14:00", [1])       # 10-2
    set_shift("YUKI", "10:00", "18:00", [0, 3])    # 10-6
    set_shift("SUSIE", "12:00", "14:00", [4])      # 12-2
    set_shift("Chay", "08:00", "18:00", [1, 4])    # 8-6
    set_shift("Chay", "10:00", "18:00", [2])       # 10-6
    set_shift("Chay", "08:00", "14:00", [3, 5])    # 8-2
    set_shift("Chay", "08:30", "17:00", [6])       # 8:30-5
    
    return df

# --- 4. 利益最大化算法 ---
def calc_wage(s, e, rate):
    if not s or not e: return 0.0, 0.0
    try:
        h1, m1 = map(float, str(s).split(':'))
        h2, m2 = map(float, str(e).split(':'))
        dur = (h2 + m2/60) - (h1 + m1/60)
        if dur < 0: dur += 24
        actual = dur - 0.5 if dur > 5 else dur
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 5. 权限与执行 ---
staff_df, status = get_data()

if "role" not in st.session_state: st.session_state.role = None
if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 5, 1])
    with col_mid:
        st.header("Roster 业务管理")
        pwd = st.text_input("🔑 密码", type="password")
        if st.button("进入系统", use_container_width=True):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            if st.session_state.role: st.rerun()
    st.stop()

# 初始化表格
if 'main_df' not in st.session_state:
    st.session_state.main_df = load_all_staff_template(list(staff_df["姓名"]))

# --- 6. 主界面 ---
st.write(f"### 📅 全员排班预览 ({'老板' if st.session_state.role=='owner' else '店长'})")

# 批量调整助手
with st.expander("👤 快速调整某人时间"):
    c1, c2, c3 = st.columns(3)
    with c1: sn = st.selectbox("员工", list(staff_df["姓名"]))
    with c2: days_sel = st.multiselect("日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
    with c3: shift = st.selectbox("常用班次", ["8-2", "10-6", "8-6", "2-6", "10-2"])
    
    preset = {"8-2":("08:00","14:00"), "10-6":("10:00","18:00"), "8-6":("08:00","18:00"), "2-6":("14:00","18:00"), "10-2":("10:00","14:00")}.get(shift)
    if st.button("更新并同步", use_container_width=True):
        for d in days_sel:
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_起"] = preset[0]
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_止"] = preset[1]
        st.rerun()

# 核心编辑器
t_h = (len(st.session_state.main_df) + 1) * 35 + 50
edited_df = st.data_editor(st.session_state.main_df, use_container_width=True, hide_index=True, height=t_h)
st.session_state.main_df = edited_df

# 财务汇总 (仅老板)
if st.session_state.role == "owner":
    st.divider()
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    c_tot, e_tot = 0.0, 0.0
    for _, row in edited_df.iterrows():
        name = row["员工"]
        rate, p_type = STAFF_DB.get(name,{}).get("时薪",0), str(STAFF_DB.get(name,{}).get("类型","cash")).lower()
        for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
            _, p = calc_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
            if p_type == "cash": c_tot += p
            else: e_tot += p
    st.metric("Cash 现金准备", f"${round(c_tot, 2)}")
    st.metric("EFT 转账总额", f"${round(e_tot, 2)}")
