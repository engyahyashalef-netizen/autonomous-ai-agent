# 🤖 Autonomous AI Agent

نظام وكيل ذكاء اصطناعي مستقل مبني بـ Python و FastAPI، ويعتمد على بنية ReAct (Reason + Act + Self-Correct) لتنفيذ المهام المعقدة بشكل شبه مستقل.

## المزايا
- حلقة تفكير وتصحيح ذاتي
- اتصال مباشر بقواعد البيانات
- API جاهز باستخدام FastAPI
- أدوات قابلة للتوسيع مثل:
  - تنفيذ أكواد Python
  - إدارة الملفات
  - طلبات HTTP
  - رفع التغييرات إلى GitHub

## التشغيل

### 1) تثبيت المتطلبات
```bash
pip install -r requirements.txt
```

### 2) إعداد ملف .env
انسخ الملف التالي:
```bash
cp .env.example .env
```

ثم عدّل القيم:
```env
GEMINI_API_KEY=your_gemini_api_key_here
DATABASE_URL=postgresql://postgres:password@db.xxxx.supabase.co:5432/postgres
```

### 3) تشغيل الوكيل المحلي
```bash
python run_agent.py
```

### 4) تشغيل السيرفر
```bash
python agent_server.py
```

## مثال عملي
يقوم الوكيل بقراءة ملف sales_data.json، ثم يحسب المجموع الصحيح مع تجاهل القيم غير الرقمية، ثم يحفظ التقرير في final_report.txt.
