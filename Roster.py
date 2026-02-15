import streamlit as st
import pandas as pd
import sqlite3
import json
import io
from datetime import datetime, timedelta
import streamlit.components.v1 as components

# --- 1. 深度配置 & 视觉增强系统 (App化核心) ---
st.set_page_config(
    page_title="店铺排班系统", 
    page_icon="📅", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# 注入 CSS 和 JS：隐藏网页特征，优化手机触摸体验
st.markdown("""
    <style>
    /* === 核心：隐藏 Streamlit 原生元素 === */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stToolbar"] {display: none !important;}
    [data-testid="stDecoration"] {display: none !important;}
    [data-testid="stStatusWidget"] {display: none !important;}
    
    /* === 手机端体验优化 === */
    .block-container {
        padding-top: 1rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }
    
    /* 让按钮更像 App 的按钮 */
    div.stButton > button:first-child {
        width: 100%;
        height: 3.5em; 
        font-weight: bold;
        border-radius: 12px; 
        border: none;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }

    /* 调整 Tab 标签页样式 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 15px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 10px 10px 0 0;
        padding: 0 15px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ffffff !important;
        border-top: 3px solid #ff4b4b !important;
    }
    
    /* 预览表格样式 */
    .preview-table th {
        background-color: #f0f2f6 !important;
        color: black !important;
        font-size: 1.2rem !important;
    }
    </style>
""", unsafe_allow_html=True)

# 强力去广告/去按钮脚本
components.html("""
    <script>
        setInterval(function() {
            var buttons = window.parent.document.querySelectorAll('button');
            buttons.forEach(function(btn) {
                if (btn.innerText.includes("Manage app") || btn.title === "Manage app" || btn.getAttribute("data-testid") === "manage-app-button") {
                    btn.remove();
                }
            });
        }, 300); 
    </script>
""", height=0)

# --- 2. SQLite 数据库层 ---
DB_FILE = "roster_visual_fixed.db"

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
        try:
            df = pd.read_json(io.StringIO(row[0]))
            sales = json.loads(row[1])
            return df, sales
        except Exception as e:
            return None, None
    return None, None

# [修复部分 1] 增加了对数据类型的强制转换，防止 AttributeError
def save_week_to_db(week_key, df, sales):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 强制将 df 转换为 DataFrame，防止传入的是 list
    if not isinstance(df, pd.DataFrame):
        try:
            df = pd.DataFrame(df)
        except:
            conn.close()
            return # 数据无法转换，直接跳过

    roster_json = df.to_json(orient='records')
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

# --- 4. 预览逻辑 ---
def simplify_time(t_str):
    if not t_str or t_str == "": return ""
    try:
        h, m = map(int, t_str.split(':'))
        disp_h = h if h <= 12 else h - 12
        if m == 0: return f"{disp_h}"
        else: return f"{disp_h}:{m:02d}"
    except: return ""

def generate_preview_df(df):
    preview_data = []
    days_map = {"周一": "Mon", "周二": "Tue", "周三": "Wed", "周四": "Thu", "周五": "Fri", "周六": "Sat", "周日": "Sun"}
    
    # 防止 df 是 list 类型
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)

    for _, row in df.iterrows():
        row_data = {"Staff": row["员工"]}
        has_shift = False
        for cn_day, en_day in days_map.items():
            s = row.get(f"{cn_day}_起", "")
            e = row.get(f"{cn_day}_止", "")
            if s and e:
                row_data[en_day] = f"{simplify_time(s)}-{simplify_time(e)}"
                has_shift = True
            else:
                row_data[en_day] = "" 
        if has_shift: 
            preview_data.append(row_data)
            
    if not preview_data:
        preview_data = [{"Staff": row["员工"]} for _, row in df.iterrows()]
        
    return pd.DataFrame(preview_data)

# --- 5. 初始模板 ---
def load_fixed_template(staff_list):
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    columns = ["员工"] + [f"{d}_{s}" for d in days for s in ["起", "止"]]
    df = pd.DataFrame(columns=columns)
    df["员工"] = staff_list
    df = df.fillna("")
    return df

# --- 6. 自动保存回调函数 ---
# [修复部分 2] 增加了空值检查和类型转换
def auto_save_roster_callback(wk_key):
    """当排班表发生变化时，自动触发此函数进行保存"""
    # 从 session_state 获取最新的编辑器数据
    # 注意：这里直接取 st.session_state 里的 key 可能还是旧的，稳妥起见我们不做复杂操作
    # 只要触发了，就说明界面更新了，我们从 editor_key 拿数据
    edited_data = st.session_state.get(f"editor_{wk_key}")
    
    if edited_data is None:
        return

    # 强制类型转换，确保它是 DataFrame
    if not isinstance(edited_data, pd.DataFrame):
        edited_data = pd.DataFrame(edited_data)

    # 更新内存中的 current_df
    st.session_state.current_df = edited_data
    # 写入数据库
    save_week_to_db(wk_key, edited_data, st.session_state.current_sales)
    # 弹出提示
    st.toast("⚡ 排班已自动保存", icon="💾")

