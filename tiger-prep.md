# Tiger Analytics F2F Prep — Sr. Engineer / Lead, GenAI + DE

Personal study doc for the face-to-face round against the **Sr. Engineer /
Lead — GenAI + DE** JD (Chennai / Bangalore / Hyderabad). Designed to be
read once, used as the night-before cheat sheet.

---

## Fit assessment in one paragraph

Strong fit on **GenAI primary**: 3 years building production LLM apps,
RAG pipelines, multi-agent orchestration on LangChain + LangGraph + CrewAI,
vector DB experience across Weaviate, Pinecone, ChromaDB, FAISS, and
governance/Responsible-AI controls already in production at Virtusa. Strong
fit on **AWS + Python + SQL**. Adequate on data pipelines via DVC + Airflow
+ Step Functions in the Loan-Default project. **Real gap: PySpark / Spark**
— never shipped, never on the resume. Plan: bring honest framing + ramp on
fundamentals before the interview so the live-coding screen isn't a flail.

---

## Pre-interview prep checklist (last 48 hours)

- [ ] Spin up Databricks Community Edition (free), run 5 PySpark cells:
      `read.parquet → filter → groupBy.agg → join → write.parquet`.
- [ ] Skim "Learning Spark 2nd ed." chapters 3 (DataFrame API), 4 (Spark
      SQL), 7 (optimisation). Free PDF from Databricks.
- [ ] Re-read your own [`WALKTHROUGH.md`](WALKTHROUGH.md) — bookmark in
      browser, not open during interview.
- [ ] Have the project repo open in your head:
      [VisionNext, PE Doc, Loan-Default, YouTube Sentiment].
- [ ] Sleep. Pack water + paper for system-design diagrams.

---

## Topics the panel will probe (ranked by likelihood)

1. **RAG architecture** — your PE Doc project is the natural entry point.
2. **System design** — "Design RAG over 10M docs / a customer-support bot."
3. **PySpark live coding** — DataFrame API, group-bys, joins, windows.
4. **SQL** — VisionNext SQL agent gives you a strong angle.
5. **LLM choice + cost** — when to use OpenAI vs Bedrock vs self-hosted.
6. **Fine-tuning landscape** — LoRA / QLoRA / PEFT terminology.
7. **Multi-agent orchestration** — LangGraph vs LangChain, error handling.
8. **Behavioural** — failure, disagreement, ownership stories.

---

## 20 Likely Questions + Model Answers

### GenAI / LLM (5)

**Q1. RAG vs fine-tuning — when do you pick each?**

RAG: when the knowledge is large, changes often, and the model needs to
cite. Fine-tuning: when you need a *behaviour* the base model doesn't have
(domain-specific output format, tone, classification). In practice I
default to RAG first — cheaper to iterate, easier to update, and you can
cite sources. Fine-tune only when prompt engineering + RAG hit a ceiling
(usually around format consistency or domain-specific reasoning patterns).
The two are not mutually exclusive — production setups often fine-tune a
small base model and ground it with RAG.

**Q2. How do you reduce hallucinations in a RAG system?**

Layered defence:
1. Retrieval quality first — hybrid search (BM25 + vector) + cross-encoder
   reranker, evaluated with RAGAS (`context_precision`, `context_recall`).
2. Constrain the prompt — "answer only from the provided context; if not
   present, say 'I don't have that information'."
3. Structured output — Pydantic models force the LLM into a schema; field-
   level LLM-as-judge confidence scoring flags low-confidence extractions
   for human review.
4. Citation requirement — every claim must reference a chunk id.
5. Eval gate in CI — regression tests on a golden set; fail the build if
   factual accuracy drops.

In PE Doc Intelligence I ran all five — that's how I kept hallucination
rate below the acceptance threshold for LPA documents.

**Q3. How do you handle inputs that exceed the LLM context window?**

