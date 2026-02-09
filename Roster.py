import streamlit as st
import pandas as pd

# 1. 基础配置
st.set_page_config(page_title="Roster", layout="wide")

# --- 2. 核心连接函数 (极简下载版) ---
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

# --- 4. 排班核心逻辑 (财务算法) ---
def calc_wages(time_str, rate):
    if not time_str or "-" not in time_str: return 0.0, 0.0
    try:
        start, end = time_str.split('-')
        h1, m1 = map(float, start.split(':'))
        h2, m2 = map(float, end.split(':'))
        duration = (h2 + m2/60) - (h1 + m1/60)
        if duration < 0: duration += 24 # 处理跨天录入
        
        # 利益最大化：超过5小时自动减去0.5小时休息
        actual_hours = duration - 0.5 if duration > 5 else duration
        return round(actual_hours, 2), round(actual_hours * rate, 2)
    except: return 0.0, 0.0

# --- 5. 主界面展示 ---
st.title("🚀 Roster 排班系统")

if status == "success":
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    
    # 快捷排班录入面板
    st.subheader("📝 快捷录入助手 (30分钟间隔)")
    TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]
    
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1.5, 1.5, 3, 1])
        with c1:
            sel_staff = st.selectbox("员工", list(STAFF_DB.keys()))
        with c2:
            sel_day = st.selectbox("日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
        with c3:
            t_start = st.selectbox("开始时间", options=TIME_OPTIONS, index=16) # 08:00
            t_end = st.selectbox("结束时间", options=TIME_OPTIONS, index=28)   # 14:00
        with c4:
            st.write("操作")
            if st.button("确认暂存", use_container_width=True):
                new_val = f"{t_start}-{t_end}"
                if 'df' not in st.session_state:
                    st.session_state.df = pd.DataFrame([ [n]+[""]*7 for n in STAFF_DB.keys() ], 
                                                     columns=["员工"]+["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
                st.session_state.df.loc[st.session_state.df['员工'] == sel_staff, sel_day] = new_val
                st.toast(f"已暂存 {sel_staff}")

    # 显示与编辑排班表
    if 'df' not in st.session_state:
        st.session_state.df = pd.DataFrame([ [n]+[""]*7 for n in STAFF_DB.keys() ], 
                                         columns=["员工"]+["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
    
    st.subheader("📸 本周排班预览 (可手动微调)")
    edited_df = st.data_editor(st.session_state.df, use_container_width=True)

    # --- 6. 财务汇总报告 (程总专属) ---
    st.divider()
    st.header("💰 财务对账中心")
    
    cash_total = 0.0
    eft_total = 0.0
    hours_total = 0.0
    
    for _, row in edited_df.iterrows():
        name = row["员工"]
        rate = STAFF_DB.get(name, {}).get("时薪", 0)
        pay_type = STAFF_DB.get(name, {}).get("类型", "cash")
        
        for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
            h, p = calc_wages(row[d], rate)
            hours_total += h
            if pay_type.lower() == "cash":
                cash_total += p
            else:
                eft_total += p
    
    col_f1, col_f2, col_f3 = st.columns(3)
    col_f1.metric("总计准备现金 (Cash)", f"${round(cash_total, 2)}")
    col_f2.metric("总计转账额 (EFT)", f"${round(eft_total, 2)}")
    col_f3.metric("本周总工时", f"{round(hours_total, 1)} 小时")

else:
    st.error("连接异常，请检查配置。")

if st.sidebar.button("退出系统"):
    st.session_state.role = None
    st.rerun()
