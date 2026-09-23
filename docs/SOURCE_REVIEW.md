# Case source review

Reviewed on 23 September 2026. This file records evidence for [PLAN.md](../PLAN.md), not implemented functionality.

## Materials inspected

| File in `case files/` | Inspection | What it establishes |
| --- | --- | --- |
| `case name.txt` | Read in full | Track 08, meeting minutes and assignment tracking, Samruk-Kazyna case owner |
| `technical_task.docx` | Extracted text and inspected all 3 rendered pages | Requirements, restrictions, scoring |
| `Протокол_совещания№1.docx` | Extracted text and inspected all 4 rendered pages | Two topics, named dialogue, summary and 10 reference assignment rows |
| `Протокол_совещания№2.docx` | Extracted text and inspected all 4 rendered pages | Four departmental reports, named dialogue, summary and 6 reference assignment rows |
| `Совещание №1.mp3` | Local media metadata inspection | 274.250 seconds, MP3, 48 kHz, mono, 4,426,407 bytes |
| `Совещание №2.mp3` | Local media metadata inspection | 206.03125 seconds, MP3, 48 kHz, mono, 3,334,695 bytes |

Audio was not transcribed, uploaded, or assessed for recognition accuracy during planning. The MP3s also contain PNG cover-art streams; select the audio stream explicitly during conversion. Filename pairing suggests the recordings correspond to the protocols, but this has not been verified.

## Requirements and scoring

The technical brief requires recognition of Russian, Kazakh and mixed speech, diarization with participant attribution, assignment extraction with owner and deadline, a meeting summary, and protocol export as PDF/DOCX. The secretary starts recording with participant notification; managers use the result for follow-up. A second scenario describes reminders near deadlines and after overdue dates.

The input section mentions Teams, Zoom, Google Meet, audio/video recordings and live streams. Platform joining is not repeated in the mandatory minimum. An upload-first implementation is a planning interpretation, not proof that the organizers have waived meeting-platform integration.

Additional features include an assignment dashboard, distribution of extracts to owners, urgency/topic classification, voice identification, and EDMS integration. Full EDMS integration and industrial deployment are explicitly outside the mandatory scope.

The restrictions require compatibility with a closed customer environment and prohibit sending audio **or text** to external cloud APIs. This covers ASR, diarization, summarization and extraction. On-premise capability appears among extras too; that does not cancel the explicit restriction.

| Criterion | Points | Planning implication |
| --- | --- | --- |
| Requirements and working behavior | 25 | Demonstrate the entire meeting-to-protocol workflow |
| Technical implementation | 25 | Show actual component interaction and evidence-backed outputs |
| README and reproducibility | 25 | Test a documented clean setup, model provisioning and sample run |
| Value and applicability | 15 | Show review, responsibility and deadline follow-up |
| Growth and originality | 10 | Explain bilingual support, evidence links and credible extensions |

## Reference assignments

These tables summarize supplied reference rows. They are expected outputs for evaluation, never input to an extraction run. Owner names are transcribed as written in the supplied documents; public demonstrations using real identities require anonymization or an appropriate synthetic replacement.

### Meeting 1

| Topic | Assignment | Owner | Deadline wording |
| --- | --- | --- | --- |
| Chemical industry | Develop common raw-material procurement strategy | Гульмира Сериковна | 15 October |
| Chemical industry | Agree catalyst delivery schedule with design institute | Айнур Каировна | 26 September |
| Chemical industry | Prepare financing decision for Pavlodar modernization | Тимур Болатович | 30 September |
| Chemical industry | Review contractual penalties | Юридический департамент | 30 September |
| Chemical industry | Present consolidated report at next meeting | Гульмира Сериковна | 20 October |
| Safety | Investigate the contractor's missed inspection schedule and report | Гульмира Сериковна | Friday |
| Safety | Audit gas sensors and protective equipment across 11 sites | Нурлан Сагатович | 15 October |
| Safety | Conduct unscheduled gas-work safety training | Нурлан Сагатович | Next week |
| Safety | Reconcile safety purchases with investment budget | Тимур Болатович | This week |
| Safety | Obtain legal opinion on claim against contractor | Айнур Каировна | Wednesday |

### Meeting 2

