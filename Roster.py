import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import io

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

# --- 3. 登录逻辑 (双重密码) ---
if "role" not in st.session_state:
    st.session_state.role = None

if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 2, 1])
    with col_mid:
        st.header("Roster 业务系统")
        pwd = st.text_input("🔑 访问密码", type="password")
        if st.button("立即登录", use_container_width=True):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            st.rerun() if st.session_state.role else st.error("密码错误")
    st.stop()

# --- 4. 辅助函数 ---
def format_time_eng(t):
    """转换时间显示: 08:00 -> 8, 09:30 -> 9:30"""
    if not t or ":" not in str(t): return ""
    h, m = str(t).split(':')
    return f"{int(h)}" if m == "00" else f"{int(h)}:{m}"

def calc_wage(s, e, rate):
    """利益最大化算法: >5h 扣 0.5h"""
    if not s or not e: return 0.0, 0.0
    try:
        h1, m1 = map(float, str(s).split(':'))
        h2, m2 = map(float, str(e).split(':'))
        dur = (h2 + m2/60) - (h1 + m1/60)
        if dur < 0: dur += 24
        actual = dur - 0.5 if dur > 5 else dur
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 5. 主界面 ---
if status == "success":
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    days_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    days_en = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    TIME_OPTIONS = [""] + [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]

    st.title(f"🚀 Roster 智能排班 ({'老板' if st.session_state.role=='owner' else '店长'})")
    
    # 顶部日期
    selected_date = st.date_input("📅 选择起始周一", datetime.now() - timedelta(days=datetime.now().weekday()))
    week_str = f"{selected_date.strftime('%Y/%m/%d')} - {(selected_date+timedelta(days=6)).strftime('%Y/%m/%d')}"

    # 初始化/同步功能
    if 'main_df' not in st.session_state:
        init_data = {"员工": list(STAFF_DB.keys())}
        for d in days_cn: init_data[f"{d}_起"], init_data[f"{d}_止"] = [""]*len(STAFF_DB), [""]*len(STAFF_DB)
        st.session_state.main_df = pd.DataFrame(init_data)

    # 快捷按钮
    c1, c2, _ = st.columns([1, 1, 2])
    if c1.button("🔄 同步上周"):
        if "tmpl" in st.session_state: st.session_state.main_df = st.session_state.tmpl.copy(); st.rerun()
    if c2.button("💾 存为模板"):
        st.session_state.tmpl = st.session_state.main_df.copy(); st.toast("模板已存")

    # --- 排班表格 (视觉分区优化) ---
    st.subheader(f"📊 内部录入预览 ({week_str})")
    col_config = {"员工": st.column_config.TextColumn("STAFF", disabled=True, width="small")}
    for d in days_cn:
        # 给起止列加上明显的周几前缀，形成视觉分区
        col_config[f"{d}_起"] = st.column_config.SelectboxColumn(f"{d} | Start", options=TIME_OPTIONS, width="small")
        col_config[f"{d}_止"] = st.column_config.SelectboxColumn(f"{d} | End", options=TIME_OPTIONS, width="small")

    edited_df = st.data_editor(st.session_state.main_df, column_config=col_config, use_container_width=True, hide_index=True, key="vFinal")
    st.session_state.main_df = edited_df

    # --- 6. 导出预览 (全英文 + 简洁格式) ---
    st.divider()
    st.subheader("📸 Team Schedule Preview (English)")
    
    export_df = pd.DataFrame({"NAME": list(STAFF_DB.keys())})
    for cn, en in zip(days_cn, days_en):
        combined = []
        for _, row in edited_df.iterrows():
            s, e = row[f"{cn}_起"], row[f"{cn}_止"]
            combined.append(f"{format_time_eng(s)}-{format_time_eng(e)}" if s and e else "-")
        export_df[en] = combined

    # 显示全英文表格
    st.table(export_df)
    
    # 保存按键逻辑：转换为 CSV 模拟“保存数据”，或者你可以直接长按屏幕截图
    csv = export_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 Download Schedule (Save to phone)",
        data=csv,
        file_name=f"Roster_{selected_date.strftime('%m%d')}.csv",
        mime='text/csv',
        use_container_width=True
    )

    # --- 7. 财务汇总 (仅老板) ---
    if st.session_state.role == "owner":
        st.divider()
        st.header("💰 Financial Center (Owner Only)")
        cash_total, eft_total = 0.0, 0.0
        for _, row in edited_df.iterrows():
            name = row["员工"]
            rate, p_type = STAFF_DB.get(name,{}).get("时薪",0), STAFF_DB.get(name,{}).get("类型","cash")
            for d in days_cn:
                _, p = calc_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
                if str(p_type).lower() == "cash": cash_total += p
                else: eft_total += p
        
        f1, f2 = st.columns(2)
        f1.metric("Cash (Ready for withdrawal)", f"${round(cash_total, 2)}")
        f2.metric("EFT (Bank Transfer)", f"${round(eft_total, 2)}")

else:
    st.error("Connection failed.")
