import streamlit as st
import pandas as pd
import sqlite3
import json
from datetime import datetime, timedelta

# 1. 深度纯净配置
st.set_page_config(page_title="Roster Pro", layout="wide", initial_sidebar_state="collapsed")
st.html("""
    <style>
    header, footer, #MainMenu {visibility: hidden !important; height: 0 !important;}
    [data-testid="stStatusWidget"], button[title="Manage app"], 
    iframe[title="manage-app-button"], .stAppDeployButton, [data-testid="stToolbar"],
    #viewer-badge, .viewerBadge_container__1QSob, div[class*="viewerBadge"] {
        display: none !important; visibility: hidden !important; opacity: 0 !important; height: 0 !important;
    }
    .block-container { padding-top: 1rem !important; }
    
    /* 预览模式下的特殊样式：大字体，紧凑 */
    .preview-table { font-family: sans-serif; }
    </style>
""")

# --- 2. SQLite 数据库层 ---
DB_FILE = "roster_screenshot.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS weekly_data
                 (week_key TEXT PRIMARY KEY, roster_json TEXT, sales_json TEXT)''')
    conn.commit()
    conn.close()

def load_week_from_db(week_key):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT roster_json, sales_json FROM weekly_data WHERE week_key=?", (week_key,))
    row = c.fetchone()
    conn.close()
    if row:
        return pd.read_json(row[0]), json.loads(row[1])
    return None, None

def save_week_to_db(week_key, df, sales):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    roster_json = df.to_json()
    sales_json = json.dumps(sales)
    c.execute("INSERT OR REPLACE INTO weekly_data (week_key, roster_json, sales_json) VALUES (?, ?, ?)",
              (week_key, roster_json, sales_json))
    conn.commit()
    conn.close()

init_db()

# --- 3. 核心算法 ---
@st.cache_data(ttl=600)
def get_staff_data():
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
    if not s or not e: return 0.0, 0.0
    try:
        s, e = finalize_t(s), finalize_t(e)
        h1, m1 = map(float, s.split(':'))
        h2, m2 = map(float, e.split(':'))
        dur = (h2 + m2/60) - (h1 + m1/60)
        if dur < 0: dur += 24
        actual = dur - 0.5 if dur > 5 else dur
        return round(actual, 2), round(actual * rate, 2)
    except: return 0.0, 0.0

# --- 4. 辅助功能：生成简易英文排班表 ---
def simplify_time(t_str):
    """将 08:00 转换为 8，将 14:00 转换为 2"""
    if not t_str or t_str == "": return ""
    try:
        h, m = map(int, t_str.split(':'))
        # 转换为12小时制逻辑 (8->8, 14->2, 18->6)
        disp_h = h if h <= 12 else h - 12
        # 如果是整点，不显示分钟
        if m == 0:
            return f"{disp_h}"
        else:
            return f"{disp_h}:{m:02d}"
    except:
        return ""

def generate_preview_df(df):
    """生成全英文、简易格式的预览表"""
    preview_data = []
    days_map = {
        "周一": "Mon", "周二": "Tue", "周三": "Wed", "周四": "Thu", 
        "周五": "Fri", "周六": "Sat", "周日": "Sun"
    }
    
    for _, row in df.iterrows():
        row_data = {"Staff": row["员工"]}
        for cn_day, en_day in days_map.items():
            s = row[f"{cn_day}_起"]
            e = row[f"{cn_day}_止"]
            if s and e:
                # 生成如 "8-2" 的格式
                row_data[en_day] = f"{simplify_time(s)}-{simplify_time(e)}"
            else:
                row_data[en_day] = "-"
        preview_data.append(row_data)
    
    return pd.DataFrame(preview_data)

# --- 5. 初始模板 ---
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

# --- 6. 登录 ---
staff_df, status = get_staff_data()
if "role" not in st.session_state: st.session_state.role = None
if 'preview_mode' not in st.session_state: st.session_state.preview_mode = False

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

# --- 7. 数据加载 ---
today = datetime.now().date()
this_monday = today - timedelta(days=today.weekday())
selected_mon = st.date_input("📅 选择排班周", this_monday)
actual_mon = selected_mon - timedelta(days=selected_mon.weekday())
week_key = actual_mon.strftime("%Y-%m-%d")

db_df, db_sales = load_week_from_db(week_key)

if db_df is not None:
    st.session_state.current_df = db_df
    st.session_state.current_sales = db_sales
else:
    if week_key == "2026-02-09":
        st.session_state.current_df = load_fixed_template(list(staff_df["姓名"]))
    else:
        df_init = pd.DataFrame({"员工": list(staff_df["姓名"])})
        for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]:
            df_init[f"{d}_起"], df_init[f"{d}_止"] = "", ""
        st.session_state.current_df = df_init
    st.session_state.current_sales = {d: 0.0 for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]}
    save_week_to_db(week_key, st.session_state.current_df, st.session_state.current_sales)

is_readonly = (st.session_state.role == "manager" and (this_monday - actual_mon).days > 14)

# --- 8. 主界面 ---
st.title(f"🚀 {week_key} 排班 ({'老板' if st.session_state.role=='owner' else '店长'})")

# === 截图预览模式 ===
if st.session_state.preview_mode:
    st.markdown("### 📱 截图预览模式 (Landscape View)")
    st.info("💡 请将手机横屏，截图后点击下方按钮返回编辑。")
    
    # 生成简易表
    preview_df = generate_preview_df(st.session_state.current_df)
    
    # 使用静态 Table 展示，更适合截图，无滚动条干扰
    st.table(preview_df)
    
    if st.button("⬅️ 退出预览，返回编辑", use_container_width=True):
        st.session_state.preview_mode = False
        st.rerun()

else:
    # === 正常编辑模式 ===
    
    # 快速排班
    if not is_readonly:
        with st.expander("👤 快速排班导入", expanded=True):
            c1, c2, c3 = st.columns(3)
            with c1: sn = st.selectbox("人员", list(staff_df["姓名"]))
            with c2: days_sel = st.multiselect("日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
            with c3: shift_b = st.selectbox("模板", ["8-2", "10-6", "8-6", "2-6", "10-2"])
            base = {"8-2":("08:00","14:00"), "10-6":("10:00","18:00"), "8-6":("08:00","18:00"), "2-6":("14:00","18:00"), "10-2":("10:00","14:00")}.get(shift_b)
            cc1, cc2 = st.columns(2)
            in_s = cc1.text_input("开始", value=base[0])
            in_e = cc2.text_input("结束", value=base[1])
            
            if st.button("✨ 导入 (自动保存)", use_container_width=True):
                for d in days_sel:
                    st.session_state.current_df.loc[st.session_state.current_df['员工'] == sn, f"{d}_起"] = finalize_t(in_s)
                    st.session_state.current_df.loc[st.session_state.current_df['员工'] == sn, f"{d}_止"] = finalize_t(in_e)
                save_week_to_db(week_key, st.session_state.current_df, st.session_state.current_sales)
                st.rerun()

    # 核心表格
    col_cfg = {d+"_"+s: st.column_config.SelectboxColumn(d+"|"+s, options=TIME_OPTIONS) for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"] for s in ["起", "止"]}
    t_h = (len(st.session_state.current_df) + 1) * 35 + 60

    edited_df = st.data_editor(
        st.session_state.current_df, 
        column_config=col_cfg, 
        use_container_width=True, 
        hide_index=True, 
        height=t_h, 
        disabled=is_readonly, 
        key=f"editor_{week_key}"
    )

    if not edited_df.equals(st.session_state.current_df):
        st.session_state.current_df = edited_df
        save_week_to_db(week_key, edited_df, st.session_state.current_sales)
        st.toast("✅ 已自动保存", icon="💾")

    # 底部按钮区
    if not is_readonly:
        c1, c2 = st.columns(2)
        with c1:
            # 新增的预览按钮
            if st.button("📱 生成截图预览 (Preview)", use_container_width=True):
                st.session_state.preview_mode = True
                st.rerun()
        with c2:
            if st.button("📥 刷新页面"): st.rerun()

    # --- 9. 财务分析 (老板专属) ---
    if st.session_state.role == "owner":
        st.divider()
        STAFF_DB = staff_df.set_index("姓名").to_dict('index')
        days_list = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        daily_h, daily_w = {d:0.0 for d in days_list}, {d:0.0 for d in days_list}
        t_cash, t_eft = 0.0, 0.0
        settle_list = []

        for _, row in st.session_state.current_df.iterrows():
            name = row["员工"]; rate = STAFF_DB.get(name, {}).get("时薪", 0); p_type = str(STAFF_DB.get(name,{}).get("类型","cash")).upper()
            p_h, p_w = 0.0, 0.0
            for d in days_list:
                h, w = calc_wage(row[f"{d}_起"], row[f"{d}_止"], rate)
                daily_h[d] += h; daily_w[d] += w; p_h += h; p_w += w
            if p_type == "CASH": t_cash += p_w
            else: t_eft += p_w
            settle_list.append({"员工姓名": name, "本周总工时": p_h, "本周总工资": f"${round(p_w, 2)}", "支付方式": p_type})

        with st.expander(f"💰 财务汇总与工占比 ({week_key})", expanded=False):
            col_lock, col_save = st.columns([1, 1])
            if 'finance_lock' not in st.session_state: st.session_state.finance_lock = True
            
            with col_lock:
                if st.session_state.finance_lock:
                    if st.button("🔓 解锁修改"): st.session_state.finance_lock = False; st.rerun()
                else:
                    st.info("编辑模式 - 自动保存")

            st.write("👇 每日营业额 ($)")
            sc = st.columns(7)
            new_sales = {}
            current_sales = st.session_state.current_sales
            sales_changed = False
            for i, d in enumerate(days_list):
                val = sc[i].number_input(d, value=current_sales.get(d, 0.0) if current_sales.get(d, 0.0)>0 else None, placeholder="0", key=f"s_{d}", disabled=st.session_state.finance_lock)
                safe_val = val if val is not None else 0.0
                new_sales[d] = safe_val
                if safe_val != current_sales.get(d, 0.0): sales_changed = True
            
            if not st.session_state.finance_lock and sales_changed:
                st.session_state.current_sales = new_sales
                save_week_to_db(week_key, st.session_state.current_df, new_sales)
                st.toast("财务数据已保存")

            with col_save:
                if not st.session_state.finance_lock:
                    if st.button("🔒 锁定并完成"): st.session_state.finance_lock = True; st.rerun()

            calc_sales = new_sales if not st.session_state.finance_lock else st.session_state.current_sales
            tot_s, tot_w, tot_h = sum(calc_sales.values()), t_cash + t_eft, sum(daily_h.values())
            
            analysis_df = pd.DataFrame({
                "指标": ["总工时(h)", "总工资($)", "工占比(%)"],
                **{d: [daily_h[d], round(daily_w[d], 2), f"{round(daily_w[d]/calc_sales[d]*100, 1) if calc_sales[d]>0 else 0}%"] for d in days_list},
                "每周总计": [round(tot_h, 1), round(tot_w, 2), f"{round(tot_w/tot_s*100, 1) if tot_s>0 else 0}%"]
            })
            st.table(analysis_df)
            m1, m2, m3 = st.columns(3)
            m1.metric("Cash", f"${round(t_cash, 2)}")
            m2.metric("EFT", f"${round(t_eft, 2)}")
            m3.metric("工时", f"{round(tot_h, 1)}h")

        with st.expander("📑 员工工资明细清单", expanded=False):
            st.table(pd.DataFrame(settle_list))
