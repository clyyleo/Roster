# --- 4. 全员固定模板识别结果 (根据手写稿 image_6a7ddc.png) ---
def load_template_v1(staff_list):
    temp = {"员工": staff_list}
    days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for d in days:
        temp[f"{d}_起"], temp[f"{d}_止"] = [""]*len(staff_list), [""]*len(staff_list)
    
    df = pd.DataFrame(temp)

    # 定义识别到的排班规则
    roster_rules = [
        # 姓名关键字, 起, 止, 涉及日期(0=周一, 6=周日)
        ("WANG", "14:00", "18:00", [0, 3, 4]), # 2-6
        ("WANG", "08:00", "14:00", [1, 2]),    # 8-2
        ("WANG", "08:30", "14:00", [6]),       # 8:30-2
        ("LAN", "08:00", "14:00", [0, 2]),     # 8-2
        ("LAN", "10:00", "15:00", [4]),        # 10-3
        ("LAN", "10:00", "18:00", [5]),        # 10-6
        ("LAN", "10:00", "17:00", [6]),        # 10-5
        ("Cindy", "08:00", "14:00", [0, 3, 4]),# 8-2
        ("Cindy", "14:00", "18:00", [1, 2]),    # 2-6
        ("DAHLIA", "08:00", "18:00", [5]),     # 8-6
        ("MOON", "10:00", "14:00", [1]),       # 10-2
        ("YUKI", "10:00", "18:00", [0, 3]),    # 10-6
        ("SUSIE", "12:00", "14:00", [4]),      # 12-2
        ("Chay", "08:00", "18:00", [1, 4]),    # 8-6
        ("Chay", "10:00", "18:00", [2]),       # 10-6
        ("Chay", "08:00", "14:00", [3, 5]),    # 8-2
        ("Chay", "08:30", "17:00", [6]),       # 8:30-5
    ]

    for name_key, start, end, day_idx in roster_rules:
        target_days_start = [f"{days[i]}_起" for i in day_idx]
        target_days_end = [f"{days[i]}_止" for i in day_idx]
        df.loc[df['员工'].str.contains(name_key, case=False, na=False), target_days_start] = start
        df.loc[df['员工'].str.contains(name_key, case=False, na=False), target_days_end] = end
    
    return df

# --- 5. 初始化逻辑修正 ---
# 确保每次点击“读取最新云端排班”或重启时都能看到完整人员
if 'main_df' not in st.session_state:
    st.session_state.main_df = load_template_v1(list(STAFF_DB.keys()))
