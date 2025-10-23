#!/usr/bin/env python3
"""Check current users and their roles in the database"""
import sqlite3

def check_users():
    conn = sqlite3.connect('facecheck.db')
    conn.row_factory = sqlite3.Row
    
    print("\n" + "="*60)
    print("ALL USERS IN DATABASE")
    print("="*60)
    
    users = conn.execute('''
        SELECT user_id, idno, firstname, lastname, role 
        FROM user 
        ORDER BY role, user_id
    ''').fetchall()
    
    print(f"\nTotal users: {len(users)}\n")
    
    for user in users:
        print(f"ID: {user['user_id']:<4} | Username: {user['idno']:<15} | "
              f"Name: {user['firstname']} {user['lastname']:<20} | Role: {user['role']}")
    
    print("\n" + "="*60)
    print("FACULTY USERS (Can access attendance)")
    print("="*60 + "\n")
    
    faculty = conn.execute('''
        SELECT u.user_id, u.idno, u.firstname, u.lastname, f.faculty_id
        FROM user u
        JOIN faculty f ON u.user_id = f.user_id
        ORDER BY u.user_id
    ''').fetchall()
    
    if faculty:
        for f in faculty:
            print(f"✅ Username: {f['idno']:<15} | Name: {f['firstname']} {f['lastname']}")
            print(f"   User ID: {f['user_id']}, Faculty ID: {f['faculty_id']}")
            print()
    else:
        print("❌ No faculty users found!")
    
    conn.close()
    
    print("="*60)
    print("LOGIN WITH ANY FACULTY USERNAME ABOVE")
    print("Default password: password123")
    print("="*60)

if __name__ == '__main__':
    try:
        check_users()
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure facecheck.db exists in the current directory!")

