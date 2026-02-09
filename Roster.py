import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 深度纯净配置：强制隐藏所有 Streamlit 官方组件
st.set_page_config(page_title="Roster Pro", layout="wide", initial_sidebar_state="collapsed")

# 深度强力隐藏脚本
st.markdown("""
    <style>
    /* 1. 隐藏顶部 Header 和底部 Footer */
    header {visibility: hidden !important; height: 0 !important;}
    footer {visibility: hidden !important;}
    
    #MainMenu {visibility: hidden !important;}
    
    /* 2. 强力移除右下角 Manage app 悬浮按钮 */
    div[data-testid="stStatusWidget"], 
    button[title="Manage app"], 
    .stAppDeployButton,
    iframe[title="manage-app-button"],
    #viewer-badge {
        display: none !important;
        visibility: hidden !important;
    }

    /* 3. 移除屏幕边缘所有多余间距 */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
    }
    
    /* 4. 手机端优化：让表格看起来更像原生 App */
    [data-testid="stVerticalBlock"] > div:has(div.stDataTable) {
        border: 1px solid #f0f2f6;
        border-radius: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. 核心数据连接 ---
def get_data_ultimate():
    try:
        raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        doc_id = raw_url.split('/d/')[1].split('/')[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid=0"
        df = pd.read_csv(csv_url)
        return df, "success"
    except Exception as e:
        return pd.DataFrame(), str(e)

staff_df, status = get_data_ultimate()

# --- 3. 登录逻辑 (boss2026 / manager888) ---
if "role" not in st.session_state:
    st.session_state.role = None

if st.session_state.role is None:
    st.write("## ") 
    _, col_mid, _ = st.columns([1, 5, 1])
    with col_mid:
        st.markdown("<h2 style='text-align: center;'>Roster 业务管理</h2>", unsafe_allow_html=True)
        pwd = st.text_input("🔑 访问密码", type="password", label_visibility="collapsed", placeholder="请输入密码...")
        if st.button("立即进入", use_container_width=True):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            if st.session_state.role: st.rerun()
            else: st.error("密码错误")
    st.stop()

# --- 4. 辅助计算逻辑 ---
def format_time_eng(t):
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
        actual = dur - 0.5 if dur > 5 else dur # 利益最大化算法
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 5. 主界面 ---
if status == "success":
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    days_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    days_en = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    TIME_OPTIONS = [""] + [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]

    # A. 顶部与同步
    selected_date = st.date_input("📅 选择日期", datetime.now() - timedelta(days=datetime.now().weekday()))
    
    if 'main_df' not in st.session_state:
        init_data = {"员工": list(STAFF_DB.keys())}
        for d in days_cn:
            init_data[f"{d}_起"], init_data[f"{d}_止"] = [""]*len(STAFF_DB), [""]*len(STAFF_DB)
        st.session_state.main_df = pd.DataFrame(init_data)

    with st.expander("➕ 快速录入助手", expanded=False):
        c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])
        with c1: s_s = st.selectbox("员工", list(STAFF_DB.keys()))
        with c2: s_d = st.selectbox("日期", days_cn)
        with c3: i_s = st.selectbox("起", options=TIME_OPTIONS, index=16)
        with c4: i_e = st.selectbox("止", options=TIME_OPTIONS, index=28)
        if st.button("填入", use_container_width=True):
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == s_s, f"{s_d}_起"] = i_s
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == s_s, f"{s_d}_止"] = i_e
            st.rerun()

    col_btn1, col_btn2 = st.columns(2)
    if col_btn1.button("🔄 同步上周", use_container_width=True):
        if "tmpl" in st.session_state: st.session_state.main_df = st.session_state.tmpl.copy(); st.rerun()
    if col_btn2.button("💾 存为模板", use_container_width=True):
        st.session_state.tmpl = st.session_state.main_df.copy(); st.toast("模板已存")

    # B. 排班表格 (强制全员显示)
    st.write(f"### {selected_date.strftime('%m/%d')} 排班表 ({'老板' if st.session_state.role=='owner' else '店长'})")
    
    col_cfg = {"员工": st.column_config.TextColumn("", disabled=True, width="small")}
    for d in days_cn:
        col_cfg[f"{d}_起"] = st.column_config.SelectboxColumn(f"{d}|起", options=TIME_OPTIONS, width="small")
        col_cfg[f"{d}_止"] = st.column_config.SelectboxColumn(f"{d}|止", options=TIME_OPTIONS, width="small")

    # 自动全员撑开高度
    t_height = (len(st.session_state.main_df) + 1) * 35 + 45

    edited_df = st.data_editor(
        st.session_state.main_df, 
        column_config=col_cfg, 
        use_container_width=True, 
        hide_index=True, 
        height=t_height,
        key="vPureFinal"
    )
    st.session_state.main_df = edited_df

    # C. 全英文预览
    if st.button("✨ 生成工作组排班图 (English)", use_container_width=True):
        exp_df = pd.DataFrame({"NAME": list(STAFF_DB.keys())})
        for cn, en in zip(days_cn, days_en):
            comb = []
            for _, row in edited_df.iterrows():
                s, e = row[f"{cn}_起"], row[f"{cn}_止"]
                comb.append(f"{format_time_eng(s)}-{format_time_eng(e)}" if s and e else "-")
            exp_df[en] = comb
        st.dataframe(exp_df, use_container_width=True, hide_index=True)
        st.info("💡 手机截图上方表格发到群组。")

    # D. 财务汇总 (仅老板模式显示)
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
        st.metric("Cash 现金准备", f"${round(c_tot, 2)}")
        st.metric("EFT 转账汇总", f"${round(e_tot, 2)}")

else:
    st.error("数据加载失败。")

if st.sidebar.button("退出登录"):
    st.session_state.role = None
    st.rerun()
