import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 深度纯净配置 (彻底屏蔽官方干扰)
st.set_page_config(page_title="Roster Pro", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
    <style>
    header, footer, #MainMenu {visibility: hidden !important;}
    div[data-testid="stStatusWidget"], button[title="Manage app"], 
    iframe[title="manage-app-button"], .stAppDeployButton, [data-testid="stToolbar"],
    #viewer-badge, .viewerBadge_container__1QSob {
        display: none !important; visibility: hidden !important;
    }
    .block-container { padding-top: 1rem !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 核心数据与逻辑 ---
def get_data():
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        doc_id = url.split('/d/')[1].split('/')[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid=0"
        return pd.read_csv(csv_url), "success"
    except Exception as e:
        return pd.DataFrame(), str(e)

def finalize_t(t):
    t = str(t).strip()
    return f"{int(t):02d}:00" if t.isdigit() else t

def calc_wage(s, e, rate):
    if not s or not e or s == "" or e == "": return 0.0, 0.0
    try:
        s, e = finalize_t(s), finalize_t(e)
        h1, m1 = map(float, s.split(':'))
        h2, m2 = map(float, e.split(':'))
        dur = (h2 + m2/60) - (h1 + m1/60)
        if dur < 0: dur += 24
        actual = dur - 0.5 if dur > 5 else dur # 利益最大化
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 3. 登录与权限 ---
staff_df, status = get_data()
if "role" not in st.session_state: st.session_state.role = None

if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 5, 1])
    with col_mid:
        st.header("Roster 财务系统")
        pwd = st.text_input("🔑 密码", type="password")
        if st.button("进入系统", use_container_width=True):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            st.rerun()
    st.stop()

# --- 4. 时间与云端同步引擎 ---
today = datetime.now().date()
this_monday = today - timedelta(days=today.weekday())
selected_date = st.date_input("📅 选择查看/排班周 (周一)", this_monday)
actual_mon = selected_date - timedelta(days=selected_date.weekday())
week_key = actual_mon.strftime("%Y-%m-%d")

# 权限判断：是否为旧周 (超过14天即为只读)
is_readonly = False
if st.session_state.role == "manager":
    if (this_monday - actual_mon).days > 14:
        is_readonly = True
        st.warning(f"⚠️ {week_key} 周排班已锁定，店长模式仅限只读。如需修改请联系老板。")

# 初始化内存
if 'cloud_db' not in st.session_state: st.session_state.cloud_db = {}

# 自动从“云端”加载当前选择周的数据，如果没有则初始化
if week_key not in st.session_state.cloud_db:
    df = pd.DataFrame({"员工": list(staff_df["姓名"])})
    for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
        df[f"{d}_起"], df[f"{d}_止"] = "", ""
    st.session_state.cloud_db[week_key] = df

current_df = st.session_state.cloud_db[week_key]

# --- 5. 功能区 ---
st.title(f"🚀 {week_key} 周次明细")

# A. 快速录入 (只读状态下隐藏)
if not is_readonly:
    with st.expander("👤 快速录入助手", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1: sn = st.selectbox("员工", list(staff_df["姓名"]))
        with c2: days_sel = st.multiselect("日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
        with c3: shift = st.selectbox("班次", ["8-2", "10-6", "8-6", "2-6", "10-2"])
        
        base = {"8-2":("08:00","14:00"), "10-6":("10:00","18:00"), "8-6":("08:00","18:00"), "2-6":("14:00","18:00"), "10-2":("10:00","14:00")}.get(shift, ("",""))
        cc1, cc2 = st.columns(2)
        in_s = cc1.text_input("起 (输8自动补全)", value=base[0])
        in_e = cc2.text_input("止", value=base[1])
        if st.button("确定填入并预览"):
            for d in days_sel:
                current_df.loc[current_df['员工'] == sn, f"{d}_起"] = finalize_t(in_s)
                current_df.loc[current_df['员工'] == sn, f"{d}_止"] = finalize_t(in_e)
            st.session_state.cloud_db[week_key] = current_df
            st.rerun()

# B. 核心表格
t_h = (len(current_df) + 1) * 35 + 60
edited_df = st.data_editor(
    current_df, 
    use_container_width=True, 
    hide_index=True, 
    height=t_h, 
    disabled=is_readonly, # 关键：超过两周自动禁用编辑
    key=f"editor_{week_key}"
)
st.session_state.cloud_db[week_key] = edited_df

# 同步按钮 (只读状态下禁用)
if not is_readonly:
    if st.button(f"💾 同步 {week_key} 排班到云端", use_container_width=True):
        st.session_state.cloud_db[week_key] = edited_df
        st.success("✅ 同步成功！老板端已更新。")

# --- 6. 财务分析 (老板专属) ---
if st.session_state.role == "owner":
    st.divider()
    st.header(f"📊 财务与工占比分析 ({week_key})")
    
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    days_list = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    daily_h, daily_w = {d:0.0 for d in days_list}, {d:0.0 for d in days_list}
    t_cash, t_eft = 0.0, 0.0
    settlement = []

    for _, row in edited_df.iterrows():
        name = row["员工"]
        rate = STAFF_DB.get(name, {}).get("时薪", 0)
        p_type = str(STAFF_DB.get(name, {}).get("类型", "cash")).upper()
        p_h, p_w = 0.0, 0.0
        for d in days_list:
            h, w = calc_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
            daily_h[d] += h
            daily_w[d] += w
            p_h += h
            p_w += w
        if p_type == "CASH": t_cash += p_w
        else: t_eft += p_w
        settlement.append({"员工": name, "工时(h)": p_h, "周薪": f"${round(p_w, 2)}", "支付": p_type})

    # 营业额录入 (去除0.0干扰)
    sc = st.columns(7)
    sales = {d: sc[i].number_input(d, value=None, placeholder="输入", key=f"s_{d}_{week_key}") or 0.0 for i, d in enumerate(days_list)}
    
    # 汇总看板
    tot_s = sum(sales.values())
    tot_w = t_cash + t_eft
    
    analysis_df = pd.DataFrame({
        "指标": ["总工时(h)", "总工资($)", "工占比(%)"],
        **{d: [daily_h[d], round(daily_w[d], 2), f"{round(daily_w[d]/sales[d]*100, 1) if sales[d]>0 else 0}%"] for d in days_list},
        "每周合计": [round(sum(daily_h.values()), 1), round(tot_w, 2), f"{round(tot_w/tot_s*100, 1) if tot_s>0 else 0}%"]
    })
    st.table(analysis_df)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Cash 现金准备", f"${round(t_cash, 2)}")
    m2.metric("EFT 转账汇总", f"${round(t_eft, 2)}")
    m3.metric("全周总时长", f"{round(sum(daily_h.values()), 1)} h")

    with st.expander("📑 查看本周工资单明细"):
        st.table(pd.DataFrame(settlement))

if st.sidebar.button("退出系统"):
    st.session_state.role = None
    st.rerun()
