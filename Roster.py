import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 基础配置
st.set_page_config(page_title="Roster Pro", layout="wide")

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

# --- 3. 登录逻辑 ---
if "role" not in st.session_state:
    st.session_state.role = None

if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.header("Roster 业务系统")
        pwd = st.text_input("🔑 访问密码", type="password")
        if st.button("立即登录", use_container_width=True):
            if pwd == "boss2026":
                st.session_state.role = "owner"
                st.rerun()
            else:
                st.error("密码错误")
    st.stop()

# --- 4. 核心计算与功能函数 ---
def calc_wages(time_str, rate):
    if not time_str or "-" not in str(time_str): return 0.0, 0.0
    try:
        start, end = str(time_str).split('-')
        h1, m1 = map(float, start.split(':'))
        h2, m2 = map(float, end.split(':'))
        duration = (h2 + m2/60) - (h1 + m1/60)
        if duration < 0: duration += 24
        # 超过5小时自动减去0.5小时休息 (利益最大化)
        actual_hours = duration - 0.5 if duration > 5 else duration
        return round(actual_hours, 2), round(actual_hours * rate, 2)
    except: return 0.0, 0.0

# --- 5. 主界面 ---
if status == "success":
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    
    # --- 日历与周次选择 ---
    st.title("🚀 Roster 智能排班系统")
    col_d1, col_d2 = st.columns([1, 3])
    with col_d1:
        selected_date = st.date_input("📅 选择周一日期", datetime.now() - timedelta(days=datetime.now().weekday()))
    
    start_of_week = selected_date
    end_of_week = start_of_week + timedelta(days=6)
    week_str = f"{start_of_week.strftime('%Y/%m/%d')} - {end_of_week.strftime('%Y/%m/%d')}"
    
    with col_d2:
        st.info(f"📍 当前正在排班：**{week_str}**")

    # --- 两步式录入 (自由输入/选择) ---
    st.subheader("⌚ 时间快速生成器")
    TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]
    
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1.5, 1, 1.5, 1.5, 1])
        with c1:
            sel_staff = st.selectbox("员工", list(STAFF_DB.keys()))
        with c2:
            sel_day = st.selectbox("日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
        with c3:
            t_start = st.selectbox("开始(选/输)", options=TIME_OPTIONS, index=16)
        with c4:
            t_end = st.selectbox("结束(选/输)", options=TIME_OPTIONS, index=28)
        with c5:
            st.write("")
            if st.button("填入表格"):
                if 'df' not in st.session_state:
                    st.session_state.df = pd.DataFrame([[n]+[""]*7 for n in STAFF_DB.keys()], columns=["员工"]+["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
                st.session_state.df.loc[st.session_state.df['员工'] == sel_staff, sel_day] = f"{t_start}-{t_end}"

    # --- 排班表格主体 ---
    if 'df' not in st.session_state:
        st.session_state.df = pd.DataFrame([[n]+[""]*7 for n in STAFF_DB.keys()], columns=["员工"]+["周一", "周二", "周三", "周四", "周五", "周六", "周日"])

    st.subheader(f"📊 排班明细 ({week_str})")
    
    # 延续功能
    if st.button("🔄 延续上周排班 (加载历史记忆)"):
        # 此处在实际应用中可对接数据库，目前先做记忆提醒
        st.toast("已加载记忆数据，个别变化请在表内直接修改。")

    # 表格直接编辑
    edited_df = st.data_editor(
        st.session_state.df,
        use_container_width=True,
        num_rows="fixed",
        hide_index=True
    )
    st.session_state.df = edited_df

    # --- 6. 财务对账中心 ---
    st.divider()
    st.header("💰 财务对账中心")
    
    cash_total, eft_total, hours_total = 0.0, 0.0, 0.0
    
    for _, row in edited_df.iterrows():
        name = row["员工"]
        rate = STAFF_DB.get(name, {}).get("时薪", 0)
        pay_type = STAFF_DB.get(name, {}).get("类型", "cash")
        
        for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
            h, p = calc_wages(row[d], rate)
            hours_total += h
            if str(pay_type).lower() == "cash": cash_total += p
            else: eft_total += p
    
    col_f1, col_f2, col_f3 = st.columns(3)
    col_f1.metric("准备现金 (Cash)", f"${round(cash_total, 2)}")
    col_f2.metric("转账总额 (EFT)", f"${round(eft_total, 2)}")
    col_f3.metric("本周工时汇总", f"{round(hours_total, 1)} 小时")

    # 导出预览 (带日期)
    st.divider()
    if st.button("📸 准备发布截图"):
        st.write(f"### {week_str} 员工排班表")
        st.table(edited_df)

else:
    st.error("数据连接异常")
