import streamlit as st
import pandas as pd

# 页面配置
st.set_page_config(page_title="Roster", layout="wide")

# --- 1. 终极连接逻辑 (极简版) ---
def get_data_ultimate():
    try:
        # 直接从 Secrets 获取完整 URL
        raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        
        # 强制转换 URL 格式为 CSV 下载格式
        # 这种方式不依赖任何插件，只要表格开启了“知道链接的人可见”就必通
        doc_id = raw_url.split('/d/')[1].split('/')[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid=0"
        
        df = pd.read_csv(csv_url)
        return df, "success"
    except Exception as e:
        return pd.DataFrame(), str(e)

# 尝试读取
staff_df, status = get_data_ultimate()

# --- 2. 登录界面 ---
if "role" not in st.session_state:
    st.session_state.role = None

if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.header("Roster 管理后台")
        pwd = st.text_input("🔑 访问密码", type="password")
        if st.button("立即登录"):
            if pwd == "boss2026":
                st.session_state.role = "owner"
                st.rerun()
            else:
                st.error("密码错误")
    st.stop()

# --- 3. 成功登录后的展示 ---
st.title("🚀 Roster 系统")

if status == "success":
    st.success(f"✅ 成功连接！已加载 {len(staff_df)} 位员工数据。")
    # 显示员工列表，核对是否包含 Sofia (27.17) 等人
    st.dataframe(staff_df, use_container_width=True)
else:
    st.error(f"❌ 依然连接失败: {status}")
    st.info("请核对 Secrets 里的 URL 是否包含 /d/ 和一串长 ID")

# 快捷排班区域
st.subheader("📝 快捷录入助手")
names = staff_df["姓名"].tolist() if not staff_df.empty else ["等待数据..."]
sel_name = st.selectbox("选择员工", names)
st.write(f"当前选中: {sel_name}")