def auto_save_sales_callback(wk_key, day_key):
    """当营业额发生变化时，自动保存"""
    val = st.session_state[f"s_{day_key}"]
    st.session_state.current_sales[day_key] = val if val is not None else 0.0
    save_week_to_db(wk_key, st.session_state.current_df, st.session_state.current_sales)
    st.toast(f"💰 {day_key} 营业额已保存", icon="✅")

# --- 7. 登录逻辑 ---
staff_df, status = get_staff_data()
if "role" not in st.session_state: st.session_state.role = None
if 'preview_mode' not in st.session_state: st.session_state.preview_mode = False

if st.session_state.role is None:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, col_mid, _ = st.columns([1, 8, 1]) 
    with col_mid:
        st.title("🔐 员工排班系统")
        st.info("请登录以继续")
        pwd = st.text_input("输入密码", type="password")
        if st.button("🚀 登录系统", use_container_width=True):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            else: st.error("密码错误")
            if st.session_state.role: st.rerun()
    st.stop()

# --- 8. 数据加载逻辑 ---
today = datetime.now().date()
this_monday = today - timedelta(days=today.weekday())

if not st.session_state.preview_mode:
    c_date, c_user = st.columns([2, 1])
    with c_date:
        selected_mon = st.date_input("选择排班周", this_monday, label_visibility="collapsed")
    with c_user:
        st.markdown(f"**{'👨‍💼 老板' if st.session_state.role=='owner' else '🧑‍🔧 店长'}**")
    actual_mon = selected_mon - timedelta(days=selected_mon.weekday())
    week_key = actual_mon.strftime("%Y-%m-%d")
else:
    week_key = st.session_state.get('last_week_key', this_monday.strftime("%Y-%m-%d"))

# 数据库读取
db_df, db_sales = load_week_from_db(week_key)

if db_df is not None:
    st.session_state.current_df = db_df
    st.session_state.current_sales = db_sales
else:
    # 新建周初始化
    if week_key == "2026-02-09":
        st.session_state.current_df = load_fixed_template(list(staff_df["姓名"]))
    else:
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        columns = ["员工"] + [f"{d}_{s}" for d in days for s in ["起", "止"]]
        df_init = pd.DataFrame(columns=columns)
        df_init["员工"] = list(staff_df["姓名"])
        df_init = df_init.fillna("")
        st.session_state.current_df = df_init
    st.session_state.current_sales = {d: 0.0 for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]}
    save_week_to_db(week_key, st.session_state.current_df, st.session_state.current_sales)

st.session_state.last_week_key = week_key
is_readonly = (st.session_state.role == "manager" and (this_monday - actual_mon).days > 14)

# --- 9. 主界面逻辑 ---

if st.session_state.preview_mode:
    st.markdown("### 📅 Roster Preview")
    preview_df = generate_preview_df(st.session_state.current_df)
    st.table(preview_df)
    if st.button("⬅️ 返回编辑模式", use_container_width=True):
        st.session_state.preview_mode = False
        st.rerun()

