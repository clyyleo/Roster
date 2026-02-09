import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 深度纯净模式：物理级屏蔽 Manage app 黑色图标
st.set_page_config(page_title="Roster Pro", layout="wide", initial_sidebar_state="collapsed")
st.html("""
    <style>
    header, footer, #MainMenu {visibility: hidden !important; height: 0 !important;}
    [data-testid="stStatusWidget"], button[title="Manage app"], 
    iframe[title="manage-app-button"], .stAppDeployButton, [data-testid="stToolbar"],
    #viewer-badge, .viewerBadge_container__1QSob {
        display: none !important; visibility: hidden !important;
    }
    .block-container { padding-top: 1rem !important; }
    </style>
""")

# --- 2. 核心算法 ---
def get_data():
    try:
        url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        doc_id = url.split('/d/')[1].split('/')[0]
        csv_url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=csv&gid=0"
        return pd.read_csv(csv_url), "success"
    except Exception as e:
        return pd.DataFrame(), str(e)

TIME_OPTIONS = [f"{h:02d}:{m:02d}" for h in range(24) for m in [0, 30]]

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
        actual = dur - 0.5 if dur > 5 else dur
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 3. 初始全员模板 (已修正 Chhay 拼写并补全排班) ---
def load_fixed_template(staff_list):
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    df = pd.DataFrame({"员工": staff_list})
    for d in days: df[f"{d}_起"], df[f"{d}_止"] = "", ""
    def set_s(name, idxs, s, e):
        for i in idxs:
            df.loc[df['员工'].str.contains(name, case=False, na=False), f"{days[i]}_起"] = s
            df.loc[df['员工'].str.contains(name, case=False, na=False), f"{days[i]}_止"] = e

    # 精准录入 2/9 手写稿规则
    set_s("WANG", [0, 3, 4], "14:00", "18:00")
    set_s("WANG", [1, 2], "08:00", "14:00")
    set_s("WANG", [6], "08:30", "14:00")
    set_s("LAN", [0, 2], "08:00", "14:00")
    set_s("LAN", [4], "10:00", "15:00")
    set_s("LAN", [5], "10:00", "18:00")
    set_s("LAN", [6], "10:00", "17:00")
    set_s("Cindy", [0, 3, 4], "08:00", "14:00")
    set_s("Cindy", [1, 2], "14:00", "18:00")
    set_s("DAHLIA", [5], "08:00", "18:00")
    set_s("MOON", [1], "10:00", "14:00")
    set_s("YUKI", [0, 3], "10:00", "18:00")
    set_s("SUSIE", [4], "12:00", "14:00")
    # 修正：手写稿 Chay -> 系统 Chhay
    set_s("Chhay", [1, 4, 5], "08:00", "18:00")
    set_s("Chhay", [2], "10:00", "18:00")
    set_s("Chhay", [3], "08:00", "14:00")
    set_s("Chhay", [6], "08:30", "17:00")
    return df

# --- 4. 登录、时间与同步 ---
staff_df, status = get_data()
if "role" not in st.session_state: st.session_state.role = None
if 'cloud_db' not in st.session_state: st.session_state.cloud_db = {}

if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 5, 1])
    with col_mid:
        st.header("Roster 业务管理")
        pwd = st.text_input("🔑 密码", type="password")
        if st.button("进入系统", use_container_width=True):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            st.rerun()
    st.stop()

today = datetime.now().date()
this_monday = today - timedelta(days=today.weekday())
selected_mon = st.date_input("📅 选择排班周", this_monday)
actual_mon = selected_mon - timedelta(days=selected_mon.weekday())
week_key = actual_mon.strftime("%Y-%m-%d")

# 强制加载 2/9 那周的初始数据
if week_key not in st.session_state.cloud_db:
    if week_key == "2026-02-09":
        st.session_state.cloud_db[week_key] = load_fixed_template(list(staff_df["姓名"]))
    else:
        df_init = pd.DataFrame({"员工": list(staff_df["姓名"])})
        for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
            df_init[f"{d}_起"], df_init[f"{d}_止"] = "", ""
        st.session_state.cloud_db[week_key] = df_init

is_readonly = False
if st.session_state.role == "manager" and (this_monday - actual_mon).days > 14:
    is_readonly = True
    st.warning("⚠️ 历史排班已锁定。")

current_df = st.session_state.cloud_db[week_key]

# --- 5. 核心展示与财务 ---
st.title(f"🚀 {week_key} 排班看板")

# 排班表格
col_cfg = {d+"_"+s: st.column_config.SelectboxColumn(d+"|"+s, options=TIME_OPTIONS) for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"] for s in ["起", "止"]}
t_h = (len(current_df) + 1) * 35 + 60
edited_df = st.data_editor(current_df, column_config=col_cfg, use_container_width=True, hide_index=True, height=t_h, disabled=is_readonly, key=f"v_{week_key}")
st.session_state.cloud_db[week_key] = edited_df

if not is_readonly and st.button(f"💾 同步 {week_key} 数据"):
    st.session_state.cloud_db[week_key] = edited_df
    st.success("✅ 云端同步成功！")

# 财务分析 (仅限老板)
if st.session_state.role == "owner":
    st.divider()
    st.header(f"💰 财务结算汇总 ({week_key})")
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    days_list = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    daily_h, daily_w = {d:0.0 for d in days_list}, {d:0.0 for d in days_list}
    t_cash, t_eft = 0.0, 0.0
    settle_data = []

    for _, row in edited_df.iterrows():
        name = row["员工"]; rate = STAFF_DB.get(name, {}).get("时薪", 0); p_type = str(STAFF_DB.get(name,{}).get("类型","cash")).upper()
        p_h, p_w = 0.0, 0.0
        for d in days_list:
            h, w = calc_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
            daily_h[d] += h; daily_w[d] += w; p_h += h; p_w += w
        if p_type == "CASH": t_cash += p_w
        else: t_eft += p_w
        settle_data.append({"员工": name, "周工时(h)": p_h, "工资": f"${round(p_w, 2)}", "类型": p_type})

    # 营业额
    sc = st.columns(7)
    sales = {d: sc[i].number_input(d, value=None, placeholder="输入", key=f"s_{d}_{week_key}") or 0.0 for i, d in enumerate(days_list)}
    
    tot_s, tot_w, tot_h = sum(sales.values()), t_cash + t_eft, sum(daily_h.values())
    analysis_df = pd.DataFrame({
        "指标": ["总工时(h)", "总工资($)", "工占比(%)"],
        **{d: [daily_h[d], round(daily_w[d], 2), f"{round(daily_w[d]/sales[d]*100, 1) if sales[d]>0 else 0}%"] for d in days_list},
        "每周合计": [round(tot_h, 1), round(tot_w, 2), f"{round(tot_w/tot_s*100, 1) if tot_s>0 else 0}%"]
    })
    st.table(analysis_df)
    m1, m2, m3 = st.columns(3)
    m1.metric("Cash (现金)", f"${round(t_cash, 2)}")
    m2.metric("EFT (转账)", f"${round(t_eft, 2)}")
    m3.metric("全周总时长", f"{round(tot_h, 1)} h")
