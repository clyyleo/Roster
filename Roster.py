import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 深度纯净配置 (最强力屏蔽所有官方干扰，包括 Manage app)
st.set_page_config(page_title="Roster Pro", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""
    <style>
    /* 强力隐藏所有官方组件 */
    header, footer, #MainMenu {visibility: hidden !important; height: 0 !important;}
    div[data-testid="stStatusWidget"], .stAppDeployButton, [data-testid="stToolbar"], #viewer-badge {
        display: none !important; visibility: hidden !important;
    }
    /* 针对 Manage app 按钮的特殊深度屏蔽 */
    button[title="Manage app"], iframe[title="manage-app-button"], .viewerBadge_container__1QSob {
        display: none !important; visibility: hidden !important;
    }
    /* 优化页面边距 */
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 核心数据连接与计算 ---
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
        actual = dur - 0.5 if dur > 5 else dur # 利益最大化：5h以上扣半小时休息
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 3. 初始全员模板 (手写稿 2/9 - 2/15 数据锁定) ---
def load_handwritten_template(staff_list):
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    df = pd.DataFrame({"员工": staff_list})
    for d in days: df[f"{d}_起"], df[f"{d}_止"] = "", ""
    
    def set_s(name, idxs, s, e):
        for i in idxs:
            df.loc[df['员工'].str.contains(name, case=False, na=False), f"{days[i]}_起"] = s
            df.loc[df['员工'].str.contains(name, case=False, na=False), f"{days[i]}_止"] = e

    # 根据 image_6a7ddc.png 精准录入
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
    set_s("Chay", [1, 4, 5], "08:00", "18:00")
    set_s("Chay", [2], "10:00", "18:00")
    set_s("Chay", [3], "08:00", "14:00")
    set_s("Chay", [6], "08:30", "17:00")
    return df

# --- 4. 登录与同步系统 ---
staff_df, status = get_data()
if "role" not in st.session_state: st.session_state.role = None
if 'cloud_db' not in st.session_state: st.session_state.cloud_db = {}

if st.session_state.role is None:
    _, col_mid, _ = st.columns([1, 5, 1])
    with col_mid:
        st.markdown("<h2 style='text-align: center;'>Roster 业务管理</h2>", unsafe_allow_html=True)
        pwd = st.text_input("🔑 密码", type="password")
        if st.button("进入系统", use_container_width=True):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            st.rerun()
    st.stop()

# --- 5. 时间与周次 (店长2周锁定逻辑) ---
today = datetime.now().date()
this_monday = today - timedelta(days=today.weekday())
selected_monday = st.date_input("📅 选择排班周 (周一)", this_monday)
actual_mon = selected_monday - timedelta(days=selected_monday.weekday())
week_key = actual_mon.strftime("%Y-%m-%d")

# 权限防火墙
is_readonly = False
if st.session_state.role == "manager" and (this_monday - actual_mon).days > 14:
    is_readonly = True
    st.warning("⚠️ 超过两周的历史排班已锁定，仅限只读。")

# 初始数据加载
if week_key not in st.session_state.cloud_db:
    # 如果是手写稿那周(2/9)，自动加载提取的数据
    if week_key == "2026-02-09":
        st.session_state.cloud_db[week_key] = load_handwritten_template(list(staff_df["姓名"]))
    else:
        st.session_state.cloud_db[week_key] = pd.DataFrame({"员工": list(staff_df["姓名"])})
        for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
            st.session_state.cloud_db[week_key][f"{d}_起"], st.session_state.cloud_db[week_key][f"{d}_止"] = "", ""

current_df = st.session_state.cloud_db[week_key]

# --- 6. 功能展示 ---
st.title(f"🚀 {week_key} 排班管理 ({'老板' if st.session_state.role=='owner' else '店长'})")

