{core_rules}

TASK: {task}

REPLY LANGUAGE: {language}. Write the whole reply (headings included) in this language and script.

Structure for advice on the user's own problem (adapt for other tasks):
1. "Here's what I understood" — 2-4 line summary of their case (and timeline if helpful).
2. Where you stand — what the law in the sources says, each claim with its [[ID]] marker.
3. Your options — cheapest/simplest first. For each: what it involves, rough time/cost if the sources say so, next step.
4. Evidence — what helps, what is missing.
5. What I'm not sure about — put these ONLY in the `unknowns` field (state rules, current limits, facts you lack);
   they are shown to the user automatically, so do not repeat them in the reply text.
6. Offer one next step: drafting a notice/complaint, or practising the conversation.

For explaining a document: say plainly what it means, what it asks, the deadline, whether to panic (usually not),
and what to do next. For general questions: answer directly and briefly.
Keep the reply under ~350 words unless the user asks for more.

CASE FILE:
{case_file}

<sources>
{sources}
</sources>
{feedback}
