#  TLMOF: Traffic Light Management Operating Framework

**TLMOF** is a high-performance, full-stack simulation of an intelligent urban traffic controller. It bridges the gap between Operating System kernel principles—like process scheduling and deadlock prevention—and real-world traffic flow optimization.

Built as part of an **Operating Systems Digital Assignment**, this project implements a custom **Hybrid WMP-F Algorithm** to manage road intersections with the same precision a kernel manages CPU tasks.

---

##  The "OS" Core & Novelty

Unlike standard "timer-based" traffic lights, TLMOS treats each lane as a **Process** and each intersection as a **Resource**.

### 1. Hybrid WMP-F Algorithm
The system utilizes a **Weighted Max-Pressure Fair** algorithm. It calculates "pressure" (queue length) and applies **Weighted Fair Queuing (WFQ)** to ensure that high-density roads are cleared without "starving" smaller side streets.

### 2. Deadlock Prevention
Utilizing a **Distributed Wait-for Graph (WFG)**, the system detects potential "gridlocks" (circular wait conditions) and preemptively adjusts signal phases to break the cycle.



### 3. Emergency Preemption
A high-priority interrupt system that detects emergency vehicle signatures, triggering an immediate context switch to a "Green Wave" state while safely pausing low-priority traffic.

---

##  Tech Stack

### Frontend
- **React (TypeScript)** + **Vite**: For a high-performance, reactive dashboard.
- **Tailwind CSS** + **Radix UI**: For a clean, modular, and accessible interface.
- **React Query**: For efficient state synchronization.

### Backend
- **Node.js & Express**: Handling the core logic and scheduling.
- **WebSockets (`ws`)**: Real-time traffic state updates.
- **Passport & Express-Session**: Secure administrative access.

### Database
- **PostgreSQL**: Robust storage for traffic logs and analytics.
- **Drizzle ORM**: Type-safe database interactions.

---

##  Project Structure

```txt
TLMOF/
├── client/          # React + Vite frontend
├── server/          # Express backend (TypeScript)
├── shared/          # Shared types (Traffic states, Schedules)
├── attached_assets/ # Visual assets & Icons
├── drizzle.config.ts
└── package.json
```
---

##  Setup & Local Development

###  Requirements
* **Node.js 20+** (Required for Vite 7)
* **pnpm** (Recommended package manager)
* **PostgreSQL**

### 1) Clone & Install
```bash
git clone [https://github.com/Mogu-code/Operating-System-TLMOF.git](https://github.com/Mogu-code/Operating-System-TLMOF.git)
cd Operating-System-TLMOF
pnpm install
```
### 2) Environment Variables
Create a `.env` file in the root folder of the project. This file is used to store your sensitive credentials:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/dbname
SESSION_SECRET=your_secret_key
```
Do not commit your .env file to GitHub. It is already included in your .gitignore

### 3) Database Setup
TLMOF uses Drizzle ORM for type-safe database management. To sync your schema with your local PostgreSQL instance, run:

```bash
pnpm run db:push
```
### 4) Run the App
To start the development server for both the frontend and backend simultaneously:
```bash
pnpm dev
```
Once the server is running, open your browser and go to:  http://localhost:5000

###  Scripts
 Use these commands to manage the lifecycle of the project:
 Command,Description
 ```bash
pnpm dev,Starts the dev server with Hot Module Replacement (HMR).
pnpm build,Compiles the project into optimized production bundles.
pnpm start,Runs the production-ready build of the application.
pnpm check,Runs TypeScript diagnostics to ensure type safety.
pnpm db:push,Pushes changes in schema.ts directly to the database.
