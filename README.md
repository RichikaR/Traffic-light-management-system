# Traffic Light Management System (TLMOF)

An Operating System–inspired traffic signal control framework that models intersections as a CPU scheduler.

Vehicles behave like processes, lanes behave like ready queues, and the traffic controller acts as a hybrid kernel scheduler.

The system combines **Max-Pressure traffic control** with **Weighted Fair Queuing fairness guarantees** to achieve both high throughput and starvation-free scheduling.

---

# OS Concept Mapping

| Operating System | Traffic System |
|---|---|
| CPU | Intersection |
| Process | Vehicle |
| Ready Queue | Lane |
| Scheduler | Traffic Signal Controller |
| Context Switch | Yellow Light |
| Deadlock | Gridlock |
| Interrupt | Emergency Vehicle |

---

# Features

### Hybrid Kernel Scheduler
Signal phases are selected using a hybrid pressure function:

```
P_s(t) = α * TrafficPressure + β * WaitTime
```

Where:

- **α** controls throughput
- **β** controls fairness

---

### Anti-Starvation Guarantee

If β > 0, no lane can wait indefinitely.

As a lane's wait time increases, its scheduling score eventually exceeds all competing phases, forcing the scheduler to serve it.

---

### Deadlock Detection (Gridlock Prevention)

Gridlock is modeled as a **deadlock condition** using Coffman's conditions.

A **Wait-For Graph (WFG)** is constructed between lanes:

- Nodes → lanes  
- Edges → blocking dependencies  

If a cycle is detected, the controller executes a **Flush Phase** to break the deadlock.

---

# Project Structure

```
Traffic-light-management-system
│
├── client/                 # React frontend
│   └── src/
│
├── server/                 # Express backend
│   └── index.ts
│
├── simulation/             # Traffic simulation logic
│
├── sumo_integration/       # SUMO research experiments
│
├── metrics_output/         # Benchmark results
│
├── package.json
└── README.md
```

---

# Installation

Clone the repository:

```bash
git clone https://github.com/RichikaR/Traffic-light-management-system.git
cd Traffic-light-management-system
```

Install dependencies:

```bash
npm install
```

---

# Running the Application

### Option 1 — Using npm

```bash
npm run dev
```

This runs:

```
tsx server/index.ts
```

and starts the development server.

---

### Option 2 — Using npx (direct execution)

You can also start the server directly using `tsx`:

```bash
npx tsx server/index.ts
```

---

# Access the Dashboard

After starting the server, open:

```
http://localhost:5000
```

---

# Production Build

Build the project:

```bash
npm run build
```

Start production server:

```bash
npm start
```

---

# Metrics

The system evaluates traffic control using:

- Average Delay (seconds per vehicle)
- Jain's Fairness Index
- Phase Changes
- Per-lane Head Wait Time

Experiments show significant improvements over fixed-time traffic signals.

---

# Research Background

TLMOF applies classical operating system scheduling concepts to urban traffic control, including:

- Max-Pressure scheduling
- Weighted Fair Queuing
- Deadlock detection via Wait-For Graphs
- Hybrid kernel scheduling

---

# License

MIT License
