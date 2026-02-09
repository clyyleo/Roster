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

# --- 4. 核心计算函数 (含 >5h 减 0.5h 逻辑) ---
def calc_wages(time_str, rate):
    if not time_str or "-" not in str(time_str): return 0.0, 0.0
    try:
        start, end = str(time_str).split('-')
        h1, m1 = map(float, start.strip().split(':'))
        h2, m2 = map(float, end.strip().split(':'))
        duration = (h2 + m2/60) - (h1 + m1/60)
        if duration < 0: duration += 24
        # 自动扣减 0.5h 休息
        actual_hours = duration - 0.5 if duration > 5 else duration
        return round(actual_hours, 2), round(actual_hours * rate, 2)
    except: return 0.0, 0.0

# --- 5. 主界面 ---
if status == "success":
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    
    # 日历与周次选择
    st.title("🚀 Roster 智能排班系统")
    col_d1, col_d2 = st.columns([1.5, 3])
    with col_d1:
        selected_date = st.date_input("📅 选择周一日期", datetime.now() - timedelta(days=datetime.now().weekday()))
    
    start_of_week = selected_date
    end_of_week = start_of_week + timedelta(days=6)
    week_str = f"{start_of_week.strftime('%Y/%m/%d')} - {end_of_week.strftime('%Y/%m/%d')}"
    
    with col_d2:
        st.info(f"📍 当前周次：**{week_str}**")

    # 初始化数据
    if 'df' not in st.session_state:
        st.session_state.df = pd.DataFrame([[n]+[""]*7 for n in STAFF_DB.keys()], columns=["员工"]+["周一", "周二", "周三", "周四", "周五", "周六", "周日"])

    # --- 排班表主体 (红圈区域优化) ---
    st.subheader(f"📊 排班明细表 ({week_str})")
    
    # 顶部快捷操作栏
    col_btn1, col_btn2, _ = st.columns([1, 1, 3])
    with col_btn1:
        if st.button("🔄 延续上周记录"):
            st.toast("已尝试加载上周排班数据")
    with col_btn2:
        if st.button("🗑️ 清空全表"):
            st.session_state.df = pd.DataFrame([[n]+[""]*7 for n in STAFF_DB.keys()], columns=["员工"]+["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
            st.rerun()

    # 时间下拉选项 (30分钟步长)
    TIME_VALS = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]
    # 组合成 "08:00-14:00" 这种格式的常用预选项，同时也支持格内直接打字修改
    PRESETS = [""] + [f"{t1}-{t2}" for t1 in ["08:00", "09:00", "11:00", "17:00"] for t2 in ["14:00", "15:00", "21:00", "22:00"]]

    # 配置表格：开启 Selectbox 模式
    column_config = {
        "员工": st.column_config.TextColumn("员工", disabled=True),
    }
    for day in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
        column_config[day] = st.column_config.SelectboxColumn(
            day,
            options=PRESETS, # 提供常用组合
            required=False,
            width="medium"
        )

    # 渲染编辑器
    edited_df = st.data_editor(
        st.session_state.df,
        column_config=column_config,
        use_container_width=True,
        num_rows="fixed",
        hide_index=True,
        key="main_editor"
    )
    st.session_state.df = edited_df

    # --- 6. 财务对账中心 (实时联动) ---
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
    
    c_f1, c_f2, c_f3 = st.columns(3)
    c_f1.metric("准备现金 (Cash)", f"${round(cash_total, 2)}")
    c_f2.metric("转账总额 (EFT)", f"${round(eft_total, 2)}")
    c_f3.metric("汇总工时", f"{round(hours_total, 1)} h")

    # 发布截图区域
    if st.checkbox("🔍 显示发布用截图版"):
        st.markdown(f"### 🥪 排班表: {week_str}")
        st.table(edited_df)

else:
    st.error("无法加载员工数据，请检查 Google Sheets。")
