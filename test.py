import sqlite3

conn = sqlite3.connect('csiams.dev.sqlite')
cur = conn.cursor()

# Update PIN to 5 digits
cur.execute("""
UPDATE users 
SET pinCode = '12345'
WHERE cardNo = '3663674'
""")

conn.commit()
print("✓ Updated PIN to: 12345")

# Verify
cur.execute("SELECT name, cardNo, pinCode FROM users WHERE cardNo = ?", ('3663674',))
result = cur.fetchone()
if result:
    print(f"\n✓ Verified:")
    print(f"  Name: {result[0]}")
    print(f"  Card: {result[1]}")
    print(f"  PIN: {result[2]} ({len(result[2])} digits)")

conn.close()