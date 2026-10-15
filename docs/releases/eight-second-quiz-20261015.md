# Eight-second post-narration answer window — staging

Merged PR #43: change the server-authoritative 10-second response window to 8 seconds on all 15 questions, preserving each Q01–Q15 recording duration and synchronization grace period. Update client countdown and last-three-second urgency, question metadata and timing tests.

Both Game smoke tests and Browser proof passed on the PR head before merge. This commit requests publishing to the existing staging Worker only, not production.
