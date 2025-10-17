import sqlite3

def check_servers_data():
    """servers 테이블 상세 데이터 확인"""
    conn = sqlite3.connect('instance/proxmox_manager.db')
    cursor = conn.cursor()
    
    print("📋 servers 테이블 상세 데이터:")
    print("=" * 60)
    
    cursor.execute("SELECT * FROM servers")
    servers = cursor.fetchall()
    
    for i, server in enumerate(servers, 1):
        print(f"\n🔍 서버 {i}:")
        print(f"  ID: {server[0]}")
        print(f"  이름: {server[1]}")
        print(f"  VMID: {server[2]}")
        print(f"  상태: {server[3]}")
        print(f"  IP: {server[4]}")
        print(f"  역할: {server[5]}")
        print(f"  방화벽: {server[6]}")
        print(f"  OS: {server[7]}")
        print(f"  CPU: {server[8]}")
        print(f"  메모리: {server[9]}")
        print(f"  생성일: {server[10]}")
        print(f"  수정일: {server[11]}")
    
    conn.close()

if __name__ == "__main__":
    check_servers_data() 