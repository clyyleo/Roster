import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. 基础配置
st.set_page_config(page_title="Roster", layout="wide")

# 2. 连接 Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# 获取员工配置 (来自 Google Sheets 的 Staff 标签页)
try:
    staff_df = conn.read(worksheet="Staff", ttl=0)
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
except Exception as e:
    st.error("⚠️ 无法读取 Staff 标签页，请检查 Google Sheets 配置")
    STAFF_DB = {}

# 3. 居中登录逻辑 (确保利益安全)
if "role" not in st.session_state:
    st.session_state.role = None

if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.markdown("<h2 style='text-align: center;'>Roster 业务管理系统</h2>", unsafe_allow_html=True)
        user = st.text_input("👤 操作人姓名")
        pwd = st.text_input("🔑 访问密码", type="password")
        if st.button("立即登录", use_container_width=True):
            if pwd == "boss2026": # 老板密码
                st.session_state.role = "owner"
                st.session_state.user_name = user if user else "程亮"
                st.rerun()
            elif pwd == "staff2026": # 店长密码
                st.session_state.role = "manager"
                st.session_state.user_name = user if user else "店长"
                st.rerun()
            else:
                st.error("密码错误")
    st.stop()

# --- 登录成功后的主界面 ---
st.title(f"🚀 Roster - {st.session_state.user_name}")

# 4. 老板管理面板 (编辑员工)
if st.session_state.role == "owner":
    with st.expander("🛠️ 员工信息管理 (编辑时薪、增减员工)"):
        st.info("直接在下方表格修改，点击保存同步至 Google Sheets")
        edited_staff = st.data_editor(staff_df, num_rows="dynamic", key="staff_editor")
        if st.button("保存员工修改"):
            conn.update(worksheet="Staff", data=edited_staff)
            st.success("云端数据库已更新！")
            st.rerun()

# 5. 30分钟下拉排班助手
st.subheader("📝 快捷排班录入")
TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]

with st.container(border=True):
    c1, c2, c3, c4 = st.columns([1.5, 1.5, 2, 1])
    with c1:
        sel_staff = st.selectbox("选择员工", list(STAFF_DB.keys()))
    with c2:
        sel_day = st.selectbox("选择日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
    with c3:
        t_start = st.selectbox("开始时间", options=TIME_OPTIONS, index=16) # 08:00
        t_end = st.selectbox("结束时间", options=TIME_OPTIONS, index=28)   # 14:00
    with c4:
        st.write("操作")
        if st.button("确认录入", use_container_width=True):
            new_val = f"{t_start}-{t_end}"
            if 'df' not in st.session_state:
                st.session_state.df = pd.DataFrame([[n]+[""]*7 for n in STAFF_DB.keys()], columns=["员工"]+["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
            st.session_state.df.loc[st.session_state.df['员工'] == sel_staff, sel_day] = new_val
            st.toast(f"已暂存 {sel_staff} 的排班")

# 6. 数据显示与发布
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame([[n]+[""]*7 for n in STAFF_DB.keys()], columns=["员工"]+["周一", "周二", "周三", "周四", "周五", "周六", "周日"])

st.subheader("📸 本周排班表 (核对无误后截图)")
final_df = st.data_editor(st.session_state.df)

# 7. 财务计算核心 (包含 >5h 扣 0.5h 逻辑)
def calc_stat(time_str, rate):
    if not time_str or "-" not in time_str: return 0.0, 0.0
    try:
        s, e = time_str.split('-')
        h1, m1 = map(float, s.split(':'))
        h2, m2 = map(float, e.split(':'))
        duration = (h2 + m2/60) - (h1 + m1/60)
        if h2 < 7: duration += 12 # 处理 8-2 跨午逻辑
        # 利益最大化：单日超过 5 小时减去 0.5 小时
        actual = duration - 0.5 if duration > 5 else duration
        return actual, round(actual * rate, 2)
    except: return 0.0, 0.0

if st.session_state.role == "owner":
    st.divider()
    st.header("💰 财务监控后台")
    total_h, total_p = 0.0, 0.0
    for _, row in final_df.iterrows():
        name = row["员工"]
        rate = STAFF_DB.get(name, {}).get("时薪", 0)
        for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
            h, p = calc_stat(row[d], rate)
            total_h += h
            total_pay += p
    st.metric("本周预计总工费", f"${round(total_pay, 2)}", delta=f"{total_h} 小时")

if st.sidebar.button("退出系统"):
    st.session_state.role = None
    st.rerun()
