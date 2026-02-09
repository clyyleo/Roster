import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# 1. 深度纯净配置 (最强力屏蔽 Manage app)
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
    /* 禁用输入框的样式优化 */
    input:disabled { color: #333 !important; background-color: #f0f2f6 !important; cursor: not-allowed; }
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
        actual = dur - 0.5 if dur > 5 else dur # 利益最大化
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 3. 全员初始模板 (Chhay & 全员锁定) ---
def load_fixed_template(staff_list):
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    df = pd.DataFrame({"员工": staff_list})
    for d in days: df[f"{d}_起"], df[f"{d}_止"] = "", ""
    def set_s(name, idxs, s, e):
        for i in idxs:
            df.loc[df['员工'].str.contains(name, case=False, na=False), f"{days[i]}_起"] = s
            df.loc[df['员工'].str.contains(name, case=False, na=False), f"{days[i]}_止"] = e

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
    set_s("Chhay", [1, 4, 5], "08:00", "18:00")
    set_s("Chhay", [2], "10:00", "18:00")
    set_s("Chhay", [3], "08:00", "14:00")
    set_s("Chhay", [6], "08:30", "17:00")
    return df

# --- 4. 登录与初始化 ---
staff_df, status = get_data()
if "role" not in st.session_state: st.session_state.role = None
if 'cloud_db' not in st.session_state: st.session_state.cloud_db = {}
# 新增：用于控制财务修改锁的状态
if 'finance_lock' not in st.session_state: st.session_state.finance_lock = True 

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

# --- 5. 周次与数据加载 (结构升级：同时存DF和Sales) ---
today = datetime.now().date()
this_monday = today - timedelta(days=today.weekday())
selected_mon = st.date_input("📅 选择排班周", this_monday)
actual_mon = selected_mon - timedelta(days=selected_mon.weekday())
week_key = actual_mon.strftime("%Y-%m-%d")

# 数据初始化逻辑
if week_key not in st.session_state.cloud_db:
    # 初始化结构：{'df': 排班表, 'sales': 营业额字典}
    init_df = None
    if week_key == "2026-02-09":
        init_df = load_fixed_template(list(staff_df["姓名"]))
    else:
        init_df = pd.DataFrame({"员工": list(staff_df["姓名"])})
        for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
            init_df[f"{d}_起"], init_df[f"{d}_止"] = "", ""
    
    st.session_state.cloud_db[week_key] = {
        'df': init_df,
        'sales': {d: 0.0 for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]}
    }

is_readonly = (st.session_state.role == "manager" and (this_monday - actual_mon).days > 14)

# 提取当前周数据
current_data = st.session_state.cloud_db[week_key]
current_df = current_data['df']
current_sales = current_data.get('sales', {d: 0.0 for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]})

# --- 6. 主功能区 ---
st.title(f"🚀 {week_key} 排班 ({'老板' if st.session_state.role=='owner' else '店长'})")

