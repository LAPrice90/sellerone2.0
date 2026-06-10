# A Hourly Blocking F Approval

Created: 2026-06-09 21:21 UK
Owner: Rep / Operations
Status: Luke approved bounded action when blocking F

## Plain-English Decision

Luke approved action on hourly A if it blocks F.

This does not approve broad A redesign tonight.

It does approve removing `AMZ Pricing Summary Hourly` as an F blocker when it prevents the F emergency lane from moving.

## Approved Tonight

If `AMZ Pricing Summary Hourly` blocks F:

- keep or place the hourly task on bounded hold
- do not touch the daily `AMZ Pricing Summary` 06:00 task
- do not start a full A review project while F is unfinished
- route F repair/proof as soon as A is clear
- record restore or morning recovery state by 07:00 UK

## Not Approved Tonight

Do not:

- permanently delete the hourly task
- redesign A scheduler live during the F emergency
- change daily A
- change prices
- write Sheets
- align databases
- delete outputs
- place orders
- receive stock
- send anything to Amazon
- bypass Amazon security

## Future Design

The proper replacement is:

- `A-HOURLY-READ-ONLY-DATA-WATCH`

This should replace hourly full A with a read-only data checker that does not use maintenance mode.

Build only after F is under control, unless hourly A directly blocks F again.
