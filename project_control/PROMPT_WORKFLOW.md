flowchart TD

A[Luke idea / issue / feature request]

A --> B[ChatGPT interprets intent]
B --> C[Convert into bounded objective]

C --> D[Check system control files]

D --> D1[PROJECT_BRIEF]
D --> D2[ARCHITECTURE]
D --> D3[CURRENT_STATE]
D --> D4[GUARDRAILS]

D --> E{Does this fit current architecture?}

E -->|No| F[Architecture review]
F --> G[Create architecture decision]
G --> H[Update ARCHITECTURE and DECISIONS]
H --> I[Create phased plan]

E -->|Yes| I

I --> J{Task size?}

J -->|Small| K[Create single Codex task]
J -->|Large| L[Break into phased tasks]

L --> K

K --> M[Codex inspects repo]

M --> N[Codex executes task]

N --> O[Codex returns structured result]

O --> P[ChatGPT system review]

P --> Q{Technically correct AND system-safe?}

Q -->|No| R[Reject local patch]
R --> S[Revise task or architecture]
S --> K

Q -->|Yes| T[Run validation checks]

T --> U{Validation passed?}

U -->|No| V[Create fix task]
V --> K

U -->|Yes| W[Update control documents]

W --> W1[CURRENT_STATE]
W --> W2[DECISIONS]
W --> W3[TASK_QUEUE]

W --> X{Did system capability evolve?}

X -->|Yes| Y[Update ARCHITECTURE]
X -->|No| Z[Task complete]

Y --> Z

Z --> AA[System ready for next request]

## Prompt footer enforcement

- Parse supplied `PROMPT NUMBER` from the task request.
- Carry it unchanged through the response.
- Final output line must be exactly: `PROMPT NUMBER: <value>`.
