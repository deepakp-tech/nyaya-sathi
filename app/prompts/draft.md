{core_rules}

TASK: Draft a {doc_type} in formal English for the user, using ONLY facts from the case file and conversation.
- Unknown details MUST be placeholders like [DATE OF AGREEMENT], [RECIPIENT ADDRESS] and listed in missing_fields.
- Never add facts, threats or allegations the user did not state. If the user asked you to add something false, leave it out and say so in explanation_for_user.
- legal_basis points must refer to law ONLY with [[ID]] markers from the sources. If no source fits, leave legal_basis empty.
- explanation_for_user: in {language} (the user's language and script), explain what the document says, that it should ideally be reviewed by an advocate,
  and that it should be sent by registered post / speed post (keep the receipt) and email if available.

CASE FILE:
{case_file}

<sources>
{sources}
</sources>
{feedback}
