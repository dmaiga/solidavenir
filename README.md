# Solid'Avenir - See it, Trust it, Fund it
**Crowdfunding & Impact Tracking Platform powered by Hedera Hashgraph**  

**Track:** Onchain Finance & Real-World Assets (RWA)

---

## 🔗 Official Links
- 🎓 **Certification – Hedera Hashgraph:** [View PDF](https://drive.google.com/file/d/1SNWzoYJ55lqK3ZBflzJZfvrE3rJCQAK2/view?usp=drive_link)  
- 📊 **Pitch Deck:** [View PDF](https://drive.google.com/file/d/1bCRylbIFU40lLtkM6SEQE5Oyh7Vl0Kbn/view?usp=drive_link)  
- 📁 **Project Documentation:** [View PDF](https://drive.google.com/file/d/1-pzQveXdRdapQ_20revg97CjN2KYlh_7/view?usp=drive_link)  
- 🎥 **Demo Video (YouTube):** [Watch Video](https://www.youtube.com/watch?si=6gF8j8ZWwULKfuJY&v=nvAchPVDPoY&feature=youtu.be)  
- 🌍 **Website:** [solidavenir.com](https://solidavenir.com)  

**Solid'Avenir** provides a transparent, verifiable, and decentralized funding platform.  
Funds are released based on milestone validation, and all evidence (photos, receipts, reports) are immutably anchored on Hedera Hashgraph.

**Core pillars:**
- 🔍 Audit & verification of every project  
- 💰 Controlled, milestone-based fund release  
- 🧾 Immutable record of proofs & reports  
- 🌐 Mobile-first, offline-ready architecture  
- 🧠 DAO-based governance for future scalability  

---

## ⚙️ Hedera Integration Summary

| Component                        | Usage |
|---------------------------------|-------|
| **Hedera Consensus Service (HCS)** | Each project has a dedicated Topic for immutable anchoring of proofs, milestones, and reports |
| **Hedera Token Service (HTS)**    | Tokenization of contributions and fractional ownership of projects |
| **Hedera Mirror Node**            | Enables public audit and traceability of all actions |
| **Hedera Account Service**        | Creates accounts for validated projects and enrolled users for fund transfers |
| **Smart Contracts (Planned)**     | Automate milestone-based fund release (Trust-as-a-Service - TaaS) |


### **Transaction Types Executed**

| Transaction | Backend Endpoint | Data Sent | Description |
|-------------|------------------|-----------|-------------|
| `AccountCreateTransaction` | `POST /create-wallet` | `{ initialBalance }` | Creates a new Hedera account for user/project. Returns `accountId`, `privateKey`, `publicKey` |
| `TransferTransaction` | `POST /transfer` | `{ fromAccountId, fromPrivateKey, toAccountId, amount }` | Transfers HBAR between Hedera accounts. Returns transaction status and HashScan link |
| `AccountBalanceQuery` | `GET /balance/:accountId` | — | Retrieves HBAR balance of a Hedera account |
| `TopicCreateTransaction` | `POST /create-topic` | `{ memo }` | Creates HCS Topic dedicated to a project for immutable anchoring of proofs and milestones |
| `TopicMessageSubmitTransaction` | `POST /send-message` | `{ topicId, message }` | Submits message (proof, report) to HCS Topic. Includes HashScan and Mirror Node link for auditability |

**Usage:**
- `AccountCreateTransaction` → Creation of Hedera accounts for validated projects
- `TransferTransaction` → Transfer of contributions (HBAR/tokens)
- `TopicCreateTransaction` → Creation of topics per validated project
- `TopicMessageSubmitTransaction` → Sending messages (proofs, reports, validations)
- `AccountBalanceQuery` → Verification of project account balances

---


## 🆔 Deployed Hedera Testnet IDs

| Component | Testnet ID | Verification Link |
|-----------|------------|-------------------|
| Operator Account | `0.0.6808286` | [View on HashScan](https://hashscan.io/testnet/account/0.0.6808286) |
| HCS Topic (Example) | `0.0.7053681` | [View on HashScan](https://hashscan.io/testnet/topic/0.0.7053681) |
| Sample Transaction | `0.0.6808286@1761862484.177943340` | [View Transaction](https://hashscan.io/testnet/transaction/0.0.6808286@1761862484.177943340) |

---

## 💰 Economic Justification for Hedera
Hedera’s low and predictable fees ($0.0001 per transaction) enable Solid’Avenir to charge only 2–5% platform fees for social projects and 5–10% for economic projects, making crowdfunding financially viable for African communities while ensuring full transparency.

1. **Low, Predictable Fees → Financial Sustainability**  
Thanks to Hedera, Solid'Avenir minimizes operational costs and offers reduced fees, maximizing funds allocated to projects.

2. **High Throughput → Mass Adoption**  
Supports thousands of simultaneous projects in West Africa, >10,000 TPS at constant cost, without prohibitive fees.

3. **ABFT Finality → Essential Trust**  
Each donation is secured with complete and instant traceability, strengthening contributor confidence.

4. **Economic Benefits for African Context**  
- **For project creators:** reduction in audit costs, faster fund access, mobile optimization  
- **For backers:** viable micro-donations, real-time impact tracking, competitive local fees  

> Hedera makes African crowdfunding safer, faster, and more accessible.

---

## 🏗️ Architecture Diagram (ASCII)

```mermaid
flowchart LR
    subgraph Frontend
        FE[🌐 Frontend<br/>UI/UX]
    end

    subgraph Backend
        BE[⚙️ Backend<br/>Django API]
    end

    subgraph Hedera
        HE[🔗 Hedera Network<br/>HCS + HTS + Mirror Nodes]
    end

    %% --- Flow connections ---
    FE -- "1️⃣ Submit Project" --> BE
    BE -- "2️⃣ Create HCS Topic" --> HE
    BE -- "3️⃣ Project Approved" --> FE
    FE -- "4️⃣ Make Payment" --> BE
    BE -- "5️⃣ HTS Token Transfer" --> HE
    FE -- "6️⃣ Submit Milestone Proof" --> BE
    BE -- "7️⃣ Submit HCS Message" --> HE
    HE -- "8️⃣ Query Mirror Node" --> BE
    BE -- "9️⃣ View Audit Reports" --> FE

    %% --- Styling ---
    style FE fill:#e1f5fe,stroke:#0288d1,stroke-width:2px
    style BE fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    style HE fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
```

---

### 🚀 Future Development

* 📱 **Mobile App** 
* 🤖 **Smart Contracts** – automatic milestone fund release
* 🪙 **Token-based DAO governance** – voting & compliance
* 🧾 **Decentralized audit dashboard** – via Mirror Node integration


---

### ✅ Collaborator & Credentials

* **Collaborator Invited:** `Hackathon@hashgraph-association.com`
* **Test Credentials:** Provided in DoraHacks submission notes

---

### 🔒 Security & Credentials

**Important Security Notes**

* ✅ No private keys committed to repository
* ✅ Example configuration files provided (`.env.example`)
* 🔐 Testnet credentials provided separately to judges

---

### 🗂️ Key Audit Files

| File                         | Description                        |
| ---------------------------- | ---------------------------------- |
| `hedera_service/src/app.js`  | Core Hedera interactions           |
| `solidavenir/core/models.py` | Business logic & wallet management |
| `solidavenir/core/views.py`  | API endpoints & workflow handling  |

---




## Project Structure

```
/hedera_service       # Node.js service for Hedera
/solidavenir          # Django backend
/scripts
  /linux              # Linux scripts (.sh)
  /windows            # Windows scripts (.bat)
docker-compose.yml    # To run services via Docker
```

### 🌱 Environment Variables (.example)

#### **hedera_service/.env.example**

```env
HEDERA_OPERATOR_ID=
HEDERA_OPERATOR_PRIVATE_KEY=
PORT=3001
NODE_ENV=development
```

#### **solidavenir/.env.example**

```env
# ⚙️ Database Configuration
# By default, Solid’Avenir uses SQLite for local development (no setup required).
# PostgreSQL is only used when running the app via Docker using the provided scripts.

# Database (Postgres via Docker)
DATABASE_URL=postgres://solidavenir:solidavenir@db:5432/solidavenir_db
POSTGRES_USER=solidavenir
POSTGRES_PASSWORD=solidavenir
POSTGRES_DB=solidavenir_db
POSTGRES_HOST=db
POSTGRES_PORT=5432
```


---
⚠️ Important:
The platform is composed of two separate services:
1. **Django backend** (Python, runs on port 8000).
2. **Hedera service** (Node.js, runs on port 3001).

If you are not using Docker, you must open **two separate terminals**:
- Terminal 1 → run the Hedera service.
- Terminal 2 → run the Django backend.

Both must be running simultaneously for the platform to function correctly.

---

## 1. Windows Setup

1. Clone the repository:

```powershell
git clone https://github.com/dmaiga/solidavenir.git
cd solidavenir
```


2. Run the scripts in separate terminals:

```
powershell

# Terminal 1 → Starts the Node.js service to use the Hedera SDK

.\scripts\windows\run_hedera_service.bat 

# Terminal 2 → Starts the Django backend for business logic
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


3. Launch the services in separate terminals:
```bash

# Terminal 1 → Starts the Node.js service to use the Hedera SDK

./scripts/linux/run_hedera_service.sh

# Terminal 2 → Starts the Django backend for business logic
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
> * Similarly, in `views` and `forms` or any HTTP calls between services, replace `localhost` with the container name (`solidavenir_hedera`) to enable proper inter-container communication.


---

## 4. General Precautions

1. **Windows**: run `.bat` scripts from PowerShell using `.\script_name.bat`. Ensure Node.js and Python are in the PATH.
2. **Linux**: make `.sh` scripts executable (`chmod +x`). Use `dos2unix` for files edited on Windows. Install `python3-venv` to create virtual environments.
3. **Docker**: replace all `localhost` references with the Docker service name for inter-container communication. Build images separately if needed.

---

