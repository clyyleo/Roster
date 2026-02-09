import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 纯净模式配置：隐藏官方菜单、页脚、Manage app 按钮
st.set_page_config(page_title="Roster Pro", layout="wide", initial_sidebar_state="collapsed")

hide_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div[data-testid="stStatusWidget"] {visibility: hidden;}
    .reportview-container .main footer {visibility: hidden;}
    /* 隐藏 Manage App 按钮 */
    button[title="Manage app"] {display: none !important;}
    /* 隐藏右上角装饰 */
    .stAppDeployButton {display: none !important;}
    </style>
"""
st.markdown(hide_style, unsafe_allow_html=True)

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

# --- 3. 登录逻辑 (双重密码: boss2026 / manager888) ---
if "role" not in st.session_state:
    st.session_state.role = None

if st.session_state.role is None:
    st.write("## ") # 留空增加美感
    _, col_mid, _ = st.columns([1, 5, 1])
    with col_mid:
        st.markdown("<h2 style='text-align: center;'>Roster 业务系统</h2>", unsafe_allow_html=True)
        pwd = st.text_input("🔑 访问密码", type="password", label_visibility="collapsed", placeholder="输入密码访问...")
        if st.button("进入系统", use_container_width=True):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            if st.session_state.role: st.rerun()
            else: st.error("密码错误")
    st.stop()

# --- 4. 辅助函数 ---
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
        actual = dur - 0.5 if dur > 5 else dur
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 5. 主界面 ---
if status == "success":
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    days_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    days_en = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    TIME_OPTIONS = [""] + [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]

    # A. 顶部选择与录入
    selected_date = st.date_input("📅 排班周一日期", datetime.now() - timedelta(days=datetime.now().weekday()))
    
    if 'main_df' not in st.session_state:
        init_data = {"员工": list(STAFF_DB.keys())}
        for d in days_cn:
            init_data[f"{d}_起"], init_data[f"{d}_止"] = [""]*len(STAFF_DB), [""]*len(STAFF_DB)
        st.session_state.main_df = pd.DataFrame(init_data)

    with st.expander("➕ 快速录入助手", expanded=False):
        c1, c2, c3, c4, c5 = st.columns([2, 2, 2, 2, 1])
        with c1: sel_s = st.selectbox("员工", list(STAFF_DB.keys()))
        with c2: sel_d = st.selectbox("日期", days_cn)
        with c3: in_s = st.selectbox("起", options=TIME_OPTIONS, index=16)
        with c4: in_e = st.selectbox("止", options=TIME_OPTIONS, index=28)
        if st.button("填入", use_container_width=True):
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == sel_s, f"{sel_d}_起"] = in_s
            st.session_state.main_df.loc[st.session_state.main_df['员工'] == sel_s, f"{sel_d}_止"] = in_e
            st.rerun()

    # 同步功能
    cc1, cc2 = st.columns(2)
    if cc1.button("🔄 同步上周", use_container_width=True):
        if "tmpl" in st.session_state: st.session_state.main_df = st.session_state.tmpl.copy(); st.rerun()
    if cc2.button("💾 存为模板", use_container_width=True):
        st.session_state.tmpl = st.session_state.main_df.copy(); st.toast("模板已存")

    # B. 排班表格 (强制撑开高度，避免上下滑动)
    st.write(f"### 排班明细 ({'老板' if st.session_state.role=='owner' else '店长'})")
    col_config = {"员工": st.column_config.TextColumn("", disabled=True, width="small")}
    for d in days_cn:
        col_config[f"{d}_起"] = st.column_config.SelectboxColumn(f"{d} | 起", options=TIME_OPTIONS, width="small")
        col_config[f"{d}_止"] = st.column_config.SelectboxColumn(f"{d} | 止", options=TIME_OPTIONS, width="small")

    # 动态计算高度：行数 * 35px + 表头 40px
    table_height = (len(st.session_state.main_df) + 1) * 35 + 40

    edited_df = st.data_editor(
        st.session_state.main_df, 
        column_config=col_config, 
        use_container_width=True, 
        hide_index=True, 
        height=table_height, # 关键：强制全员显示
        key="vPure"
    )
    st.session_state.main_df = edited_df

    # C. 导出图片预览
    if st.button("✨ 生成工作组排班图 (English)", use_container_width=True):
        export_df = pd.DataFrame({"NAME": list(STAFF_DB.keys())})
        for cn, en in zip(days_cn, days_en):
            combined = []
            for _, row in edited_df.iterrows():
                s, e = row[f"{cn}_起"], row[f"{cn}_止"]
                combined.append(f"{format_time_eng(s)}-{format_time_eng(e)}" if s and e else "-")
            export_df[en] = combined
        st.markdown(f"**SCHEDULE: {selected_date.strftime('%Y/%m/%d')}**")
        st.dataframe(export_df, use_container_width=True, hide_index=True)
        st.info("💡 手机长按或截图上方表格发到群组。")

    # D. 财务汇总 (仅老板)
    if st.session_state.role == "owner":
        st.divider()
        st.header("💰 财务汇总")
        cash_total, eft_total = 0.0, 0.0
        for _, row in edited_df.iterrows():
            name = row["员工"]
            rate, p_type = STAFF_DB.get(name,{}).get("时薪",0), STAFF_DB.get(name,{}).get("类型","cash")
            for d in days_cn:
                _, p = calc_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
                if str(p_type).lower() == "cash": cash_total += p
                else: eft_total += p
        st.metric("Cash 现金准备", f"${round(cash_total, 2)}")
        st.metric("EFT 转账汇总", f"${round(eft_total, 2)}")

else:
    st.error("无法读取配置。")

if st.sidebar.button("退出系统"):
    st.session_state.role = None
    st.rerun()
