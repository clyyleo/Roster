import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 页面基本配置
st.set_page_config(page_title="Roster", layout="wide")

# --- 1. 诊断版连接逻辑 ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # 强制打印出正在尝试连接的配置（仅供诊断）
    # 如果这里显示的是空，说明 Secrets 根本没被 Streamlit 读取到
    secrets_status = st.secrets.get("connections", {}).get("gsheets", {}).get("spreadsheet", "未找到URL")
    
    # 尝试读取数据
    staff_df = conn.read(worksheet="Staff", ttl=0)
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    st.success("✅ Google Sheets 连接成功！")
except Exception as e:
    st.error(f"❌ 诊断信息: {str(e)}")
    st.info(f"当前系统读取到的 URL 是: {secrets_status}")
    STAFF_DB = {}

# 初始化 staff_df 以防读取失败
staff_df = pd.DataFrame(columns=["姓名", "时薪", "类型"])

try:
    # 尝试从 Google Sheets 读取
    staff_df = conn.read(worksheet="Staff", ttl=0)
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
except Exception as e:
    st.warning("⚠️ 无法读取 Google Sheets 配置。请检查 Secrets 中的 URL 和表格中的 'Staff' 标签页。")
    STAFF_DB = {}

# --- 2. 居中登录逻辑 ---
if "role" not in st.session_state:
    st.session_state.role = None

if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.markdown("<h2 style='text-align: center;'>Roster 业务管理系统</h2>", unsafe_allow_html=True)
        user = st.text_input("👤 操作人姓名")
        pwd = st.text_input("🔑 访问密码", type="password")
        if st.button("立即登录", use_container_width=True):
            if pwd == "boss2026":
                st.session_state.role = "owner"
                st.session_state.user_name = user if user else "程亮"
                st.rerun()
            elif pwd == "staff2026":
                st.session_state.role = "manager"
                st.session_state.user_name = user if user else "店长"
                st.rerun()
            else:
                st.error("密码错误")
    st.stop()

# --- 3. 登录成功后的主界面 ---
st.title(f"🚀 Roster - {st.session_state.user_name}")

# 老板管理面板
if st.session_state.role == "owner":
    with st.expander("🛠️ 员工信息管理 (编辑时薪、增减员工)"):
        # 即使读取失败，也会显示一个带列名的空表，不会报 NameError
        edited_staff = st.data_editor(staff_df, num_rows="dynamic", key="staff_editor")
        if st.button("保存员工修改"):
            try:
                conn.update(worksheet="Staff", data=edited_staff)
                st.success("云端数据库已更新！")
                st.rerun()
            except:
                st.error("保存失败，请检查 Google Sheets 写入权限。")

# --- 4. 快捷排班录入 ---
st.subheader("📝 快捷排班录入")
TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]

with st.container(border=True):
    c1, c2, c3, c4 = st.columns([1.5, 1.5, 2, 1])
    with c1:
        # 如果 STAFF_DB 为空，提供一个默认列表防止报错
        staff_list = list(STAFF_DB.keys()) if STAFF_DB else ["请先在下方添加员工"]
        sel_staff = st.selectbox("选择员工", staff_list)
    with c2:
        sel_day = st.selectbox("选择日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
    with c3:
        t_start = st.selectbox("开始时间", options=TIME_OPTIONS, index=16) 
        t_end = st.selectbox("结束时间", options=TIME_OPTIONS, index=28)   
    with c4:
        st.write("操作")
        if st.button("确认录入", use_container_width=True):
            if STAFF_DB:
                new_val = f"{t_start}-{t_end}"
                if 'df' not in st.session_state:
                    st.session_state.df = pd.DataFrame([[n]+[""]*7 for n in STAFF_DB.keys()], columns=["员工"]+["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
                st.session_state.df.loc[st.session_state.df['员工'] == sel_staff, sel_day] = new_val
                st.toast(f"已暂存 {sel_staff} 的排班")
            else:
                st.error("请先在下方管理面板添加员工信息。")

# --- 5. 数据显示 ---
if 'df' not in st.session_state:
    initial_rows = [[n]+[""]*7 for n in STAFF_DB.keys()] if STAFF_DB else [["示例员工"]+[""]*7]
    st.session_state.df = pd.DataFrame(initial_rows, columns=["员工"]+["周一", "周二", "周三", "周四", "周五", "周六", "周日"])

st.subheader("📸 本周排班表")
final_df = st.data_editor(st.session_state.df)

if st.sidebar.button("退出系统"):
    st.session_state.role = None
    st.rerun()
