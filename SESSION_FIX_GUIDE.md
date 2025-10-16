# 🔧 Session Error Fix Guide

## Error: "API Error: 401 - Unauthorized"

This error means your login session isn't being recognized by the API.

---

## ✅ **Quick Fixes (Try These First)**

### **Fix 1: Logout and Login Again** ⭐ MOST COMMON
1. Click "Logout" button
2. Close browser completely
3. Open browser again
4. Login as a **FACULTY** user
5. Go to attendance page
6. Try starting camera again

### **Fix 2: Clear Browser Cache/Cookies**
1. Press `Ctrl + Shift + Delete`
2. Select "Cookies and other site data"
3. Click "Clear data"
4. Login again as faculty

### **Fix 3: Use Correct Faculty Account**
Login with one of these faculty accounts:
- **FAC001** (Jane Smith)
- **1** (Jewel Gesim)
- **123123** (Ninzo Ocliasa)
- **987654321** (Dennis Durano)
- **206317741** (Franz Caminade)
- **332638547** (Heubert Ferolino)

Default password is usually: `password123`

### **Fix 4: Try Different Browser**
- If using Chrome, try Firefox or Edge
- Private/Incognito window sometimes works
- Check if cookies are enabled

---

## 🔍 **Why This Happens**

### **Common Causes:**
1. **Session Expired** - You've been logged in too long
2. **Cookie Blocked** - Browser blocking session cookies
3. **Wrong Role** - Logged in as student/admin instead of faculty
4. **Multiple Tabs** - Session conflict from multiple tabs
5. **Browser Cache** - Old session data cached

---

## 🛠️ **Technical Fixes (Advanced)**

### **If Quick Fixes Don't Work:**

1. **Check Browser Console:**
   - Press `F12`
   - Look at Console tab
   - See if there are any errors

2. **Check Network Tab:**
   - Press `F12`
   - Click "Network" tab
   - Look for `/api/attendance/detect` request
   - Check if cookies are being sent

3. **Restart Flask Application:**
   ```bash
   # Stop the app (Ctrl+C in terminal)
   # Start it again
   python start_app.py
   ```

4. **Check Terminal Logs:**
   Look for these debug messages:
   ```
   Session contents: {...}
   Session has user_id: True/False
   Session role: faculty/admin/student
   ```

---

## ⚡ **Step-by-Step Solution**

### **Complete Reset Procedure:**

1. **Stop the Flask App**
   - Go to terminal where app is running
   - Press `Ctrl + C`

2. **Clear Your Browser**
   - Close ALL browser windows
   - Clear cache and cookies
   - Restart browser

3. **Start App Fresh**
   ```bash
   python start_app.py
   ```

4. **Login Fresh**
   - Go to `http://localhost:5000`
   - Login with faculty account (e.g., FAC001)
   - Password: `password123` (or your set password)

5. **Test Attendance**
   - Go to "Take Attendance" page
   - Click "Start Camera"
   - Should work now! ✅

---

## 📋 **Verification Checklist**

Before using attendance:
- [ ] Logged in as FACULTY user (not student/admin)
- [ ] Can see dashboard properly
- [ ] Session not expired (logged in recently)
- [ ] Only one browser tab open
- [ ] Cookies enabled in browser
- [ ] Using supported browser (Chrome/Firefox/Edge)

---

## 🚨 **Still Not Working?**

### **Check These:**

1. **Are you definitely logged in as faculty?**
   ```
   - Look at top right corner
   - Should show faculty name
   - Role should be "Faculty"
   ```

2. **Is Flask app running?**
   ```
   - Check terminal for errors
   - Should see "Running on http://127.0.0.1:5000"
   ```

3. **Database has faculty users?**
   ```bash
   python test_session.py
   # Shows all faculty users
   ```

4. **Check session config in app.py:**
   ```python
   SESSION_COOKIE_SECURE=False  # Should be False for localhost
   SESSION_COOKIE_HTTPONLY=True
   SESSION_COOKIE_SAMESITE='Lax'
   ```

---

## 💡 **Prevention Tips**

To avoid this error in future:

1. **Don't stay logged in too long** - Session expires after 1 hour
2. **Use one tab only** - Multiple tabs can cause session conflicts
3. **Logout properly** - Use logout button, don't just close browser
4. **Regular logins** - Login fresh each day
5. **Clear cache periodically** - Prevents stale data

---

## 🔐 **Security Note**

This error is actually a **good thing** - it means:
- ✅ Your system is checking authentication properly
- ✅ Unauthorized users can't access attendance
- ✅ Sessions are being validated
- ✅ Security is working as intended

---

## 📞 **Debug Mode**

To see detailed session info:

1. Look at your terminal where Flask is running
2. When you click "Start Camera", you'll see:
   ```
   Session contents: {'user_id': 3, 'role': 'faculty', ...}
   Session has user_id: True
   Session role: faculty
   ```

3. If you see:
   ```
   Session contents: {}
   Session has user_id: False
   ERROR: No user_id in session!
   ```
   → **You need to login again!**

---

## ✅ **Expected Behavior**

When working correctly:
1. Login as faculty
2. Go to attendance page
3. Select class
4. Click "Start Camera"
5. Camera starts ✅
6. Face recognition works ✅
7. No 401 errors ✅

---

## 🎯 **Quick Test**

Run this to verify you can login:
```bash
python test_session.py
```

This shows all faculty accounts you can use.

---

**TL;DR: Just logout, close browser, login again as faculty, and try again! 99% of the time this fixes it.** 😊

---

*If none of these work, check the Flask terminal for detailed error messages.*

