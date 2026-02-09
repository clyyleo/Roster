import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 深度纯净配置
st.set_page_config(page_title="Roster Pro", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    header {visibility: hidden !important; height: 0 !important;}
    footer {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    div[data-testid="stStatusWidget"], 
    button[title="Manage app"], 
    iframe[title="manage-app-button"],
    .stAppDeployButton,
    [data-testid="stToolbar"] {
        display: none !important;
        visibility: hidden !important;
    }
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
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

staff_df, status = get_data()

def format_eng_time(t):
    if not t or ":" not in str(t): return ""
    h, m = str(t).split(':')
    return f"{int(h)}" if m == "00" else f"{int(h)}:{m}"

def calc_wage(s, e, rate):
    if not s or not e: return 0.0, 0.0
    try:
        h1, m1 = map(float, str(s).split(':'))
        h2, m2 = map(float, str(e).split(':'))
        dur = (h2 + m2/60) - (h1 + m1/60)
        if dur < 0: dur += 24
        actual = dur - 0.5 if dur > 5 else dur # 利益最大化
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 3. 权限逻辑 ---
if "role" not in st.session_state:
    st.session_state.role = None

if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 5, 1])
    with col_mid:
        st.markdown("<h3 style='text-align: center;'>Roster 业务管理</h3>", unsafe_allow_html=True)
        pwd = st.text_input("🔑 密码", type="password", placeholder="输入密码...", label_visibility="collapsed")
        if st.button("进入系统", use_container_width=True):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            if st.session_state.role: st.rerun()
            else: st.error("密码错误")
    st.stop()

# --- 4. 主界面 ---
if status == "success":
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    days_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    days_en = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    TIME_OPTIONS = [""] + [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]
    
    PRESET_SHIFTS = {
        "自定义": None,
        "8-2": ("08:00", "14:00"),
        "8-6": ("08:00", "18:00"),
        "10-3": ("10:00", "15:00"),
        "10-6": ("10:00", "18:00"),
        "2-6": ("14:00", "18:00")
    }

    sel_date = st.date_input("📅 选择起始日期", datetime.now() - timedelta(days=datetime.now().weekday()))
    
    if 'main_df' not in st.session_state:
        init_data = {"员工": list(STAFF_DB.keys())}
        for d in days_cn: init_data[f"{d}_起"], init_data[f"{d}_止"] = [""]*len(STAFF_DB), [""]*len(STAFF_DB)
        st.session_state.main_df = pd.DataFrame(init_data)

    # A. 顶部快速录入助手 (升级版：支持日期多选)
    with st.expander("👤 批量/常用班次录入", expanded=True):
        c1, c2 = st.columns([1, 1])
        with c1: sn = st.selectbox("选择员工", list(STAFF_DB.keys()))
        with c2: shift_choice = st.selectbox("常用班次", list(PRESET_SHIFTS.keys()))
        
        # 日期多选框
        selected_days = st.multiselect("选择重复日期 (可多选)", days_cn, placeholder="点击勾选周几...")
        
        c4, c5, c6 = st.columns([1, 1, 1])
        preset = PRESET_SHIFTS[shift_choice]
        with c4: in_start = st.selectbox("Start", TIME_OPTIONS, index=TIME_OPTIONS.index(preset[0]) if preset else 16)
        with c5: in_end = st.selectbox("End", TIME_OPTIONS, index=TIME_OPTIONS.index(preset[1]) if preset else 28)
        with c6:
            st.write("")
            if st.button("批量填入表格", use_container_width=True):
                if not selected_days:
                    st.warning("请至少选择一个日期")
                else:
                    for d in selected_days:
                        st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_起"] = in_start
                        st.session_state.main_df.loc[st.session_state.main_df['员工'] == sn, f"{d}_止"] = in_end
                    st.rerun()

    # B. 排班表格
    st.write(f"### {sel_date.strftime('%m/%d')} 详细排班表")
    col_cfg = {"员工": st.column_config.TextColumn("", disabled=True, width="small")}
    for d in days_cn:
        col_cfg[f"{d}_起"] = st.column_config.SelectboxColumn(f"{d}|起", options=TIME_OPTIONS, width="small")
        col_cfg[f"{d}_止"] = st.column_config.SelectboxColumn(f"{d}|止", options=TIME_OPTIONS, width="small")

    t_h = (len(st.session_state.main_df) + 1) * 35 + 50
    edited_df = st.data_editor(st.session_state.main_df, column_config=col_cfg, use_container_width=True, hide_index=True, height=t_h, key="vFinalMulti")
    st.session_state.main_df = edited_df

    # 同步与模板
    cc1, cc2 = st.columns(2)
    if cc1.button("🔄 同步上周", use_container_width=True):
        if "tmpl" in st.session_state: st.session_state.main_df = st.session_state.tmpl.copy(); st.rerun()
    if cc2.button("💾 存为模板", use_container_width=True):
        st.session_state.tmpl = st.session_state.main_df.copy(); st.toast("模板已存")

    # C. 导出预览
    st.divider()
    if st.button("✨ 生成工作组截图 (English Preview)", use_container_width=True):
        exp_df = pd.DataFrame({"NAME": list(STAFF_DB.keys())})
        for cn, en in zip(days_cn, days_en):
            cb = []
            for _, row in edited_df.iterrows():
                s, e = row[f"{cn}_起"], row[f"{cn}_止"]
                cb.append(f"{format_eng_time(s)}-{format_eng_time(e)}" if s and e else "-")
            exp_df[en] = cb
        st.markdown(f"#### SCHEDULE: {sel_date.strftime('%b %d')} - {(sel_date+timedelta(days=6)).strftime('%b %d')}")
        st.dataframe(exp_df, use_container_width=True, hide_index=True)
        st.info("💡 手机直接截图上方表格发给群组。")

    # D. 财务汇总
    if st.session_state.role == "owner":
        st.divider()
        st.header("💰 财务汇总")
        c_tot, e_tot = 0.0, 0.0
        for _, row in edited_df.iterrows():
            name = row["员工"]
            rate, p_type = STAFF_DB.get(name,{}).get("时薪",0), STAFF_DB.get(name,{}).get("类型","cash")
            for d in days_cn:
                _, p = calc_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
                if str(p_type).lower() == "cash": c_tot += p
                else: e_tot += p
        st.metric("Cash (取现准备)", f"${round(c_tot, 2)}")
        st.metric("EFT (转账汇总)", f"${round(e_tot, 2)}")

else:
    st.error("数据加载失败。")

if st.sidebar.button("退出系统"):
    st.session_state.role = None
    st.rerun()
