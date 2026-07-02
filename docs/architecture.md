# Architecture — PNB Sahayak

**A multilingual, voice-first employee policy assistant on the Sarvam AI stack.**
This document is the Solution Architecture: six architecture views (context → components →
sequence → RAG → agentic escalation → deployment), plus security, non-functionals, and the
Sarvam API rationale. Each view is shown as a diagram image, with the editable Mermaid source
collapsed beneath it.

> **Diagram legend (palette).**
> 🟦 **Blue** = Sarvam models · ⬛ **Navy** = our app / orchestration ·
> 🟧 **Orange** = decision gates & the escalation path · ⬜ **Light** = supporting components & data stores.
>
> The diagrams below are also in [`docs/diagrams/`](diagrams/) as high-resolution PNGs (handy for slides).

---

## 1 · System context — who and what it talks to

![System context diagram](diagrams/1-system-context.png)

<details><summary>Diagram source (Mermaid)</summary>

```mermaid
flowchart TB
    EMP["👤 Bank employee<br/>branch · ops · field"]:::actor
    IAM["🔐 SSO / IAM<br/><i>planned — not in PoC</i>"]:::planned
    APP["🏦 PNB Sahayak<br/>web app + orchestration"]:::app
    SARV["🧠 Sarvam AI stack<br/>STT · TTS · Translate · LLM · OCR"]:::sarvam
    KB[("📄 Approved PNB documents<br/>DMS / internal KB")]:::store
    N8N["⚙️ n8n workflow"]:::escalate
    SHEET["📋 Tracking sheet<br/>HR / policy team"]:::store
    GOV["📊 Governance & analytics<br/>dashboard · audit log"]:::store

    EMP -->|"asks aloud — Hindi / English / Hinglish"| APP
    IAM -.->|"authenticates · planned"| APP
    APP -->|all AI inference| SARV
    APP -->|retrieves passages| KB
    APP -->|"unanswered → ticket"| N8N
    N8N --> SHEET
    APP -->|logs every turn| GOV

    classDef actor fill:#F1F5FB,stroke:#64748B,color:#15202E;
    classDef app fill:#0E1A2B,stroke:#0E1A2B,color:#ffffff;
    classDef sarvam fill:#2458F6,stroke:#1B3FB0,color:#ffffff;
    classDef escalate fill:#FB7A17,stroke:#C85F0E,color:#ffffff;
    classDef store fill:#F1F5FB,stroke:#64748B,color:#15202E;
    classDef planned fill:#F8FAFC,stroke:#94A3B8,color:#64748B,stroke-dasharray:5 3;
```

</details>

