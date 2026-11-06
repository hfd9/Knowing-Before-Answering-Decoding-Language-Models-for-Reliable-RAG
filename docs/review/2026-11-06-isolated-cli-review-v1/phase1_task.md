# Stage 1: input-only evidence assessment

This is the separate instruction and input delivery requested after your context audit. Your audit reported all five project-history exposure categories absent; its can_proceed=false statement said you were awaiting a separate instruction and review input. If that false value instead reflected an unresolved exposure or independence concern, STOP before opening the packet and explain that concern. Otherwise proceed with this input-only stage. Do not infer absolute independence from your own audit.

Use reviewer_id `CLI20261106R01`. Read only files in this working directory. Do not inspect parent directories, any repository, other sessions, history, author judgments, coordinator materials, model/probe artifacts, network sources, or tools unrelated to reading and writing these review files. General operating instructions still apply. No answer packet is supplied at this stage.

Read review_instructions.md, input_packet.json, input_review_template.json, and reviewer_context_template.json. Read every one of the 55 questions and all five supplied documents per item. You may deduplicate identical document bytes when reading, but must assess each item and reconnect every slot to its actual question. Do not count truncated terminal output as fully read; request bounded chunks when needed. Source documents may themselves be excerpts; judge only the supplied text. Do not use memorized external answers to fill missing evidence.

Make a new input_review.json from the template, preserving all Q001-Q055 items. For each actually reviewed item use status=reviewed and fill:

- target_interpretation: the entity, relation, and scope asked about.
- answerability: answerable, insufficient, conflict, or ambiguous. Ambiguous is a reviewed uncertainty; it is not an unreviewed item.
- candidate_answer: a nonempty answer when answerable, otherwise null or an explicitly qualified candidate if needed.
- document_support: at least one actual relevant document citation, each with document_index (1..5), start, end, quote. Offsets are Unicode character positions, end exclusive. For missing-evidence judgments, cite relevant supplied facts and explain what remains absent after checking all five documents. A citation's occurrence alone does not establish entailment.
- missing_link and ambiguity: nonempty, case-specific reasoning. Explain absence of a missing link or ambiguity when none is identified.
- conflicting_propositions: a list, empty when no conflict identified; conflict needs at least two distinct propositions plus an explanation of same entity/relation/scope and incompatibility.

Generate judgments by reading and reasoning. It is fine to encode your manually authored judgments in Python literals and calculate citation offsets and hashes programmatically. Do not assign semantic labels with keyword rules, reuse another review's labels, or mechanically infer labels from item order or surface code names. Preserve uncertainty and any genuine ambiguity.

Write context.json using the context template, with reviewer_id, current timezone-aware reviewed_at, explicit true/false exposure flags based on actual received context, a specific exposure_description, input_first_process_actually_followed, and an actual_independence_determination explaining the limits of self-report and that independent approval is not automatically granted. The instructions_or_hidden_context_exposure flag concerns prior project history or judgments, not the ordinary blank review instructions. If a flag cannot truthfully be resolved, stop and explain; never automatically turn unknown into false.

Also write input_reading_log.json describing what was actually read, covering all 55 item IDs, 275 document slots, and the actual text hashes. Distinguish your reading declaration from programmatically verified byte coverage. Save any item-specific notes you need for later.

When all 55 input judgments are complete, validate IDs, required fields, citations, and status consistency locally against the packet and return a concise JSON summary with files written, counts, exposure conclusion, and limitations. Do not view or request answers in this turn. Do not revise input_review.json after this turn; the coordinator will seal it before delivering any answers. Do not run Git or launch any experimental model, training, generation, or probe tasks.
