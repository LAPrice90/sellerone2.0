# SO21 Worker Utilisation Rule

Updated: 2026-06-09 15:27 UK
Owner: Rep / Operations

## Problem

Luke observed that workers were only active in short bursts, with long quiet gaps between Operations checks.

This means the system was not behaving like a team of employees. It was behaving like a periodic check-in.

## New Rule

Active means recent movement, not just an assigned packet.

Operations must track:

- active worker or reviewer
- assigned packet
- last visible movement
- current state
- next action

## Quiet Worker Rule

If a worker or reviewer is quiet for one Operations pass:

- send a focused nudge

If still quiet on the next Operations pass:

- mark it blocked with exact reason, or
- replace it with a fresh bounded worker if safe

If a lane finishes:

- close or review it immediately
- refill the lane with the next safe packet

## Cadence Change

The Operations monitor has been tightened from a 15-minute heartbeat to a 2-minute heartbeat.

Purpose:

- reduce dead air
- catch quiet workers faster
- keep reviewer closure moving
- refill safe lanes sooner

## Lane Standard

Operations should normally keep these moving when safe:

- one emergency/runtime lane if needed
- one to two control/proof workers
- one to two reviewers
- one read-only MOT/diagnosis or planning lane

## Forbidden Drift

Higher cadence does not approve protected work.

Still forbidden without separate approval:

- Amazon security bypass
- repeated SMS, phone, or code attempts
- price changes
- Sheet writes
- database alignment
- output deletion
- permanent Task Scheduler changes
- destructive cleanup
- second owner for the same live runtime
- unbounded runtime restart