| Assignment | Owner | Deadline wording |
| --- | --- | --- |
| Prepare supplier delay claim | Ерлан, departmental lawyer | By end of week |
| Find an alternative raw-material supplier for comparison | Ботагоз Нурлановна | Two weeks |
| Meet contractors and agree schedule with checkpoints | Жандос Талгатович | This week |
| Submit short report after contractor meeting | Жандос Талгатович | After that meeting |
| Organize extra training groups or trainer and prepare estimate | Ерболат Мухтарович | One week for estimate |
| Notify contractors and update contract template | Салтанат Ерболовна | Not stated |

## Required reasoning cases

1. **Speaker and owner differ.** A chair issues instructions to other participants. The voice label cannot be copied into the assignee field.
2. **An owner may never speak.** Ерлан receives a task without a dialogue turn or speaker cluster.
3. **An owner can be an organization.** Preserve юридический департамент; do not invent a named lawyer.
4. **A deadline is negotiated.** Meeting 1 moves from two weeks to three weeks and specifies 15 October. Preserve the final agreement and its supporting turns.
5. **Recaps repeat assignments.** Consolidate repetitions; do not create duplicate tasks or let a general recap overwrite a more explicit owner assignment. In meeting 2, Ерлан remains the claim executor despite the final recap grouping the work under Ботагоз.
6. **Calendar context is missing.** Neither protocol states a meeting date or year. Preserve month/day and relative wording. File timestamps and the current date are not meeting dates.
7. **Some deadlines are dependencies.** A report after another meeting has an event deadline, not a known calendar day.
8. **Some deadlines are absent.** The contractor notice and template update have no stated due date.
9. **One row can contain several deliverables.** Training has a one-week estimate and a broader one-month goal in the dialogue. Preserve both, even though the reference row emphasizes the estimate.
10. **A duration can be part of the task.** Five working days is a proposed invoice-submission contract term, not the deadline for updating the template.
11. **Conditions are meaningful.** An external trainer is conditional; termination of a contractor is conditional on repeated breaches. Do not convert these into unconditional commitments.
12. **A suspicion is not a confirmed fact.** Formalistic safety briefings are suggested as a concern in the dialogue. The generated summary must preserve that uncertainty even if the supplied summary is stronger.

## Evaluation limitations

- Both written protocols are Russian. Kazakh names and an organization name do not make these Kazakh-language test sets.
- The protocols contain edited dialogue and answer tables, not verified verbatim transcripts with word/speaker timing labels.
- WER/CER and diarization error measurements require separately checked audio transcripts and speaker intervals. Do not report them from these documents alone.
- Extraction evaluation can start from the dialogue sections, excluding all supplied summary and assignment tables. Add stable turn IDs to evaluation fixtures.
- Compare semantic assignments, owners, deadline kinds and evidence. Exact wording or exactly 10/6 output rows is not a sufficient metric; valid grouping can vary.
- Add recorded Kazakh and mixed-language fixtures, including bilingual sentences, natural names, dates and numbers. At least one unseen recording must be held out from prompt tuning.

## Additional user-provided information

- Required stack: Python FastAPI, React, Docker Compose.
- Target: a comprehensive implementation sprint lasting five hours; hardware will be arranged by the team.
- ASR: Tilqazyna `til-asr`, a Kazakh/Russian FastConformer recognition stage followed by punctuation, according to the supplied 18 August 2026 integration document.
- Contract: multipart `POST /v1/audio/transcriptions`, `file`, `model=til-asr`, `words=true`; response contains `duration_seconds`, `text`, and `words[{word,start,end}]` in global seconds. Speaker labels and live streaming were not documented.
- Documented formats: WAV, MP3, M4A, OGG, FLAC. The provider describes internal long-recording chunking and recommends a long client timeout; use a configurable 900-second read timeout initially.
- Provider-reported throughput and unlimited production quotas are unverified claims, not project measurements. Sandbox quota is documented as 10 requests/minute.
- A `qwen` model alias is listed for text tasks. Its precise chat contract, JSON-schema behavior, model revision and private deployment availability still need confirmation.
- Public provider URL: `https://router.tilqazyna.kz/v1`. The user explicitly confirmed on 23 September 2026 that organizers approved using the hosted API. This is the demo plan; availability of private model deployment artifacts remains unverified.
- Credentials from the conversation are intentionally excluded. Do not copy them into source, fixtures, logs, examples or documentation.
