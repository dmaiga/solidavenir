
---

# Solid’Avenir

Crowdfunding platform with Hedera service and Django backend.

## Project Structure

```
/hedera_service       # Node.js service for Hedera
/solidavenir          # Django backend
/scripts
  /linux              # Linux scripts (.sh)
  /windows            # Windows scripts (.bat)
docker-compose.yml    # To run services via Docker
```

---

## 1. Windows Setup

1. Clone the repository:

```powershell
git clone https://github.com/dmaiga/solidavenir.git
cd solidavenir
```

2. Run the scripts:

```powershell
.\scripts\windows\run_hedera_service.bat
.\scripts\windows\run_backend.bat
```

> The backend script will create a Python virtual environment, install dependencies, apply migrations, and create a **superuser admin** with:
>
> * **username:** `admin`
> * **email:** `admin@solidavenir.com`
> * **password:** `changeMe123!`
> * **user\_type:** `admin`

---

## 2. Linux Setup

1. Clone the repository:

```bash
git clone https://github.com/dmaiga/solidavenir.git
cd solidavenir
```

2. Make scripts executable:

```bash
chmod +x scripts/linux/run_hedera_service.sh
chmod +x scripts/linux/run_backend.sh
```

> ⚠️ If the scripts were edited on Windows, run:
>
> ```bash
> dos2unix scripts/linux/*.sh
> ```

3. Launch the services:

```bash
./scripts/linux/run_hedera_service.sh
./scripts/linux/run_backend.sh
```

> The backend script automatically:
>
> * Creates a Python virtual environment.
> * Installs all required dependencies.
> * Applies Django migrations.
> * Creates a **superuser admin** (`username=admin`, `email=admin@solidavenir.com`, `password=changeMe123!`, `user_type=admin`).

> Make sure Python 3 and `python3-venv` are installed.

---

## 3. Docker Compose Setup

1. Launch services using Docker Compose:

```bash
docker-compose up --build
```

> Tips & Precautions:
>
> * If build fails, build images separately:
>
> ```bash
> docker build -t solidavenir ./solidavenir
> docker build -t hedera_service ./hedera_service
> ```
>
> * In `core/models.py`, replace `localhost` in `ensure_wallet` with the **Docker service name** (`hedera_service`) because `localhost` inside a container refers to the container itself.
>
> * Similarly, in `views` or any HTTP calls between services, replace `localhost` with the container name (`solidavenir_hedera`) to enable proper inter-container communication.

**Docker Compose Extract:**

```yaml
services:
  db:
    image: postgres:15
    container_name: solidavenir_db
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-solidavenir}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-solidavenir}
      POSTGRES_DB: ${POSTGRES_DB:-solidavenir_db}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - solidavenir_net

  django:
    build: ./solidavenir
    container_name: solidavenir_django
    env_file:
      - ./solidavenir/.env
    depends_on:
      - db
    ports:
      - "8000:8000"
    networks:
      - solidavenir_net
    entrypoint: ["/entrypoint.sh"]

  hedera_service:
    build: ./hedera_service
    container_name: solidavenir_hedera
    env_file:
      - ./hedera_service/.env
    ports:
      - "3001:3001"
    networks:
      - solidavenir_net

volumes:
  postgres_data:

networks:
  solidavenir_net:
    driver: bridge
```

---

## 4. General Precautions

1. **Windows**: run `.bat` scripts from PowerShell using `.\script_name.bat`. Ensure Node.js and Python are in the PATH.
2. **Linux**: make `.sh` scripts executable (`chmod +x`). Use `dos2unix` for files edited on Windows. Install `python3-venv` to create virtual environments.
3. **Docker**: replace all `localhost` references with the Docker service name for inter-container communication. Build images separately if needed.

---