Two patterns. (a) For *retrieval* — chunk + embed, retrieve top-K, fit
within context. Cross-encoder rerank narrows from 50→4 before stuffing.
(b) For *long single documents* — markdown-aware hierarchical chunking
(preserve section boundaries), then map-reduce or refine chains: process
each chunk, then combine. For PE LPA documents (often 100+ pages) I used
2-stage markdown-aware chunking — first by section header, then by token
limit within section, so semantic units don't get split across chunks.

**Q4. What evaluation metrics do you use for a RAG system?**

I separate retrieval from generation:
- **Retrieval**: context_precision (are retrieved chunks relevant?),
  context_recall (did we miss any needed chunks?), MRR for ranked lists.
- **Generation**: faithfulness (does the answer use only retrieved
  context?), answer_relevance, answer_correctness against ground truth.
- **End-to-end**: latency p95, token cost per query, deflection rate (for
  support bots), human eval samples weekly.

Tooling: RAGAS for the automated layer, LangSmith for trace-level
debugging, golden eval set with regression gates in CI.

**Q5. How do you choose between OpenAI, Anthropic, and self-hosted Llama?**

Three axes: cost, latency, data sensitivity.
- OpenAI / Anthropic: best quality, paid by token, data leaves your VPC.
  Default for non-sensitive use cases.
- Bedrock-hosted Claude or Llama: same quality tier, data stays in AWS
  account, more expensive per token but no egress.
- Self-hosted Llama / Mistral on GPU: cheapest at scale, full data
  sovereignty, but you own the serving infra. Break-even is roughly when
  managed-API spend exceeds $5-10K/month or compliance forbids egress.

I'd start managed, profile cost + latency, migrate to self-hosted only
when one of those axes forces it.

---

### RAG / Vector search (3)

**Q6. Walk me through your PE Document Intelligence Platform.**

(Use this as a 3-minute structured story.)
- *Problem*: extract structured fields from PE LPA + Subscription docs;
  inconsistent layouts, 100+ pages, financial precision required.
- *Architecture*: 6 specialised subagents on LangGraph — extractor,
  classifier, validator, reconciler, summariser, citation-builder.
  Bulk pipeline runs 10 docs concurrently.
- *RAG stack*: Weaviate hybrid search (BM25 + vector), cross-encoder
  reranking with `bge-reranker-large`, 2-stage markdown-aware chunking
  (section header → token limit).
- *Extraction*: dynamic Pydantic models built at runtime from the schema;
  LLM-as-judge scores per-field confidence, anything below threshold goes
  to human review.
- *Safety*: PII middleware redacts SSN/email/phone/address before LLM
  calls but preserves 17 PE-domain financial terms (carried interest,
  preferred return, hurdle rate, etc.).
- *Eval*: classification, extraction, RAG, summarisation — part of the
  511-test, 97%-coverage backend test base. Regression gate blocks merges.

**Q7. Hybrid search — why is BM25 + vector better than pure vector?**

Vector search captures *semantic similarity* — "increase profitability"
matches "improve earnings". BM25 captures *lexical match* — "Section 3.2"
matches "Section 3.2" exactly. Pure vector misses exact identifiers,
codes, dates, names. Pure BM25 misses paraphrases. Hybrid: run both, take
union of top-K from each, rerank with a cross-encoder. For PE docs (lots
of policy IDs + paraphrased explanations) this lifted retrieval precision
from ~60% to ~80%.

**Q8. What's a cross-encoder reranker and when do you need one?**

Bi-encoder (your embedding model): scores query and doc independently,
fast — used for the first-pass retrieval over millions of vectors.
Cross-encoder: takes (query, doc) as one input, attends jointly, scores
in one pass — much more accurate but quadratic to run, so you only do it
on the top 50 candidates from the bi-encoder. Pattern: bi-encoder
retrieves 50, cross-encoder reranks to 4-5, those 4-5 go into the LLM
prompt. I used `bge-reranker-large` in PE Doc — easy 10-15 point lift on
context precision.