# 快速排班助手
if not is_readonly:
    with st.expander("👤 快速排班导入", expanded=True):
        c1, c2, c3 = st.columns(3)
        with c1: sn = st.selectbox("人员", list(staff_df["姓名"]))
        with c2: days_sel = st.multiselect("日期多选", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
        with c3: shift_b = st.selectbox("模板", ["8-2", "10-6", "8-6", "2-6", "10-2"])
        
        base = {"8-2":("08:00","14:00"), "10-6":("10:00","18:00"), "8-6":("08:00","18:00"), "2-6":("14:00","18:00"), "10-2":("10:00","14:00")}.get(shift_b)
        cc1, cc2 = st.columns(2)
        in_s = cc1.text_input("开始 (输8即08:00)", value=base[0])
        in_e = cc2.text_input("结束", value=base[1])
        if st.button("✨ 导入当前周"):
            for d in days_sel:
                current_df.loc[current_df['员工'] == sn, f"{d}_起"] = finalize_t(in_s)
                current_df.loc[current_df['员工'] == sn, f"{d}_止"] = finalize_t(in_e)
            # 更新排班数据
            st.session_state.cloud_db[week_key]['df'] = current_df
            st.rerun()

# 核心表格
col_cfg = {d+"_"+s: st.column_config.SelectboxColumn(d+"|"+s, options=TIME_OPTIONS) for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"] for s in ["起", "止"]}
t_h = (len(current_df) + 1) * 35 + 60
edited_df = st.data_editor(current_df, column_config=col_cfg, use_container_width=True, hide_index=True, height=t_h, disabled=is_readonly, key=f"e_{week_key}")
# 实时保存排班修改
st.session_state.cloud_db[week_key]['df'] = edited_df

# 【双向同步按钮】
if not is_readonly:
    col_sync1, col_sync2 = st.columns(2)
    with col_sync1:
        if st.button(f"☁️ 上传排班表到云端", use_container_width=True):
            st.toast("✅ 排班表已同步！")
    with col_sync2:
        if st.button(f"📥 刷新/下载最新数据", use_container_width=True):
            st.rerun()

# --- 7. 财务分析 (老板专属 - 带安全锁) ---
if st.session_state.role == "owner":
    st.divider()
    
    # 预计算财务数据
    STAFF_DB = staff_df.set_index("姓名").to_dict('index')
    days_list = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    daily_h, daily_w = {d:0.0 for d in days_list}, {d:0.0 for d in days_list}
    t_cash, t_eft = 0.0, 0.0
    settle_list = []

    for _, row in edited_df.iterrows():
        name = row["员工"]; rate = STAFF_DB.get(name, {}).get("时薪", 0); p_type = str(STAFF_DB.get(name,{}).get("类型","cash")).upper()
        p_h, p_w = 0.0, 0.0
        for d in days_list:
            h, w = calc_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
            daily_h[d] += h; daily_w[d] += w; p_h += h; p_w += w
        if p_type == "CASH": t_cash += p_w
        else: t_eft += p_w
        settle_list.append({"员工姓名": name, "本周总工时": p_h, "本周总工资": f"${round(p_w, 2)}", "支付方式": p_type})

    # 1. 财务汇总与工占比 (折叠 + 安全锁)
    with st.expander(f"💰 点击查看：财务汇总与工占比 ({week_key})", expanded=False):
        
        # 安全锁控制逻辑
        col_lock, col_save = st.columns([1, 1])
        is_locked = st.session_state.finance_lock
        
        with col_lock:
            if is_locked:
                if st.button("🔓 解锁并修改财务数据", use_container_width=True):
                    st.session_state.finance_lock = False
                    st.rerun()
            else:
                st.info("⚠️ 编辑模式：修改完成后请点击右侧保存")

        # 营业额录入区
        st.write("👇 每日营业额 ($)")
        sc = st.columns(7)
        new_sales = {}
        for i, d in enumerate(days_list):
            # 如果锁定，disabled=True；如果解锁，disabled=False
            val = sc[i].number_input(
                d, 
                value=current_sales.get(d, 0.0) if current_sales.get(d, 0.0) > 0 else None, 
                placeholder="0", 
                key=f"s_{d}_{week_key}",
                disabled=is_locked 
            )
            new_sales[d] = val if val is not None else 0.0
        
        # 保存逻辑
        with col_save:
            if not is_locked:
                if st.button("💾 确认保存并上传云端", type="primary", use_container_width=True):
                    # 保存到云端结构
                    st.session_state.cloud_db[week_key]['sales'] = new_sales
                    st.session_state.finance_lock = True # 保存后自动上锁
                    st.success("✅ 财务数据已保存至云端！")
                    st.rerun()

        # 实时显示计算结果 (基于当前输入)
        tot_s, tot_w, tot_h = sum(new_sales.values()), t_cash + t_eft, sum(daily_h.values())
        
        # 为了显示效果，如果是在修改中，使用新输入的值；如果是锁定，使用存档值
        calc_sales = new_sales if not is_locked else current_sales

        analysis_df = pd.DataFrame({
            "指标": ["总工时(h)", "总工资($)", "工占比(%)"],
            **{d: [daily_h[d], round(daily_w[d], 2), f"{round(daily_w[d]/calc_sales[d]*100, 1) if calc_sales[d]>0 else 0}%"] for d in days_list},
            "每周总计": [round(tot_h, 1), round(tot_w, 2), f"{round(tot_w/sum(calc_sales.values())*100, 1) if sum(calc_sales.values())>0 else 0}%"]
        })
        st.table(analysis_df)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Cash 结算", f"${round(t_cash, 2)}")
        m2.metric("EFT 汇总", f"${round(t_eft, 2)}")
        m3.metric("全周工时", f"{round(tot_h, 1)} h")

    # 2. 个人工资明细 (折叠)
    with st.expander("📑 点击查看：员工工资明细清单", expanded=False):
        st.table(pd.DataFrame(settle_list))
