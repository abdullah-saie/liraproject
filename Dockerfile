FROM python:3.10-slim

# ضبط مسار العمل
WORKDIR /app

# نسخ ملف المتطلبات أولاً لتسريع الـ Build
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# الانتقال لمجلد الباك-إند لتشغيل الأوامر منه
WORKDIR /app/backend

# تشغيل التطبيق (تأكد من استخدام المنفذ الذي يوفره Railway)
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]