---

### LangChain / LangGraph (2)

**Q9. When do you pick LangGraph over plain LangChain?**

LangChain LCEL: linear pipelines. Input → retriever → prompt → llm →
parser → output. Great for RAG, summarisation, simple chains.

LangGraph: when you need cycles, branching, or shared state across agents.
Specifically:
- Multi-agent workflows where agents hand off to each other (planner →
  worker → verifier).
- Retry loops where the verifier sends bad output back to the worker.
- Stateful conversation with memory.
- Conditional routing based on intermediate output.

In VisionNext (orchestrator + SQL expert + visualiser) the orchestrator
routes to the right specialist based on intent, and the SQL expert can
ask the visualiser for chart hints — that's a graph, not a chain. Hence
LangGraph.

**Q10. How do you handle errors and retries in a multi-agent workflow?**

Three layers:
1. **Tool-level retry** — exponential backoff on transient LLM API
   failures (rate limits, 5xx). 3 retries, then bubble up.
2. **Agent-level fallback** — if the SQL agent fails to produce valid
   SQL after retries, route to a "clarification" path that asks the user
   for more context instead of erroring.
3. **Graph-level circuit breaker** — token budget gate per conversation;
   if cumulative tokens exceed budget, return a "request is too complex,
   please simplify" message rather than burning more spend.

Observability: every node logs to LangSmith with trace id, so post-hoc
analysis catches patterns (e.g. one agent type retrying too often).

---

### PySpark / Spark (4) — the gap area, prep these hardest

**Q11. Narrow vs wide transformations?**

Narrow: each output partition depends on one input partition. `map`,
`filter`, `union`, `coalesce` (when reducing partitions). No data movement
across nodes. Pipelined together within a stage.

Wide: each output partition depends on multiple input partitions. Requires
a **shuffle** — repartitioning data across executors over the network.
`groupBy`, `join` (most types), `distinct`, `orderBy`, `repartition`.

The catalyst optimiser tries to push narrow transformations together into
a single stage and minimise shuffles. Knowing which is which lets you
predict where the slow stages will be.

**Q12. What's a shuffle and why is it expensive?**

Shuffle is the data movement that happens between stages when partitioning
needs to change. Pipeline:
1. Each map task writes its output partitioned by the new key, to local
   disk.
2. Reduce tasks fetch the relevant partitions over the network from every
   map task.
3. Reduce task sorts + merges + processes.

Expensive because: (a) network IO across all executors, (b) disk IO at
both ends, (c) serialisation overhead, (d) memory pressure during sort.
Minimise by broadcasting small tables, picking the right partition count
(default 200 is often wrong), and using AQE to coalesce small post-shuffle
partitions.

**Q13. Broadcast join vs shuffle hash join — when do you pick which?**

Broadcast: the small table is replicated to every executor; the large
table stays in place; the join happens locally per partition. No shuffle.
Pick this when one side fits in memory — default Spark threshold is 10 MB,
tune via `spark.sql.autoBroadcastJoinThreshold`. Manually force with
`broadcast(df_small)`.

Shuffle hash / sort-merge: both sides shuffled by join key, then joined
in matched partitions. Pay the shuffle cost but handles arbitrary sizes.
Sort-merge is the default for two large tables.

Rule of thumb: if one side is < a few hundred MB, broadcast it. The cost
of replicating that table to every executor is much less than shuffling
the multi-GB other side.

**Q14. How do you optimise a slow PySpark job?**

Diagnostic checklist:
1. Look at the Spark UI — which stage takes the time? Is it shuffle-heavy?
2. Check partition count — too few = stragglers, too many = task overhead.
   Aim for partitions of 100-200 MB each.
3. Look for **skew** — one partition dominating. Fix with salting the key
   or with `skew join` hint in AQE.
4. Broadcast small tables explicitly if the optimiser missed them.
5. Cache + persist intermediate results if they're reused (`df.cache()`)
   but don't cache lazily — call an action to materialise.
