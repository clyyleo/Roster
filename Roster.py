import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 基础配置
st.set_page_config(page_title="Roster Pro", layout="wide")

# --- 2. 核心数据连接 (极简版) ---
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

# --- 3. 登录与权限控制 ---
if "role" not in st.session_state:
    st.session_state.role = None

if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.header("Roster 业务系统")
        pwd = st.text_input("🔑 访问密码", type="password")
        if st.button("立即登录", use_container_width=True):
            if pwd == "boss":
                st.session_state.role = "owner"
                st.rerun()
            elif pwd == "roster":
                st.session_state.role = "manager"
                st.rerun()
            else:
                st.error("密码不正确，请重新输入")
    st.stop()

# --- 4. 辅助函数：计算逻辑 (利益最大化：>5h扣0.5h) ---
def format_time_display(t):
    if not t or ":" not in str(t): return ""
    h, m = str(t).split(':')
    return f"{int(h)}" if m == "00" else f"{int(h)}:{m}"

def calc_daily_wage(start_t, end_t, rate):
    if not start_t or not end_t: return 0.0, 0.0
    try:
        h1, m1 = map(float, str(start_t).split(':'))
        h2, m2 = map(float, str(end_t).split(':'))
        duration = (h2 + m2/60) - (h1 + m1/60)
        if duration < 0: duration += 24
        # 超过5小时自动减去0.5h休息
        actual = duration - 0.5 if duration > 5 else duration
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 5. 主界面 ---
if status == "success":
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    TIME_OPTIONS = [""] + [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]

    st.title(f"🚀 Roster 智能排班 ({'老板模式' if st.session_state.role == 'owner' else '店长模式'})")
    
    # 顶部日期与同步
    col_a, col_b = st.columns([2, 3])
    with col_a:
        selected_date = st.date_input("📅 选择本周周一", datetime.now() - timedelta(days=datetime.now().weekday()))
        week_str = f"{selected_date.strftime('%Y/%m/%d')} - {(selected_date+timedelta(days=6)).strftime('%Y/%m/%d')}"
    
    with col_b:
        st.write("")
        c1, c2 = st.columns(2)
        if c1.button("🔄 同步上周排班", use_container_width=True):
            if "last_week_data" in st.session_state:
                st.session_state.main_df = st.session_state.last_week_data.copy()
                st.rerun()
        if c2.button("💾 保存为本周模板", use_container_width=True):
            st.session_state.last_week_data = st.session_state.main_df.copy()
            st.toast("已记录本周排班为模板")

    # 初始化表格
    if 'main_df' not in st.session_state:
        init_data = {"员工": list(STAFF_DB.keys())}
        for d in days:
            init_data[f"{d}_起"], init_data[f"{d}_止"] = [""] * len(STAFF_DB), [""] * len(STAFF_DB)
        st.session_state.main_df = pd.DataFrame(init_data)

    # 排班编辑区
    st.subheader(f"📊 排班明细 ({week_str})")
    col_config = {"员工": st.column_config.TextColumn("员工", disabled=True, width="small")}
    for d in days:
        col_config[f"{d}_起"] = st.column_config.SelectboxColumn(f"{d}(起)", options=TIME_OPTIONS, width="small")
        col_config[f"{d}_止"] = st.column_config.SelectboxColumn(f"{d}(止)", options=TIME_OPTIONS, width="small")

    edited_df = st.data_editor(st.session_state.main_df, column_config=col_config, use_container_width=True, hide_index=True, key="editor_vFinal")
    st.session_state.main_df = edited_df

    # 导出预览
    st.divider()
    if st.button("✨ 生成工作组预览 (简洁合并版)", use_container_width=True):
        export_data = {"员工": list(STAFF_DB.keys())}
        for d in days:
            combined = []
            for _, row in edited_df.iterrows():
                s, e = row[f"{d}_起"], row[f"{d}_止"]
                combined.append(f"{format_time_display(s)}-{format_time_display(e)}" if s and e else "-")
            export_data[d] = combined
        st.markdown(f"### 📋 排班发布: {week_str}")
        st.table(pd.DataFrame(export_data))

    # 6. 财务中心 - 仅老板可见
    if st.session_state.role == "owner":
        st.divider()
        st.header("💰 财务汇总 (店长不可见)")
        cash_total, eft_total, hours_total = 0.0, 0.0, 0.0
        for _, row in edited_df.iterrows():
            name = row["员工"]
            rate = STAFF_DB.get(name, {}).get("时薪", 0)
            p_type = STAFF_DB.get(name, {}).get("类型", "cash")
            for d in days:
                h, p = calc_daily_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
                hours_total += h
                if str(p_type).lower() == "cash": cash_total += p
                else: eft_total += p
        
        f1, f2, f3 = st.columns(3)
        f1.metric("准备现金 (Cash)", f"${round(cash_total, 2)}")
        f2.metric("转账额 (EFT)", f"${round(eft_total, 2)}")
        f3.metric("总工时汇总", f"{round(hours_total, 1)} h")

if st.sidebar.button("退出系统"):
    st.session_state.role = None
    st.rerun()
