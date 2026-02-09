import streamlit as st
import pandas as pd

# 1. 基础配置
st.set_page_config(page_title="Roster", layout="wide")

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

# --- 4. 财务算法 (保留所有自动化计算) ---
def calc_wages(time_str, rate):
    if not time_str or "-" not in time_str: return 0.0, 0.0
    try:
        start, end = time_str.split('-')
        h1, m1 = map(float, start.split(':'))
        h2, m2 = map(float, end.split(':'))
        duration = (h2 + m2/60) - (h1 + m1/60)
        if duration < 0: duration += 24
        # 超过5小时自动减去0.5小时休息
        actual_hours = duration - 0.5 if duration > 5 else duration
        return round(actual_hours, 2), round(actual_hours * rate, 2)
    except: return 0.0, 0.0

# --- 5. 主界面：Deputy 风格排班表 ---
st.title("🚀 Roster 智能排班")

if status == "success":
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    
    # 生成 30 分钟间隔的时间段选项 (例如: 08:00-14:00)
    # 为避免下拉框过长，这里预设一些常用组合，也可通过输入自定义
    TIME_SELECTIONS = [""] 
    times = [f"{h:02d}:{m:02d}" for h in range(6, 23) for m in [0, 30]]
    # 自动生成 08:00-14:00, 11:00-21:00 等常用排班
    for i in range(len(times)):
        for j in range(i + 2, min(i + 21, len(times))): # 限制班次在 1-10 小时内
            TIME_SELECTIONS.append(f"{times[i]}-{times[j]}")

    # 初始化排班数据
    if 'df' not in st.session_state:
        st.session_state.df = pd.DataFrame([ [n]+[""]*7 for n in STAFF_DB.keys() ], 
                                         columns=["员工"]+["周一", "周二", "周三", "周四", "周五", "周六", "周日"])

    st.subheader("🗓️ 本周排班表 (点击红圈格子直接选时间)")
    st.info("💡 提示：点击格子可从下拉菜单选择常用时间，也可直接输入(格式如 09:00-15:00)")
    
    # 配置表格列属性：将周一到周日全部设为下拉列表模式
    column_config = {
        "员工": st.column_config.TextColumn("员工", disabled=True),
    }
    for day in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
        column_config[day] = st.column_config.SelectboxColumn(
            day,
            options=TIME_SELECTIONS,
            width="medium"
        )

    # 渲染 Deputy 风格排班编辑器
    edited_df = st.data_editor(
        st.session_state.df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed"
    )
    
    # 同步修改结果
    st.session_state.df = edited_df

    # --- 6. 财务汇总报告 (保留所有自动化计算) ---
    st.divider()
    st.header("💰 财务对账中心")
    
    cash_total, eft_total, hours_total = 0.0, 0.0, 0.0
    
    for _, row in edited_df.iterrows():
        name = row["员工"]
        rate = STAFF_DB.get(name, {}).get("时薪", 0) # 自动匹配 Sofia 等人的 27.17
        pay_type = STAFF_DB.get(name, {}).get("类型", "cash") # 自动区分 Cash/EFT
        
        for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
            h, p = calc_wages(row[d], rate)
            hours_total += h
            if pay_type.lower() == "cash":
                cash_total += p
            else:
                eft_total += p
    
    col_f1, col_f2, col_f3 = st.columns(3)
    col_f1.metric("预计准备现金 (Cash)", f"${round(cash_total, 2)}")
    col_f2.metric("预计转账总额 (EFT)", f"${round(eft_total, 2)}")
    col_f3.metric("本周总工时", f"{round(hours_total, 1)} 小时")

else:
    st.error("数据连接异常")

if st.sidebar.button("退出系统"):
    st.session_state.role = None
    st.rerun()