6. Predicate pushdown — filter early, before joins, before wide
   transformations.
7. Avoid `collect()` and `toPandas()` on large data — pulls everything to
   the driver and OOMs.
8. Use columnar formats (parquet / delta) for inputs and outputs.
9. Enable AQE (`spark.sql.adaptive.enabled=true`) — Spark 3.x dynamically
   coalesces partitions, switches join strategies, handles skew.

---

### SQL + data modeling (2)

**Q15. Live: top 5 pages by unique users per day.**

```python
from pyspark.sql import functions as F, Window

w = Window.partitionBy("date").orderBy(F.col("uniques").desc())

result = (events
    .filter(F.col("event_type") == "page_view")
    .groupBy("date", "page_id")
    .agg(F.countDistinct("user_id").alias("uniques"))
    .withColumn("rank", F.row_number().over(w))
    .filter(F.col("rank") <= 5)
    .orderBy("date", "rank")
)
```

Pure SQL equivalent (if they ask):

```sql
WITH per_page AS (
  SELECT date, page_id, COUNT(DISTINCT user_id) AS uniques
  FROM events
  WHERE event_type = 'page_view'
  GROUP BY date, page_id
),
ranked AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY date ORDER BY uniques DESC) AS rank
  FROM per_page
)
SELECT date, page_id, uniques FROM ranked WHERE rank <= 5
ORDER BY date, rank;
```

**Q16. How would you model an event-stream warehouse for an analytics use case?**

Star schema:
- Fact table: `events` — narrow, append-only, partitioned by `date` for
  pruning. Columns: `event_id`, `user_id`, `session_id`, `event_type`,
  `event_ts`, `page_id`, `device_id`, and 2-3 measures (`duration_ms`,
  etc.).
- Dimension tables: `dim_user`, `dim_page`, `dim_device`, `dim_date`.
  Slowly Changing Dimensions Type 2 for user attributes (track historical
  state).
- Partitioning: by `date` always; sub-partition by `event_type` only if
  one type dominates queries.
- File format: Parquet or Delta — columnar, schema enforcement, time
  travel (Delta).
- Aggregations: rollups in a separate `daily_user_page_stats` table built
  by a scheduled Airflow / dbt job.

Drives the warehouse story for both ad-hoc analytics and ML feature
generation.

---

### System design (2)

**Q17. Design a RAG system over 10M enterprise docs.**

Whiteboard skeleton:

1. **Ingestion** — files land in S3. Spark job (one stage per doc type):
   - Extract text via tika / unstructured.io.
   - Markdown-normalise.
   - Chunk hierarchically — section then token.
   - Embed with `pandas_udf` batching, call OpenAI / Bedrock /
     sentence-transformers depending on cost target.
   - Write to Pinecone / Weaviate via batched upserts.
   - Metadata index in Postgres / OpenSearch for filterable retrieval
     (date, owner, doc type, ACL).

2. **Retrieval API** — FastAPI on ECS / EKS:
   - Hybrid search: BM25 (OpenSearch) + vector (Pinecone), top 50 each.
   - Filter by ACL — never return chunks the requester can't see.
   - Cross-encoder rerank to top 4-5.
   - PII redaction layer on retrieved text.

3. **Generation** — LangChain LCEL chain → LLM call (OpenAI / Bedrock
   Claude). Structured output via Pydantic. Citation requirement in the
   prompt.

4. **Observability** — LangSmith for traces, Prometheus for latency, S3
   for full request/response audit logs (7-yr retention for compliance).

5. **Eval + governance** — RAGAS regression suite, human eval weekly,
   guardrails block PII leakage and prompt injection.

6. **Scale** — at 10M docs, embedding cost dominates ingestion. Cache
   embeddings keyed by chunk hash; only re-embed on doc change. Estimate
   storage at ~50 GB embeddings (1536-dim float32 × 8M chunks).

