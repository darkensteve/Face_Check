import os

def delete_database():
    """Delete the database file"""
    db_file = "facecheck.db"
    
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"✅ Deleted: {db_file}")
    else:
        print(f"ℹ️  File not found: {db_file}")

if __name__ == "__main__":
    delete_database()