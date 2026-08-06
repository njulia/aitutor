# End-to-end testing

Run browser tests against a disposable local or staging deployment with test-mode billing. Use a new parent account for each destructive journey.

Release-critical journeys:

1. Register and sign in as a parent.
2. Add, rename and switch between multiple children.
3. Copy a child code, sign in as that child, and confirm sibling data is inaccessible.
4. Generate work, submit answers, use **Read it to me**, and verify progress and XP.
5. Review the child's own progress, reward balance, quests and certificates.
6. Return to the parent account and review every child's progress and pending rewards.
7. Start the free 11+ diagnostic mock, submit it once, and reject a changed or expired attempt token.
8. Start test-mode checkout, receive the signed webhook, verify entitlement, then cancel through the portal.
9. Confirm public landing pages have canonical URLs while account, child, progress and reward pages are not indexed.

Test speech on at least one Chromium browser and Safari/iOS where available. Speech output uses the device's installed voice and therefore should be verified by an audible start, stop and replay rather than by voice name.
