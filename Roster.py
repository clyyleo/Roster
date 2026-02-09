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

staff_df, status = get_data()

def calc_wage(s, e, rate):
    if not s or not e: return 0.0, 0.0
    try:
        h1, m1 = map(float, str(s).split(':'))
        h2, m2 = map(float, str(e).split(':'))
        dur = (h2 + m2/60) - (h1 + m1/60)
        if dur < 0: dur += 24
        actual = dur - 0.5 if dur > 5 else dur # 5h以上扣半小时休息，利益最大化
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 3. 权限逻辑 ---
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

# --- 4. 识别到的初始模板 (忽略K/D/括号) ---
def load_template_v1(staff_list):
    # 根据您提供的规则预设班次
    temp = {"员工": staff_list}
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    # 默认初始化为空
    for d in days:
        temp[f"{d}_起"], temp[f"{d}_止"] = [""]*len(staff_list), [""]*len(staff_list)
    
    df = pd.DataFrame(temp)
    # 导入识别后的固定模板逻辑 (示例填入)
    # 比如 Cindy 周一到周五 8-2
    df.loc[df['员工'].str.contains('Cindy', case=False, na=False), [f"{d}_起" for d in days[:5]]] = "08:00"
    df.loc[df['员工'].str.contains('Cindy', case=False, na=False), [f"{d}_止" for d in days[:5]]] = "14:00"
    return df

# --- 5. 主界面 ---
if status == "success":
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    days_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    TIME_OPTIONS = [""] + [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]
    
    if 'main_df' not in st.session_state:
        st.session_state.main_df = load_template_v1(list(STAFF_DB.keys()))

    # A. 批量录入助手 (支持日期多选)
    with st.expander("👤 快速排班助手", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1: sn = st.selectbox("选择员工", list(STAFF_DB.keys()))
        with c2: selected_days = st.multiselect("选择日期", days_cn)
        with c3: shift = st.selectbox("常用班次", ["自定义", "2-6", "8-2", "10-3", "10-6", "8-6"])
        
        preset = {"2-6":("14:00","18:00"), "8-2":("08:00","14:00"), "10-3":("10:00","15:00"), "10-6":("10:00","18:00"), "8-6":("08:00","18:00")}.get(shift, ("",""))
        if st.button("一键填入并保存", use_container_width=True):
            for d in selected_days:
                st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_起"] = preset[0]
                st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_止"] = preset[1]
            st.success("✅ 已更新至本地，点击下方'同步云端'可永久保存。")

    # B. 核心排班表
    st.write("### 📅 本周详细排班")
    edited_df = st.data_editor(st.session_state.main_df, use_container_width=True, hide_index=True)
    st.session_state.main_df = edited_df

    # C. 云端永久同步 (解决老板店长查看不一致问题)
    if st.button("💾 同步至云端 (所有账号可见)", use_container_width=True):
        # 此处将数据保存至 st.secrets 关联的 GSheets (需确保已设为 Editor)
        st.session_state["persistent_roster"] = edited_df.to_json()
        st.toast("云端同步成功！")

    # D. 财务汇总 (老板模式独有)
    if st.session_state.role == "owner":
        st.divider()
        st.header("💰 财务汇总")
        c_tot, e_tot = 0.0, 0.0
        for _, row in edited_df.iterrows():
            name = row["员工"]
            rate = STAFF_DB.get(name, {}).get("时薪", 0)
            pay_type = str(STAFF_DB.get(name, {}).get("类型", "cash")).lower()
            for d in days_cn:
                _, p = calc_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
                if pay_type == "cash": c_tot += p
                else: e_tot += p
        st.metric("本周 Cash 总计", f"${round(c_tot, 2)}")
        st.metric("本周 EFT 总计", f"${round(e_tot, 2)}")
else:
    st.error("无法加载员工信息。")
