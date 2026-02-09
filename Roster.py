import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 深度纯净配置：强力隐藏所有官方痕迹
st.set_page_config(page_title="Roster Pro", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* 彻底隐藏顶部装饰、GitHub链接和所有官方按钮 */
    header {visibility: hidden !important; height: 0 !important;}
    footer {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    .stDeployButton {display: none !important;}
    [data-testid="stSidebar"] {display: none !important;}
    [data-testid="stToolbar"] {display: none !important;}
    button[title="Manage app"] {display: none !important;}
    
    /* 手机端全员显示优化：强制取消表格内滑动 */
    .stDataFrame div[data-testid="stTable"] {
        overflow: visible !important;
    }
    
    /* 调整页面顶部间距 */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 0rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. 核心连接与算法 ---
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
        # 利益最大化：超过5小时扣除0.5h休息
        actual = dur - 0.5 if dur > 5 else dur
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 3. 登录逻辑 (boss2026 / manager888) ---
if "role" not in st.session_state:
    st.session_state.role = None

if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 5, 1])
    with col_mid:
        st.markdown("<h2 style='text-align: center;'>Roster 业务管理</h2>", unsafe_allow_html=True)
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

    # A. 顶部录入与日期
    sel_date = st.date_input("📅 排班日期", datetime.now() - timedelta(days=datetime.now().weekday()))
    
    # 快速导入功能
    with st.expander("👤 单独录入员工时间"):
        c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
        with c1: s_name = st.selectbox("员工", list(STAFF_DB.keys()))
        with c2: s_day = st.selectbox("日期", days_cn)
        with c3: i_s = st.selectbox("开始", TIME_OPTIONS, index=16)
        with c4: i_e = st.selectbox("结束", TIME_OPTIONS, index=28)
        if st.button("确定导入表格", use_container_width=True):
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == s_name, f"{s_day}_起"] = i_s
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == s_name, f"{s_day}_止"] = i_e
            st.rerun()

    if 'main_df' not in st.session_state:
        init_data = {"员工": list(STAFF_DB.keys())}
        for d in days_cn: init_data[f"{d}_起"], init_data[f"{d}_止"] = [""]*len(STAFF_DB), [""]*len(STAFF_DB)
        st.session_state.main_df = pd.DataFrame(init_data)

    # 同步功能
    cc1, cc2 = st.columns(2)
    if cc1.button("🔄 同步上周", use_container_width=True):
        if "tmpl" in st.session_state: st.session_state.main_df = st.session_state.tmpl.copy(); st.rerun()
    if cc2.button("💾 存为模板", use_container_width=True):
        st.session_state.tmpl = st.session_state.main_df.copy(); st.toast("模板已存")

    # B. 排班表格 (视觉分区优化：全员显示)
    st.write(f"### {sel_date.strftime('%m/%d')} 排班表")
    col_cfg = {"员工": st.column_config.TextColumn("", disabled=True, width="small")}
    for d in days_cn:
        col_cfg[f"{d}_起"] = st.column_config.SelectboxColumn(f"{d} | Start", options=TIME_OPTIONS, width="small")
        col_cfg[f"{d}_止"] = st.column_config.SelectboxColumn(f"{d} | End", options=TIME_OPTIONS, width="small")

    # 动态撑开高度：人数 * 35px + 表头
    t_h = (len(st.session_state.main_df) + 1) * 35 + 50

    edited_df = st.data_editor(st.session_state.main_df, column_config=col_cfg, use_container_width=True, hide_index=True, height=t_h, key="vClean")
    st.session_state.main_df = edited_df

    # C. 全英文预览 (用于截图发布)
    st.divider()
    if st.button("✨ 生成工作组排班图 (English Preview)", use_container_width=True):
        exp_df = pd.DataFrame({"NAME": list(STAFF_DB.keys())})
        for cn, en in zip(days_cn, days_en):
            comb = []
            for _, row in edited_df.iterrows():
                s, e = row[f"{cn}_起"], row[f"{cn}_止"]
                comb.append(f"{format_eng_time(s)}-{format_eng_time(e)}" if s and e else "-")
            exp_df[en] = comb
        st.markdown(f"#### SCHEDULE: {sel_date.strftime('%b %d')} - {(sel_date+timedelta(days=6)).strftime('%b %d')}")
        st.dataframe(exp_df, use_container_width=True, hide_index=True)
        st.info("💡 截图保存上方表格发到群组即可。")

    # D. 财务汇总 (老板模式专属)
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
        st.metric("Cash 现金汇总", f"${round(c_tot, 2)}")
        st.metric("EFT 转账汇总", f"${round(e_tot, 2)}")

else:
    st.error("数据连接失败。")

if st.sidebar.button("退出登录"):
    st.session_state.role = None
    st.rerun()
