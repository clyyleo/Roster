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

# --- 3. 登录与权限 (密码: boss2026 / manager888) ---
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
            if st.session_state.role: st.rerun()
            else: st.error("密码错误")
    st.stop()

# --- 4. 计算与转换逻辑 ---
def format_time_eng(t):
    if not t or ":" not in str(t): return ""
    h, m = str(t).split(':')
    return f"{int(h)}" if m == "00" else f"{int(h)}:{m}"

def calc_wage(s, e, rate):
    if not s or not e: return 0.0, 0.0
    try:
        h1, m1 = map(float, str(s).split(':'))
        h2, m2 = map(float, str(e).split(':'))
        dur = (h2 + m2/60) - (h1 + m1/60)
        if dur < 0: dur += 24
        actual = dur - 0.5 if dur > 5 else dur # 利益最大化
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 5. 主界面 ---
if status == "success":
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    days_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    days_en = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    TIME_OPTIONS = [""] + [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]

    st.title(f"🚀 Roster 排班 ({'老板' if st.session_state.role=='owner' else '店长'})")
    
    # 周次选择
    selected_date = st.date_input("📅 选择起始周一", datetime.now() - timedelta(days=datetime.now().weekday()))
    week_str = f"{selected_date.strftime('%Y/%m/%d')} - {(selected_date+timedelta(days=6)).strftime('%Y/%m/%d')}"

    # 初始化数据
    if 'main_df' not in st.session_state:
        init_data = {"员工": list(STAFF_DB.keys())}
        for d in days_cn:
            init_data[f"{d}_起"], init_data[f"{d}_止"] = [""]*len(STAFF_DB), [""]*len(STAFF_DB)
        st.session_state.main_df = pd.DataFrame(init_data)

    # --- A. 顶部快速导入功能 ---
    st.subheader("➕ 快速员工导入 (单独录入)")
    with st.container(border=True):
        c1, c2, c3, c4, c5 = st.columns([1.5, 1.5, 1.5, 1.5, 1])
        with c1: sel_staff = st.selectbox("选择员工", list(STAFF_DB.keys()))
        with c2: sel_day = st.selectbox("选择日期", days_cn)
        with c3: in_s = st.selectbox("开始", options=TIME_OPTIONS, index=16)
        with c4: in_e = st.selectbox("结束", options=TIME_OPTIONS, index=28)
        with c5:
            st.write("")
            if st.button("填入表格"):
                st.session_state.main_df.loc[st.session_state.main_df['员工'] == sel_staff, f"{sel_day}_起"] = in_s
                st.session_state.main_df.loc[st.session_state.main_df['员工'] == sel_staff, f"{sel_day}_止"] = in_e
                st.rerun()

    # 同步与模板
    btn_c1, btn_c2, _ = st.columns([1, 1, 3])
    if btn_c1.button("🔄 同步上周"):
        if "tmpl" in st.session_state: st.session_state.main_df = st.session_state.tmpl.copy(); st.rerun()
    if btn_c2.button("💾 存为模板"):
        st.session_state.tmpl = st.session_state.main_df.copy(); st.toast("模板已存")

    # --- B. 核心排班表格 (视觉分区优化) ---
    st.subheader(f"📊 排班明细 ({week_str})")
    col_config = {"员工": st.column_config.TextColumn("", disabled=True, width="small")}
    for d in days_cn:
        col_config[f"{d}_起"] = st.column_config.SelectboxColumn(f"{d} | Start", options=TIME_OPTIONS, width="small")
        col_config[f"{d}_止"] = st.column_config.SelectboxColumn(f"{d} | End", options=TIME_OPTIONS, width="small")

    edited_df = st.data_editor(st.session_state.main_df, column_config=col_config, use_container_width=True, hide_index=True, key="vFinal")
    st.session_state.main_df = edited_df

    # --- C. 导出图片预览 (英文简洁版) ---
    st.divider()
    if st.button("✨ 生成工作组排班图 (English Preview)", use_container_width=True):
        st.subheader(f"Team Schedule: {selected_date.strftime('%b %d')} - {(selected_date+timedelta(days=6)).strftime('%b %d')}")
        
        # 转换显示格式
        export_df = pd.DataFrame({"NAME": list(STAFF_DB.keys())})
        for cn, en in zip(days_cn, days_en):
            combined = []
            for _, row in edited_df.iterrows():
                s, e = row[f"{cn}_起"], row[f"{cn}_止"]
                combined.append(f"{format_time_eng(s)}-{format_time_eng(e)}" if s and e else "-")
            export_df[en] = combined
        
        # 以简洁表格形式展示，方便手机截图
        st.dataframe(export_df, use_container_width=True, hide_index=True)
        st.info("💡 截图保存上方表格，即可直接发到工作组群！")

    # --- D. 财务汇总 (仅老板) ---
    if st.session_state.role == "owner":
        st.divider()
        st.header("💰 财务汇总 (Owner Only)")
        cash_total, eft_total = 0.0, 0.0
        for _, row in edited_df.iterrows():
            name = row["员工"]
            rate, p_type = STAFF_DB.get(name,{}).get("时薪",0), STAFF_DB.get(name,{}).get("类型","cash")
            for d in days_cn:
                _, p = calc_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
                if str(p_type).lower() == "cash": cash_total += p
                else: eft_total += p
        
        f1, f2 = st.columns(2)
        f1.metric("Cash 现金准备", f"${round(cash_total, 2)}")
        f2.metric("EFT 转账总额", f"${round(eft_total, 2)}")

else:
    st.error("无法读取 Google 表格，请确认链接权限。")

if st.sidebar.button("退出系统"):
    st.session_state.role = None
    st.rerun()
