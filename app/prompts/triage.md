Classify the user's latest message in the context of the conversation.

Covered categories: tenancy, consumer, employment. Anything else (divorce, family, criminal defence, tax,
property title, immigration, company law...) is out_of_scope. Use "unclear" if you cannot tell yet.

Modes:
- advise: the user describes their own problem and wants to know where they stand / what to do
- general_question: a general question about law/procedure, not about their specific facts
- explain_document: they pasted or describe a notice/letter/document and want it explained
- draft: they ask you to write a notice, complaint, reply or application
- roleplay: they want to practise arguing (or are continuing a practice session)
- roleplay_feedback: they want to stop practising and get feedback
- chit_chat: greetings or questions about you

Currently active mode from previous turn: {active_mode}

Red flags: emergency (safety at risk), criminal (police/FIR/arrest/criminal complaint), court_case (summons,
hearing date, case filed, legal notice with deadline against the user), large_amount (above ~Rs 20 lakh or property),
deadline_risk (events years ago, time limit may have passed), complex (many parties, insolvency, etc.).
