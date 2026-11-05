# Imagen base de Python (version "slim" = liviana)
FROM python:3.12-slim

# Carpeta de trabajo dentro del contenedor
WORKDIR /code

# Primero se copian y se instalan las dependencias (Docker las guarda en cache
# y no las reinstala si solo cambias tu codigo)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Despues se copia el codigo de la aplicacion
COPY app ./app

# Comando por defecto: arranca la API. (El worker sobreescribe este comando en docker-compose.yml)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