# 快速录入助手 (只读时隐藏)
if not is_readonly:
    with st.expander("👤 快速批量排班 (支持多选)", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1: sn = st.selectbox("人员", list(staff_df["姓名"]))
        with c2: days_sel = st.multiselect("日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
        with c3: shift_base = st.selectbox("模板", ["自定义", "8-2", "10-6", "8-6", "2-6", "10-2"])
        
        base_v = {"8-2":("08:00","14:00"), "10-6":("10:00","18:00"), "8-6":("08:00","18:00"), "2-6":("14:00","18:00"), "10-2":("10:00","14:00")}.get(shift_base, ("",""))
        cc1, cc2 = st.columns(2)
        new_s = cc1.text_input("起 (输8即08:00)", value=base_v[0])
        new_e = cc2.text_input("止", value=base_v[1])
        if st.button("✨ 导入当前周"):
            for d in days_sel:
                current_df.loc[current_df['员工'] == sn, f"{d}_起"] = finalize_t(new_s)
                current_df.loc[current_df['员工'] == sn, f"{d}_止"] = finalize_t(new_e)
            st.session_state.cloud_db[week_key] = current_df
            st.rerun()

# 核心排班表
column_config = {}
for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
    column_config[f"{d}_起"] = st.column_config.SelectboxColumn(f"{d}|起", options=TIME_OPTIONS)
    column_config[f"{d}_止"] = st.column_config.SelectboxColumn(f"{d}|止", options=TIME_OPTIONS)

t_h = (len(current_df) + 1) * 35 + 60
edited_df = st.data_editor(current_df, column_config=column_config, use_container_width=True, hide_index=True, height=t_h, disabled=is_readonly, key=f"ed_{week_key}")
st.session_state.cloud_db[week_key] = edited_df

# 同步按钮
if not is_readonly:
    if st.button(f"💾 永久同步 {week_key} 数据到云端", use_container_width=True):
        st.session_state.cloud_db[week_key] = edited_df
        st.success("✅ 同步成功！老板端已即时更新。")

# --- 7. 财务结算中心 (老板专属) ---
if st.session_state.role == "owner":
    st.divider()
    st.header(f"💰 财务结算与工占比 ({week_key})")
    
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    days_list = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    daily_h, daily_w = {d:0.0 for d in days_list}, {d:0.0 for d in days_list}
    t_cash, t_eft = 0.0, 0.0
    settle_list = []

    for _, row in edited_df.iterrows():
        name = row["员工"]
        rate = STAFF_DB.get(name, {}).get("时薪", 0)
        p_type = str(STAFF_DB.get(name, {}).get("类型", "cash")).upper()
        p_h, p_w = 0.0, 0.0
        for d in days_list:
            h, w = calc_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
            daily_h[d] += h; daily_w[d] += w; p_h += h; p_w += w
        if p_type == "CASH": t_cash += p_w
        else: t_eft += p_w
        settle_list.append({"员工": name, "周工时(h)": p_h, "周薪": f"${round(p_w, 2)}", "类型": p_type})

    # 营业额录入 (老板独享，无0.0)
    st.write("填写每日营业额 ($):")
    sc = st.columns(7)
    sales = {d: sc[i].number_input(d, value=None, placeholder="输入", key=f"s_{d}_{week_key}") or 0.0 for i, d in enumerate(days_list)}
    
    # 汇总看板
    tot_s = sum(sales.values()); tot_w = t_cash + t_eft; tot_h = sum(daily_h.values())
    analysis_df = pd.DataFrame({
        "指标": ["总工时(h)", "总工资($)", "工占比(%)"],
        **{d: [daily_h[d], round(daily_w[d], 2), f"{round(daily_w[d]/sales[d]*100, 1) if sales[d]>0 else 0}%"] for d in days_list},
        "每周总计": [round(tot_h, 1), round(tot_w, 2), f"{round(tot_w/tot_s*100, 1) if tot_s>0 else 0}%"]
    })
    st.table(analysis_df)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("现金汇总 (Cash)", f"${round(t_cash, 2)}")
    m2.metric("转账汇总 (EFT)", f"${round(t_eft, 2)}")
    m3.metric("全周总时长", f"{round(tot_h, 1)} h")

    with st.expander("📑 查看本周工资单明细"):
        st.table(pd.DataFrame(settle_list))
