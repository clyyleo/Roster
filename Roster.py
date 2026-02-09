import streamlit as st
import pandas as pd

# 页面基本配置
st.set_page_config(page_title="Roster", layout="wide")

# --- 1. 万能连接逻辑 (零依赖版) ---
def get_data():
    try:
        # 获取 Secrets 里的 URL
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        # 将标准的编辑链接转换为 CSV 下载链接，这是最稳的方法
        csv_url = url.replace('/edit#gid=', '/export?format=csv&gid=')
        if '/edit' in url and 'gid=' not in url:
            csv_url = url.replace('/edit', '/export?format=csv')
        
        df = pd.read_csv(csv_url)
        return df, "success"
    except Exception as e:
        return pd.DataFrame(), str(e)

# 尝试读取数据
staff_df, status = get_data()

# --- 2. 登录逻辑 ---
if "role" not in st.session_state:
    st.session_state.role = None

if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.markdown("<h2 style='text-align: center;'>Roster 业务管理系统</h2>", unsafe_allow_html=True)
        pwd = st.text_input("🔑 访问密码", type="password")
        if st.button("立即登录", use_container_width=True):
            if pwd == "boss2026":
                st.session_state.role = "owner"
                st.rerun()
            else:
                st.error("密码错误")
    st.stop()

# --- 3. 主界面 ---
st.title(f"🚀 Roster - 管理后台")

if status == "success":
    st.success("✅ Google Sheets 数据连接成功！")
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
else:
    st.error(f"❌ 连接失败诊断: {status}")
    st.info("请确保 Google 表格已开启‘知道链接的任何人’可查看。")
    STAFF_DB = {}

# 老板管理面板：直接查看从表格读到的数据
with st.expander("🛠️ 员工信息预览 (当前云端数据)"):
    st.dataframe(staff_df, use_container_width=True)

# 30分钟下拉排班助手
st.subheader("📝 快捷排班录入")
TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]

with st.container(border=True):
    c1, c2, c3 = st.columns([2, 2, 3])
    with c1:
        names = list(STAFF_DB.keys()) if STAFF_DB else ["请先检查表格"]
        sel_staff = st.selectbox("选择员工", names)
    with c2:
        sel_day = st.selectbox("选择日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
    with c3:
        t1 = st.selectbox("开始", options=TIME_OPTIONS, index=16)
        t2 = st.selectbox("结束", options=TIME_OPTIONS, index=28)
        if st.button("确认暂存"):
            st.toast(f"已记录 {sel_staff}")

if st.sidebar.button("退出系统"):
    st.session_state.role = None
    st.rerun()