**Q18. Design a customer-support chatbot with safety guardrails.**

Same skeleton as Q17 but emphasise:
- **Intent classifier** in front — only route in-scope intents to RAG.
  Out-of-scope (small talk, abuse) handled by a separate path or
  escalated.
- **Input guardrails** — PII scrubber, prompt-injection detector,
  toxicity filter.
- **Output guardrails** — toxicity + PII check on LLM output before
  sending to user; "I'm not sure about that, let me connect you to a
  human" fallback when confidence low.
- **Human escalation path** — every conversation gets a "talk to human"
  button; agent-availability gating; full conversation history piped to
  the human agent.
- **Eval** — deflection rate (% of conversations solved without
  escalation) as the north-star metric; cost per resolved conversation
  as the cost metric.

---

### Behavioural (2)

**Q19. Tell me about a time you disagreed with a team decision.**

(Use a real story. If you have one from Virtusa, lead with that. Fallback
template:)

"At Virtusa we were debating whether to fine-tune Llama for the PE Doc
extraction or stick with RAG + GPT-4. The team leaning was fine-tune
because it 'felt' more sophisticated. I pushed back: our extraction
accuracy on a 50-sample eval set was already 87% with RAG, fine-tuning
would cost 2-3 weeks of engineering and ongoing maintenance, and we
hadn't yet exhausted prompt + retrieval optimisations. I proposed: spend
one sprint maxing out the RAG path, eval rigorously, then decide. We
landed at 92% with reranking + better chunking — no fine-tune needed,
shipped two weeks earlier."

**Q20. Hardest production bug you've debugged?**

Pick something with a clear cause + fix story. If you have a real one,
use it. Fallback structure: *Symptom → Investigation → Root cause → Fix
→ Prevention.* Example from Loan-Default:

"Train integration tests started failing with `AttributeError: Can't get
attribute 'FeatureArtifacts' on pytest.__main__`. Looked like a pickle
deserialisation issue. Traced to `joblib.dump` of a dataclass defined in
a module that gets run as `__main__` via `python -m`. The pickle stores
`module=__main__`, but at load time `__main__` is pytest. **Fix**:
replaced the dataclass with a plain dict — pickleable from anywhere, no
module ambiguity. **Prevention**: added a CI step that loads each
joblib artefact from a separate process to catch this class of issue
early."

---

## Questions to ask THEM at the end

Prepared questions show seriousness. Pick 2-3.

1. "What's the current GenAI stack? Are you on managed APIs, self-hosted,
   or a mix? Any plans to migrate?"
2. "What's the typical data scale for the pipelines this role would own
   — TBs, PBs?"
3. "How is the GenAI team structured relative to the data engineering
   team? Are you one team or two collaborating?"
4. "What does on-call look like for production GenAI systems here?
   What's the average MTTR target?"
5. "What's a recent technical decision the team made that you'd reverse
   today, given what you've learned?"  *(Strong signal of curiosity +
   intellectual honesty.)*
6. "How are model + RAG evaluation gates wired into your CI? Any
   regression-block patterns in place?"

---

## Mindset for the room

- **Be specific, always.** Replace "we did RAG" with "we used Weaviate
  hybrid search, bge reranker, 2-stage chunking — that lifted precision
  from 60% to 80%." Specifics signal real work.
- **Own gaps.** PySpark and fine-tuning: name them yourself before they
  do. "Haven't shipped PySpark in production; I've ramped on fundamentals
  this week — happy to white-board a Spark job. For fine-tuning, my
  production work has been RAG-grounded; I know LoRA / PEFT but haven't
  trained at scale."
- **Tell stories with numbers.** Latency drop, accuracy lift, cost
  savings, test count. Tiger Analytics interviews engineering hires hard
  on impact metrics.
- **No AI tools in the room.** Same rule as Adobe — interviews are about
  your reasoning, not your access to autocomplete.

Good luck.
