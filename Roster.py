import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 深度纯净配置
st.set_page_config(page_title="Roster Pro", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>header,footer,#MainMenu{visibility:hidden;} div[data-testid="stStatusWidget"], button[title="Manage app"]{display:none !important;}</style>""", unsafe_allow_html=True)

# --- 2. 核心数据连接 ---
def get_data():
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        doc_id = url.split('/d/')[1].split('/')[0]
        staff_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid=0"
        return pd.read_csv(staff_url), "success"
    except Exception as e:
        return pd.DataFrame(), str(e)

# --- 3. 全员固定模板识别 (基于手写原件 image_6a7ddc.png) ---
def load_full_roster_template(staff_list):
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    # 初始化全空表格
    init_data = {"员工": staff_list}
    for d in days:
        init_data[f"{d}_起"], init_data[f"{d}_止"] = [""]*len(staff_list), [""]*len(staff_list)
    df = pd.DataFrame(init_data)

    # 快捷填入函数
    def set_shift(name_key, day_indices, start, end):
        for idx in day_indices:
            df.loc[df['员工'].str.contains(name_key, case=False, na=False), f"{days[idx]}_起"] = start
            df.loc[df['员工'].str.contains(name_key, case=False, na=False), f"{days[idx]}_止"] = end

    # --- 开始按图录入规则 ---
    set_shift("WANG", [0, 3, 4], "14:00", "18:00") # 2-6
    set_shift("WANG", [1, 2], "08:00", "14:00")    # 8-2
    set_shift("WANG", [6], "08:30", "14:00")       # 8:30-2

    set_shift("LAN", [0, 2], "08:00", "14:00")     # 8-2
    set_shift("LAN", [4], "10:00", "15:00")        # 10-3
    set_shift("LAN", [5], "10:00", "18:00")        # 10-6
    set_shift("LAN", [6], "10:00", "17:00")        # 10-5

    set_shift("Cindy", [0, 3, 4], "08:00", "14:00") # 8-2
    set_shift("Cindy", [1, 2], "14:00", "18:00")    # 2-6

    set_shift("DAHLIA", [5], "08:00", "18:00")      # 8-6

    set_shift("MOON", [1], "10:00", "14:00")        # 10-2

    set_shift("YUKI", [0, 3], "10:00", "18:00")     # 10-6

    set_shift("SUSIE", [4], "12:00", "14:00")       # 12-2

    set_shift("Chay", [1, 4], "08:00", "18:00")     # 8-6
    set_shift("Chay", [2], "10:00", "18:00")        # 10-6
    set_shift("Chay", [3, 5], "08:00", "14:00")     # 8-2
    set_shift("Chay", [6], "08:30", "17:00")        # 8:30-5

    return df

# --- 4. 利益最大化计算 (5h扣0.5h休息) ---
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
        st.header("Roster 业务管理系统")
        pwd = st.text_input("🔑 访问密码", type="password")
        if st.button("进入系统", use_container_width=True):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            if st.session_state.role: st.rerun()
    st.stop()

# 全员初始化
if 'main_df' not in st.session_state:
    st.session_state.main_df = load_full_roster_template(list(staff_df["姓名"]))

# --- 6. 主界面 ---
st.write(f"### 全员排班预览 ({'老板' if st.session_state.role=='owner' else '店长'})")

# 核心编辑器 (全高度撑开)
t_h = (len(st.session_state.main_df) + 1) * 35 + 55
edited_df = st.data_editor(st.session_state.main_df, use_container_width=True, hide_index=True, height=t_h)
st.session_state.main_df = edited_df

# 财务中心 (老板专属，带分类账单)
if st.session_state.role == "owner":
    st.divider()
    st.header("💰 财务汇总 (老板可见)")
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    c_tot, e_tot = 0.0, 0.0
    for _, row in edited_df.iterrows():
        name = row["员工"]
        rate, p_type = STAFF_DB.get(name,{}).get("时薪",0), str(STAFF_DB.get(name,{}).get("类型","cash")).lower()
        for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
            _, p = calc_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
            if p_type == "cash": c_tot += p
            else: e_tot += p
    
    col1, col2 = st.columns(2)
    col1.metric("Cash 现金准备", f"${round(c_tot, 2)}")
    col2.metric("EFT 转账汇总", f"${round(e_tot, 2)}")