**In words.** Employees interact by voice; the app uses the Sarvam stack for all AI; it
answers **only from approved PNB documents**; unanswered questions become tracked tickets;
every turn is logged for governance. **SSO/IAM authentication is planned for production — the
PoC itself has no sign-in.** *(The PoC uses Sarvam's hosted API + a Google Sheet + a local
knowledge base; production adds SSO/IAM and uses Sarvam on-prem + the bank's DMS.)*

---

## 2 · Logical / component architecture — the layers

![Component architecture diagram](diagrams/2-component-architecture.png)

<details><summary>Diagram source (Mermaid)</summary>

```mermaid
flowchart TB
    subgraph L1["① Experience"]
        SPA["Web SPA — mic capture · WebSocket captions<br/>show-the-work panel · audio player"]:::app
    end
    subgraph L2["② Application / orchestration — FastAPI"]
        ORCH["Orchestrator<br/>pipeline control + efficiency levers"]:::app
        ASK["/api/ask — turn-by-turn"]:::app
        WS["/ws/transcribe — streaming captions"]:::app
    end
    subgraph L3["③ Voice — Sarvam"]
        STT["Saaras saaras:v3<br/>STT + language detect"]:::sarvam
        TTS["Bulbul bulbul:v3 — TTS"]:::sarvam
    end
    subgraph L4["④ Language — Sarvam"]
        TRN["Mayura mayura:v1<br/>translate in / out · language-lock"]:::sarvam
    end
    subgraph L5["⑤ Retrieval / knowledge"]
        ING["Ingestion (batch)<br/>parse → OCR → clean → chunk"]:::neutral
        IDX[("BM25 index<br/>~1,683 source-tagged passages")]:::store
        RET["Retriever — top 2–3 + scores"]:::neutral
        GATE{"Relevance gate<br/>(threshold)"}:::decision
    end
    subgraph L6["⑥ Reasoning — Sarvam"]
        PB["Prompt builder<br/>grounding rules + context + citation"]:::neutral
        LLM["Sarvam-30B<br/>grounded answer / draft + cite · reasoning_effort=null"]:::sarvam
        PARSE["Parser — answer + source id + confidence"]:::neutral
    end
    subgraph L7["⑦ Agentic escalation"]
        ESC["Escalation service<br/>→ n8n webhook → Sheet + local JSONL"]:::escalate
    end
    subgraph L8["⑧ Governance & observability (cross-cutting)"]
        LOG["Structured logging (per-stage)"]:::store
        DASH["Dashboard — volumes · languages<br/>confidence · escalations · gaps"]:::store
    end

    SPA --> ORCH
    ORCH --> ASK
    ORCH --> WS
    ASK -->|audio| STT
    STT -->|"query"| TRN
    TRN -->|"English query"| RET
    ING --> IDX --> RET --> GATE
    GATE -->|yes| PB --> LLM --> PARSE
    PARSE -->|"answer"| TRN
    TRN -->|"localized answer"| TTS --> SPA
    GATE -->|no| ESC
    PARSE --> LOG
    ESC --> LOG
    LOG --> DASH

    classDef app fill:#0E1A2B,stroke:#0E1A2B,color:#ffffff;
    classDef sarvam fill:#2458F6,stroke:#1B3FB0,color:#ffffff;
    classDef decision fill:#FB7A17,stroke:#C85F0E,color:#ffffff;
    classDef escalate fill:#FB7A17,stroke:#C85F0E,color:#ffffff;
    classDef neutral fill:#FFFFFF,stroke:#64748B,color:#15202E;
    classDef store fill:#F1F5FB,stroke:#64748B,color:#15202E;
    style L1 fill:#F8FAFC,stroke:#CBD5E1,color:#15202E
    style L2 fill:#F8FAFC,stroke:#CBD5E1,color:#15202E
    style L3 fill:#F8FAFC,stroke:#CBD5E1,color:#15202E
    style L4 fill:#F8FAFC,stroke:#CBD5E1,color:#15202E
    style L5 fill:#F8FAFC,stroke:#CBD5E1,color:#15202E
    style L6 fill:#F8FAFC,stroke:#CBD5E1,color:#15202E
    style L7 fill:#F8FAFC,stroke:#CBD5E1,color:#15202E
    style L8 fill:#F8FAFC,stroke:#CBD5E1,color:#15202E
```

</details>

**Component notes.** The **orchestrator** applies the efficiency levers (skip translate when
the language is English; skip the LLM entirely on a gate-fail; cap answer length; reasoning
off). **Ingestion** is an offline/batch pipeline, re-run only when documents change. The
**relevance gate** is the safety heart: no sourced passage → no generation → escalate.
**Production upgrade:** swap/augment BM25 with **hybrid retrieval** (BM25 + dense embeddings +
a cross-encoder reranker) on a vector store for higher precision.

---

## 3 · End-to-end request sequence — data flow + latency budget

![Request sequence diagram](diagrams/3-request-sequence.png)

<details><summary>Diagram source (Mermaid)</summary>

```mermaid
%%{init: {'themeVariables': {'noteBkgColor':'#F1F5FB','noteBorderColor':'#64748B','noteTextColor':'#15202E'}}}%%
sequenceDiagram
    autonumber
    actor E as Employee
    participant W as Web app
    participant O as Orchestrator
    participant S as Saaras (STT)
    participant M as Mayura (Translate)
    participant R as Retriever (BM25)
    participant L as Sarvam-30B (LLM)
    participant B as Bulbul (TTS)

    E->>W: Speak question (records 16k WAV)
    W->>O: POST /api/ask (audio)
    O->>S: audio
    S-->>O: transcript + language
    Note right of S: ~0.5–1.5s
    alt language ≠ English
        O->>M: transcript
        M-->>O: English query
        Note right of M: ~0.3–0.6s
    end
    O->>R: English query
    R-->>O: top 2–3 passages + scores
    Note right of R: ~10–50ms
    alt no relevant passage (gate fail)
        O-->>W: "Can't answer" + ticket id
        Note over O: escalate (ticket) — skip LLM + TTS
    else relevant passage
        O->>L: grounded prompt (context + rules)
        L-->>O: answer + cited source
        Note right of L: ~1–2.5s
        alt user language ≠ English
            O->>M: answer
            M-->>O: answer in user language (locked)
            Note right of M: ~0.3–0.6s
        end
        O->>B: answer text
        B-->>O: speech (user language)
        Note right of B: ~1–2s
        O-->>W: transcript · language · source + link · confidence · answer · audio
    end
    W-->>E: Show panel + play spoken answer
    O->>O: log interaction (per-stage latency)
```

</details>

**Latency budget:** target **~4–6s** end-to-end for a turn (text visible in ~2–3s; audio
follows — TTS is usually the largest single cost). The **streaming captions** path
(`/ws/transcribe`) is separate and real-time (words appear as you speak).

---

## 4 · RAG / knowledge pipeline — ingestion → grounded answer

![RAG knowledge pipeline diagram](diagrams/4-rag-pipeline.png)

<details><summary>Diagram source (Mermaid)</summary>

```mermaid
flowchart LR
    subgraph INGEST["Ingestion — offline / batch"]
        direction LR
        DOCS[("Approved PNB documents<br/>56 real PDFs")]:::store
        EXT["Extract text"]:::neutral
        OCR["Sarvam Vision OCR<br/>(2 scanned)"]:::sarvam
        CLEAN["Clean / normalize"]:::neutral
        CHUNK["Chunk → passages<br/>+ source: file · URL · title"]:::neutral
        IDX[("BM25 index<br/>~1,683 passages")]:::store
        DOCS --> EXT --> CLEAN
        DOCS --> OCR --> CLEAN
        CLEAN --> CHUNK --> IDX
    end
    Q["User query (English)"]:::app
    RET["Retrieve top 2–3 + scores"]:::neutral
    GATE{"max score ≥ threshold?"}:::decision
    ESC["Escalate (no LLM)"]:::escalate
    CTX["Assemble context<br/>passages + source tags"]:::neutral
    ANS["Sarvam-30B<br/>answer ONLY from context + cite source"]:::sarvam
    CITE["Attach citation + confidence"]:::neutral

    IDX --> RET
    Q --> RET --> GATE
    GATE -->|no| ESC
    GATE -->|yes| CTX --> ANS --> CITE

    classDef app fill:#0E1A2B,stroke:#0E1A2B,color:#ffffff;
    classDef sarvam fill:#2458F6,stroke:#1B3FB0,color:#ffffff;
    classDef decision fill:#FB7A17,stroke:#C85F0E,color:#ffffff;
    classDef escalate fill:#FB7A17,stroke:#C85F0E,color:#ffffff;
    classDef neutral fill:#FFFFFF,stroke:#64748B,color:#15202E;
    classDef store fill:#F1F5FB,stroke:#64748B,color:#15202E;
    style INGEST fill:#F8FAFC,stroke:#CBD5E1,color:#15202E
```

</details>

**Why this is bank-safe:** generation is **retrieval-gated** and **citation-enforced** — the
model is instructed to answer *only* from the injected passages and to name the source; if
nothing clears the threshold, it never reaches the model. This is the concrete control behind
"no hallucination."

---

## 5 · Agentic escalation workflow — event → action, no human in the loop

![Agentic escalation workflow diagram](diagrams/5-escalation-workflow.png)

<details><summary>Diagram source (Mermaid)</summary>

```mermaid
flowchart TB
    ASK["Employee asks<br/>(voice / typed)"]:::app
    SEARCH["Search approved documents"]:::neutral
    CONF{"Confident, relevant answer?"}:::decision
    ANS["Answer + cited source + confidence"]:::neutral
    LOG[("Log interaction")]:::store
    DASH["Dashboard:<br/>knowledge-gap topics"]:::store
    TELL["Tell employee honestly:<br/>not in documents"]:::escalate
    TICKET["Build ticket:<br/>question · ts · language · confidence · transcript"]:::escalate
    N8N["n8n webhook"]:::escalate
    ROW["New row in tracking sheet<br/>(HR / policy team)"]:::store
    BACKUP[("Local JSONL backup")]:::store

    ASK --> SEARCH --> CONF
    CONF -->|Yes| ANS --> LOG --> DASH
    CONF -->|No| TELL --> TICKET
    TICKET --> LOG
    TICKET --> N8N
    N8N --> ROW
    N8N --> BACKUP

    classDef app fill:#0E1A2B,stroke:#0E1A2B,color:#ffffff;
    classDef decision fill:#FB7A17,stroke:#C85F0E,color:#ffffff;
    classDef escalate fill:#FB7A17,stroke:#C85F0E,color:#ffffff;
    classDef neutral fill:#FFFFFF,stroke:#64748B,color:#15202E;
    classDef store fill:#F1F5FB,stroke:#64748B,color:#15202E;
```

</details>

**Callouts:** *"Answers only from approved documents."* · *"Unanswered → tracked ticket
automatically."* · *"Every question logged → governance + knowledge-gap insight."*
**Production:** route tickets to the bank's ITSM/workflow instead of a Sheet.

---

## 6 · Deployment & infrastructure — sovereignty / on-prem

![Deployment and infrastructure diagram](diagrams/6-deployment.png)

<details><summary>Diagram source (Mermaid)</summary>

```mermaid
flowchart TB
    subgraph BANK["PNB environment — on-prem / private cloud"]
        LB["Load balancer"]:::neutral
        APPN["App instances<br/>stateless · FastAPI ×N"]:::app
        IDXS[("Index + documents (KB)")]:::store
        LOGS[("Logs / audit")]:::store
        DASHS["Dashboard"]:::store
        IAM["SSO / IAM<br/>(planned)"]:::planned
        DMS[("DMS — document source")]:::store
        ING["Ingestion pipeline"]:::neutral
        LB --> APPN
        APPN --> IDXS
        APPN --> LOGS
        APPN --> DASHS
        IAM -.->|planned| APPN
        DMS --> ING --> IDXS
    end
    subgraph SARV["Sarvam models"]
        M1["Saaras · Bulbul · Sarvam-30B · Mayura · Vision"]:::sarvam
    end
    APPN <-->|"private link / VPN · IP-whitelist<br/>(ideal: Sarvam deployed on-prem)"| SARV

    classDef app fill:#0E1A2B,stroke:#0E1A2B,color:#ffffff;
    classDef sarvam fill:#2458F6,stroke:#1B3FB0,color:#ffffff;
    classDef neutral fill:#FFFFFF,stroke:#64748B,color:#15202E;
    classDef store fill:#F1F5FB,stroke:#64748B,color:#15202E;
    classDef planned fill:#F8FAFC,stroke:#94A3B8,color:#64748B,stroke-dasharray:5 3;
    style BANK fill:#F8FAFC,stroke:#CBD5E1,color:#15202E
    style SARV fill:#F8FAFC,stroke:#CBD5E1,color:#15202E
```

</details>

**Residency.** In the ideal RFP-compliant setup, **Sarvam models run inside the bank's
boundary** (sovereign / on-prem) so no document data leaves. If hosted, access is via private
link/VPN with IP-whitelisting and data minimisation. The PoC uses Sarvam's hosted API;
production uses the on-prem / sovereign option.

---

## 7 · Security & governance

| Concern | How it's addressed |
|---|---|
| **AuthN / Z** | *Planned for production (not in the PoC):* SSO/IAM integration; role-based access; per-user audit identity |
| **Data minimisation & residency** | only necessary text sent to models; no training on bank data; on-prem residency (§6) |
| **Grounding guardrails** | retrieval-gated generation + enforced citations + "I don't know → escalate" (§4/§5) |
| **Hallucination monitoring** | confidence score per answer; dashboard tracks confidence distribution and escalation rate; human review of escalations |
| **Audit & explainability** | every answer logged with its source + confidence; append-only interaction log |
| **Compliance mapping** | DPDP (consent, minimisation, access control); RBI FREE-AI (fairness, accountability, transparency, explainability); on-prem residency |

## 8 · Non-functional requirements (NFRs)

| NFR | Approach |
|---|---|
| **Latency** | budget in §3; levers — skip-LLM-on-no-match, skip-translate-on-match, top-2–3 retrieval, capped answers, reasoning off, response cache for common questions |
| **Scalability** | stateless app instances behind a load balancer; served in-memory index; cache layer; concurrency sized to demand |
| **Availability & resilience** | health checks; graceful degradation — local ticket backup if n8n is down; type-fallback if the mic fails |

---

## Sarvam APIs used (and why)

| Sarvam API / model | One line | Why we use it |
|---|---|---|
| **Saaras** (`saaras:v3`) | Speech → text (22 Indian languages) | Understands the spoken question; also powers live streaming |
| **Mayura** (`mayura:v1`, Translate API) | Text → text across languages, code-mixed / Roman styles | Bridges the user's language and the English documents, and keeps Hinglish answers consistent (`sarvam-translate:v1` covers extra languages) |
| **Sarvam-30B** (Chat Completions) | The LLM that reads context and writes the answer or draft | Short, grounded answers and drafted content; chosen over `sarvam-105b` because 30B is recommended for voice / low-latency |
| **Bulbul** (`bulbul:v3`) | Text → speech (11 Indian languages) | Speaks the answer back in the user's language |
| **Sarvam Vision** (Document Digitization) | Document / PDF → text (OCR) | Read the 2 scanned PDFs that had no text layer |

## Built (PoC) vs. Production

| Area | Built now (PoC) | Production upgrade |
|---|---|---|
| **Retrieval** | BM25 over ~1,683 passages | Hybrid: BM25 + dense embeddings + cross-encoder reranker on a vector store |
| **Knowledge source** | 56 real PNB PDFs (local) | Bank **DMS** feed + scheduled re-ingestion |
| **Escalation sink** | n8n → Google Sheet + local JSONL | n8n → bank **ITSM / workflow** |
| **Model hosting** | Sarvam hosted API | Sarvam **on-prem / sovereign** deployment |
| **Access** | open local / shared link | **SSO / IAM**, role-based access |

> All policy documents are **real, public PNB files**; nothing about the bank is fabricated.
