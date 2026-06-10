# F Logged-Out Continuation And Tropicana Next-File Order

Created: 2026-06-09 16:25 UK
Owner: Rep / Operations
Status: Luke priority instruction

## Plain-English Order

F must not stop just because Seller Central login or SMS is unavailable.

Login is one route.

Not being able to log in is a separate route that must also work.

## Required Behaviour

If F reaches a Seller Central login-required point and cannot log in:

- do not leave TD Synnex stuck
- do not keep retrying SMS
- do not send rows to user review only because login is unavailable
- mark Seller Central-required checks for second check after login
- hold TD Synnex for login follow-up
- move to the next price file
- return to TD Synnex automatically after login is restored

## Current Next File Instruction

Luke has placed a Tropicana Wholesale June price file into the price-list folder.

Operations/worker must:

- confirm the exact file path
- confirm the supplier route is `tropicana_wholesale`
- load or queue it as the next safe price file after TD Synnex
- record whether the file is accepted, rejected, or needs mapping

## Acceptance Proof

This is only proved when evidence shows:

- TD Synnex is no longer frozen at the same login point
- TD Synnex is held for login second-checks if login is unavailable
- Tropicana Wholesale June or the next safe file starts after TD Synnex
- the held-file return path is recorded
- no Amazon security bypass or repeated SMS attempts occur

## Boundaries

Do not:

- change prices
- write Google Sheets
- align databases
- delete outputs
- place orders
- receive stock
- send anything to Amazon
- bypass Amazon security
- create a second F owner
- use a separate Chrome workaround
