import streamlit as st
import pandas as pd
import sqlite3
import json
import io
from datetime import datetime, timedelta
import streamlit.components.v1 as components

# --- 1. 基础配置 & CSS美化 (保持移动端体验) ---
st.set_page_config(page_title="Roster Pro", page_icon="📅", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    /* 隐藏不需要的元素 */
    #MainMenu, footer, header {visibility: hidden;}
    [data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"] {display: none !important;}
    
    /* 移动端间距优化 */
    .block-container {padding-top: 0.5rem !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important;}
    
    /* 按钮样式 App化 */
    div.stButton > button:first-child {
        width: 100%; height: 3.2em; font-weight: bold; border-radius: 10px; border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* 关键数据指标卡片 */
    [data-testid="stMetricValue"] {font-size: 1.2rem !important;}
    </style>
""", unsafe_allow_html=True)

# 去广告脚本
components.html("""<script>setInterval(function(){var b=window.parent.document.querySelectorAll('button');b.forEach(function(x){if(x.innerText.includes("Manage app"))x.remove()})},300);</script>""", height=0)

# --- 2. 数据库核心 (员工管理 + 排班数据) ---
DB_FILE = "shop_master.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 1. 排班数据表 (按周存储)
    c.execute('''CREATE TABLE IF NOT EXISTS weekly_data
                 (week_key TEXT PRIMARY KEY, roster_json TEXT, sales_json TEXT, adjustments_json TEXT)''')
    # 2. 员工配置表 (替代 Google Sheets)
    c.execute('''CREATE TABLE IF NOT EXISTS staff_config
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  name TEXT UNIQUE, 
                  rate REAL, 
                  wage_type TEXT, 
                  default_start TEXT, 
                  default_end TEXT,
                  is_active INTEGER DEFAULT 1)''')
    conn.commit()
    conn.close()

# --- 3. 数据读写函数 ---
def get_all_staff():
    """获取所有在职员工"""
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql("SELECT * FROM staff_config WHERE is_active=1", conn)
    conn.close()
    return df

def save_staff(df_edited):
    """保存员工修改"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # 简单处理：全删全增（数据量小，安全）
    # 实际逻辑：仅更新变动。这里为了演示方便，假设老板在 data_editor 里操作
    # 建议：只用于更新，不直接删表。下面是简化逻辑：
    for _, row in df_edited.iterrows():
        c.execute('''INSERT OR REPLACE INTO staff_config (id, name, rate, wage_type, default_start, default_end, is_active)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                     (row.get('id'), row['name'], row['rate'], row['wage_type'], row['default_start'], row['default_end'], 1))
    conn.commit()
    conn.close()

def delete_staff(staff_id):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE staff_config SET is_active=0 WHERE id=?", (staff_id,))
    conn.commit()
    conn.close()

def load_week_data(week_key):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT roster_json, sales_json, adjustments_json FROM weekly_data WHERE week_key=?", (week_key,))
    row = c.fetchone()
    conn.close()
    if row:
        try:
            df = pd.read_json(io.StringIO(row[0])) if row[0] else None
            sales = json.loads(row[1]) if row[1] else {}
            adjs = json.loads(row[2]) if row[2] else {}
            return df, sales, adjs
        except: pass
    return None, {}, {}

def save_week_data(week_key, df, sales, adjs):
    conn = sqlite3.connect(DB_FILE)
    # 强制转换 df
    if not isinstance(df, pd.DataFrame): df = pd.DataFrame(df)
    
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO weekly_data (week_key, roster_json, sales_json, adjustments_json) VALUES (?, ?, ?, ?)",
              (week_key, df.to_json(orient='records'), json.dumps(sales), json.dumps(adjs)))
    conn.commit()
    conn.close()

# --- 4. 业务逻辑计算 (你的核心要求) ---
def parse_time(t_str):
    """把 '08:00' 转为小数 8.0"""
    if not t_str or ":" not in str(t_str): return None
    try:
        h, m = map(int, str(t_str).split(':'))
        return h + m/60.0
    except: return None

def calc_daily_hours(start, end):
    """计算单人单日工时：>5小时自动扣0.5"""
    s, e = parse_time(start), parse_time(end)
    if s is None or e is None: return 0.0
    
    duration = e - s
    if duration < 0: duration += 24 # 跨夜
    
    # === 核心规则 ===
    net_hours = duration - 0.5 if duration > 5 else duration
    return max(0.0, net_hours)

def calculate_stats(df, sales_dict, adj_dict, staff_db):
    """生成全套报表数据"""
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    
    # 结果容器
    report = {
        "daily_hours": {d: 0.0 for d in days}, # 每天总工时
        "daily_wage": {d: 0.0 for d in days},  # 每天总薪资
        "staff_stats": {} # 每个人: {total_hours, total_wage, wage_type}
    }
    
    # 1. 遍历排班表计算工时和薪资
    for _, row in df.iterrows():
        name = row.get("员工")
        if not name: continue
        
        # 获取员工信息
        s_info = staff_db[staff_db['name'] == name].iloc[0] if not staff_db[staff_db['name'] == name].empty else None
        rate = s_info['rate'] if s_info is not None else 0
        w_type = s_info['wage_type'] if s_info is not None else "Cash"
        
        p_total_h = 0.0
        p_total_w = 0.0
        
        for d in days:
            h = calc_daily_hours(row.get(f"{d}_起"), row.get(f"{d}_止"))
            wage = h * rate
            
            report["daily_hours"][d] += h
            report["daily_wage"][d] += wage
            p_total_h += h
            p_total_w += wage
            
        report["staff_stats"][name] = {
            "hours": p_total_h, 
            "wage": p_total_w, 
            "type": w_type,
            "rate": rate
        }

    # 2. 应用“每日工时修正” (老板/店长手动微调)
    for d in days:
        manual_adj = adj_dict.get(d, 0.0)
        report["daily_hours"][d] += manual_adj
        # 注意：手动调整的工时是否加钱？这里默认不加钱，只加统计时长。
        # 如果需要加钱，需要知道按谁的时薪加，比较复杂。通常这只是为了平账。

    # 3. 计算周总计
    total_sales = sum(sales_dict.get(d, 0.0) for d in days)
    total_hours = sum(report["daily_hours"].values())
    total_wage = sum(report["daily_wage"].values())
    
    # 4. 计算衍生指标
    metrics = {
        "total_sales": total_sales,
        "total_hours": total_hours,
        "total_wage": total_wage,
        "avg_hourly_rate": (total_wage / total_hours) if total_hours > 0 else 0.0,
        "labor_percent": (total_wage / total_sales * 100) if total_sales > 0 else 0.0,
        "daily_metrics": []
    }
    
    for d in days:
        sal = sales_dict.get(d, 0.0)
        wag = report["daily_wage"][d]
        hrs = report["daily_hours"][d]
        lp = (wag / sal * 100) if sal > 0 else 0.0
        metrics["daily_metrics"].append({
            "日期": d,
            "营业额": sal,
            "总工时": round(hrs, 2),
            "预估工资": round(wag, 2),
            "人工占比": f"{round(lp, 1)}%"
        })
        
    return metrics, report

# --- 5. 初始化与登录 ---
init_db()
if "role" not in st.session_state: st.session_state.role = None
if "lock_edit" not in st.session_state: st.session_state.lock_edit = True # 默认锁定，防误触

# 登录页
if st.session_state.role is None:
    st.markdown("<br><br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 8, 1])
    with c2:
        st.title("🔐 Roster System")
        pwd = st.text_input("请输入密码", type="password")
        if st.button("登录", use_container_width=True):
            if pwd == "boss2026": st.session_state.role = "owner"
            elif pwd == "manager888": st.session_state.role = "manager"
            elif pwd == "staff": st.session_state.role = "staff" # 仅查看
            else: st.error("密码错误")
            if st.session_state.role: st.rerun()
    st.stop()

# --- 6. 主程序 ---
staff_df = get_all_staff() # 加载最新员工名单
today = datetime.now().date()
this_monday = today - timedelta(days=today.weekday())

# 顶部导航
c_d, c_u = st.columns([2, 1])
with c_d:
    sel_date = st.date_input("选择周 (以周一为准)", this_monday, label_visibility="collapsed")
with c_u:
    st.caption(f"当前用户: {st.session_state.role}")

actual_mon = sel_date - timedelta(days=sel_date.weekday())
week_key = actual_mon.strftime("%Y-%m-%d")

# 权限检查 (店长不能改2周前)
days_diff = (this_monday - actual_mon).days
is_history = days_diff > 14
can_edit = (st.session_state.role == "owner") or (st.session_state.role == "manager" and not is_history)

# 加载数据
df_current, sales_data, adj_data = load_week_data(week_key)

# 如果是新的一周，初始化空表
if df_current is None or df_current.empty:
    if staff_df.empty:
        df_current = pd.DataFrame(columns=["员工"])
    else:
        # 初始列
        cols = ["员工"] + [f"{d}_{s}" for d in ["周一","周二","周三","周四","周五","周六","周日"] for s in ["起", "止"]]
        df_current = pd.DataFrame(columns=cols)
        df_current["员工"] = staff_df["name"].tolist()
        df_current = df_current.fillna("") # 填充空字符串

# 确保 session state 同步
st.session_state.current_df = df_current
st.session_state.sales = sales_data
st.session_state.adjs = adj_data

# === TAB 分页布局 ===
tab1, tab2, tab3 = st.tabs(["📅 排班操作", "📊 报表与财务", "👥 员工管理(老板)"])

# ----------------- TAB 1: 排班操作 -----------------
with tab1:
    # 1. 顶部控制栏
    if can_edit:
        c_lock, c_import = st.columns([1, 2])
        with c_lock:
            # 防误触锁
            lock_icon = "🔒" if st.session_state.lock_edit else "🔓"
            btn_label = "解锁编辑" if st.session_state.lock_edit else "锁定表格"
            if st.button(f"{lock_icon} {btn_label}", use_container_width=True):
                st.session_state.lock_edit = not st.session_state.lock_edit
                st.rerun()
        
        with c_import:
            # 智能导入功能
            with st.expander("⚡ 导入员工常用时间 (可微调)", expanded=False):
                if st.session_state.lock_edit:
                    st.warning("请先解锁表格")
                else:
                    c_i1, c_i2, c_i3 = st.columns(3)
                    target_staff = c_i1.selectbox("选择员工", staff_df["name"].tolist(), key="imp_s")
                    
                    # 获取该员工默认时间
                    s_rec = staff_df[staff_df["name"]==target_staff].iloc[0]
                    d_s = s_rec['default_start'] if s_rec['default_start'] else "09:00"
                    d_e = s_rec['default_end'] if s_rec['default_end'] else "17:00"
                    
                    # 导入前允许修改
                    mod_s = c_i2.text_input("开始", d_s, key="imp_start")
                    mod_e = c_i3.text_input("结束", d_e, key="imp_end")
                    
                    target_days = st.multiselect("应用到哪些天?", ["周一","周二","周三","周四","周五","周六","周日"], default=["周一"])
                    
                    if st.button("确认导入", use_container_width=True):
                        for d in target_days:
                            st.session_state.current_df.loc[st.session_state.current_df['员工']==target_staff, f"{d}_起"] = mod_s
                            st.session_state.current_df.loc[st.session_state.current_df['员工']==target_staff, f"{d}_止"] = mod_e
                        save_week_data(week_key, st.session_state.current_df, st.session_state.sales, st.session_state.adjs)
                        st.toast(f"✅ 已导入 {target_staff}")
                        st.rerun()

    # 2. 排班主表格
    time_opts = [f"{h:02d}:{m:02d}" for h in range(6, 24) for m in [0, 30]] # 6点到24点
    col_cfg = {
        "员工": st.column_config.TextColumn("员工", disabled=True, pinned=True),
    }
    # 批量设置时间选择器
    for d in ["周一","周二","周三","周四","周五","周六","周日"]:
        for s in ["起", "止"]:
            col_cfg[f"{d}_{s}"] = st.column_config.SelectboxColumn(
                f"{d[1]}{s}", # 简写标题：一起, 一止
                options=time_opts, 
                width="small"
            )

    disabled_status = st.session_state.lock_edit or not can_edit
    
    edited_df = st.data_editor(
        st.session_state.current_df,
        column_config=col_cfg,
        use_container_width=True,
        hide_index=True,
        disabled=disabled_status,
        height=(len(staff_df)+2) * 35 + 40,
        key=f"editor_{week_key}"
    )

    # 自动保存逻辑
    if not disabled_status and not edited_df.equals(st.session_state.current_df):
        st.session_state.current_df = edited_df
        save_week_data(week_key, edited_df, st.session_state.sales, st.session_state.adjs)
        st.toast("💾 保存成功")

    # 3. 生成图片模式按钮
    st.divider()
    if st.button("🖼️ 全屏展示 (截图用)", use_container_width=True):
        st.session_state.show_fullscreen = True
        st.rerun()

# ----------------- TAB 2: 报表与财务 -----------------
with tab2:
    if st.session_state.role == "staff":
        st.warning("无权限查看")
    else:
        # 1. 营业额输入 & 工时微调
        st.subheader("📝 每日数据录入")
        cols = st.columns(4) # 分两行显示周一到周日
        cols2 = st.columns(3)
        all_cols = cols + cols2
        days = ["周一","周二","周三","周四","周五","周六","周日"]
        
        has_change = False
        for i, d in enumerate(days):
            with all_cols[i]:
                st.markdown(f"**{d}**")
                # 营业额
                val_s = st.number_input("Sales", value=float(st.session_state.sales.get(d, 0.0)), step=100.0, key=f"s_{d}", label_visibility="collapsed")
                if val_s != st.session_state.sales.get(d, 0.0):
                    st.session_state.sales[d] = val_s
                    has_change = True
                
                # 工时修正 (酌情加减)
                val_a = st.number_input("Adj(h)", value=float(st.session_state.adjs.get(d, 0.0)), step=0.5, key=f"a_{d}", help="手动增减当天总工时")
                if val_a != st.session_state.adjs.get(d, 0.0):
                    st.session_state.adjs[d] = val_a
                    has_change = True
        
        if has_change:
            save_week_data(week_key, st.session_state.current_df, st.session_state.sales, st.session_state.adjs)
            st.rerun()

        st.divider()
        
        # 2. 自动计算报表
        metrics, report = calculate_stats(st.session_state.current_df, st.session_state.sales, st.session_state.adjs, staff_df)
        
        # 核心指标卡片
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("总营业额", f"${metrics['total_sales']:,.2f}")
        k2.metric("总工时", f"{metrics['total_hours']:.2f}h")
        k3.metric("平均人工占比", f"{metrics['labor_percent']:.2f}%")
        k4.metric("平均时薪", f"${metrics['avg_hourly_rate']:.2f}")

        # 每日详情表
        st.markdown("##### 📅 每日经营概况")
        st.dataframe(pd.DataFrame(metrics['daily_metrics']), use_container_width=True, hide_index=True)
        
        # 员工工资单
        st.markdown("##### 💰 员工工资单 (含 >5h 扣休)")
        staff_bill = []
        for name, data in report['staff_stats'].items():
            staff_bill.append({
                "姓名": name,
                "总工时": f"{data['hours']:.2f}",
                "时薪": f"${data['rate']:.2f}",
                "应发工资": f"${data['wage']:.2f}",
                "支付方式": data['type']
            })
        st.dataframe(pd.DataFrame(staff_bill), use_container_width=True, hide_index=True)

# ----------------- TAB 3: 员工管理 (老板专属) -----------------
with tab3:
    if st.session_state.role != "owner":
        st.warning("⛔ 仅限老板访问")
    else:
        st.info("💡 提示：在这里修改员工，排班表下次加载时会自动更新。ID是自动生成的。")
        
        # 将 SQLite 数据转为可编辑 DF
        staff_editable = staff_df.copy()
        
        edited_staff = st.data_editor(
            staff_editable,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "name": "姓名",
                "rate": st.column_config.NumberColumn("时薪", format="$%.2f"),
                "wage_type": st.column_config.SelectboxColumn("类型", options=["Cash", "Transfer"]),
                "default_start": st.column_config.TextColumn("常用开始 (09:00)"),
                "default_end": st.column_config.TextColumn("常用结束 (17:00)"),
                "is_active": st.column_config.CheckboxColumn("在职状态")
            },
            num_rows="dynamic", # 允许老板增加行
            use_container_width=True,
            hide_index=True,
            key="staff_editor"
        )
        
        if st.button("💾 保存员工名单变更", use_container_width=True):
            # 将编辑后的数据保存回 DB
            save_staff(edited_staff)
            st.success("名单已更新！请刷新页面。")
            st.rerun()

# ----------------- 独立全屏展示模式 (Tab之外) -----------------
if st.session_state.get("show_fullscreen"):
    st.markdown("""
        <style>
        .stTabs, .stDateInput {display: none;} /* 隐藏其他控件 */
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown(f"## 📅 排班表: {week_key}")
    # 生成一个非常干净的 HTML 表格用于截图
    
    # 简单的 HTML 渲染逻辑
    html = "<table style='width:100%; border-collapse: collapse; text-align: center; font-family: sans-serif;'>"
    html += "<tr style='background:#f0f0f0; border-bottom:2px solid #333;'><th style='padding:10px;'>员工</th>"
    for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
        html += f"<th>{d}</th>"
    html += "</tr>"
    
    for _, row in st.session_state.current_df.iterrows():
        name = row['员工']
        if not name: continue
        html += f"<tr style='border-bottom:1px solid #ddd;'><td style='font-weight:bold; padding:10px;'>{name}</td>"
        days_map = ["周一","周二","周三","周四","周五","周六","周日"]
        for d in days_map:
            s, e = row.get(f"{d}_起"), row.get(f"{d}_止")
            if s and e:
                html += f"<td style='padding:8px; background:#e8f4ff; border-radius:4px;'>{s}<br><span style='color:#666;'>|</span><br>{e}</td>"
            else:
                html += "<td></td>"
        html += "</tr>"
    html += "</table>"
    
    st.markdown(html, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔙 返回编辑模式", use_container_width=True):
        st.session_state.show_fullscreen = False
        st.rerun()