else:
    tab_roster, tab_finance, tab_settings = st.tabs(["📅 排班操作", "💰 财务分析", "⚙️ 设置"])

    # --- Tab 1: 排班核心 ---
    with tab_roster:
        if not is_readonly:
            with st.expander("⚡ 快速排班导入 (点击展开)", expanded=False):
                c1, c2, c3 = st.columns(3)
                with c1: sn = st.selectbox("人员", list(staff_df["姓名"]))
                with c2: days_sel = st.multiselect("日期", ["周一", "周二", "周三", "周四", "周五", "周六", "周日"])
                with c3: shift_b = st.selectbox("模板", ["8-2", "10-6", "8-6", "2-6", "10-2"])
                
                base = {"8-2":("08:00","14:00"), "10-6":("10:00","18:00"), "8-6":("08:00","18:00"), "2-6":("14:00","18:00"), "10-2":("10:00","14:00")}.get(shift_b)
                
                if st.button("应用模板", use_container_width=True):
                    for d in days_sel:
                        st.session_state.current_df.loc[st.session_state.current_df['员工'] == sn, f"{d}_起"] = finalize_t(base[0])
                        st.session_state.current_df.loc[st.session_state.current_df['员工'] == sn, f"{d}_止"] = finalize_t(base[1])
                    save_week_to_db(week_key, st.session_state.current_df, st.session_state.current_sales)
                    st.rerun()

        col_cfg = {d+"_"+s: st.column_config.SelectboxColumn(d+"|"+s, options=TIME_OPTIONS) for d in ["周一", "周二", "周三", "周四", "周五", "周六", "周日"] for s in ["起", "止"]}
        t_h = (len(st.session_state.current_df) + 1) * 35 + 40 

        # === 核心修改：绑定 on_change 回调 ===
        st.data_editor(
            st.session_state.current_df, 
            column_config=col_cfg, 
            use_container_width=True, 
            hide_index=True, 
            height=t_h, 
            disabled=is_readonly, 
            key=f"editor_{week_key}",
            on_change=auto_save_roster_callback, # 绑定回调
            args=(week_key,) # 传递参数
        )

        st.divider()
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            if st.button("📸 生成预览截图", use_container_width=True):
                st.session_state.preview_mode = True
                st.rerun()
        with c_p2:
            if st.button("🔄 刷新表格", use_container_width=True): st.rerun()

    # --- Tab 2: 财务分析 ---
    with tab_finance:
        if st.session_state.role != "owner":
            st.warning("⛔ 仅限管理员查看财务数据")
        else:
            st.subheader(f"财务报表: {week_key}")
            
            # 计算逻辑
            STAFF_DB = staff_df.set_index("姓名").to_dict('index')
            days_list = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            daily_h, daily_w = {d:0.0 for d in days_list}, {d:0.0 for d in days_list}
            t_cash, t_eft = 0.0, 0.0
            settle_list = []

            for _, row in st.session_state.current_df.iterrows():
                name = row["员工"]
                rate = STAFF_DB.get(name, {}).get("时薪", 0)
                p_type = str(STAFF_DB.get(name,{}).get("类型","cash")).upper()
                p_h, p_w = 0.0, 0.0
                for d in days_list:
                    s = row.get(f"{d}_起", "")
                    e = row.get(f"{d}_止", "")
                    h, w = calc_wage(s, e, rate)
                    daily_h[d] += h; daily_w[d] += w; p_h += h; p_w += w
                
                if p_type == "CASH": t_cash += p_w
                else: t_eft += p_w
                disp_h = f"{int(p_h)}" if p_h.is_integer() else f"{round(p_h, 2)}"
                settle_list.append({"员工": name, "工时": disp_h, "工资": f"${round(p_w, 2)}", "方式": p_type})

            st.write("👇 本周营业额 ($) - 修改后自动保存")
            
            sc1 = st.columns(3)
            sc2 = st.columns(4)
            cols = sc1 + sc2
            current_sales = st.session_state.current_sales
            
            # === 核心修改：营业额也绑定自动保存 ===
            for i, d in enumerate(days_list):
                cols[i].number_input(
                    d, 
                    value=current_sales.get(d, 0.0), 
                    key=f"s_{d}", 
                    on_change=auto_save_sales_callback,
                    args=(week_key, d)
                )

            # 最终计算 (从 session state 实时读取)
            calc_sales = st.session_state.current_sales
            tot_s = sum(calc_sales.values())
            tot_w = t_cash + t_eft
            tot_h = sum(daily_h.values())
            
            m1, m2, m3 = st.columns(3)
            m1.metric("总营业额", f"${tot_s:,.0f}")
            m2.metric("总工资", f"${tot_w:,.0f}", delta=f"占比 {round(tot_w/tot_s*100, 1) if tot_s>0 else 0}%", delta_color="inverse")
            m3.metric("总工时", f"{round(tot_h, 1)}h")

            st.write("📊 每日分析")
            analysis_df = pd.DataFrame({
                "Day": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                "Sales": [calc_sales[d] for d in days_list],
                "Wage": [round(daily_w[d], 0) for d in days_list],
                "%": [f"{round(daily_w[d]/calc_sales[d]*100, 0) if calc_sales[d]>0 else 0}%" for d in days_list]
            })
            st.dataframe(analysis_df, use_container_width=True, hide_index=True)

            with st.expander("📑 工资单详情"):
                st.dataframe(pd.DataFrame(settle_list), use_container_width=True, hide_index=True)

    # --- Tab 3: 系统设置 ---
    with tab_settings:
        st.info("当前系统版本：v2.1 Fixed Auto-Save")
        st.write(f"当前用户：{st.session_state.role}")
        
        if st.button("🚪 退出登录", use_container_width=True):
            st.session_state.role = None
            st.rerun()
            
        st.divider()
        st.write("员工名单（来自 Google Sheets）：")
        st.dataframe(staff_df, use_container_width=True)
