# Stage 2: answer and atomic-claim evidence assessment

Continue as reviewer_id `CLI20261106R01` in this same session. Stage 1 is complete. The coordinator has now sealed the exact input_review.json and only afterward delivered output_packet.json and claim_review_template.json. Before reading answers, check input_seal.json against the byte hash of input_review.json; if the hash differs, STOP and report it. Preserve input_review.json, context.json, input_reading_log.json and all stage-1 files byte-for-byte. Do not revise input judgments after seeing answers. Any later reconsideration must be a separately disclosed note and must not alter the sealed input file.

Read only this working directory, as in stage 1. Do not access a repository, parent folders, other sessions, project history, author judgments, coordinator mappings, external sources or network tools. No author labels or coordinator comparisons have been supplied. General operating instructions still apply. The designated answer packet is now permitted; reading it in this second stage is not prior-output exposure before input sealing. Report any other actual exposure honestly, and retain the limits of your context self-report.

Read all 55 complete original answers and reconnect them to their questions and all five supplied documents. Check the source candidate_sentence_units; these are only mechanical text spans, not pre-split atomic claims. Do not treat a terminal output that is truncated as complete reading. Do not use external knowledge to supply missing evidence.

Produce claim_review.json from the supplied template with reviewer_id, sealed_input_review_sha256 and sealed_input_review_completed_at taken exactly from input_seal.json. Preserve all 55 item IDs, all original unit_id and source_span objects, and all their fields and hashes exactly. For reviewed items set status=reviewed and full_answer_claim_coverage_confirmed=true only after actually covering the full answer.

For each unit, leave its document_support, counterevidence, missing_link, ambiguity and judgment summary fields null. Replace atomic_claims=null with a nonempty list of separate manually reasoned semantic claims. Each atomic claim must contain:

- claim_id: nonempty and unique within the item.
- claim: one independently assessable proposition; split compounds and distinct scopes when they can differ in support.
- judgment: supported, contradicted, unsupported, ambiguous or not_applicable.
- role: target or explanation. A response not providing the requested specific target answer must have no target-role atoms; assess its substantive supplied facts and reasons as explanation atoms.
- output_citation: start, end, quote, wholly within this unit's original source_span; Unicode offsets, end exclusive.
- document_support and counterevidence: lists of exact supplied document citations with document_index, start, end, quote. Supported requires at least one support citation. Contradicted requires at least one counterevidence citation. Citation matching alone does not prove entailment or contradiction.
- missing_link and ambiguity: nonempty case-specific reasoning, also explaining when no missing premise or material ambiguity is identified.

Judge the target answer and explanation separately. Per item fill:

- gives_specific_target_answer: a boolean, based on the requested relation/scope and what the response actually provides. Explain a partial or compound-answer interpretation in the claim reasoning rather than guessing from word overlap.
- target_claim_supported: not_applicable when no specific target answer is supplied; otherwise summarize the target atoms using contradicted before unsupported before ambiguous before supported. No target atom may be not_applicable when a target is supplied.
- withholding_matches_gap: not_applicable if a specific target is supplied; otherwise supported, contradicted, unsupported or ambiguous, based on whether the stated withholding matches the actual evidence gap.
- explanation_all_claims_supported: no if any applicable explanation atom is unsupported or contradicted; otherwise ambiguous if any is ambiguous; yes if all applicable explanation atoms are supported; not_applicable if there are no applicable explanation atoms.

An accurate answer or appropriate withholding does not establish that the rest of the explanation is supported. For an absence or conflict assertion check all five documents; distinguish absent requested evidence from absence of all relevant information. For a conflict, identify actual mutually incompatible propositions on the same entity, relation and scope; an unfamiliar name or different attribute is not by itself a contradiction. These are generic scoring requirements, not labels for any item. Keep genuine ambiguity, and do not infer claims from prior author results, item order, code-name patterns or keyword-based rules.

You may encode manually authored claims in Python literals and compute quote offsets, hashes and label reductions programmatically. Do not mechanically label sentences by keywords or simply copy an entire compound sentence into one atom when its parts can differ in support. Confirm semantic coverage explicitly; mechanical sentence coverage is a separate check.

Write output_context.json as an updated context declaration with a current timezone-aware reviewed_at after the answer review. Preserve the stage-1 context.json. Keep the input-first statement truthful, describe the allowed second-stage answer exposure, and do not claim automatic independent approval.

Also save output_reading_log.json (all 55 answer IDs, complete text hashes, original unit mappings and reading declarations) and output_validation_report.json. Validate source spans, every citation, item coverage, atom IDs/fields, support/counterevidence requirements, target applicability and summary reductions, plus the unchanged sealed input SHA256. Save any manually authored review program as provenance. Return a concise JSON summary with actual counts, files, exposure limitations and validation outcome when all 55 answers are complete. Do not read or produce any author comparison, run Git, or launch an experimental model, probe, training or new-answer task.
