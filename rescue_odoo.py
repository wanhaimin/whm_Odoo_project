import psycopg2
import sys

# 数据库连接配置
# 这里的配置是根据您的 odoo.conf 默认值预设的
DB_CONFIG = {
    'dbname': 'odoo',  # 【注意】这里请填入您在网页端创建的数据库名称
    'user': 'odoo',
    'password': 'odoo',
    'host': '127.0.0.1',
    'port': '5434'     # Docker 映射出来的端口
}

def rescue_action():
    print("="*50)
    print("Odoo 紧急救援工具 - 动作删除助手")
    print("="*50)
    print("这个工具可以直接从数据库底层删除导致系统崩溃的'窗口动作'。")
    print("即使网页打不开，这里也能工作。")
    print("-" * 50)

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        print(f"[成功] 已连接到数据库: {DB_CONFIG['dbname']}")
    except Exception as e:
        print(f"[错误]无法连接数据库: {e}")
        print("请检查 Odoo 是否正在运行 (至少数据库服务需要运行)")
        return

    while True:
        print("\n请输入您刚才修改后导致崩溃的动作名称（比如 '教师'）")
        keyword = input("请输入搜索关键字 (输入 'q' 退出): ").strip()
        
        if keyword.lower() == 'q':
            break
            
        if not keyword:
            continue

        # 搜索数据库
        # 我们同时搜索动作的 名称(name) 和 域名(domain) 和 原始XMLID(xml_id)
        sql = """
            SELECT id, name, res_model, type 
            FROM ir_act_window 
            WHERE name ILIKE %s OR type ILIKE %s
        """
        cur.execute(sql, (f'%{keyword}%', f'%{keyword}%'))
        rows = cur.fetchall()

        if not rows:
            print(f"⚠️  未找到包含 '{keyword}' 的窗口动作。")
            continue

        print(f"\n找到 {len(rows)} 个匹配记录:")
        print("-" * 60)
        print(f"{'ID':<8} | {'名称 (Name)':<20} | {'模型 (Model)':<15}")
        print("-" * 60)
        
        for row in rows:
            print(f"{row[0]:<8} | {row[1]:<20} | {row[2]:<15}")
            
        print("-" * 60)
        
        target_id = input("请输入要【删除】的 ID (不删除请直接回车): ").strip()
        
        if target_id:
            if not target_id.isdigit():
                print("❌ ID 必须是数字！")
                continue
                
            # 二次确认
            confirm = input(f"❗ 警告: 您确定要永久删除 ID 为 {target_id} 的记录吗? (yes/no): ")
            if confirm.lower() == 'yes':
                try:
                    cur.execute("DELETE FROM ir_act_window WHERE id = %s", (target_id,))
                    conn.commit()
                    print(f"✅ 成功: ID {target_id} 已从数据库中移除。")
                    print("➡️  现在请尝试重启 Odoo 服务并刷新网页。")
                except Exception as e:
                    print(f"❌ 删除失败: {e}")
                    conn.rollback()
            else:
                print("已取消操作。")

    cur.close()
    conn.close()
    print("程序已退出。")

if __name__ == "__main__":
    rescue_action()
