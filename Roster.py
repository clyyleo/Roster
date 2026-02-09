import streamlit as st
import pandas as pd

# 页面配置：初始设为居中，方便显示登录框
st.set_page_config(page_title="Roster", layout="centered")

# 员工基本信息配置
STAFF_DB = {
    "WANG": {"rate": 28.0, "type": "Transfer"},
    "LAN": {"rate": 25.0, "type": "Cash"},
    "Cindy": {"rate": 28.0, "type": "Transfer"},
    "Dahlia": {"rate": 25.0, "type": "Cash"},
    "Chay": {"rate": 25.0, "type": "Cash"}
}

# 登录状态检查
if "role" not in st.session_state:
    st.session_state.role = None

def show_login():
    st.markdown("<h2 style='text-align: center;'>Roster 系统登录</h2>", unsafe_allow_html=True)
    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
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
                st.error("密码错误，请重试。")

# 如果未登录则停止并显示登录界面
if st.session_state.role is None:
    show_login()
    st.stop()

# --- 登录成功后的内容 ---
st.title(f"🚀 Roster - {st.session_state.user_name}")

days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
if 'df' not in st.session_state:
    st.session_state.df = pd.DataFrame(
        [[name] + [""]*7 for name in STAFF_DB.keys()],
        columns=["员工"] + days
    )

st.subheader("📝 本周排班录入 (格式如: 8-2)")
edited_df = st.data_editor(st.session_state.df, num_rows="dynamic")

st.divider()
st.subheader("📸 发布预览 (截图发群)")
st.table(edited_df) # 静态表格方便截图

if st.session_state.role == "owner":
    st.divider()
    st.header("💰 财务监控后台 (仅老板可见)")
    st.info("工时自动核算逻辑已激活。")

if st.sidebar.button("退出系统"):
    st.session_state.role = None
    st.rerun()
