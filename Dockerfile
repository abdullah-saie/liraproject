FROM python:3.10-slim

# ضبط مسار العمل
WORKDIR /app

# نسخ ملف المتطلبات وتثبيته
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# تشغيل التطبيق مباشرة من المجلد الرئيسي
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8080"]
