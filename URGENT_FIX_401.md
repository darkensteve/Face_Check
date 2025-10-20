# 🚨 URGENT: Fix 401 Error

## ⚡ QUICK FIX (Do This Now!)

You're seeing "API Error: 401" because your **session is not active**.

---

## 🎯 **EXACT STEPS TO FIX:**

### **Step 1: Stop Flask** ⛔
In your terminal where Flask is running:
```bash
Press Ctrl + C
```
**Wait until it says it stopped!**

### **Step 2: Close ALL Browser Tabs** 🌐
- Close **ALL** tabs with `localhost:5000`
- Close the entire browser window
- **This is important!** Old sessions are cached

### **Step 3: Start Flask Fresh** 🚀
```bash
python start_app.py
```
**Wait for:**
```
* Running on http://127.0.0.1:5000
* Running on http://localhost:5000
```

### **Step 4: Open Fresh Browser** 🌐
- Open a **NEW** browser window
- Go to: `http://localhost:5000`

### **Step 5: Login as Faculty** 👤
Use one of these:

| Username | Password | Name |
|----------|----------|------|
| `FAC001` | `password123` | Jane Smith |
| `1` | `password123` | Jewel Gesim |
| `123123` | `password123` | Ninzo Ocliasa |
| `12345678` | `password123` | Jeff Salimbangon |

**Click "Login" button and wait for dashboard to load!**

### **Step 6: Go to Attendance** 📸
1. In sidebar, click **"Take Attendance"**
2. Select **FRELEAN** class
3. Click **"Start Camera"**
4. **Should work now!** ✅

---

## 🔍 **Why This Happens:**

The 401 error means:
```
Browser: "Here's my request to /api/attendance/detect"
Server: "Who are you? I don't see a session cookie!"
Browser: ❌ 401 Unauthorized
```

**Cause:** Your browser doesn't have a valid session cookie.

**Solution:** Fresh login creates new session cookie.

---

## 📊 **How to Verify You're Logged In:**

After Step 5 (login), you should see:
- ✅ Dashboard page loads
- ✅ Shows "Welcome, [Your Name]"
- ✅ Sidebar shows "Take Attendance" link
- ✅ Top right shows your name

If you don't see dashboard after login, something went wrong!

---

## 🐛 **If Still Getting 401:**

### **Check 1: Are you logged in?**
After login, open browser console (F12) and run:
```javascript
fetch('/api/check-session')
  .then(r => r.json())
  .then(d => console.log(d))
```

**Should show:**
```json
{
  "valid": true,
  "role": "faculty",
  "user_id": 5,
  "name": "Jewel Gesim"
}
```

**If shows 401 or "valid: false":** You're not logged in! Go back to Step 5.

### **Check 2: Is Flask running?**
Look at your terminal. Should show:
```
* Running on http://127.0.0.1:5000
```

**If not running:** Go back to Step 3.

### **Check 3: Correct URL?**
Make sure you're on:
- ✅ `http://localhost:5000`
- ❌ NOT `http://127.0.0.1:5000` (use localhost instead)

### **Check 4: Clear Browser Cache**
Press `Ctrl + Shift + Delete`, select:
- ✅ Cookies and site data
- ✅ Cached images and files

Then start from Step 4.

---

## 💡 **Common Mistakes:**

### ❌ **Mistake 1: Not stopping Flask first**
**Wrong:**
```
Start camera → Error → Restart Flask
```

**Right:**
```
Stop Flask → Close browser → Start Flask → Fresh login → Start camera
```

### ❌ **Mistake 2: Not closing browser**
**Wrong:**
```
Just refresh the page
```

**Right:**
```
Close ALL tabs → Open new browser → Login fresh
```

### ❌ **Mistake 3: Not waiting for login to complete**
**Wrong:**
```
Type username → Type password → Immediately go to attendance
```

**Right:**
```
Type username → Type password → Click Login → Wait for dashboard → Then go to attendance
```

---

## 🎯 **The Correct Flow:**

```
1. Stop Flask (Ctrl+C)
        ↓
2. Close browser completely
        ↓
3. Start Flask (python start_app.py)
        ↓
4. Open new browser → localhost:5000
        ↓
5. Login with FAC001 / password123
        ↓
6. Wait for dashboard to load ✅
        ↓
7. Click "Take Attendance"
        ↓
8. Select FRELEAN class
        ↓
9. Click "Start Camera"
        ↓
10. Camera starts → No 401 error! ✅
```

---

## 📸 **What You Should See:**

### **After Login (Step 5):**
![Dashboard loads with your name]

### **After Start Camera (Step 9):**
```
Recognition Status: Camera active - detecting faces...
[Camera feed shows]
[Green box appears when face detected]
```

### **NOT:**
```
❌ API Error: 401
❌ Unauthorized
❌ Session expired
```

---

## 🔧 **If You See This in Terminal:**

### **Good Signs ✅:**
```
Session contents: {'user_id': 5, 'role': 'faculty', ...}
Session has user_id: True
Session role: faculty
Processing face recognition...
```

### **Bad Signs ❌:**
```
ERROR: No user_id in session!
Session contents: {}
```
→ **You're not logged in!** Go back to Step 5.

---

## 📞 **Emergency Checklist:**

If STILL getting 401 after doing ALL steps:

- [ ] Flask is running (terminal shows "Running on...")
- [ ] Browser is on `http://localhost:5000`
- [ ] Logged in with faculty account (FAC001, 1, 123123, or 12345678)
- [ ] Dashboard loaded successfully after login
- [ ] Can see "Take Attendance" in sidebar
- [ ] Selected a class (FRELEAN)
- [ ] Browser console (F12) shows no JavaScript errors
- [ ] Terminal shows session info when clicking "Start Camera"

If ALL boxes checked and still 401:
1. Screenshot the error
2. Show terminal output
3. Show browser console (F12)

---

## 🎉 **Success Looks Like:**

```
✅ Flask running
✅ Logged in as faculty
✅ Dashboard loaded
✅ Camera starts
✅ Green box appears
✅ Face recognized
✅ Attendance marked
✅ NO 401 ERROR!
```

---

## ⚡ **TL;DR - Do This:**

1. **Ctrl+C** (stop Flask)
2. **Close browser**
3. **`python start_app.py`** (start Flask)
4. **Open `localhost:5000`**
5. **Login: FAC001 / password123**
6. **Wait for dashboard**
7. **Go to "Take Attendance"**
8. **Select class**
9. **Click "Start Camera"**
10. **WORKS!** ✅

---

**Follow these steps EXACTLY in order. Don't skip any!** 🎯

**Sundan pag-ayo! (Follow carefully!)** 😊

