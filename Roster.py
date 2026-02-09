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

# --- 4. 辅助函数：时间补全与计算 ---
def format_time_input(val):
    """手动输入数字自动补全为 00:00 格式"""
    if not val: return ""
    val = str(val).strip()
    if ":" not in val:
        try:
            h = int(val)
            return f"{h:02d}:00"
        except: return val
    return val

def calc_daily_wage(start_t, end_t, rate):
    """计算工时与工资 (包含 >5h 减 0.5h 逻辑)"""
    if not start_t or not end_t: return 0.0, 0.0
    try:
        # 补全格式
        s = format_time_input(start_t)
        e = format_time_input(end_t)
        h1, m1 = map(float, s.split(':'))
        h2, m2 = map(float, e.split(':'))
        duration = (h2 + m2/60) - (h1 + m1/60)
        if duration < 0: duration += 24 # 跨天处理
        
        # 利益最大化：超过 5h 扣 0.5h
        actual = duration - 0.5 if duration > 5 else duration
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 5. 主界面 ---
if status == "success":
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]] #

    st.title("🚀 Roster 智能排班系统")
    
    # 周次日历
    selected_date = st.date_input("📅 选择周一日期", datetime.now() - timedelta(days=datetime.now().weekday()))
    week_str = f"{selected_date.strftime('%Y/%m/%d')} - {(selected_date+timedelta(days=6)).strftime('%Y/%m/%d')}"

    # --- A. 上方录入条 (保留之前功能) ---
    st.subheader("➕ 快速员工导入")
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1.5, 1, 1.5, 1.5, 1])
        with c1: sel_staff = st.selectbox("员工", list(STAFF_DB.keys()))
        with c2: sel_day = st.selectbox("日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
        with c3: in_start = st.selectbox("开始时间", options=TIME_OPTIONS, index=16)
        with c4: in_end = st.selectbox("结束时间", options=TIME_OPTIONS, index=28)
        with c5:
            st.write("")
            if st.button("导入表格"):
                key = f"{sel_staff}_{sel_day}"
                st.session_state[f"{key}_start"] = in_start
                st.session_state[f"{key}_end"] = in_end

    # --- B. 下方排班表 (分列显示) ---
    st.subheader(f"📊 排班明细 ({week_str})")
    
    # 构造数据结构：每个员工、每天都有“起”“止”两列
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    data = {"员工": list(STAFF_DB.keys())}
    for d in days:
        data[f"{d}_起"] = [st.session_state.get(f"{n}_{d}_start", "") for n in STAFF_DB.keys()]
        data[f"{d}_止"] = [st.session_state.get(f"{n}_{d}_end", "") for n in STAFF_DB.keys()]
    
    df_display = pd.DataFrame(data)

    # 表格配置
    col_config = {"员工": st.column_config.TextColumn("员工", disabled=True, width="small")}
    for d in days:
        col_config[f"{d}_起"] = st.column_config.SelectboxColumn("起", options=TIME_OPTIONS, width="small")
        col_config[f"{d}_止"] = st.column_config.SelectboxColumn("止", options=TIME_OPTIONS, width="small")

    edited_df = st.data_editor(
        df_display,
        column_config=col_config,
        use_container_width=True,
        hide_index=True,
        key="main_roster"
    )

    # --- 6. 财务对账中心 (自动汇总) ---
    st.divider()
    st.header("💰 财务对账中心")
    
    cash_total, eft_total, hours_total = 0.0, 0.0, 0.0
    
    for _, row in edited_df.iterrows():
        name = row["员工"]
        rate = STAFF_DB.get(name, {}).get("时薪", 0) #
        p_type = STAFF_DB.get(name, {}).get("类型", "cash") #
        
        for d in days:
            h, p = calc_daily_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
            hours_total += h
            if str(p_type).lower() == "cash": cash_total += p
            else: eft_total += p
    
    f1, f2, f3 = st.columns(3)
    f1.metric("准备现金 (Cash)", f"${round(cash_total, 2)}")
    f2.metric("转账额 (EFT)", f"${round(eft_total, 2)}")
    f3.metric("总工时", f"{round(hours_total, 1)} h")

else:
    st.error("数据加载失败")
